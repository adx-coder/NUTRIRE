import clsx from "clsx";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  selected?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
  as?: "button" | "span";
  variant?: "default" | "sage" | "mustard" | "terracotta";
  icon?: ReactNode;
}

export function Chip({ children, selected = false, onClick, ariaLabel, as = "button", variant = "default", icon }: Props) {
  const base =
    "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium " +
    "transition-all duration-200 min-h-[40px] border backdrop-blur-xl";

  const tone = selected
    ? "bg-sage-deep/90 text-white border-sage-deep/50 shadow-[0_2px_8px_rgba(58,101,81,0.3)]"
    : variant === "sage"
    ? "bg-white/30 text-sage-deep border-white/40 hover:bg-white/45 hover:border-sage/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]"
    : variant === "mustard"
    ? "bg-white/30 text-[#8A6A28] border-white/40 hover:bg-white/45 hover:border-mustard/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]"
    : variant === "terracotta"
    ? "bg-white/30 text-terracotta border-white/40 hover:bg-white/45 hover:border-terracotta/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]"
    : "bg-white/25 text-ink-soft border-white/35 hover:bg-white/40 hover:text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]";

  const className = clsx(base, tone);

  if (as === "span") {
    return <span className={className} aria-label={ariaLabel}>{icon}{children}</span>;
  }
  return (
    <button type="button" onClick={onClick} aria-pressed={selected} aria-label={ariaLabel} className={className}>
      {icon}{children}
    </button>
  );
}
