import type { Config } from 'tailwindcss';
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  safelist: [
    'bg-speech', 'bg-music', 'bg-sfx', 'bg-accent',
    'border-speech', 'border-music', 'border-sfx', 'border-accent',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0b',
        surface: '#141416',
        'surface-2': '#1c1c1f',
        'surface-3': '#232327',
        border: '#26262a',
        'border-soft': '#1f1f23',
        text: '#f2f2f3',
        'text-dim': '#9a9aa0',
        'text-mute': '#5e5e64',
        accent: '#7c83ff',
        good: '#4ade80',
        speech: '#60a5fa',
        music: '#fbbf24',
        sfx: '#f472b6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: { tight: '-0.01em', tighter: '-0.025em' },
    },
  },
} satisfies Config;
