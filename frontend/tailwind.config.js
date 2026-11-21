/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0A0A0A",
          panel: "#121212",
          panel2: "#181818",
          hover: "#1C1C1C",
        },
        line: {
          DEFAULT: "#1F1F1F",
          strong: "#2A2A2A",
        },
        fg: {
          primary: "#FAFAFA",
          secondary: "#A1A1AA",
          muted: "#71717A",
          dim: "#52525B",
        },
        accent: {
          long: "#4ADE80",
          short: "#F43F5E",
          neutral: "#FBBF24",
          info: "#60A5FA",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        DEFAULT: "4px",
        md: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};
