# Tinybird — Style Reference
> Data noir interface — high contrast text and a single, electric green highlight on a deep, almost black background.

**Theme:** dark

Tinybird presents a 'data noir' aesthetic, marrying industrial-strength data tools with a sophisticated, restrained dark theme. The interplay of near-black backgrounds and pristine white text creates a high-contrast experience, punctuated by a single, vibrant green accent. Careful use of grayscale and subtle elevation on cards provides depth, ensuring critical information stands out against the dark canvas without feeling overwhelming.

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Midnight Ink | `#0a0a0a` | `--color-midnight-ink` | Page backgrounds, elevated surface backgrounds |
| Obsidian Slate | `#262626` | `--color-obsidian-slate` | Card backgrounds, section dividers |
| Iron Oxide | `#151515` | `--color-iron-oxide` | Subtly darker surface backgrounds, minor elements |
| Deep Graphite | `#353535` | `--color-deep-graphite` | Hover states, subtle borders |
| Silver Mist | `#8d8d8d` | `--color-silver-mist` | Secondary text, inactive elements, input placeholders |
| Pure White | `#ffffff` | `--color-pure-white` | Primary text, main headings, critical information |
| Electric Green | `#27f795` | `--color-electric-green` | Primary call-to-action buttons, active navigation, key interactive elements – signals interaction and success in an almost neon glow against the dark UI |
| Deep Jade | `#008060` | `--color-deep-jade` | Subtle indicators, success states (less prominent than Electric Green) |
| Alert Red | `#800000` | `--color-alert-red` | Error states, warnings |
| Crimson Hue | `#ec6d62` | `--color-crimson-hue` | Semantic highlight, less harsh than Alert Red |
| Goldenrod | `#f5c451` | `--color-goldenrod` | Informational highlight, warning states |
| Leaf Green | `#61c454` | `--color-leaf-green` | Alternative success indicator, muted compared to Electric Green |

## Tokens — Typography

### Roboto — The primary sans-serif for all UI elements and body text. Weight 400 is the default for readability, while 600 and 700 are used for emphasis in headings and navigation. The tight letter-spacing at larger sizes ('-0.0200em') creates a more refined, precise look for headlines, typical of digital-native brands. · `--font-roboto`
- **Substitute:** system-ui, sans-serif
- **Weights:** 400, 600, 700
- **Sizes:** 12px, 14px, 16px, 18px, 24px, 64px
- **Line height:** 1.13, 1.33, 1.50, 1.57, 1.67, 1.78
- **Letter spacing:** -0.0200em at display sizes, expanding to more neutral at body sizes
- **Role:** The primary sans-serif for all UI elements and body text. Weight 400 is the default for readability, while 600 and 700 are used for emphasis in headings and navigation. The tight letter-spacing at larger sizes ('-0.0200em') creates a more refined, precise look for headlines, typical of digital-native brands.

### Roboto Mono — Used for code snippets, data points, and technical labels. Its monospace nature clearly differentiates technical content, while the very tight letter-spacing ('-0.0840em') makes even large numbers feel precise and compact, aligning with the brand's focus on efficiency and data infrastructure. · `--font-roboto-mono`
- **Substitute:** monospace
- **Weights:** 400
- **Sizes:** 12px, 14px, 16px, 56px
- **Line height:** 1.00, 1.50, 1.57, 1.67
- **Letter spacing:** -0.0840em for tight, technical presentation regardless of size
- **Role:** Used for code snippets, data points, and technical labels. Its monospace nature clearly differentiates technical content, while the very tight letter-spacing ('-0.0840em') makes even large numbers feel precise and compact, aligning with the brand's focus on efficiency and data infrastructure.

### Type Scale

| Role | Size | Line Height | Letter Spacing | Token |
|------|------|-------------|----------------|-------|
| caption | 12px | 1.78 | — | `--text-caption` |
| body | 14px | 1.57 | — | `--text-body` |
| body-lg | 16px | 1.57 | — | `--text-body-lg` |
| subheading | 18px | 1.67 | — | `--text-subheading` |
| heading | 24px | 1.33 | — | `--text-heading` |
| display-sm | 56px | 1 | -0.084px | `--text-display-sm` |
| display-lg | 64px | 1.13 | -0.02px | `--text-display-lg` |

## Tokens — Spacing & Shapes

**Base unit:** 8px

**Density:** comfortable

### Spacing Scale

| Name | Value | Token |
|------|-------|-------|
| 8 | 8px | `--spacing-8` |
| 16 | 16px | `--spacing-16` |
| 24 | 24px | `--spacing-24` |
| 32 | 32px | `--spacing-32` |
| 40 | 40px | `--spacing-40` |
| 48 | 48px | `--spacing-48` |
| 56 | 56px | `--spacing-56` |
| 64 | 64px | `--spacing-64` |
| 72 | 72px | `--spacing-72` |
| 152 | 152px | `--spacing-152` |

