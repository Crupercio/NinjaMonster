# DESIGN SYSTEM — POKÉMON COLLECTIBLE GAME
> Version 1.0 — Living Document

This is the **single source of truth** for all UI decisions in this project.
Every page, component, and animation must be derived from this system.
Reference this document at the start of every Claude session that touches UI.

---

## STACK CONSTRAINTS (NON-NEGOTIABLE)

- **Templating:** Django HTML templates
- **CSS:** Vanilla CSS + CSS custom properties (NO Tailwind, NO Bootstrap)
- **Interactivity:** Alpine.js 3.x (lightweight state) + HTMX 2.x (server updates)
- **Fonts:** Google Fonts — already loaded: `Chakra Petch`, `Plus Jakarta Sans`, `JetBrains Mono`
- **No React, No Vue, No build step** — everything must work in `<style>` blocks or `base.css`

---

## 1. VISUAL IDENTITY

### Aesthetic
**"Dark Anime Tactical"** — The UI lives at the intersection of:
- A high-end trading card game interface (Pokémon TCG Online, Legends of Runeterra)
- A Japanese RPG menu system (Persona 5, Fire Emblem: Three Houses)
- A military tactical screen (dark, precise, purposeful)

### Mood
- **Mysterious** during exploration and pack reveals
- **Exciting** during battles and rare pulls
- **Satisfying** during collection completion
- **Intimate** in trainer profiles and albums

### What it must never feel like
- A SaaS dashboard
- A generic e-commerce shop
- A school project
- A Tailwind starter template

### Reference Touchstones
| Reference | What to steal |
|-----------|--------------|
| Persona 5 | Diagonal cuts, aggressive typography, red/black contrast |
| Legends of Runeterra | Card depth, environmental backdrops, premium card reveals |
| Pokémon TCG Online | Rarity shimmer, pack opening energy |
| Fire Emblem | Clean tactical panels, portrait framing, warm/cool duality |
| Hades | Persistent world feel, UI that belongs in the world |

---

## 2. COLOR SYSTEM

### Base Palette (CSS Variables in `:root`)

```css
:root {
  /* ── Backgrounds ─────────────────────────────────────────── */
  --bg-void:     #0d0d1a;   /* Deepest background — use behind everything */
  --bg-primary:  #1a1a2e;   /* Main page background */
  --bg-card:     #16213e;   /* Card surfaces, panels */
  --bg-raised:   #0f3460;   /* Elevated elements — inputs, active states */
  --bg-overlay:  rgba(13, 13, 26, 0.85); /* Modal/drawer backdrops */

  /* ── Accent Colors ───────────────────────────────────────── */
  --accent-red:    #e94560;   /* Primary CTA, danger, Pokéball red */
  --accent-gold:   #f5a623;   /* Rewards, achievements, premium */
  --accent-cyan:   #00d4ff;   /* Combo highlights, info, links */
  --accent-purple: #a78bfa;   /* Epic/legendary, special events */

  /* ── Text ────────────────────────────────────────────────── */
  --text-1:  #f0f0f8;   /* Primary headings and labels */
  --text-2:  #9ca3af;   /* Secondary/supporting text */
  --text-3:  #4b5563;   /* Placeholder, disabled, ghost text */

  /* ── Borders ─────────────────────────────────────────────── */
  --border-lo:  rgba(15,  52, 96, 0.8);   /* Hairline separators */
  --border-md:  rgba(30,  58,110, 1.0);   /* Default card borders */
  --border-hi:  rgba(100,149,237, 0.35);  /* Emphasized/hover borders */

  /* ── Rarity Colors ───────────────────────────────────────── */
  --r-common:      #9ca3af;
  --r-uncommon:    #4ade80;
  --r-rare:        #60a5fa;
  --r-epic:        #a78bfa;
  --r-holo:        #fbbf24;
  --r-full-art:    #f97316;
  --r-secret:      #f43f5e;

  /* ── Glow RGB values (for box-shadow) ───────────────────── */
  --glow-red:    233, 69, 96;
  --glow-gold:   251,191, 36;
  --glow-cyan:     0,212,255;
  --glow-purple: 167,139,250;

  /* ── Spacing ─────────────────────────────────────────────── */
  --radius-sm:  6px;
  --radius-md:  10px;
  --radius-lg:  16px;
  --radius-xl:  24px;

  --shadow-card: 0 4px 24px rgba(0,0,0,0.5);
  --shadow-lift: 0 8px 32px rgba(0,0,0,0.7);
}
```

