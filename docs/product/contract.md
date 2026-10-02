# Machine Assistant — Product contract

Copied from `siinanXD/vision` `PRODUCT.md` on 2026-09-27 (option B: the product is built here). vision keeps a reference copy.

## Product goal

**Status:** DEFINED (2026-09-27) — see `docs/product/` for architecture, UX spec and cost model.

**Machine Assistant** is a chat-first web application for people who maintain and operate industrial machines.
A customer adds a machine and uploads what they have: manuals, wiring diagrams, parts lists, PLC I/O lists,
photos of the control cabinet. The product turns those documents into a structured **machine map**
(assemblies → parts → locations → datasheets) and answers questions grounded in the documents.

Every answer shows *where to look*, not only *what to do*:

- the machine map at the top of the screen highlights the assemblies and parts the answer refers to,
- evidence images (page crops of diagrams, tables, photos) are shown inline next to the answer,
- every referenced part is a chip; tapping it opens the part sheet with the datasheet,
- when a photo of the control cabinet exists, the referenced part is marked with a box on that photo.

The main screen is a chat window. The left rail lists the customer's machines. Selecting a machine keeps the
chat and adds the machine map above it. The UI must work on desktop, tablet and phone.

Business intent: each machine costs API money to onboard and to query; the product makes that cost measurable
per machine so that a setup fee and a per-machine subscription can be priced with a known margin
(see `docs/product/cost-model.md`; decided pricing: model A, per machine setup fee + monthly subscription).

## Required input from the human

### 1. Goal

A technician with a question about a specific machine gets a grounded answer, sees where the relevant parts
are in the machine, and reaches the part's datasheet in one tap — without opening a single PDF by hand.

### 2. Users

- **Maintenance technicians / Instandhalter** (primary): ask troubleshooting and locating questions on the shop floor, often on a phone or tablet.
- **Machine operators**: ask operating and setup questions.
- **Service engineers of machine builders (OEM)**: support several machines at several customers.
- **Workspace admin** (secondary): adds machines, uploads documents, corrects the machine map, sees costs.

### 3. Must-have capabilities (v1)

1. **Machine library** — create a machine (name, manufacturer, type, serial, optional photo), upload PDFs and images, see ingestion status and ingestion cost.
2. **Machine map** — automatically derived model of the machine: assemblies/zones, parts with their identifiers (e.g. `-K3`, `-F12`, `-Q1`), manufacturer and order number, datasheet page/document, location. Humans can correct it; corrections win over extraction.
3. **Grounded chat** — streaming answers over the selected machine's documents with citations (document, page, region). Global chat across all machines when no machine is selected. Conversation history per machine.
4. **Answer visualization** — referenced parts are highlighted in the machine map; evidence page crops are shown inline; part chips open the part sheet.
5. **Cabinet photo localization** — when a cabinet/machine photo exists, referenced parts are marked with a bounding box on the photo. Boxes are computed once at ingestion (and after corrections), never per chat message.
6. **Responsive UI** — desktop (rail + map + chat), tablet, phone (drawer + collapsible map strip + bottom sheets). No horizontal scrolling, keyboard reachable, WCAG AA contrast.
7. **Cost ledger and observability** — every AI call is traced (model, tokens, cost, evidence) and attributed to a machine; the admin sees ingestion cost and monthly query cost per machine.

### 4. Constraints

- German-first UI; strings are externalized so English can follow.
- Customer documents are confidential: strict per-workspace and per-machine isolation, no cross-tenant retrieval, no training on customer data, EU-region hosting preferred.
- Stack as in this repository: Next.js (Vercel), FastAPI + PostgreSQL/pgvector (Railway), Langfuse; secrets via the platform secret stores.
- Runtime AI providers sit behind typed adapters: Anthropic Claude for extraction and answers; Google Gemini for photo localization (bounding boxes) and optional illustration generation; OpenAI image generation optional. Provider choice must be swappable per capability.
- Runtime API spend is accepted but bounded: a per-workspace monthly cap and a per-machine ingestion estimate shown before ingestion starts. The factory's subscription-first policy governs coding executors, not the product runtime.
- No secrets in the repository; runtime keys come from Infisical.

### 5. Acceptance (Preview/Staging candidate)

Demonstrated on a Vercel Preview + Railway staging with one demo machine built from publicly available documentation (no customer data):

- [ ] Add a machine and upload ≥ 3 documents including one wiring diagram PDF and one cabinet photo; ingestion of ≤ 300 pages completes in < 15 minutes and the cost ledger shows the ingestion cost.
- [ ] The machine map shows ≥ 5 assemblies and ≥ 20 parts with identifiers, each with at least one citation; a human correction (rename/move a part) persists and survives re-ingestion.
- [ ] A golden set of 20 questions (in `evals/`) reaches groundedness ≥ 0.90, valid citations ≥ 95 %, and referenced-part precision ≥ 0.85 in CI.
- [ ] Referenced parts are highlighted in the map and their chips open a part sheet that shows the datasheet page.
- [ ] For 10 labeled cabinet parts, the drawn box overlaps the ground-truth box with IoU ≥ 0.5 in ≥ 80 % of cases.
- [ ] 5 negative tests prove no answer contains content from another machine or workspace.
- [ ] The UI works at 390 px width without horizontal scroll; Lighthouse accessibility ≥ 90 on the machine view.
- [ ] Every AI call appears in Langfuse with model, tokens, cost, machine id and evidence references.

### Known limitations (2026-09-27)

None recorded. The former entry (planning module not workspace-scoped) is void since the module was removed
(Issue #123).

### Non-goals (v1)

Live PLC/sensor data, AR overlays, 3D CAD, spare-part ordering, native mobile apps, editing of source PDFs,
languages beyond German/English, multi-agent orchestration.

## Working rules

GitHub issues with acceptance criteria are the unit of work (template `.github/ISSUE_TEMPLATE/build-task.yml`); one implementation owner per issue; every change through a pull request with green CI; an independent review before merge; `READY FOR HUMAN ACCEPTANCE` only when the acceptance list above is demonstrated on a Preview/Staging deployment; production promotion is an explicit human decision.
