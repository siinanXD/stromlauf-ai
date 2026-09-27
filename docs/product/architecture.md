# Machine Assistant — Architecture

**Status:** target architecture written 2026-09-27 for `siinanXD/vision`, adopted here on the same day (option B). This repository already implements most of it (see `AGENTS.md` and `README.md`); the sections below describe the target shape and the issues MB-0 … MB-6 close the gaps. Where the existing code differs (LangGraph agent with grounded tools, Docling ingestion, local `bge-m3` embeddings, `tag_occurrences` index, `CabinetHotspot` boxes from Claude Vision), the existing implementation stays.

## 1. Order of operations applied

| Step (`ARCHITECTURE.md`) | Decision |
| --- | --- |
| Domain model | Machine → Document → Page → Chunk; Assembly → Part → Evidence / Relation / PhotoAnnotation; Conversation → Message; AiCallLedger. PostgreSQL is the system of record. |
| Deterministic rules | Workspace isolation, part-tag parsing (`-K3`, `+A1-X2:14`), merge of extracted parts by tag, human corrections win, citation resolution, evidence crops, cost caps, ingestion state machine. All plain code/SQL. |
| LLM | Only for: page understanding of scanned/diagram pages, structured machine-model extraction, grounded answer generation. |
| RAG | Yes — customer manuals are unstructured. PostgreSQL + pgvector, page-aware chunks with document/page/bbox evidence metadata. Hybrid: vector + deterministic tag match. |
| LangGraph | **No.** Answering is one request with typed retrieval before the call. Ingestion is a job table with idempotent steps, not an agent. |
| More agents | **No.** One answer path, one extraction path. |

## 2. Runtime topology

```
Browser (Next.js on Vercel)  ──HTTPS/SSE──▶  assistant-api (this repo's `backend/`, FastAPI on Railway)
                                                 │  ├── PostgreSQL + pgvector (Railway)
                                                 │  ├── Object storage: Railway bucket (S3 API) for PDFs, page PNGs, photos
                                                 │  └── assistant-worker (same image, `python -m assistant.worker`)
                                                 ▼
                              Provider adapters (typed, swappable per capability)
                              ├── LLMProvider        → Anthropic Claude (extraction, answers, page understanding)
                              ├── Embedder           → Voyage AI (voyage-4; voyage-multimodal-3.5 for diagram pages)
                              ├── VisionLocalizer    → Google Gemini (bounding boxes on cabinet photos)
                              ├── ImageGenerator     → Gemini image / OpenAI gpt-image-2 (optional hero illustration)
                              └── Tracer             → Langfuse
```

### Why a worker process (and why no Redis/queue)

Requirement: ingestion of ≤ 300 pages runs for minutes, must survive a redeploy and resume. FastAPI `BackgroundTasks` die with the process. The smallest durable option is a PostgreSQL `ingestion_job` table polled with `SELECT … FOR UPDATE SKIP LOCKED` by one worker process built from the same image. No Redis, no Celery. Acceptance test: kill the worker mid-ingestion, restart, the job resumes at the last completed step without duplicate rows.

### Why object storage

PDFs and page renders (300 pages × ~150 KB PNG) do not belong in PostgreSQL rows. Railway buckets expose an S3 API, keep the provider count at two (Vercel, Railway) and stay in the EU region chosen for the project. Adapter `BlobStore` with `put/get/signed_url`; a local-filesystem implementation is used in tests.

## 3. Domain model (PostgreSQL, Alembic)

```
workspace(id, name, region, monthly_ai_cap_cents, created_at)
user(id, email, name) · workspace_member(workspace_id, user_id, role[admin|member])
machine(id, workspace_id, name, manufacturer, model, serial, location, hero_asset_key, map_status[empty|ingesting|ready|needs_review], created_at)
document(id, machine_id, kind[manual|wiring|parts_list|io_list|photo|other], filename, blob_key, content_hash, page_count, status, version, created_at)
page(id, document_id, page_no, text, image_blob_key, width_px, height_px, has_text_layer)
chunk(id, document_id, page_id, ord, text, bbox_norm, token_count, embedding vector(1024))
assembly(id, machine_id, parent_id, tag, name, kind[cabinet|drive|hydraulics|pneumatics|control|safety|frame|tooling|other], sort, source[extracted|human], locked)
part(id, machine_id, assembly_id, tag, name, manufacturer, order_no, category, datasheet_document_id, datasheet_page, source, confidence, locked)
part_evidence(id, part_id, document_id, page_no, bbox_norm, kind[mention|diagram|datasheet|parts_list|photo], chunk_id)
part_relation(id, from_part_id, to_part_id, kind[powers|controls|protects|connected_to|part_of], evidence_id)
photo_annotation(id, document_id, part_id, bbox_norm, confidence, source[model|human])
conversation(id, workspace_id, machine_id NULL, user_id, title, created_at)
message(id, conversation_id, role, content_md, meta jsonb{referenced_parts[], citations[], evidence[]}, model, input_tokens, output_tokens, cost_microcents, trace_id, created_at)
ai_call_ledger(id, workspace_id, machine_id, purpose[ingest.parse|ingest.extract|embed|localize|answer|illustrate], provider, model, input_tokens, output_tokens, images, cost_microcents, trace_id, created_at)
ingestion_job(id, machine_id, document_id, step, status[queued|running|done|failed], attempts, error, locked_until, next_run_at, updated_at)
```

