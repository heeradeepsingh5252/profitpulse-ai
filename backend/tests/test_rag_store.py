from profitpulse.rag.store import ChromaKnowledgeStore


class FakeCollection:
    def __init__(self):
        self.rows = {}
        self.last_where = None
        self.query_distances = None

    def add(self, ids, documents, metadatas):
        for item_id, doc, meta in zip(ids, documents, metadatas):
            self.rows[item_id] = {"document": doc, "metadata": meta}

    def query(self, query_texts, n_results, where, include):
        self.last_where = where
        selected = [
            (key, value) for key, value in self.rows.items()
            if value["metadata"]["organization_id"] == where["organization_id"]
        ][:n_results]
        return {
            "ids": [[key for key, _ in selected]],
            "documents": [[value["document"] for _, value in selected]],
            "metadatas": [[value["metadata"] for _, value in selected]],
            "distances": [[
                self.query_distances[index]
                if self.query_distances is not None and index < len(self.query_distances)
                else 0.1
                for index, _ in enumerate(selected)
            ]],
        }

    def get(self, where, include):
        self.last_where = where
        if "$and" in where:
            clauses = where["$and"]
            selected = [(key, value) for key, value in self.rows.items()
                        if all(value["metadata"].get(k) == v for clause in clauses for k, v in clause.items())]
        else:
            selected = [(key, value) for key, value in self.rows.items()
                        if all(value["metadata"].get(k) == v for k, v in where.items())]
        return {"ids": [key for key, _ in selected], "metadatas": [value["metadata"] for _, value in selected]}

    def delete(self, ids):
        for item_id in ids:
            self.rows.pop(item_id, None)


class FakeClient:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, **kwargs):
        return self.collection


def test_ingest_search_and_tenant_filter(tmp_path):
    client = FakeClient()
    store = ChromaKnowledgeStore(path=str(tmp_path), client=client)
    uploaded = store.ingest("org-a", "policy.md", [{"page_number": 3, "text": "Finance approval is required for purchases above INR 25000."}])
    result = store.search("org-a", "finance approval")
    assert uploaded["chunk_count"] == 1
    assert result["result_count"] == 1
    assert result["results"][0]["source"]["citation"] == "[policy.md, p. 3]"
    assert client.collection.last_where == {"organization_id": "org-a"}
    assert store.search("org-b", "finance approval")["result_count"] == 0


def test_delete_is_tenant_scoped(tmp_path):
    client = FakeClient()
    store = ChromaKnowledgeStore(path=str(tmp_path), client=client)
    doc = store.ingest("org-a", "one.txt", [{"page_number": 1, "text": "alpha document"}])
    store.ingest("org-b", "two.txt", [{"page_number": 1, "text": "beta document"}])
    assert store.delete_document("org-b", doc["document_id"]) == 0
    assert len(store.list_documents("org-a")) == 1
    assert len(store.list_documents("org-b")) == 1
    assert store.delete_document("org-a", doc["document_id"]) == 1
    assert store.list_documents("org-a") == []



def test_search_filters_weak_cosine_matches_by_default(tmp_path):
    client = FakeClient()
    store = ChromaKnowledgeStore(path=str(tmp_path), client=client)
    store.ingest("org-a", "policy.md", [{"page_number": 1, "text": "Finance approval is required."}])
    # This mirrors the weak unrelated match observed during the live demo.
    client.collection.query_distances = [0.8868]

    result = store.search("org-a", "PP_DELETE_TEST_84729")

    assert result["result_count"] == 0
    assert result["results"] == []


def test_search_accepts_matches_within_cosine_threshold(tmp_path):
    client = FakeClient()
    store = ChromaKnowledgeStore(path=str(tmp_path), client=client)
    store.ingest("org-a", "policy.md", [{"page_number": 1, "text": "Finance approval is required."}])
    client.collection.query_distances = [0.4612]

    result = store.search("org-a", "Who approves the purchase?")

    assert result["result_count"] == 1
    assert result["results"][0]["distance"] == 0.4612


def test_search_threshold_can_be_configured(tmp_path, monkeypatch):
    client = FakeClient()
    store = ChromaKnowledgeStore(path=str(tmp_path), client=client)
    store.ingest("org-a", "policy.md", [{"page_number": 1, "text": "Finance approval is required."}])
    client.collection.query_distances = [0.80]
    monkeypatch.setenv("RAG_MAX_COSINE_DISTANCE", "0.85")

    result = store.search("org-a", "finance approval")

    assert result["result_count"] == 1
