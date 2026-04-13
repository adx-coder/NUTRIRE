# Stitch Design Prompt — Nutrire

## What is Nutrire

Nutrire is a **mobile-first food access app** for the DMV (DC, Maryland, Virginia). It helps families find free groceries and meals near them — verified hours, multilingual (English, Spanish, Amharic), and AI-generated "what to expect" guides that reduce anxiety before a first visit.

**Design all screens as iPhone 15 Pro screens (393×852px).** This is a progressive web app that runs full-screen on mobile — no browser chrome. It should feel native iOS — smooth transitions, safe area padding, thumb-reachable actions, bottom-anchored CTAs.

It is NOT a charity app. It should feel like a premium consumer product — think Anthropic claude.ai, Cohere, Linear, or Arc Browser. Clean, warm, confident. The kind of app a stressed parent on a cracked phone can use and immediately feel "ok, I can go here."

**1,401 real organizations** from 5 data sources. Every org has LLM-generated warm copy, structured hours, and eligibility info.

---

## Design Language

**Aesthetic:** Cohere Labs (reeded glass texture, dark gradient cards, botanical accents) meets Anthropic claude.ai (warm cream, conversational simplicity, generous whitespace) meets native iOS (safe areas, large touch targets, bottom sheets, haptic-feeling transitions).

**Colors:**
- Background: `#FBFAF7` (warm paper), `#FFFFFF` (raised), `#F4F1EA` (muted)
- Ink: `#1F2421` (primary), `#4A524E` (soft), `#7E867F` (muted)
- Sage (trust): `#4F7F6A`, `#3A6551` deep, `#E8EFE9` soft
- Terracotta (urgent): `#C96F4A`, `#FAE9E1` soft
- Mustard (warm): `#D9A441`, `#FBEFD0` soft
- Stone (stale): `#9A9A92`

**Typography:** Inter (body), Inter Tight (display/headings, bold, tight tracking). Body 15-17px. Eyebrows 11px uppercase. Headlines 28-36px.

**Textures:**
- Reeded glass: vertical ribbed lines (repeating gradient, ~6px period) on dark sections
- Paper grain: subtle noise overlay on warm background
- Botanical SVG accents: fern/wheat/leaf at 12-22% opacity on dark cards

**Corners:** Cards 20-24px. Buttons 16px. Inputs 12px.

**Shadows:** Warm, soft. Hero cards get a green/amber/grey glow based on data confidence.

---

## Screen 1: Home (iPhone)

The first thing users see. Warm landing — not a charity site, not a government portal.

**Safe area top:** Status bar (time, battery, signal)

**Content (scrollable):**
- Top bar: Nutrire logo mark (animated circle) + "Nutrire" wordmark left. "EN / ES / አማ" language pills right.
- Hero section (centered):
  - Small live badge: pulsing green dot + "Live across DC · MD · VA"
  - Giant headline: "Free groceries and meals, **near you.**" — 36px display, "near you" in sage-deep with a soft underline swoosh
  - Subhead: "No sign-up. No forms. Just the closest option you can actually get to." — 15px, ink-soft
- **Location input** (prominent, centered):
  - 56px tall pill with MapPin icon, placeholder "ZIP or neighborhood", green submit arrow
  - Below: "📍 Use my location" text link
- **Quick chips:** "Groceries this week" (sage) · "Hot meal tonight" (mustard) · "Diapers or formula" (terracotta)
- **Stats strip** (horizontal scroll): 4 reeded-glass mini cards with botanical accents:
  - "1.5M facing hunger" · "49% PG County" · "14 languages" · "1,400+ tracked"
- **Three door cards** (vertical stack, each full-width):
  - Dark sage gradient card: "Give food or money" with heart icon + fern accent
  - Dark mustard: "Volunteer" with users icon + wheat accent
  - Dark terracotta: "Explore the gap" with chart icon + leaf accent
  - Each: reeded glass texture, botanical accent, title, one-line blurb, arrow
- **Research banner:** Full-width dark sage card: "Nutrire is also a census-tract Equity Gap engine." + "View methodology →"

