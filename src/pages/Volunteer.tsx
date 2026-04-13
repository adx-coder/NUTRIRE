import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ExternalLink, Users } from "lucide-react";
import { useT } from "@/i18n/useT";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { haversineMeters, metersToMiles } from "@/lib/geo";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";
import { TopNav } from "@/components/TopNav";
import { PageHeader } from "@/components/PageHeader";
import { Chip } from "@/components/Chip";
import { useLocationStore } from "@/store/location";
import type { EnrichedOrganization } from "@/types";

type FilterKey = "nearby" | "has_url" | "spanish";

interface VolRow {
  org: EnrichedOrganization;
  distanceMiles: number;
}

const ease = [0.22, 1, 0.36, 1] as const;

export default function Volunteer() {
  const t = useT();
  const storedLocation = useLocationStore((s) => s.location);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const orgs = useOrgs();

  const [filters, setFilters] = useState<Record<FilterKey, boolean>>({
    nearby: false,
    has_url: false,
    spanish: false,
  });

  const toggle = (key: FilterKey) =>
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }));

  const rows = useMemo<VolRow[]>(() => {
    const volOrgs = orgs.filter((o) => o.acceptsVolunteers);
    const withDistance: VolRow[] = volOrgs.map((org) => ({
      org,
      distanceMiles: metersToMiles(
        haversineMeters(userLocation, { lat: org.lat, lng: org.lon }),
      ),
    }));
    const filtered = withDistance.filter(({ org, distanceMiles }) => {
      if (filters.nearby && distanceMiles > 10) return false;
      if (filters.has_url && !org.volunteerUrl && !org.website) return false;
      if (filters.spanish && !org.languages.includes("es")) return false;
      return true;
    });
    return filtered.sort((a, b) => a.distanceMiles - b.distanceMiles);
  }, [filters, orgs, userLocation]);

  return (
    <main className="min-h-screen relative overflow-hidden" style={{ background: GLASS_BG }}>
      <GlassBackdrop />
      <div className="relative z-10">
        <TopNav backTo="/give" />
        <div className="max-w-3xl mx-auto px-3 sm:px-5 lg:px-10 pt-8 sm:pt-10 lg:pt-14 pb-20">
          <PageHeader
            eyebrow={t("vol.eyebrow")}
            title={t("vol.title")}
            subtitle={t("vol.subtitle", { count: rows.length })}
          />

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease }}
            className="mt-8 flex flex-wrap gap-2"
          >
            <Chip selected={filters.nearby} onClick={() => toggle("nearby")}>{t("vol.filterNearby")}</Chip>
            <Chip selected={filters.has_url} onClick={() => toggle("has_url")}>{t("vol.filterLink")}</Chip>
            <Chip selected={filters.spanish} onClick={() => toggle("spanish")}>{t("vol.filterSpanish")}</Chip>
          </motion.div>

          {rows.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-display text-xl font-semibold text-ink">{t("all.noResults")}</p>
              <p className="mt-2 text-sm text-ink-soft">{t("all.tryRemoving")}</p>
            </div>
          ) : (
            <motion.div
              initial="hidden"
              animate="visible"
              variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.04, delayChildren: 0.15 } } }}
              className="mt-8 flex flex-col gap-3"
            >
              {rows.map(({ org, distanceMiles }) => (
                <motion.div
                  key={org.id}
                  variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease } } }}
                >
                  <VolunteerCard org={org} distanceMiles={distanceMiles} />
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>
      </div>
    </main>
  );
}

function VolunteerCard({ org, distanceMiles }: { org: EnrichedOrganization; distanceMiles: number }) {
  const t = useT();
  const volUrl = org.volunteerUrl || org.website;
  return (
    <article className="rounded-2xl border border-white/40 bg-white/30 backdrop-blur-2xl p-3.5 sm:p-5 hover:bg-white/40 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-base font-semibold text-ink truncate">{org.name}</h3>
          <p className="mt-1 text-sm text-ink-soft truncate">{org.address}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-white/25 backdrop-blur-xl border border-white/35 text-[11px] font-medium text-ink-soft">
              <Users size={10} /> {t("vol.welcome")}
            </span>
            {org.languages.length > 0 && org.languages.some((l) => l !== "en") && (
              <span className="h-6 px-2 rounded-full bg-sage-soft/60 text-[11px] font-medium text-sage-deep inline-flex items-center">
                {org.languages.filter((l) => l !== "en").join(", ")}
              </span>
            )}
            <span className="h-6 px-2 rounded-full bg-white/20 border border-white/30 text-[11px] font-medium text-ink-muted inline-flex items-center">
              {distanceMiles.toFixed(1)} mi
            </span>
          </div>
        </div>
        <div className="shrink-0 flex flex-col sm:items-end gap-2 w-full sm:w-auto">
          {volUrl && (
            <a
              href={volUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 h-10 px-3.5 rounded-xl bg-sage-deep text-white text-sm font-semibold hover:bg-[#2E5342] transition-colors w-full sm:w-auto"
            >
              {t("vol.cta")} <ExternalLink size={13} />
            </a>
          )}
          <Link
            to={`/org/${org.id}`}
            className="inline-flex items-center justify-center h-10 px-3.5 rounded-xl bg-white/40 border border-white/50 text-sm font-medium text-ink hover:bg-white/60 transition-colors w-full sm:w-auto"
          >
            {t("map.viewDetails")}
          </Link>
        </div>
      </div>
    </article>
  );
}
