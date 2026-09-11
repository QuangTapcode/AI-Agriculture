# Frontend context

AgriAI is a Vietnamese-first React 18 and Vite application for agricultural monitoring, market data, quality analysis, crop operations, and a RAG-backed assistant.

## UI direction

- Prototype A “Field Command” is the approved direction.
- Public pages use a forest-dark visual field; authenticated data pages use a dark shell with restrained light data surfaces.
- Manrope is the display face and DM Sans is the body/data face.
- Motion explains hierarchy or state changes and must respect reduced-motion preferences.

## Data trust

- Render quantitative values only when returned by an approved application API.
- Show source and freshness with the value.
- Reject mock/sample/demo payloads in production presentation.
- Show an explicit unavailable state when data is absent.

## Delivery

Use Vitest for component/data behavior and Playwright for responsive, interaction, console, and visual checks. Finish one route before starting the next.