---

## Screen 2: Best Match (iPhone) — THE MONEY SHOT

One answer. The app decided for you.

**Top bar:** "← Back" left, location chip "Columbia Heights · Change" right

**Why-this-match strip:** Horizontal scrollable row of small tags: "Open now" · "12 min walk" · "No ID" · "Spanish" · "Confirmed". Sage-soft bg, sage-deep text.

**The Golden Card (full-width, rounded-24px):**

**DARK ZONE** (top — dark sage gradient + reeded glass lines + diagonal light sweep):
- Top bar: pulsing white dot + "Open now · closes 4pm" ... "0.8 mi"
- Org name: **"Martha's Table"** — 26px, white, bold
- "Columbia Heights, DC" — 12px, white/50%
- heroCopy: *"Walk-in fresh market with produce, bread, and dairy every Saturday morning — no forms, no questions."* — 16px, white/90%, light weight. **This is the hero content.**
- Transit: 🚶 icon + "12 min walk · near U Street Metro" — 12px, white/60%

**LIGHT ZONE** (bottom — warm paper):
- **"WHAT TO EXPECT"** eyebrow
- 3 bullets with sage ✓ circles:
  - "Walk in on 14th St. Staff will greet you."
  - "No forms. Tell them your first name if you want."
  - "~15 minutes. Full bag of produce, bread, dairy."
- **Eligibility highlight:** sage-soft card: "Anyone welcome. Bring nothing."
- **CTA:** Full-width sage-deep button 48px: **"Get directions →"**
- **Footer row:** "(202) 328-6608 · Share" left, "● Confirmed 2h ago" right, muted 12px

**Confidence glow:** Green ring/shadow around entire card (fresh data). Amber ring for recent. Grey for stale.

**Map strip** (below card, 160px, rounded-16px):
- Shows user pin (green) → org pin (sage) with dashed line
- Light Carto basemap

**Backup section:**
- "IF THAT DOESN'T WORK" eyebrow + "See all 1,401 →"
- 3 compact rows (rounded-16px, white, subtle border):
  - Each: org name + distance right, status dot + label, heroCopy 2-line clamp, eligibility + "Details →"

---

## Screen 3: All Options (iPhone)

Full list with search. Mobile = single column, no map.

**Top bar:** "← Back" left, location chip right

**Content:**
- Headline: "1,401 options near you" — 24px display
- **Search bar:** magnifying glass icon, "Try 'teff flour' or 'hot meals'" placeholder, rounded-xl. Full width.
- **Filter chips** (horizontal scroll): "Open now" · "Today" · "Walkable" · "Near metro" · "Español" · "አማርኛ" · "No ID" · "Delivers"
- **Results list:** Stacked backup cards (same compact design). Each card:
  - Org name bold + distance muted right
  - Pulsing dot + open status
  - heroCopy in 14px, 2-line clamp
  - Eligibility sage + "Details →"
  - Subtle confidence border glow

---

## Screen 4: Org Detail (iPhone)

The full deep-dive. Dark hero header flowing into light scrollable content.

**Dark hero section** (extends behind status bar, full-bleed):
- Nav overlay: "← Back" (white) left, "Send" (glass pill) right
- Pulsing dot + "Open now · closes 4pm" ... "0.8 mi"
- **Org name: 28px, white, bold**
- "Columbia Heights, DC" white/40%
- heroCopy: 17px, white/85%, light weight
- Two buttons: "Get directions" (white bg, sage text, rounded-2xl) + phone (glass pill)
- Reeded glass overlay + light sweep

**Light sections** (scrollable, warm paper):
- **What to expect** — 3 checkmark bullets
- **Who's welcome** — eligibility in sage-soft card + cultural notes italic
- **Hours** — clock icon + hours text + ⚠️ reconciliation warning if applicable
- **Getting there** — MapPin + full address + nearest transit
- **Neighborhood** — 2×2 stat grid (poverty rate, SNAP, income, food insecurity). Food insecurity >40% gets terracotta highlight.
- **What's available** — food type chips in muted rounded labels
- **Source** — confidence dot + "Confirmed 2h ago" + source link
- **Feedback** — "Was this accurate?" with ✓ / ✗ circle buttons
- Divider
- **If that doesn't work** — 3 backup cards

