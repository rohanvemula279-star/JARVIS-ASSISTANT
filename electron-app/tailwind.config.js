/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        jarvis: {
          black: '#050505',
          dark: '#0a0a0a',
          charcoal: '#1a1a1a',
          gray: '#2a2a2a',
          white: '#f5f5f5',
          cyan: '#00f0ff',
          dim: 'rgba(255,255,255,0.05)',
        }
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 240, 255, 0.2)',
        'glow-white': '0 0 20px rgba(255, 255, 255, 0.1)',
      },
      fontFamily: {
        mono: ['Space Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
