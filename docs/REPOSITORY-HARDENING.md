# Repository hardening checklist

Configure these controls after publication. They cannot be enforced from repository files alone.

## Main branch ruleset

- Require pull requests before merge.
- Require at least one approving review.
- Require Code Owner review for governance, schemas, scripts, and workflows.
- Dismiss stale approvals when new commits are pushed.
- Require approval of the most recent push by someone other than its author.
- Require the `validate` status check.
- Require conversation resolution.
- Block force pushes and branch deletion.
- Apply rules to administrators when practical.
- Require signed commits or signed release tags according to contributor workflow.

## Actions policy

- Allow only required actions.
- Require actions to be pinned to full commit SHAs.
- Keep default workflow token permissions read-only.
- Do not expose repository or provider secrets to pull-request workflows.
- Review Dependabot changes to action SHAs before merging.

## Security features

- Enable private vulnerability reporting.
- Enable secret scanning and push protection.
- Enable dependency graph, Dependabot alerts, and security updates.
- Enable CodeQL if executable runtime code grows beyond the current validators.
- Periodically run OpenSSF Scorecard after the public repository is stable.

## Releases

- Publish tagged releases from reviewed commits.
- Rebuild deterministic `.skill` archives in CI.
- Compare generated packages with committed sources.
- Publish `SHA256SUMS` with release assets.
- Add build provenance or signed attestations when release automation is introduced.
- Generate an SBOM for validator dependencies and published archives when release automation is introduced.
