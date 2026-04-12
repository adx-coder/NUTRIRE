import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ExternalLink, Users } from "lucide-react";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { haversineMeters, metersToMiles } from "@/lib/geo";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";
import { TopNav } from "@/components/TopNav";
import { PageHeader } from "@/components/PageHeader";
import { Chip } from "@/components/Chip";
import { useLocationStore } from "@/store/location";
import type { EnrichedOrganization } from "@/types";

type FilterKey = "nearby" | "has_url" | "spanish" | "walk_in";

interface VolRow {
  org: EnrichedOrganization;
  distanceMiles: number;
}

const ease = [0.22, 1, 0.36, 1] as const;

export default function Volunteer() {
  const storedLocation = useLocationStore((s) => s.location);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const orgs = useOrgs();

  const [filters, setFilters] = useState<Record<FilterKey, boolean>>({
    nearby: false,
    has_url: false,
    spanish: false,
    walk_in: false,
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
      if (filters.walk_in && !org.accessRequirements.includes("walk_in")) return false;
      return true;
    });
    return filtered.sort((a, b) => a.distanceMiles - b.distanceMiles);
  }, [filters, orgs, userLocation]);

  return (
    <main className="min-h-screen relative overflow-hidden" style={{ background: GLASS_BG }}>
      <GlassBackdrop />
      <div className="relative z-10">
        <TopNav backTo="/give" />
        <div className="max-w-3xl mx-auto px-5 lg:px-10 pt-10 lg:pt-14 pb-20">
          <PageHeader
            eyebrow="Volunteer"
            title={<>Give a few hours<br />this week.</>}
            subtitle={<>{rows.length} organizations across the DMV are looking for volunteers.</>}
          />

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease }}
            className="mt-8 flex flex-wrap gap-2"
          >
            <Chip selected={filters.nearby} onClick={() => toggle("nearby")}>Within 10 mi</Chip>
            <Chip selected={filters.has_url} onClick={() => toggle("has_url")}>Has sign-up link</Chip>
            <Chip selected={filters.spanish} onClick={() => toggle("spanish")}>Spanish needed</Chip>
          </motion.div>

          {rows.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-display text-xl font-semibold text-ink">Nothing matches those filters.</p>
              <p className="mt-2 text-sm text-ink-soft">Try removing a few.</p>
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
  const volUrl = org.volunteerUrl || org.website;
  return (
    <Link
      to={`/org/${org.id}`}
      className="block rounded-2xl border border-white/40 bg-white/30 backdrop-blur-2xl p-5 hover:bg-white/40 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-base font-semibold text-ink truncate">{org.name}</h3>
          <p className="mt-1 text-sm text-ink-soft truncate">{org.address}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-white/25 backdrop-blur-xl border border-white/35 text-[11px] font-medium text-ink-soft">
              <Users size={10} /> Volunteers welcome
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
        {volUrl && (
          <a
            href={volUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-sage-deep text-white text-sm font-semibold hover:bg-[#2E5342] transition-colors"
          >
            Sign up <ExternalLink size={13} />
          </a>
        )}
      </div>
    </Link>
  );
}
