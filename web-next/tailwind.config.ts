import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Zomato-ish palette derived from the design mocks.
        brand: {
          50:  "#fff5f5",
          100: "#ffe1e1",
          200: "#ffc5c5",
          400: "#f76b6b",
          500: "#e23744",   // primary
          600: "#cb202d",
          700: "#a01821",
        },
        ink: {
          900: "#1f2937",
          700: "#374151",
          500: "#6b7280",
          300: "#d1d5db",
        },
        cream: "#fff8f5",
        whyBg: "#fdecec",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
      },
      borderRadius: {
        "2xl": "1rem",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
