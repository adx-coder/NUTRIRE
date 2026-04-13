import { useCallback } from "react";
import { useLocationStore } from "@/store/location";
import { translations, type UILang } from "./translations";

/**
 * Translation hook. Returns a `t(key, vars?)` function
 * that resolves the current language from the store.
 *
 * Usage:
 *   const t = useT();
 *   t("home.nearYou")              // "near you" | "cerca de ti" | "በአቅራቢያዎ"
 *   t("all.optionsNear", { count: 42, location: "DC" })
 */
export function useT() {
  const lang = useLocationStore((s) => s.language) as UILang;
  const dict = translations[lang] || translations.en;

  return useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let str = dict[key] ?? translations.en[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          str = str.replace(new RegExp(`\\{\\{${k}\\}\\}`, "g"), String(v));
        }
      }
      return str;
    },
    [dict],
  );
}

/** Get the current UI language code */
export function useLang(): UILang {
  return useLocationStore((s) => s.language) as UILang;
}
