# Domain documentation

The repository uses a multi-context layout described by `CONTEXT-MAP.md`.

Agents must read the context for every subsystem they modify. Shared contracts such as API response metadata must be checked against both frontend and backend contexts. Architectural decisions that affect more than one area belong under `docs/adr/`.
