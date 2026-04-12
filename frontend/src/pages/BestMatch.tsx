import { useMemo } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft, ArrowRight, Phone, Share2,
  Footprints, Bus, Car, Train, Check, Clock, AlertTriangle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import MapGL, { Marker as GLMarker, Source, Layer } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { FernAccent, WheatAccent, LeafAccent } from "@/components/Botanicals";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { rankOrgs } from "@/lib/rank-orgs";
import { reliabilityTone } from "@/lib/freshness";
import { useLocationStore } from "@/store/location";
import type { RankedOrg } from "@/types";

const ease = [0.22, 1, 0.36, 1] as const;

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

export default function BestMatch() {
  const navigate = useNavigate();
  const storedLocation = useLocationStore((s) => s.location);
  const language = useLocationStore((s) => s.language);
  const intent = useLocationStore((s) => s.intent);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const locationLabel = storedLocation?.label ?? "Columbia Heights";
  const orgs = useOrgs();

  const preferServices = intent?.type === "service" ? intent.services : undefined;

  const results = useMemo(
    () => rankOrgs(orgs, { userLocation, now: new Date(), mode: "closest", languages: [language], preferServices }),
    [userLocation, language, orgs, preferServices],
  );

  const promotable = results.filter((r) => reliabilityTone(r.org.reliability).shouldPromote);
  const hero = promotable[0];
  const backups = results.filter((r) => r.org.id !== hero?.org.id).slice(0, 5);

  if (!hero) return <EmptyState />;

  const { org } = hero;
  const tone = reliabilityTone(org.reliability);
  const miles = (hero.distanceMeters / 1609.344).toFixed(1);
  const transit = bestTransit(org, hero.walkMinutes, hero.transitMinutes, hero.driveMinutes);
  const Botanical = org.services[0] === "hot_meals" ? WheatAccent : org.services[0] === "mobile_pantry" ? LeafAccent : FernAccent;

  const openDirections = () => window.open(`https://www.google.com/maps/dir/?api=1&destination=${org.lat},${org.lon}`, "_blank", "noopener,noreferrer");
  const callOrg = () => { if (org.phone) window.location.href = `tel:${org.phone.replace(/[^0-9+]/g, "")}`; };
  const shareOrg = async () => {
    const text = [org.name, `${org.address}, ${org.city}, ${org.state}`, hero.openStatus.label, org.ai.plainEligibility, org.phone ? `Call: ${org.phone}` : null, "— via Nutrire (NourishNet)"].filter(Boolean).join("\n");
    if (navigator.share) { try { await navigator.share({ title: org.name, text }); return; } catch {} }
    try { await navigator.clipboard.writeText(text); } catch {}
  };

  return (
    <main
      className="relative min-h-screen overflow-hidden"
      style={{ background: "#EDE8E0" }}
    >
      {/* Vivid backdrop pools — strong enough for glass to read */}
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 50% at 5% 20%, rgba(79,140,110,0.35) 0%, transparent 55%),
          radial-gradient(ellipse 50% 45% at 80% 8%, rgba(170,145,215,0.3) 0%, transparent 50%),
          radial-gradient(ellipse 45% 40% at 75% 85%, rgba(225,175,80,0.25) 0%, transparent 50%),
          radial-gradient(ellipse 40% 35% at 95% 45%, rgba(155,130,200,0.22) 0%, transparent 45%),
          radial-gradient(ellipse 50% 45% at 20% 85%, rgba(100,160,130,0.2) 0%, transparent 50%),
          radial-gradient(ellipse 55% 50% at 45% 5%, rgba(240,210,170,0.28) 0%, transparent 50%)
        `,
      }} />
      {/* Grain */}
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none opacity-[0.035]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
        backgroundSize: "200px",
      }} />
      {/* Botanical */}
      <div aria-hidden="true" className="absolute -right-16 -bottom-16 w-[300px] h-[300px] lg:w-[400px] lg:h-[400px] pointer-events-none opacity-[0.04] text-sage-deep"><Botanical /></div>

      {/* ── NAV ── */}
      <motion.nav initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} className="relative z-10 px-5 lg:px-8 pt-4 pb-1 flex items-center justify-between">
        <button onClick={() => navigate("/")} className="h-9 px-3 rounded-lg text-[12px] font-medium text-ink-muted hover:text-ink hover:bg-ink/5 transition-colors inline-flex items-center gap-1.5">
          <ArrowLeft size={14} /> Back
        </button>
        <span className="text-[11px] text-ink-muted font-medium">{locationLabel}</span>
      </motion.nav>

      {/* ── BENTO GRID: map dominates left, cards stack right ── */}
      <div className="relative z-10 px-3 lg:px-5 pt-3 pb-4 lg:min-h-[calc(100dvh-72px)] grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] lg:grid-rows-[auto_auto_1fr] gap-2.5">

        {/* ── CARD 1: Identity ── */}
        <motion.div
          initial={{ opacity: 0, y: 14, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.1, ease }}
          whileHover={{ scale: 1.008, transition: { duration: 0.2 } }}
          className="lg:order-2 rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_4px_16px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.5)] p-4 flex flex-col gap-2 cursor-pointer"
          onClick={() => navigate(`/org/${org.id}`)}>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <OpenDot state={hero.openStatus.state} />
              <span className="text-[12px] text-ink-soft font-medium">{hero.openStatus.label}</span>
              <span className="text-ink/10">·</span>
              <span className="text-[12px] text-ink-muted tabular-nums">{miles} mi · {transit.label}</span>
            </div>
            <h1 className="font-display text-[clamp(28px,5.5vw,48px)] font-bold text-ink leading-[0.95] tracking-[-0.03em]">
              {org.name}
            </h1>
            <p className="mt-1 text-[11px] text-ink-muted font-medium">
              {org.neighborhood || org.city || "DMV"}{org.state ? `, ${org.state}` : ""}
            </p>
            {org.ai.heroCopy?.trim() && (
              <p className="mt-3 text-[14px] lg:text-[15px] text-ink/80 leading-[1.5] font-normal text-pretty">
                {org.ai.heroCopy}
              </p>
            )}
          </div>
          {/* Clock + confidence — compact row */}
          <div className="flex items-center gap-3">
            <HoursClock org={org} now={new Date()} />
            <div className="flex items-center gap-1.5 text-[9px] text-ink-muted">
              <span className="h-[4px] w-[4px] rounded-full" style={{ backgroundColor: tone.dotColor }} />
              {tone.label}
              {org.sourceName && <><span>·</span>{org.sourceName}</>}
            </div>
          </div>
        </motion.div>

        {/* ── CARD 2: What to expect + eligibility + insights ── */}
        <motion.div
          initial={{ opacity: 0, y: 14, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2, ease }}
          whileHover={{ scale: 1.005, transition: { duration: 0.2 } }}
          className="lg:order-3 rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_4px_16px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.5)] p-4 flex flex-col">
          {org.ai?.firstVisitGuide && org.ai.firstVisitGuide.length > 0 && (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-ink-muted">What to expect</p>
              <ul className="mt-2 space-y-2">
                {org.ai.firstVisitGuide.map((b, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4, delay: 0.35 + i * 0.1, ease }}
                    className="flex items-start gap-2">
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ duration: 0.3, delay: 0.4 + i * 0.1, type: "spring", stiffness: 300 }}
                      className="mt-[3px] h-3.5 w-3.5 rounded-full bg-white/30 border border-white/40 flex items-center justify-center shrink-0">
                      <Check size={7} className="text-ink-soft" strokeWidth={3} />
                    </motion.div>
                    <span className="text-[12px] text-ink/70 leading-snug">{b}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
          )}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.55, ease }}
            whileHover={{ scale: 1.01, boxShadow: "0 6px 20px rgba(0,0,0,0.08)" }}
            className="mt-3 rounded-xl bg-white/30 backdrop-blur-lg border border-white/40 px-3.5 py-2.5 cursor-default">
            <p className="text-[13px] text-ink font-medium leading-snug">{org.ai.plainEligibility}</p>
          </motion.div>
          {org.ai.culturalNotes && (
            <p className="mt-2 text-[10px] text-ink-muted italic">{org.ai.culturalNotes}</p>
          )}
          <div className="mt-auto pt-3">
            <MatchInsights hero={hero} />
          </div>
        </motion.div>

        {/* ── CARD 3: Destination — map + actions (LEFT, spans all rows) ── */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.15, ease }}
          className="lg:order-1 lg:row-span-3 rounded-2xl overflow-hidden bg-white/25 backdrop-blur-2xl border border-white/35 shadow-[0_4px_16px_rgba(0,0,0,0.06)] flex flex-col">
          <div className="flex-1 min-h-[120px] relative">
            <MapGL
              initialViewState={{
                longitude: (userLocation.lng + org.lon) / 2,
                latitude: (userLocation.lat + org.lat) / 2,
                zoom: 12.5,
                pitch: 40,
                bearing: -10,
              }}
              style={{ width: "100%", height: "100%" }}
              mapStyle={MAP_STYLE}
              attributionControl={false}
              interactive={true}
              dragRotate={true}
            >
              {/* Route line */}
              <Source type="geojson" data={{
                type: "Feature",
                properties: {},
                geometry: { type: "LineString", coordinates: [[userLocation.lng, userLocation.lat], [org.lon, org.lat]] },
              }}>
                <Layer type="line" paint={{ "line-color": "#4F7F6A", "line-width": 2.5, "line-dasharray": [2, 1.5], "line-opacity": 0.5 }} />
              </Source>

              {/* User pin — human silhouette with sonar */}
              <GLMarker longitude={userLocation.lng} latitude={userLocation.lat} anchor="center">
                <div className="relative w-12 h-12 flex items-center justify-center">
                  <div className="absolute w-12 h-12 rounded-full border border-[#4F7F6A]/20 animate-ping" style={{ animationDuration: "2.5s" }} />
                  <div className="absolute w-8 h-8 rounded-full border border-[#4F7F6A]/15 animate-ping" style={{ animationDuration: "2.5s", animationDelay: "0.5s" }} />
                  <div className="relative w-7 h-7 rounded-full bg-[#4F7F6A] shadow-[0_0_16px_rgba(79,127,106,0.7)] flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="7" r="4" fill="white" />
                      <path d="M12 13c-4.4 0-8 2-8 4.5V20h16v-2.5c0-2.5-3.6-4.5-8-4.5z" fill="white" />
                    </svg>
                  </div>
                </div>
              </GLMarker>

              {/* Org pin — beacon drop with glow */}
              <GLMarker longitude={org.lon} latitude={org.lat} anchor="bottom">
                <div className="relative flex flex-col items-center">
                  {/* Glow halo */}
                  <div className="absolute -top-1 w-8 h-8 rounded-full bg-white/10 blur-md animate-pulse" />
                  {/* Pin shape */}
                  <svg width="32" height="42" viewBox="0 0 32 42" className="drop-shadow-[0_4px_12px_rgba(255,255,255,0.3)]">
                    <defs>
                      <linearGradient id="pinGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ffffff" />
                        <stop offset="100%" stopColor="#d4e8dc" />
                      </linearGradient>
                    </defs>
                    <path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 26 16 26s16-14 16-26C32 7.2 24.8 0 16 0z" fill="url(#pinGrad)" />
                    <circle cx="16" cy="15" r="7" fill="#1B3528" />
                    <circle cx="16" cy="15" r="3" fill="#4F7F6A" />
                  </svg>
                  {/* Ground shadow */}
                  <div className="w-4 h-1 rounded-full bg-black/30 blur-[2px] -mt-0.5" />
                </div>
              </GLMarker>
            </MapGL>
            {/* Fade into actions */}
            <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-12 pointer-events-none" style={{ background: "linear-gradient(0deg, rgba(237,232,224,0.9) 0%, transparent 100%)" }} />
            {/* Top fade for blending */}
            <div aria-hidden="true" className="absolute inset-x-0 top-0 h-6 pointer-events-none" style={{ background: "linear-gradient(180deg, rgba(237,232,224,0.3) 0%, transparent 100%)" }} />
          </div>
          <div className="px-4 py-2.5 flex items-center gap-2">
            {tone.urgentCall ? (
              <button onClick={callOrg} className="flex-1 h-[38px] rounded-xl bg-terracotta text-white font-semibold text-[13px] flex items-center justify-center gap-2 hover:brightness-110 transition-all">
                <Phone size={14} /> Call first
              </button>
            ) : (
              <motion.button
                onClick={openDirections}
                whileHover={{ scale: 1.02, y: -1 }}
                whileTap={{ scale: 0.97 }}
                className="flex-1 h-[38px] rounded-xl bg-sage-deep text-white font-semibold text-[13px] flex items-center justify-center gap-2 transition-all shadow-[0_4px_12px_-4px_rgba(58,101,81,0.4)] hover:shadow-[0_8px_20px_-4px_rgba(58,101,81,0.5)]">
                Get directions <ArrowRight size={14} strokeWidth={2.5} />
              </motion.button>
            )}
            <button onClick={shareOrg} className="h-[38px] w-[38px] rounded-xl bg-white/30 border border-white/40 text-ink-muted flex items-center justify-center hover:bg-ink/8 transition-colors shrink-0">
              <Share2 size={14} />
            </button>
            {org.phone && !tone.urgentCall && (
              <button onClick={callOrg} className="h-[38px] w-[38px] rounded-xl bg-white/30 border border-white/40 text-ink-muted flex items-center justify-center hover:bg-ink/8 transition-colors shrink-0">
                <Phone size={14} />
              </button>
            )}
          </div>
        </motion.div>

        {/* ── CARD 4: Alternatives ── */}
        <motion.div
          initial={{ opacity: 0, y: 14, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.4, ease }}
          whileHover={{ scale: 1.005, transition: { duration: 0.2 } }}
          className="lg:order-4 rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_4px_16px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.5)] p-4 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-ink-muted">Alternatives nearby</p>
            <Link to="/all" className="text-[10px] font-medium text-ink-muted hover:text-ink-soft inline-flex items-center gap-0.5">
              All {results.length} <ArrowRight size={9} />
            </Link>
          </div>
          <div className="flex-1 flex flex-col gap-0.5">
            {backups.slice(0, 5).map((b, i) => (
              <motion.button
                key={b.org.id}
                onClick={() => navigate(`/org/${b.org.id}`)}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: 0.5 + i * 0.06, ease }}
                whileHover={{ x: 4, backgroundColor: "rgba(31,36,33,0.04)" }}
                whileTap={{ scale: 0.98 }}
                className="w-full flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors group">
                <BackupDot state={b.openStatus.state} />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-ink-soft font-medium truncate group-hover:text-ink transition-colors">{b.org.name}</p>
                  <p className="text-[9px] text-ink-muted truncate">{b.openStatus.label}</p>
                </div>
                <motion.span
                  className="text-[10px] text-ink-muted tabular-nums shrink-0"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.7 + i * 0.06 }}
                >{pickDistance(b)}</motion.span>
              </motion.button>
            ))}
          </div>
          {org.ai.reconciliationWarnings?.length ? (
            <div className="mt-2 pt-2 border-t border-ink/5 flex items-start gap-1.5 text-[9px] text-ink-muted">
              <AlertTriangle size={10} className="shrink-0 mt-0.5" />
              <span>{org.ai.reconciliationWarnings[0]}</span>
            </div>
          ) : null}
        </motion.div>
      </div>
    </main>
  );
}

// ── Open Hours Clock — radial 24h visualization ──

function HoursClock({ org, now }: { org: RankedOrg["org"]; now: Date }) {
  const dayKeys = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;
  const todayKey = dayKeys[now.getDay()];
  const parsed = org.ai?.parsedHours;
  const slots = (parsed && parsed[todayKey]) ?? [];

  const nowH = now.getHours();
  const nowM = now.getMinutes();
  const isOpen = slots.some((s) => {
    const [oh, om] = s.start.split(":").map(Number);
    const [ch, cm] = s.end.split(":").map(Number);
    return nowH * 60 + nowM >= oh * 60 + (om || 0) && nowH * 60 + nowM < ch * 60 + (cm || 0);
  });

  // Next relevant time
  const nextSlot = slots.find((s) => {
    const [oh, om] = s.start.split(":").map(Number);
    return nowH * 60 + nowM < oh * 60 + (om || 0);
  });
  const closeSlot = slots.find((s) => {
    const [oh, om] = s.start.split(":").map(Number);
    const [ch, cm] = s.end.split(":").map(Number);
    return nowH * 60 + nowM >= oh * 60 + (om || 0) && nowH * 60 + nowM < ch * 60 + (cm || 0);
  });

  const displayTime = `${nowH % 12 || 12}:${String(nowM).padStart(2, "0")}`;
  const ampm = nowH >= 12 ? "PM" : "AM";

  // Progress through the day (0-1)
  const dayProgress = (nowH * 60 + nowM) / (24 * 60);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9, rotateX: 20 }}
      animate={{ opacity: 1, scale: 1, rotateX: 0 }}
      transition={{ duration: 0.8, delay: 0.2, ease }}
      className="shrink-0"
      style={{ perspective: "600px" }}
    >
      <div
        className="relative w-[140px] rounded-2xl overflow-hidden bg-white/25 backdrop-blur-2xl border border-white/35 shadow-[0_8px_32px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.5)]"
        style={{ transform: "rotateX(2deg) rotateY(-2deg)", transformStyle: "preserve-3d" }}
      >
        {/* Glass sheen */}
        <div aria-hidden="true" className="absolute inset-0 pointer-events-none" style={{
          background: "linear-gradient(145deg, rgba(255,255,255,0.3) 0%, transparent 40%, rgba(255,255,255,0.05) 100%)",
        }} />

        <div className="relative px-4 pt-3 pb-3">
          {/* Status badge */}
          <div className="flex items-center gap-1.5 mb-2">
            {isOpen ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" />
                  <span className="relative h-2 w-2 rounded-full bg-sage" />
                </span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-sage-deep">Open</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-ink-muted" />
                <span className="text-[9px] font-bold uppercase tracking-wider text-ink-muted">Closed</span>
              </>
            )}
          </div>

          {/* Big digital time */}
          <div className="flex items-baseline gap-0.5">
            <span className="text-[32px] font-bold text-ink leading-none tabular-nums tracking-tight">
              {displayTime}
            </span>
            <span className="text-[11px] font-semibold text-ink-muted ml-0.5">{ampm}</span>
          </div>

          {/* Day progress bar */}
          <div className="mt-2 h-[3px] rounded-full bg-ink/8 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-sage"
              initial={{ width: 0 }}
              animate={{ width: `${dayProgress * 100}%` }}
              transition={{ duration: 1, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
            />
            {/* Open hour segments overlay */}
            {slots.map((s, i) => {
              const [sh, sm] = s.start.split(":").map(Number);
              const [eh, em] = s.end.split(":").map(Number);
              const startPct = (sh * 60 + (sm || 0)) / (24 * 60) * 100;
              const endPct = (eh * 60 + (em || 0)) / (24 * 60) * 100;
              return (
                <div key={i} className="absolute top-0 h-full bg-sage/30 rounded-full" style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }} />
              );
            })}
          </div>

          {/* Next event */}
          <p className="mt-2 text-[9px] text-ink-muted">
            {isOpen && closeSlot
              ? `Closes ${closeSlot.end}`
              : nextSlot
              ? `Opens ${nextSlot.start}`
              : slots.length > 0
              ? `Today: ${slots.map(s => s.start).join(", ")}`
              : "Check hours"}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

// ── Match Insights infographic ──

function MatchInsights({ hero }: { hero: RankedOrg }) {
  const { org } = hero;
  const score = Math.round(hero.score * 100);
  const circumference = 2 * Math.PI * 28;
  const dashOffset = circumference - (hero.score * circumference);

  // Factor breakdown
  const factors = [
    { label: "Proximity", value: Math.max(0, 1 - (hero.distanceMeters / 1609.344) / 8), color: "#4F7F6A" },
    { label: "Open status", value: hero.openStatus.state === "open" ? 1 : hero.openStatus.state === "opens_today" ? 0.85 : 0.3, color: "#6B9B82" },
    { label: "Ease of access", value: org.accessRequirements.includes("appointment_required") ? 0.5 : 1, color: "#8AB4A0" },
    { label: "Data confidence", value: org.reliability.score, color: "#D9A441" },
    { label: "Tone score", value: org.ai.toneScore, color: "#A8C8B5" },
  ];

  const sources = org.crossSourceCount ?? 1;
  const languages = org.languages.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.65, ease }}
      className="rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_4px_16px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.5)] p-4"
    >
      <div className="flex gap-5">
        {/* Score ring */}
        <div className="relative shrink-0 w-[72px] h-[72px]">
          <svg viewBox="0 0 64 64" className="w-full h-full -rotate-90">
            <circle cx="32" cy="32" r="28" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
            <motion.circle
              cx="32" cy="32" r="28" fill="none"
              stroke="#4F7F6A"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: dashOffset }}
              transition={{ duration: 1.2, delay: 0.8, ease: [0.22, 1, 0.36, 1] }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[18px] font-bold text-ink tabular-nums">{score}</span>
          </div>
        </div>

        {/* Factor bars */}
        <div className="flex-1 space-y-1.5">
          {factors.map((f) => (
            <div key={f.label} className="flex items-center gap-2">
              <span className="text-[9px] text-ink-soft w-[70px] shrink-0 truncate">{f.label}</span>
              <div className="flex-1 h-[4px] rounded-full bg-white/6 overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: f.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.round(f.value * 100)}%` }}
                  transition={{ duration: 0.8, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom data pills */}
      <div className="mt-3 flex items-center gap-2 text-[9px] text-ink-muted">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/30 backdrop-blur-lg border border-white/40">
          {sources} {sources === 1 ? "source" : "sources"}
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/30 backdrop-blur-lg border border-white/40">
          {languages} {languages === 1 ? "language" : "languages"}
        </span>
        {org.foodTypes.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/30 backdrop-blur-lg border border-white/40">
            {org.foodTypes.length} food types
          </span>
        )}
      </div>
    </motion.div>
  );
}

