# Run Contracts

## Contents

- RunSpec
- ChangeEnvelope
- TaskPacket
- FailurePacket
- ResultPacket
- ReviewVerdict
- State record

Use structured data when the provider supports JSON schemas or function calling. Otherwise preserve the same fields in Markdown.

## RunSpec

```json
{
  "run_id": "string",
  "objective": "observable outcome",
  "non_goals": ["explicit exclusion"],
  "acceptance_criteria": [
    {"id": "AC-1", "statement": "observable behavior", "verification": "test or inspection"}
  ],
  "constraints": ["compatibility, style, dependency, or scope constraint"],
  "protected_paths": ["paths that workers must not modify"],
  "verification_commands": ["repository-grounded command"],
  "risk_level": "low|medium|high",
  "human_approval_required_for": ["external or irreversible action"],
  "max_attempts": 3
}
```

## ChangeEnvelope

```json
{
  "primary_layer": "services",
  "allowed_layers": {
    "services": {"reason": "primary use case", "depth": "full"},
    "tests": {"reason": "acceptance coverage", "depth": "full"}
  },
  "conditional_layers": {
    "database": {"condition": "current schema is insufficient", "approval": "ask"}
  },
  "forbidden_layers": ["middleware"],
  "protected_interfaces": ["public_http_api"],
  "architecture_acceptance": ["transaction boundary remains in the service layer"]
}
```

## TaskPacket

Send one packet per work package:

```json
{
  "run_id": "RUN-001",
  "task_id": "AUTH-017",
  "objective": "Add refresh-token rotation",
  "depends_on": [],
  "allowed_paths": ["src/auth/**", "tests/auth/**"],
  "forbidden_paths": [".github/**", "migrations/**"],
  "primary_layer": "services",
  "allowed_layers": {"services": "full", "tests": "full"},
  "protected_interfaces": ["public_auth_api"],
  "acceptance_criteria": ["AC-1", "AC-2"],
  "relevant_evidence": [
    {"path": "src/auth/session.ts", "reason": "existing token pattern"}
  ],
  "verification_commands": ["npm run lint", "npm test -- auth"],
  "constraints": ["Do not add dependencies", "Do not weaken tests"],
  "attempt": 1
}
```

Keep packets small. Provide file paths and evidence summaries instead of the entire chat transcript.

## FailurePacket

```json
{
  "run_id": "RUN-001",
  "task_id": "AUTH-017",
  "attempt": 2,
  "failed_command": "npm test -- auth",
  "exit_code": 1,
  "failure_excerpt": "minimal relevant output",
  "violated_criterion": "AC-2",
  "changed_files": ["src/auth/refresh.ts"],
  "repair_constraint": "Fix the causal defect; do not change acceptance tests"
}
```

Do not dump unbounded logs into the next model call. Preserve full logs in the run record and provide the focused excerpt plus a path to the full artifact when available.

## ResultPacket

```json
{
  "run_id": "RUN-001",
  "task_id": "AUTH-017",
  "status": "completed|blocked|failed",
  "changed_files": ["src/auth/refresh.ts", "tests/auth/refresh.test.ts"],
  "changed_layers": ["services", "tests"],
  "architecture_decisions": [],
  "acceptance_coverage": [
    {"criterion": "AC-1", "evidence": "test name or inspection result"}
  ],
  "verification": [
    {"command": "npm test -- auth", "exit_code": 0, "summary": "24 passed"}
  ],
  "assumptions": [],
  "remaining_risks": [],
  "unrun_checks": []
}
```

## ReviewVerdict

```json
{
  "verdict": "APPROVE|BLOCK|NEEDS_HUMAN",
  "blocking_findings": [
    {
      "criterion": "AC-2",
      "location": "src/auth/refresh.ts:83",
      "evidence": "concrete failure or defect",
      "recommended_action": "smallest corrective action"
    }
  ],
  "non_blocking_findings": [],
  "missing_tests": [],
  "confidence": "low|medium|high"
}
```

Reject vague findings such as "could be cleaner" unless they point to a repository rule, acceptance criterion, or material maintenance risk.

## State record

Persist at least:

```yaml
run_id: RUN-001
state: VERIFY
active_task: AUTH-017
owner: sonnet-worker
attempt: 2
worktree: ../worktrees/RUN-001-AUTH-017
last_verified_commit: null
completed_criteria: [AC-1]
pending_criteria: [AC-2]
blocking_reason: null
```

Update state after every delegation, verification run, review verdict, and human decision. Use the state record rather than conversational memory as the source of truth for retry counts and completion.
