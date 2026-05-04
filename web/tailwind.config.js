/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Raven design system
        ink:       '#0D0F0E',
        'ink-mid': '#2A2E2C',
        surface:   '#F5F0E8',
        'surface-2': '#EDE8DF',
        border:    '#D8D2C6',
        gold:      '#C9A84C',
        'gold-light': '#E2C97E',
        teal:      '#2A7C6F',
        'teal-light': '#3AA896',
        red:       '#C0392B',
        'red-light': '#E74C3C',
        amber:     '#E67E22',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
    },
  },
  plugins: [],
}
