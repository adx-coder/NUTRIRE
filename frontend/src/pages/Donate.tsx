import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ExternalLink, Heart, AlertTriangle } from "lucide-react";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { trackFilter } from "@/lib/analytics";
import { haversineMeters, metersToMiles } from "@/lib/geo";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";
import { TopNav } from "@/components/TopNav";
import { PageHeader } from "@/components/PageHeader";
import { Chip } from "@/components/Chip";
import { useLocationStore } from "@/store/location";
import type { EnrichedOrganization } from "@/types";

type FilterKey = "food" | "money" | "nearby" | "has_url";

interface DonorRow {
  org: EnrichedOrganization;
  distanceMiles: number;
}

const ease = [0.22, 1, 0.36, 1] as const;

export default function Donate() {
  const storedLocation = useLocationStore((s) => s.location);
  const userLocation = storedLocation?.coords ?? mockUserLocation;
  const orgs = useOrgs();

  const [filters, setFilters] = useState<Record<FilterKey, boolean>>({
    food: false,
    money: false,
    nearby: false,
    has_url: false,
  });

  const toggle = (key: FilterKey) => {
    const newVal = !filters[key];
    trackFilter(`donate_${key}`, newVal);
    setFilters((prev) => ({ ...prev, [key]: newVal }));
  };

  const rows = useMemo<DonorRow[]>(() => {
    const donorOrgs = orgs.filter(
      (o) => o.acceptsFoodDonations || o.acceptsMoneyDonations,
    );
    const withDistance: DonorRow[] = donorOrgs.map((org) => ({
      org,
      distanceMiles: metersToMiles(
        haversineMeters(userLocation, { lat: org.lat, lng: org.lon }),
      ),
    }));
    const filtered = withDistance.filter(({ org, distanceMiles }) => {
      if (filters.food && !org.acceptsFoodDonations) return false;
      if (filters.money && !org.acceptsMoneyDonations) return false;
      if (filters.nearby && distanceMiles > 5) return false;
      if (filters.has_url && !org.donateUrl) return false;
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
            eyebrow="Donor view"
            title={<>Where your help matters<br />most this week.</>}
            subtitle={
              <>{rows.length} organizations across DC, Maryland, and Virginia accept donations.</>
            }
          />

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease }}
            className="mt-8 flex flex-wrap gap-2"
          >
            <Chip selected={filters.food} onClick={() => toggle("food")}>Accepts food</Chip>
            <Chip selected={filters.money} onClick={() => toggle("money")}>Accepts money</Chip>
            <Chip selected={filters.nearby} onClick={() => toggle("nearby")}>Within 5 mi</Chip>
            <Chip selected={filters.has_url} onClick={() => toggle("has_url")}>Has donate link</Chip>
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
                  <DonorCard org={org} distanceMiles={distanceMiles} />
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>
      </div>
    </main>
  );
}

function DonorCard({ org, distanceMiles }: { org: EnrichedOrganization; distanceMiles: number }) {
  const urgency = org.urgency;
  return (
    <Link
      to={`/org/${org.id}`}
      className="block rounded-2xl border border-white/40 bg-white/30 backdrop-blur-2xl p-5 hover:bg-white/40 transition-colors"
    >
      {/* Urgency banner */}
      {urgency && (urgency.level === "high" || urgency.level === "medium") && (
        <div className={`-mt-1 mb-3 flex items-start gap-2 rounded-xl px-3 py-2 text-[11px] leading-snug ${
          urgency.level === "high"
            ? "bg-terracotta/8 border border-terracotta/15 text-terracotta"
            : "bg-mustard/8 border border-mustard/15 text-ink-soft"
        }`}>
          <AlertTriangle size={12} className="shrink-0 mt-0.5" />
          <span>{urgency.message}</span>
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-base font-semibold text-ink truncate">{org.name}</h3>
          <p className="mt-1 text-sm text-ink-soft truncate">{org.address}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {org.acceptsFoodDonations && (
              <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-sage-soft/60 text-[11px] font-medium text-sage-deep">
                <Heart size={10} /> Food
              </span>
            )}
            {org.acceptsMoneyDonations && (
              <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-white/25 backdrop-blur-xl border border-white/35 text-[11px] font-medium text-ink-soft">
                $ Money
              </span>
            )}
            {urgency && urgency.level === "high" && (
              <span className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-terracotta/10 border border-terracotta/15 text-[11px] font-bold text-terracotta">
                {urgency.multiplier}x impact
              </span>
            )}
            <span className="h-6 px-2 rounded-full bg-white/20 border border-white/30 text-[11px] font-medium text-ink-muted inline-flex items-center">
              {distanceMiles.toFixed(1)} mi
            </span>
          </div>
        </div>
        {org.donateUrl && (
          <a
            href={org.donateUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-sage-deep text-white text-sm font-semibold hover:bg-[#2E5342] transition-colors"
          >
            Donate <ExternalLink size={13} />
          </a>
        )}
      </div>
    </Link>
  );
}
