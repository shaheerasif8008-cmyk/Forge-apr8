import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        paper: "#f4efe8",
        accent: "#b3541e",
        moss: "#4a5c43",
        gold: "#d1a84a",
      },
      fontFamily: {
        display: ["Georgia", "Times New Roman", "serif"],
        body: ["ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 12px 32px rgba(23, 32, 51, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
