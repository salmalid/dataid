import type { Config } from "tailwindcss";

/**
 * Two colour systems live here and must not be mixed:
 *  - `brand` / `ink` / `surface` — UI chrome, gradients, glass. Never encodes a data value.
 *  - `series` / `status` — the validated data-viz palette. Only ever used inside charts.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        violet: {
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
        },
        surface: {
          0: "#ffffff",
          50: "#fafafa",
          100: "#f4f4f5",
          800: "#141417",
          850: "#0f0f12",
          900: "#0a0a0c",
          950: "#050506",
        },
        series: {
          1: "#2a78d6",
          2: "#eb6834",
          3: "#1baf7a",
          4: "#eda100",
          5: "#e87ba4",
          6: "#008300",
          7: "#4a3aa7",
          8: "#e34948",
        },
        status: {
          good: "#0ca30c",
          warning: "#fab219",
          serious: "#ec835a",
          critical: "#d03b3b",
        },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        "4xl": "2rem",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg,#6366f1 0%,#8b5cf6 45%,#ec4899 100%)",
        "mesh": "radial-gradient(at 12% 8%, rgba(99,102,241,0.28) 0px, transparent 55%), radial-gradient(at 85% 12%, rgba(139,92,246,0.22) 0px, transparent 50%), radial-gradient(at 55% 92%, rgba(236,72,153,0.16) 0px, transparent 55%)",
        "grid-light": "linear-gradient(rgba(15,15,20,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(15,15,20,0.05) 1px, transparent 1px)",
        "grid-dark": "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(99,102,241,0.20), 0 18px 48px -12px rgba(99,102,241,0.42)",
        card: "0 1px 2px rgba(9,9,11,0.05), 0 8px 28px -12px rgba(9,9,11,0.14)",
        "card-dark": "0 1px 2px rgba(0,0,0,0.5), 0 12px 36px -16px rgba(0,0,0,0.75)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.85)", opacity: "0.7" },
          "80%,100%": { transform: "scale(1.6)", opacity: "0" },
        },
        drift: {
          "0%,100%": { transform: "translate3d(0,0,0)" },
          "50%": { transform: "translate3d(24px,-30px,0)" },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.55s cubic-bezier(0.22,1,0.36,1) both",
        shimmer: "shimmer 1.8s infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.24,0,0.38,1) infinite",
        drift: "drift 18s ease-in-out infinite",
        marquee: "marquee 38s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
