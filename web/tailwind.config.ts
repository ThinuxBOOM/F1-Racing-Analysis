import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0b0f", panel: "#13131a", panel2: "#1a1a23", line: "#262633",
        ink: "#e8e8ee", mute: "#8a8a99", accent: "#e10600", ok: "#3fb27f", warn: "#e0a43a", info: "#4aa3ff",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
export default config;
