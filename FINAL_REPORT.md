# Nutrire - Final Report

**NourishNet Data Challenge 2025**
**Team: Sankhasubhra Ghosal & Ashwath David**

---

## 1. The Problem We Saw

When we first looked at the food assistance landscape in the DC metro area, we thought it would be straightforward. There are food banks with websites, 211 hotlines with databases, county food councils with directories. The data exists. So why is it still so hard for a family to find groceries on a Tuesday evening?

We actually went through the process ourselves. We opened Capital Area Food Bank's locator, then 211 Maryland's search, then the Montgomery County Food Council map. Each one has a different layout, different search, different way of showing hours. Some just give you a name and phone number. Some say things like "Eligibility: Must reside in service area. Photo ID required" which honestly reads more like a barrier than an invitation.

The bigger issue is that none of these tools tell you what to actually expect when you show up. Walking into a food pantry for the first time can feel intimidating. You don't know where to go, what to bring, whether there's going to be a long form to fill out. No existing tool addresses that anxiety.

So we decided to build something different. Not just another aggregator, but a tool that thinks about access the way a person would. One that gives you a single best answer instead of a list of 50 results. One that tells you "Walk in through the side door, no line usually, bring your own bags" instead of "Services available to eligible residents."

We built it for three groups:

**Families looking for food** - They type their location and get their best option immediately. Not a list to scroll through. One answer, with directions, hours, and a first-visit guide. We don't ask for income or family size. The only inputs are where you are and what you need.

**Donors** - People who want to help but don't know which organizations near them actually accept food or money. We show them exactly who needs what, with direct links to donate.

**Volunteers** - Same idea. Filter by distance, language need, and availability. Find a shift that works for you.

---

## 2. What the App Looks Like

