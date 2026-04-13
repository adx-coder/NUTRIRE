/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-raised": "var(--bg-raised)",
        "bg-muted": "var(--bg-muted)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        "ink-muted": "var(--ink-muted)",
        "ink-disabled": "var(--ink-disabled)",
        sage: "var(--sage)",
        "sage-deep": "var(--sage-deep)",
        "sage-soft": "var(--sage-soft)",
        terracotta: "var(--terracotta)",
        "terracotta-soft": "var(--terracotta-soft)",
        mustard: "var(--mustard)",
        "mustard-soft": "var(--mustard-soft)",
        stone: "var(--stone)",
        "stone-soft": "var(--stone-soft)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter Tight", "Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["13px", { lineHeight: "1.5" }],
        sm: ["15px", { lineHeight: "1.55" }],
        base: ["17px", { lineHeight: "1.6" }],
        md: ["19px", { lineHeight: "1.5" }],
        lg: ["24px", { lineHeight: "1.3" }],
        xl: ["32px", { lineHeight: "1.2" }],
        hero: ["44px", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
      },
      spacing: {
        "4.5": "18px",
        "5.5": "22px",
        "13": "52px",
        "15": "60px",
        "18": "72px",
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "24px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(31, 36, 33, 0.04), 0 8px 24px -12px rgba(31, 36, 33, 0.08)",
        hero: "0 4px 8px rgba(31, 36, 33, 0.06), 0 24px 56px -24px rgba(31, 36, 33, 0.14)",
      },
      maxWidth: {
        reading: "680px",
        card: "480px",
      },
      transitionTimingFunction: {
        dignity: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 360ms cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
