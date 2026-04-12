import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2937",
        sand: "#f3efe6",
        accent: "#c96f3b",
      },
    },
  },
  plugins: [],
};

export default config;
