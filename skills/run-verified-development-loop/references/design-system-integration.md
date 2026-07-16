# Design-system integration

## Input authority

For UI work, load:

1. approved `.ai/design-system.yaml`;
2. task `DESIGN-BRIEF.md`;
3. PRD/RunSpec acceptance criteria;
4. architecture manifest and Change Envelope;
5. frozen acceptance tests and approved visual references.

The PRD controls intended user behavior. The Design Brief controls task experience and state coverage. The project manifest controls tokens, components, interaction/accessibility rules, and required design gate classes. Architecture controls source ownership and dependencies.

## Work-package boundaries

List permitted token/component/feature paths and protect system governance files. A feature writer may consume approved tokens and components. New tokens, primitives, public component APIs, global theme behavior, or component semantic changes require an approved design-system change.

## Verification order

```text
scope and architecture
-> token and forbidden-value checks
-> component states and keyboard semantics
-> focused accessibility
-> responsive interaction flows
-> visual regression at named viewports/modes
-> build and broad tests
-> focused visual/system review
```

Require evidence for every applicable design criterion. A screenshot alone does not prove interaction, semantics, responsive behavior, content robustness, or accessibility. An automated accessibility scan alone does not prove usable keyboard/screen-reader experience.

## Review outcomes

Block acceptance for arbitrary styling, duplicated primitives, missing states, unapproved snapshot updates, inaccessible interactions, responsive overflow, reliance on color alone, ignored reduced motion, or visual evidence from a different revision/tree.

If no independent visual reviewer is available, use `READY_FOR_HUMAN_REVIEW`; do not self-certify subjective design quality.
