# Nutrire - Design Spec

> **Note:** This document was written early in the project as the design target. The shipped product evolved from this spec - most notably adopting a glassmorphism aesthetic, using a custom i18n system instead of i18next, and shipping as organization-centric rather than event-centric. The core design principles (dignity, warmth, one-answer-not-a-list, banned-words enforcement) were carried through faithfully. For the canonical description of the shipped system, see [FINAL_SYSTEM.md](./FINAL_SYSTEM.md).

The design decisions below are cited back to research/foundation.md and use the voice rules in [COPY.md](./COPY.md).

---

## 1. Design principles (the seven commitments, condensed)

From `foundation.md` §6. Pinned here for quick reference during the build.

1. **C1 — No self-labeling at the entrance.** Home does not force the user to claim "I need food" before seeing value. *(R§4 — Link & Phelan labeling mechanism)*
2. **C2 — One decision per screen.** One hero card, not a ranked list. Recognition, not evaluation. *(R§3 — Mani/Mullainathan/Shafir/Zhao 2013 bandwidth tax)*
3. **C3 — Drastic transaction-cost reduction before stigma work.** Ruthless simplicity over warm language. Every screen must justify its load. *(R§4 — Bhargava & Manoli, Currie take-up findings)*
4. **C4 — Copy reframes user as a neighbor.** Banned-words list enforced. *(R§4 — Martin 2021, Hill & Guittar 2022)*
5. **C5 — Freshness as dignity.** Stale events never hidden, never promoted. Honest labels. *(R§4 — Garthwaite, Plentiful App Store reviews)*
6. **C6 — Broker as first-class user.** Share, save, print. *(R§5 — CDC navigator evidence)*
7. **C7 — Language parity is law.** EN + ES + AM, equal polish surface. *(R§2 — DC Language Access Act 2004)*

When a design choice contradicts one of these, document why in the component's comment header.

---

## 2. Visual system

### Color

Warm paper, sage trust, restrained accents. Never charity green, never fintech neon, never corporate teal. Tokens are HSL-biased (easier to tune lightness later).

```css
/* tokens in src/styles/tokens.css */

/* Surface — warm off-white, not iCloud blue-white */
--bg:              #FBFAF7;
--bg-raised:       #FFFFFF;
--bg-muted:        #F4F1EA;

/* Ink — near-black, never pure black */
--ink:             #1F2421;
--ink-soft:        #4A524E;
--ink-muted:       #7E867F;
--ink-disabled:    #B7BDB5;

/* Sage — primary, trustworthy, neighborly */
--sage:            #4F7F6A;
--sage-deep:       #3A6551;
--sage-soft:       #E8EFE9;

/* Terracotta — urgent actions only (call now) */
--terracotta:      #C96F4A;
--terracotta-soft: #FAE9E1;

/* Mustard — "likely" confidence tier, NOT warnings */
--mustard:         #D9A441;
--mustard-soft:    #FBEFD0;

/* Stone — stale confidence, quiet UI */
--stone:           #9A9A92;
--stone-soft:      #EEECE6;

/* Border */
--border:          #E7E3DA;
--border-strong:   #CEC9BD;
```

**Rules:**
- **Never red.** Stale data is not danger. Red is reserved for form validation errors only (and even then, prefer terracotta).
- **Mustard means "likely," not "caution."** The color language of "yellow = warning" is wrong for this domain. We use mustard to signal *partial confidence*, which is a neutral, honest fact.
- **Sage for trust and primary actions.** Every primary button is sage.
- **Terracotta only for "call now" urgency and error micro-copy.** Don't let it creep into primary flows.
- **No gradients.** Anywhere. One exception: a subtle vertical sage→paper fade on the Home hero. That's it.
- **Contrast minimums:** `--ink` on `--bg` = WCAG AAA. `--ink-soft` on `--bg` = WCAG AA minimum. Test every text pair.

### Typography

