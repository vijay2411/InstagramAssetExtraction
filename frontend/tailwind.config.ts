import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces — warm-cast dark, not pure neutral
        bg:            '#0b0908',
        'bg-warm':     '#14100c',
        surface:       '#161310',
        'surface-2':   '#1c1815',
        'surface-3':   '#26211c',
        border:        '#2a2520',
        'border-soft': '#221e1a',

        // Ink — paper-white with warm cast, not pure white
        text:          '#faf7f2',
        'text-dim':    '#b0a99f',
        'text-mute':   '#6b675e',

        // Primary palette — amber ember, not purple
        ember:         '#e8b13a',
        'ember-hot':   '#ffc85a',
        plum:          '#9f4c6d',
        sea:           '#4ec9b0',
        coral:         '#ff8a5b',
        good:          '#6ad99a',

        // Per-stem colors — harmonised with the ember palette
        speech:        '#80b5ff',
        music:         '#e8b13a',  // same as ember
        sfx:           '#ff8a5b',  // coral

        // Legacy alias so existing class names don't break
        accent:        '#e8b13a',
      },
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans:    ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        tight:   '-0.01em',
        tighter: '-0.025em',
        display: '-0.04em',
      },
      fontSize: {
        'display-sm': ['2.25rem', { lineHeight: '1.05', letterSpacing: '-0.035em' }],
        'display':    ['3.5rem',  { lineHeight: '1.0',  letterSpacing: '-0.04em' }],
        'display-lg': ['5.5rem',  { lineHeight: '0.95', letterSpacing: '-0.045em' }],
      },
      backgroundImage: {
        'dot-grid': "radial-gradient(circle at 1px 1px, rgba(250,247,242,0.055) 1px, transparent 0)",
      },
      animation: {
        'aurora':      'aurora 26s ease-in-out infinite',
        'aurora-slow': 'aurora 42s ease-in-out infinite reverse',
        'shimmer':     'shimmer 3s linear infinite',
      },
      keyframes: {
        aurora: {
          '0%,100%': { transform: 'translate3d(-8%, -6%, 0) rotate(0deg) scale(1.15)' },
          '50%':     { transform: 'translate3d(6%, 4%, 0) rotate(12deg) scale(1.3)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  safelist: [
    'bg-ember', 'bg-speech', 'bg-music', 'bg-sfx', 'bg-coral', 'bg-sea', 'bg-plum', 'bg-accent',
    'border-ember', 'border-speech', 'border-music', 'border-sfx', 'border-coral', 'border-accent',
    'text-ember', 'text-speech', 'text-music', 'text-sfx', 'text-coral',
  ],
} satisfies Config;
