# MetaChromatic Brand Identity — Design Spec

**Date:** 2026-04-03
**Status:** Active
**Scope:** Icon, typography, glassmorphism design system

---

## 1. Brand Concept

MetaChromatic's visual identity is built around a **prismatic "M"** — an organic, flowing letterform rendered in a full spectral gradient, sitting on a deep navy foundation with geometric wireframe accents. The overall aesthetic is **dark glassmorphism**: frosted glass panels over rich dark backgrounds, with prismatic color accents.

---

## 2. Color Palette

### Foundation

| Token | Hex | Usage |
|-------|-----|-------|
| `--mc-navy` | `#0a0e1a` | Primary background |
| `--mc-navy-light` | `#141a2e` | Elevated surfaces |
| `--mc-navy-mid` | `#1e2842` | Cards, panels |
| `--mc-navy-surface` | `#232d4a` | Active/hover states |

### Prismatic Spectrum

| Token | Hex | Swatch |
|-------|-----|--------|
| `--mc-blue` | `#1e3a8a` | Deep blue |
| `--mc-cyan` | `#06b6d4` | Primary accent |
| `--mc-purple` | `#7c3aed` | Secondary accent |
| `--mc-magenta` | `#c026d3` | Highlight |
| `--mc-rose` | `#e11d48` | Alert/warm |
| `--mc-orange` | `#f97316` | Warm accent |
| `--mc-yellow` | `#eab308` | Warning/gold |
| `--mc-green` | `#22c55e` | Success |

### Semantic

| Purpose | Token | Color |
|---------|-------|-------|
| Success | `--mc-success` | `#22c55e` |
| Warning | `--mc-warning` | `#eab308` |
| Error | `--mc-error` | `#e11d48` |
| Info | `--mc-info` | `#06b6d4` |

---

## 3. Icon

### Files

| File | Purpose |
|------|---------|
| `products/design/icons/metachromatic-icon.svg` | Full-detail 512px icon |
| `products/design/icons/metachromatic-favicon.svg` | Simplified 32px favicon |

### Construction

The icon is composed of 5 layers:

1. **Navy squircle** — `rx=115` rounded rect, `#0a0e1a` with subtle `#3a4a6b` border at 40% opacity
2. **Geometric wireframe** — Diamond shapes + radial lines at 10% white opacity
3. **Center glow** — Radial gradient, white→transparent
4. **Prismatic M** — Dual-gradient letterform with inner depth faces
5. **Specular highlights** — Thin white strokes at 12% opacity for dimensional sheen

### Usage Guidelines

- **Minimum size:** 16x16 px (use favicon variant below 64px)
- **Clear space:** 12.5% of icon width on all sides
- **On dark backgrounds:** No modifications needed
- **On light backgrounds:** Add `box-shadow: 0 4px 24px rgba(0,0,0,0.3)` for separation

---

## 4. Typography

### Font Stack

```css
--mc-font-display: 'Prompt', ui-sans-serif, system-ui, sans-serif;
--mc-font-body:    'Prompt', ui-sans-serif, system-ui, sans-serif;
--mc-font-mono:    'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
```

Import from Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### Hierarchy on Glass Surfaces

| Level | Size | Weight | Color | Extra |
|-------|------|--------|-------|-------|
| Display (h1) | `3rem` | 700 | `--mc-text-primary` | `text-shadow: var(--mc-text-glow)` |
| Heading (h2) | `2.25rem` | 600 | `--mc-text-primary` | — |
| Subheading (h3) | `1.5rem` | 600 | `--mc-text-primary` | — |
| Body | `1rem` | 400 | `--mc-text-secondary` | `line-height: 1.6` |
| Caption | `0.75rem` | 500 | `--mc-text-muted` | `text-transform: uppercase; letter-spacing: 0.05em` |
| Code | `0.875rem` | 400 | `--mc-text-secondary` | Mono font |

---

## 5. Glassmorphism System

### Core Recipe

```css
.glass-panel {
  background: rgba(10, 14, 26, 0.65);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
}
```

### Blur Tiers

| Level | Blur | Opacity | Use Case |
|-------|------|---------|----------|
| Light | 8px | 55% | Tooltips, dropdowns |
| Normal | 16px | 65% | Cards, panels |
| Heavy | 24px | 85% | Navigation, modals |
| Extreme | 40px | 50% (bg only) | Modal backdrops |

### Interaction States

- **Hover:** Border brightens to `rgba(255,255,255,0.15)`, subtle translateY(-2px)
- **Active/Focus:** Cyan ring `0 0 0 2px rgba(6,182,212,0.2)`
- **Disabled:** Opacity 0.5, pointer-events none

---

## 6. Prismatic Effects

### Gradient Text

```css
.prismatic-text {
  background: var(--mc-gradient-prismatic);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### Animated Gradient Border

```css
.prismatic-border::before {
  content: '';
  position: absolute;
  inset: 0;
  padding: 1px;
  border-radius: inherit;
  background: var(--mc-gradient-prismatic);
  background-size: 200% 200%;
  animation: prismatic-shift 4s ease infinite;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}
```

---

## 7. Integration

### Tailwind Extension

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        mc: {
          navy:    { DEFAULT: '#0a0e1a', light: '#141a2e', mid: '#1e2842' },
          blue:    '#1e3a8a',
          cyan:    '#06b6d4',
          purple:  '#7c3aed',
          magenta: '#c026d3',
          rose:    '#e11d48',
          orange:  '#f97316',
          yellow:  '#eab308',
          green:   '#22c55e',
        },
      },
      backdropBlur: {
        'mc':       '16px',
        'mc-heavy': '24px',
      },
      borderRadius: {
        'mc':    '16px',
        'mc-sm': '8px',
        'mc-lg': '24px',
      },
      fontFamily: {
        sans: ['Prompt', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
    },
  },
};
```

### CSS Import

```css
@import 'products/design/tokens/metachromatic-tokens.css';
@import 'products/design/tokens/metachromatic-glass.css';
```

---

## 8. Files Reference

| File | Description |
|------|-------------|
| `products/design/icons/metachromatic-icon.svg` | Full prismatic M icon (512px) |
| `products/design/icons/metachromatic-favicon.svg` | Simplified favicon (32px) |
| `products/design/tokens/metachromatic-tokens.css` | All CSS custom properties |
| `products/design/tokens/metachromatic-glass.css` | Glassmorphism utility classes |
| `products/design/scripts/generate-icons.mjs` | SVG → PNG rasterization |