```css
--font-ui:   "Inter", system-ui, sans-serif;
--font-display: "Inter Tight", "Inter", sans-serif;

/* Size ramp — fewer steps than default Tailwind */
--text-xs:   13px;  /* meta only */
--text-sm:   15px;  /* secondary */
--text-base: 17px;  /* body — bigger than typical 16px */
--text-md:   19px;  /* card primary */
--text-lg:   24px;  /* section headers */
--text-xl:   32px;  /* page headers */
--text-hero: 44px;  /* home H1, bestmatch time */

--lh-tight:  1.2;
--lh-normal: 1.55;  /* higher than default — breathing room is the point */
--lh-loose:  1.75;

--fw-regular: 400;
--fw-medium:  500;
--fw-semi:    600;
--fw-bold:    700;
```

**Rules:**
- **Body is 17px**, not 16px. Research: food-insecure users skew older and visually strained. Start bigger.
- **Line-height 1.55** baseline. Breathing room is a design feature. (C2 bandwidth tax — denser text is a cognitive cost.)
- **Inter only.** One family. Inter Tight for display when we need slightly more density at large sizes.
- **No italics** in UI. They're harder to read at low vision.
- **No all-caps** except the `font-weight: 600` nav labels if we use any.
- **Max line length: 68ch** for body text. Longer lines are fatiguing.

### Spacing

Base unit: **4px**. Scale: `4, 8, 12, 16, 20, 24, 32, 40, 56, 72, 96`.

- **Card padding:** 20–24px. Nothing tighter.
- **Screen padding:** 20px mobile, 32px tablet, 56px desktop with a max content width of `680px` for single-column reading surfaces.
- **Vertical rhythm:** 24px between cards, 40px between sections. Users should feel the *breathing room* immediately.

### Radius

```css
--r-sm:  8px;   /* chips, small buttons */
--r-md:  12px;  /* inputs */
--r-lg:  16px;  /* cards */
--r-xl:  24px;  /* hero card */
--r-full: 999px;
```

**Rules:**
- **Nothing has sharp corners.** Corners are visual tension; we want calm.
- **Hero card is 24px radius.** Larger than normal — it reads as "important."

### Shadow

One shadow value. Never more. Never layered.

```css
--shadow-card: 0 1px 2px rgba(31, 36, 33, 0.04), 0 8px 24px -12px rgba(31, 36, 33, 0.08);
--shadow-hero: 0 4px 8px rgba(31, 36, 33, 0.06), 0 24px 56px -24px rgba(31, 36, 33, 0.14);
```

No `inset` shadows. No glassmorphism. No frosted blur.

### Motion

Motion has one job: guide the eye toward the next decision.

```css
--ease: cubic-bezier(0.22, 1, 0.36, 1);  /* ease-out-expo-ish */
--dur-fast: 140ms;
--dur-med:  220ms;
--dur-slow: 360ms;
```

Rules:
- **Primary card entrance:** 360ms fade-up from translateY(8px). One time, on first paint.
- **Button press:** scale(0.98), 140ms.
- **Route transitions:** crossfade 220ms. No slide, no push, no parallax.
- **Never bounce.** Never sparkle. Never celebrate. Nothing "performs."
- **Prefers-reduced-motion:** all transitions collapse to 0ms. Test with OS toggle.

### Imagery

**No photographs of people.** Not stock, not custom. Research finding: charity-brochure imagery is a supplicant-framing signal. Nutrire warmth comes from type, space, and color — not from smiling faces.

**Allowed imagery:**
- Abstract botanical illustrations (line art, single-color sage) — sparingly, on Home and empty states
- Custom map tiles (see §7)
- A single small logo wordmark

**Icons:** Lucide-react (open source). One weight (1.5px stroke). Always paired with text labels in primary navigation.

---

## 3. Component primitives

Locked early. The Golden Card sets the visual vocabulary for the whole app.

### 3.1 The Golden Card (Best Match hero)

**Purpose:** the screen that wins the challenge. Maria's single answer.

**Anatomy (top to bottom):**

