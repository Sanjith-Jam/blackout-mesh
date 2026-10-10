/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        vintage: 'var(--bg-vintage)',
        'brand-forest': 'var(--brand-forest)',
        'brand-earth': 'var(--brand-earth)',
        'brand-sand': 'var(--brand-sand)',
        'brand-sand-dark': 'var(--brand-sand-dark)',
      }
    },
  },
  plugins: [],
}
