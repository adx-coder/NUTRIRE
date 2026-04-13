import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LocationInput } from "@/components/LocationInput";
import { Chip } from "@/components/Chip";
import { useLocationStore } from "@/store/location";
import { useOrgs } from "@/data/load-data";
import { computeOpenStatus } from "@/lib/open-status";
import { ShoppingBasket, Soup, Baby, Menu, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useT } from "@/i18n/useT";
import { LangSwitcher } from "@/components/LangSwitcher";
import { useFirstMount } from "@/lib/use-first-mount";
import type { ServiceType } from "@/types";

const ease = [0.22, 1, 0.36, 1] as const;

type QuickAction = {
  v: "sage" | "mustard" | "terracotta";
  icon: LucideIcon;
  tKey: string;
  services: ServiceType[];
  accent: string;
  orb: string;
  transform: string;
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    v: "sage",
    icon: ShoppingBasket,
    tKey: "home.chip.groceries",
    services: ["food_pantry", "mobile_pantry"],
    accent: "#4F7F6A",
    orb: "radial-gradient(circle at 35% 30%, rgba(255,255,255,0.96), rgba(232,245,238,0.82) 42%, rgba(79,127,106,0.22) 72%, rgba(79,127,106,0.1) 100%)",
    transform: "translate(14px, 0px) rotate(-8deg)",
  },
  {
    v: "mustard",
    icon: Soup,
    tKey: "home.chip.hotMeals",
    services: ["hot_meals"],
    accent: "#A97A1D",
    orb: "radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95), rgba(255,245,215,0.82) 42%, rgba(217,164,65,0.24) 72%, rgba(217,164,65,0.1) 100%)",
    transform: "translate(88px, 110px) rotate(10deg)",
  },
  {
    v: "terracotta",
    icon: Baby,
    tKey: "home.chip.babySupplies",
    services: ["food_pantry", "baby_supplies"],
    accent: "#C96F4A",
    orb: "radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95), rgba(255,235,228,0.82) 42%, rgba(201,111,74,0.22) 72%, rgba(201,111,74,0.1) 100%)",
    transform: "translate(12px, 220px) rotate(-12deg)",
  },
];

