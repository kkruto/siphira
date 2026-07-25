/** Siphira John — design tokens straight from her brief. */
module.exports = {
  content: [
    './apps/**/templates/**/*.html',
    './templates/**/*.html',
    './apps/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        // Her four brand colours, named by role rather than hue so a future
        // palette change is a one-line edit here.
        paper:    '#FAFAF9',   // warm white — page background
        ink:      '#1F2937',   // charcoal — headings and body text
        sage:     '#84A98C',   // sage green — buttons, accents, links
        'sage-deep': '#6B8E74', // hover state, and the AA-contrast text variant
        sand:     '#D6C6B8',   // cards and highlights
        'sand-soft': '#EFE8E1', // tinted surface, lighter than sand
        muted:    '#6B7280',   // secondary text
        line:     '#E7E2DC',   // hairline borders
      },
      fontFamily: {
        // Rounded, modern, warm — the brief asked for rounded sans throughout.
        sans: ['Nunito', 'ui-rounded', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Nunito', 'ui-rounded', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
      },
      maxWidth: {
        prose: '68ch',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(31,41,55,0.04), 0 8px 24px -12px rgba(31,41,55,0.10)',
        lift: '0 2px 4px rgba(31,41,55,0.05), 0 18px 40px -18px rgba(31,41,55,0.18)',
      },
      keyframes: {
        'fade-up': {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s ease-out both',
      },
      typography: (theme) => ({
        siphira: {
          css: {
            '--tw-prose-body': theme('colors.ink'),
            '--tw-prose-headings': theme('colors.ink'),
            '--tw-prose-links': theme('colors.sage-deep'),
            '--tw-prose-bold': theme('colors.ink'),
            '--tw-prose-quotes': theme('colors.muted'),
            '--tw-prose-quote-borders': theme('colors.sage'),
            '--tw-prose-bullets': theme('colors.sage'),
            '--tw-prose-hr': theme('colors.line'),
            '--tw-prose-captions': theme('colors.muted'),
            '--tw-prose-code': theme('colors.ink'),
            '--tw-prose-pre-bg': '#F4F1EC',
            '--tw-prose-pre-code': theme('colors.ink'),
          },
        },
      }),
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
