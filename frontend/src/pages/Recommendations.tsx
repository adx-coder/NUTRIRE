import { useState, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Download, ArrowLeft, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import MapGL, { Marker as GLMarker, Source, Layer, type MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEquityGaps } from "@/data/load-data";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";

const ease = [0.22, 1, 0.36, 1] as const;
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

export default function Recommendations() {
  const gapData = useEquityGaps();
  const gaps = gapData?.gaps ?? [];
  const [current, setCurrent] = useState(0);
  const mapRef = useRef<MapRef>(null);

  const gap = gaps[current];
  const total = gaps.length;

  const goTo = useCallback((idx: number) => {
    const g = gaps[idx];
    if (!g) return;
    setCurrent(idx);
    mapRef.current?.flyTo({ center: [g.centroidLon, g.centroidLat], zoom: 12, duration: 1200, pitch: 30 });
  }, [gaps]);

  const prev = () => goTo((current - 1 + total) % total);
  const next = () => goTo((current + 1) % total);

  const downloadInsights = () => {
    const blob = new Blob([JSON.stringify({ generatedAt: new Date().toISOString(), gaps }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "nutrire-insights.json";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!gap) return (
    <main className="min-h-screen flex items-center justify-center" style={{ background: GLASS_BG }}>
      <GlassBackdrop /><p className="relative z-10 text-ink-soft">Loading...</p>
    </main>
  );

  const needPct = Math.min(gap.needScore / 0.3 * 100, 100);
  const supplyPct = Math.min(gap.supplyScore / 0.3 * 100, 100);
  const gapPct = Math.min(gap.gap / 0.15 * 100, 100);

  // GeoJSON for all gap circles
  const circlesData = {
    type: "FeatureCollection" as const,
    features: gaps.map((g, i) => ({
      type: "Feature" as const,
      properties: { idx: i, gap: g.gap, active: i === current },
      geometry: { type: "Point" as const, coordinates: [g.centroidLon, g.centroidLat] },
    })),
  };

  return (
    <main className="relative h-screen overflow-hidden" style={{ background: GLASS_BG }}>

      {/* ── MAP: Full background ── */}
      <div className="absolute inset-0">
        <MapGL
          ref={mapRef}
          initialViewState={{ longitude: gap.centroidLon, latitude: gap.centroidLat, zoom: 11, pitch: 25 }}
          style={{ width: "100%", height: "100%" }}
          mapStyle={MAP_STYLE}
          attributionControl={false}
          interactiveLayerIds={["gap-circles"]}
          cursor="pointer"
          onClick={(e) => {
            const feature = e.features?.[0];
            if (feature?.properties?.idx != null) {
              goTo(feature.properties.idx);
            }
          }}
        >
          {/* All gap circles */}
          <Source type="geojson" data={circlesData}>
            <Layer id="gap-circles" type="circle" paint={{
              "circle-radius": ["case", ["get", "active"], 18, ["interpolate", ["linear"], ["get", "gap"], 0, 6, 0.15, 14]],
              "circle-color": ["case", ["get", "active"], "#C96F4A", "rgba(201,111,74,0.4)"],
              "circle-opacity": ["case", ["get", "active"], 0.6, 0.3],
              "circle-stroke-width": ["case", ["get", "active"], 2, 0],
              "circle-stroke-color": "#C96F4A",
            }} />
          </Source>

          {/* Active gap marker */}
          <GLMarker longitude={gap.centroidLon} latitude={gap.centroidLat} anchor="center">
            <div className="relative">
              <div className="absolute inset-[-8px] rounded-full border-2 border-terracotta/40 animate-ping" style={{ animationDuration: "2s" }} />
              <div className="w-4 h-4 rounded-full bg-terracotta border-2 border-white shadow-[0_0_16px_rgba(201,111,74,0.5)]" />
            </div>
          </GLMarker>
        </MapGL>

        {/* Gradient overlays to make content readable */}
        <div aria-hidden="true" className="absolute inset-0 pointer-events-none" style={{
          background: "linear-gradient(180deg, rgba(237,232,224,0.7) 0%, rgba(237,232,224,0.2) 30%, rgba(237,232,224,0.1) 50%, rgba(237,232,224,0.6) 80%, rgba(237,232,224,0.95) 100%)",
        }} />
        <div aria-hidden="true" className="absolute inset-0 pointer-events-none" style={{
          background: "linear-gradient(90deg, rgba(237,232,224,0.85) 0%, rgba(237,232,224,0.3) 40%, transparent 60%)",
        }} />
      </div>

      {/* ── CONTENT: Overlaid on map ── */}
      <div className="relative z-10 h-full flex flex-col">
        {/* Nav */}
        <motion.nav initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
          className="px-5 lg:px-8 pt-5 flex items-center justify-between shrink-0">
          <Link to="/" className="h-9 px-3 rounded-lg bg-white/40 backdrop-blur-xl border border-white/50 text-[12px] font-medium text-ink-muted hover:text-ink transition-colors inline-flex items-center gap-1.5 shadow-sm">
            <ArrowLeft size={14} /> Back
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-ink-muted hidden lg:block">{total} areas analyzed</span>
            <button onClick={downloadInsights} className="h-9 px-3 rounded-lg bg-sage-deep text-white text-[12px] font-semibold inline-flex items-center gap-1.5 hover:brightness-110 shadow-sm">
              <Download size={13} /> JSON
            </button>
          </div>
        </motion.nav>

        {/* Main content area */}
        <div className="flex-1 flex items-end lg:items-center px-5 lg:px-10 pb-6 lg:pb-0">
          <div className="w-full max-w-[520px]">
            {/* Header */}
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease }}>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-sage-deep/50">Research contribution</p>
              <h1 className="mt-1 font-display text-[20px] lg:text-[24px] font-bold text-ink tracking-tight leading-tight">
                Equity Gap Analysis
              </h1>
            </motion.div>

            {/* Editorial card — the featured gap */}
            <motion.div
              initial={{ opacity: 0, y: 14, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.1, ease }}
              className="mt-4 rounded-2xl bg-white/50 backdrop-blur-2xl border border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.7)] p-5 lg:p-6"
            >
              {/* Nav arrows */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={prev}
                    className="h-8 w-8 rounded-full bg-white/50 border border-white/60 flex items-center justify-center hover:bg-white/70 transition-colors">
                    <ChevronLeft size={16} className="text-ink" />
                  </motion.button>
                  <span className="text-[12px] text-ink-muted tabular-nums font-medium">{current + 1} of {total}</span>
                  <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={next}
                    className="h-8 w-8 rounded-full bg-white/50 border border-white/60 flex items-center justify-center hover:bg-white/70 transition-colors">
                    <ChevronRight size={16} className="text-ink" />
                  </motion.button>
                </div>
                <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-terracotta/10 border border-terracotta/15 text-[10px] font-bold text-terracotta">
                  <Sparkles size={9} /> #{current + 1}
                </span>
              </div>

              <AnimatePresence mode="wait">
                <motion.div key={gap.zip} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.3, ease }}>
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-muted">ZIP {gap.zip}</p>
                  <h2 className="mt-1 font-display text-[22px] lg:text-[26px] font-bold text-ink leading-tight">{gap.label}</h2>
                  <p className="mt-3 text-[13px] text-ink/60 leading-relaxed text-pretty">{gap.why}</p>

                  {/* Bars */}
                  <div className="mt-4 space-y-2.5">
                    <Bar label="Need" value={gap.needScore} pct={needPct} color="#C96F4A" />
                    <Bar label="Supply" value={gap.supplyScore} pct={supplyPct} color="#4F7F6A" />
                    <Bar label="Gap" value={gap.gap} pct={gapPct} color="#D9A441" bold />
                  </div>

                  {/* Stats row */}
                  <div className="mt-4 flex items-center gap-3 text-[11px] text-ink-muted">
                    <span><span className="font-bold text-[14px] text-ink">{(gap.population / 1000).toFixed(0)}K</span> people</span>
                    <span className="text-ink/10">·</span>
                    <span><span className="font-bold text-[14px] text-ink">{gap.underservedPopulation.toLocaleString()}</span> underserved</span>
                    <span className="text-ink/10">·</span>
                    <span><span className="font-bold text-[14px] text-ink">{gap.nearbyOrgCount}</span> orgs</span>
                  </div>

                  {/* Suggested host */}
                  {gap.suggestedHost && (
                    <div className="mt-4 rounded-xl bg-sage/5 border border-sage/10 px-3.5 py-2.5">
                      <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-sage-deep/50">Suggested host</p>
                      <p className="mt-0.5 text-[13px] font-semibold text-ink">{gap.suggestedHost.name}</p>
                      <p className="text-[10px] text-ink-muted">{gap.suggestedHost.distance_km.toFixed(1)} km{gap.suggestedHost.has_hours ? " · confirmed" : ""}</p>
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </motion.div>

            {/* Quick jump dots */}
            <div className="mt-3 flex items-center justify-center gap-1">
              {gaps.slice(0, Math.min(20, total)).map((_, i) => (
                <button key={i} onClick={() => goTo(i)}
                  className={`rounded-full transition-all duration-200 ${
                    i === current ? "w-5 h-1.5 bg-terracotta" : "w-1.5 h-1.5 bg-ink/15 hover:bg-ink/30"
                  }`} />
              ))}
              {total > 20 && <span className="text-[9px] text-ink-muted ml-1">+{total - 20}</span>}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function Bar({ label, value, pct, color, bold }: { label: string; value: number; pct: number; color: string; bold?: boolean }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${bold ? "text-ink" : "text-ink-muted"}`}>{label}</span>
        <span className={`text-[11px] font-bold tabular-nums ${bold ? "text-ink" : "text-ink-soft"}`}>{(value * 100).toFixed(1)}%</span>
      </div>
      <div className={`${bold ? "h-2" : "h-1.5"} rounded-full bg-ink/6 overflow-hidden`}>
        <motion.div className="h-full rounded-full" style={{ backgroundColor: color }}
          initial={{ width: 0 }} animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }} />
      </div>
    </div>
  );
}
