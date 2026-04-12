/** Shared warm glassmorphism backdrop — used on all pages */
export function GlassBackdrop() {
  return (
    <>
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 50% at 5% 20%, rgba(79,140,110,0.25) 0%, transparent 55%),
          radial-gradient(ellipse 50% 45% at 85% 10%, rgba(175,155,210,0.18) 0%, transparent 50%),
          radial-gradient(ellipse 45% 40% at 75% 85%, rgba(225,175,80,0.15) 0%, transparent 50%),
          radial-gradient(ellipse 40% 35% at 95% 50%, rgba(140,120,190,0.12) 0%, transparent 45%),
          radial-gradient(ellipse 50% 45% at 50% 5%, rgba(240,210,170,0.2) 0%, transparent 50%)
        `,
      }} />
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none opacity-[0.035]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
        backgroundSize: "200px",
      }} />
    </>
  );
}

export const GLASS_BG = "#EDE8E0";