### Color Usage Rules

| Color | Use for | Never use for |
|-------|---------|---------------|
| `--accent-red` | Primary buttons, Pokéball, damage indicators | Success states, coins |
| `--accent-gold` | Coins, achievements, holographic accents | Warnings/errors |
| `--accent-cyan` | Combo chains, links, info badges | Danger/error |
| `--accent-purple` | Epic rarity, legendary Pokémon, event labels | Normal UI |
| `--bg-raised` | Input fields, hovered cards, active nav items | Page backgrounds |

### Glow Rules

Glows are earned — do not apply them by default:

```
✅ GLOW: Premium rarity cards (holo, full_art, secret_rare)
✅ GLOW: Active battle selections
✅ GLOW: Newly revealed pack cards
✅ GLOW: CTA buttons on hover
✅ GLOW: Achievement unlocks

❌ NO GLOW: Common/uncommon cards at rest
❌ NO GLOW: Navigation items
❌ NO GLOW: Form inputs (use border highlight instead)
❌ NO GLOW: Every card in a grid (pick your moments)
```

Glow formula:
```css
/* Subtle */
box-shadow: 0 0 8px rgba(var(--glow-gold), 0.4);

/* Standard */
box-shadow: 0 0 16px rgba(var(--glow-gold), 0.6);

/* Dramatic (pack reveal, legendary) */
box-shadow: 0 0 32px rgba(var(--glow-gold), 0.8), 0 0 64px rgba(var(--glow-gold), 0.3);
```

---

## 3. TYPOGRAPHY SYSTEM

### Font Stack

```css
--font-display: 'Chakra Petch', 'Rajdhani', sans-serif;
  /* Use for: headings, card names, rarity labels, nav items */
  /* Feel: angular, game-like, precise */

--font-body: 'Plus Jakarta Sans', system-ui, sans-serif;
  /* Use for: paragraphs, descriptions, form labels */
  /* Feel: clean, readable, modern */

--font-mono: 'JetBrains Mono', monospace;
  /* Use for: dex numbers, stat values, battle logs, coin amounts */
  /* Feel: technical, game HUD */
```

### Scale

```css
/* Display — Page titles, hero text */
.t-display {
  font-family: var(--font-display);
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

/* H1 — Section titles */
.t-h1 {
  font-family: var(--font-display);
  font-size: clamp(1.4rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: 0.01em;
}

/* H2 — Card names, panel headers */
.t-h2 {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* Label — Rarity tags, badge text, nav caps */
.t-label {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

/* Body — Descriptions, flavor text */
.t-body {
  font-family: var(--font-body);
  font-size: 0.9rem;
  font-weight: 400;
  line-height: 1.6;
}

/* Mono — Dex numbers, stats, coin counts */
.t-mono {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
}
```

### Typography Rules

- **Pokémon names**: `Chakra Petch 600` — never lowercase
- **Dex numbers** (`#001`): `JetBrains Mono` — always zero-padded
- **Rarity labels**: ALL CAPS, `Chakra Petch`, colored with rarity token
- **Coin amounts**: `JetBrains Mono` + `--accent-gold` color
- **Flavor text**: `Plus Jakarta Sans` italic, `--text-2` color
- **NEVER** use default `font-family: sans-serif` — always specify the token

---

## 4. SPACING & LAYOUT SYSTEM

### Spacing Scale

```css
--space-1:  4px;    /* Hairline gaps, icon padding */
--space-2:  8px;    /* Tight internal padding */
--space-3:  12px;   /* Badge padding, compact rows */
--space-4:  16px;   /* Standard card padding */
--space-5:  24px;   /* Section gaps */
--space-6:  32px;   /* Page section breathing room */
--space-8:  48px;   /* Hero section padding */
--space-10: 64px;   /* Page top/bottom margins */
```

