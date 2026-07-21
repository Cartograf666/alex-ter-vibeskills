---
name: design-system-governance
description: Discover, select, document, extend, and enforce a product design system through design tokens, component contracts, responsive behavior, interaction states, content rules, accessibility, visual evidence, and deterministic UI quality gates. Use when starting a UI product, preparing a frontend feature, choosing a component system or visual direction, auditing an existing interface, preventing one-off styling, or reviewing whether implementation follows the approved design language.
---

# Govern Product Design

Treat design as an implementation contract, not final-stage decoration. Reuse an existing approved system before proposing a new one.

## Respond in the user's language

Detect the user's language from their messages and use it for all prose addressed to them: questions, explanations, recommendations, status, and the closing summary. Keep every machine token verbatim — code, commands, file paths, schema field names, stable IDs, and the status or verdict values this skill returns — and convey their meaning in the surrounding prose rather than translating the tokens. If the user's language is unclear, ask once, then continue in the chosen language.

Persisted artifacts are contracts, not chat. Keep their template headings, YAML keys, stable IDs, and status tokens exactly as specified so downstream skills and validators keep working. Narrative content inside an artifact may follow the user's language when the user asks for it.

## Load references and assets

- Read [discovery-and-audit.md](references/discovery-and-audit.md) before concluding whether a system exists.
- Read [selection-interview.md](references/selection-interview.md) only when no usable system is available.
- Read [current-system-catalog.md](references/current-system-catalog.md) before recommending a starting system; verify linked official documentation because ecosystems change.
- Read [design-quality-gates.md](references/design-quality-gates.md) before creating a development contract or accepting UI work.
- Copy [design-system-template.yaml](assets/design-system-template.yaml) to `.ai/design-system.yaml` when documenting or adopting a project system.
- Copy [design-brief-template.md](assets/design-brief-template.md) to the task specification directory for material UI work.
- Validate and approve the manifest with bundled `scripts/validate_design_system.py` and `scripts/approve_design_system.py`.
- Install the hash-locked validator dependencies with `python3 -m pip install --require-hashes -r requirements.txt` in a shell-capable host.

## Choose an operating mode

- `DISCOVER_EXISTING`: find the real system, tokens, libraries, and patterns;
- `SELECT_FOUNDATION`: conduct a one-question-at-a-time selection interview;
- `BOOTSTRAP_SYSTEM`: create a provisional manifest and initial token/component contracts;
- `PLAN_FEATURE`: create a task Design Brief and design acceptance criteria;
- `ENFORCE_IMPLEMENTATION`: detect hardcoded values, one-off components, missing states, and responsive or accessibility gaps;
- `REVIEW_DESIGN`: review UI evidence without implementing.

## Discover before selecting

Inspect Figma or other design sources when connected, repository instructions, token files, theme configuration, CSS variables, component libraries, Storybook or equivalent, screenshots, product surfaces, accessibility tests, visual regression configuration, and recurring patterns.

Classify the result:

- `APPROVED_EXISTING`: documented and authoritative;
- `OBSERVED_EXISTING`: consistently implemented but not approved;
- `PARTIAL`: useful tokens or components exist but important contracts are missing;
- `ABSENT`: no coherent reusable system exists;
- `NOT_APPLICABLE`: the task has no user interface or generated visual artifact.

Never replace an existing system merely because another system is fashionable. Propose migration separately with cost, compatibility, and rollout consequences.

## Select only when needed

When classification is `ABSENT`, use the selection interview. Ask exactly one question at a time and recommend an answer based on platform, product type, framework, density, brand maturity, accessibility, localization, and maintenance capacity.

Separate two decisions:

1. component and interaction foundation;
2. visual direction layered through tokens.

Do not equate a theme gallery or visual trend with a complete design system. Preserve hard boundaries for contrast, reduced motion, keyboard access, readable typography, touch targets, localization, and responsive behavior.

## Define the system contract

The manifest must identify:

- source and version of the adopted or custom system;
- token source paths and required token categories;
- component source and registry or documentation paths;
- component variants, sizes, states, and composition rules;
- typography, icon, illustration, color-mode, density, and content conventions;
- responsive breakpoints and layout behavior;
- motion tokens and reduced-motion behavior;
- WCAG target and keyboard, focus, semantics, contrast, zoom, and touch requirements;
- deterministic design, accessibility, and visual-regression gate IDs;
- approval bound to the exact manifest payload.

Approval also binds the bytes of declared token, component-registry, and documentation paths. Changing them invalidates the system approval and requires an intentional reviewed update.

Mark a new manifest `provisional`. Do not present an inferred visual language as approved.

## Govern feature work

For every material UI task, add a Design Brief containing:

- affected journeys, screens, viewport classes, and content states;
- reused components and justified extensions;
- loading, empty, error, disabled, success, permission, offline, and destructive states where relevant;
- keyboard, focus, screen-reader, contrast, zoom, localization, and reduced-motion expectations;
- visual references or approved prototypes;
- criterion-to-gate evidence mapping.

Require an Architecture Change Request for structural layer expansion and a Design System Change Request for new tokens, primitives, public component APIs, interaction patterns, or intentional system deviations.

## Enforce implementation

Block acceptance when implementation:

- duplicates an existing component without justification;
- introduces arbitrary colors, spacing, type, radius, shadow, z-index, or motion instead of tokens;
- omits required variants or interaction states;
- matches one screenshot but fails other viewports or content lengths;
- weakens focus, semantics, keyboard use, contrast, zoom, reduced motion, or touch behavior;
- changes approved snapshots without mapped product/design intent;
- claims design conformance without retained visual and accessibility evidence.

Use deterministic tools for token, lint, accessibility, build, and screenshot comparisons. Use human or model visual review for hierarchy, clarity, brand fit, and semantic quality that tools cannot decide.

## Return a verdict

Return one of:

- `DESIGN_READY`: manifest or task brief is approved and verifiable;
- `DESIGN_NOT_READY`: give the single highest-leverage missing decision or artifact;
- `DESIGN_REVIEW_APPROVE`: implementation conforms;
- `DESIGN_REVIEW_BLOCK`: list evidence-bound deviations;
- `NOT_APPLICABLE`: record the reason and require no design gates.

## Summarize what you did

After returning the outcome, close with a short summary in the user's language that states:

- what you did and what it decided or produced;
- the status or verdict you returned and what it means for the user;
- where each created or updated file now lives, by exact repository path;
- the recommended next step.

Name file locations explicitly and never claim a file was written that was not. When repository writes were unavailable and the output was returned in chat only, say so and name where it should be persisted.

This skill normally writes:

- `.ai/design-system.yaml` — the design-system manifest;
- the task `DESIGN-BRIEF.md` in the task specification directory, for example `.ai/specs/<slug>/DESIGN-BRIEF.md`;
- any Design System Change Request document you created, at its repository path.
