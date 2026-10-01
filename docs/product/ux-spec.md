# Machine Assistant — UX specification

Figma: **Vision – Machine Assistant UI** — https://www.figma.com/design/2OqLHx6iMLcQetq6uM90FC
Pages: `Foundations` (tokens, type scale), `Desktop 1440`, `Mobile 390`, `Flows & Notes`.

## 1. Design principles

1. **Chat first, machine always visible.** The conversation is the primary surface; the machine map sits above it and reacts to every answer.
2. **Show where to look.** Every answer highlights parts in the map, shows evidence crops and, when a cabinet photo exists, a box on the photo. Amber (`accent/signal`) is reserved for "look here".
3. **Everything cited, nothing invented.** Citations `[n]` are chips that open the page; parts are chips that open the part sheet. If a part cannot be located, the UI says so.
4. **Shop-floor ready.** Large tap targets (≥ 44 px), high contrast, works one-handed on a phone, camera and microphone in the composer.
5. **Costs are visible.** Ingestion estimate before starting, monthly cost per machine in the top bar, cost per answer in the answer footer.

## 2. Tokens

Color variables (collection `Vision Colors`, modes Light / Dark): `bg/canvas`, `bg/surface`, `bg/surface-2`, `bg/rail`, `fg/primary`, `fg/secondary`, `fg/on-rail`, `border/subtle`, `border/strong`, `accent/signal` (amber, highlights), `accent/brand` (blue, actions), `status/ok|warn|error`.
Typography: Inter (UI), IBM Plex Mono (part identifiers). Scale: Display 28 / Title 20 / Heading 16 / Body 15 / Body 14 / Label 13 / Caption 12 / Overline 11 / Mono 13 / Mono 12.
Spacing 8-px grid; radii 8 (chips/inputs), 12 (cards), 14–16 (panels/sheets); rail width 280.

Implementation: CSS variables in `frontend/src/app/globals.css` with `prefers-color-scheme` + `data-theme` override; Tailwind 4 and shadcn are already in use and map to these variables. Since 2026-10-01 the variables follow the approved Figma file "iOS clean" (`wtxajO1YC5HvtQG7CI44BC`): collections `Color` (Light/Dark) and `Layout`, text styles `iOS/…` in Inter and `Tag/…` in JetBrains Mono; the token list above describes the earlier "Vision" file. Where a Figma color is below 4.5:1 as text, a `-strong` variant is used for text.

## 3. Screens and states

### 3.1 Start / Alle Maschinen (desktop `Desktop / Start`, mobile via drawer)
- Rail: brand, search, "Alle Maschinen", machine list (name, manufacturer · location, status dot: ok / warn / ingesting), "Maschine hinzufügen", user + monthly cost.
- Main: hero prompt "Wonach suchst du?", 3 suggestion cards, recent conversations, composer with machine selector.
- States: empty workspace (no machines → onboarding CTA replaces suggestions), ingesting machine (blue dot, "wird verarbeitet"), budget exceeded (banner above composer, composer disabled).

### 3.2 Maschinenansicht (`Desktop / Maschinenansicht`, `Mobile / Maschinenansicht`)
- Top bar: machine name, manufacturer / serial / location chips, document count, map status, monthly cost, settings.
- **Machine map panel**: tabs Schema · Schaltschrank-Foto · Dokumente; zones (assemblies) as cards with part chips; connectors; legend; "n Bauteile aus der Antwort markiert" chip; expand to full screen. Map is rendered from `/v1/machines/{id}/map` (SVG/HTML, not an image). Hover/focus shows part name; click opens the part sheet.
- **Chat**: user bubbles right (dark), assistant left with amber avatar. Answer = paragraphs, numbered steps, part chip row (referenced parts amber first), evidence row (page crops / photo with box / parts-list highlight), sources row, action row (copy, feedback, "Im Modell zeigen", "Foto vergrößern", model · cost · latency).
- Composer: attach file, image, text, mic, send. Hint line under the composer.
- Streaming state: skeleton for the map highlight until `meta` arrives; tokens stream; evidence appears with `meta`.
- Error states: provider timeout ("Antwort dauert zu lange — erneut versuchen"), no evidence found ("In den Dokumenten dieser Maschine nichts gefunden — Frage umformulieren oder Dokument hochladen").
- Mobile: rail becomes a drawer (`Mobile / Maschinen`), the map becomes a collapsible strip with horizontally scrolling zone cards; expand opens the full map as a sheet.