```
┌─────────────────────────────────────┐
│  TOMORROW · 10:00 AM — 1:00 PM       │  ← eyebrow: time, --text-sm, --sage-deep, semi
│                                      │
│  Saturday Fresh Market               │  ← title: --text-xl, --ink, semibold
│  Martha's Table · Columbia Heights   │  ← org + neighborhood: --text-base, --ink-soft
│                                      │
│  ────── 18 min walk ──────            │  ← how: --text-md, medium, sage chip on left
│                                      │
│  ✓ Bring nothing. Just come.         │  ← what-to-bring: plain summary, --text-base
│  ✓ English, Español, አማርኛ             │  ← languages: inline, --text-sm
│                                      │
│  ● Confirmed 2 hours ago             │  ← confidence dot + line, --text-sm, --sage
│                                      │
│  Closest to you, happening tomorrow, │  ← "why": --text-sm, --ink-soft, italic is OK here
│  no ID needed, Spanish spoken.       │
│                                      │
│  ┌─────────────────────────────┐     │  ← primary button, --sage bg, --bg text, full width
│  │     Get directions    →     │     │
│  └─────────────────────────────┘     │
└─────────────────────────────────────┘
   shadow: --shadow-hero
   radius: --r-xl
   padding: 28px
   bg: --bg-raised
```

**Responsive:** on mobile, full-width with 20px screen padding. On desktop, max-width 480px centered.

**Entry animation:** fade-up 360ms, only on first mount. Never re-animates.

**Why this layout, specifically:**

