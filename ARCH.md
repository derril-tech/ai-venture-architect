# ARCH.md

## System Architecture — AI Venture Architect

### Overview
A multi-tenant, event-driven platform that uses **CrewAI** for role-based agents and **LangGraph** for **stateful, fault-tolerant DAGs**. It continuously ingests market signals, builds topic/trend intelligence, benchmarks competitors, and generates **validated product ideas** and **investor-ready artifacts** with **citations** and **guardrails**.

### Diagram
```
Next.js 14 (SSR/ISR, Mantine+Tailwind) ── REST/SSE/WS ─► FastAPI /v1 (RBAC, RLS, OpenAPI)
                                                        │
                                                        ├─► NATS (signals.ingest, normalize, trends.detect, bench.run, idea.generate,
                                                        │         model.business, model.tech, validate.run, export.make)
                                                        │
                                                        └─► Workers (Python 3.11 + CrewAI + LangGraph):
                                                             • ingest-worker (crawlers/APIs, cleaning)
                                                             • normalize-worker (entity resolution, currency/unit, snapshots)
                                                             • trend-worker (topic clusters, kinetics, deltas)
                                                             • competitor-worker (pricing/feature diffs, traction proxies)
                                                             • ideation-worker (UVP/ICP/MVP, positioning; citations)
                                                             • business-worker (TAM/SAM/SOM, pricing, CAC/LTV)
                                                             • tech-worker (stack options, cost curves, privacy)
                                                             • validation-worker (risks/compliance, score/confidence)
                                                             • export-worker (PDF/Notion, CSV/JSON bundles)
Data Plane:
  • Postgres 16 + pgvector (RLS by workspace_id) — signals, topics, competitors, ideas, scores, watches, audit
  • OpenSearch — keyword, faceting, aggregations
  • Redis — cache/session/rate-limits; DLQ progress
  • S3/R2 — raw artifacts (HTML/PDF), exports (PDF/Notion/CSV/JSON)
  • (Optional) LanceDB for local vector R&D; Neo4j for market graph; ClickHouse for usage analytics
Observability:
  • OpenTelemetry → Prometheus/Grafana; Sentry errors
Security:
  • KMS per workspace, signed URLs, CSP/TLS/HSTS, least-privilege egress
```

### CrewAI + LangGraph Orchestration
- **Nodes (agents):** Research, Competitor, Ideation, Business, Tech, Validation, Export.  
- **Edges:** success/insufficient-evidence/low-confidence → **loop** with new retrieval; **retry** with backoff; **abort** on guardrail breach.  
- **Shared State:** `run_id`, workspace assumptions, retrieved passages + **citations**, intermediate models (TAM/SAM/SOM), risk flags.  
- **Budgets & Guards:** per-node token budgets; source diversity quota; **recency gates**; “facts-first” retrieval step before any generation.

### Data Model (Summary)
- **signals**(id, workspace_id, source, url, entity, text, meta, embedding).  
- **competitors/products**(pricing JSONB, features JSONB, last_seen).  
- **topics/topic_members**(centroid, membership scores).  
- **ideas**(title, uvp, icps, mvp_features, roadmap, tam/sam/som, unit_econ, risks, tech_stack, gtms, attractiveness, confidence, sources, state).  
- **reports**(type, s3_path). **watches/alerts** for digests. **audit_log** for governance.  
All tables enforce **RLS by workspace_id**; indexes on `embedding` (ivfflat) and OpenSearch fields for query/filter speed.

### Retrieval & Analysis
- **Hybrid Search:** BM25 (OpenSearch) + pgvector dense search → **cross-encoder re-rank**.  
- **Topic/Trend:** HDBSCAN/BERTopic; compute slope/acceleration & change-points; flag deltas for digests.  
- **Competitor Diffing:** structured extraction of pricing tiers/features; versioned snapshots and diff views.  
- **Whitespace/JTBD:** label gaps from reviews/forums; join with geo/regulatory overlays.

### Modeling & Scoring
- **Market Models:** top-down (industry stats) + bottoms-up (pricing × ICP counts); scenario bands.  
- **Unit Economics:** CAC/LTV heuristics by channel; sensitivity.  
- **Tech Feasibility:** stack choices, build-vs-buy, latency/cost curves; privacy/regulatory notes.  
- **Composite Attractiveness:** weighted function with **explain** breakdown and **confidence bands**.

### Frontend
- **Pages:** Dashboard, Opportunities, Idea Detail, Watches, Reports, Settings.  
- **Components:** SignalList, TopicExplorer, CompetitorMatrix, IdeaCanvas, TAMChart, ScoreCard, RiskMatrix, ExportWizard.  
- **Realtime:** SSE for idea generation streams; WS for run progress.  
- **Guardrails:** export disabled until min confidence; badges for recency/provenance.

### APIs (selected)
- `POST /ingest` (source, url|payload)  
- `GET /signals` (query, filters, topic_id, date range)  
- `POST /ideas/generate` → `{run_id, idea_id, attractiveness, confidence}`  
- `POST /ideas/{id}/validate` → updated scores/risks/tam/sam/som  
- `POST /exports/deck` → signed URL (PDF)  
- `POST /watches` / `GET /alerts`  
Standards: **OpenAPI 3.1**, Problem+JSON, cursor pagination, SSE for long jobs.

### Performance & Scaling
- **Caching:** Redis for hot queries, topic member pages, competitor diffs.  
- **Precompute:** sector-specific ANN indexes; nightly digest candidates.  
- **Backpressure:** NATS consumer groups; retry with jitter; per-connector rate limits.  
- **SLO Targets:** Time-to-top‑3 ideas < 60s p95; Search < 1.2s p95; Deck export < 10s p95.

### Security & Compliance
- **Isolation:** RLS everywhere; per-workspace KMS keys; signed URLs; encrypted secrets.  
- **Governance:** audit completeness checks; data deletion/export (DSR); retention windows.  
- **Safety:** robots/ToS compliance; read-only connectors by default; **citation required** for claims; bias & recency checks.

### Deployment
- **FE:** Vercel (ISR/Edge cache).  
- **API/Workers:** Render/Fly/GKE pools per worker type; autoscale by queue.  
- **IaC:** Terraform; blue/green deploy; DB migrations with approvals; PITR backups.  
- **Monitoring:** OTel dashboards + on-call runbooks; error budgets & alerting.
