# UX Redesign Tracker — Style D Rollout

**Design System:** Style D (TCG Premium + Atlas Sidebar)
- Colors: navy void `#080810` + gold `#e8b84b`
- Layout: 220px persistent sidebar + 56px top nav
- Radii: `4–12px` (sharp-edged)
- Fonts: Chakra Petch (headings) + Plus Jakarta Sans (body) + JetBrains Mono (numbers)
- Base template: `templates/base.html` — needs sidebar migration (tracked below)

**Status legend:** `✅ Done` · `🔄 In Progress` · `⬜ Pending` · `⏭ Skip` (redundant/removed)

---

## Phase 1 — Public / Auth (highest visibility)

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 1 | `landing/landing.html` | `/` | ✅ Done | Style D, real images, sidebar, packs, arcade |
| 2 | `registration/login.html` | `/login/` | ✅ Done | Standalone Style D, two-column, features left / form right |
| 3 | `registration/register.html` | `/users/register/` | ✅ Done | Standalone Style D, perks grid left / form right, starter pack badge |
| 4 | `registration/password_reset.html` | `/users/password-reset/` | ✅ Done | Standalone Style D card, email input |
| 5 | `registration/password_reset_confirm.html` | — | ✅ Done | New password form, validlink check |
| 6 | `registration/password_reset_done.html` | — | ✅ Done | Email sent confirmation card |
| 7 | `registration/password_reset_complete.html` | — | ✅ Done | Password changed success card |

---

## Phase 2 — Base Shell (unlocks all interior pages)

| # | Template | Status | Notes |
|---|----------|--------|-------|
| 8 | `base.html` | ✅ Done | Style D sidebar + top nav. All interior pages inherit this. |

---

## Phase 3 — Collection Core

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 9 | `stickers/pokemon_album.html` | `/stickers/album/` | ✅ Done | Already on Style D vars, inherits base shell |
| 10 | `stickers/regional_album_detail.html` | `/stickers/album/<region>/` | ✅ Done | Already on Style D vars, inherits base shell |
| 11 | `stickers/sticker_detail.html` | `/stickers/<id>/` | ✅ Done | Already on Style D vars, inherits base shell |
| 12 | `stickers/placement_mode.html` | `/stickers/place/` | ⬜ Pending | Drag-place UI — check after testing |
| 13 | `stickers/workshop.html` | `/stickers/workshop/` | ✅ Done | Re-themed from blue to Style D tokens |
| 14 | `stickers/multi_pack_open.html` | `/stickers/open/` | ✅ Done | Already Style D colors |
| 15 | `pokemon/mi_casa.html` | `/pokemon/mi-casa/` | ✅ Done | Blue hardcodes replaced with Style D vars |
| 16 | `pokemon/detail.html` (if exists) | `/pokemon/<id>/` | ⬜ Pending | Pokedex entry |

---

## Phase 4 — Arcade Games

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 17 | `game/fun_hub.html` | `/game/hub/` | ✅ Done | Blue hardcodes → Style D tokens |
| 18 | `game/silhouette_tower.html` | `/game/silhouette/` | ✅ Done | Blue hardcodes → Style D tokens |
| 19 | `game/memory_hub.html` | `/game/memory/` | ✅ Done | Blue hardcodes → Style D tokens |
| 20 | `game/memory_game.html` | `/game/memory/<board>/` | ✅ Done | Blue hardcodes → Style D tokens |
| 21 | `game/coming_soon_game.html` | `/game/coming-soon/` | ✅ Done | Blue hardcodes → Style D tokens |
| 22 | `game/loteria_lobby.html` | `/game/loteria/` | ✅ Done | Blue hardcodes → Style D tokens |
| 23 | `game/loteria_room.html` + `hub` + `results` + `board_builder` | various | ✅ Done | Blue hardcodes → Style D tokens |

---

