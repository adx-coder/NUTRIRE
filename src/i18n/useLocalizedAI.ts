import { useLocationStore } from "@/store/location";
import type { AIEnrichment } from "@/types";

/**
 * Returns AI text in the user's language if a translation exists,
 * otherwise falls back to the English original.
 *
 * Usage:
 *   const ai = useLocalizedAI(org.ai);
 *   ai.heroCopy   // Spanish if lang=es and translation exists
 */
export function useLocalizedAI(ai: AIEnrichment) {
  const lang = useLocationStore((s) => s.language);

  if (lang === "en" || !ai.translations?.[lang]) {
    return ai;
  }

  const t = ai.translations[lang];
  return {
    ...ai,
    heroCopy: t.heroCopy ?? ai.heroCopy,
    plainEligibility: t.plainEligibility ?? ai.plainEligibility,
    firstVisitGuide: t.firstVisitGuide ?? ai.firstVisitGuide,
    culturalNotes: t.culturalNotes ?? ai.culturalNotes,
  };
}
