import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LocationInput } from "@/components/LocationInput";
import { Chip } from "@/components/Chip";
import { useLocationStore } from "@/store/location";
import { useOrgs } from "@/data/load-data";
import { computeOpenStatus } from "@/lib/open-status";
import { ShoppingBasket, Soup, Baby } from "lucide-react";

const ease = [0.22, 1, 0.36, 1] as const;

export default function Home() {
  const navigate = useNavigate();
  const setIntent = useLocationStore((s) => s.setIntent);
  const afterLocation = () => { setIntent(null); navigate("/find"); };

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: "#EDE8E0" }}>
      {/* Rich backdrop */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 50% at 5% 20%, rgba(79,140,110,0.25) 0%, transparent 55%),
          radial-gradient(ellipse 50% 45% at 85% 10%, rgba(175,155,210,0.18) 0%, transparent 50%),
          radial-gradient(ellipse 45% 40% at 75% 85%, rgba(225,175,80,0.15) 0%, transparent 50%),
          radial-gradient(ellipse 40% 35% at 95% 50%, rgba(140,120,190,0.12) 0%, transparent 45%),
          radial-gradient(ellipse 50% 45% at 50% 5%, rgba(240,210,170,0.2) 0%, transparent 50%)
        `,
      }} />
      {/* Floating glass orbs */}
      <FloatingOrbs />

      <div aria-hidden="true" className="fixed inset-0 pointer-events-none opacity-[0.035]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
        backgroundSize: "200px",
      }} />

      <div className="relative z-10">
        {/* Nav */}
        <motion.nav initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
          className="px-6 lg:px-10 pt-6 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <LogoMark />
            <span className="font-display text-lg font-bold text-ink tracking-tight">Nutrire</span>
          </div>
          <div className="hidden sm:flex items-center gap-1">
            {[{ label: "Give", to: "/give" }, { label: "Equity Map", to: "/map" }, { label: "Research", to: "/methodology" }, { label: "Volunteer", to: "/give/volunteer" }].map((item) => (
              <motion.button key={item.label} onClick={() => navigate(item.to)} whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }}
                className="px-3 py-1.5 rounded-lg text-[12px] text-ink-soft hover:text-ink hover:bg-white/40 transition-colors">{item.label}</motion.button>
            ))}
            <div className="mx-1.5 h-4 w-px bg-ink/8" />
            <div className="flex gap-0.5 text-[10px] font-medium text-ink-muted">
              <button className="px-1.5 py-1 rounded hover:text-ink hover:bg-white/30">EN</button>
              <button className="px-1.5 py-1 rounded hover:text-ink hover:bg-white/30">ES</button>
              <button className="px-1.5 py-1 rounded hover:text-ink hover:bg-white/30">አማ</button>
            </div>
          </div>
        </motion.nav>

        {/* ══════════════════════════════════════════════════
            HERO — full viewport, centered, immersive
            ══════════════════════════════════════════════════ */}
        <section className="h-[calc(100dvh-56px)] flex flex-col justify-between items-center px-6 lg:px-12 text-center pt-[8vh]">
          <div /> {/* spacer */}
          <div className="w-full max-w-4xl">
            {/* Headline — MASSIVE, fills the space */}
            <motion.div initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.1, ease }}>
              <h1 className="font-display font-bold text-ink leading-[0.92] tracking-[-0.04em] text-[clamp(56px,12vw,120px)]">
                <span className="relative inline-block">
                  <RotatingMeals />
                  <motion.span aria-hidden="true" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.8, delay: 0.9, ease }} style={{ transformOrigin: "left" }}
                    className="absolute inset-x-0 -bottom-1 h-3 bg-sage/6 -z-10 rounded-full" />
                </span>
              </h1>
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6, delay: 0.6, ease }}
                className="mt-2 font-display text-[clamp(24px,5vw,48px)] font-bold text-sage-deep tracking-[-0.02em]">
                near you
              </motion.p>
            </motion.div>

            {/* Tagline — glass pill, not plain text */}
            <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.6, delay: 0.5, ease }}
              className="mt-6 inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-white/30 backdrop-blur-2xl border border-white/40 shadow-[0_2px_12px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,0.6)]">
              <span className="relative flex h-2 w-2"><span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-50" /><span className="relative h-2 w-2 rounded-full bg-sage" /></span>
              <span className="text-[14px] text-ink/60 font-medium">1,400+ verified resources across DC · MD · VA</span>
            </motion.div>

            {/* Input */}
            <motion.div initial={{ opacity: 0, y: 14, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.7, delay: 0.6, ease }}
              className="mt-8 w-full max-w-xl mx-auto">
              <LocationInput onSubmit={afterLocation} autoFocus />
            </motion.div>

            {/* Chips */}
            <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06, delayChildren: 0.85 } } }}
              className="mt-4 flex flex-wrap justify-center gap-2.5">
              {([
                { v: "sage" as const, icon: <ShoppingBasket size={15} />, label: "Groceries", services: ["food_pantry", "mobile_pantry"] as const },
                { v: "mustard" as const, icon: <Soup size={15} />, label: "Hot meals", services: ["hot_meals"] as const },
                { v: "terracotta" as const, icon: <Baby size={15} />, label: "Baby supplies", services: ["food_pantry"] as const },
              ] as const).map((c) => (
                <motion.div key={c.label} variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease } } }}>
                  <Chip variant={c.v} onClick={() => { setIntent({ type: "service", services: [...c.services] }); navigate("/find"); }} icon={c.icon}>{c.label}</Chip>
                </motion.div>
              ))}
            </motion.div>
          </div>

          {/* Bottom: trending pantries */}
          <TrendingStrip />
        </section>

      </div>
    </main>
  );
}

function TrendingStrip() {
  const navigate = useNavigate();
  const orgs = useOrgs();
  const now = new Date();

  // Get top 5 by reliability, that are open or opening today
  const trending = useMemo(() => {
    return orgs
      .filter((o) => o.lat && o.lon && o.ai?.heroCopy)
      .map((o) => ({ org: o, status: computeOpenStatus(o, now) }))
      .filter((r) => r.status.state === "open" || r.status.state === "opens_today")
      .sort((a, b) => b.org.reliability.score - a.org.reliability.score)
      .slice(0, 5);
  }, [orgs]);

  if (trending.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 1.1, ease }}
      className="w-full max-w-4xl pb-5"
    >
      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-muted/50 mb-2.5 text-center">Trending near you</p>
      <div className="flex gap-2 overflow-x-auto pb-1 justify-center flex-wrap">
        {trending.map(({ org, status }) => (
          <motion.button
            key={org.id}
            onClick={() => navigate(`/org/${org.id}`)}
            whileHover={{ y: -2, scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="shrink-0 flex items-center gap-2.5 px-3.5 py-2 rounded-full bg-white/25 backdrop-blur-xl border border-white/35 hover:bg-white/40 transition-all shadow-[inset_0_1px_0_rgba(255,255,255,0.4)] text-left group"
          >
            {status.state === "open" ? (
              <span className="relative flex h-1.5 w-1.5 shrink-0">
                <span className="absolute inset-0 rounded-full bg-sage animate-ping opacity-40" />
                <span className="relative h-1.5 w-1.5 rounded-full bg-sage" />
              </span>
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-mustard shrink-0" />
            )}
            <span className="text-[12px] font-medium text-ink/70 group-hover:text-ink truncate max-w-[140px]">{org.name}</span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}

// ── Sub ──

const MEALS_WORDS = [{ word: "Nutrients" }, { word: "Meals" }, { word: "Comidas" }, { word: "ምግብ" }, { word: "Repas" }, { word: "餐食" }, { word: "Bữa ăn" }, { word: "وجبات" }];

function RotatingMeals() {
  const [index, setIndex] = useState(0);
  useEffect(() => { const t = setInterval(() => setIndex((i) => (i + 1) % MEALS_WORDS.length), 2800); return () => clearInterval(t); }, []);
  return (
    <span className="relative inline-block">
      <span className="invisible">Nutrients</span>
      <AnimatePresence mode="wait">
        <motion.span key={MEALS_WORDS[index].word}
          initial={{ opacity: 0, filter: "blur(8px)" }}
          animate={{ opacity: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, filter: "blur(8px)" }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-0 flex items-center justify-center">
          {MEALS_WORDS[index].word}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

/** Floating glass orbs — drifting background elements */
function FloatingOrbs() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[
        { size: 300, x: "10%", y: "20%", color: "rgba(79,140,110,0.12)", duration: 20, delay: 0 },
        { size: 250, x: "75%", y: "15%", color: "rgba(175,155,210,0.1)", duration: 25, delay: 2 },
        { size: 200, x: "60%", y: "70%", color: "rgba(225,175,80,0.08)", duration: 22, delay: 4 },
        { size: 180, x: "25%", y: "75%", color: "rgba(140,120,190,0.07)", duration: 28, delay: 1 },
        { size: 350, x: "50%", y: "40%", color: "rgba(240,230,210,0.15)", duration: 30, delay: 3 },
      ].map((orb, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: orb.size, height: orb.size,
            left: orb.x, top: orb.y,
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

function LogoMark() {
  return (
    <motion.svg width="26" height="26" viewBox="0 0 28 28" fill="none" aria-hidden="true"
      initial={{ rotate: -8, scale: 0.85, opacity: 0 }} animate={{ rotate: 0, scale: 1, opacity: 1 }} transition={{ duration: 0.7, ease }}>
      <circle cx="14" cy="14" r="13" stroke="#4F7F6A" strokeWidth="1.5" />
      <motion.circle cx="14" cy="14" r="8" fill="#E8EFE9" animate={{ scale: [1, 1.04, 1] }} transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }} style={{ originX: "14px", originY: "14px" }} />
      <circle cx="14" cy="14" r="3.5" fill="#4F7F6A" />
      <motion.circle cx="21" cy="9" r="1.5" fill="#D9A441" animate={{ opacity: [0.7, 1, 0.7] }} transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }} />
    </motion.svg>
  );
}