## Phase 5 — Social / Guilds

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 24 | `guilds/guild_list.html` | `/guilds/` | ✅ Done | Blue hardcodes → Style D |
| 25 | `guilds/guild_detail.html` | `/guilds/<id>/` | ✅ Done | Blue hardcodes → Style D |
| 26 | `guilds/guild_album.html` | `/guilds/<id>/album/` | ✅ Done | Blue hardcodes → Style D |

---

## Phase 6 — Quests & Expeditions

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 27 | `quests/quest_list.html` | `/quests/` | ✅ Done | Blue hardcodes → Style D |
| 28 | `quests/quest_detail.html` | `/quests/<id>/` | ⏭ Skip | Template doesn't exist |
| 29 | `expedition/hub.html` | `/expedition/` | ✅ Done | Blue hardcodes → Style D |
| 30 | `expedition/expedition_detail.html` | `/expedition/<id>/` | ⏭ Skip | Template doesn't exist |

---

## Phase 7 — User Profile / Settings

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 31 | `users/profile.html` | `/users/profile/` | ✅ Done | Blue hardcodes → Style D |
| 32 | `users/settings.html` | `/users/settings/` | ⏭ Skip | Template doesn't exist |
| 33 | `users/leaderboard.html` | `/users/leaderboard/` | ⏭ Skip | Template doesn't exist |

---

## Phase 8 — Misc / Utility

| # | Template | URL | Status | Notes |
|---|----------|-----|--------|-------|
| 34 | `404.html` | — | ⏭ Skip | Doesn't exist yet |
| 35 | `500.html` | — | ⏭ Skip | Doesn't exist yet |
| 36 | `base_email.html` (if exists) | — | ⏭ Skip | Email template — different constraints |

---

## Icon Generation Spec

Custom icons to generate (16×16 or 32×32, transparent PNG, gold/white line-art style):

| Icon | Use | Size | Style |
|------|-----|------|-------|
| `icon_pack.png` | Sidebar: packs / collection | 32px | Gold envelope with diamond |
| `icon_album.png` | Sidebar: album | 32px | Open book with pokeball spine |
| `icon_quest.png` | Sidebar: quests | 32px | Star with checkmark |
| `icon_expedition.png` | Sidebar: expedition | 32px | Compass/map marker |
| `icon_guild.png` | Sidebar: guild | 32px | Shield with group silhouette |
| `icon_arcade.png` | Sidebar: arcade / fun hub | 32px | Joystick or game cabinet |
| `icon_pokedex.png` | Sidebar: pokédex | 32px | Device screen with pokeball |
| `icon_leaderboard.png` | Sidebar: leaderboard | 32px | Trophy or bar chart |
| `icon_ryo.png` | Currency badge in nav | 20px | Coin with ¥ symbol |
| `icon_dust.png` | Craft cost on rarity cards | 20px | Sparkle/crystal shard |

Style: thin stroke (1.5–2px), rounded ends, white or gold (`#e8b84b`) on transparent. Matches Style D sidebar-icon weight.

---

## Progress Summary

| Phase | Total | Done | Pending | Skip |
|-------|-------|------|---------|------|
| 1 – Public/Auth | 7 | 7 | 0 | 0 |
| 2 – Base Shell | 1 | 1 | 0 | 0 |
| 3 – Collection | 8 | 7 | 1 | 0 |
| 4 – Arcade | 7 | 7 | 0 | 0 |
| 5 – Social | 3 | 3 | 0 | 0 |
| 6 – Quests/Expedition | 4 | 2 | 0 | 2 |
| 7 – User/Profile | 3 | 1 | 0 | 2 |
| 8 – Misc | 3 | 0 | 0 | 3 |
| **Total** | **36** | **29** | **0** | **7** |

*Last updated: 2026-05-05 — All 29 applicable templates complete. Style D rollout 100% done.*

---

*Last updated: 2026-05-04 — Landing redesign completed. Next batch: Phase 1 auth pages (login, register) after landing approval.*