### Border Radius

| Element | Value |
|---------|-------|
| cards | 8px |
| buttons | 0px |
| default | 4px |

### Layout

- **Card padding:** 0px
- **Element gap:** 8px

## Components

### Primary CTA Button
**Role:** Call to action

Solid Electric Green (#27f795) background with Pure White (#ffffff) text. Padding: 8px vertical, 24px horizontal. Sharp corners (0px border-radius) for a direct, functional feel.

### Ghost Navigation Link
**Role:** Navigation

Transparent background with Pure White (#ffffff) text. No padding, no border-radius. Minimalist, almost invisible until hovered.

### Badge Button
**Role:** Categorization/Tagging

Transparent background with Silver Mist (#8d8d8d) text. 4px border-radius, 2px vertical and 4px horizontal padding. Subtle visual weight suitable for filtering or tagging.

### Disabled/Secondary Ghost Link
**Role:** Navigation/Low-priority action

Transparent background with Silver Mist (#8d8d8d) text. No padding, no border-radius. Indicates a less emphasized action or inactive state.

### Sign Up Button
**Role:** Navigation/Action

Solid Electric Green (#27f795) background with Midnight Ink (#0a0a0a) text. Sharp corners (0px border-radius). Padding: 8px vertical, 24px horizontal. Top right navigation prominent action.

### Sign In Button
**Role:** Navigation/Action

Transparent background with Pure White (#ffffff) text. No border, no padding. Low visual weight navigation action.

### Client Logo Grid Item
**Role:** Brand endorsement display

Images contained within a `div` on the Midnight Ink (#0a0a0a) background. Minimal padding and no border-radius, presenting logos directly without adornment, emphasizing the dark canvas.

## Do's and Don'ts

### Do
- Use Midnight Ink (#0a0a0a) for all primary page backgrounds to maintain the brand's 'data noir' aesthetic.
- Apply Electric Green (#27f795) exclusively for primary calls-to-action and active states to ensure high impact and clear signaling.
- Utilize Roboto at weight 400 for all body copy and default text at 14px with lineHeight 1.57 for maximum readability.
- Reserve Roboto Mono for all data points, code blocks, and technical figures, specifically at 56px with -0.0840em letter-spacing for large numbers.
- Implement 0px border-radius for all primary buttons to convey a direct, precise interaction model.
- Maintain a clear hierarchy with Pure White (#ffffff) for primary text and Silver Mist (#8d8d8d) for secondary or supporting text.
- Employ Obsidian Slate (#262626) with an 8px border-radius for card backgrounds to visually separate content blocks from the main background.

### Don't
- Do not introduce additional saturated colors; Electric Green (#27f795) is the singular brand accent.
- Avoid decorative shadows or excessive elevation; depth is created through varying shades of gray and card backgrounds.
- Do not use letter-spacing on body text; apply tight letter-spacing (-0.0200em or -0.0840em) only to display headings and technical text fields.
- Never use rounded buttons or pill shapes; all interactive elements should maintain sharp corners unless specifically designated for cards (8px).
- Avoid light backgrounds; the design system is strictly dark-mode first.
- Do not use generic system fonts for data or code; Roboto Mono is mandated for technical content to ensure distinction.
- Refrain from using gratuitous iconography; only use icons when they serve a clear functional purpose, maintaining the minimal aesthetic.

## Imagery

The site's visual language is text-dominant, with imagery appearing primarily as product-focused illustrations or iconographic elements. Where present, visuals are stark and clean: client logos are monochrome, either Pure White or Silver Mist against the dark background. Abstract graphics are geometric and align with a data visualization aesthetic. There are no photographs. The overall impression is one of pure UI, where information and code are the primary visual content, accented by minimalist, functional graphics that support the technical narrative.

## Layout

The layout is primarily centered and contained, with a max-width approach implied by content blocks, although the main background is full-bleed Midnight Ink. The hero section is full-bleed dark with a prominent, centered headline and subtext, followed by centered CTA buttons. Sections alternate between dense information blocks, often with client logos in a grid, and testimonial cards that adopt a card grid structure. Vertical spacing between sections is generous and irregular, ranging from 136px to 456px, creating a comfortable rhythm. Navigation is a sticky top bar with left-aligned brand icon and right-aligned text links and CTA buttons.

## Agent Prompt Guide

### Quick Color Reference
- Text: #ffffff (Pure White)
- Background: #0a0a0a (Midnight Ink)
- CTA: #27f795 (Electric Green)
- Secondary Text: #8d8d8d (Silver Mist)
- Card Background: #262626 (Obsidian Slate)

### 3-5 Example Component Prompts
1. Create a hero section: background #0a0a0a. Headline with 'Ship fast over a Managed ClickHouse®' at 64px Roboto weight 600, #ffffff, letter-spacing -0.020em. Subtext 'The data infrastructure...' at 18px Roboto weight 400, #8d8d8d. Primary CTA button with text 'Try for free', background #27f795, text #0a0a0a, 8px vertical padding, 24px horizontal padding, 0px border-radius. Secondary CTA with text 'Contact sales', background transparent, text #ffffff.
2. Design a testimonial card: background #262626, 8px border-radius. Inner text 'We stopped investing in our ClickHouse cluster...' at 16px Roboto weight 400, #ffffff. Author name 'Jared Palmer' at 14px Roboto weight 600, #ffffff. Position 'VP of AI at Vercel' at 14px Roboto weight 400, #8d8d8d.
3. Implement a navigation bar item: Text 'Product [+]', color #ffffff, font Roboto weight 400, no padding, 0px border-radius. On hover, color #27f795. The '+' should be Roboto Mono weight 400, 14px.
4. Render a data metric display: Number '1.47B' using Roboto Mono 56px weight 400, #ffffff, letter-spacing -0.084em. Label 'REQUESTS PER MONTH' using Roboto 12px weight 400, #8d8d8d.

## Similar Brands

- **Vercel** — Dark-mode UI, prominent green accent color for CTAs, and a focus on developer tools and infrastructure.
- **Stripe (developer docs)** — High-contrast dark theme, monospace fonts for code, and a clean, function-over-form aesthetic for developer audience.
- **Supabase** — Dark UI, single vibrant accent color, and a modern, slightly industrial feel for database and backend tools.

## Quick Start

### CSS Custom Properties

```css
:root {
  /* Colors */
  --color-midnight-ink: #0a0a0a;
  --color-obsidian-slate: #262626;
  --color-iron-oxide: #151515;
  --color-deep-graphite: #353535;
  --color-silver-mist: #8d8d8d;
  --color-pure-white: #ffffff;
  --color-electric-green: #27f795;
  --color-deep-jade: #008060;
  --color-alert-red: #800000;
  --color-crimson-hue: #ec6d62;
  --color-goldenrod: #f5c451;
  --color-leaf-green: #61c454;

  /* Typography — Font Families */
  --font-roboto: 'Roboto', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-roboto-mono: 'Roboto Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

  /* Typography — Scale */
  --text-caption: 12px;
  --leading-caption: 1.78;
  --text-body: 14px;
  --leading-body: 1.57;
  --text-body-lg: 16px;
  --leading-body-lg: 1.57;
  --text-subheading: 18px;
  --leading-subheading: 1.67;
  --text-heading: 24px;
  --leading-heading: 1.33;
  --text-display-sm: 56px;
  --leading-display-sm: 1;
  --tracking-display-sm: -0.084px;
  --text-display-lg: 64px;
  --leading-display-lg: 1.13;
  --tracking-display-lg: -0.02px;

  /* Typography — Weights */
  --font-weight-regular: 400;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* Spacing */
  --spacing-unit: 8px;
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-56: 56px;
  --spacing-64: 64px;
  --spacing-72: 72px;
  --spacing-152: 152px;

  /* Layout */
  --card-padding: 0px;
  --element-gap: 8px;

  /* Border Radius */
  --radius-md: 4px;
  --radius-lg: 8px;

  /* Named Radii */
  --radius-cards: 8px;
  --radius-buttons: 0px;
  --radius-default: 4px;
}
```

### Tailwind v4

```css
@theme {
  /* Colors */
  --color-midnight-ink: #0a0a0a;
  --color-obsidian-slate: #262626;
  --color-iron-oxide: #151515;
  --color-deep-graphite: #353535;
  --color-silver-mist: #8d8d8d;
  --color-pure-white: #ffffff;
  --color-electric-green: #27f795;
  --color-deep-jade: #008060;
  --color-alert-red: #800000;
  --color-crimson-hue: #ec6d62;
  --color-goldenrod: #f5c451;
  --color-leaf-green: #61c454;

  /* Typography */
  --font-roboto: 'Roboto', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-roboto-mono: 'Roboto Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

  /* Typography — Scale */
  --text-caption: 12px;
  --leading-caption: 1.78;
  --text-body: 14px;
  --leading-body: 1.57;
  --text-body-lg: 16px;
  --leading-body-lg: 1.57;
  --text-subheading: 18px;
  --leading-subheading: 1.67;
  --text-heading: 24px;
  --leading-heading: 1.33;
  --text-display-sm: 56px;
  --leading-display-sm: 1;
  --tracking-display-sm: -0.084px;
  --text-display-lg: 64px;
  --leading-display-lg: 1.13;
  --tracking-display-lg: -0.02px;

  /* Spacing */
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-56: 56px;
  --spacing-64: 64px;
  --spacing-72: 72px;
  --spacing-152: 152px;

  /* Border Radius */
  --radius-md: 4px;
  --radius-lg: 8px;
}
```
