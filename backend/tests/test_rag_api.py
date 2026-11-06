from fastapi.testclient import TestClient

from profitpulse.main import app
from profitpulse.rag import store as rag_store


class FakeStore:
    def ingest(self, org, filename, pages):
        return {"document_id": "00000000-0000-4000-8000-000000000001", "filename": filename,
                "chunk_count": 1, "page_count": len(pages), "status": "indexed"}

    def search(self, org, query, top_k):
        return {"query": query, "result_count": 1, "results": [{"text": "Approved above INR 25,000.",
                "source": {"filename": "policy.md", "page_number": 1, "citation": "[policy.md, p. 1]"}}]}

    def list_documents(self, org):
        return [{"document_id": "doc-1", "filename": "policy.md", "chunk_count": 1}]

    def delete_document(self, org, document_id):
        return 1 if org == "org-a" else 0


def test_upload_and_search_are_tenant_scoped(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(rag_store, "get_knowledge_store", lambda: fake)
    client = TestClient(app)
    headers = {"X-Organization-ID": "11111111-1111-4111-8111-111111111111"}
    uploaded = client.post("/api/v1/knowledge/documents", headers=headers,
                           files={"file": ("policy.md", b"Policy text", "text/markdown")})
    assert uploaded.status_code == 201
    searched = client.post("/api/v1/knowledge/search", headers=headers,
                           json={"query": "approval policy", "top_k": 4})
    assert searched.status_code == 200
    assert searched.json()["results"][0]["source"]["citation"] == "[policy.md, p. 1]"


def test_upload_rejects_unsupported_extension():
    client = TestClient(app)
    headers = {"X-Organization-ID": "11111111-1111-4111-8111-111111111111"}
    response = client.post("/api/v1/knowledge/documents", headers=headers,
                           files={"file": ("bad.exe", b"x", "application/octet-stream")})
    assert response.status_code == 400
