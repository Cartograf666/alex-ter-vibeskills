# Handoff Contract

Use the bundled canonical schema:

```text
assets/development-contract.schema.json
```

The repository example at `examples/development-contract.yaml` illustrates a complete contract. Do not maintain an alternative producer-specific RunSpec.

## Required sections

- metadata and document depth;
- source PRD, optional Technical Brief with omission reason, architecture manifest, baseline, and applicable design-system manifest and Design Brief;
- RunSpec with every PRD acceptance ID and verification gate IDs;
- Change Envelope with component paths and change depth;
- reviewed or untrusted quality-gate commands with a non-empty resolved-input manifest, sandbox, network, secret, timeout, and approval policy;
- immutable acceptance-test ownership policy;
- explicit design applicability, approved system status, design acceptance, and required UI gate IDs;
- requested and effective automation modes, policy sources, retry/concurrency/tool/time/cost limits;
- interaction mode, progress cadence, interruption events, terminal goal, and resumability;
- provider routes by role, fallbacks, substitution, reviewer independence, and sensitive-code transfer policy;
- hash-bound approval.

## Validate before approval

From the toolkit repository:

```bash
python3 scripts/validate_contract.py .ai/specs/<slug>/development-contract.yaml
```

From a standalone installed skill, locate this skill directory and run its bundled validator with the bundled schema:

```bash
python3 <skill-dir>/scripts/validate_contract.py \
  .ai/specs/<slug>/development-contract.yaml \
  --schema <skill-dir>/assets/development-contract.schema.json
```

The validator checks schema conformance, unique IDs, complete PRD/RunSpec acceptance traceability, gate references and resolved input hashes, Technical Brief omission rules, component scope conflicts, most-restrictive automation policy, untrusted gate restrictions, document hashes, approval payload hash, and approval revision ancestry.

When design applies, every required design gate must exist in the approved design-system manifest and development contract and must be referenced by at least one RunSpec acceptance criterion.

## Approve

After the user explicitly approves the material summary:

```bash
python3 <skill-dir>/scripts/approve_contract.py \
  .ai/specs/<slug>/development-contract.yaml \
  --approved-by <stable-human-identity> \
  --method <local-confirmation|runtime-attestation> \
  --key-id <host-key-id> \
  --repository <repo-root>
```

Use runtime attestation for high/critical work. `local-confirmation` binds content but does not authenticate the named person.

`runtime-attestation` requires a trusted host to keep approval keys of at least 32 random bytes outside every model and tool context. Select a non-secret `--key-id`; provide a JSON keyring through `VIBESKILLS_APPROVAL_HMAC_KEYS` (the `default` key may use `VIBESKILLS_APPROVAL_HMAC_KEY`). Retain retired verification keys for historical audit and revoke compromised IDs. The approval script binds the selected key ID and secret to the contract payload, authority event, approver, and Git revision. If the validator cannot access that key, it fails closed. Never paste keys into a prompt, repository file, packet, or log.

Then validate again. Never preserve approval after changing PRD, Technical Brief, architecture inputs, RunSpec, Change Envelope, gates, budgets, provider policy, or test policy.

## Stable identifiers

Do not renumber approved IDs. Behavior changes return to preparation and produce a new contract version or explicit superseding decision.
