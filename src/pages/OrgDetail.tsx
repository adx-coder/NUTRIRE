import { useMemo, useState, type ReactNode } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Share2, Phone, Check, X, AlertTriangle, Clock, Bus, Train, ArrowRight, CloudRain } from "lucide-react";
import { useT } from "@/i18n/useT";
import { useLocalizedAI } from "@/i18n/useLocalizedAI";
import { motion } from "framer-motion";
import clsx from "clsx";
import MapGL, { Marker as GLMarker, Source, Layer } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { EnrichedOrganization, RankedOrg } from "@/types";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { rankOrgs } from "@/lib/rank-orgs";
import { reliabilityTone } from "@/lib/freshness";
import { haversineMeters, walkMinutes, driveMinutes } from "@/lib/geo";
import { computeOpenStatus } from "@/lib/open-status";
import { useLocationStore } from "@/store/location";
import { navigateBackOr } from "@/lib/navigation";
import { useStatusLabel } from "@/lib/use-status-label";
import { useWeather } from "@/lib/use-weather";

const ease = [0.22, 1, 0.36, 1] as const;
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

export default function OrgDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const t = useT();
  const storedLocation = useLocationStore((s) => s.location);
  const language = useLocationStore((s) => s.language);
  const userLocation = storedLocation?.coords ?? mockUserLocation;

  const orgs = useOrgs();
  const allRanked = useMemo(() => rankOrgs(orgs, { userLocation, now: new Date(), mode: "closest", languages: [language], maxResults: 50 }), [userLocation, language, orgs]);

  const rankedMatch = allRanked.find((r) => r.org.id === id) ?? null;
  const foundOrg = rankedMatch?.org ?? orgs.find((o) => o.id === id) ?? null;
  const backups = allRanked.filter((r) => r.org.id !== id).slice(0, 4);

  // Build heroResult — use ranked if available, otherwise synthesize from org data
  const heroResult = useMemo<RankedOrg | null>(() => {
    if (rankedMatch) return rankedMatch;
    if (!foundOrg) return null;
    const meters = haversineMeters(userLocation, { lat: foundOrg.lat, lng: foundOrg.lon });
    const safeMeters = isNaN(meters) ? 0 : meters;
    return {
      org: foundOrg,
      distanceMeters: safeMeters,
      walkMinutes: walkMinutes(safeMeters),
      transitMinutes: null,
      driveMinutes: driveMinutes(safeMeters),
      openStatus: computeOpenStatus(foundOrg, new Date()),
      why: "",
      score: 0,
    };
  }, [rankedMatch, foundOrg, userLocation]);

  const org = heroResult?.org ?? null;

  // Hooks must be called unconditionally — before any early return
  const ai = useLocalizedAI(org?.ai ?? { heroCopy: "", plainEligibility: "", firstVisitGuide: [], culturalNotes: null, toneScore: 0, qualityScore: 0, generatedAt: "", model: "" } as any);

  const [shareOpen, setShareOpen] = useState(false);
  const [feedback, setFeedback] = useState<null | "thanks">(null);

  const heroStatusLabel = useStatusLabel(heroResult?.openStatus ?? { state: "unknown", label: "" });
  const weather = useWeather(org?.lat, org?.lon);

  const navigateBack = () => {
    navigateBackOr(navigate, "/find");
  };

  if (!org || !heroResult) return <NotFound onBack={navigateBack} />;

  const tone = reliabilityTone(org.reliability);
  const miles = (heroResult.distanceMeters / 1609.344).toFixed(1);

  const openDirections = () => window.open(`https://www.google.com/maps/dir/?api=1&destination=${org.lat},${org.lon}`, "_blank", "noopener,noreferrer");
  const callOrg = () => { if (org.phone) window.location.href = `tel:${org.phone.replace(/[^0-9+]/g, "")}`; };

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: "#EDE8E0" }}>
      {/* Backdrop */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 50% at 10% 25%, rgba(79,140,110,0.28) 0%, transparent 55%),
          radial-gradient(ellipse 50% 45% at 85% 15%, rgba(175,155,210,0.2) 0%, transparent 50%),
          radial-gradient(ellipse 45% 40% at 70% 85%, rgba(225,175,80,0.16) 0%, transparent 50%),
          radial-gradient(ellipse 40% 35% at 95% 50%, rgba(140,120,190,0.12) 0%, transparent 45%)
        `,
      }} />
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none opacity-[0.035]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
        backgroundSize: "200px",
      }} />

      <div className="relative z-10">
        {/* Nav */}
        <motion.nav initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
          className="px-3 sm:px-4 lg:px-6 pt-3 sm:pt-4 flex items-center justify-between">
          <button onClick={navigateBack} className="h-9 px-3 rounded-lg text-[12px] font-medium text-ink-muted hover:text-ink hover:bg-white/40 transition-colors inline-flex items-center gap-1.5">
            <ArrowLeft size={14} /> {t("nav.back")}
          </button>
          <div className="flex items-center gap-2">
            <button onClick={() => setShareOpen(true)} className="h-9 px-3 rounded-lg bg-white/30 backdrop-blur-xl border border-white/40 text-[12px] font-medium text-ink-soft hover:text-ink transition-colors inline-flex items-center gap-1.5">
              <Share2 size={13} /> {t("org.send")}
            </button>
          </div>
        </motion.nav>

        {/* ── BENTO: Map left, info stacked right — same DNA as BestMatch ── */}
        <div className="px-2 sm:px-3 lg:px-5 pt-2 pb-4 md:min-h-[calc(100dvh-56px)] grid grid-cols-1 md:grid-cols-[1fr_1fr] lg:grid-cols-[1.1fr_0.9fr] md:grid-rows-[auto_auto_1fr] gap-2">

          {/* ── MAP CARD (left, spans all rows) ── */}
          <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.1, ease }}
            className="md:order-1 md:row-span-3 rounded-2xl overflow-hidden bg-white/20 backdrop-blur-2xl border border-white/30 shadow-[0_4px_16px_rgba(0,0,0,0.05)] flex flex-col">
            <div className="flex-1 min-h-[200px] sm:min-h-[250px] md:min-h-0">
              <MapGL initialViewState={{ longitude: org.lon, latitude: org.lat, zoom: 14.5, pitch: 30 }}
                style={{ width: "100%", height: "100%" }} mapStyle={MAP_STYLE} attributionControl={false}>
                <GLMarker longitude={org.lon} latitude={org.lat} anchor="bottom">
                  <div className="relative flex flex-col items-center">
                    <div className="absolute -top-1 w-8 h-8 rounded-full bg-sage/20 blur-md animate-pulse" />
                    <svg width="28" height="38" viewBox="0 0 32 42" className="drop-shadow-[0_3px_8px_rgba(58,101,81,0.35)]">
                      <path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 26 16 26s16-14 16-26C32 7.2 24.8 0 16 0z" fill="#3A6551" />
                      <circle cx="16" cy="15" r="6" fill="white" />
                    </svg>
                  </div>
                </GLMarker>
                {userLocation && (
                  <>
                    <GLMarker longitude={userLocation.lng} latitude={userLocation.lat} anchor="center">
                      <div className="w-3 h-3 rounded-full bg-sage border-2 border-white shadow-[0_0_8px_rgba(79,127,106,0.5)]" />
                    </GLMarker>
                    <Source type="geojson" data={{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[userLocation.lng, userLocation.lat], [org.lon, org.lat]] } }}>
                      <Layer type="line" paint={{ "line-color": "#4F7F6A", "line-width": 2, "line-dasharray": [2, 1.5], "line-opacity": 0.4 }} />
                    </Source>
                  </>
                )}
              </MapGL>
            </div>
            {/* Actions at bottom of map card */}
            <div className="px-3 sm:px-4 py-3 flex items-center gap-2 border-t border-white/20">
              {tone.urgentCall ? (
                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} onClick={callOrg}
                  className="flex-1 h-[38px] rounded-xl bg-terracotta text-white font-semibold text-[13px] flex items-center justify-center gap-2">
                  <Phone size={14} /> {t("match.callFirst")}
                </motion.button>
              ) : (
                <motion.button whileHover={{ scale: 1.02, y: -1 }} whileTap={{ scale: 0.97 }} onClick={openDirections}
                  className="flex-1 h-[38px] rounded-xl bg-sage-deep text-white font-semibold text-[13px] flex items-center justify-center gap-2 shadow-[0_4px_12px_-4px_rgba(58,101,81,0.4)]">
                  {t("match.getDirections")} <ArrowRight size={14} strokeWidth={2.5} />
                </motion.button>
              )}
              <button onClick={() => setShareOpen(true)} aria-label="Share" className="h-[38px] w-[38px] rounded-xl bg-white/30 border border-white/40 text-ink-muted flex items-center justify-center hover:bg-white/50 transition-colors shrink-0">
                <Share2 size={14} />
              </button>
              {org.phone && !tone.urgentCall && (
                <a href={`tel:${org.phone?.replace(/[^0-9+]/g, "")}`} className="h-[38px] w-[38px] rounded-xl bg-white/30 border border-white/40 text-ink-muted flex items-center justify-center hover:bg-white/50 transition-colors shrink-0">
                  <Phone size={14} />
                </a>
              )}
            </div>
          </motion.div>

          {/* ── IDENTITY CARD (top-right) ── */}
          <GlassCard delay={0.15} className="md:order-2">
            <div className="flex items-center gap-2 mb-1">
              <StatusDot state={heroResult.openStatus.state} />
              <span className="text-[12px] text-ink-soft font-medium line-clamp-1">{heroStatusLabel}</span>
              <span className="text-ink/10">·</span>
              <span className="text-[12px] text-ink-muted tabular-nums">{miles} mi</span>
            </div>
            <h1 className="font-display text-[clamp(24px,4.5vw,38px)] font-bold text-ink leading-[0.95] tracking-[-0.025em]">{org.name}</h1>
            <p className="mt-1 text-[11px] text-ink-muted">{org.neighborhood || org.city || "DMV"}{org.state ? `, ${org.state}` : ""}</p>
            {ai.heroCopy?.trim() && (
              <p className="mt-2.5 text-[13px] text-ink/70 leading-[1.5] text-pretty">{ai.heroCopy}</p>
            )}
            {weather && (
              <div className={clsx(
                "mt-2 flex items-center gap-2 px-2.5 py-1.5 rounded-lg border",
                weather.isAdverse ? "bg-mustard/10 border-mustard/15" : "bg-sage/5 border-sage/10"
              )}>
                {weather.isAdverse ? <CloudRain size={12} className="text-mustard shrink-0" /> : <span className="text-[12px] shrink-0">☀️</span>}
                <p className="text-[11px] text-ink/70 leading-snug">
                  {weather.temp}°F · {weather.label}
                  {weather.isAdverse && ` · ${t("weather.travelAffected")}`}
                </p>
              </div>
            )}
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-ink-muted">
              <span className="h-[4px] w-[4px] rounded-full" style={{ backgroundColor: tone.dotColor }} />
              {tone.label}
              {org.sourceName && <><span>·</span><span>{org.sourceName}</span></>}
              {(org.crossSourceCount ?? 1) > 1 && <><span>·</span><span>{org.crossSourceCount} sources</span></>}
            </div>
          </GlassCard>

          {/* ── DETAILS CARD (mid-right) — expect + eligibility + hours ── */}
          <GlassCard delay={0.25} className="md:order-3">
            {/* What to expect */}
            {ai.firstVisitGuide && ai.firstVisitGuide.length > 0 && (
              <div className="mb-3">
                <CardLabel>{t("match.whatToExpect")}</CardLabel>
                <ul className="mt-2 space-y-2">
                  {ai.firstVisitGuide.map((b, i) => (
                    <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: 0.35 + i * 0.08, ease }}
                      className="flex items-start gap-2">
                      <div className="mt-[3px] h-3.5 w-3.5 rounded-full bg-sage/10 border border-sage/15 flex items-center justify-center shrink-0">
                        <Check size={7} className="text-sage-deep" strokeWidth={3} />
                      </div>
                      <span className="text-[12px] text-ink/65 leading-snug">{b}</span>
                    </motion.li>
                  ))}
                </ul>
              </div>
            )}

            {/* Eligibility */}
            <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.5, ease }}
              whileHover={{ scale: 1.005 }}
              className="rounded-xl bg-white/30 border border-white/40 px-3 py-2.5 mb-3">
              <p className="text-[13px] text-ink font-medium leading-snug">{ai.plainEligibility}</p>
              {ai.culturalNotes && <p className="mt-1.5 text-[10px] text-ink-muted italic">{ai.culturalNotes}</p>}
            </motion.div>

            {/* Food types */}
            {org.foodTypes && org.foodTypes.length > 0 && (
              <div className="mb-3">
                <CardLabel>{t("org.whatsAvailable")}</CardLabel>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {org.foodTypes.map((ft) => (
                    <span key={ft} className="px-2.5 py-1 rounded-lg bg-white/35 border border-white/40 text-[10px] font-medium text-ink/60">
                      {ft.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Hours — only show if there's structured data beyond what the status dot already says */}
            {(org.ai?.parsedHours && Object.keys(org.ai.parsedHours).some(k => k !== "raw" && k !== "byAppointment")) && (
              <div className="mb-3">
                <CardLabel>{t("org.hours")}</CardLabel>
                <div className="mt-1.5"><FormattedHours org={org} /></div>
                {org.ai.reconciliationWarnings?.length ? (
                  <div className="mt-1.5 flex items-start gap-1.5 text-[10px] text-terracotta">
                    <AlertTriangle size={10} className="shrink-0 mt-0.5" /><span>{org.ai.reconciliationWarnings[0]}</span>
                  </div>
                ) : null}
              </div>
            )}

            {/* Getting there — transit directions */}
            {org.transit?.transitSummary && (
              <div className="mt-3">
                <CardLabel>{t("org.gettingThere")}</CardLabel>
                <div className="mt-1.5 flex items-start gap-2 px-2.5 py-2 rounded-xl bg-white/30 border border-white/40">
                  {org.transit.nearestMetro ? <Train size={13} className="text-sage-deep shrink-0 mt-0.5" /> : <Bus size={13} className="text-sage-deep shrink-0 mt-0.5" />}
                  <div>
                    <p className="text-[12px] text-ink/70 leading-snug">{org.transit.transitSummary}</p>
                    {org.transit.transitDirections?.naturalDirections && (
                      <p className="mt-1 text-[10px] text-ink/45 leading-snug">{org.transit.transitDirections.naturalDirections}</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </GlassCard>

          {/* ── ALTERNATIVES CARD (bottom-right) ── */}
          <GlassCard delay={0.35} className="md:order-4">
            <div className="flex items-center justify-between mb-2">
              <CardLabel>{t("org.ifThatDoesntWork")}</CardLabel>
              <button onClick={() => navigate("/all")} className="text-[10px] font-medium text-ink-muted hover:text-ink-soft inline-flex items-center gap-0.5">
                All {allRanked.length} <ArrowRight size={9} />
              </button>
            </div>
            <div className="space-y-0.5">
              {backups.map((b, i) => (
                <motion.button key={b.org.id} onClick={() => navigate(`/org/${b.org.id}`)}
                  initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: 0.45 + i * 0.05, ease }}
                  whileHover={{ x: 3 }}
                  className="w-full flex items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-ink/4 transition-colors group">
                  <StatusDot state={b.openStatus.state} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-ink-soft font-medium truncate group-hover:text-ink transition-colors">{b.org.name}</p>
                    <p className="text-[9px] text-ink-muted truncate">{b.openStatus.label}</p>
                  </div>
                  <span className="text-[10px] text-ink-muted tabular-nums shrink-0">
                    {b.walkMinutes <= 25 ? `${b.walkMinutes}m walk` : `${(b.distanceMeters / 1609.344).toFixed(1)} mi`}
                  </span>
                </motion.button>
              ))}
            </div>

            {/* Feedback */}
            <div className="mt-3 pt-2 border-t border-ink/5">
              {feedback === "thanks" ? <p className="text-[10px] text-ink-muted">Noted.</p> : (
                <div className="flex items-center gap-2">
                  <p className="text-[10px] text-ink-muted">Accurate?</p>
                  <button onClick={() => setFeedback("thanks")} aria-label="Yes" className="h-6 w-6 rounded-full bg-white/40 border border-white/50 hover:bg-white/60 inline-flex items-center justify-center"><Check size={11} className="text-ink" /></button>
                  <button onClick={() => setFeedback("thanks")} aria-label="No" className="h-6 w-6 rounded-full bg-white/40 border border-white/50 hover:bg-white/60 inline-flex items-center justify-center"><X size={11} className="text-ink" /></button>
                </div>
              )}
            </div>
          </GlassCard>
        </div>
      </div>

      {shareOpen && <ShareSheet org={org} ranked={heroResult} onClose={() => setShareOpen(false)} />}
    </main>
  );
}

// ── Shared ──

function GlassCard({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.5, delay, ease }}
      whileHover={{ scale: 1.005, transition: { duration: 0.2 } }}
      className={clsx("rounded-2xl p-3 sm:p-4 bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_4px_16px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,0.5)]", className)}>
      {children}
    </motion.div>
  );
}

function CardLabel({ children }: { children: ReactNode }) {
  return <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-ink-muted">{children}</p>;
}

function StatusDot({ state }: { state: string }) {
  if (state === "open") return (<span className="relative flex h-2 w-2"><span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" /><span className="relative h-2 w-2 rounded-full bg-sage" /></span>);
  if (state === "opens_today") return <Clock size={11} className="text-ink-soft" />;
  return <span className="h-2 w-2 rounded-full bg-ink-muted" />;
}

const DAYS = ["mon","tue","wed","thu","fri","sat","sun"] as const;
const DL: Record<string,string> = { mon:"Mon", tue:"Tue", wed:"Wed", thu:"Thu", fri:"Fri", sat:"Sat", sun:"Sun" };
function FormattedHours({ org }: { org: EnrichedOrganization }) {
  const t = useT();
  const p = org.ai?.parsedHours;
  if (!p) return <p className="text-[12px] text-ink line-clamp-3">{org.hoursRaw || t("org.callForHours")}</p>;
  const days = DAYS.filter((d) => p[d] && p[d]!.length > 0);
  if (!days.length) return <p className="text-[12px] text-ink">{p.byAppointment ? t("org.byAppointment") : org.hoursRaw || t("org.callForHours")}</p>;
  return (<div className="space-y-0.5">{days.map((d) => (<div key={d} className="flex items-baseline gap-2 text-[11px]"><span className="w-7 text-ink-muted font-medium shrink-0">{DL[d]}</span><span className="text-ink">{p[d]!.map((s, i) => <span key={i}>{i > 0 && ", "}{s.start}–{s.end}</span>)}</span></div>))}</div>);
}


function NotFound({ onBack }: { onBack: () => void }) {
  return (<main className="min-h-screen flex items-center justify-center px-6" style={{ background: "#EDE8E0" }}><div className="text-center"><h1 className="text-lg font-semibold text-ink">Not found.</h1><p className="mt-2 text-sm text-ink-soft">Try another or call 2-1-1.</p><button onClick={onBack} className="mt-4 text-sm text-sage-deep font-medium inline-flex items-center gap-1"><ArrowLeft size={14} /> Back</button></div></main>);
}

function ShareSheet({ org, ranked, onClose }: { org: EnrichedOrganization; ranked: RankedOrg; onClose: () => void }) {
  const localAi = ranked.org.ai.translations?.[useLocationStore.getState().language];
  const elig = localAi?.plainEligibility ?? ranked.org.ai.plainEligibility;
  const msg = [org.name, `${org.address}, ${org.city}, ${org.state}`, ranked.openStatus.label, elig, org.phone ? `Call: ${org.phone}` : null, "via Nutrire (NourishNet)"].filter(Boolean).join("\n");
  const enc = encodeURIComponent(msg);
  const copy = async () => { try { await navigator.clipboard.writeText(msg); } catch {} onClose(); };
  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/25 backdrop-blur-sm" onClick={onClose}>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease }}
        className="w-full max-w-[400px] bg-white/80 backdrop-blur-2xl rounded-t-3xl md:rounded-3xl p-5 border border-white/50" onClick={(e) => e.stopPropagation()}>
        <div className="w-10 h-1 rounded-full bg-ink/10 mx-auto mb-4 md:hidden" />
        <h2 className="text-base font-semibold text-ink">Send this to them</h2>
        <pre className="mt-3 p-3 rounded-xl bg-white/50 text-[11px] text-ink whitespace-pre-wrap font-sans leading-relaxed">{msg}</pre>
        <div className="mt-4 space-y-2">
          <a href={`https://wa.me/?text=${enc}`} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-[42px] rounded-xl bg-sage-deep text-white font-semibold text-[13px]">WhatsApp</a>
          <a href={`sms:?&body=${enc}`} className="flex items-center justify-center w-full h-[42px] rounded-xl bg-white/50 border border-white/60 text-ink font-semibold text-[13px]">Text</a>
          <button onClick={copy} className="flex items-center justify-center w-full h-[42px] rounded-xl text-[12px] text-ink-soft hover:text-ink">Copy</button>
        </div>
      </motion.div>
    </div>
  );
}
