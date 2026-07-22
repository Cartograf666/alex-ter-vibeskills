# Stage Map

Derive the current stage from repository evidence. A stage counts as done only when its artifact exists, validates, and carries the approval its owning skill requires.

## Detection order

Evaluate top to bottom. Stop at the first `UNSATISFIED` stage; that is the current position.

| # | Stage | Satisfied when | Route to when unsatisfied |
|---|---|---|---|
| 1 | Project architecture documented | `.ai/architecture.yaml` exists and validates as approved | `architecture-governance` in `BOOTSTRAP_EXISTING` for an existing codebase, `BOOTSTRAP_GREENFIELD` before first implementation |
| 2 | Design system documented | `.ai/design-system.yaml` exists and validates as approved, or the product has no user interface | `design-system-governance` in `DISCOVER_EXISTING`, then `SELECT_FOUNDATION` only when nothing usable exists |
| 3 | Material decisions resolved | a current `.ai/discovery/<slug>-decision-brief.md` exists, or preparation legitimately began with `discovery_mode: direct` | `grill-requirements` |
| 4 | Development contract drafted | `.ai/specs/<slug>/development-contract.yaml` exists with its PRD, and a Technical Brief unless its omission is recorded | `prepare-development-cycle` |
| 5 | Contract approved | `status: approved`, `implementation_authorized: true`, and `validate_contract.py` passes | the user approves through `scripts/approve_contract.py`; this is a human action, not a routing action |
| 6 | Implementation run executed | `.ai/runs/<run-id>.yaml` exists and validates against the approved contract | `run-verified-development-loop` |
| 7 | Terminal outcome handled | the run reached `ACCEPT`, `VERIFIED_NOT_ATTESTED`, or `READY_FOR_HUMAN_REVIEW` and the user acted on it | independent human review, merge, or a further run for the remaining work |

Stages 1 and 2 are project-level and run once, then again only when a governed boundary changes. Stages 3 through 7 repeat per task slug.

## Project shape

For a new project, stage 1 precedes preparation because a provisional architecture must exist before implementation is authorized.

For an existing codebase, run stage 1 in `BOOTSTRAP_EXISTING` so current violations are baselined rather than refactored. Do not route an existing project into a broad cleanup unless the user explicitly authorizes refactoring.

Treat stage 2 as `NOT_APPLICABLE` when the task produces no user interface and no generated visual artifact. Record the reason instead of silently skipping it.

## Concurrent task slugs

Several slugs may occupy different stages at once. List each slug with its stage and evidence path, then ask which one to continue. Do not merge their positions into a single project-wide answer.

## Invalidated approval

An approved contract stops authorizing implementation when its PRD, Technical Brief, architecture inputs, RunSpec, Change Envelope, gates, budgets, provider policy, or test policy change. When document hashes no longer match, report stage 4 as current again and route back to `prepare-development-cycle`.

The same applies to a manifest: changing the payload of `.ai/architecture.yaml` or `.ai/design-system.yaml` returns it to provisional review and reopens stage 1 or 2.

## Governance re-entry

Route back to a governance skill mid-task when:

- implementation needs an undeclared layer, a deeper change, a new dependency direction, or a protected-interface change, which requires an Architecture Change Request from `architecture-governance`;
- UI work needs a new token, primitive, public component API, interaction pattern, or approved visual deviation, which requires `design-system-governance`;
- product intent or scope becomes materially unclear before approval, which requires `grill-requirements`.

Re-entry does not restart the pipeline. Report it as a bounded detour from the current stage and name the stage the work returns to.
