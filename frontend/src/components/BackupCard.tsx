import type { RankedOrg } from "@/types";
import { ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

interface Props {
  result: RankedOrg;
  onClick?: () => void;
  className?: string;
}

export function BackupCard({ result, onClick, className }: Props) {
  const { org, walkMinutes, transitMinutes, driveMinutes, openStatus } = result;
  const mode = pickMode(org, walkMinutes, transitMinutes, driveMinutes);

  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ y: -2, scale: 1.005 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={clsx(
        "group relative w-full text-left overflow-hidden",
        "rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40",
        "shadow-[0_2px_8px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,0.5)]",
        "hover:bg-white/40 hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage/20",
        "transition-all duration-200",
        className,
      )}
      aria-label={`${org.name} — ${openStatus.label}`}
    >
      <div className="relative px-4 py-3.5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-display text-[14px] font-semibold text-ink leading-tight truncate">{org.name}</h3>
          <span className="text-[11px] text-ink-muted tabular-nums shrink-0">{mode}</span>
        </div>

        <div className="mt-1 flex items-center gap-2">
          <StatusDot state={openStatus.state} />
          <span className="text-[11px] text-ink-soft font-medium">{openStatus.label}</span>
        </div>

        {org.ai.heroCopy?.trim() && (
          <p className="mt-2 text-[12px] text-ink/60 leading-snug line-clamp-2">{org.ai.heroCopy}</p>
        )}

        <div className="mt-2 flex items-end justify-between gap-3">
          <p className="text-[11px] text-sage-deep font-medium truncate">{org.ai.plainEligibility}</p>
          <ArrowRight size={12} className="text-ink-muted group-hover:text-ink group-hover:translate-x-0.5 transition-all shrink-0" />
        </div>
      </div>
    </motion.button>
  );
}

function StatusDot({ state }: { state: string }) {
  if (state === "open") return (
    <span className="relative flex h-[6px] w-[6px]">
      <span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" />
      <span className="relative h-[6px] w-[6px] rounded-full bg-sage" />
    </span>
  );
  if (state === "opens_today") return <span className="h-[6px] w-[6px] rounded-full bg-mustard" />;
  return <span className="h-[6px] w-[6px] rounded-full bg-ink-muted" />;
}

function pickMode(org: RankedOrg["org"], walk: number, transit: number | null, drive: number): string {
  if (walk <= 25) return `${walk}m walk`;
  if (org.nearestTransit) {
    const wk = org.nearestTransit.walkMinutes ?? Math.round(org.nearestTransit.distanceMeters / 80);
    return `${wk}m → ${org.nearestTransit.name.split(" (")[0]}`;
  }
  if (transit !== null && transit <= 40) return `~${transit}m bus`;
  return `${drive}m drive`;
}