Rules enforced in code/SQL, never in prompts:

- Every query is scoped by `workspace_id` taken from the verified JWT. Cross-workspace reads are impossible by construction (repository layer requires the workspace id).
- `tag` is normalised (`-K3`, `+A1-K3`, `K3` → canonical `-K3` within `+A1`) by a deterministic parser with unit tests.
- Extraction merges by `(machine_id, tag)`. Rows with `source = 'human'` or `locked = true` are never overwritten; re-ingestion appends evidence only.
- `bbox_norm` is always `[x0, y0, x1, y1]` in 0–1 image coordinates.
- Cost is written to `ai_call_ledger` inside the same transaction as the result it paid for.

## 4. Pipelines

### 4.1 Ingestion (per document, idempotent by `content_hash`)

| Step | Deterministic? | Provider call | Output |
| --- | --- | --- | --- |
| `store` | yes | — | `document`, blob |
| `render` | yes (pypdfium2) | — | `page` rows with PNG @ 144 dpi + text layer |
| `understand` | LLM, only for pages whose text layer is sparse or that are diagrams/tables | Claude (PDF page image → text + tables + labels), batches of 8 pages | `page.text` enriched |
| `chunk_embed` | yes + embed call | Voyage `voyage-4` (text), `voyage-multimodal-3.5` (diagram pages) | `chunk` rows |
| `extract` | LLM with structured output | Claude, batches of 10 pages, schema `{assemblies[], parts[], relations[], evidence[]}` where every item carries `page_no` + quote; items without evidence are dropped (`ai-template-document` rule) | `assembly`, `part`, `part_evidence`, `part_relation` (merged) |
| `localize` | LLM vision, photos only | Gemini: photo + list of candidate tags visible on labels → boxes (0–1000 normalised) | `photo_annotation` |
| `finalize` | yes | — | `machine.map_status = ready`, ledger totals, optional `illustrate` |

