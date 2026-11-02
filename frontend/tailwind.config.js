/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["Charter", "Bitstream Charter", "Iowan Old Style", "Sitka Text", "Cambria", "Georgia", "serif"],
      },
      colors: {
        buy: { DEFAULT: "#1e6b4f", dark: "#4fb38a" },
        abstain: { DEFAULT: "#a86a12", dark: "#e0a346" },
        marker: { DEFAULT: "#f5d547", dark: "#8a7418" },
      },
    },
  },
  plugins: [],
};