### Layout Zones

Every page has three conceptual layers:

```
┌─────────────────────────────────────┐
│  LAYER 3: UI (fixed nav, modals)    │  z-index: 100+
├─────────────────────────────────────┤
│  LAYER 2: CONTENT (cards, panels)   │  z-index: 10–99
├─────────────────────────────────────┤
│  LAYER 1: ENVIRONMENT (bg, fog)     │  z-index: 0–9
└─────────────────────────────────────┘
```

### Grid Patterns

**Pokémon Collection Grid:**
```css
grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
gap: var(--space-3);
```

**Card Deck / Pack Grid:**
```css
display: flex;
gap: var(--space-5);
justify-content: center;
flex-wrap: wrap;
```

**Stat Row:**
```css
grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
gap: var(--space-3);
```

**Battle Arena (2 teams):**
```css
display: grid;
grid-template-columns: 1fr auto 1fr;
align-items: center;
gap: var(--space-4);
```

### Page Max Width
```css
.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-5);
}
```

---

## 5. COMPONENT SYSTEM

### 5.1 Pokemon / Sticker Cards

```css
/* Base card — all Pokémon/sticker cards inherit from this */
.game-card {
  background: var(--bg-card);
  border: 1px solid var(--border-md);
  border-radius: var(--radius-lg);
  position: relative;
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

/* Inner frame — separates image zone from text zone */
.game-card__image {
  background: linear-gradient(160deg, #0d1b3e 0%, #0a1628 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3);
}

.game-card__body {
  padding: var(--space-3) var(--space-4);
  text-align: center;
}

/* Hover lift — applied to all clickable cards */
.game-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-hi);
  box-shadow: var(--shadow-lift);
}

/* Rarity border flash — applied via .r-{rarity} class on card */
.game-card.r-holographic  { border-color: var(--r-holo); }
.game-card.r-full_art     { border-color: var(--r-full-art); }
.game-card.r-secret_rare  { border-color: var(--r-secret); }
.game-card.r-epic         { border-color: var(--r-epic); }

/* Premium glow — only holo+ cards */
.game-card.r-holographic { box-shadow: 0 0 14px rgba(var(--glow-gold), 0.45); }
.game-card.r-secret_rare { box-shadow: 0 0 14px rgba(var(--glow-red), 0.5); }
```

**States:**
- `missing` / `locked`: `opacity: 0.3; filter: grayscale(90%);`
- `new`: add pulsing gold border animation
- `duplicate`: show `×N` badge in top-right corner

---

### 5.2 Buttons

```css
/* Base */
.btn {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.6rem 1.4rem;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.18s ease, filter 0.15s ease;
}

/* Primary — main CTAs */
.btn-primary {
  background: var(--accent-red);
  color: #fff;
}
.btn-primary:hover {
  filter: brightness(1.1);
  box-shadow: 0 4px 16px rgba(var(--glow-red), 0.5);
  transform: translateY(-1px);
}
.btn-primary:active { transform: scale(0.97); }

/* Gold — rewards, purchases */
.btn-gold {
  background: linear-gradient(135deg, #f5a623, #fbbf24);
  color: #1a1a2e;
}
.btn-gold:hover {
  filter: brightness(1.08);
  box-shadow: 0 4px 16px rgba(var(--glow-gold), 0.55);
  transform: translateY(-1px);
}

/* Ghost — secondary actions */
.btn-ghost {
  background: transparent;
  border: 1px solid var(--border-md);
  color: var(--text-2);
}
.btn-ghost:hover {
  border-color: var(--border-hi);
  color: var(--text-1);
  background: rgba(255,255,255,0.04);
}

/* Danger — destructive actions */
.btn-danger {
  background: rgba(233, 69, 96, 0.15);
  border: 1px solid var(--accent-red);
  color: var(--accent-red);
}
```

**Rules:**
- Never use `border-radius: 50px` pill buttons — use `var(--radius-md)` max
- CTA buttons must have hover glow
- Use `btn-gold` exclusively for coin-spending actions
- Icon buttons (square) use `padding: 0.5rem`

---

### 5.3 Panels

