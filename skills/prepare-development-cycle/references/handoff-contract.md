# Handoff Contract

Create `.ai/specs/<slug>/development-contract.yaml`:

```yaml
schema_version: 1
status: draft
implementation_authorized: false
document_depth: COMPACT_PRD

source_documents:
  prd: .ai/specs/example/PRD.md
  technical_brief: .ai/specs/example/TECHNICAL-BRIEF.md
  architecture_manifest: .ai/architecture.yaml
  architecture_baseline: .ai/architecture-baseline.yaml

run_spec:
  objective: Observable implementation outcome
  non_goals: []
  acceptance_criteria:
    - id: AC-1
      statement: Observable behavior
      verification: Named test, command, or inspection
  constraints: []
  compatibility_requirements: []
  verification_expectations: []
  risks: []
  human_approval_required_for: []

change_envelope:
  primary_layer: services
  allowed_layers:
    services:
      reason: Primary use-case implementation
      depth: full
    tests:
      reason: Acceptance coverage
      depth: full
  conditional_layers: {}
  forbidden_layers: []
  protected_interfaces: []
  architecture_acceptance: []

automation:
  mode: manual
  max_implementation_attempts: 3
  max_review_rounds: 2

approval:
  approved_by: null
  approved_at: null
```

After explicit approval, update `status`, `implementation_authorized`, and approval metadata. Stable acceptance IDs must not be renumbered during implementation. Changed behavior requires returning to preparation and recording a new decision.