**Share sheet** (iOS-style bottom sheet, slides up):
- Handle bar at top
- "Send this to them" heading
- Message preview in muted card
- "Send on WhatsApp" (sage), "Send by text" (outlined), "Copy" (text)

---

## Screen 5: Equity Map (iPhone)

Full-screen map with bottom sheet drawers.

**Map fills viewport:**
- 1,400+ small green org pins
- Terracotta circle hotspots for equity gaps (radius = gap severity)
- User pin (larger green with white border)
- Light Carto basemap

**Floating controls:**
- Top-left: "← Back" glass pill
- Top-right: "Download" small sage pill
- Bottom: floating stats bar: "1,401 resources · 60 gaps · 23 underserved"

**Bottom sheet** (iOS-style, draggable, slides up on pin tap):
- Handle bar
- For org: name, heroCopy italic, phone, hours, eligibility, first-visit bullets, "View details →"
- For gap: "⚠️ Equity gap · ZIP 20744", description, need/supply/gap stats, suggested host, population

**Segmented control** (top of bottom sheet when expanded): "All" | "Resources" | "Gaps"

---

## Screen 6: Recommendations (iPhone)

Research contribution. Scrollable card list.

**Top bar:** "← Back" + "Recommendations"

**Content:**
- Eyebrow: "RESEARCH CONTRIBUTION"
- Headline: "Where new pantries would close the biggest gaps." — 24px
- Subtitle: methodology explanation, 14px, ink-soft

**Scrollable card list:**
- Top 3: dark terracotta gradient + reeded glass + botanical accent
- 4-10: dark mustard gradient
- Rest: light paper with sage reeded lines
- Each card (full-width, rounded-20px):
  - ZIP eyebrow + area name title + priority rank badge
  - Description text
  - 3-stat row: population, need score, underserved count
  - Gap % + nearby orgs chips
  - Suggested host card (sage-soft nested card)
  - "View on map" link

**Bottom:** "Download insights JSON" sage button

---

## Screen 7: Donate (iPhone)

Donor-focused list.

**Top bar:** "← Back" + "Donate"
- Eyebrow: "DONOR VIEW"
- Headline: "Where your help matters most."
- Filter chips (horizontal scroll): "Food" · "Money" · "Within 5 mi" · "Has link"
- Card list: org name, address, "♥ Food" / "$ Money" chips, distance, "Donate →" sage button

---

## Screen 8: Volunteer (iPhone)

Same structure as Donate.
- Filter chips: "Within 10 mi" · "Sign-up link" · "Spanish needed"
- Cards: org name, "👥 Volunteers welcome" chip, language chips, "Sign up →"

---

## UX Principles

1. **Native iOS feel.** Safe areas, 44px min touch targets, bottom sheets not modals, thumb-reachable CTAs, no hover-dependent interactions.
2. **No charity aesthetic.** Premium consumer product. The team that built Linear designed this.
3. **heroCopy and firstVisitGuide are the innovation.** No other food app has LLM-generated anxiety-reducing content. Make them the visual hero.
4. **One answer, not a list.** BestMatch = ONE recommendation. The app decided for you.
5. **Confidence is visual.** Green glow = fresh. Amber = recent. Grey = stale. Pulsing dot = open now.
6. **Share is first-class.** Equal to directions. People share food info by word of mouth.
7. **Reeded glass is the signature texture.** Vertical ribbed lines on dark gradient sections.
8. **Botanical accents add warmth.** Fern, wheat, leaf SVGs at low opacity prevent dark sections from feeling corporate.
9. **Every screen works at 393px wide.** No assumptions about desktop.
10. **Progressive disclosure.** BestMatch shows only essentials. OrgDetail shows everything. Don't dump all data at once.
