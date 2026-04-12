import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Coords, LangCode, ServiceType } from "@/types";

/**
 * Nutrire — user location + language + search intent store.
 *
 * We persist only language (so a Spanish-speaking user keeps Spanish on reload).
 * Location + intent are session-only: never stored across reloads — dignity/privacy.
 */

export interface UserLocation {
  coords: Coords;
  label: string;
  source: "geolocate" | "typed" | "default";
}

/** What the user is looking for — set by suggestion chips on Home */
export type SearchIntent =
  | { type: "service"; services: ServiceType[] }
  | { type: "general" }
  | null;

interface LocationState {
  location: UserLocation | null;
  language: LangCode;
  intent: SearchIntent;
  setLocation: (loc: UserLocation) => void;
  clearLocation: () => void;
  setLanguage: (lang: LangCode) => void;
  setIntent: (intent: SearchIntent) => void;
}

export const useLocationStore = create<LocationState>()(
  persist(
    (set) => ({
      location: null,
      language: "en",
      intent: null,
      setLocation: (loc) => set({ location: loc }),
      clearLocation: () => set({ location: null }),
      setLanguage: (lang) => set({ language: lang }),
      setIntent: (intent) => set({ intent }),
    }),
    {
      name: "nutrire-prefs",
      partialize: (state) => ({ language: state.language }),
    },
  ),
);
