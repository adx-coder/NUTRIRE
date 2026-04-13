# Nutrire — Copy Style Guide

This document defines how Nutrire speaks to users. Copy is a design surface in this project — not decoration. Every string we ship is pressure-tested against three questions:

1. **Does it label the user?** (If yes, it's a separation mechanism per Link & Phelan 2001. Rewrite.)
2. **Does it assume bandwidth the user may not have?** (Mullainathan-Shafir scarcity: cut to half the normal consumer-app length.)
3. **Would a neighbor say it?** (Katie Martin's framing: neighbors, not burdens.)

If any answer fails, the string doesn't ship.

All copy rules here are cited to [research/foundation.md](../research/foundation.md).

---

## 1. Voice: four words

**Warm. Brief. Neighborly. Honest.**

- **Warm** — tone is that of a friend who has done this before and will walk you through it. Not a government notice. Not a nonprofit fundraiser. Not a cheerful app.
- **Brief** — fewer words than you think. Cut everything that doesn't carry information or emotional weight.
- **Neighborly** — second person ("you"), never third ("individuals"). Everyday words, never bureaucratic ones.
- **Honest** — if we don't know, we say so. If it might be wrong, we say so. If stale, we don't hide it. Honesty is dignity. (C5 in research foundation.)

---

## 2. Banned words (and why)

These words never appear in user-facing copy. Each has a citation to the research.

| Banned | Reason | Use instead |
|---|---|---|
| **needy** | Labels the user; creates separation (Link & Phelan 2001) | (omit entirely — describe the situation, not the person) |
| **food insecure** | Clinical label; stigmatized identity per Goffman | (omit; use "running low on groceries this week" if context needed) |
| **recipient** | Charity hierarchy — labels user as "one who receives" | "neighbor", or just "you" |
| **beneficiary** | Worse version of recipient | "you" |
| **emergency food** | Reframes routine access as crisis; triggers shame (Garthwaite 2016) | "free groceries this week" / "community meals" |
| **assistance** | Bureaucratic; flags user as in need of help | "free groceries" / "meals" / "a box to take home" |
| **eligible** | Forces self-categorization before showing value | (omit; describe what you need to bring, not whether you qualify) |
| **underserved** | Researcher word; labels a community | (in researcher/methodology pages only) |
| **low-income** | Labels user; separation | (omit; never describe the user's income in the user surface) |
| **at-risk** | Public health jargon; labels user | (omit) |
| **in need** | Supplicant framing | (omit) |
| **welfare** | Loaded term; suppresses take-up (Moffitt takeup literature) | "SNAP" / "food benefits" / "free groceries" |
| **client** | Pantry word, not user word | "neighbor" / "you" / "visitor" |
| **case** | Bureaucratic | "situation" / "visit" |
| **intake** | Bureaucratic | "sign-in" / "front desk" |
| **verification** | Sounds like the police | "check" |
| **must** | Commanding | "please" / "you'll need" |
| **required** | Feels like a gate | "bring" / "please bring" |
| **Do not** | Scolding | "Skip this if…" / "You can come another day if…" |
| **unfortunately** | Apologetic preamble that delays the answer | (cut; give the answer directly) |
| **please note** | Bureaucratic filler | (cut) |
| **please be advised** | Legalistic | (cut) |
| **hunger crisis** | Headline word for donors, stigma word for users | (donor side only) |
| **fighting hunger** | Charity war-metaphor | (donor side only, sparingly) |

---

## 3. Preferred phrasings

### For the household (Maria) surface

| Situation | Use this | Not this |
|---|---|---|
| App headline | *"Free groceries and meals near you."* | "Food Assistance Finder" |
| Search prompt | *"Where are you?"* | "Enter your ZIP code to locate services" |
| Best match intro | *"Here's a good option for you."* | "Based on your query, we recommend:" |
| What-to-bring (ideal) | *"Bring nothing. Just come."* | "No documentation required" |
| What-to-bring (ID case) | *"Bring a photo ID if you have one."* | "Valid photo identification required" |
| What-to-bring (address) | *"Bring something with your address on it — a bill or letter is fine."* | "Proof of residency required" |
| Eligibility (open) | *"Anyone is welcome."* | "Open to eligible residents" |
| Eligibility (restricted) | *"They serve DC residents first. They rarely turn people away."* | "DC residents only" |
| Confidence — verified | *"Confirmed 2 hours ago."* | "Verified data" |
| Confidence — stale | *"We haven't confirmed this recently. Call first — the number's below."* | "Data may be outdated" |
| Directions CTA | *"Get directions"* | "Navigate" |
| Call CTA | *"Call first"* | "Contact" |
| Empty state | *"Nothing in the next 24 hours right near you. Here are 3 to call."* | "No results found" |
| Language switch | *"Cambiar a español"* / *"ወደ አማርኛ ቀይር"* | "Language: ES" |
| Save/follow | *"This is my regular place"* | "Add to favorites" |
| Feedback | *"Was this accurate?"* (one tap yes/no) | "Rate this result" |
| Error | *"Something's off on our end. Try again in a minute."* | "Error 500: Internal Server Error" |

### For the broker surface (soft entry)

| Situation | Use this | Not this |
|---|---|---|
| Broker link entry | *"Helping someone else find food?"* | "Case worker mode" |
| Batch save | *"Save these for later"* | "Add to case file" |
| Share | *"Send this to them"* (WhatsApp/SMS) | "Export" |
| Print | *"Print a one-pager"* | "Generate report" |

### For the donor surface (James)

Different audience, different voice — more data, still warm. No charity-war-metaphors.

| Situation | Use this | Not this |
|---|---|---|
| Donor entry | *"Where your help matters most right now."* | "Donate to fight hunger" |
| Org card lead | *"This neighborhood is stretched. Here's who's closest."* | "High-need area. Make a donation." |
| Current needs | *"This week they need rice, canned protein, and diapers."* | "Current urgent needs:" |
| Drop-off | *"You can drop food here Monday–Friday, 9–4."* | "Donation hours" |
| Give money CTA | *"Give directly"* | "Donate Now" |

### For the volunteer surface (Priya)

| Situation | Use this | Not this |
|---|---|---|
| Volunteer entry | *"Give a few hours this week."* | "Volunteer Opportunities" |
| Shift card | *"Saturday 9am–12pm · 3 of 8 spots left"* | "SHIFT AVAILABLE: Sort Donations" |
| Commit | *"Sign up"* | "Register for this opportunity" |

### For the research / methodology surface (Samira)

Here the voice shifts — researchers expect precise, academic language. Use banned user-facing terms freely here (*underserved, food insecurity, equity gap*), because the audience is different and the terms are appropriate. But still avoid charity-war-metaphors.

---

## 4. Tone examples — before and after

Each row is a specific string that will appear in the app. The "before" is what a typical civic-tech or nonprofit site would ship. The "after" is what Nutrire ships.

### Home screen hero

**Before:**
> *"Welcome to Nutrire, the comprehensive food assistance locator for the DC metropolitan area. Find food pantries, meal programs, and emergency food resources in your neighborhood. Please enter your ZIP code or share your location to begin."*

**After:**
> *"Free groceries and meals near you."*
>
> *[location input]*

Reduction: 48 words → 6 words + one input. (Scarcity design rule: cut to half the normal word count, then cut again.)

---

### Best Match card explanation

**Before:**
> *"Based on your location and preferences, our algorithm has identified Martha's Table Saturday Market as the closest verified food distribution event. This pantry serves eligible residents of the DC metropolitan area."*

**After:**
> *"Closest to you, happening tomorrow, no ID needed, Spanish spoken."*

Reduction: 38 words → 12 words. And the 12 words answer Maria's actual questions (proximity, timing, friction, language), while the 38 words answer none of them.

---

### Eligibility notes

**Before:**
> *"This distribution site requires proof of DC residency. Acceptable documentation includes: valid state-issued photo identification, a current utility bill, a lease agreement, or a recent piece of official mail addressed to the applicant. First-time visitors may be required to fill out additional paperwork."*

**After:**
> *"They ask to see a photo ID and something with your address — a bill or letter is fine. First visit takes about 10 extra minutes for a quick form."*

Reduction: 51 words → 32 words. More importantly: the word "applicant" is gone, "required" is gone, "acceptable documentation" is gone. The user is treated as a neighbor hearing from a friend, not an applicant hearing from a bureaucrat.

---

### Confidence — stale event

**Before:**
> *"⚠️ WARNING: This information has not been verified recently and may be outdated or inaccurate. Proceed with caution."*

**After:**
> *"We haven't confirmed this recently. Call first — (202) 555-0100."*

The "before" treats the user as a risk-management target. The "after" treats them as someone holding a phone who can call a number. The number is right there.

---

### Empty state — no results

**Before:**
> *"No matching results found. Please adjust your search criteria or try a different location."*

**After:**
> *"Nothing open in the next few hours right near you."*
>
> *"Three places to call:"*
>
> *[list of 3 orgs with phone numbers]*

Never leave the user at a dead end. Every empty state has a next step. This is bandwidth-tax-aware design — we do the "now what?" work for the user.

---

### Error state

**Before:**
> *"An unexpected error occurred. Please refresh the page or contact support."*

**After:**
> *"Something's off on our end. Try again in a minute."*
>
> *"Still stuck? Call 2-1-1 — a real person will help."*

Errors should not leave the user more helpless. Link out to the universal 211 human channel as the escape hatch. The research explicitly names 211 as the irreplaceable fallback.

---

### First-time visitor guidance

**Before:**
> *"As a first-time visitor, you will need to complete an intake form. Please arrive 15 minutes early."*

**After:**
> *"It's your first time? Show up a few minutes early — they'll sign you in at the front. It takes about 10 minutes."*

The second version removes "intake," removes "first-time visitor" (a gentle labeling), and uses "sign you in" (neighborly) instead of "complete an intake form" (clinical).

---

### Weather warning

**Before:**
> *"ALERT: Inclement weather may affect this event. Verify with the organization before attending."*

**After:**
> *"Rain tomorrow. This one's outdoors — worth a quick call first."*

---

### "Not this one?" soft rejection

**Before:**
> *"Feedback: Please rate your experience with this result on a scale of 1–5."*

**After:**
> *"Was this helpful? [👍 Yes] [👎 No]"*
>
> *(if 👎)* *"Thanks — we'll mark it down."*

One tap. No star rating. No text field. The feedback is anonymous, silent, instantly acknowledged. The research showed 96% of clients support feedback only when anonymous and visibly acted-upon.

---

## 5. Microcopy patterns (repeat-use strings)

These are strings that appear in many places. Lock them once here and never re-invent them in individual components.

### Time

- *"today"* / *"tomorrow"* / *"Saturday"* — day names, not dates, when within the week
- *"in 2 hours"* / *"in 30 minutes"* — relative when under 24 hours
- *"this Saturday"* — when that day is upcoming
- *"April 12"* — only when beyond a week
- **Never:** *"04/12/2026"*, *"at 10:00:00 AM EST"*

### Distance

- *"0.6 miles"* / *"12 min walk"* / *"22 min bus"* — with the mode implied
- *"18 min drive"* — only when distance > 3 miles or user preference says car
- **Never:** *"0.6 mi as the crow flies"*, *"1.2km"*, *"Euclidean distance"*

### Confidence

| Tier | String |
|---|---|
| verified | *"Confirmed 2 hours ago."* |
| likely | *"Last confirmed 5 days ago. Usually runs weekly."* |
| stale | *"We haven't confirmed this recently. Call first."* |
| unknown | *"We haven't been able to check this one. Call first."* |

### Loading

- *"Finding what's closest to you..."* (home → results)
- *"One moment..."* (generic, <1s expected)
- **Never:** *"Loading..."*, *"Please wait..."*, *"Fetching data..."*

### What to bring (rendered directly from `eligibility.plainSummary`)

Backend produces these. Ranked from most-dignity to most-friction:

1. *"Bring nothing. Just come."*
2. *"Bring a photo ID if you have one."*
3. *"Bring a photo ID and something with your address."*
4. *"Bring a photo ID, proof of address, and proof of income."*
5. *"Call ahead — they'll tell you what to bring."*

### What to expect (rendered from `accessibility.stigmaFreeSignals` + eligibility)

Example combinations the backend can produce:

- *"You'll wait about 15 minutes. Staff are welcoming. Walk in, sign your first name, get your box."*
- *"You can choose your own groceries. It feels like a small market."*
- *"Children are welcome. There's seating and a restroom."*
- *"They speak Spanish and Amharic at the door."*

---

## 6. Localization rules

### Baseline: English, Spanish, Amharic

- **EN** — authoritative; all new strings written in EN first.
- **ES** — shipped in v1. DMV Spanish-speaking population is huge. Review by a native speaker is a blocker for production; for the challenge demo we'll ship with a clear *"community review in progress"* disclaimer.
- **AM** (Amharic, `am`) — shipped in v1 because it's legally mandated by the DC Language Access Act and no other DMV food tool supports it. Same native-review disclaimer.

### Disclaimers for machine-assisted translations

When we ship a language we cannot guarantee as native-quality:

At the top of the language switcher:
> *"Español (en revisión por la comunidad)"* / *"አማርኛ (በማህበረሰብ እየተገመገመ)"*

In the settings / about page:
> *"We shipped Spanish and Amharic so users in those communities could see the app in their language. Our translations were reviewed by non-native speakers and may contain mistakes. If you find one, please tell us."*

**This disclaimer is non-negotiable.** Shipping broken Amharic without saying so is worse than shipping English only.

### Localization gotchas

- **Freshness strings must localize.** "2 hours ago" in Spanish is "hace 2 horas", not "2 horas ago". Use a real i18n library for relative times (Intl.RelativeTimeFormat native API).
- **Dates must localize.** April 12 in Spanish is *"12 de abril"*, not *"Abril 12"*. Use Intl.DateTimeFormat.
- **Numbers must localize.** Distance format differs. Use Intl.NumberFormat.
- **Right-to-left is not in scope for v1** (Amharic is left-to-right), but Arabic and Farsi would be. Flag as v2.
- **Never hardcode English concatenation.** `"You are " + n + " miles away"` is a localization bug factory. Use full templated strings per language.

### Banned word translations

The banned-word list in §2 applies in every language. *"Food insecure"* is just as stigmatizing in Spanish (*"inseguridad alimentaria"*) as in English. Translators must be told the tone goals, not just the strings.

---

## 7. Copy review checklist

Before any string ships, it must pass this checklist.

- [ ] Does it label the user? (If yes, rewrite.)
- [ ] Does it use a banned word from §2?
- [ ] Is it the shortest version that still answers the user's question?
- [ ] Would a friend say it this way?
- [ ] If stale, does it name the problem honestly?
- [ ] If empty, does it offer a next step?
- [ ] If error, does it point to 211 as fallback?
- [ ] Does it work in Spanish and Amharic without awkward concatenation?
- [ ] Does the research citation still hold?

---

## 8. Open questions flagged for a native speaker

These strings must be reviewed before PDF submission. Flag with `@translation-review` in code.

- All Spanish strings across the Maria flow
- All Amharic strings across the Maria flow
- The dignity disclaimer on the language switcher (native phrasing matters enormously here)
- The "was this helpful?" feedback button (short colloquial phrasings differ sharply by language)
- Empty state and error state strings (emotional tone is hardest to get right in translation)

---

**End of copy guide.** Every string in the app must justify itself against this document.
