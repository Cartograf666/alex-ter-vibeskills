# Contributing

Contributions should preserve the separation between decision interview, development preparation, architecture governance, and implementation execution.

Before opening a pull request:

```bash
python3 -m pip install --require-hashes -r requirements-lock.txt
python3 scripts/sync_shared_assets.py
python3 scripts/package_skills.py
python3 scripts/validate_repo.py
```

When changing a canonical schema or shared validator, run `sync_shared_assets.py` and commit generated standalone skill copies. When changing a skill, rebuild and commit the corresponding `.skill` archive and checksum manifest.

When changing Python dependencies, update `requirements-dev.txt`, regenerate `requirements-lock.txt` with `uv pip compile requirements-dev.txt --generate-hashes --output-file requirements-lock.txt`, and review every version and hash diff.

Add tests for contract semantics, approval invalidation, policy precedence, frozen test integrity, or packaging behavior when changing those areas. Security-sensitive changes should explain threat model and negative cases.

Do not weaken an invariant merely to make an example or package pass validation.
