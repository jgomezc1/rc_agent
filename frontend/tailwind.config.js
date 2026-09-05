/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: "#1e40af",
          dark: "#0f172a",
          accent: "#3b82f6",
        }
      }
    },
  },
  plugins: [require("@tailwindcss/typography")],
}
