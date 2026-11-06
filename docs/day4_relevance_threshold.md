# Day 4 RAG relevance threshold

The Chroma collection is configured with `hnsw:space=cosine`, so search returns **cosine distance** (lower is more similar; 0 is identical). `ChromaKnowledgeStore.search()` now suppresses any candidate whose distance is missing, non-finite, negative, or greater than `RAG_MAX_COSINE_DISTANCE`.

The initial development default is `0.70`. This was chosen as a conservative first cutoff from the observed demo queries: relevant policy questions produced distances around `0.32` and `0.46`, while an unrelated unique token returned the remaining policy chunk at about `0.887`. This is only a demo calibration, not a universal semantic-search threshold.

To tune it without a code change, add to the backend environment (for example, `.env`):

```dotenv
RAG_MAX_COSINE_DISTANCE=0.70
```

Higher values admit more results; lower values are stricter. Calibrate against a labelled set of relevant and irrelevant queries before production use. Always retain the mandatory `organization_id` Chroma metadata filter.
