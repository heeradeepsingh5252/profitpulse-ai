"""Chroma persistence with mandatory organization metadata filters."""
from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from profitpulse.rag.chunker import build_page_chunks

COLLECTION_NAME = "profitpulse_knowledge"
# Chroma is configured with cosine distance (lower is more similar; 0 is identical).
# This initial demo cutoff is configurable and should be calibrated on labelled queries.
DEFAULT_MAX_COSINE_DISTANCE = 0.70


def _max_cosine_distance() -> float:
    raw_value = os.getenv("RAG_MAX_COSINE_DISTANCE", str(DEFAULT_MAX_COSINE_DISTANCE))
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise KnowledgeStoreError("RAG_MAX_COSINE_DISTANCE must be a number between 0 and 2") from exc
    if not math.isfinite(value) or not 0.0 <= value <= 2.0:
        raise KnowledgeStoreError("RAG_MAX_COSINE_DISTANCE must be a number between 0 and 2")
    return value


class KnowledgeStoreError(RuntimeError):
    pass


class ChromaKnowledgeStore:
    def __init__(self, path: str | None = None, client: Any | None = None):
        self.path = path or os.getenv("CHROMA_PATH", "/app/data/chroma")
        Path(self.path).mkdir(parents=True, exist_ok=True)
        if client is None:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=self.path)
            except Exception as exc:
                raise KnowledgeStoreError("ChromaDB could not be initialized") from exc
        self.client = client
        try:
            # Chroma's default embedding function supplies local ONNX embeddings.
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "description": "Tenant-scoped ProfitPulse knowledge documents"},
            )
        except Exception as exc:
            raise KnowledgeStoreError("The ProfitPulse Chroma collection is unavailable") from exc

    def ingest(self, organization_id: str, filename: str, pages: list[dict[str, object]]) -> dict[str, Any]:
        chunks = build_page_chunks(pages)
        if not chunks:
            raise ValueError("No text chunks were produced from the document")
        if len(chunks) > 5000:
            raise ValueError("Document creates too many chunks; split it into smaller files")
        document_id = str(uuid4())
        uploaded_at = datetime.now(timezone.utc).isoformat()
        ids, documents, metadatas = [], [], []
        for chunk in chunks:
            text = str(chunk["text"])
            page_number = int(chunk["page_number"])
            chunk_index = int(chunk["chunk_index"])
            ids.append(str(uuid4()))
            documents.append(text)
            metadatas.append({
                "organization_id": str(organization_id),
                "document_id": document_id,
                "filename": filename[:255],
                "page_number": page_number,
                "chunk_index": chunk_index,
                "uploaded_at": uploaded_at,
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
        try:
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        except Exception as exc:
            raise KnowledgeStoreError("The document could not be stored in ChromaDB") from exc
        return {
            "document_id": document_id,
            "filename": filename[:255],
            "chunk_count": len(chunks),
            "page_count": len({int(chunk["page_number"]) for chunk in chunks}),
            "status": "indexed",
        }

    def search(self, organization_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
        query = (query or "").strip()
        if len(query) < 3:
            raise ValueError("query must contain at least 3 characters")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")
        try:
            result = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"organization_id": str(organization_id)},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise KnowledgeStoreError("Knowledge search failed") from exc
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]
        max_distance = _max_cosine_distance()
        hits = []
        for index, text in enumerate(documents):
            # Distances are requested explicitly from Chroma. If a distance is
            # missing, non-finite, negative, or above the configured cutoff, do
            # not present the passage as evidence for this query.
            raw_distance = distances[index] if index < len(distances) else None
            if raw_distance is None:
                continue
            distance = float(raw_distance)
            if not math.isfinite(distance) or distance < 0.0 or distance > max_distance:
                continue

            metadata = metadatas[index] or {}
            filename = str(metadata.get("filename", "unknown"))
            page_number = int(metadata.get("page_number", 1))
            hits.append({
                "chunk_id": ids[index] if index < len(ids) else None,
                "text": text,
                "source": {
                    "document_id": metadata.get("document_id"),
                    "filename": filename,
                    "page_number": page_number,
                    "citation": f"[{filename}, p. {page_number}]",
                },
                "distance": distance,
            })
        return {"query": query, "result_count": len(hits), "results": hits,
                "scope": "organization-scoped Chroma search"}

    def list_documents(self, organization_id: str) -> list[dict[str, Any]]:
        try:
            result = self.collection.get(
                where={"organization_id": str(organization_id)},
                include=["metadatas"],
            )
        except Exception as exc:
            raise KnowledgeStoreError("Could not list knowledge documents") from exc
        grouped: dict[str, dict[str, Any]] = {}
        for metadata in result.get("metadatas") or []:
            document_id = str(metadata.get("document_id", ""))
            if not document_id:
                continue
            entry = grouped.setdefault(document_id, {
                "document_id": document_id,
                "filename": metadata.get("filename"),
                "uploaded_at": metadata.get("uploaded_at"),
                "chunk_count": 0,
            })
            entry["chunk_count"] += 1
        return sorted(grouped.values(), key=lambda item: str(item.get("uploaded_at", "")), reverse=True)

    def delete_document(self, organization_id: str, document_id: str) -> int:
        # First enumerate matching chunks under the tenant filter. A document ID alone
        # is never sufficient to delete another organization's records.
        try:
            matched = self.collection.get(
                where={"$and": [
                    {"organization_id": str(organization_id)},
                    {"document_id": str(document_id)},
                ]},
                include=["metadatas"],
            )
            ids = matched.get("ids") or []
            if ids:
                self.collection.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            raise KnowledgeStoreError("Could not delete the requested knowledge document") from exc


_store: ChromaKnowledgeStore | None = None

def get_knowledge_store() -> ChromaKnowledgeStore:
    global _store
    if _store is None:
        _store = ChromaKnowledgeStore()
    return _store

def reset_knowledge_store_for_tests() -> None:
    global _store
    _store = None
