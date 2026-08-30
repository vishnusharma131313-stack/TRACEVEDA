/** @type {import('tailwindcss').Config} */

/*
 * TRACEVEDA DESIGN SYSTEM
 *
 * Five colours plus neutrals. Nothing else is defined on purpose — if a
 * component needs a colour that is not here, the answer is to reuse one of
 * these, not to add a sixth.
 *
 *   surface   warm off-white ground (agricultural, not fintech)
 *   ink       charcoal-green text
 *   verified  deep green   — CONFIRMED states only. Earn it.
 *   alert     terracotta   — warnings and advisories
 *   critical  true red     — tamper / blocked / recall only, so it stays loud
 *   chain     deep indigo  — the tamper-evident layer, and nothing else
 */

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#FAF8F3',
          sunk: '#F4F1E8',
          raised: '#FFFFFF',
        },
        ink: {
          DEFAULT: '#1C2B22',
          soft: '#3A4A41',
        },

        verified: {
          DEFAULT: '#2F6844',
          light: '#3D8A5A',
          dark: '#1F4A2F',
          50: '#F0F7F2',
          100: '#DCF0E2',
          200: '#B5DFC3',
          300: '#8AC9A0',
          400: '#57A578',
          500: '#2F6844',
          600: '#27583A',
          700: '#1F4730',
          800: '#183626',
          900: '#11261B',
        },

        alert: {
          DEFAULT: '#C4622D',
          light: '#E8854D',
          dark: '#9C4E24',
          50: '#FDF6F1',
          100: '#FAE7D9',
          200: '#F3CBAE',
          300: '#E9A87E',
          400: '#DA8553',
          500: '#C4622D',
          600: '#A75226',
          700: '#88421F',
          800: '#693318',
          900: '#4A2411',
        },

        critical: {
          DEFAULT: '#B3261E',
          light: '#DC362E',
          dark: '#8C1D18',
          50: '#FDF3F2',
          100: '#FADFDD',
          200: '#F4BEBA',
          300: '#E9928C',
          400: '#D4655D',
          500: '#B3261E',
          600: '#99201A',
          700: '#7C1A15',
          800: '#5E1410',
          900: '#400E0B',
        },

        chain: {
          DEFAULT: '#3B3269',
          light: '#5B52A0',
          dark: '#2A2450',
          50: '#F4F3FA',
          100: '#E6E3F4',
          200: '#CBC6E7',
          300: '#A9A1D5',
          400: '#8177BD',
          500: '#5D53A0',
          600: '#4A4183',
          700: '#3B3269',
          800: '#2C254F',
          900: '#1D1936',
        },

        neutral: {
          DEFAULT: '#8A857A',
          50: '#FAFAF8',
          100: '#F4F3EE',
          200: '#E8E6DD',
          300: '#D4D1C6',
          400: '#B0ACA0',
          500: '#8A857A',
          600: '#6B665D',
          700: '#4A463F',
          800: '#2E2B26',
          900: '#1A1815',
        },
      },

      fontFamily: {
        serif: ['"Source Serif 4"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'Consolas', 'monospace'],
      },

      fontSize: {
        display: ['3.25rem', { lineHeight: '1.08', letterSpacing: '-0.025em', fontWeight: '700' }],
        h1: ['2.125rem', { lineHeight: '1.18', letterSpacing: '-0.018em', fontWeight: '700' }],
        h2: ['1.625rem', { lineHeight: '1.25', letterSpacing: '-0.012em', fontWeight: '600' }],
        h3: ['1.3125rem', { lineHeight: '1.35', fontWeight: '600' }],
        h4: ['1.0625rem', { lineHeight: '1.4', fontWeight: '600' }],
        h5: ['0.9375rem', { lineHeight: '1.4', fontWeight: '600' }],
        body: ['0.9375rem', { lineHeight: '1.6' }],
        small: ['0.8125rem', { lineHeight: '1.5' }],
        micro: ['0.6875rem', { lineHeight: '1.35', letterSpacing: '0.04em' }],
      },

      boxShadow: {
        card: '0 1px 2px rgba(28,43,34,.05), 0 1px 3px rgba(28,43,34,.04)',
        'card-hover': '0 10px 30px rgba(28,43,34,.08), 0 3px 8px rgba(28,43,34,.05)',
        elevated: '0 24px 60px rgba(28,43,34,.12), 0 8px 18px rgba(28,43,34,.06)',
        'chain-glow': '0 0 0 1px rgba(59,50,105,.14), 0 8px 26px rgba(59,50,105,.16)',
        'critical-glow': '0 0 0 1px rgba(179,38,30,.2), 0 8px 26px rgba(179,38,30,.18)',
      },

      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
        '3xl': '1.5rem',
      },

      animation: {
        'fade-in': 'fadeIn .35s ease-out both',
        'slide-up': 'slideUp .45s cubic-bezier(.22,1,.36,1) both',
        'pulse-gentle': 'pulseGentle 2.4s ease-in-out infinite',
        shimmer: 'shimmer 1.6s linear infinite',
        'chain-pulse': 'chainPulse 2.2s ease-in-out infinite',
      },

      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGentle: { '0%,100%': { opacity: '1' }, '50%': { opacity: '.55' } },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        chainPulse: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(59,50,105,.35)' },
          '50%': { boxShadow: '0 0 0 6px rgba(59,50,105,0)' },
        },
      },
    },
  },
  plugins: [],
}
