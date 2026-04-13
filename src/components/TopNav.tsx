import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { useT } from "@/i18n/useT";
import { navigateBackOr } from "@/lib/navigation";

interface Props {
  backTo?: string;
  onBack?: () => void;
  right?: ReactNode;
}

/**
 * Consistent top nav pill row used across routes.
 * Left: back button. Right: optional slot.
 */
export function TopNav({ backTo, onBack, right }: Props) {
  const navigate = useNavigate();
  const t = useT();

  const handleBack = () => {
    if (onBack) return onBack();
    navigateBackOr(navigate, backTo ?? "/");
  };

  return (
    <motion.nav
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="px-5 lg:px-10 pt-5 flex items-center justify-between"
    >
      <button
        type="button"
        onClick={handleBack}
        className="inline-flex items-center gap-1.5 h-10 px-3 rounded-xl text-sm font-medium text-ink-soft hover:text-ink hover:bg-white/40 transition-colors"
        aria-label={t("nav.back")}
      >
        <ArrowLeft size={16} aria-hidden="true" />
        {t("nav.back")}
      </button>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </motion.nav>
  );
}
