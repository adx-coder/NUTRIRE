import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";
import { TopNav } from "@/components/TopNav";
import { PageHeader } from "@/components/PageHeader";
import { useT } from "@/i18n/useT";

/**
 * Methodology — DESIGN.md §4.9. Long-form research documentation citing
 * research/foundation.md throughout. This page is for NSF-affiliated
 * researchers and hackathon judges, so academic language is fine.
 */
export default function Methodology() {
  const t = useT();
  return (
    <main className="min-h-screen relative overflow-hidden" style={{ background: GLASS_BG }}>
      <GlassBackdrop />

      <div className="relative z-10">
        <TopNav backTo="/" />

        <div className="mx-auto max-w-reading px-5 lg:px-10 pt-10 lg:pt-14 pb-24">
          <PageHeader
            eyebrow={t("method.eyebrow")}
            title={t("method.title")}
            subtitle={
              <>
                Nutrire is a household food-access tool and a research contribution to the
                NourishNet program. This page documents how the research view&rsquo;s data,
                scores, and recommendations are produced, cites the evidence base we built on,
                and states the limitations of the work honestly.
              </>
            }
          />

          <article className="mt-14 flex flex-col gap-12 text-base text-ink">
          <Section title="1. What Nutrire is">
            <p>
              Nutrire is a food-access web application for the DC / Maryland /
              Virginia area. It has one product and three audiences. For a
              household looking for a free meal or groceries this week, it is a
              recognition tool that answers a single question: &ldquo;where
              should I go, and when?&rdquo; Without forms, accounts, or a
              stigmatized self-label at the door. For a case worker, church
              volunteer, school nurse, or trusted neighbor helping others, it
              is a broker tool: shareable, printable, and batch-friendly. For
              researchers and program officers, it is this page and the Equity
              Gap map: an open, citable view of where the DMV&apos;s food
              distribution network fits the need, and where it does not.
            </p>
            <p>
              The three-surface architecture is deliberate and grounded in the
              stigma literature discussed below. The household surface cannot
              be research-shaped without reintroducing the labeling mechanism
              that keeps people from walking through the door
              (Link &amp; Phelan, 2001). The research surface cannot be
              household-shaped without losing the academic precision that
              makes it useful to funders and policy audiences. Keeping them
              separate is a design decision, not a lack of integration.
            </p>
          </Section>

          <Section title="2. The Equity Gap Index">
            <p>
              For each DMV census tract we compute three composite indicators.
              Need is an index of how intensely a tract is likely to need food
              assistance, drawn from ACS-derived poverty, car access, language
              isolation, rent burden, and an estimated SNAP participation gap.
              Supply is an index of how reachable the existing event footprint
              is from the tract, weighted by the eligibility friction of each
              event, its freshness, and whether it matches the tract&apos;s
              dominant non-English languages. The Equity Gap is the difference,
              normalized to a stable scale.
            </p>
            <pre className="overflow-x-auto rounded-md border border-white/30 bg-white/20 backdrop-blur-lg px-4 py-3 text-sm leading-relaxed text-ink">
{`Need   = 0.30 · poverty
       + 0.20 · noVehicle
       + 0.20 · languageIsolation
       + 0.15 · rentBurden
       + 0.15 · snapGap

Supply = Σ events_in_reach · eligibilityEase
                           · freshness
                           · languageMatch

EquityGap = Need − Supply        (normalized to −1 .. +1)`}
            </pre>
            <p>
              The index weights were chosen by triangulating three sources:
              the Capital Area Food Bank 2025 Hunger Report&apos;s own
              correlates of food insecurity, the scarcity-bandwidth literature
              in research/foundation.md §3 (which argues that transit and
              language friction are load-bearing because they consume
              cognitive bandwidth disproportionately), and the take-up
              paradox in §4 (which warns us not to over-weight stigma
              signals as if they were the only barrier). The backend team is
              producing real values for a production pipeline; the numbers
              rendered in the current research view are hand-crafted mocks
              built to exercise the UI and make the argument legible.
            </p>
          </Section>

          <Section title="3. Data sources">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-white/30 text-left">
                    <th className="py-2 pr-3 font-semibold text-ink">Source</th>
                    <th className="py-2 pr-3 font-semibold text-ink">Used for</th>
                    <th className="py-2 pr-3 font-semibold text-ink">License</th>
                  </tr>
                </thead>
                <tbody className="text-ink-soft">
                  <SourceRow
                    name="American Community Survey (ACS, 5-year)"
                    use="Tract demographics, income, car access, language isolation, rent burden"
                    license="Public domain"
                    url="https://www.census.gov/programs-surveys/acs"
                  />
                  <SourceRow
                    name="USDA Food Access Research Atlas"
                    use="LILA/LI food desert designations"
                    license="Public domain"
                    url="https://www.ers.usda.gov/data-products/food-access-research-atlas/"
                  />
                  <SourceRow
                    name="WMATA GTFS"
                    use="Transit reachability and walk-to-stop times"
                    license="Open (WMATA terms of use)"
                    url="https://developer.wmata.com/"
                  />
                  <SourceRow
                    name="NOAA / NWS forecasts"
                    use="Weather warnings for outdoor distributions"
                    license="Public domain"
                    url="https://www.weather.gov/documentation/services-web-api"
                  />
                  <SourceRow
                    name="OpenStreetMap"
                    use="Walkability surface, geocoding backfill"
                    license="ODbL 1.0"
                    url="https://www.openstreetmap.org/copyright"
                  />
                  <SourceRow
                    name="DC, Maryland, Virginia open data portals"
                    use="Tract boundaries, SNAP retailer lists, community resource directories"
                    license="Mixed, per portal"
                    url="https://opendata.dc.gov/"
                  />
                  <SourceRow
                    name="Capital Area Food Bank 2025 Hunger Report"
                    use="Regional food insecurity baselines and county-level rates"
                    license="Cited with attribution"
                    url="https://hunger-report.capitalareafoodbank.org/report-2025/"
                  />
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="4. The DMV reality (why this matters)">
            <p>
              The Capital Area Food Bank&apos;s 2025 Hunger Report, published
              with survey work by NORC at the University of Chicago, estimates
              that 1.5 million DMV residents are food insecure and that 36% of
              DMV households experienced food insecurity in 2025, nearly
              unchanged from 37% in 2024, meaning this is a stable structural
              condition and not a post-pandemic blip.
            </p>
            <p>
              County rates range from Prince George&apos;s County, MD at 49%
              (nearly one household in two) to Arlington County, VA at 22%. The
              District of Columbia sits in the high thirties to low forties,
              with substantial ward-level variation. The research view&apos;s
              choropleth is designed to make these differences visible at a
              glance and to make the intra-county variation inside DC and
              Prince George&apos;s equally visible.
            </p>
            <p>
              A new population has been added by federal employment shocks in
              2025: 41% of DMV households with a federal-employment job loss
              reported food insecurity in the survey, double the 17% rate
              among households without such a loss. More than two-thirds of
              food-insecure federal-affected households reported very low food
              security. The &ldquo;new hunger&rdquo; population is large,
              concentrated in specific commuter-shed tracts, and under-served
              by the existing pantry footprint that was built to a pre-2025
              geography.
            </p>
            <p className="text-sm text-ink-muted">
              Source: Capital Area Food Bank 2025 Hunger Report; see
              research/foundation.md §1 for the full citation set, including
              the Washington Post and CNN secondary coverage.
            </p>
          </Section>

          <Section title="5. Language access as equity">
            <p>
              The DC Language Access Act of 2004 legally mandates government
              services in five non-English languages: Spanish, Chinese,
              Vietnamese, Korean, and Amharic. The DMV is the largest
              Ethiopian diaspora community outside of Africa. One census tract
              adjacent to downtown Silver Spring is 29% Ethiopian. The
              Southern Towers apartment complex tract in Alexandria is 40%
              Ethiopian. Montgomery County has roughly 13,000 residents
              claiming Ethiopian ancestry, a figure that has tripled since
              2000.
            </p>
            <p>
              No existing DMV food-finder tool we surveyed supports Amharic.
              Shipping it in v1 of Nutrire is not a goodwill gesture; it is a
              response to a legal requirement, a concentrated speaker
              population, and a specific gap in the existing information
              infrastructure. The research view&apos;s &ldquo;Amharic
              speakers&rdquo; layer and the Silver Spring and Southern Towers
              recommendations in the Recommendations surface trace directly to
              the data points in this paragraph.
            </p>
            <p className="text-sm text-ink-muted">
              Source: research/foundation.md §2; Greater Greater Washington,
              &ldquo;DC&apos;s Little Ethiopia has moved to Silver Spring and
              Alexandria&rdquo;; Baltimore Banner coverage of Montgomery
              County Ethiopian population growth.
            </p>
          </Section>

          <Section title="6. Research grounding">
            <h3 className="mt-2 text-md font-semibold text-ink">
              Scarcity and bandwidth
            </h3>
            <p>
              Mani, Mullainathan, Shafir, and Zhao (2013), writing in Science,
              show that the cognitive effect of financial concerns on
              low-income individuals is equivalent to a 13-point dip in IQ or
              the loss of a full night of sleep. Their New Jersey mall
              experiment and their Tamil Nadu sugarcane farmer study each
              demonstrate that the same person performs measurably worse on
              fluid-intelligence tasks under scarcity than under relative
              plenty. Mullainathan and Shafir&apos;s book Scarcity (2013)
              formalizes this as a &ldquo;bandwidth tax&rdquo; that produces
              tunneling, reduced executive function, and diminished
              self-control. The design implication for a food-access tool is
              sharp: users arrive already taxed, so every additional decision,
              filter, dropdown, and form field is a load on a scarce resource.
              Nutrire&apos;s household surface is deliberately a recognition
              interface rather than a comparison interface.
            </p>

            <h3 className="mt-4 text-md font-semibold text-ink">Stigma</h3>
            <p>
              Link and Phelan&apos;s &ldquo;Conceptualizing Stigma&rdquo;
              (Annual Review of Sociology, 2001) defines stigma as the
              co-occurrence of labeling, stereotyping, separation, status loss,
              and discrimination, exercised through institutional power.
              Garthwaite&apos;s Hunger Pains (Policy Press, 2016), an
              eighteen-month ethnography inside a Trussell Trust foodbank in
              the UK, finds that shame and stigma are the primary emotional
              experience of first-time foodbank users, often stronger than
              hunger itself. Martin&apos;s Reinventing Food Banks and Pantries
              (Island Press, 2021) argues that destigmatization is a design
              responsibility of the host organization, not a character trait
              to be asked of the client. These findings drive the
              banned-words list in COPY.md, the no-self-label home screen,
              and the commitment to anonymous feedback.
            </p>

            <h3 className="mt-4 text-md font-semibold text-ink">
              The take-up paradox
            </h3>
            <p>
              Bhargava and Manoli&apos;s experimental work on tax-credit
              take-up and Janet Currie&apos;s review of SNAP enrollment
              evidence converge on an uncomfortable finding: attempts to lower
              stigma through warmer framing often do not move take-up rates,
              while reductions in transaction costs (fewer forms, shorter
              waits, prefilled applications) do. This is counterintuitive and
              important. It does not mean stigma does not exist; Garthwaite
              and the SNAP-stigma literature show it plainly does. It means
              the design lever with the largest measured effect is usually
              simplicity, not warmth. Nutrire respects this ordering:
              ruthless transaction-cost reduction first, dignity copy second.
              Every screen on the household side has to justify its existence
              as load-bearing.
            </p>
          </Section>

          <Section title="7. Honest limitations">
            <ol className="flex list-decimal flex-col gap-3 pl-5 text-ink-soft marker:text-ink-muted">
              <li>
                We have not spoken to a single food-insecure DMV resident.
                Every design implication is extrapolated from secondary
                research. The most rigorous version of this project would
                include intercept interviews and pantry-operator shadowing; a
                follow-on research plan is included in the PDF report.
              </li>
              <li>
                The stigma literature is contested. Bhargava &amp; Manoli and
                Currie show that transaction costs beat stigma as an empirical
                barrier, yet Garthwaite, Hill &amp; Guittar, and the PMC
                SNAP-stigma paper show stigma has a massive effect. Both can
                be true (different measurement scales, different populations,
                different outcomes) but we do not overclaim.
              </li>
              <li>
                We do not know if digital privacy actually reduces perceived
                stigma. The one study that checked (PMC11846313) found no
                association between stigma and online SNAP use. Our assumption
                that anonymous browsing alleviates shame is a reasonable
                hypothesis, not an empirical finding.
              </li>
              <li>
                Broker research is thin for food access specifically. Most
                navigator evidence comes from health-care settings and
                enrollment work (SNAP, WIC, Medicaid), not from pantry
                finding. We are extrapolating across domains.
              </li>
              <li>
                We are designing for a population whose language of use we do
                not share. Even with an i18n pass, quality Spanish and
                Amharic localization requires native speakers, ideally
                speakers from the specific DMV immigrant communities, and we
                do not have them on the team. We flag this explicitly in the
                UI and treat any shipped translation as a beta.
              </li>
              <li>
                The Capital Area Food Bank Hunger Report is survey-based.
                It is good data, but it is the best available rather than
                ground truth. Response biases apply.
              </li>
              <li>
                DMV-specific journalism on first-person client experience is
                surprisingly thin. We pulled the Hunger Report&apos;s own
                quotes, which are the strongest sources we have, but a more
                thorough build would include dedicated Washington Post and
                DCist archive searches for named individual profiles.
              </li>
            </ol>
          </Section>

          <Section title="8. Future work">
            <ul className="flex list-disc flex-col gap-2 pl-5 text-ink-soft marker:text-ink-muted">
              <li>
                Native-speaker translation review for Spanish and Amharic,
                ideally led by community members from Langley Park, Silver
                Spring, and Southern Towers.
              </li>
              <li>
                Broker shadowing research with case workers at Capital Area
                Food Bank partner sites and school nurses in Prince
                George&apos;s County public schools.
              </li>
              <li>
                Real-time freshness signals via lightweight SMS check-ins
                from pantry operators on the morning of each distribution,
                feeding directly into the confidence tier.
              </li>
              <li>
                Integration with DC 311 and 211 Maryland so that navigator
                referrals to Nutrire are counted and tracked without
                compromising client anonymity.
              </li>
              <li>
                Expansion to the Baltimore metro area, which shares regional
                food bank infrastructure with the DMV but has a meaningfully
                different transit and demographic profile.
              </li>
              <li>
                A printable one-page handoff format optimized for broker
                workflows and for clients who share a phone or do not have
                reliable data access.
              </li>
              <li>
                Formal evaluation against a held-out &ldquo;was the user able
                to reach the recommended event&rdquo; outcome, in partnership
                with a navigator program.
              </li>
            </ul>
          </Section>

          <Section title="9. Team and acknowledgments">
            <p>
              Nutrire is a student research contribution to the NourishNet
              program, funded by the National Science Foundation and
              coordinated through the University of Maryland. We are grateful
              to the Capital Area Food Bank for publishing the 2025 Hunger
              Report with the level of specificity that made a county- and
              ward-level research view possible, to the broader open-source
              community whose tools (React, Leaflet, Tailwind, OpenStreetMap,
              Lucide, and many others) carry most of the engineering load,
              and to the researchers whose work on scarcity, stigma, and
              take-up we cite throughout. Any errors in interpretation are
              ours.
            </p>
          </Section>
        </article>

          <div className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-white/30 pt-8 text-sm">
            <Link
              to="/map"
              className="font-medium text-sage-deep hover:underline"
            >
              ← Back to the Equity Gap map
            </Link>
            <Link
              to="/recommendations"
              className="font-medium text-sage-deep hover:underline"
            >
              View recommendations →
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <h2 className="font-display text-xl font-semibold text-ink tracking-tight">{title}</h2>
      <div className="mt-4 flex flex-col gap-4 leading-relaxed text-ink-soft">
        {children}
      </div>
    </motion.section>
  );
}

function SourceRow({
  name,
  use,
  license,
  url,
}: {
  name: string;
  use: string;
  license: string;
  url: string;
}) {
  return (
    <tr className="border-b border-white/30 align-top">
      <td className="py-3 pr-3">
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-sage-deep underline-offset-4 hover:underline"
        >
          {name}
        </a>
      </td>
      <td className="py-3 pr-3">{use}</td>
      <td className="py-3 pr-3 text-ink-muted">{license}</td>
    </tr>
  );
}