| Field order | Reasoning |
|---|---|
| Time first | Maria's question is "when", not "what." *(R§3 scarcity — tunneling toward immediate need)* |
| Title + org second | Identity — trusted-brand signal (Martha's Table is known) |
| Transit third | "Can I get there?" is Maria's #2 question |
| What to bring fourth | "Will they make me fill things out?" is her #3 question, and dignity-forward answering is load-bearing *(R§4)* |
| Languages fifth | Small, inline, not a separate row — it's context, not priority |
| Confidence sixth | Trust is earned here. Always visible. *(R§4 — Plentiful stale-data complaints)* |
| "Why" seventh | Explanation layer — respects user as thinking person *(R§3 — explanation reduces cognitive load)* |
| CTA last | Single clear action at the bottom-thumb zone *(R§3 — one decision per screen)* |

**Variants:**
- `tier: "verified"` — sage dot, "Confirmed X ago"
- `tier: "likely"` — mustard dot, "Last confirmed X ago. Usually runs weekly."
- `tier: "stale"` — stone dot, *"We haven't confirmed this recently. Call first — (202) 555-0100."* — and the button changes from "Get directions" to "Call first" in terracotta
- `tier: "unknown"` — never shown as Best Match; pushed to All Options list

### 3.2 Backup Card

Smaller version of Golden Card. Same fields but collapsed:

```
┌──────────────────────────────────────┐
│  SAT · 10AM    Martha's Table         │
│  18 min walk   ● verified             │
│  "Bring nothing. Just come."          │
│                         [Details →]  │
└──────────────────────────────────────┘
```

Padding 16px. No shadow on the backup cards (only hero has shadow-hero). `--bg-raised` background. Radius `--r-lg`.

### 3.3 Chip

Used for filters and language support. Not a button — lower weight.

```
┌──────────────┐
│  Today       │  ← --text-sm, --ink-soft, --bg-muted, --r-full, 8px 14px padding
└──────────────┘
```

Selected state: `--sage-soft` background, `--sage-deep` text.
Hover: `--border` 1px ring.

### 3.4 Primary button

```
┌─────────────────────────────────┐
│       Get directions    →       │
└─────────────────────────────────┘
```

- bg: `--sage`
- text: `--bg-raised`
- font: `--text-md` semibold
- padding: 16px 24px
- radius: `--r-lg`
- height: 52px minimum (thumb-friendly)
- press: scale(0.98)
- disabled: `--stone-soft` bg, `--stone` text

**Variant: urgent (call now)**
- bg: `--terracotta`
- Used only for stale-event "Call first" and errors

**Variant: quiet secondary**
- bg: `--bg`
- border: 1px `--border-strong`
- text: `--ink`

### 3.5 Location input

```
┌─────────────────────────────────┐
│  📍  Where are you?              │  ← --text-md, placeholder in --ink-muted
└─────────────────────────────────┘
 + "Use my location" — small sage link below
```

- Height 56px (even bigger than buttons — this is the single most important input in the app)
- Icon on the left, 22px Lucide `map-pin`
- Autofocus on Home
- Autocomplete from Nominatim (later) — plain text fallback now
- Submit on Enter

### 3.6 Confidence dot

```
●  Confirmed 2 hours ago
```

An 8px circle, `--sage` for verified, `--mustard` for likely, `--stone` for stale. Never `--terracotta` (that's for urgent actions, not confidence).

### 3.7 Language chip (inline)

```
English · Español · አማርኛ
```

Plain text, separator `·`, `--text-sm`, `--ink-soft`. No borders, no backgrounds. It's content, not interactive UI.

---

## 4. Screens

### 4.1 Home (`/`)

**Purpose:** soft landing. No self-labeling. One question: where are you.

**Layout:**
```
┌─────────────────────────────────────┐
│                                      │
│         Nutrire                      │  ← wordmark, --text-md, --sage-deep, semibold
│                                      │
│                                      │
│   Free groceries and                 │  ← --text-hero, --ink, semibold
│   meals near you.                    │
│                                      │
│                                      │
│   ┌─────────────────────────────┐   │
│   │  📍 Where are you?           │   │  ← location input, autofocus
│   └─────────────────────────────┘   │
│     Use my location                  │  ← sage text link
│                                      │
│                                      │
│   [ Looking for groceries ]          │  ← contextual chips, optional
│   [ Looking for a hot meal ]         │
│   [ Helping a neighbor ]             │
│                                      │
│                                      │
│                                      │
│   ·  ·  ·                            │  ← quiet below-fold:
│   About · Methodology · EN ES AM     │  ← research entry is "Methodology"
│                                      │
└─────────────────────────────────────┘
```

**Decisions:**
- **No photo, no illustration, no hero image.** The hero is the headline and the input. Empty space is the feature.
- **Chips are optional suggestions, not doors.** User can ignore them and just tap submit. This is the "no self-labeling" walk-back. *(C1)*
- **Language switcher is a tiny link, not a dropdown.** Auto-detected from `navigator.language`. Spanish users land in Spanish.
- **Methodology link is a footer link**, not a nav item. Judges (Samira) will find it. Maria will never think about it. *(The three-door walk-back from the research session.)*

### 4.2 Best Match (`/find/:location`)

**Purpose:** the money shot. One answer.

**Layout:**
```
┌─────────────────────────────────────┐
│  ← Back                             │  ← --text-sm, --ink-soft, 20px padding
│                                      │
│  Here's a good option for you.      │  ← --text-lg, --ink-soft, warm preamble
│                                      │
│  ┌─────────────────────────────┐   │
│  │      [ Golden Card ]         │   │  ← the hero, full spec in §3.1
│  └─────────────────────────────┘   │
│                                      │
│  If that doesn't work:              │  ← --text-sm, --ink-soft
│                                      │
│  ┌─────────────────────────────┐   │
│  │      [ Backup Card 1 ]       │   │
│  └─────────────────────────────┘   │
│  ┌─────────────────────────────┐   │
│  │      [ Backup Card 2 ]       │   │
│  └─────────────────────────────┘   │
│                                      │
│  See all options near me →          │  ← quiet sage link
│                                      │
└─────────────────────────────────────┘
```

**Decisions:**
- **"Here's a good option for you"** — warm preamble from a neighbor. Not "Your recommendation" or "Best match."
- **Two backups, not three.** Two is cognitively manageable under scarcity; three invites comparison. *(R§3)*
- **"See all" is a quiet link**, not a button. We don't want to push users into the list view — the list view is for brokers and persistence, not for Maria's primary flow.

### 4.3 Event Detail (`/event/:id`)

**Purpose:** everything the user needs to know before showing up.

**Sections:**
```
1. Back bar + share button (top)
2. Restated Golden Card content (no CTA here yet)
3. "What to expect" — 3 bullets, plain language
4. "Who's welcome" — eligibility in full, dignity-forward copy
5. Full address + transit breakdown
6. Primary action: "Get directions" or "Call first" (depending on confidence)
7. Source citation: "From Martha's Table website, last checked April 8."
8. Tiny feedback: "Was this accurate? [👍] [👎]"
9. "If that doesn't work:" — 2 backups strip at the bottom
```

**Decisions:**
- Directions button opens `geo:` URL (native maps) on mobile, Google Maps link fallback on desktop.
- Call button uses `tel:` — one tap to phone.
- Share button (top-right) produces a pre-filled WhatsApp/SMS message with the key info in the user's language. *(C6 — broker primitive baked in from day one.)*
- Feedback is anonymous. One tap. No text box. No stars. *(R§4 — 96% of clients want anonymous feedback.)*

### 4.4 All Options (`/all`)

**Purpose:** the list view — mostly for brokers and for users who rejected the Best Match.

**Layout:**
```
Chips row: [Today] [This week] [Walkable] [By bus] [Español] [Amharic] [No ID]

Vertical list of cards (Backup Card style) with pagination or infinite scroll.

Each card tappable → Event Detail.
```

**Decisions:**
- Chips are the only filter UI. No dropdowns, no sidebars, no advanced panel.
- Default sort is "recommended" (ranking engine).
- Chips combine additively.
- No map here — map lives on the Research view only. The household side is never map-first.

### 4.5 Broker mode (`/helping`)

**Purpose:** the quiet second gear for case workers, volunteers, neighbors helping multiple households.

**Layout:**
```
Top: "Helping someone else find food?" — single line
Location input (same component as Home)

After submitting:
Best Match + list view combined
+ "Save this for [name]" — per-card save action
+ "Print a one-pager" — top right button
+ "Share via WhatsApp" — top right button

Sidebar (desktop) or drawer (mobile): "Your saved list"
- Add households (just a name label, no login)
- Assign events to a household
- Export the list as a printable one-pager
```

**Decisions:**
- **No accounts.** Everything in localStorage. Clear history button is prominent.
- **Print view is a dedicated route `/print/:listId`** — clean CSS print styles, one page per household.
- **Share generates a plain-text message**, not a Nutrire-branded URL. A broker's client may not have data to load a URL.

### 4.6 Helper views (`/give`)

**Purpose:** James (donor) and Priya (volunteer).

**Sub-routes:**
- `/give` — two cards: "Give groceries or money" and "Give time"
- `/give/donate` — donor view with map sorted by need
- `/give/volunteer` — volunteer shift feed

**Donor view layout:**
```
Top-left: intro text — "Where your help matters most this week."
Map on left (desktop) / top (mobile) — pins color-coded by need score
Scrollable list on right — org cards sorted by need

Each org card:
- Name + neighborhood
- Current need: "This week: rice, canned protein, diapers"
- Data line: "Serves a tract where 38% of households have no vehicle"
- Drop-off address + hours
- Two buttons: "Drop off food" (opens maps) + "Give directly" (opens donate URL)
```

**Volunteer view layout:**
```
Top: filter chips — [This week] [This weekend] [Drive] [Translate] [Within 5mi]
Below: shift feed (Too Good To Go card rhythm)

Each shift card:
- Date + time (eyebrow)
- Role (title)
- Org + location
- Spots: "3 of 8 spots left"
- Skills chips (optional)
- Commit button: "Sign up" (opens org's URL or mailto)
```

### 4.7 Research view (`/map`)

**Purpose:** Samira and judges. The Equity Gap choropleth.

**Layout:**
```
Full-viewport Leaflet map (max-width none)
Top-left floating card: layer toggle
  ○ Equity Gap (default)
  ○ Need score
  ○ Supply score
  ○ Food desert (USDA)
  ○ Language isolation — Amharic
  ○ Language isolation — Spanish
  ○ Transit reach from events

Top-right: "Download data" button (downloads insights.json)

Click on a tract → right side panel (drawer on mobile):
  - Tract stats
  - Nearby events list
  - Gap score breakdown
  - Recommendation from the engine (if present)

Bottom-left: tiny link "Methodology" → /methodology
```

**Decisions:**
- Leaflet with custom tile style (see §7). No default OSM tiles.
- Choropleth uses 7 steps from `--sage-soft` to `--terracotta`. Stable, accessible color ramp.
- Tract hover shows tooltip. Tract click opens the drawer.
- Legend is a small fixed element bottom-right.

### 4.8 Recommendations (`/recommendations`)

**Purpose:** the research contribution — gap-filling suggestions.

**Layout:**
```
Intro paragraph (the research claim)
Grid of recommendation cards (3 columns desktop, 1 column mobile)

Each card:
- Area name (big)
- "Why" paragraph
- Stats table (need score, population, language gap)
- Suggested host
- Suggested cadence
- Expected reach
- "View on map" link → highlights tract on /map
```

### 4.9 Methodology (`/methodology`)

**Purpose:** research-grade documentation. This page is for judges and the PDF report.

Long-form content. Plain typography, max-width 680px. Links to data sources. Links to research citations. Honest limitations section.

---

## 5. Layout and navigation

### Navigation chrome

- **Household side (Home, Best Match, Detail, All Options):** NO nav bar. No tab bar. No drawer. A tiny back chevron top-left where needed. A tiny "Nutrire" wordmark top-center. That's it. *(C2 scarcity — navigation chrome is cognitive cost.)*
- **Helper / Research side:** a minimal top bar with 3 links: Find Food · Give · Map. Active state is sage underline.
- **Footer:** one line of links in the page footer — About · Methodology · Languages. Never shown on Home (Home has its own quiet footer).

### Responsive

- Mobile first. Every layout drawn mobile first, then enhanced.
- Breakpoint: 720px (tablet), 1024px (desktop).
- Maria's flow is optimized for 360px wide.
- Research view is optimized for 1024px+.
- Helper views split at 720px — map+list side-by-side on desktop, stacked on mobile.

---

## 6. Accessibility (the floor, not the ceiling)

### Hard requirements (tested)

- WCAG 2.1 AA contrast on all text/background pairs
- All interactive elements reachable by keyboard, focus visible
- All images and icons have accessible labels
- Screen reader reading order matches visual order
- Language attribute set correctly per screen content
- Form inputs have visible and programmatic labels
- Tap targets ≥44x44 px
- Respect `prefers-reduced-motion`
- Respect `prefers-color-scheme` — but we only ship light mode in v1 (cited limitation)
- Text resizable to 200% without horizontal scroll
- Heading hierarchy is semantic (one H1 per page)

### Softer commitments (tried, documented)

- Dyslexia-friendly font toggle (OpenDyslexic optional)
- Large-text mode that re-lays-out, not just scales
- High-contrast mode override
- Screen reader tested with NVDA (Windows) and VoiceOver (macOS) — at least the Maria flow
- Works offline once the JSON is cached

---

## 7. Map style

Leaflet, but not default OSM tiles. Use a custom tile style that matches the sage/paper palette.

**Options (open source, free):**
1. **Stadia Maps `stamen_toner_lite`** — free tier, looks premium, paper-like
2. **CARTO `positron`** — free, minimal, neutral
3. **OpenFreeMap** — self-hostable, completely free

Go with **CARTO Positron** for v1 (fastest to integrate, neutral base), then consider custom styling with Protomaps if time permits. Default Leaflet tiles are banned — they're the "ArcGIS iframe" aesthetic in research terms.

Map overlay style:
- Choropleth: 7-step color ramp from `--sage-soft` through `--mustard` to `--terracotta`
- Event pins: small sage dots, clustered via Leaflet.markercluster
- Tract borders: 0.5px `--border-strong`, 0.3 opacity
- Hover highlight: `--sage` outline, 2px
- Selected tract: `--sage-deep` outline, 2px + filled overlay

---

## 8. Anti-patterns (explicit bans)

These have been tried elsewhere, proven to fail (often in the competitive-analysis doc). Never introduce them.

- ❌ Sign-up wall before showing results
- ❌ "Welcome tour" / onboarding carousel
- ❌ Cookie/privacy banner that blocks interaction
- ❌ Ads or sponsorships anywhere on the household side
- ❌ "Donate now" CTA on any household-side screen
- ❌ Stock photos of smiling families holding produce
- ❌ Loading spinners longer than 300ms (use skeleton screens)
- ❌ Map-first Home screen
- ❌ Ranked numeric lists (1., 2., 3.)
- ❌ Star ratings on organizations
- ❌ "Likes" or social signals on events
- ❌ Pop-ups of any kind
- ❌ Email/phone capture
- ❌ "Download our app" banner
- ❌ Red warning triangles
- ❌ Glassmorphism
- ❌ Dark mode as v1 requirement (cite as future work)
- ❌ Chat/AI assistant bubble
- ❌ "Premium features" or upsells of any kind

---

## 9. Quality bar (how we know it's good enough to ship)

A screen ships when it passes all of these:

1. **The Grandma test:** could a non-technical person use this in 10 seconds with no instructions?
2. **The stress test:** does it still work if the user is distracted, tired, and on a slow connection?
3. **The stigma test:** would a user feel more or less dignified than before they opened it? (Must be more.)
4. **The bandwidth test:** can the screen be understood in one recognition pass, not multiple evaluation passes?
5. **The honesty test:** does every claim on the screen come from the data, or are we bluffing?
6. **The banned-words test:** does the copy pass §2 of COPY.md?
7. **The accessibility test:** does it pass §6 of this doc?
8. **The three-translation test:** does it still work in Spanish and Amharic without visual break?

If any test fails, the screen doesn't ship.

---

## 10. Tech stack (locked)

- **Vite** (build tool)
- **React 18** + **TypeScript** (strict mode)
- **Tailwind CSS 3** (with our tokens as CSS vars, consumed via `@layer base`)
- **shadcn/ui** (for accessible primitives — Button, Dialog, Input, etc.)
- **React Router v6** (for the routes in §4)
- **Zustand** (tiny state — location, saved broker list, language)
- **Leaflet** + **react-leaflet** (map in Research view only)
- **Leaflet.markercluster** (for pins)
- **i18next** + **react-i18next** (for EN/ES/AM)
- **Lucide-react** (icons)
- **fuse.js** (fuzzy search in All Options)
- **date-fns** (date/time formatting with locales)

No Next.js, no React Server Components — Vite SPA is sufficient and ships static. No Redux, no Apollo. Nothing else unless justified.

---

## 11. File layout

```
src/
├── main.tsx
├── App.tsx                      # router
├── types.ts                     # mirrors SCHEMA.md interfaces
├── data/
│   ├── mock-graph.ts            # hand-crafted DMV mock (starts here)
│   ├── mock-tracts.ts
│   └── index.ts                 # loader (swaps to real JSON later)
├── lib/
│   ├── ranking.ts               # deterministic ranking engine
│   ├── geo.ts                   # haversine, transit helpers
│   ├── time.ts                  # relative time strings
│   └── freshness.ts             # confidence tier → copy
├── pages/
│   ├── Home.tsx
│   ├── BestMatch.tsx
│   ├── EventDetail.tsx
│   ├── AllOptions.tsx
│   ├── Broker.tsx
│   ├── GiveHome.tsx
│   ├── Donate.tsx
│   ├── Volunteer.tsx
│   ├── Map.tsx                  # research / equity gap
│   ├── Recommendations.tsx
│   └── Methodology.tsx
├── components/
│   ├── GoldenCard.tsx
│   ├── BackupCard.tsx
│   ├── Chip.tsx
│   ├── Button.tsx               # shadcn-based
│   ├── LocationInput.tsx
│   ├── ConfidenceDot.tsx
│   ├── LanguageChips.tsx
│   ├── EventShareMenu.tsx
│   └── MapChoropleth.tsx
├── i18n/
│   ├── en.json
│   ├── es.json
│   ├── am.json
│   └── index.ts
├── styles/
│   ├── tokens.css               # CSS vars
│   └── globals.css
└── store/
    ├── location.ts              # Zustand
    ├── brokerList.ts
    └── language.ts
```

---

## 12. Build order (for the coding phase)

1. Scaffold the project.
2. Drop in tokens and Tailwind config.
3. Write `types.ts` mirroring SCHEMA.md.
4. Hand-craft `mock-graph.ts` with 12 real DMV events.
5. Build the **Golden Card** in isolation at `/sandbox` — iterate until it passes the quality bar.
6. Wire up `ranking.ts`.
7. Build **Home** → **Best Match** → **Event Detail** — the Maria linear flow, all against mocks.
8. Build **All Options**.
9. Build **Broker mode** (uses the same components as Maria with a batch layer on top).
10. Build **Helper views** (Donate + Volunteer) — simpler cards, lower effort.
11. Build **Research view** (Equity Map) — this is the Samira visual moment.
12. Build **Recommendations** and **Methodology**.
13. i18n pass (EN/ES/AM).
14. Accessibility pass.
15. Run it locally, test every flow, screenshot.

Deployment and git are out of scope for now — build and test locally.

---

**End of design spec.** This doc is the contract for every PR. If a PR doesn't cite this doc, it doesn't merge.
