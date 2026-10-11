# Supply-chain integrity

VeriFix asks the code it patches to prove itself, so its own releases are held to the same standard.
Everything below runs in CI (`.github/workflows/ui-quality.yml`, job `supply-chain`) and can be
reproduced locally with `python scripts/supply_chain.py <command>`.

| Control | How it works | Evidence |
| --- | --- | --- |
| **Lockfile integrity** | `requirements-runtime.hashes.lock` lists every PyPI file digest for all 104 pinned packages (1,754 SHA-256 digests). CI installs with `pip install --require-hashes`. `verify-lock` fails if the hashed lock drifts from the plain lock. | Local check: the full install succeeds; a single wrong digest makes pip refuse with "THESE PACKAGES DO NOT MATCH THE HASHES". |
| **SCA (OSV)** | `sca` queries `api.osv.dev` for every pin. HIGH, CRITICAL and UNKNOWN severity findings fail the build unless `quality/supply-chain/vuln_allowlist.json` accepts them with a justification and an expiry date. | 0 findings on 2026-10-11. Positive control: `requests==2.19.0` plus `pyyaml==5.3` yields 14 findings and the policy blocks. |
| **SBOM** | `sbom` writes CycloneDX 1.5 JSON with purls, every file digest and licences. The serial number is content-derived, so the SBOM itself is reproducible. | `artifacts/supply-chain/sbom.cdx.json` |
| **Reproducible builds** | `deterministic_zip` uses sorted members, fixed timestamps (1980-01-01), fixed modes and fixed compression. `reproduce` builds twice, in opposite member order, and compares the digests. | Identical digests locally and in CI. |
| **SLSA provenance / in-toto** | `provenance` emits an in-toto Statement v1 with a `https://slsa.dev/provenance/v1` predicate. It binds the bundle digest to the git commit and to the digests of both lock files. On `main`, `actions/attest-build-provenance` signs the bundle with Sigstore (GitHub artifact attestations). | Verify with `gh attestation verify verifix-release.zip --repo shivanshjain456/neatHack` |
| **Verify before deploy** | `scripts/deploy_ui_release.py` builds the code bundle deterministically and writes provenance, then runs `verify_provenance`. Deployment is refused if the subject digest, the commit or the material digests do not match, or if tracked source is dirty. Secrets are added only *after* attestation and never appear in the attested bundle. | `artifacts/supply-chain/deploy-provenance.intoto.json` |
| **Artifact digest pinning** | Every GitHub Action is pinned to a full 40-hex commit SHA; `pins` fails CI on any tag reference. | `tests/test_supply_chain.py::test_every_github_action_is_pinned_to_a_commit_sha` |
| **Immutable audit trail** | Every agent run appends one record to `.verifix_runtime/audit_ledger.jsonl`. The record carries the status, the final diff digest and the digests of the assurance reports. Records are hash-chained (`hash = sha256(prev ‖ canonical_json(body))`), so any edit, deletion or reorder is reported at its index. Truncation is caught against a published head hash. | `tests/test_supply_chain.py::test_audit_ledger_chain_verifies_and_detects_tampering` |

## Build type `lambda-zip-v1`

The bundle contains `src/verifix` (as `verifix/`), `scripts/`, `benchmarks/`, `docs/`, `quality/`,
`README.md`, `pyproject.toml`, both lock files, `BUSINESS_PLAN.md` and `QUALITY_REPORT.md`.
`__pycache__` and `*.pyc` files are excluded. External parameters are the repository URL and the
commit. Resolved dependencies are the commit plus the SHA-256 digests of both lock files.

## Limits (stated plainly)

* Local deploy provenance is produced by the operator's machine. It is unsigned and corresponds to
  SLSA Build L1. The CI attestation is signed by GitHub's Sigstore instance and isolated by the
  hosted runner, which corresponds to Build L2.
* The Lambda deployment zip also carries third-party wheels downloaded for manylinux. Those are
  pinned by the hashed lock, but the zip containing them is attested only on the deploy path, not
  in CI.
