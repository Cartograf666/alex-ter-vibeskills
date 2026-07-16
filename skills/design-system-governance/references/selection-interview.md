# Design-system selection interview

Ask one question at a time. State the recommendation and trade-off before asking.

## Decision order

1. What platforms and host ecosystems must feel native?
2. What product shape dominates: marketing/content, consumer workflow, SaaS, data-dense enterprise, commerce extension, or native app?
3. What framework and component dependencies are already fixed?
4. Is the desired character restrained/minimal, editorial, expressive, tactile, or high-density enterprise?
5. How mature is the brand: established tokens/assets, partial identity, or no identity?
6. Which density, viewport, localization, input-method, dark-mode, and accessibility requirements are mandatory?
7. Can the team own component source, or does it need vendor-maintained APIs and upgrades?

## Recommendation mapping

- Shopify embedded surface: prefer Polaris.
- Native Apple: follow Apple HIG and platform components.
- Android-first: prefer Material 3.
- Microsoft-integrated product: prefer Fluent 2.
- Data-heavy enterprise React: compare Carbon and Ant Design against stack, brand, density, and component needs.
- Custom React/Tailwind SaaS: prefer a token-governed shadcn/ui foundation when source ownership is acceptable.
- Strong unique brand or nonmatching stack: use a custom token-first system, reusing accessible primitives where possible.

Do not choose by screenshots alone. Confirm implementation availability, licensing, accessibility, theming, localization, bundle/runtime constraints, release cadence, and migration cost.

## Visual-direction follow-up

After selecting the foundation, choose at most three product traits and record excluded traits. Example directions:

- restrained minimal;
- warm editorial;
- expressive color and motion;
- soft tactile surfaces;
- high-density operational;
- platform-native.

Treat glass, brutalism, gradients, 3D, or other visual fashions as optional theme techniques, not the component or accessibility contract.
