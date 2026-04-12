import type { ReactNode } from "react";
import { motion } from "framer-motion";

interface Props {
  eyebrow: string;
  title: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
}

/**
 * Consistent page hero across routes.
 *
 *   EYEBROW (uppercase sage-deep)
 *   Display title (Inter Tight, big)
 *   subtitle (optional)
 */
export function PageHeader({ eyebrow, title, subtitle, meta }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sage-deep">
        {eyebrow}
      </p>
      <h1 className="mt-3 font-display font-bold text-ink text-balance leading-[0.98] tracking-[-0.02em] text-[clamp(32px,5vw,56px)]">
        {title}
      </h1>
      {subtitle && (
        <p className="mt-4 text-base lg:text-lg text-ink-soft max-w-2xl text-pretty">
          {subtitle}
        </p>
      )}
      {meta && <div className="mt-4">{meta}</div>}
    </motion.div>
  );
}
