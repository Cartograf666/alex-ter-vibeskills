# Current design-system starting points

This is a decision aid, not a popularity ranking. Recheck official documentation, supported versions, licenses, and platform packages at selection time.

| Starting point | Strong fit | Main trade-off | Official source |
|---|---|---|---|
| shadcn/ui | Custom React/Tailwind SaaS and teams that want source ownership | Team owns composition, consistency, upgrades, and governance | [shadcn/ui](https://ui.shadcn.com/docs) |
| Material 3 | Android-first and products benefiting from platform familiarity and expressive theming | Can feel generic or Android-led without careful brand adaptation | [Material 3](https://m3.material.io/) |
| Fluent 2 | Microsoft ecosystem and cross-platform enterprise experiences | Strong platform character and ecosystem assumptions | [Fluent 2](https://fluent2.microsoft.design/) |
| Carbon | Complex enterprise and data-rich products needing code, design tooling, and strong guidance | Distinct IBM-derived language and heavier adoption surface | [Carbon](https://carbondesignsystem.com/) |
| Ant Design | Data-heavy React back offices with broad component needs | Opinionated APIs and visual language require deliberate theming | [Ant Design](https://ant.design/docs/spec/introduce/) |
| Polaris | Apps embedded in Shopify surfaces | Specialized for Shopify; avoid as a generic external product foundation | [Polaris](https://shopify.dev/docs/api/polaris/index) |
| Apple HIG | Native Apple-platform applications | Guidance and platform components, not a general web library | [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/) |
| Custom token-first | Strong differentiated brand or unsupported stack | Highest ownership, documentation, testing, and maintenance cost | Project-owned sources |

## Required comparison

Before adoption, compare:

- platform and framework fit;
- source ownership versus vendor API stability;
- token and theme architecture;
- component and pattern coverage;
- accessibility and localization support;
- responsive and input-method behavior;
- design-tool availability and design-to-code parity;
- performance, dependency, and bundle constraints;
- license, maintenance, migration, and release policy.
