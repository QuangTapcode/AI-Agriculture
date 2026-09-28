from app.services.agentic_rag_service import AgenticRagService


class TwoStepRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, owner, crop=None):
        self.calls.append((query, owner, crop))
        if len(self.calls) == 1:
            return {
                "status": "ready",
                "sources": [{
                    "name": "lua.txt",
                    "document_id": "lua",
                    "excerpt": "Huong dan cham soc lua sau mua.",
                    "score": 0.42,
                }],
            }
        return {
            "status": "ready",
            "sources": [{
                "name": "nho.txt",
                "document_id": "nho",
                "excerpt": "Ky thuat trong nho va phong benh cho nho.",
                "crop": "nho",
                "score": 0.74,
            }],
        }


def test_agentic_rag_rewrites_query_after_weak_evidence():
    retriever = TwoStepRetriever()
    service = AgenticRagService(retriever=retriever, max_steps=2, min_relevance=0.18)

    result = service.retrieve(
        "Quy trinh trong nho tai Ninh Thuan",
        owner=None,
        crop="nho",
        region="Ninh Thuan",
        intent="cultivation_advice",
    )

    assert result["status"] == "ready"
    assert result["sources"][0]["name"] == "nho.txt"
    assert len(retriever.calls) == 2
    assert result["agentic"]["steps"] == 2
    assert result["agentic"]["outcome"] == "evidence_found_after_rewrite"
