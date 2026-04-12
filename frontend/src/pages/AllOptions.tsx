import { useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft, MapPin, Search, X } from "lucide-react";
import { motion } from "framer-motion";
import MapGL, { Marker as GLMarker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import Fuse from "fuse.js";
import type { RankedOrg } from "@/types";
import { Chip } from "@/components/Chip";
import { BackupCard } from "@/components/BackupCard";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { rankOrgs } from "@/lib/rank-orgs";
import { useLocationStore } from "@/store/location";

type FilterKey = "open" | "today" | "walk" | "metro" | "es" | "am" | "no_id" | "delivers";

const ease = [0.22, 1, 0.36, 1] as const;

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

export default function AllOptions() {
  const navigate = useNavigate();
  const storedLocation = useLocationStore((s) => s.location);
  const language = useLocationStore((s) => s.language);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const locationLabel = storedLocation?.label ?? "Columbia Heights";
  const now = useMemo(() => new Date(), []);

  const [active, setActive] = useState<Set<FilterKey>>(new Set());
  const [query, setQuery] = useState("");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(30);

  const toggle = (key: FilterKey) => {
    setActive((prev) => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  };

  const orgs = useOrgs();
  const allResults = useMemo(
    () => rankOrgs(orgs, { userLocation, now, mode: "closest", languages: [language], maxResults: 200 }),
    [userLocation, language, now, orgs],
  );

  const fuse = useMemo(() => new Fuse(allResults, {
    keys: [
      { name: "org.name", weight: 0.25 }, { name: "org.ai.heroCopy", weight: 0.2 },
      { name: "org.ai.plainEligibility", weight: 0.15 }, { name: "org.ai.culturalNotes", weight: 0.15 },
      { name: "org.neighborhood", weight: 0.1 }, { name: "org.city", weight: 0.1 },
    ],
    threshold: 0.4, includeScore: true,
  }), [allResults]);

  const filters: { key: FilterKey; label: string; apply: (r: RankedOrg) => boolean }[] = useMemo(() => [
    { key: "open", label: "Open now", apply: (r) => r.openStatus.state === "open" },
    { key: "today", label: "Today", apply: (r) => r.openStatus.state === "open" || r.openStatus.state === "opens_today" },
    { key: "walk", label: "Walkable", apply: (r) => r.walkMinutes <= 20 },
    { key: "metro", label: "Near metro", apply: (r) => !!r.org.nearestTransit && r.org.nearestTransit.name.toLowerCase().includes("metro") },
    { key: "es", label: "Español", apply: (r) => r.org.languages.includes("es") },
    { key: "am", label: "አማርኛ", apply: (r) => r.org.languages.includes("am") },
    { key: "no_id", label: "No ID", apply: (r) => r.org.accessRequirements.includes("no_id_required") },
    { key: "delivers", label: "Delivers", apply: (r) => r.org.services.includes("delivery") },
  ], []);

  const filtered = useMemo(() => {
    let base = allResults;
    if (query.trim()) base = fuse.search(query.trim()).map((h) => ({ ...h.item, searchScore: h.score ?? null }));
    if (active.size === 0) return base;
    const toApply = filters.filter((f) => active.has(f.key));
    return base.filter((r) => toApply.every((f) => f.apply(r)));
  }, [allResults, active, filters, query, fuse]);

  return (
    <main className="min-h-screen" style={{ background: "#EDE8E0" }}>
      {/* Backdrop */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 50% at 5% 30%, rgba(79,140,110,0.25) 0%, transparent 55%),
          radial-gradient(ellipse 50% 45% at 90% 10%, rgba(175,155,210,0.18) 0%, transparent 50%),
          radial-gradient(ellipse 45% 40% at 70% 90%, rgba(225,175,80,0.15) 0%, transparent 50%)
        `,
      }} />
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none opacity-[0.03]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
        backgroundSize: "200px",
      }} />

      <div className="relative z-10">
        {/* Nav */}
        <motion.nav initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease }}
          className="px-5 lg:px-8 pt-5 flex items-center justify-between">
          <button onClick={() => navigate(-1)} className="h-9 px-3 rounded-lg text-[12px] font-medium text-ink-muted hover:text-ink hover:bg-white/40 transition-colors inline-flex items-center gap-1.5">
            <ArrowLeft size={14} /> Back
          </button>
          <div className="hidden sm:inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-white/30 backdrop-blur-xl border border-white/40 text-[12px] text-ink-soft">
            <MapPin size={12} className="text-sage-deep" />
            <span className="font-medium text-ink">{locationLabel}</span>
            <span className="text-ink-muted">·</span>
            <Link to="/" className="text-sage-deep font-medium hover:underline">Change</Link>
          </div>
        </motion.nav>

        {/* Split layout */}
        <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:h-[calc(100vh-52px)]">
          {/* Left: list */}
          <div className="px-5 lg:px-8 pt-6 pb-16 lg:overflow-y-auto">
            <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}
              className="font-display text-[28px] lg:text-[32px] font-bold text-ink tracking-tight leading-[1.1]">
              {filtered.length} options near {locationLabel}
            </motion.h1>

            {/* Search — glass input */}
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.05, ease }} className="mt-5 relative">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
              <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder='Try "teff flour" or "hot meals near metro"'
                className="w-full h-11 pl-10 pr-10 rounded-xl bg-white/40 backdrop-blur-xl border border-white/50 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-sage/20 focus:border-sage/30 transition-colors shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]" />
              {query && (
                <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"><X size={16} /></button>
              )}
            </motion.div>

            {/* Filters */}
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1, ease }}
              className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filters">
              {filters.map((f) => (
                <Chip key={f.key} selected={active.has(f.key)} onClick={() => toggle(f.key)}>{f.label}</Chip>
              ))}
              {active.size > 0 && (
                <button onClick={() => setActive(new Set())} className="text-[13px] text-ink-muted hover:text-ink ml-1 min-h-[44px]">Clear</button>
              )}
            </motion.div>

            {/* Results */}
            <div className="mt-6">
              {filtered.length === 0 ? (
                <div className="py-16 text-center">
                  <p className="font-display text-xl font-semibold text-ink">Nothing matches.</p>
                  <p className="mt-2 text-sm text-ink-soft">Try removing filters.</p>
                  <button onClick={() => { setActive(new Set()); setQuery(""); }} className="mt-4 text-sm text-sage-deep font-medium hover:underline min-h-[44px]">Clear all</button>
                </div>
              ) : (
                <>
                  <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.04 } } }} className="space-y-2">
                    {filtered.slice(0, visibleCount).map((r) => (
                      <motion.div key={r.org.id}
                        variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease } } }}
                        onMouseEnter={() => setHoveredId(r.org.id)} onMouseLeave={() => setHoveredId(null)}>
                        <BackupCard result={r} onClick={() => navigate(`/org/${r.org.id}`)} />
                      </motion.div>
                    ))}
                  </motion.div>
                  {filtered.length > visibleCount && (
                    <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                      onClick={() => setVisibleCount((c) => c + 30)}
                      className="mt-4 w-full h-11 rounded-xl bg-white/30 backdrop-blur-xl border border-white/40 text-[13px] font-medium text-ink-soft hover:text-ink transition-colors shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]">
                      Show more · {filtered.length - visibleCount} more nearby
                    </motion.button>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Right: map — MapLibre GL */}
          <div className="hidden lg:block border-l border-white/20">
            <MapGL initialViewState={{ longitude: userLocation.lng, latitude: userLocation.lat, zoom: 11.5, pitch: 20 }}
              style={{ width: "100%", height: "100%" }} mapStyle={MAP_STYLE} attributionControl={false}>
              <GLMarker longitude={userLocation.lng} latitude={userLocation.lat} anchor="center">
                <div className="w-3.5 h-3.5 rounded-full bg-sage border-[2.5px] border-white shadow-[0_0_10px_rgba(79,127,106,0.5)]" />
              </GLMarker>
              {filtered.slice(0, Math.min(visibleCount, 80)).map((r) => (
                <GLMarker key={r.org.id} longitude={r.org.lon} latitude={r.org.lat} anchor="center">
                  <div className={`rounded-full border-2 border-white transition-all duration-200 ${
                    hoveredId === r.org.id ? "w-3 h-3 bg-sage-deep shadow-[0_0_8px_rgba(58,101,81,0.5)]" : "w-2 h-2 bg-sage/70"
                  }`} />
                </GLMarker>
              ))}
            </MapGL>
          </div>
        </div>
      </div>
    </main>
  );
}
