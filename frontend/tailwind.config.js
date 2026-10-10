/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark Intelligence Foundation
        'navy': {
          50: '#0f172a',
          100: '#0a0e27',
          200: '#0b1028',
          300: '#080d22',
          400: '#101733',
          500: '#1e293b',
          600: '#334155',
          700: '#475569',
          800: '#64748b',
          900: '#94a3b8',
          950: '#f8fafc',
        },
        // Functional Accents
        'emerald': '#34D399',
        'cyan': '#22D3EE',
        'amber': '#FBBF24',
        'red': '#F87171',
        'indigo': '#667EEA',
        'purple': '#764BA2',
      },
      backgroundImage: {
        'grid-pattern': "url(\"data:image/svg+xml,%3Csvg width='48' height='48' viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%2394A3B8' fill-opacity='0.08'%3E%3Cpath d='M0 0h48v48H0z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        'noise-pattern': "url(\"data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23noiseFilter)'/%3E%3C/svg%3E\")",
      }
    }
  },
  plugins: [],
}
