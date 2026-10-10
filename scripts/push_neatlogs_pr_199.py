#!/usr/bin/env python3
"""Push verified fix branch for neatlogs#199 to shivanshjain456/neatlogs and open PR."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from verifix.config import load_env_if_present


def main() -> int:
    load_env_if_present()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.stderr.write("Missing GITHUB_TOKEN\n")
        return 1

    fork_repo = "shivanshjain456/neatlogs"
    branch = "fix/masking-exporter-concurrent-pool-199"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    chk = httpx.get(f"https://api.github.com/repos/{fork_repo}", headers=headers, timeout=15.0)
    if chk.status_code != 200:
        print(f"Fork {fork_repo} not created yet (HTTP {chk.status_code}). Click 'Create fork' at https://github.com/neatlogs/neatlogs/fork first.")
        return 2

    work_dir = Path("/tmp/neatlogs_pr_199_work")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/neatlogs/neatlogs.git", str(work_dir)],
        check=True,
    )
    subprocess.run(["git", "-C", str(work_dir), "checkout", "-b", branch], check=True)

    diff_path = Path("/home/user/verifix/benchmarks/neatlogs_pr_199_patch.diff")
    subprocess.run(["git", "-C", str(work_dir), "apply", str(diff_path)], check=True)

    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.name", "Shivansh Jain"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.email", "shivanshjain456@users.noreply.github.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(work_dir), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(work_dir),
            "commit",
            "-m",
            "fix(masking): use deadline-bounded slot acquisition across shared _mask_pool (Fixes #199)",
        ],
        check=True,
    )

    remote_url = f"https://x-access-token:{token}@github.com/{fork_repo}.git"
    subprocess.run(
        ["git", "-C", str(work_dir), "push", "--force", remote_url, f"{branch}:{branch}"],
        check=True,
    )

    pr_body = Path("/home/user/verifix/REAL_OSS_BUG_REPORT_NEATLOGS.md").read_text(encoding="utf-8")
    pr_resp = httpx.post(
        "https://api.github.com/repos/neatlogs/neatlogs/pulls",
        headers=headers,
        json={
            "title": "fix(masking): use deadline-bounded slot acquisition across shared _mask_pool (Fixes #199)",
            "head": f"shivanshjain456:{branch}",
            "base": "main",
            "body": f"Fixes #199\n\n{pr_body}",
        },
        timeout=20.0,
    )
    compare_url = f"https://github.com/neatlogs/neatlogs/compare/main...shivanshjain456:neatlogs:{branch}?expand=1"
    if pr_resp.status_code in (200, 201):
        print("Opened PR:", pr_resp.json().get("html_url"))
    else:
        print("Pushed branch successfully! Open 1-click PR at:", compare_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
