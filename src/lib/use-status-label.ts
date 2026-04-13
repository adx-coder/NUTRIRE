import type { OpenStatus } from "@/types";
import { useT } from "@/i18n/useT";

/**
 * Returns the translated open-status label.
 * Falls back to the English label if no translation key exists.
 */
export function useStatusLabel(status: OpenStatus): string {
  const t = useT();
  if (!status.labelKey) return status.label;
  const translated = t(status.labelKey, status.labelVars);
  // If t() returned the key itself (no translation found), fall back to English
  return translated === status.labelKey ? status.label : translated;
}
