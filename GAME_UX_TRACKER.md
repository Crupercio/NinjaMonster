# Pokemon Amigo — UX/UI Improvement Tracker
> **For AI continuity**: This file is the single source of truth for all planned UX/UI work.
> If you are a new AI session picking this up, read this entire file before touching any code.
> Mark tasks `[x]` when complete. Add notes under each task as needed.

---

## Project Context

**App:** Pokemon Amigo — Django 5 + Django Channels + Alpine.js + HTMX  
**Stack:** Python/Django backend, vanilla JS + Alpine.js frontend, hand-written CSS  
**Theme:** Dark luxury arcade — navy/gold/purple (see Design System section below)  
**Mini Games:** Silhouette Tower, Sticker Memory, Pokemon Loteria  
**Battle system:** DEPRECATED — do not touch battle templates or views  
**Key files:**
- `templates/base.html` — global layout, nav, shared JS blocks
- `static/css/base.css` — all global styles, CSS variables
- `static/css/theme.css` — theme overrides
- `static/js/games.js` — shared game JS (CREATE THIS — Phase 1A)
- `templates/game/fun_hub.html` — arcade home
- `templates/game/silhouette_tower.html` — Silhouette Tower play screen
- `templates/game/silhouette_hub.html` — tower selector
- `templates/game/memory_game.html` — Memory Game play screen
- `templates/game/memory_hub.html` — board selector
- `templates/game/loteria_room.html` — Loteria live play (most complex)
- `templates/game/loteria_lobby.html` — Loteria pre-game
- `templates/game/loteria_hub.html` — Loteria deck selector
- `templates/game/loteria_results.html` — Loteria results/claim
- `templates/game/coming_soon_game.html` — placeholder template

---

## Design System (DO NOT DEVIATE FROM THIS)

### Color Palette
```css
--bg-void:     #0b1628   /* deepest background */
--bg-base:     #0e0e20   /* page background */
--bg-felt:     #172040   /* card surface */
--bg-card:     rgba(25,38,78,.96)
--accent-gold: #e8b84b   /* primary accent — headers, highlights, CTAs */
--accent-purple: #a78bfa /* secondary accent — subtitles, special states */
--text-1:      #f1f5f9   /* primary text */
--text-2:      #94a3b8   /* secondary text */
--text-3:      #64748b   /* muted text */
--border-dim:  rgba(91,129,255,.22)
```

### Rarity Colors
```
Common:      #9ca3af  (gray)
Uncommon:    #4ade80  (green)
Rare:        #60a5fa  (blue)
Epic:        #a78bfa  (purple)
Prismatic:   #e879f9  (pink)
Full Art:    #f97316  (orange)
Secret Rare: #f43f5e  (red)
```

### Typography
- Headers/UI labels: `Chakra Petch` — uppercase, bold, letter-spacing
- Body/descriptions: `Plus Jakarta Sans`
- Numbers/data: `JetBrains Mono`

### Border Radius
- Cards/panels: 20–26px
- Buttons: 10–14px
- Badges/pills: 999px (fully rounded)
- Small elements: 6–12px

### Animations
- Micro-interactions: 0.15s ease
- Card flips: 0.45–0.55s cubic-bezier
- Transitions between states: 0.3s ease
- Entrance animations: 0.4–0.6s ease-out
- Rarity shimmer: 0.8s — gold glow pulse
- Holo sweep: 2.5s infinite

### Component Patterns
- Panels: `background: linear-gradient(180deg, rgba(25,38,78,.96), rgba(12,18,38,.96)); border: 1px solid rgba(91,129,255,.22); border-radius: 26px; box-shadow: 0 20px 40px rgba(0,0,0,.28);`
- Gold kicker text: `color: var(--accent-gold); text-transform: uppercase; letter-spacing: .18em; font-size: .72rem; font-weight: 700;`
- Meta boxes: `border-radius: 16px; border: 1px solid rgba(232,184,75,.14); background: rgba(10,15,29,.48);`

---

## Sound Design Plan

### Approach: Web Audio API + Web Speech API (zero dependencies, zero files)