### 3.3 Bauteil-Datenblatt (`Desktop / Bauteil-Datenblatt (Drawer)`, `Mobile / Bauteil (Bottom Sheet)`)
- Header: tag chip, assembly chip, name, manufacturer · order number, close.
- Photo with boxes (if any), datasheet card (document, page, "Öffnen"), position & connections table, related parts (relation verbs: schützt / schaltet / steuert / versorgt), evidence list.
- Footer: "Im Foto zeigen" (signal), "Korrigieren" (opens inline edit of name / tag / assembly; saving locks the row).
- Datasheet missing: card says "Kein Datenblatt verknüpft — hochladen" and offers upload.

### 3.4 Schaltschrank-Foto (`Desktop / Schaltschrank-Foto (Lightbox)`)
- Full photo with all annotations; referenced ones amber and filled, others white outline; side list with confidence; "Markierung korrigieren" enters drag mode (move/resize box, save → `source = human`).
- Pinch-zoom on touch; keyboard: arrows move the selected box, Enter saves, Esc cancels.

### 3.5 Maschine hinzufügen (`Desktop / Maschine hinzufügen`)
- Stepper 1 Maschine · 2 Dokumente · 3 Modell erstellen. Form, dropzone, file list with auto-detected document kind and quality warnings (blurry photo, no text layer), right column with the ingestion **cost estimate** and running-cost estimate, "Modell erstellen · ≈ 2,10 €" button, tips card.
- Ingestion progress (state of the same screen): step list (Lesen → Einbetten → Modell → Fotos) with per-document progress, "Fragen schon möglich" hint, failure row with retry.

## 4. Responsive rules

| Breakpoint | Layout |
| --- | --- |
| ≥ 1280 | rail 280 fixed + main; part sheet as right drawer 440; lightbox modal |
| 768–1279 | rail collapsible to 72 px icon rail; map panel height 220; drawer 400 |
| < 768 | rail = drawer; map = strip (70 px) expandable; part sheet = bottom sheet; lightbox full screen |

No horizontal body scroll at any width; wide content (map, evidence row, zone strip) scrolls inside its own container. Safe-area insets respected on phones.

## 5. Accessibility

Landmarks (`nav`, `main`, `aside`, `dialog`), visible focus rings (2 px brand), all chips are buttons with `aria-label` ("Bauteil -K3 öffnen"), evidence images have alt text from the citation, map zones are a list with keyboard navigation, live region announces streamed answer completion, contrast ≥ 4.5:1 (amber-on-dark text uses `#1F1300`), `prefers-reduced-motion` disables highlight pulses.

## 6. Motion

Purposeful only: map highlight fade-in 200 ms when `meta` arrives; sheet/drawer slide 250 ms; streaming caret. CSS transitions / the View Transitions API are enough for v1. GSAP or Three.js are **not** part of v1 (see §8).

## 7. Copy (German, du-Form)

Short, technical, no marketing. Examples: "Frag etwas zu dieser Maschine …", "In der Antwort referenziert", "Bauteil · antippen = Datenblatt", "Markierung falsch? Rahmen verschieben und speichern."

## 8. Note on 3D / animation tooling

- **Three.js (GLTF, lighting, cameras)** — not for v1. There is no CAD/GLTF model of the customer's machine; the map is derived from documents, so a 2D schematic is the honest representation. Candidate for v2 if an OEM supplies STEP/GLTF files: then a "3D" tab next to "Schema" with the same part highlighting.
- **GSAP / Motion design** — optional polish for the map highlight and sheet transitions; CSS/View Transitions cover v1. Add GSAP only if a measured interaction needs a timeline (complexity budget applies).
- **Design DNA / Genjutsu-style creative direction** — useful as input for the visual polish pass of the Figma file and the `frontend-design` implementation, not as runtime code.
