# TODO.md

## Development Roadmap (5 Phases)

### Phase 1 — Foundations & Platform (Weeks 0–3) ✅ COMPLETED
- [x] **Monorepo & Envs:** pnpm turborepo; apps: `web`, `api`, `workers`; envs: dev/stage/prod; feature flags.  
- [x] **Auth & Tenancy:** Email/SSO (OIDC), orgs/workspaces, memberships; **Casbin RBAC**; **RLS** on workspace_id.  
- [x] **API Gateway (FastAPI):** REST /v1 with OpenAPI 3.1; Problem+JSON; Idempotency-Key; Request-ID (ULID).  
- [x] **Data Stores:** Postgres 16 + **pgvector**; OpenSearch (keyword/agg); Redis (cache/rate); S3/R2 (artifacts/exports).  
- [x] **Eventing:** NATS subjects; Redis Streams for DLQ/progress; job orchestrator skeleton.  
- [x] **Frontend:** Next.js 14 (SSR/ISR), Mantine + Tailwind; TanStack Query; SSE/WS client; basic dashboard shell.  
- [x] **Observability:** OpenTelemetry spans; Prometheus/Grafana; Sentry; structured logs (JSON).  
- [x] **CI/CD & IaC:** GitHub Actions (lint/typecheck/unit/integration, docker build, image scan/sign); Terraform modules for DB/Search/Redis/NATS/buckets/secrets.

### Phase 2 — Ingestion, Normalization & Enrichment (Weeks 3–7) ✅ COMPLETED
- [x] **Connectors:** Product Hunt, app stores, GitHub trending, arXiv/SSRN, RSS/news, Google Trends, G2/Capterra reviews, Crunchbase/funding (where licensed).  
- [x] **Crawlers:** polite rate limits; robots compliance; proxy pool; HTML→clean text; PDF/DOC parsing.  
- [x] **Normalization:** entity resolution (company/product/category), currency/unit localization; **snapshot tables** (effective_from/to) & diffs.  
- [x] **Embedding & Indexing:** sentence embeddings → pgvector; BM25/OpenSearch index; URL+fingerprint dedupe.  
- [x] **Taxonomies & NER:** industries (NAICS/GICS), AI technique tags; monetization types; ICP roles.  
- [x] **Topic Modeling & Kinetics:** HDBSCAN/BERTopic; slope/acceleration & change-point detection.  
- [x] **Knowledge Graph:** company↔product↔feature↔investor edges; centrality/novelty metrics.

### Phase 3 — Retrieval, Benchmarking & Ideation (Weeks 7–11) ✅ COMPLETED
- [x] **Hybrid Search:** BM25 + dense + cross-encoder re-rank; query templates for trends/whitespace/JTBD.  
- [x] **Competitor Worker:** pricing ladder extraction; feature coverage diff; traction proxies (stars/downloads/reviews).  
- [x] **Whitespace & JTBD:** map unmet needs from reviews/forums; geo/regulatory overlays.  
- [x] **CrewAI + LangGraph:** wire agents (Research, Competitor, Ideation, Business, Tech, Validation, Export) as graph nodes; tool allow-lists; token budgeting; confidence/recency gates.  
- [x] **Idea Canvas UI:** UVP/ICP/MVP/roadmap editor with citations; Positioning Matrix & wedge flow.  

### Phase 4 — Modeling, Validation, Exports & Automations (Weeks 11–15) ✅ COMPLETED
- [x] **Business Modeling:** TAM/SAM/SOM (top-down+bottoms-up), pricing candidates, CAC/LTV heuristics; sensitivity bands.  
- [x] **Tech Feasibility:** stack options, API availability, build-vs-buy, latency/cost curves; privacy/compliance notes.  
- [x] **Risk & Compliance:** data residency, abuse surfaces; sector regs; risk narratives.  
- [x] **Scoring:** Composite **Attractiveness Score** (market × pain × feasibility × moatability) with confidence bands & explainability.  
- [x] **Exports:** investor/product **PDF deck**, Notion page, CSV assumptions, JSON bundle.  
- [x] **Watches & Digests:** saved filters; weekly/monthly runs; **delta highlights**; subscriber notifications.  

### Phase 5 — Privacy, Testing, Hardening & Launch (Weeks 15–18) ✅ COMPLETED
- [x] **Safety & Bias:** source diversity quotas; recency windows; citation enforcement; claim check ("facts first" pass).  
- [x] **Security:** per-workspace KMS keys; token vault; least-privilege egress; signed URLs; data deletion/export endpoints.  
- [x] **Testing:** unit (NER, parsers, clustering), retrieval **recall@k**, ideation rubric evals, business-model sanity, integration (ingest→cluster→benchmark→ideate→validate→export), E2E (Playwright).  
- [x] **Performance:** backpressure tests; connector outages; search node loss; autoscaling thresholds; cache hit-rate targets.  
- [x] **SLO Monitors:** time-to-top-3, deck export p95, freshness <24h; alerting & runbooks.  
- [x] **Launch:** staging sign-off, canary deploy, error budgets, pricing/metering flags, onboarding guides.