**Web Audio API** (in `static/js/games.js`) generates all game sounds programmatically:
- No audio files to host or manage
- Instant, no network latency
- Works offline
- Fully customizable pitch/duration/waveform

**Web Speech API** (browser `speechSynthesis`) calls Pokemon names in Loteria:
- Speaks any text string aloud using device TTS voice
- Covers ALL 905 Pokemon names without pre-recording
- Zero files, zero cost
- Can adjust pitch/rate/volume
- Works on all modern browsers (Chrome, Firefox, Safari, Edge)
- Fallback: if speechSynthesis unavailable, show name visually with no audio

### Sound Map
| Event | Sound Type | Parameters |
|-------|-----------|-----------|
| Button click | Tick | freq:800, dur:0.06 |
| Card flip (Memory) | Whoosh | sweep 400→200hz, dur:0.2 |
| Match found | Chime up | 523→659→784hz arpeggio |
| Mismatch | Buzz | freq:180, dur:0.25 |
| Correct answer (Silhouette) | Ding + Ryo | 880hz then 1046hz, dur:0.3 |
| Wrong answer (Silhouette) | Low buzz | freq:150, dur:0.4 |
| Cash out / Ryo earned | Coin series | 4-note ascending jingle |
| Rare card reveal | Shimmer | high freq sweep + reverb sim |
| Secret Rare reveal | Fanfare | full ascending chord arpeggio |
| Game complete | Victory | 5-note fanfare |
| Loteria draw | Spoken name | speechSynthesis |
| Loteria win pattern | Cheer | multi-tone burst |
| Sticker placed | Lock click | short high tick |
| Dust earned | Sparkle | descending high notes |

---

## Phase 1 — Sensation Layer
**Goal:** Make every interaction feel alive. Highest ROI, touches all games.  
**Estimated effort:** 3–5 days

### 1A — Shared Sound Engine `static/js/games.js` ✅
- [x] Create Web Audio API context manager (lazy init on first user gesture)
- [x] Implement `GameSounds.play(type)` function with all sound types
- [x] Implement `GameSounds.speak(name)` using Web Speech API for Loteria
- [x] Add volume control + mute toggle (persisted in localStorage)
- [x] Loaded in `base.html` via `<script src="{% static 'js/games.js' %}"></script>`

### 1B — Silhouette Tower Sounds ✅
- [x] Correct answer → play 'correct' sound + Ryo float-up animation
- [x] Wrong answer → play 'wrong' buzz
- [x] Cash out form submit → play 'coin' jingle
- [x] Floor advance (auto-advance) → play 'floorUp' with 300ms delay before submit
- [x] Victory (tower cleared) → fanfare + screen flash

### 1C — Memory Game Sounds + Matched Pair Celebration ✅
- [x] Card flip → 'flip' whoosh sound
- [x] Match found → 'match' chime + bounce animation (`.matched` class)
- [x] Mismatch → 'mismatch' buzz + red flash animation (`.mismatch-flash` class)
- [x] Timer warning (last 10s before speed target) → urgent 'tick' sound each second
- [x] Game complete → 'victory' fanfare + victory-flash overlay
- [x] Streak ≥ 3 → showToast "X in a row! 🔥"

### 1D — Loteria Pokemon Name TTS ✅
- [x] On each new card draw: `GameSounds.speak(pokemon.name)` fires with 250ms delay
- [x] Visual draw animation: `.loteria-draw-new` on call name element
- [x] Mute button in bottom-right (global, persists via localStorage)
- [x] Pattern win → play 'loteriaWin' cheer + speak "¡Loteria!" + victory flash

### 1E — Button Press + Card Hover CSS ✅
- [x] All `.btn` get stronger `active` press state (`scale(0.95)`)
- [x] Game cards on Fun Hub get hover lift (`translateY(-5px)` + shadow)
- [x] Sticker/album cards get hover lift
- [x] Memory game cards get pre-flip hover scale hint
- [x] Ryo float-up animation keyframes added
- [x] Loteria draw-in animation keyframes added
- [x] Match bounce, mismatch flash, victory flash, near-miss pulse keyframes

