# NourishNet Data Challenge

This challenge is organized by a University of Maryland-led team receiving NSF funding to develop NourishNet. The NourishNet team is building tools, such as FoodLoops, to recover and redistribute surplus food, helps reduce food waste through community/campus partnerships, and develops tech (like Quantum Nose – a food spoilage detection sensor) to ensure recovered food is fresh.

## Challenge Background

Food distribution events are a vital mechanism for connecting essential resources to individuals and families experiencing food insecurity. Yet, these events are typically organized by a wide range of groups, such as nonprofits, community organizations, faith-based groups, and local agencies, each operating with its own communication practices and outreach strategies. This fragmentation creates several challenges that highlight a critical need for AI-driven tools and approaches that can unify information, improve coordination, and ensure that food distribution efforts reach the households that need them most:

- **Inconsistent communication channels:** Information about upcoming distribution events is spread across social media posts, flyers, websites, and word-of-mouth, making it difficult to obtain a unified, reliable picture of available resources.
- **Limited guidance for donors:** Individuals and organizations that want to donate food or funds often lack clarity on which distribution groups are active in their area, what their needs are, and how to reach them effectively.
- **Lack of visibility for volunteers:** Potential volunteers may not know which organizations are nearest to them or where their support is most urgently needed.
- **Information for food-insecure households:** For those who need assistance the most, finding accurate and timely information about events (location, schedule, eligibility, and transportation options) can be difficult.
- **Misalignment between event locations and community needs:** Without coordinated planning, events may not be hosted in areas with the highest levels of food insecurity, or they may be inaccessible to the families they are meant to serve because of barriers related to transportation, timing or other logistics.

## Challenge Overview

Your mission is to ensure that families in Maryland, metropolitan Washington, DC, and the surrounding area who need food resources the most are able to easily locate, access, and benefit from them. And that those who would want to help as donors or volunteers can find avenues to provide support. Participants will start with a dataset of urls to a variety of online information sources. The challenge is twofold:

1. Can you take that unstructured data and build a system capable of ingesting and processing data in real time as websites are updated?
2. Can you create a UI/UX that provides easy access to relevant information for key stakeholder groups including households, donors and volunteers?

## Task

In this data challenge, you will design and build a use-inspired tool that transforms fragmented, unstructured data from community websites into a one-stop source of information for households, donors, and volunteers alike.

Using **Kiro**, an agentic coding environment from AWS, you will vibe code to craft a series of prompts that Kiro can use to develop a web-app using a **React framework**. Your solution must be built **exclusively using open source tools and libraries**. **No additional AWS services beyond Kiro may be used.**

This tool should be able to do at least one of the following:

- Connect families to nearby food distribution events, providing clear, timely details such as event location, hours, requirements, and types of food.
- Connect donors to organizations that match their preferences and requirements for donating food or money.
- Connect volunteers to organizations that match their preferences and requirements for donating their time.

You will develop a React package and deploy it on **GitHub Pages**. Judges will interact with the live tool directly, evaluating it on the basis of real use: how well it works, how easy it is to navigate, and how effectively it connects users to the information they need.

## Data Provided

- A CSV file with over a dozen websites offering options for food bank events in metropolitan Washington, DC and surrounding areas, along with other websites related to food security
- Students can use any additional public data source they like, such as census data, poverty indicators, transportation networks, and other socioeconomic and/or geospatial datasets, to improve the accuracy and usefulness of recommendations.

## Deliverables

You will submit the three deliverables below as a **public GitHub repository** organized and documented for reproducibility.

1. **Final React Package:** The final code ready to be executed and hosted by the data challenge organizers for tool evaluation. Teams can improve upon the code provided by Kiro based on their Prompt Markdown if desired.
2. **README:** A `README.md` with complete setup and build instructions, enabling judges and other reviewers to run your tool independently.
3. **PDF Report:** A structured report documenting your tool and the thinking behind it. Your report should:
   - Describe your intended users and how the tool supports them in finding and engaging with food assistance programs and events.
   - Explain how your tool's user interface works, including its core features and flow.
   - Explain the tool's backend data ingestion process and architecture, including the schema/data model (if applicable).
   - If applicable, describe any additional data sources you provided to Kiro.
   - Explain your experience implementing the tool through prompt engineering.
   - Discuss how the tool could be improved in future iterations.
   - If you made substantial improvements to the code produced by Kiro for your final React package, please describe those changes.

## Deadline

**Monday, April 13, 2026** at:
- 2 PM Pacific
- 3 PM Mountain
- 4 PM Central
- 5 PM Eastern

Do not make any updates to the repository after the deadline. **Updates to the repository past the deadline will result in disqualification.**

## Evaluation Criteria

### Usability, Design & Innovation (50%)

This is the heart of the challenge. Judges must be able to execute your React package to evaluate this. They will assess whether your tool genuinely serves the people it is designed for. Key questions include:

- Does your solution meaningfully address the real-world needs of families seeking food assistance, potential donors, and volunteers?
- Is the interface intuitive and accessible, particularly for users who may have limited technical literacy or are non-English speakers?

### Prompt Engineering (30%)

Your prompt markdown file must speak for itself. Judges will run your prompts in Kiro independently and evaluate whether they consistently produce a tool similar to what you describe in your report. If you made substantial changes to the code produced by Kiro for your final application, please describe those improvements in your report.

### Report Communication (20%)

Your PDF report should reflect the clarity of your thinking and authentic experience during the data challenge in your original writing. **Please do not use AI to produce your report.** Judges will look for a report that is well organized and easy to follow, communicates your design decisions and their rationale, and explains your experience implementing the tool through prompt engineering.

---

## Key Constraints (Summary)

- **Must use Kiro** (AWS agentic coding environment) for development via prompts
- **React framework** required
- **Open source only** — no non-Kiro AWS services
- **Deploy to GitHub Pages**
- **Public GitHub repo** with README + PDF report + final code
- **Report must be human-written** (no AI)
- **Freeze repo** at deadline
