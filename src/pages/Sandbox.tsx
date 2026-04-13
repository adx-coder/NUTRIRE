import { useMemo, useState } from "react";
import type { LangCode } from "@/types";
import { BackupCard } from "@/components/BackupCard";
import { rankOrgs, type RankMode } from "@/lib/rank-orgs";
import { useOrgs, mockUserLocation } from "@/data/load-data";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";

export default function Sandbox() {
  const [mode, setMode] = useState<RankMode>("closest");
  const [lang, setLang] = useState<LangCode>("en");
  const orgs = useOrgs();

  const results = useMemo(
    () => rankOrgs(orgs, { userLocation: mockUserLocation, mode, languages: [lang], now: new Date() }),
    [mode, lang, orgs],
  );

  return (
    <main className="min-h-screen relative overflow-hidden" style={{ background: GLASS_BG }}>
      <GlassBackdrop />
      <div className="relative z-10">
        <header className="px-5 py-3 flex items-center gap-4 text-sm">
          <span className="font-semibold text-sage-deep">sandbox</span>
          <div className="flex gap-2">
            {(["closest", "most_private", "most_welcoming"] as RankMode[]).map((m) => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1 rounded-full border backdrop-blur-xl transition-colors ${
                  mode === m ? "bg-sage/10 border-sage/20 text-sage-deep font-semibold" : "bg-white/20 border-white/30 text-ink-soft"
                }`}>{m.replace("_", " ")}</button>
            ))}
          </div>
          <div className="flex gap-2 ml-auto">
            {(["en", "es", "am"] as const).map((l) => (
              <button key={l} onClick={() => setLang(l)}
                className={`px-3 py-1 rounded-full border backdrop-blur-xl transition-colors ${
                  lang === l ? "bg-sage/10 border-sage/20 text-sage-deep font-semibold" : "bg-white/20 border-white/30 text-ink-soft"
                }`}>{l.toUpperCase()}</button>
            ))}
          </div>
        </header>
        <section className="px-5 py-6 max-w-lg mx-auto space-y-3">
          {results.slice(0, 8).map((r) => <BackupCard key={r.org.id} result={r} />)}
        </section>
      </div>
    </main>
  );
}
