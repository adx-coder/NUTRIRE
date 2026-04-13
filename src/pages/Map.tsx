import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Download, X, AlertTriangle, Check, ArrowRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from "react-leaflet";
import L from "leaflet";

import { useOrgs, useEquityGaps, mockUserLocation, type EquityGap } from "@/data/load-data";
import { useLocationStore } from "@/store/location";
import type { EnrichedOrganization } from "@/types";
import { navigateBackOr } from "@/lib/navigation";
import { useT } from "@/i18n/useT";

const orgIcon = new L.DivIcon({
  html: `<div style="width:10px;height:10px;border-radius:50%;background:#3A6551;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3)"></div>`,
  iconSize: [10, 10],
  iconAnchor: [5, 5],
  className: "",
});

const userIcon = new L.DivIcon({
  html: `<div style="width:16px;height:16px;border-radius:50%;background:#4F7F6A;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  className: "",
});

type ViewMode = "orgs" | "gaps" | "both";

const GAP_CIRCLE_STYLE = { color: "#A85A3A", fillColor: "#A85A3A", fillOpacity: 0.35, weight: 2 } as const;

export default function MapPage() {
  const t = useT();
  const navigate = useNavigate();
  const storedLocation = useLocationStore((s) => s.location);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const orgs = useOrgs();
  const gapData = useEquityGaps();
  const gaps = gapData?.gaps ?? [];

  const [viewMode, setViewMode] = useState<ViewMode>("both");
  const [selectedOrg, setSelectedOrg] = useState<EnrichedOrganization | null>(null);
  const [selectedGap, setSelectedGap] = useState<EquityGap | null>(null);

  const geoOrgs = useMemo(
    () => orgs.filter((o) => o.lat != null && o.lon != null && !isNaN(o.lat) && !isNaN(o.lon)),
    [orgs],
  );

  const hasMapData = geoOrgs.length > 0 || gaps.length > 0;

  const handleBack = () => {
    navigateBackOr(navigate, "/");
  };

  const downloadInsights = () => {
    const payload = {
      generatedAt: new Date().toISOString(),
      totalOrgs: orgs.length,
      equityGaps: gaps,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nutrire-insights.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="relative h-screen w-full overflow-hidden" style={{ background: "#EDE8E0" }}>
      <MapContainer
        center={[userLocation.lat, userLocation.lng]}
        zoom={10}
        className="h-full w-full z-0"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />

        <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon}>
          <Popup>Your location</Popup>
        </Marker>

        {(viewMode === "orgs" || viewMode === "both") &&
          geoOrgs.map((org) => (
            <Marker
              key={org.id}
              position={[org.lat, org.lon]}
              icon={orgIcon}
              eventHandlers={{
                click: () => {
                  setSelectedOrg(org);
                  setSelectedGap(null);
                },
              }}
            >
              <Popup>
                <div className="text-sm max-w-[200px]">
                  <strong>{org.name}</strong>
                  {org.hoursRaw && <p className="mt-1 text-xs text-ink-soft">{org.hoursRaw.slice(0, 60)}</p>}
                </div>
              </Popup>
            </Marker>
          ))}

        {(viewMode === "gaps" || viewMode === "both") &&
          gaps.map((gap) => (
            <CircleMarker
              key={gap.zip}
              center={[gap.centroidLat, gap.centroidLon]}
              radius={Math.max(8, gap.gap * 200)}
              pathOptions={GAP_CIRCLE_STYLE}
              eventHandlers={{
                click: () => {
                  setSelectedGap(gap);
                  setSelectedOrg(null);
                },
              }}
            >
              <Popup>
                <div className="text-sm max-w-[200px]">
                  <strong>{gap.label}</strong>
                  <p className="text-xs text-ink-soft">Gap: {(gap.gap * 100).toFixed(1)}% - {gap.nearbyOrgCount} orgs nearby</p>
                </div>
              </Popup>
            </CircleMarker>
          ))}
      </MapContainer>

      <div className="absolute left-2 sm:left-4 top-3 sm:top-4 z-[1000] flex flex-col gap-2">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex w-fit items-center gap-1.5 h-10 px-3 rounded-xl bg-white/50 backdrop-blur-2xl border border-white/60 text-[12px] font-medium text-ink-soft shadow-sm hover:text-ink hover:bg-white/70 transition-all"
        >
          <ArrowLeft size={14} /> {t("nav.back")}
        </button>

        <div className="w-[180px] sm:w-[220px] rounded-2xl bg-white/50 backdrop-blur-2xl border border-white/60 shadow-sm overflow-hidden p-2.5 sm:p-3.5">
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-sage-deep/60 mb-2">{t("map.view")}</p>
          <div className="flex flex-col gap-0.5">
            {(["both", "orgs", "gaps"] as ViewMode[]).map((mode) => (
              <label
                key={mode}
                className={clsx(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] transition-colors",
                  mode === viewMode ? "bg-sage/10 font-semibold text-sage-deep" : "text-ink-soft hover:bg-white/50",
                )}
              >
                <input
                  type="radio"
                  name="view-mode"
                  value={mode}
                  checked={mode === viewMode}
                  onChange={() => setViewMode(mode)}
                  className="h-3 w-3 accent-sage-deep"
                />
                {mode === "both" ? t("map.all") : mode === "orgs" ? `${t("map.resources")} (${geoOrgs.length})` : `${t("map.gaps")} (${gaps.length})`}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="absolute right-2 sm:right-4 top-3 sm:top-4 z-[1000] flex items-center gap-1.5 sm:gap-2">
        <Link
          to="/recommendations"
          className="hidden sm:inline-flex h-10 px-3 rounded-xl bg-white/50 backdrop-blur-2xl border border-white/60 text-[12px] font-medium text-ink-soft hover:text-ink transition-all items-center gap-1.5 shadow-sm"
        >
          {t("map.recommendations")}
        </Link>
        <button
          type="button"
          onClick={downloadInsights}
          className="h-10 px-3 rounded-xl bg-sage-deep text-white text-[12px] font-semibold inline-flex items-center gap-1.5 hover:brightness-110 shadow-sm"
        >
          <Download size={13} /> <span className="hidden sm:inline">JSON</span>
        </button>
      </div>

      <div className="absolute bottom-2 sm:bottom-4 left-2 sm:left-4 z-[1000] rounded-xl bg-white/50 backdrop-blur-2xl border border-white/60 shadow-sm px-2.5 sm:px-3.5 py-2">
        <p className="text-[10px] sm:text-[11px] text-ink-soft">
          {geoOrgs.length} resources - {gaps.length} gaps - {gaps.filter((g) => g.gap > 0.03).length} underserved
        </p>
      </div>

      {!hasMapData && (
        <div className="absolute inset-x-3 bottom-20 sm:bottom-4 sm:left-4 sm:right-auto z-[1050] max-w-[360px] rounded-2xl bg-white/70 backdrop-blur-2xl border border-white/70 shadow-[0_8px_32px_rgba(0,0,0,0.12)] p-4">
          <p className="text-sm font-semibold text-ink">Map data is unavailable right now.</p>
          <p className="mt-1 text-xs text-ink-soft">Try the recommendations view or come back after the dataset finishes loading.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/recommendations"
              className="inline-flex items-center justify-center h-9 px-3 rounded-xl bg-sage-deep text-white text-xs font-semibold hover:brightness-110 transition-all"
            >
              View recommendations
            </Link>
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center justify-center h-9 px-3 rounded-xl bg-white/60 border border-white/70 text-xs font-medium text-ink hover:bg-white/80 transition-all"
            >
              Go back
            </button>
          </div>
        </div>
      )}

      <AnimatePresence>
        {selectedOrg && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-x-2 bottom-2 sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-16 z-[1100] sm:w-[340px] max-h-[60vh] sm:max-h-[calc(100vh-100px)] overflow-y-auto rounded-2xl bg-white/60 backdrop-blur-2xl border border-white/70 shadow-[0_8px_40px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.7)] p-4 sm:p-5"
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="min-w-0">
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-sage-deep/60">
                  {selectedOrg.sourceName ?? selectedOrg.sourceId}
                </p>
                <h2 className="mt-1 font-display text-[16px] sm:text-[18px] font-bold text-ink leading-tight">{selectedOrg.name}</h2>
                <p className="mt-0.5 text-[11px] text-ink-muted">{selectedOrg.address}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrg(null)}
                className="shrink-0 h-7 w-7 rounded-full bg-white/50 border border-white/60 hover:bg-white/80 inline-flex items-center justify-center transition-colors"
              >
                <X size={13} className="text-ink" />
              </button>
            </div>

            {selectedOrg.ai?.heroCopy && (
              <p className="text-[12px] text-ink/65 italic leading-relaxed mb-3">{selectedOrg.ai.heroCopy}</p>
            )}

            {selectedOrg.ai?.plainEligibility && (
              <div className="rounded-xl bg-white/40 border border-white/50 px-3 py-2 mb-3">
                <p className="text-[12px] text-ink font-medium">{selectedOrg.ai.plainEligibility}</p>
              </div>
            )}

            {selectedOrg.ai?.firstVisitGuide && selectedOrg.ai.firstVisitGuide.length > 0 && (
              <div className="mb-3">
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-ink-muted mb-1.5">{t("map.firstVisit")}</p>
                <ul className="space-y-1.5">
                  {selectedOrg.ai.firstVisitGuide.map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-[11px] text-ink/60 leading-snug">
                      <Check size={10} className="text-sage-deep mt-0.5 shrink-0" strokeWidth={3} />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selectedOrg.phone && (
              <a href={`tel:${selectedOrg.phone}`} className="text-[12px] text-sage-deep font-medium hover:underline block mb-2">{selectedOrg.phone}</a>
            )}

            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate(`/org/${selectedOrg.id}`)}
              className="w-full h-9 rounded-xl bg-sage-deep text-white text-[12px] font-semibold flex items-center justify-center gap-1.5 hover:brightness-110 transition-all"
            >
              {t("map.viewDetails")} <ArrowRight size={12} />
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedGap && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-x-2 bottom-2 sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-16 z-[1100] sm:w-[340px] max-h-[60vh] sm:max-h-[calc(100vh-100px)] overflow-y-auto rounded-2xl bg-white/60 backdrop-blur-2xl border border-white/70 shadow-[0_8px_40px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.7)] p-4 sm:p-5"
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="min-w-0">
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-terracotta inline-flex items-center gap-1">
                  <AlertTriangle size={10} /> Equity gap - ZIP {selectedGap.zip}
                </p>
                <h2 className="mt-1 font-display text-[16px] sm:text-[18px] font-bold text-ink leading-tight">{selectedGap.label}</h2>
              </div>
              <button
                type="button"
                onClick={() => setSelectedGap(null)}
                className="shrink-0 h-7 w-7 rounded-full bg-white/50 border border-white/60 hover:bg-white/80 inline-flex items-center justify-center transition-colors"
              >
                <X size={13} className="text-ink" />
              </button>
            </div>

            <p className="text-[12px] text-ink/60 leading-relaxed mb-4">{selectedGap.why}</p>

            <div className="space-y-2 mb-4">
              {[
                { label: t("rec.need"), value: selectedGap.needScore, color: "#C96F4A" },
                { label: t("rec.supply"), value: selectedGap.supplyScore, color: "#4F7F6A" },
                { label: t("rec.gap"), value: selectedGap.gap, color: "#D9A441" },
              ].map((bar) => (
                <div key={bar.label}>
                  <div className="flex justify-between text-[10px] mb-0.5">
                    <span className="text-ink-muted font-medium">{bar.label}</span>
                    <span className="text-ink font-bold tabular-nums">{(bar.value * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-ink/6 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min((bar.value / 0.15) * 100, 100)}%` }}
                      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                      className="h-full rounded-full"
                      style={{ backgroundColor: bar.color }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-1.5 text-[12px] mb-4">
              <div className="flex justify-between"><span className="text-ink-muted">{t("rec.people")}</span><span className="text-ink font-semibold tabular-nums">{selectedGap.population.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-ink-muted">{t("rec.underserved")}</span><span className="text-ink font-semibold tabular-nums">{selectedGap.underservedPopulation.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-ink-muted">{t("rec.orgs")}</span><span className="text-ink font-semibold tabular-nums">{selectedGap.nearbyOrgCount}</span></div>
            </div>

            {selectedGap.suggestedHost && (
              <div className="rounded-xl bg-sage/5 border border-sage/10 px-3 py-2.5">
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-sage-deep/50">{t("map.suggestedHost")}</p>
                <p className="mt-0.5 text-[13px] font-semibold text-ink">{selectedGap.suggestedHost.name}</p>
                <p className="text-[10px] text-ink-muted">{selectedGap.suggestedHost.distance_km.toFixed(1)} km{selectedGap.suggestedHost.has_hours ? " - confirmed" : ""}</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