### 1F — Unified Toast System ✅
- [x] `<div id="toast-stack">` in `base.html` (top-right fixed)
- [x] CSS: slide-in from right (280ms cubic-bezier), stack vertically, auto-dismiss 3.5s
- [x] 4 variants: success (green), warning (gold), error (red), info (blue)
- [x] `window.showToast(message, type)` global function
- [x] Django messages auto-rendered as toasts on DOMContentLoaded
- [x] Hover-to-pause auto-dismiss timer

---

## Phase 2 — Feedback & Context
**Goal:** Players understand what's happening and feel persistent progress.  
**Estimated effort:** 4–6 days

### 2A — Personal Bests on Hub Pages ✅
- [x] Silhouette Hub: shows best floor + Ryo per tower (localStorage)
- [x] Memory Hub: shows best grade + turns + Ryo per board (localStorage)
- [x] Saved on cash-out, wrong answer, cleared (Silhouette) and finishBoard (Memory)

### 2B — Silhouette Run History Panel ✅
- [x] Shows last 8 answers as chips (sprite + ✓/✗ + name) below the game grid
- [x] Persisted in localStorage per tower key, cleared 3s after run ends
- [x] Records correct/wrong status and floor number

### 2C — Memory Grade Screen Redesign ✅
- [x] Animated Ryo counter (easeOutCubic, 1200ms) 
- [x] Animated Dust counter (900ms)
- [x] Coin + dust sounds fire on grade screen load
- [x] Grade emoji prefix (⭐ Perfect, ✨ Great, 👍 Good, ✓ Clear)
- [x] Speed bonus badge shown if applicable
- [x] Grade color-coded (gold/green/blue/gray)
- [x] Upgrade CTA: "Try Standard/Collector/Master Board ↑" (based on current board)

### 2D — Loteria Rules Modal ✅
- [x] "❓ How to Play" button on Loteria Hub hero
- [x] CSS-drawn pattern diagrams for all 4 patterns (Chorro, Centrito, Cuatro Esquinas, Buena)
- [x] Explains board building mechanic (Level 20+ Pokemon)
- [x] Auto-shows on first visit (localStorage `loteria_rules_seen` flag)
- [x] Click outside or ✕ to close
- [x] CTA: "Build My Board" link

### 2E — Session Recovery Prompt ✅ (was already in fun_hub.html)
- [x] Active run shown in hero-actions on Silhouette Hub

### 2F — Loteria Near-Miss Indicator ✅
- [x] Live chip showing "X cells left / X cells from Buena / 🔥 1 cell from Buena!"
- [x] Gold pulsing border on boards when 1 cell away (`board-near-miss` CSS class)
- [x] Updates on every state sync (every ~4s)

---

## Phase 3 — Social & Depth
**Goal:** Make Loteria feel live, give all games replayability hooks.  
**Estimated effort:** 1–2 weeks

### 3A — Loteria WebSocket Upgrade
- [ ] Replace 4-second polling with Django Channels consumer
- [ ] Infrastructure already exists (Redis + Channels for old battle system)
- [ ] New consumer: `LoteriaRoomConsumer` in `apps/game/consumers.py`
- [ ] Broadcast: new_draw, pattern_won, room_closed events
- [ ] Client: connect on room load, handle events in JS

### 3B — NPC Activity in Loteria Room
- [ ] Fake "NPC marked a cell" events in the room feed
- [ ] NPCs react with emoji when they get close to winning
- [ ] Simple server-side simulation during draw ticks

### 3C — Daily Challenge Widget on Fun Hub
- [ ] `DailyChallenge` model (or hardcoded rotating challenges)
- [ ] 2-task challenge on Fun Hub: e.g., "Reach Floor 5 + Play 1 Memory game → +200 Ryo bonus"
- [ ] Progress shown as checkboxes with strikethrough on complete

### 3D — Leaderboard Strips on Hub Pages
- [ ] Top 3 scores today/this week per game
- [ ] Silhouette Hub: "Floor reached" leaderboard
- [ ] Memory Hub: "Fewest turns on Master Board"
- [ ] Loteria Hub: "Biggest pot won"

### 3E — Quest Integration
- [ ] Wire mini-game completions to quest system
- [ ] Sample quests: "Play 1 Loteria round", "Reach Silhouette Floor 5", "Perfect a Memory board"
- [ ] Add quest-check calls in `fun_views.py` at game completion points

