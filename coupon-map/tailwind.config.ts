import type { Config } from "tailwindcss";
import { heroui } from "@heroui/react";

// Newspaper palette inherited from the archived admin panel.
// Main color = forest green (#1B5740). All UI uses these CSS-var-backed tokens.
const palette = {
  bg: "#F4F3EF",
  paper: "#ECEAE4",
  white: "#FAFAF7",
  ink: "#000000",
  "ink-2": "#1A1917",
  "ink-3": "#4A4845",
  g: "#1B5740",
  "g-2": "#2A7055",
  "g-light": "#C4DDCF",
  "g-pale": "#EAF1EE",
  au: "#8C6018",
  "au-pale": "#F4EFE8",
  or: "#D97706",
  "or-pale": "#FDF1E2",
  rd: "#8C2A1E",
  "rd-pale": "#F4EAE9",
  rule: "#D0CEC6",
  "rule-strong": "#B5B2A8",
};

export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "./node_modules/@heroui/theme/dist/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: palette,
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "PingFang SC",
          "Microsoft YaHei",
          "sans-serif",
        ],
      },
    },
  },
  darkMode: "class",
  plugins: [
    heroui({
      themes: {
        light: {
          colors: {
            background: palette.bg,
            foreground: palette["ink-2"],
            primary: {
              50: palette["g-pale"],
              100: palette["g-light"],
              500: palette.g,
              600: palette["g-2"],
              DEFAULT: palette.g,
              foreground: palette.white,
            },
            warning: { DEFAULT: palette.or, foreground: palette.white },
            danger: { DEFAULT: palette.rd, foreground: palette.white },
          },
        },
      },
    }),
  ],
} satisfies Config;
