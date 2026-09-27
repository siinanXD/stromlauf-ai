# Machine Assistant — Cost model and pricing

**Purpose:** answer the owner's question "what does one machine cost me, and what can I sell it for?" with numbers
that the product itself measures (`ai_call_ledger`). Prices below are list prices checked on 2026-09-27; the ledger
replaces them with measured medians after the first machines.

## 1. Provider list prices used

| Capability | Provider / model | Price |
| --- | --- | --- |
| Page understanding, extraction, answers (default) | Anthropic `claude-sonnet-5` | $2.00 / M input, $10.00 / M output; cache reads ≈ 10 % of input |
| "Gründlich" mode, hard extraction | Anthropic `claude-opus-5` | $5.00 / M input, $25.00 / M output |
| Cheap mode (optional) | Anthropic `claude-haiku-4-5` | $1.00 / M input, $5.00 / M output |
| Text embeddings | Voyage `voyage-4` | $0.06 / M tokens (first 200 M free) |
| Diagram-page embeddings | Voyage `voyage-multimodal-3.5` | $0.12 / M tokens + $0.60 / B pixels |
| Photo localization (bounding boxes) | Google Gemini 3 Pro | ≈ $0.001 per image input + $2 / M text in, $12 / M out |
| Illustration (optional, once per machine) | Gemini "Nano Banana 2" ≈ $0.067 (1K) · Nano Banana Pro $0.134 (2K) · OpenAI `gpt-image-2` ≈ $0.05 (medium) | per image |
| OCR fallback for scanned manuals (optional) | Mistral OCR 4 | $4 / 1 000 pages ($2 batch) |
| Batch discounts | Anthropic Batches −50 %, Gemini Batch −50 %, Voyage batch −33 % | only for non-urgent re-ingestion |

Sources: Anthropic pricing (claude-api skill, 2026-06), [Voyage pricing](https://docs.voyageai.com/docs/pricing), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Nano Banana pricing](https://www.myarchitectai.com/blog/nano-banana-api-pricing), [GPT Image 2 pricing](https://unifically.com/blogs/gpt-image-2), [Mistral OCR](https://mistral.ai/pricing/api/).

## 2. Onboarding cost per machine (one-time)

Assumptions for a **typical machine**: 300 pages (manual 200, wiring diagram 60, parts list 20, misc 20), 40 % of
pages are diagrams/scans that need vision reading, 3 cabinet photos.

| Step | Volume | Sonnet 5 | Opus 5 (extraction only) |
| --- | --- | --- | --- |
| Render pages (pypdfium2) | 300 pages | $0.00 | $0.00 |
| Page understanding (vision) | 120 pages × (1.5 k in + 0.6 k out) | $1.08 | $1.08 |
| Embeddings | 180 k tokens text + 120 diagram pages | $0.03 | $0.03 |
| Machine-model extraction | 210 k in + 75 k out | $1.17 | $2.93 |
| Photo localization | 3 photos | $0.03 | $0.03 |
| Illustration (optional) | 1 image | $0.05–0.13 | $0.05–0.13 |
| **Total** | | **≈ $2.4** | **≈ $4.2** |

Scaling: cost is roughly linear in pages. 100 pages ≈ $0.8, 1 000 pages ≈ $8 (Sonnet) / ≈ $14 (Opus extraction).
Re-ingestion after a human correction costs only the `localize` step (cents).

## 3. Running cost per question

Context per answer: system prompt 1 k + machine-map summary 2.5 k (both cached) + 12 chunks × 500 = 6 k + history 2 k ≈ 11.5 k input, 500 output.

| Model | Per answer | 200 answers / month | 1 000 answers / month |
| --- | --- | --- | --- |
| Haiku 4.5 | ≈ $0.014 | $2.80 | $14 |
| **Sonnet 5 (default, with caching)** | **≈ $0.022** | **$4.40** | **$22** |
| Opus 5 ("Gründlich") | ≈ $0.07 | $14 | $70 |

Retrieval (pgvector) and evidence crops cost nothing per query. Photo boxes are computed at ingestion, not per query.

Infrastructure (independent of machine count until ~100 machines): Railway API + worker + PostgreSQL ≈ $30–60 / month, Vercel Pro $20, Langfuse cloud from $0–59, object storage cents. Say **≈ $100 / month fixed**.

## 4. Pricing options

**Decision (owner, 2026-09-27): Model A — per machine.** Setup 149–299 € per machine, 39–79 € per machine per month, 300 questions included, 0.15 € per additional question. Models B and C stay documented as later options for workspace and OEM deals.

| Model | Setup per machine | Monthly per machine | Included questions | Gross margin on AI cost |
| --- | --- | --- | --- | --- |
| **A — per machine (recommended)** | 149–299 € | 39–79 € | 300, then 0.15 €/question | > 90 % |
| B — per workspace | 490 € (up to 5 machines) | 249 € (up to 10 machines) | fair use, Opus mode +0.10 €/question | > 85 % |
| C — OEM/service partner | 99 € per machine (volume) | 19 € per machine | 100, cheap mode default | > 80 % |

Value anchor: a maintenance hour costs 60–90 €; saving 15 minutes of manual-searching per machine per week already
pays 39 €/month. The setup fee also covers the human review of the machine map (≈ 20–40 minutes for a 300-page machine).

Break-even on fixed cost: ≈ 3 machines on model A at 39 €/month.

## 5. Guardrails built into the product

- Estimate before ingestion (pages × measured per-page median) shown in the "Maschine hinzufügen" screen.
- `workspace.monthly_ai_cap_cents`; calls beyond it fail with `BudgetExceeded` and the UI asks the admin to raise it.
- Ledger per machine and per purpose, exposed in the UI (`3,20 € diesen Monat` chip) and in Langfuse.
- Model per purpose is configuration, not code: `ANSWER_MODEL`, `EXTRACT_MODEL`, `UNDERSTAND_MODEL`, `LOCALIZE_MODEL`.
- No per-question image generation. Illustration is opt-in, once per machine.
