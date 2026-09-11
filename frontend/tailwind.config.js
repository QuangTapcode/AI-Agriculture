/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'DM Sans Variable'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        display: ["'Manrope Variable'", "'DM Sans Variable'", 'sans-serif'],
        mono: ["'JetBrains Mono'", 'Menlo', 'Monaco', 'Consolas', "'Courier New'", 'monospace'],
      },
      colors: {
        field: {
          ink: '#06110E',
          deep: '#0B1D16',
          moss: '#164C37',
          lime: '#BAFF59',
          mist: '#EFF9F2',
          canvas: '#F3F7F4',
        },
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        }
      },
      fontSize: {
        'xs':   ['0.75rem',  { lineHeight: '1.5' }],
        'sm':   ['0.875rem', { lineHeight: '1.6' }],
        'base': ['1rem',{ lineHeight: '1.625' }],
        'lg':   ['1.0625rem',{ lineHeight: '1.5' }],
        'xl':   ['1.1875rem',{ lineHeight: '1.4' }],
        '2xl':  ['1.375rem', { lineHeight: '1.35'}],
        '3xl':  ['1.75rem',  { lineHeight: '1.3' }],
        '4xl':  ['2.25rem', { lineHeight: '1.12'}],
        'display': ['clamp(3rem, 6vw, 6.125rem)', { lineHeight: '.94', letterSpacing: '-.06em' }],
      },
      boxShadow: {
        field: '0 30px 80px rgba(0, 0, 0, .28)',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
