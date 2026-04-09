# UI/UX Improvement Plan
> Authored: 2026-04-08  
> Status: PENDING REVIEW — do not implement until Luis confirms

---

## Table of Contents

1. [Inspiration References](#1-inspiration-references)
2. [Design System Foundation](#2-design-system-foundation)
3. [Pokédex — Deep Redesign](#3-pokédex--deep-redesign)
4. [Full-Site Page Audit](#4-full-site-page-audit)
5. [Navigation & Shell](#5-navigation--shell)
6. [Implementation Phases](#6-implementation-phases)

---

## 1. Inspiration References

> Check these before confirming the plan — they define the visual direction.

### Pokédex Filtering UI
| Site | URL | What to steal |
|------|-----|----------------|
| **Pokémon Database** | https://pokemondb.net/pokedex/all | Multi-filter bar (type, generation, color); inline image grid; instant JS filtering without page reload. **Closest to what we're building.** |
| **Pokédex.org** | https://pokedex.org | Large card layout; search-as-you-type; smooth animations; minimal chrome. Great card size reference. |
| **Smogon Pokédex** | https://www.smogon.com/dex/sv/pokemon | Left sidebar filters (type, tier, role); persistent filter state; dense-but-scannable list. |
| **PokéAPI Sprites** | https://pokeapi.co/api/v2/pokemon/1 | Shows all sprite variants available (official-artwork is the HD image at ~475×475px). |

### Card Game / Collection UI
| Site | URL | What to steal |
|------|-----|----------------|
| **Hearthstone Card Gallery** | https://hearthstone.blizzard.com/en-us/cards | Multi-select class/type chips (toggleable pills, not dropdown); active chip highlighting. **Exact pattern we want for type filtering.** |
| **Marvel Snap Cards** | https://marvelsnapzone.com/cards/ | Multi-filter with AND/OR logic toggle; card hover reveal; category chips across top. |
| **Pokémon TCG Online** | https://tcg.pokemon.com/en-us/card-dex/ | Large artwork, rarity chips, set/series filter — translates well to our sticker album. |

### Dark-Theme Game Dashboards
| Site | URL | What to steal |
|------|-----|----------------|
| **Pokémon Showdown** | https://play.pokemonshowdown.com | Clean dark battle UI; moveset cards; stat bars; color-coded types. Our battle UI inspiration. |
| **Legends: Arceus Map** | https://www.serebii.net/legendsarceus/areas.shtml | Region-based filtering concept. |
| **PokeMMO** | https://pokemmo.com | Overall dark game aesthetic close to ours. |

### Typography & Fonts  
The GDD specifies: **Chakra Petch** (titles), **Plus Jakarta Sans** (body), **JetBrains Mono** (battle log).  
Currently the project uses `system-ui` — loading these would instantly elevate the look.
- Google Fonts: https://fonts.google.com/specimen/Chakra+Petch
- Google Fonts: https://fonts.google.com/specimen/Plus+Jakarta+Sans

---

## 2. Design System Foundation

### Current State
- `base.css` is 65 lines — extremely lean
- All templates use heavy inline styles (most layout/color is inline)
- No custom JS files — only Alpine.js + HTMX + inline `<script>` tags
- No CSS variables for the color palette (hardcoded hex everywhere)

### What to Fix First (affects everything downstream)

**A) Add CSS custom properties to `base.css`**
```css
:root {
  --bg-primary:   #1a1a2e;
  --bg-card:      #16213e;
  --bg-raised:    #0f3460;
  --accent-red:   #e94560;
  --accent-gold:  #f5a623;
  --combo-blue:   #00d4ff;
  --text-primary: #eee;
  --text-muted:   #9ca3af;
  --text-dim:     #6b7280;
  --border:       #0f3460;
  --border-hover: #e94560;
  --radius-sm:    6px;
  --radius-md:    10px;
  --radius-lg:    16px;
}
```

**B) Load GDD-specified fonts in `base.html`**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
```
Then in CSS:
```css
body      { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
h1, h2, h3 { font-family: 'Chakra Petch', system-ui, sans-serif; }
.battle-log, .combo-log { font-family: 'JetBrains Mono', monospace; }
```

**C) Type color palette as CSS vars** (currently duplicated per-template)
```css
/* Used on type pills, filter chips, card borders */
--type-fire:     #f97316; --type-water:    #3b82f6;
--type-grass:    #22c55e; --type-electric: #eab308;
--type-psychic:  #ec4899; --type-ice:      #67e8f9;
--type-dragon:   #7c3aed; --type-dark:     #374151;
--type-fairy:    #f9a8d4; --type-normal:   #9ca3af;
--type-fighting: #b45309; --type-poison:   #a855f7;
--type-ground:   #ca8a04; --type-flying:   #93c5fd;
--type-bug:      #84cc16; --type-rock:     #78716c;
--type-ghost:    #4c1d95; --type-steel:    #6b7280;
```

---

## 3. Pokédex — Deep Redesign

### Current Problems
1. **Single-select type dropdown** — no multi-select; auto-submits (jarring)
2. **No generation filter** (model has `Generation` M2M, completely hidden)
3. **No region filter** (derivable from gen number: Gen1=Kanto, Gen2=Johto, etc.)
4. **No name search**
5. **No role filter** (`primary_role` field exists: DPS/TANK/SUPPORT/CONTROL/ASSASSIN/BRUISER)
6. **Tiny sprites** (80×80px, pixelated) — looks dated
7. **Cards too small** (minmax 150px) — 6-8 per row on desktop; feels crowded
8. **Only HP + Speed on cards** — 4 other stats hidden
9. **Pagination breaks filter state** (generation/multiple types would need URL param juggling)
10. **No visual count** ("showing 24 of 151")

---

### Redesigned Filter System

#### Filter Bar Layout
```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Search by name...    [Gen ▼]  [Region ▼]  [Role ▼]     │
│                                                              │
│  TYPE FILTER (multi-select chips):                          │
│  [Fire] [Water] [Grass] [Electric] [Psychic] [Ice]         │
│  [Dragon] [Dark] [Fairy] [Normal] [Fighting] [Poison]      │
│  [Ground] [Flying] [Bug] [Rock] [Ghost] [Steel]            │
│                                                              │
│  [✕ Clear All]   Showing 47 of 151 Pokémon    [Type Chart →]│
└─────────────────────────────────────────────────────────────┘
```

#### Type Chip Behavior (Alpine.js, no page reload)
- Each chip is a toggle button — active chips glow with their type color
- Selecting multiple types = OR logic: show Pokémon that have ANY selected type
- Chips styled with the 18 type colors from CSS vars
- Optional: small Pokémon type icon SVG inside each chip

#### Generation + Region Filter (dropdown)
Since Gen and Region are 1:1 in-game, show both labels:
```
Gen 1 — Kanto   (#001–151)
Gen 2 — Johto   (#152–251)
Gen 3 — Hoenn   (#252–386)
Gen 4 — Sinnoh  (#387–493)
...
```

#### Role Filter (dropdown or chips)
```
All Roles | DPS | TANK | SUPPORT | CONTROL | ASSASSIN | BRUISER
```

#### Sort Options (dropdown, right-aligned)
```
Sort by: Pokédex # ▼ | Name | HP | Speed | Attack | Total Stats
```

---

### Redesigned Pokédex Card

Current: 150px min, 80×80 sprite, name + types + 2 stats  
**Proposed: 200px min, 160×160 sprite (2× size), all 6 stat bars**

```
┌────────────────────────┐
│   #025                 │  ← Pokédex number (top-left, dim)
│                        │
│      [160×160 sprite]  │  ← Official artwork via PokeAPI CDN
│                        │     /official-artwork/025.png (475px → scaled 160px)
│   Pikachu              │  ← Name (Chakra Petch bold)
│   ⚡ Electric          │  ← Type pill(s) with icon + color
│                        │
│   ⚔️ CONTROL           │  ← Role badge (subtle)
│                        │
│   HP  ████░░░  45      │
│   ATK ███░░░░  49      │  ← All 6 stats (compact bars, small)
│   SPD ███████  90      │
└────────────────────────┘
```

**Hover state:** card border glows with primary type color (Fire = orange, Water = blue, etc.)  
**Click:** goes to detail page (unchanged)  

Sprite source change:
- Current: `/media/pokemon/sprites/001.png` (local, pixelated)
- Proposed: `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{id}.png`
- Fallback to local pixelated sprite (current behavior) if CDN fails

---

### Filter Without Page Reload (Alpine.js approach)

Because we already have Alpine.js loaded, we can do **client-side filtering on the Pokédex** after an initial page load that fetches ALL Pokémon (no pagination needed for Gen 1 at 151 entries; paginate only for All Gens):

```html
<div x-data="pokedex()" x-init="init()">
  <!-- filter bar -->
  <!-- card grid (x-show on each card based on filter state) -->
</div>

<script>
function pokedex() {
  return {
    search: '',
    selectedTypes: [],   // [] = all; ['Fire', 'Water'] = OR match
    selectedGen: '',
    selectedRole: '',
    sortBy: 'number',
    // ...computed filtered list
  }
}
</script>
```

This eliminates pagination for Gen 1 (151 items) and gives instant filter feedback.  
If all generations are loaded (800+ Pokémon), keep server-side pagination with form submission.

---

## 4. Full-Site Page Audit

### Page: Home (`/`)
**Score: B+**

| Issue | Improvement |
|-------|-------------|
| "Welcome, username!" H1 is generic | Add ranked tier badge + guild tag inline: "Welcome back, [Gold] TrainerName!" |
| Stats row (4 cards) uses `.pokemon-card` | Dedicated `.stat-widget` class with icon, label, big number — remove misuse of pokemon-card |
| AI Battle difficulty select looks like a form field | Style with custom select or 3-button toggle (Easy / Medium / Hard) with color coding |
| No visual indicator of active team | Show 6 mini sprites of current team at top ("Your Team: Pikachu / Charizard / ...") |
| Active events banner is good | Make it pulse/shimmer for "ends soon" events (< 2 hours) |
| PvP card is low-emphasis (grey border) | Give it a blue/electric border to differentiate from AI card |

---

### Page: Pokédex (`/pokemon/`)
**Score: C — Primary redesign target (see Section 3)**

---

### Page: Pokémon Detail (`/pokemon/<id>/`)

**Score: B**

| Issue | Improvement |
|-------|-------------|
| Sprite is large already but might be pixelated | Use official artwork URL (same CDN approach) |
| Stat bars are styled well | Add total base stat sum ("Total: 320") at bottom |
| Move pool table is dense | Group by slot with a tab/accordion (Standard | Chase | Special | Support | Passive) |
| No "Catch" CTA prominence | Button is small; make it a full-width primary CTA if not owned |
| Combo chain info at bottom is good | Add visual chain diagram: if this Pokémon is in your team, show how it connects |
| Type effectiveness section missing | Add a mini 2-row table: "Weak to / Resistant to" using the type chart data |

---

### Page: My Pokémon (`/pokemon/my/`)
**Score: B-**

| Issue | Improvement |
|-------|-------------|
| Cards are small and uniform | Show level prominently; training countdown is buried |
| Training timer is JS-only countdown | Add a circular progress ring (CSS only, no lib needed) showing time remaining % |
| No search or sort | Add name search + sort by: Level, EXP needed, In Training |
| "Sell" button is destructive and prominent | Move to detail page; replace with subtle "···" menu on card |
| No visual distinction between "training" and "ready" | Training cards should have a subtle pulsing border animation |

---

### Page: My Team (`/pokemon/team/`)
**Score: B+**

| Issue | Improvement |
|-------|-------------|
| 6 empty slots look identical | Show empty slots with dashed border + "+" icon; make it obvious they're clickable |
| Combo chain preview panel is good | Add chain "flow diagram": Arrow connectors between chain links (Pokémon A → applies Burn → triggers Pokémon B) |
| No team name | Allow naming the team ("Squad Alpha") — stored on User |
| Slot positions (1–6) aren't visually front vs bench | Show "Front Row" (slots 1–3) and "Back Row" (slots 4–6) labels with the positional damage rule reminder (-20% damage from back row) |

---

### Page: Battle Action (`/game/battle/<id>/action/`)
**Score: B**

| Issue | Improvement |
|-------|-------------|
| Move buttons are plain `<button>` elements | Style each move button with its move type color + slot label (Standard/Chase/etc.) |
| HP bars update but no animation | Animate HP bar reduction (CSS transition is already there; ensure it fires) |
| Combo chain log uses JetBrains Mono (correct) | Add chain link icons between entries: ⛓️ Link 2 → ⛓️ Link 3 |
| Switch/Attack toggle is text only | Give toggle buttons distinct visual states (active/inactive) with color |
| No round countdown | Show current round number prominently |

---

### Page: Sticker Album (`/stickers/album/`)
**Score: B+** (recently overhauled in P4-4)

| Issue | Improvement |
|-------|-------------|
| Silhouettes for missing stickers are good | Add a subtle "sparkle" CSS animation on duplicate stickers |
| Stats row at top is good | Add completion percentage ring (SVG circle with stroke-dasharray) |
| Alpine.js filter (All/Missing/Complete/Search) is good | Add rarity filter chips along top (Common / Uncommon / Rare / etc.) |
| No "dismantle all duplicates" quick action | Add a "Convert Duplicates → Dust" button in the stats row |

---

### Page: Quests (`/quests/`)
**Score: B-**

| Issue | Improvement |
|-------|-------------|
| Quest list is a flat list | Group by type with sticky headers: 📅 Daily / 📆 Weekly / 📖 Story |
| Progress bars exist but no percentage | Show "3/5" fraction alongside bar |
| Story quests show narrative_text but inline | Give story quests an "Act" card layout with chapter number as large decorative text |
| Completed quests are still in list | Add a "Completed Today" collapsible section at bottom |

---

### Page: Ranked Home (`/ranked/`)
**Score: B-**

| Issue | Improvement |
|-------|-------------|
| Tier display is text-only | Add tier badge icon (Bronze shield, Silver, Gold crown, etc.) using CSS shapes or emoji |
| LP bar exists but thin | Make LP bar thicker and show tier thresholds as markers |
| Win/loss record text-only | Add a win streak counter badge if > 0 |

---

### Page: Leaderboard (`/ranked/leaderboard/`)
**Score: B**

| Issue | Improvement |
|-------|-------------|
| 3 tabs (Wins/Combo/Season) | Highlight current user's row with `--accent-red` background tint |
| Ranks 1/2/3 | Add 🥇🥈🥉 to top 3 rows |
| Table is purely text | Add sparkline/mini bar for stat values |

---

### Page: Guild List & Detail (`/guilds/`)
**Score: B-** (new in P4-5)

| Issue | Improvement |
|-------|-------------|
| Guild list is plain cards | Show member avatar stack (up to 5 mini profile letters/initials) |
| Guild detail page | Add a "Guild War" teaser section (greyed out, "Coming Soon") per GDD |
| Rank/role labels text-only | Leader = 👑, Officer = ⭐, Member = default |

---

### Page: Events (`/events/`)
**Score: B+**

| Issue | Improvement |
|-------|-------------|
| Event list is good | Add countdown timer per event (Alpine.js, reuse existing countdown logic from my_pokemon.html) |
| Event type (BONUS_RYO etc.) shown as raw text | Map to human labels: BONUS_RYO → "+Ryo Boost", DOUBLE_COMBO_DUST → "Double Dust Weekend" |

---

### Page: Trainer Profile (`/users/<username>/`)
**Score: B**

| Issue | Improvement |
|-------|-------------|
| Achievement badge grid is good | Locked badges should be dark/greyed silhouette, not hidden |
| Stats text-only | Add visual sparkline or radar chart (CSS-only hexagon stat web for the 5 stats) |
| "Recent Battles" section | Color-code W/L rows (green tint / red tint) |

---

### Page: Registration / Login (`/login/`, `/register/`)
**Score: C**

| Issue | Improvement |
|-------|-------------|
| Plain form with no branding | Add the logo and a tagline ("Master the Kizuna Method") above the form |
| No visual error state styling | Input borders should turn red on error, green on success |
| Login page is minimal | Add a short feature highlight below the form (3 icons: ⚔️ Battle / 🃏 Collect / 🔗 Combo) |

---

### Page: Type Chart (`/pokemon/types/`)
**Score: A-**
Best-looking page. Minor improvement: highlight the hovered row/column with a semi-transparent overlay to make reading easier.

---

### Page: Landing (`/`)
**Score: B+**
Already has a dedicated CSS file. Main improvement: add the font stack (Chakra Petch for the hero title).

---

## 5. Navigation & Shell

### Current Nav Problems
- Too many links in one row — wraps on < 1100px wide screens
- No active-page highlighting (current page link looks same as others)
- Logo image (150×150px) is too large — shrinks the nav height
- Ryo button and Logout are inline-styled differently from nav links
- No mobile hamburger menu

### Proposed Nav Improvements

| Fix | How |
|-----|-----|
| Active page indicator | `{% url 'pokemon:pokedex' %}` == `request.path` → add `.active` class |
| Logo size | Reduce to 40×40px or use text logo "PCB" in Chakra Petch |
| Group nav links into sections | Main: Home, Battles, Ranked / Social: Guilds, Leaderboard, Watch / Collect: Pokédex, My Pokémon, Album, Trade, Events, Quests |
| Mobile hamburger | Alpine.js `x-data="{open:false}"` toggle — already have Alpine loaded |
| Ryo balance | Keep as-is (it's already a good design) |

---

## 6. Implementation Phases

> Each phase = one coding session. Confirm this plan before starting P-UI-1.

### P-UI-1: Design System Foundation *(do first — everything else builds on it)*
- [ ] Add CSS variables to `base.css`
- [ ] Load GDD fonts (Chakra Petch + Plus Jakarta Sans + JetBrains Mono) in `base.html`
- [ ] Update `base.css` to use font families
- [ ] Add type color CSS vars
- [ ] Reduce nav logo to 40px
- [ ] Add active-page highlight to nav links
- [ ] Estimated: 4 new CSS rules, no template logic changes

### P-UI-2: Pokédex Redesign *(highest user-visible impact)*
- [ ] Backend: update `PokedexView` to pass `generations` and support multi-type + gen + role query params
- [ ] Backend: add `by_role()` and `by_generation()` to `PokemonQuerySet`
- [ ] Template: full filter bar with type chips (Alpine.js), gen/region dropdown, role dropdown, name search
- [ ] Template: increase card size (200px min), sprites to 160×160, official artwork CDN
- [ ] Template: all 6 stat bars on card
- [ ] Template: hover border color = primary type color
- [ ] Template: "Showing X of Y" count
- [ ] Tests: 8–10 new tests for filter combinations

### P-UI-3: Home + Shell Polish
- [ ] Home: team preview (6 mini sprites of current team)
- [ ] Home: redesign stat widgets with icons
- [ ] Home: AI difficulty as 3-button toggle
- [ ] Nav: mobile hamburger (Alpine.js)
- [ ] Nav: active page highlight
- [ ] Nav: grouping/overflow handling

### P-UI-4: Battle UI + My Pokémon
- [ ] Battle: type-colored move buttons
- [ ] Battle: slot labels on moves
- [ ] Battle: round counter display
- [ ] My Pokémon: training progress ring (CSS)
- [ ] My Pokémon: name search + sort
- [ ] My Team: Front Row / Back Row labels

### P-UI-5: Profile, Quests, Guild, Events
- [ ] Profile: locked badges as greyed silhouettes
- [ ] Quests: grouped headers (Daily/Weekly/Story)
- [ ] Quests: completed collapsible section
- [ ] Events: countdown timers per event
- [ ] Events: human-readable event type labels
- [ ] Guild: role icons (👑 ⭐)

### P-UI-6: Login/Register + Type Chart + Minor Polish
- [ ] Login/Register: branding, error/success input states, feature highlights
- [ ] Type chart: row/column hover highlight
- [ ] Leaderboard: top-3 medals, user row highlight
- [ ] Ranked: tier badge icon shapes

---

## Decisions Made (2026-04-08)

1. **Multi-type filter**: OR logic — selecting Electric + Grass shows all Electric, all Grass, and dual-type combos. ✅
2. **Image source**: Local `/media/pokemon/sprites/` (475×475 originals), displayed at 160×160. ✅
3. **Client-side filtering**: Alpine.js, no pagination for Gen 1 (151 Pokémon). ✅
4. **Card info**: Image, number, name, gen, types only — no stats on cards. ✅
5. **P-UI-2 (Pokédex)** implemented first. Remaining phases pending Luis confirmation.
