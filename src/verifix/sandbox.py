"""Execution sandbox for code under test: hermetic environment, network guard and resource limits.

Patched code and the repository's tests are untrusted. Before this module existed the test runner
passed the operator's full environment (API keys included) to that code. Now every subprocess that
executes repository code gets:

* an allowlisted environment (no credentials; ``HOME`` points at a private temp dir),
* a socket guard injected ahead of the code (``connect``/``getaddrinfo`` raise ``PermissionError``),
* POSIX resource limits (CPU seconds, address space, file size, open files, process count).

Limits are best-effort: ``resource`` is POSIX-only and some limits are refused by some kernels;
``apply_limits`` records what was actually applied so callers can report it truthfully.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Variables a Python test process legitimately needs. Everything else (API keys, tokens, AWS
# credentials, operator secrets) is withheld from code under test.
ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT", "TMPDIR")

# Python source executed before any repository code. It removes outbound networking from the
# interpreter. A determined native extension could bypass it; it stops ordinary Python code.
NETWORK_GUARD = r'''
import socket as _vfx_socket
def _vfx_blocked(*_a, **_k):
    raise PermissionError("VeriFix sandbox: network access is disabled for code under test")
for _vfx_name in ("connect", "connect_ex", "sendto"):
    setattr(_vfx_socket.socket, _vfx_name, _vfx_blocked)
_vfx_socket.create_connection = _vfx_blocked
_vfx_socket.getaddrinfo = _vfx_blocked
del _vfx_name
'''

DEFAULT_LIMITS = {
    "cpu_seconds": 60,
    "address_space_bytes": 1536 * 1024 * 1024,
    "file_size_bytes": 64 * 1024 * 1024,
    "open_files": 256,
}


def sandbox_env(pythonpath: list[str] | None = None, extra: dict[str, str] | None = None,
                hash_seed: str = "0") -> dict[str, str]:
    """Return an allowlisted environment for running untrusted repository code."""
    env = {k: os.environ[k] for k in ENV_ALLOWLIST if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin")
    home = Path(tempfile.gettempdir()) / "verifix_sandbox_home"
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONNOUSERSITE"] = "1"
    env["VERIFIX_SANDBOX"] = "1"
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    if extra:
        env.update(extra)
    return env


def apply_limits(limits: dict[str, int] | None = None) -> dict[str, Any]:
    """Apply POSIX rlimits to the current process (call in the child via ``preexec_fn``)."""
    applied: dict[str, Any] = {}
    try:
        import resource
    except ImportError:  # non-POSIX platform
        return {"available": False}
    spec = {**DEFAULT_LIMITS, **(limits or {})}
    table = {
        "cpu_seconds": resource.RLIMIT_CPU,
        "address_space_bytes": resource.RLIMIT_AS,
        "file_size_bytes": resource.RLIMIT_FSIZE,
        "open_files": resource.RLIMIT_NOFILE,
    }
    for key, rlim in table.items():
        value = int(spec[key])
        try:
            soft, hard = resource.getrlimit(rlim)
            new_hard = hard if hard != resource.RLIM_INFINITY and hard < value else value
            if hard == resource.RLIM_INFINITY:
                new_hard = value
            resource.setrlimit(rlim, (min(value, new_hard), new_hard))
            applied[key] = min(value, new_hard)
        except (ValueError, OSError) as exc:
            applied[key] = f"not applied: {exc.__class__.__name__}"
    return applied


def limits_preexec() -> Any:
    """``preexec_fn`` for ``subprocess`` on POSIX; ``None`` elsewhere."""
    if os.name != "posix":
        return None
    return lambda: apply_limits()


def guarded_python_command(code: str, *args: str, isolated_site: bool = False) -> list[str]:
    """Build ``python -c`` that installs the network guard before running ``code``."""
    flags = ["-B"] + (["-S"] if isolated_site else [])
    return [sys.executable, *flags, "-c", NETWORK_GUARD + "\n" + code, *args]
