# Design-system discovery and audit

## Evidence order

1. Project instructions and approved design documentation.
2. Connected Figma libraries, variables, components, and prototypes.
3. Token and theme files, CSS variables, Tailwind or framework configuration.
4. Component source, registries, Storybook, examples, and package dependencies.
5. Existing screens across representative routes and viewports.
6. UI lint, accessibility, screenshot, and end-to-end tests.

## Audit dimensions

- Token coverage: color, typography, spacing, sizing, radius, border, elevation, motion, breakpoint, and z-index.
- Component coverage: variants, sizes, states, composition, public API, documentation, and tests.
- Pattern coverage: navigation, forms, tables, feedback, dialogs, destructive actions, onboarding, and empty states.
- Accessibility: semantics, keyboard, focus, contrast, zoom/reflow, reduced motion, touch targets, and announcements.
- Responsive behavior: viewport classes, containers, wrapping, overflow, density, long content, and localization.
- Governance: ownership, versioning, migration, deprecation, review, and release process.

## Classification rule

Use `APPROVED_EXISTING` only with an authoritative source. Use `OBSERVED_EXISTING` or `PARTIAL` for repository evidence without approval. A component library alone is not a complete system unless tokens, interaction rules, accessibility, and governance are defined.

For `PARTIAL`, extend the smallest missing layer. Do not discard useful project conventions.