---

## Phase 4 — Polish & Engagement
**Goal:** Long-term retention, visual personality, collectible identity.  
**Estimated effort:** Ongoing

### 4A — Fun Hub Redesign
- [ ] Featured game slot (rotates daily or by engagement) — visually larger
- [ ] "Active players now" count on Loteria card (even if cached/fake for now)
- [ ] Candy wallet shows "earn candy" tip if empty
- [ ] Coming Soon card: animated "???" silhouette teaser with lock icon

### 4B — Coming Soon Game Teaser
- [ ] Replace static coming_soon_game.html with animated locked card
- [ ] Blurred/silhouette logo with "???" text
- [ ] "Stay tuned" message with flavor text
- [ ] Could hint at next game (e.g., "Something competitive is coming...")

### 4C — Memory Mascot Personalities
- [ ] Each board's mascot character has a name + catchphrase
- [ ] Shown on hub card AND grade screen
- [ ] Mascot reacts visually to game events (GIF swap)

### 4D — Silhouette Tower Visual Themes
- [ ] Rookie Tower: bright/sunny theme (light overlay)
- [ ] Regional Tower: forest/nature theme (green tones)
- [ ] Master Tower: cave/dark theme (blue-black)
- [ ] National Tower: cosmic/space theme (deep purple + stars)
- [ ] Each theme: different CSS background gradient on the floor backgrounds

### 4E — Daily Login Ritual
- [ ] First visit modal (slides up from bottom)
- [ ] Shows streak (7-day calendar dots)
- [ ] "Day X streak! You earned Y Ryo + Z pack"
- [ ] Animated coin drop on claim

---

## Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 — Sensation Layer | ✅ Complete | 6/6 tasks |
| Phase 2 — Feedback & Context | ✅ Complete | 6/6 tasks |
| Phase 3 — Social & Depth | ⏳ Pending | 0/5 tasks |
| Phase 4 — Polish & Engagement | ⏳ Pending | 0/5 tasks |

---

## Implementation Notes for AI Sessions

### Adding sounds to a template
```html
<!-- At bottom of template, inside {% block extra_js %} -->
<script>
// Sounds fire via global window.GameSounds from static/js/games.js
// Available: playSound('correct'|'wrong'|'coin'|'flip'|'match'|'mismatch'|'victory'|'rare'|'secret'|'click'|'place'|'dust')
// For Loteria: speakPokemon('Charizard')
</script>
```

### Toast system usage
```html
<!-- Trigger from JS: -->
showToast('You earned 450 Ryo!', 'success')
showToast('Not enough dust', 'error')
showToast('Pattern complete!', 'warning')  // warning = gold
showToast('New card drawn', 'info')
```

### CSS class conventions
- `.btn` — base button (all buttons must have this)
- `.btn-primary` — gold fill button
- `.btn-secondary` — outline button
- `.btn-sm` — small variant
- `.btn-disabled` — disabled state (opacity .55, pointer-events none)
- `.game-card` — arcade game cards on fun_hub
- `.msg` — inline message (success/error/info variants)

### Django messages → Toast migration
Replace `{% if messages %}...{% endif %}` blocks with:
```html
{% for msg in messages %}
<script>showToast("{{ msg }}", "{{ msg.tags|default:'info' }}")</script>
{% endfor %}
```
(after toast system is built in base.html)

---

## Known Issues / Decisions

- Battle system is deprecated — do NOT modify any `battle_*.html` templates or `BattleView` etc.
- Loteria currently uses 4-second polling — WebSocket upgrade is Phase 3A, not urgent
- NPC names list in `fun.py` has only 6 names — expand to 20+ when doing Phase 3B
- Memory and Loteria have zero test coverage — add tests in `tests/test_game/` after each phase
- `_build_loteria_board_cards` has unreachable code after `continue` statement (line ~280 in fun_views.py) — fix when touching that file
- Nav still references "battle" in path checks (e.g., `/battle/fun/silhouette`) — this is the URL prefix, NOT the deprecated battle system. Do not change URLs.
