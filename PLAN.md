# PLAN.md

## Product: AI Venture Architect — multi-agent market research & AI product ideation

### Vision & Goals
Build a **production-grade, multi-tenant platform** that continuously ingests market signals, clusters trends, benchmarks competitors, and—via **CrewAI + LangGraph**—generates **validated product briefs** and **investor-ready artifacts** with **source citations** and **bias/recency guardrails**.

### Key Objectives
- **Market Intelligence Packs:** trend scans, growth signals, whitespace analysis, competitor matrices with diffs & pricing ladders.
- **Validated Product Briefs:** UVP, ICPs/personas, problem hypotheses, MVP & v1.0 features, positioning/wedge.
- **Business Modeling:** TAM/SAM/SOM (top-down + bottoms-up), pricing, CAC/LTV heuristics, sensitivity bands.
- **Tech Feasibility:** stack options, API availability, build-vs-buy, infra cost curves, privacy/compliance notes.
- **GTM Plans & Digests:** lighthouse customers, experiment backlogs; **weekly/monthly Top Opportunities** with deltas.
- **Exports:** Pitch-style **PDF/Notion**, CSV assumptions, **JSON bundles**; share links with expiring tokens.
- **Governance & Safety:** source diversity checks, recency windows, human-in-the-loop review states; read-only connectors by default.

### Target Users
Founders & venture studios • VC/angel analysts • Enterprise strategy/innovation • Agencies/consultancies.

### High-Level Approach
1. **Orchestration (CrewAI + LangGraph):** Role agents (Research, Competitor, Ideation, Business, Tech, Validation, Export) are **LangGraph nodes**. Control edges encode **retry/branch/loop** based on confidence, evidence sufficiency, and recency. Shared state (assumptions, signals, scores) persisted to Postgres/LanceDB.
2. **Data Platform:** Ingest crawlers + API connectors → normalization (entity resolution, currency/unit, locale) → **snapshot versioning** → embeddings (pgvector) + keyword index (OpenSearch) → hybrid retrieval (BM25 + dense + cross-encoder).
3. **Application:** Next.js 14 (SSR for dashboards, Server Actions for exports) with Mantine + Tailwind. Streaming SSE/WS for pipeline progress; Recharts for charts; workspace RBAC.
4. **DevOps & Security:** Multi-env (dev/stage/prod), IaC (Terraform), autoscaling workers; OpenTelemetry, Prometheus, Sentry; per-workspace KMS keys, RLS, audit logs.

### Deliverables (v1)
- Opportunity Explorer dashboard with trend kinetics, competitor matrices, whitespace maps.
- Idea detail canvas (UVP/ICP/MVP/roadmap), sources & citations, risk/compliance panel, attractiveness + confidence.
- Watches/digests with deltas & alerts.
- Export Wizard: investor/product deck (PDF), Notion page, CSV/JSON bundles.
- Admin: connectors, quotas, RBAC, usage & error budgets.

### Phased Milestones (mapped to TODO.md)
- **P1 Foundations** → tenancy, RBAC, ingestion skeleton, hybrid search, CI/CD, observability.
- **P2 Ingestion & Enrichment** → connectors, normalization, snapshots, taxonomies/NER, topic clusters, market graph.
- **P3 Retrieval & Ideation** → hybrid search + re-rank, competitor diffing, whitespace/JTBD, CrewAI+LangGraph ideation loop.
- **P4 Modeling, Validation & Reporting** → TAM/SAM/SOM, unit econ, tech feas, risk/compliance, scoring, exports, watches.
- **P5 Privacy, Testing & Launch** → bias/recency guards, performance & chaos tests, staging hardening, production rollout.

### Success Criteria
**Product KPIs**
- ≥80% of surfaced ideas rated “actionable” by pilot users.
- ≥25% of weekly ideas move to experiment design.
- Digest open rate ≥60%, CTR ≥20%.
- ≥4× time saved vs manual research.

**Engineering SLOs**
- Time-to-Top‑3 ideas < **60s p95** per workspace run.
- Deck export < **10s p95**; Search API p95 < **1.2s**.
- Pipeline success ≥ **99%** monthly; data freshness < **24h** per tracked source.

### Guardrails & Scope
Decision-support only; **not** financial/legal advice. All generated claims must include **citations**; apply **source diversity** & **recency windows**. Read-only connectors; on‑prem/VPC optional. Sensitive data never used for training; adhere to robots.txt & terms for public sources.

### Rollout Plan
Pilot with 3–5 workspaces → expand connectors & sectors → add paid packs (CB Insights/Statista) behind feature flags → open self-serve onboarding with quotas & metering.
