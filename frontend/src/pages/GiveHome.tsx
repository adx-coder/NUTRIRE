import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowUpRight, HandCoins, Clock3 } from "lucide-react";
import { GlassBackdrop, GLASS_BG } from "@/components/GlassBackdrop";

const ease = [0.22, 1, 0.36, 1] as const;

export default function GiveHome() {
  const navigate = useNavigate();

  return (
    <main className="min-h-screen relative overflow-hidden" style={{ background: GLASS_BG }}>
      <GlassBackdrop />
      <div className="relative z-10">
        <motion.nav initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
          className="px-5 lg:px-10 pt-5">
          <button onClick={() => navigate("/")}
            className="h-9 px-3 rounded-lg text-[12px] font-medium text-ink-muted hover:text-ink hover:bg-white/40 transition-colors inline-flex items-center gap-1.5">
            <ArrowLeft size={14} /> Back
          </button>
        </motion.nav>

        <div className="max-w-2xl mx-auto px-5 lg:px-10 pt-14 lg:pt-20 pb-20 text-center">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sage-deep/50">Thanks for showing up</p>
            <h1 className="mt-3 font-display font-bold text-ink tracking-[-0.02em] text-[clamp(32px,6vw,52px)] leading-tight">
              Where you'll matter most
            </h1>
            <p className="mt-3 text-[15px] text-ink/55 max-w-md mx-auto">
              Your help closes the gap where the need is biggest.
            </p>
          </motion.div>

          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg mx-auto">
            <motion.button onClick={() => navigate("/give/donate")}
              initial={{ opacity: 0, y: 14, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.5, delay: 0.2, ease }}
              whileHover={{ y: -3, scale: 1.01 }} whileTap={{ scale: 0.98 }}
              className="group rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 p-6 text-left shadow-[0_4px_16px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,0.5)] hover:bg-white/40 hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)] transition-all"
              style={{ background: "linear-gradient(135deg, rgba(79,140,110,0.12), rgba(255,255,255,0.3))" }}>
              <div className="h-10 w-10 rounded-xl bg-sage/10 flex items-center justify-center">
                <HandCoins size={20} className="text-sage-deep" />
              </div>
              <h2 className="mt-4 font-display text-[18px] font-semibold text-ink">Give food or money</h2>
              <p className="mt-1.5 text-[12px] text-ink/55 leading-relaxed">Drop off groceries or give directly to orgs serving your neighborhood.</p>
              <div className="mt-4 inline-flex items-center gap-1 text-[12px] font-semibold text-sage-deep">
                Donate <ArrowUpRight size={13} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </div>
            </motion.button>

            <motion.button onClick={() => navigate("/give/volunteer")}
              initial={{ opacity: 0, y: 14, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.5, delay: 0.3, ease }}
              whileHover={{ y: -3, scale: 1.01 }} whileTap={{ scale: 0.98 }}
              className="group rounded-2xl bg-white/30 backdrop-blur-2xl border border-white/40 p-6 text-left shadow-[0_4px_16px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,0.5)] hover:bg-white/40 hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)] transition-all"
              style={{ background: "linear-gradient(135deg, rgba(175,155,210,0.08), rgba(255,255,255,0.3))" }}>
              <div className="h-10 w-10 rounded-xl bg-ink/5 flex items-center justify-center">
                <Clock3 size={20} className="text-ink-soft" />
              </div>
              <h2 className="mt-4 font-display text-[18px] font-semibold text-ink">Give time</h2>
              <p className="mt-1.5 text-[12px] text-ink/55 leading-relaxed">Pick a shift this week. Sorting, driving, translating, greeting.</p>
              <div className="mt-4 inline-flex items-center gap-1 text-[12px] font-semibold text-ink-soft group-hover:text-ink">
                Volunteer <ArrowUpRight size={13} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </div>
            </motion.button>
          </div>
        </div>
      </div>
    </main>
  );
}
