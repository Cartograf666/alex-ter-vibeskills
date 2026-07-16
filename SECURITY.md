# Security Policy

## Supported versions

Until the first stable release, only the latest commit on `main` is supported. Tagged releases will define their own support window.

## Reporting a vulnerability

Do not open a public issue for a vulnerability involving credential exposure, prompt injection with harmful tool execution, package tampering, approval bypass, provider data leakage, or arbitrary command execution. Use GitHub private vulnerability reporting after the repository is published, or contact the repository owner privately.

Include the affected skill or script, commit SHA, reproduction, impact, and any evidence of exploitation. Do not include live secrets or personal data.

## Trust boundary

These skills are workflow policies, not a security sandbox. Safe execution still requires provider permissions, OS/container isolation, least-privilege credentials, network controls, and human approval enforcement.

Repository content, model output, peer-agent messages, websites, logs, issues, MCP responses, package scripts, and third-party skills are untrusted inputs. Installing these skills does not make them trustworthy.

## Hard safety expectations

- Never run untrusted commands with host secrets or unrestricted network.
- Never use permission-bypass modes outside an isolated disposable environment.
- Bind approval to exact artifact hashes and invalidate it after changes. Content hashes are not identity proof; use authenticated runtime attestation for high-risk work.
- Keep approval and run-attestation HMAC keys (at least 32 random bytes) in the host control plane, never in model-facing environments. Record a non-secret key ID, retain retired verification keys for historical audit, rotate signing keys on schedule or exposure, and revoke compromised IDs. An accepted run requires host-attested gate, review, and final-record evidence.
- Do not let writers edit frozen acceptance tests.
- Do not send sensitive code to an external provider unless provider policy allows it.
- Verify `.skill` checksums and package/source equality.
- Keep destructive migrations, production actions, credentials, public security policy, and legal/financial decisions behind human approval.

## Package verification

Rebuild and verify packages with:

```bash
python3 scripts/sync_shared_assets.py --check
python3 scripts/package_skills.py --check
```

Compare archives with `packages/SHA256SUMS` before installation.