// ── Tiny helpers ──

function OpenDot({ state }: { state: string }) {
  if (state === "open") return (
    <span className="relative flex h-2.5 w-2.5">
      <span className="absolute inset-0 rounded-full bg-white animate-ping opacity-25" />
      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.3)]" />
    </span>
  );
  if (state === "opens_today") return <Clock size={12} className="text-ink-soft" />;
  return <span className="h-2 w-2 rounded-full bg-white/20" />;
}

function BackupDot({ state }: { state: string }) {
  if (state === "open") return <span className="h-1.5 w-1.5 rounded-full bg-white/60 shrink-0" />;
  if (state === "opens_today") return <span className="h-1.5 w-1.5 rounded-full bg-white/35 shrink-0" />;
  return <span className="h-1.5 w-1.5 rounded-full bg-white/15 shrink-0" />;
}

function pickDistance(r: RankedOrg): string {
  if (r.walkMinutes <= 25) return `${r.walkMinutes}m walk`;
  return `${(r.distanceMeters / 1609.344).toFixed(1)} mi`;
}

function bestTransit(org: RankedOrg["org"], walk: number, transit: number | null, drive: number): { Icon: LucideIcon; label: string } {
  if (walk <= 20) return { Icon: Footprints, label: `${walk} min walk` };
  if (org.nearestTransit) {
    const wk = org.nearestTransit.walkMinutes ?? Math.round(org.nearestTransit.distanceMeters / 80);
    return { Icon: org.nearestTransit.name.toLowerCase().includes("metro") ? Train : Bus, label: `${wk} min to ${org.nearestTransit.name.split(" (")[0]}` };
  }
  if (transit !== null && transit <= 40) return { Icon: Bus, label: `~${transit} min bus` };
  return { Icon: Car, label: `${drive} min drive` };
}

function EmptyState() {
  return (
    <main className="min-h-screen flex items-center justify-center px-6" style={{ background: "#EDE8E0" }}>
      <div className="max-w-[400px] text-center">
        <p className="font-display text-2xl font-semibold text-ink">Nothing open nearby right now.</p>
        <p className="mt-3 text-base text-ink-soft">
          Try <Link to="/all" className="text-sage-deep underline font-medium">all options</Link> — or call 2-1-1.
        </p>
      </div>
    </main>
  );
}