*(Include 3-4 screenshots from https://adx-coder.github.io/NUTRIRE/ here)*

**Home Page** - Clean landing with a location input. No forms, no sign-up. Type your ZIP or hit "Near me" and you're in. There are quick-action chips for common needs (groceries, hot meals, baby supplies). The whole thing is designed to feel warm, not institutional.

**Best Match** - This is the core of Nutrire. The app picks your single best option based on distance, whether it's open, how easy it is to access (walk-in vs appointment), and how reliable the data is. You see the org name, a one-line description written in plain language, transit directions, and a "What to expect" guide for first-time visitors. Below that, four backup alternatives in case the first one doesn't work out.

**Organization Detail** - Click into any org and you get the full picture. A map on the left, and on the right: hours broken down by day, food types they carry, eligibility in plain English, transit directions with bus/metro details, and live weather so you know if travel might be affected. We also made this work in three languages - English, Spanish, and Amharic. Switch the language in the top bar and everything translates, not just the UI but all the AI-generated descriptions for every single organization.

**Equity Map** - This is the research side. A full-screen map showing all 1,395 organizations as green pins, with orange hotspots over underserved ZIP codes. Click on a gap and you see the need vs supply breakdown and which nearby org could expand to serve that area. This is meant for policymakers and researchers thinking about where to open the next food pantry.

The app is fully responsive and works on mobile. We also added live weather from Open-Meteo, real-time open/closed detection from parsed hours, and actual geocoding when you type a ZIP code (using OpenStreetMap's Nominatim), so the results are based on your real location, not some hardcoded default.

---

## 3. How We Built the Backend

The backend is a Python pipeline with nine stages. Each stage reads from the previous one's output, so you can re-run any part without starting over. The whole thing takes messy web data from six different food directories and turns it into one clean JSON file that the frontend loads.

**Scraping** was the first challenge. We wrote custom scrapers for Capital Area Food Bank (which has an ArcGIS API behind their map), Maryland Food Bank (29 pages of paginated results), 211 Maryland and Virginia (Next.js server-rendered pages), and Montgomery County Food Council (WordPress plugin with structured fields). A couple of these sites have Cloudflare protection, so normal HTTP requests get blocked. We used browser automation with Playwright to handle that. We ended up with about 1,500 raw records, but they were messy - inconsistent formats, missing hours, vague descriptions.

**LLM enrichment** is where the raw data becomes actually useful. For each organization, we scraped their website (if they have one), then sent all that context to Mistral Small with a function-calling tool that extracts 15 fields in one API call. It generates a warm one-line description, a three-step first-visit guide, plain-English eligibility, cultural notes, and structured hours. The important guardrail: any hours the model returns have to actually appear in the source text. Early versions were making up schedules. We also run a banned-words filter on descriptions - no "food insecure", no "eligible recipients", nothing that sounds clinical or gatekeeping. The whole enrichment pass costs about $0.21 for 1,500 records, and everything is cached so re-runs are free.

**Deduplication** brought us from 1,500 to 1,395 unique orgs. The same church pantry might be listed on CAFB, 211 Maryland, and the MoCo Food Council. We used fuzzy name matching plus address and phone cross-referencing to find and merge these.

**Geocoding** got us to 100% coordinate coverage using a three-tier fallback: ArcGIS coordinates from CAFB, then Nominatim (OpenStreetMap's geocoder), then ZIP code centroids as a last resort.

**Transit** was one of the trickier parts. For each org, we find the nearest Metro station and bus stop using WMATA data (102 stations, 7,505 stops), then get actual walking distances along real roads using OpenStreetMap routing. To pick between Metro and bus, we use a cost model from transit research where Metro's higher frequency (3-min average wait vs 10-min for bus) makes it worth a longer walk.

**Translations** - we translated all the AI-generated content into Spanish and Amharic for all 1,395 organizations. These are the three priority languages in the DMV area, and the DC Language Access Act actually mandates language access for them.

**Equity gap analysis** is the research layer. Using Census poverty and SNAP data for 60+ ZIP codes, we computed where food need is highest relative to nearby supply. The output identifies 30 underserved areas and suggests which existing organization could expand to fill each gap.

---

## 4. Our Experience with Prompt Engineering

This is probably the part where we learned the most.

### Kiro Prompts

Our final Kiro prompt pack lives in `PROMPTS.md`, and we reworked it substantially after our first draft to make it independently reproducible for judges on a clean machine.

Our first attempt with Kiro was pretty basic. We described the app as "a food finder for the DC area with React" and got back a generic search page with a list of results. It worked, but it looked like every other food bank locator.

The turning point was when we started describing the experience we wanted instead of the technical structure. Instead of "Create a card component that displays organization data with name, address, phone, hours, and a map," we wrote something like "When someone opens the app, they should see their single best option, not a list. The app decides for them. Show the org name, a warm description that sounds like a neighbor talking, whether it's open right now, how to get there by bus or Metro, and a step-by-step guide for what to expect on a first visit."

That shift from describing components to describing user experiences made a big difference in what Kiro produced. A few specific things we figured out along the way:

Giving Kiro our exact TypeScript types up front meant the generated code actually worked with our real data instead of placeholder objects. We spent less time fixing type errors and more time on design.

Breaking the work into incremental prompts worked much better than trying to describe everything at once. In the final version we also added a Prompt 0 bootstrap step so the app's shipped data files are handled explicitly before any UI generation happens. That mattered because the product is only meaningful when the resource and equity data are actually present.

Describing the emotion we wanted ("this should feel welcoming, not institutional, more like a premium consumer app than a government portal") actually influenced the output. The color choices, spacing, and component style shifted when we included those descriptions.

We also found that being specific about what we did NOT want was as useful as saying what we did want. "No sign-up wall, no charity aesthetic, no stock photos of families" helped Kiro avoid the patterns we were trying to break from.

### Mistral Prompts (Data Enrichment)

For the backend enrichment, we designed a single function-calling tool called enrich_food_org that extracts 15 fields per organization. We tried chaining multiple smaller prompts initially but one structured extraction was cheaper and more consistent.

The hardest field to get right was heroCopy, the one-line description that appears on every card. We wanted it to sound like a neighbor telling you about a place, not a directory listing. Our prompt said "Write one sentence a friend would use to describe this place to someone who's never been." First versions were still stiff and marketing-like. Adding the banned-words list (no "assistance", no "eligibility", no "food insecure") and specifying the tone as "warm and neighborly" finally got us descriptions that felt right.

Hours were the trickiest extraction. The model would sometimes generate plausible-sounding schedules that weren't in the source data at all. Our fix was a post-processing check: any hours in the output have to appear as tokens in the original text. If they don't match, we drop them and fall back to "Call for hours." That tradeoff, showing less data rather than wrong data, was an important design decision for us.

---

## 5. What We Would Improve

If we had more time, there are a few things we would work on:

**Real-time source monitoring.** Right now the pipeline runs as a batch job. Ideally we would watch the source websites for changes and only re-scrape when something updates. The live weather already refreshes in real-time, but hours and services can go stale between pipeline runs.

**More languages.** We have English, Spanish, and Amharic. But the DMV also has significant French, Vietnamese, Korean, and Chinese-speaking communities. The i18n system is built to support them, we just need the translation work.

**SMS access.** Not everyone has a smartphone with a data plan. A text-based interface where you text your ZIP code and get back your best option would reach people who need it most.

**Community corrections.** Right now there is no way for a user to tell us "this pantry moved" or "these hours are wrong." A lightweight feedback mechanism per organization would help keep the data accurate over time.

**Better hours coverage.** Only about half the organizations have structured hours right now. The rest show "Call for hours" which is not ideal. With more scraping sources or a model trained to predict likely hours from org type and neighborhood patterns, we could improve this.

---

## 6. What We Changed from Kiro's Output

Kiro gave us a solid starting point for the React app structure, routing, and basic page layouts. We then built substantially beyond that:

The entire Python data pipeline was built outside Kiro. That includes all the scraping (6 custom scrapers), LLM enrichment with Mistral, deduplication, geocoding, transit routing with WMATA data, weather integration, equity gap analysis, the TLDAI accessibility index, and Spanish/Amharic translations for all 1,395 orgs.

The ranking algorithm was a major change. Kiro gave us distance sorting. We replaced it with a seven-factor scoring system that weighs proximity, open status, access friction (walk-in vs appointment), data reliability, language match, tone, and service match. The weights shift based on what the user is looking for.

The UI aesthetic evolved significantly. We moved to a glassmorphism design with layered glass effects, animated backgrounds, and a depth treatment on interactive elements that Kiro's initial output did not have.

We added live data signals: real-time weather from Open-Meteo API, actual geocoding of typed addresses via Nominatim, and open/closed status computed from parsed hours against the current time. Kiro's version used only static data.

The transit directions, equity gap engine, error boundary, accessibility improvements, and trilingual support were all built by us on top of Kiro's foundation.
