import type { Config } from "tailwindcss";

/**
 * Design tokens ported from the original Streamlit shell (ui/shell.py):
 * IBM Plex Sans + IBM Plex Mono, a cyan accent, and a cool slate palette.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#0891b2",
          strong: "#0e7490",
          soft: "#ecfeff",
          line: "#a5f3fc",
        },
        bg: "#f6f8fb",
        surface: {
          DEFAULT: "#ffffff",
          alt: "#f4f7fb",
          2: "#eef2f7",
        },
        line: {
          DEFAULT: "#dde3ec",
          soft: "#e8edf4",
        },
        ink: {
          DEFAULT: "#1e2a3a",
          muted: "#4f6480",
          faint: "#7e92a8",
        },
        flag: {
          DEFAULT: "#d97706",
          soft: "#fffbeb",
          line: "#fde68a",
          text: "#b45309",
        },
        danger: {
          DEFAULT: "#dc2626",
          soft: "#fef2f2",
          line: "#fca5a5",
          text: "#b91c1c",
        },
        ok: {
          DEFAULT: "#16a34a",
          soft: "#f0fdf4",
          line: "#86efac",
          text: "#15803d",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        sm: "0 1px 2px rgba(79,100,128,.06),0 1px 1px rgba(79,100,128,.04)",
        md: "0 4px 14px rgba(50,70,100,.08),0 1px 3px rgba(50,70,100,.05)",
        lg: "0 18px 48px rgba(40,60,90,.14)",
      },
      borderRadius: {
        xl: "14px",
        "2xl": "18px",
      },
      keyframes: {
        scanSweep: {
          "0%": { top: "0", opacity: "0.9" },
          "100%": { top: "calc(100% - 2px)", opacity: "0.15" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
      },
      animation: {
        scanSweep: "scanSweep 1.2s ease-in-out infinite alternate",
        fadeIn: "fadeIn 0.25s ease-out both",
        shimmer: "shimmer 1.4s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
