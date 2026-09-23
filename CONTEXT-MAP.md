# AgriAI context map

| Area | Context | Main paths |
| --- | --- | --- |
| Frontend | `frontend/CONTEXT.md` | `frontend/src`, `frontend/prototypes` |
| Backend and RAG | `backend/CONTEXT.md` | `backend/app`, `backend/tests` |
| YOLO training | `training/yolo/CONTEXT.md` | `training/yolo`, `backend/app/services/quality_service.py` |

Read the most specific context before changing a subsystem. Cross-system changes must satisfy every affected context.