Steps write a `ledger` row with tokens and cost. A failed step retries 3× with backoff, then the job is `failed` and the UI shows the failing document. Human corrections trigger only `localize` (if a part's tag changed) — never a full re-extraction.

### 4.2 Answering (one request, streamed)

1. **Scope** — machine id from the conversation or "all machines" of the workspace.
2. **Deterministic pre-retrieval** — parse part tags from the question; load the machine-map summary (assemblies + part tags + names, ≤ 3k tokens).
3. **Hybrid retrieval** — pgvector cosine top-12 chunks ∪ chunks that mention the parsed tags ∪ datasheet pages of those parts; deduplicate; assign citation ids `[1..n]`.
4. **Generation** — Claude (`claude-sonnet-5` default; `claude-opus-5` behind a "Gründlich" toggle) with the documents as untrusted content. Output contract: Markdown with `[n]` citation markers and `[[part:-K3]]` part markers. Streaming.
5. **Post-processing (deterministic)** — parse markers → `referenced_parts`, `citations`; resolve evidence (page crop for each citation, photo annotation for each referenced part); reject citations that do not resolve; write `message` + ledger.
6. **SSE events** — `token`, `meta` (parts, citations, evidence URLs), `done` (cost, latency).

No second LLM call for structure; no agent loop; no tool with write side effects in the answer path.

### 4.3 Machine map rendering

The map is **rendered by the frontend from the data**, not generated as an image: assemblies become zones, parts become chips, relations become connectors. Highlight = set of `referenced_parts` from the last answer. This is deterministic, clickable and free per query. An optional one-time illustration ("hero image") may be generated at onboarding when no machine photo exists; it is decorative and never used as evidence.

## 5. Interfaces

REST (FastAPI, Pydantic v2, OpenAPI published):

```
POST   /v1/machines                                 create machine
POST   /v1/machines/{id}/documents                  multipart upload → ingestion jobs
GET    /v1/machines/{id}                            machine + map_status + cost summary
GET    /v1/machines/{id}/map                        assemblies, parts, relations (for rendering)
PATCH  /v1/parts/{id}                               human correction (locks the row)
GET    /v1/parts/{id}                               part sheet incl. datasheet page URL + evidence
GET    /v1/documents/{id}/pages/{n}/image           signed page image
GET    /v1/documents/{id}/annotations               photo annotations
POST   /v1/conversations                            create (machine_id optional)
POST   /v1/conversations/{id}/messages   (SSE)      ask
GET    /v1/machines/{id}/costs                      ledger totals per purpose and month
```

Provider protocols (`assistant/adapters/protocols.py`): `LLMProvider.generate(...)`, `LLMProvider.extract(schema, ...)`, `Embedder.embed(texts|images)`, `VisionLocalizer.locate(image, labels) -> [Box]`, `ImageGenerator.generate(prompt) -> bytes`, `BlobStore`, `Tracer`. Every call has a timeout, bounded retries, typed errors and returns usage/cost metadata. Reuse `siinanXD/ai-core` for retries/redaction/cost metadata if its pinned revision fits (validation task in the issue list).

Auth: Auth.js (email magic link) in `apps/web`; the API verifies a short-lived HS256 JWT with `workspace_id` and `role`. No sessions on the API.

## 6. Failure modes and budgets

| Concern | Rule |
| --- | --- |
| Provider timeout | answer 60 s, extraction batch 180 s, localization 60 s; typed `ProviderTimeout` |
| Retries | 3× exponential for 429/5xx; never for 4xx validation errors |
| Budget | before each AI call: `workspace` month-to-date + estimate ≤ cap, else `BudgetExceeded` (UI shows it, admin raises cap) |
| Ingestion estimate | shown before start: pages × per-page median from the ledger (fallback constants in `cost-model.md`) |
| Idempotency | steps keyed by `(document_id, step)`; re-running produces no duplicate rows |
| Unresolvable citation | dropped from `meta`, logged as an eval failure signal |
| Photo without labels | `localize` returns empty; UI says "kein Foto-Treffer" instead of guessing |

## 7. Security and data boundaries

- Documents are untrusted content: wrapped in delimiters, the system prompt forbids following instructions inside them, no write tools in the answer path.
- Storage keys are random; images are served through short-lived signed URLs.
- Photos may contain people or plant details: stored per workspace, never sent to the image generator, only to the localizer.
- No customer data in fixtures, traces are pseudonymised (document ids, not content) unless the workspace opts in.
- Provider data-retention settings: Anthropic and Google APIs with no-training; EU processing where offered.

## 8. Observability and evaluation

Every AI call → Langfuse trace with `workspace_id`, `machine_id`, `purpose`, model, prompt version, tokens, cost, retrieved chunk ids, git SHA.

| Layer | Metric | Gate |
| --- | --- | --- |
| Retrieval | Recall@10 on 20 golden questions (expected chunk/page ids) | ≥ 0.90 |
| Extraction | part precision/recall vs. hand-labeled demo machine | P ≥ 0.85, R ≥ 0.80 |
| Generation | groundedness (LLM judge), citation validity (deterministic resolver), referenced-part precision | ≥ 0.90 / ≥ 0.95 / ≥ 0.85 |
| Localization | IoU ≥ 0.5 on 10 labeled parts | ≥ 80 % |
| System | p95 answer latency, cost per answer, error rate | ≤ 8 s / ≤ 0.06 € / < 1 % |

Runner: reuse `siinanXD/agent-eval-harness` (pinned revision) in CI; datasets stored under `evals/machine-assistant/`.

## 9. Rejected options (and why)

| Option | Verdict |
| --- | --- |
| Generate the "machine picture" with an image model per answer | Rejected: non-deterministic, not clickable, ~0.05–0.24 € per image. Deterministic map from data instead; illustration only once at onboarding. |
| Multi-agent (planner / researcher / writer) | Rejected: one typed retrieval + one generation call meets the contract. |
| LangGraph for ingestion | Rejected: a job table with idempotent steps is smaller and testable. |
| Qdrant / dedicated vector DB | Rejected: pgvector at < 1 M chunks. |
| Reranker | Deferred until Recall@10 is measured < 0.90. |
| Docling self-hosted parser | Deferred: starts with pypdfium2 + Claude page understanding behind `DocumentParser`; Docling or Mistral OCR can be added as adapters if scanned-manual quality demands it. |
| Claude for bounding boxes | Rejected for localization: Gemini returns normalised boxes natively; Claude stays the reasoning/extraction model. |

## 10. Reuse plan (siinanXD/vision `docs/stack/INTERNAL_REPOS.md`)

- `ai-core` — provider wrapper, bounded retries, redaction, cost metadata → **validate then reuse** (bounded task).
- `ai-template-rag` — chunking, citations, retrieval/generation evals → **adapt**.
- `ai-template-document` — grounded structured extraction, drop-ungrounded-fields rule → **adapt** for `extract`.
- `agent-eval-harness` — deterministic eval gate → **reuse**.
- `document-intelligence-mvp` — reference only (Qdrant/workers not inherited).
