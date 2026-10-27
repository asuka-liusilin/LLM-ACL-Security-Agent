/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#081a2e',
          800: '#0d2743',
          700: '#123757',
          600: '#1a4a70',
        },
        accent: {
          50: '#eefbfd',
          100: '#d3f4f8',
          400: '#2bb6c8',
          500: '#0f9fb3',
          600: '#0b8296',
        },
      },
      fontFamily: {
        sans: [
          '"Microsoft YaHei"',
          '"PingFang SC"',
          '"Hiragino Sans GB"',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'sans-serif',
        ],
        mono: ['"JetBrains Mono"', 'Consolas', '"Courier New"', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(8, 26, 46, 0.04), 0 8px 24px -12px rgba(8, 26, 46, 0.16)',
      },
    },
  },
  plugins: [],
}