export default function Home() {
  const navigate = useNavigate();
  const setIntent = useLocationStore((s) => s.setIntent);
  const setLanguage = useLocationStore((s) => s.setLanguage);
  const currentLang = useLocationStore((s) => s.language);
  const [menuOpen, setMenuOpen] = useState(false);
  const t = useT();

  const first = useFirstMount("home");
  const skip = !first; // skip entrance animations on return visits
  const d = (delay: number) => skip ? 0 : delay;
  const dur = (duration: number) => skip ? 0.15 : duration;

  const afterLocation = () => {
    setIntent(null);
    navigate("/find");
  };

  const goToIntent = (services: ServiceType[]) => {
    setIntent({ type: "service", services });
    navigate("/find");
  };

  return (
    <main className="relative h-screen overflow-hidden" style={{ background: "#EDE8E0" }}>
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 60% 50% at 5% 20%, rgba(79,140,110,0.25) 0%, transparent 55%),
            radial-gradient(ellipse 50% 45% at 85% 10%, rgba(175,155,210,0.18) 0%, transparent 50%),
            radial-gradient(ellipse 45% 40% at 75% 85%, rgba(225,175,80,0.15) 0%, transparent 50%),
            radial-gradient(ellipse 40% 35% at 95% 50%, rgba(140,120,190,0.12) 0%, transparent 45%),
            radial-gradient(ellipse 50% 45% at 50% 5%, rgba(240,210,170,0.2) 0%, transparent 50%)
          `,
        }}
      />
      <FloatingOrbs />

      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none opacity-[0.035]"
        style={{
          backgroundImage:
            'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.85\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'1\'/%3E%3C/svg%3E")',
          backgroundSize: "200px",
        }}
      />

      <div className="relative z-10 h-full flex flex-col">
        <motion.nav
          initial={skip ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: dur(0.5) }}
          className="px-4 sm:px-6 lg:px-10 pt-4 sm:pt-6 flex items-center justify-between"
        >
          <div className="flex items-center gap-2.5">
            <img src={`${import.meta.env.BASE_URL}logos/nutrire-mark.png`} alt="Nutrire" className="h-9 w-9" />
            <span className="font-display text-[22px] font-bold text-ink tracking-tight">Nutrire</span>
          </div>

          <div className="hidden sm:flex items-center gap-1">
            {[
              { key: "nav.give", to: "/give" },
              { key: "nav.equityMap", to: "/map" },
              { key: "nav.research", to: "/methodology" },
              { key: "nav.volunteer", to: "/give/volunteer" },
            ].map((item) => (
              <motion.button
                key={item.key}
                onClick={() => navigate(item.to)}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.97 }}
                className="px-3 py-1.5 rounded-lg text-[12px] text-ink-soft hover:text-ink hover:bg-white/40 transition-colors"
              >
                {t(item.key)}
              </motion.button>
            ))}
            <div className="mx-1.5 h-4 w-px bg-ink/8" />
            <LangSwitcher current={currentLang} onChange={(l) => setLanguage(l)} />
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="sm:hidden h-10 w-10 rounded-xl bg-white/30 backdrop-blur-xl border border-white/40 flex items-center justify-center text-ink-soft"
            aria-label="Menu"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </motion.nav>

        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="sm:hidden absolute inset-x-0 top-[60px] z-50 mx-4 rounded-2xl bg-white/60 backdrop-blur-2xl border border-white/50 shadow-[0_8px_32px_rgba(0,0,0,0.1)] p-4 flex flex-col gap-1"
            >
              {[
                { key: "nav.give", to: "/give" },
                { key: "nav.equityMap", to: "/map" },
                { key: "nav.research", to: "/methodology" },
                { key: "nav.volunteer", to: "/give/volunteer" },
              ].map((item) => (
                <button
                  key={item.key}
                  onClick={() => {
                    navigate(item.to);
                    setMenuOpen(false);
                  }}
                  className="w-full text-left px-4 py-3 rounded-xl text-[14px] font-medium text-ink hover:bg-white/50 transition-colors"
                >
                  {t(item.key)}
                </button>
              ))}
              <div className="mt-1 pt-2 border-t border-white/30 px-4">
                <LangSwitcher
                  current={currentLang}
                  onChange={(l) => {
                    setLanguage(l);
                    setMenuOpen(false);
                  }}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <section className="relative flex-1 h-[calc(100dvh-84px)] overflow-hidden px-4 sm:px-6 lg:px-12 pt-4 pb-5 lg:pt-2 lg:pb-4">
          <div className="mx-auto h-full w-full max-w-[1380px] xl:grid xl:grid-cols-[170px_minmax(0,1fr)] xl:gap-6 xl:items-center">
            <QuickSearchSculpture actions={QUICK_ACTIONS} onSelect={goToIntent} />

            <div className="mx-auto w-full max-w-[980px] text-center flex flex-col items-center justify-center h-full">
              <motion.div initial={skip ? false : { opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: dur(1), delay: d(0.1), ease }}>
                <h1 className="font-display font-bold text-ink leading-[0.92] tracking-[-0.035em] text-[clamp(38px,7.5vw,74px)]">
                  {t("home.heroLine1")}{"\n"}
                  <span className="sm:inline block">{t("home.heroLine2")}</span>
                  <motion.span
                    initial={skip ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: dur(0.7), delay: d(0.45), ease }}
                    className="block text-sage-deep"
                  >
                    <span className="relative">
                      {t("home.nearYou")}.
                      <motion.span
                        aria-hidden="true"
                        initial={skip ? false : { scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        transition={{ duration: dur(0.8), delay: d(1), ease }}
                        style={{ transformOrigin: "left" }}
                        className="absolute inset-x-[-3px] -bottom-1 h-[5px] bg-sage/12 -z-10 rounded-full"
                      />
                    </span>
                  </motion.span>
                </h1>
              </motion.div>

              <motion.div
                initial={skip ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: dur(0.5), delay: d(0.6), ease }}
                className="mt-4 h-6 overflow-hidden"
              >
                <RotatingTagline />
              </motion.div>

              <motion.div
                initial={skip ? false : { opacity: 0, y: 14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: dur(0.7), delay: d(0.6), ease }}
                className="mt-6 w-full max-w-xl mx-auto"
              >
                <LocationInput onSubmit={afterLocation} autoFocus />
              </motion.div>

              <motion.div
                initial={skip ? "visible" : "hidden"}
                animate="visible"
                variants={{ hidden: {}, visible: { transition: { staggerChildren: skip ? 0 : 0.06, delayChildren: skip ? 0 : 0.85 } } }}
                className="mt-3 flex flex-wrap justify-center gap-2.5 lg:hidden"
              >
                {QUICK_ACTIONS.map((action) => {
                  const Icon = action.icon;
                  return (
                    <motion.div key={action.tKey} variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease } } }}>
                      <Chip variant={action.v} onClick={() => goToIntent(action.services)} icon={<Icon size={15} />}>
                        {t(action.tKey)}
                      </Chip>
                    </motion.div>
                  );
                })}
              </motion.div>

              <TrendingStrip />

              <CredentialBadges />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

const QUICK_EMOJIS = ["\uD83E\uDD66", "\uD83C\uDF72", "\uD83C\uDF7C"];

function QuickSearchSculpture({
  actions,
  onSelect,
}: {
  actions: QuickAction[];
  onSelect: (services: ServiceType[]) => void;
}) {
  const t = useT();

  return (
    <motion.aside
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.7, delay: 0.5, ease }}
      className="hidden xl:flex flex-col gap-3 w-[160px] self-center"
      aria-label="Quick search"
    >
      {actions.map((action, i) => (
        <motion.button
          key={action.tKey}
          type="button"
          onClick={() => onSelect(action.services)}
          whileHover={{ scale: 1.05, x: 3 }}
          whileTap={{ scale: 0.96 }}
          className="group relative flex items-center gap-3 px-4 py-3 rounded-2xl border border-white/50 backdrop-blur-2xl transition-all overflow-hidden"
          style={{
            background: "linear-gradient(135deg, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.22) 100%)",
            boxShadow: `
              0 1px 0 0 rgba(255,255,255,0.6) inset,
              0 -1px 0 0 rgba(0,0,0,0.03) inset,
              0 8px 24px -4px rgba(0,0,0,0.07),
              0 2px 6px -1px rgba(0,0,0,0.04)
            `,
          }}
          aria-label={t(action.tKey)}
        >
          <div
            aria-hidden="true"
            className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
            style={{ background: "linear-gradient(135deg, rgba(255,255,255,0.15), transparent 60%)" }}
          />
          <div
            className="relative flex items-center justify-center w-9 h-9 rounded-xl"
            style={{
              background: "linear-gradient(145deg, rgba(255,255,255,0.7), rgba(255,255,255,0.3))",
              boxShadow: "0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.8)",
            }}
          >
            <span className="text-[20px] leading-none select-none">{QUICK_EMOJIS[i]}</span>
          </div>
          <span className="relative text-[12px] font-semibold text-ink/60 group-hover:text-ink/80 transition-colors">
            {t(action.tKey)}
          </span>
        </motion.button>
      ))}
    </motion.aside>
  );
}

function TrendingStrip() {
  const navigate = useNavigate();
  const orgs = useOrgs();
  const t = useT();
  const now = new Date();

  const trending = useMemo(() => {
    return orgs
      .filter((o) => o.lat && o.lon && o.ai?.heroCopy)
      .map((o) => ({ org: o, status: computeOpenStatus(o, now) }))
      .filter((r) => r.status.state === "open" || r.status.state === "opens_today")
      .sort((a, b) => b.org.reliability.score - a.org.reliability.score)
      .slice(0, 4);
  }, [orgs]);

  if (trending.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 1, ease }}
      className="mt-5 xl:mt-6 mx-auto w-full max-w-[980px]"
    >
      <div className="rounded-[30px] border border-white/45 bg-white/22 backdrop-blur-2xl px-4 sm:px-5 py-4 xl:py-3.5 shadow-[0_20px_60px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.55)]">
        <div className="flex items-center justify-between gap-3">
          <div className="text-left">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted/55">{t("home.trending")}</p>
            <p className="mt-1 text-[13px] text-ink/58">Open now or opening soon nearby.</p>
          </div>
        </div>

        <div className="mt-4 flex gap-2.5 overflow-x-auto pb-1 snap-x snap-mandatory scrollbar-none xl:grid xl:grid-cols-4 xl:gap-3 xl:overflow-visible">
          {trending.map(({ org, status }) => (
            <motion.button
              key={org.id}
              onClick={() => navigate(`/org/${org.id}`)}
              whileHover={{ y: -2, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="snap-start shrink-0 min-w-[180px] sm:min-w-[200px] xl:min-w-0 rounded-[24px] border border-white/45 bg-white/28 px-4 py-3 xl:py-2.5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] hover:bg-white/40 transition-all"
            >
              <div className="flex items-center gap-2">
                {status.state === "open" ? (
                  <span className="relative flex h-2 w-2 shrink-0">
                    <span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" />
                    <span className="relative h-2 w-2 rounded-full bg-sage" />
                  </span>
                ) : (
                  <span className="h-2 w-2 rounded-full bg-mustard shrink-0" />
                )}
                <span className="text-[11px] font-medium text-ink/50">{status.state === "open" ? t("home.openNow") : t("home.openingSoon")}</span>
              </div>
              <p className="mt-2 text-[14px] font-semibold text-ink leading-snug">{org.name}</p>
              <p className="mt-1 text-[12px] text-ink/55 truncate">{status.label}</p>
            </motion.button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

const TAGLINES = [
  { text: "1,400+ verified resources across DC \u00b7 MD \u00b7 VA", lang: "en" },
  { text: "1,400+ recursos verificados en DC \u00b7 MD \u00b7 VA", lang: "es" },
  { text: "1,400+ \u12E8\u1270\u1228\u130B\u1308\u1321 \u121D\u1295\u132E\u127D \u1260 DC \u00b7 MD \u00b7 VA", lang: "am" },
  { text: "1 400+ ressources v\u00e9rifi\u00e9es \u00e0 DC \u00b7 MD \u00b7 VA", lang: "fr" },
  { text: "1,400+ ngu\u1ED3n l\u1EF1c \u0111\u00e3 x\u00e1c minh t\u1EA1i DC \u00b7 MD \u00b7 VA", lang: "vi" },
];

function RotatingTagline() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % TAGLINES.length), 3200);
    return () => clearInterval(timer);
  }, []);

  return (
    <span className="relative inline-flex items-center gap-2.5">
      <span className="relative flex h-[6px] w-[6px] shrink-0">
        <span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" />
        <span className="relative h-[6px] w-[6px] rounded-full bg-sage" />
      </span>
      <AnimatePresence mode="wait">
        <motion.span
          key={TAGLINES[index].lang}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -14 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="text-[13px] sm:text-[14px] text-ink/50 font-medium"
        >
          {TAGLINES[index].text}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

function CredentialBadges() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8, delay: 1.5, ease: [0.22, 1, 0.36, 1] }}
      className="mt-5 xl:mt-6 flex items-center justify-center gap-1.5 text-[11px] font-medium text-ink/35"
    >
      <img src={`${import.meta.env.BASE_URL}logos/nutrire-mark.png`} alt="" className="w-4 h-4 opacity-50" />
      <span>A NourishNet Data Challenge project</span>
      <span className="text-ink/15 mx-0.5">·</span>
      <span>University of Maryland</span>
      <span className="text-ink/15 mx-0.5">·</span>
      <span>NSF Funded</span>
    </motion.div>
  );
}

function FloatingOrbs() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[
        { size: "clamp(150px, 25vw, 300px)", x: "10%", y: "20%", color: "rgba(79,140,110,0.12)", duration: 20, delay: 0 },
        { size: "clamp(120px, 20vw, 250px)", x: "75%", y: "15%", color: "rgba(175,155,210,0.1)", duration: 25, delay: 2 },
        { size: "clamp(100px, 18vw, 200px)", x: "60%", y: "70%", color: "rgba(225,175,80,0.08)", duration: 22, delay: 4 },
        { size: "clamp(90px, 15vw, 180px)", x: "25%", y: "75%", color: "rgba(140,120,190,0.07)", duration: 28, delay: 1 },
        { size: "clamp(170px, 28vw, 350px)", x: "50%", y: "40%", color: "rgba(240,230,210,0.15)", duration: 30, delay: 3 },
      ].map((orb, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: orb.size,
            height: orb.size,
            aspectRatio: "1",
            left: orb.x,
            top: orb.y,
            background: `radial-gradient(circle, ${orb.color} 0%, transparent 70%)`,
            filter: "blur(40px)",
          }}
          animate={{
            x: [0, 30, -20, 10, 0],
            y: [0, -20, 15, -10, 0],
            scale: [1, 1.05, 0.95, 1.02, 1],
          }}
          transition={{
            duration: orb.duration,
            repeat: Infinity,
            ease: "easeInOut",
            delay: orb.delay,
          }}
        />
      ))}
    </div>
  );
}

