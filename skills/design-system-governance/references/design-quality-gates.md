# Design quality gates

Choose gates from repository evidence and list all resolved scripts/configuration in the development contract.

## Required classes for material UI work

- token/static check: reject undeclared hardcoded visual values and unsupported component imports;
- component tests: variants, states, keyboard behavior, and semantic contracts;
- automated accessibility: focused component and representative page checks;
- responsive interaction tests: required viewport classes, zoom/reflow, overflow, and long/localized content;
- visual regression: deterministic screenshots at named viewports and color modes;
- build/type/lint gates;
- focused visual review against the Design Brief and approved references.

Automated accessibility tools do not replace keyboard, screen-reader, focus-order, content, and human visual review.

## Evidence rules

- The approved manifest's `quality_gate_ids` is the set every UI contract must require. Adding a gate to the manifest requires re-approving the manifest and updating later contracts; a contract prepared earlier with a subset no longer validates and must be prepared again. Run records bound to such contracts also fail validation because run-record validation calls the same contract validation.
- Bind each design acceptance criterion to named gate IDs.
- Include token sources, component registries, package manifests, visual-test configuration, and accessibility configuration in the resolved input manifests of relevant gates.
- Retain screenshot, accessibility, interaction, and review artifacts by path and SHA-256.
- Compare the combined final revision, not only isolated worktrees.
- Baseline only evidence-backed existing differences. A baseline never authorizes a new copy or severity increase.
- Require explicit approval for intentional snapshot updates and connect them to a requirement or design-system change.

## Default accessibility target

Use WCAG 2.2 AA for web products unless the project requires a stricter or platform-specific standard. Include keyboard access, visible focus, semantic name/role/value, contrast, 200% zoom/reflow, reduced motion, error identification, target size, and non-color cues where applicable.