```css
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border-md);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}

/* Panel with top accent bar — use for named sections */
.panel--accented {
  border-top: 3px solid var(--accent-red);
}

/* Panel with frosted look — modals, overlays only */
.panel--frosted {
  background: rgba(22, 33, 62, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* Panel header */
.panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-lo);
}

.panel__title {
  font-family: var(--font-display);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-2);
}
```

---

### 5.4 Modals

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
}

.modal {
  background: var(--bg-card);
  border: 1px solid var(--border-hi);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  max-width: 480px;
  width: 100%;
  box-shadow: var(--shadow-lift);
  /* Entrance animation applied via Alpine x-transition */
}
```

Alpine entrance:
```html
x-transition:enter="transition ease-out duration-200"
x-transition:enter-start="opacity-0 scale-95"
x-transition:enter-end="opacity-100 scale-100"
```
*(Use Alpine's transition classes, not CSS animations, for modals)*

---

### 5.5 Progress Bars

```css
.progress-track {
  background: var(--bg-raised);
  border-radius: 100px;
  height: 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 100px;
  background: linear-gradient(90deg, #3b82f6, #a78bfa);
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Completion state */
.progress-fill--complete {
  background: linear-gradient(90deg, #4ade80, #22d3ee);
}

/* HP bar — battle context */
.progress-fill--hp-high   { background: #4ade80; }
.progress-fill--hp-mid    { background: #facc15; }
.progress-fill--hp-low    { background: #ef4444; }

/* EXP bar — trainer level */
.progress-fill--exp {
  background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
}
```

---

### 5.6 Badges

```css
/* Base badge */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-display);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
}

/* NEW — freshly collected */
.badge--new {
  background: rgba(74, 222, 128, 0.15);
  border: 1px solid #4ade80;
  color: #4ade80;
}

/* DUPE — already owned */
.badge--dupe {
  background: rgba(251, 191, 36, 0.15);
  border: 1px solid #fbbf24;
  color: #fbbf24;
}

/* Rarity badges — use rarity token color */
.badge--rarity {
  background: rgba(var(--rc-rgb, 156,163,175), 0.12);
  border: 1px solid var(--rc, #9ca3af);
  color: var(--rc, #9ca3af);
}
```

---

### 5.7 Rarity Labels & Tags

```css
/* Inline text label */
.rarity-label {
  font-family: var(--font-display);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.rarity-label--common      { color: var(--r-common); }
.rarity-label--uncommon    { color: var(--r-uncommon); }
.rarity-label--rare        { color: var(--r-rare); }
.rarity-label--epic        { color: var(--r-epic); }
.rarity-label--holographic { color: var(--r-holo); }
.rarity-label--full_art    { color: var(--r-full-art); }
.rarity-label--secret_rare { color: var(--r-secret); }
```

For premium rarities (holo+), add shimmer:
```css
.rarity-label--holographic {
  background: linear-gradient(90deg, #fbbf24, #f97316, #fbbf24);
  background-size: 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer-text 2.5s linear infinite;
}

@keyframes shimmer-text {
  0%   { background-position: 200% center; }
  100% { background-position: -200% center; }
}
```

---

### 5.8 Navigation Bar

The nav must feel like a game HUD — not a website header.

```css
.game-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 56px;
  background: rgba(13, 13, 26, 0.92);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-lo);
  display: flex;
  align-items: center;
  padding: 0 var(--space-5);
  gap: var(--space-4);
}
```

**Nav Rules:**
- Logo uses `Chakra Petch 700`
- Active nav item has `--accent-red` underline, NOT background highlight
- Coin display is always visible top-right: `JetBrains Mono` + `🪙` + `--accent-gold`
- Dropdown menus use `--bg-card` + `border: 1px solid var(--border-hi)` + `box-shadow: var(--shadow-lift)`

---

## 6. MOTION & INTERACTION SYSTEM

### Timing Tokens

```css
--ease-out:   cubic-bezier(0.16, 1, 0.3, 1);    /* Settling elements */
--ease-in:    cubic-bezier(0.7, 0, 0.84, 0);     /* Exiting elements */
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1); /* Rewards, confirms */
--ease-sharp:  cubic-bezier(0.4, 0, 0.2, 1);      /* Card flips, transitions */

--dur-fast:   110ms;   /* Hover, color changes */
--dur-std:    220ms;   /* Most transitions */
--dur-reveal: 550ms;   /* Card flips, reveals */
--dur-drama:  900ms;   /* Pack opens, legendary reveals */
```

### Interaction Patterns

**Hover (cards):**
```css
transform: translateY(-4px);
border-color: var(--border-hi);
box-shadow: var(--shadow-lift);
transition: all var(--dur-std) var(--ease-out);
```

**Click feedback (buttons):**
```css
:active { transform: scale(0.96); }
```

**Card flip (pack reveal):**
```css
.card-inner {
  transition: transform var(--dur-reveal) var(--ease-sharp);
  transform-style: preserve-3d;
}
.card-inner.flipped {
  transform: rotateY(180deg);
}
```

**Stagger animation (reveal all):**
```js
cards.forEach((c, i) => {
  setTimeout(() => flip(i), i * 180); // 180ms between each card
});
```

**Entrance (page load):**
```css
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-in {
  animation: fade-up 0.35s var(--ease-out) both;
}
/* Stagger with: animation-delay: calc(var(--i, 0) * 60ms) */
```

### Animation Principles

1. **Settle, don't bounce** — only use bounce easing for rewards/confirmation
2. **Short durations** — fast = snappy = game-like. If it feels sluggish, halve it
3. **One layer at a time** — don't animate scale, opacity, AND transform simultaneously unless it's a premium reveal
4. **Premium reveals get drama** — legendary / holographic cards earn a longer, more complex animation
5. **No CSS animations on every card** — only on triggered events (reveal, hover, select)

### When NOT to animate

- Navigation link color changes
- Text content updates
- Error messages
- Form validation states
- Loading skeletons (use pulse only, no complex transforms)

---

## 7. ENVIRONMENT DESIGN RULES

> ⚠️ This section governs Album pages. These pages must NOT look like grids.

### Core Principle

Each regional album page is a **living environment** — a scene from the Pokémon world. Pokémon silhouettes are placed where they would *actually be found*, not in arbitrary rows.

### Environment Types

| Region | Environment Feel | Palette Accent |
|--------|-----------------|----------------|
| Kanto  | Classic forest + meadows | Warm greens, sunset oranges |
| Johto  | Ancient ruins, bamboo forests | Deep greens, stone grays |
| Hoenn  | Ocean routes, rainforest | Deep blues, turquoise |
| Sinnoh | Snowy peaks, caverns | Ice blues, purples |

### Placement Rules by Type

```
🌊 Water types     → Near water edges, riverbanks, pools
🌿 Grass types     → Hidden in tall grass, near trees
🔥 Fire types      → Rocky outcroppings, volcanic ground
✈️ Flying types    → Upper z-layer, sky positions, treetops
👻 Ghost types     → Shadowed areas, corners, overlapping edges
🪨 Rock/Ground     → Low on the scene, boulder areas
🧊 Ice types       → Elevated, distant, icy ledges
🌙 Dark/Psychic    → Darker corners, forest depths
```

### Scene Layering

```
z-index: 1   → Sky background (gradient, clouds)
z-index: 2   → Distant environment (mountains, horizon)
z-index: 3   → Mid-environment (trees, water)
z-index: 4   → Ground plane
z-index: 5   → Pokémon silhouettes / cards (lower slots)
z-index: 6   → Pokémon silhouettes / cards (upper/flying slots)
z-index: 7   → Fog/atmosphere overlay
z-index: 8   → UI elements (panel, progress bar)
```

### Silhouette Behavior

**Locked / Not Owned:**
```css
filter: brightness(0) opacity(0.25);
/* Shows pure black silhouette — maintains mystery */
```

**Owned but not revealed:**
```css
filter: saturate(0) opacity(0.5);
/* Grayed out — you know it exists but haven't "found" it */
```

**Owned:**
```css
filter: none;
/* Full color sprite with optional idle float animation */
```

**On hover (owned):**
```css
transform: translateY(-6px) scale(1.08);
filter: drop-shadow(0 8px 16px rgba(255,255,255,0.15));
```

### Reveal Animation (on unlock)

```css
@keyframes pokemon-appear {
  0%   { filter: brightness(0) opacity(0.2); transform: scale(0.85); }
  40%  { filter: brightness(0) opacity(1);   transform: scale(1.05); }
  60%  { filter: saturate(0.5) brightness(0.7) opacity(1); transform: scale(1); }
  100% { filter: none; transform: scale(1); }
}
```

### Idle Float (owned Pokémon in scene)

```css
@keyframes idle-float {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-5px); }
}
/* Apply with varied durations per Pokémon: 2.5s–4s, ease-in-out, infinite */
/* Stagger with animation-delay: random between 0–2s */
```

---

## 8. RARITY SYSTEM (VISUAL + UX)

### Rarity Hierarchy

| Rarity | Color | Border | Glow | Card Effect |
|--------|-------|--------|------|-------------|
| Common | `#9ca3af` gray | Subtle | None | Standard |
| Uncommon | `#4ade80` green | Slight | None | Standard |
| Rare | `#60a5fa` blue | Visible | Faint blue | Slight shimmer on hover |
| Epic | `#a78bfa` purple | Glowing | Purple | Shimmer + lift |
| Holographic | `#fbbf24` gold | Animated | Pulsing gold | Full shimmer + sparkles |
| Full Art | `#f97316` orange | Glowing | Warm orange | Pan background effect |
| Secret Rare | `#f43f5e` rose | Animated | Red pulse | Distortion + rainbow |

### Visual Implementation per Rarity

**Rare:**
```css
.card--rare {
  border-color: var(--r-rare);
}
.card--rare:hover {
  box-shadow: 0 0 16px rgba(96, 165, 250, 0.4);
}
```

**Epic:**
```css
.card--epic {
  border-color: var(--r-epic);
  box-shadow: 0 0 10px rgba(167, 139, 250, 0.3);
}
```

**Holographic:**
```css
@keyframes holo-border {
  0%,100% { border-color: #fbbf24; box-shadow: 0 0 14px rgba(251,191,36,0.5); }
  50%      { border-color: #f97316; box-shadow: 0 0 24px rgba(249,115,22, 0.6); }
}

.card--holographic {
  animation: holo-border 2.5s ease-in-out infinite;
}

/* Rainbow tilt effect on hover — CSS only */
.card--holographic:hover {
  background: linear-gradient(
    135deg,
    rgba(251,191,36,0.08),
    rgba(167,139,250,0.08),
    rgba(96,165,250,0.08)
  );
}
```

**Secret Rare:**
```css
@keyframes secret-pulse {
  0%,100% { box-shadow: 0 0 16px rgba(244,63,94,0.5); border-color: #f43f5e; }
  50%      { box-shadow: 0 0 32px rgba(244,63,94,0.9), 0 0 64px rgba(244,63,94,0.2); }
}

.card--secret_rare {
  animation: secret-pulse 1.8s ease-in-out infinite;
}
```

### Pack Reveal — Rarity Escalation Rule

When revealing packs, **common cards reveal instantly** — premium cards get a **delay + longer animation**.

```js
const REVEAL_DELAY = {
  common: 0,
  uncommon: 0,
  rare: 200,          // slight pause before reveal
  epic: 400,          // screen darkens briefly
  holographic: 600,   // full dramatic pause + shimmer entrance
  full_art: 600,
  secret_rare: 800    // maximum drama
};
```

---

## 9. ANTI-PATTERNS (DO NOT DO THESE)

### Layout Anti-Patterns
```
❌ White or light backgrounds anywhere
❌ Centered layout with max-width 700px like a blog post
❌ Flat color blocks with no depth or texture
❌ Symmetrical layouts with equal whitespace everywhere
❌ Standard Bootstrap grid rows and columns
❌ Album pages as uniform grids — Pokémon must be placed naturally
```

### Color Anti-Patterns
```
❌ Using blue (#3b82f6) as a primary action color — that's Tailwind default
❌ Gradient every surface "just to add depth" — earn it
❌ Full opacity white text on colored backgrounds without testing contrast
❌ Gray (#6b7280) as ANY accent — it's for dead/disabled text only
❌ Using more than 3 accent colors on a single screen
❌ Neon green (#00ff00) or neon blue (#0000ff) — too generic gaming
```

### Typography Anti-Patterns
```
❌ Using system-ui / sans-serif — always specify font tokens
❌ All-caps body text — only labels and badges are uppercase
❌ Font size below 0.6rem — minimum legible size
❌ Bold weight for body copy — reserve bold for labels and headings
❌ Light weight (300) for anything in the UI — too fragile on dark bg
```

### Motion Anti-Patterns
```
❌ Infinite spinning loaders for more than 2 seconds
❌ Bounce easing on everything — earned only for rewards
❌ Transition: all — always specify the property
❌ Animating every card simultaneously on page load
❌ Scale animations greater than 1.15 — feels cartoonish
❌ Fade-in duration over 400ms — too slow, feels broken
```

### Component Anti-Patterns
```
❌ Pills / rounded-full buttons everywhere
❌ Generic glassmorphism panels on every surface
❌ Drop shadow on top of glow — pick one
❌ Badges with more than 3 words
❌ Empty state = just text — always include an icon or illustration
❌ Cards without any hover state
❌ Forms that look like a Google Form
```

### Game Feel Anti-Patterns
```
❌ Treating this like a SaaS product — it's a GAME
❌ Overly safe, minimal UI — games are expressive
❌ No feedback on collection milestones — celebrate them
❌ Battle page that looks like a data table
❌ Pack opening with no anticipation or escalation
❌ Rarity labels in the same style as regular text
```

---

## 10. PROMPT TEMPLATE FOR FUTURE CHATS

Copy this block at the start of any Claude session that touches UI:

```
---DESIGN SYSTEM CONTEXT---

This is a Django-based Pokémon-inspired collectible game with a dark anime tactical aesthetic.
The full design system is at DESIGN_SYSTEM.md in the project root — READ IT FIRST before generating any UI.

STACK:
- Django templates (no React/Vue)
- Vanilla CSS with CSS custom properties
- Alpine.js 3.x for interactivity
- HTMX 2.x for server updates
- Google Fonts: Chakra Petch (display), Plus Jakarta Sans (body), JetBrains Mono (mono)

CORE RULES:
1. All CSS uses --tokens from :root (--bg-primary, --accent-red, --r-holo, etc.)
2. Font: Chakra Petch for headings/labels, Plus Jakarta Sans for body, JetBrains Mono for stats
3. Never use Tailwind classes, Bootstrap, or default browser styling
4. Cards must have hover states. Premium rarity cards must glow.
5. Buttons: btn-primary (red), btn-gold (coin actions), btn-ghost (secondary)
6. Animations: fast (110ms hover), standard (220ms transitions), dramatic (550ms+ reveals)
7. Album pages: NO uniform grids — Pokémon placed in environments by type
8. Glows are earned: only holo+, active selections, CTA hover, and reward moments
9. This is a GAME UI — expressive, cinematic, not a dashboard

AESTHETIC REFS: Persona 5, Legends of Runeterra, Pokémon TCG Online, Fire Emblem
MOOD: Cinematic, dark, mysterious, collectible-driven

---END DESIGN SYSTEM CONTEXT---
```

---

## 11. UI REVIEW CHECKLIST

Run this before considering any page "done":

### Visual Quality
- [ ] No light backgrounds anywhere on the page
- [ ] All text uses the correct font family (display/body/mono)
- [ ] Colors come from CSS tokens — no hardcoded hex in new code
- [ ] Rarity labels are properly colored and styled
- [ ] Premium cards (holo+) have appropriate glow
- [ ] Spacing feels deliberate — no random padding values

### Game Feel
- [ ] Does the page feel like part of a game, or a website?
- [ ] Are there visual feedback moments for user actions?
- [ ] Does empty state have personality (icon, flavor text)?
- [ ] Are collection milestones visually celebrated?
- [ ] Do rare/premium items feel special vs. common items?

### Consistency
- [ ] Navigation remains unchanged and functional
- [ ] Button styles match the design system (no custom one-off buttons)
- [ ] Panel/card border-radius uses --radius tokens
- [ ] All shadows use --shadow-card or --shadow-lift

### Interaction Quality
- [ ] All clickable cards have hover states
- [ ] Buttons have :hover AND :active states
- [ ] No CTA without a glow on hover
- [ ] Transitions specified by property (not `transition: all`)
- [ ] Mobile layout tested (nothing overflows at 375px)

### Performance
- [ ] No `backdrop-filter` on more than 2 elements simultaneously
- [ ] Infinite animations only on premium/active elements
- [ ] `will-change: transform` added to animated elements that cause repaints
- [ ] Images use `loading="lazy"` and explicit width/height

### Anti-Pattern Check
- [ ] No Tailwind classes introduced
- [ ] No Bootstrap grid rows
- [ ] No default `font-family: sans-serif`
- [ ] No inline color values (must use CSS tokens)
- [ ] Album page is NOT a uniform grid

---

## 12. ADVANCED — IMPROVEMENT ROADMAP

### CSS Architecture Improvements

**Priority 1: Consolidate page-level `<style>` blocks**

Currently, each template has its own `<style>` block. Over time, extract shared patterns into `base.css` using component classes:

```
base.css
├── :root (tokens)
├── reset
├── typography utilities (.t-display, .t-h1, etc.)
├── layout (.page-container, .reveal-grid, etc.)
├── components (.game-card, .btn, .panel, .badge, etc.)
├── rarity system (.r-* classes)
└── animations (@keyframes library)
```

**Priority 2: CSS `@layer` for specificity control**

```css
@layer base, components, utilities, page;
```

This prevents page-level overrides from fighting component styles.

**Priority 3: Container queries for card components**

```css
@container (min-width: 200px) {
  .game-card__body { padding: var(--space-5); }
}
```

Cards adapt to their grid context, not the viewport.

---

### Alpine.js Patterns for Game UI

**Pattern: Card Reveal with Rarity Escalation**
```js
// In x-data
reveal(i) {
  const card = this.cards[i];
  const delay = { common: 0, uncommon: 0, rare: 200, epic: 400, holographic: 600 };
  setTimeout(() => {
    card.flipped = true;
    if (card.premium) {
      card.shimmer = true;
      setTimeout(() => card.shimmer = false, 900);
    }
  }, delay[card.rarity] || 0);
}
```

**Pattern: Staggered Grid Entrance**
```html
<template x-for="(item, i) in items" :key="item.id">
  <div
    class="game-card animate-in"
    :style="`animation-delay: ${i * 40}ms`"
  >
```

**Pattern: Tooltip on hover**
```html
<div x-data="{ show: false }" @mouseenter="show = true" @mouseleave="show = false">
  <div class="card">...</div>
  <div x-show="show" x-transition class="tooltip">Pokémon info here</div>
</div>
```

---

### HTMX Patterns for Game UI

**Pattern: Live coin balance update after purchase**
```html
<span
  hx-get="/api/user/coins/"
  hx-trigger="purchase-complete from:body"
  hx-swap="innerHTML"
  class="t-mono" style="color: var(--accent-gold);"
>
  {{ user.coins }}
</span>
```

**Pattern: Optimistic UI for album claiming**
```html
<button
  hx-post="/stickers/claim/{{ sticker.id }}/"
  hx-target="#sticker-{{ sticker.id }}"
  hx-swap="outerHTML"
  hx-indicator="#spinner"
>Claim</button>
```

---

### Sound Design (Future Enhancement)

Even subtle audio massively increases game feel. Suggested events:

| Event | Sound Type |
|-------|-----------|
| Card flip | Soft whoosh |
| Common reveal | Soft chime |
| Rare reveal | Rising tone |
| Holographic reveal | Sparkle fanfare |
| Pack purchase | Coin jingle |
| Collection complete | Victory chord |
| Battle win | Triumphant sting |
| Battle loss | Low drone fade |

Implementation: Use the Web Audio API or `<audio>` elements triggered by Alpine.js events. Keep files under 100KB each (short MP3/OGG clips).

---

*End of Design System v1.0*
*Update this document whenever a new component or pattern is established.*
