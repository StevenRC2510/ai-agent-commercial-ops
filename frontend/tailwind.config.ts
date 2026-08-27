import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: token("canvas"),
        surface: {
          DEFAULT: token("surface"),
          raised: token("surface-raised"),
          sunken: token("surface-sunken"),
        },
        line: { DEFAULT: token("line"), strong: token("line-strong") },
        ink: { DEFAULT: token("ink"), muted: token("ink-muted"), subtle: token("ink-subtle") },
        accent: {
          DEFAULT: token("accent"),
          hover: token("accent-hover"),
          fg: token("accent-fg"),
          soft: token("accent-soft"),
        },
        attention: {
          DEFAULT: token("attention"),
          soft: token("attention-soft"),
          line: token("attention-line"),
        },
        positive: token("positive"),
        danger: token("danger"),
      },
      keyframes: {
        enter: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        lift: {
          from: { opacity: "0", transform: "translateY(12px) scale(0.99)" },
          to: { opacity: "1", transform: "none" },
        },
        wave: {
          "0%, 60%, 100%": { transform: "none", opacity: "0.45" },
          "30%": { transform: "translateY(-3px)", opacity: "1" },
        },
      },
      animation: {
        enter: "enter 220ms cubic-bezier(0.22, 1, 0.36, 1) both",
        lift: "lift 240ms cubic-bezier(0.22, 1, 0.36, 1) both",
        wave: "wave 1200ms ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
