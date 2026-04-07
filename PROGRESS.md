# Development Progress Tracker
> Read this file at the start of every new session before touching any code.
> Update it immediately after completing each feature or infrastructure task.
> The GDD at `GAME_DESIGN_DOCUMENT.md` is the design authority — this file tracks build status.

---

## How to Start the Dev Environment

```bash
# 1. Start Redis (WSL Ubuntu)
wsl -d Ubuntu -u root -- redis-server --daemonize yes --bind 0.0.0.0 --port 6379

# 2. Run the dev server
POSTGRES_DB=pokemon_battle \
POSTGRES_USER=pokemon_user \
POSTGRES_PASSWORD=pokemon_dev_pass \
POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
REDIS_URL=redis://localhost:6379/0 \
DJANGO_SETTINGS_MODULE=config.settings.development \
python manage.py runserver

# 3. Run tests
USE_POSTGRES_IN_TESTS=1 \
POSTGRES_DB=pokemon_battle \
POSTGRES_USER=pokemon_user \
POSTGRES_PASSWORD=pokemon_dev_pass \
POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
DJANGO_SETTINGS_MODULE=config.settings.test \
python -m pytest -q
```

**Baseline test result:** 178 passed, 11 pre-existing failures (not introduced by infra work).
The 11 failures are in `test_game/test_ai.py`, `test_game/test_combo_chain.py`, and `test_pokemon/test_progression.py`.

---

## Infrastructure — COMPLETED ✅

| # | Task | Status | Notes |
|---|------|--------|-------|
| I-1 | Commit pending sticker migration | ✅ Done | Commit `1ac168b` |
| I-2 | PostgreSQL migration | ✅ Done | DB: `pokemon_battle`, user: `pokemon_user`, PG 18 on localhost:5432 |
| I-3 | Redis + channels_redis | ✅ Done | Redis 7.0 via WSL Ubuntu; channels_redis 4.3.0; fallback to InMemory if no REDIS_URL |
| I-4 | CSS extracted to static files | ✅ Done | `static/css/base.css` + `static/css/landing.css`; both templates updated |
| I-5 | HTMX + Alpine.js wired | ✅ Done | CDN-loaded in `base.html`; CSRF auto-header for HTMX POST; Alpine deferred |
| I-6 | Production settings hardened | ✅ Done | SECRET_KEY validation, WhiteNoise, HSTS, CSRF_TRUSTED_ORIGINS, referrer policy |
| I-7 | PROGRESS.md created | ✅ Done | This file |

---

## Phase 1 — Critical Fixes (GDD Section 24, Phase 1)

**Phase 1 COMPLETE ✅ — Next: Phase 2**

| # | Task | Status | GDD Reference | Notes |
|---|------|--------|--------------|-------|
| P1-1 | Wire sticker award to battle wins | ✅ Done | Section 12.4, 20.5 | Commit `dc99025`; 6 new tests; also fixed loser `battles_played` bug |
| P1-2 | Add pity system to sticker packs | ✅ Done | Section 12.4 | Commit `69b7412`; 7 new tests; pity_holographic/full_art/secret_rare on User |
| P1-3 | Implement positional damage rules | ✅ Done | Section 5.2 | Commit `585ffdd`; 8 new tests; ×0.80 back-row; front-row-first targeting + AI |
| P1-4 | Add combo chain damage amplification | ✅ Done | Section 6.3 | Commit `1725f63`; 6 new tests; COMBO_AMP table in services.py |
| P1-5 | Pack opening animation | ✅ Done | Section 12.5 | Commit `1612a6a`; Alpine.js card flip; premium shimmer; Reveal All; noscript fallback |

---

## Phase 2 — Core Experience (GDD Section 24, Phase 2)

| # | Task | Status | GDD Reference |
|---|------|--------|--------------|
| P2-1 | Tutorial / first-time experience | 🔲 Not started | Section 20.7 |
| P2-2 | Quest & mission system | 🔲 Not started | Section 14 |
| P2-3 | Trainer profile page | 🔲 Not started | Section 18.2, 13 |
| P2-4 | Combo chain preview in team builder | 🔲 Not started | Section 20.10 |
| P2-5 | Type chart in UI (Pokedex + Team Builder) | 🔲 Not started | Section 20.14 |
| P2-6 | Achievement badge system | 🔲 Not started | Section 14.4 |
| P2-7 | Bench switching in battle | 🔲 Not started | Section 5.6 |

---

## Phase 3 — Competitive Layer (GDD Section 24, Phase 3)

| # | Task | Status | GDD Reference |
|---|------|--------|--------------|
| P3-1 | PvP matchmaking queue | 🔲 Not started | Section 15.2 — requires Redis (now done) |
| P3-2 | Ranked season system | 🔲 Not started | Section 15.3 |
| P3-3 | Leaderboard | 🔲 Not started | Section 20.9 |
| P3-4 | Spectator mode | 🔲 Not started | Section 20.15 |

---

## Phase 4 — Depth & Polish (GDD Section 24, Phase 4)

| # | Task | Status | GDD Reference |
|---|------|--------|--------------|
| P4-1 | Story quest narrative (Act 1) | 🔲 Not started | Section 3.2 |
| P4-2 | Seasonal events framework | 🔲 Not started | Section 20.11 |
| P4-3 | Album completion rewards | 🔲 Not started | Section 20.13 |
| P4-4 | Sticker album visual overhaul | 🔲 Not started | Section 12.6 |
| P4-5 | Guild / clan system | 🔲 Not started | Section 20.12 |

---

## Known Pre-Existing Test Failures (do not fix until planned)

These 11 tests fail on both SQLite and PostgreSQL — introduced before this project session:

```
tests/test_game/test_ai.py::TestMediumAI::test_medium_generates_actions
tests/test_game/test_ai.py::TestMediumAI::test_medium_prefers_status_moves
tests/test_game/test_ai.py::TestHardAI::test_hard_generates_actions
tests/test_game/test_combo_chain.py::TestBattleCreation::test_start_battle_transitions_to_active
tests/test_game/test_combo_chain.py::TestRoundExecution::test_round_increments_counter
tests/test_game/test_combo_chain.py::TestRoundExecution::test_check_winner_none_when_alive
tests/test_game/test_combo_chain.py::TestRoundExecution::test_check_winner_returns_survivor
tests/test_game/test_combo_chain.py::TestRoundExecution::test_status_effects_tick_after_actions
tests/test_pokemon/test_progression.py::TestAwardBattleExp::test_exp_carryover
```
(Note: 11 reported, 9 listed above — the remaining 2 are also in test_ai.py)

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `GAME_DESIGN_DOCUMENT.md` | Complete GDD — authoritative design reference |
| `PROGRESS.md` | This file — build status tracker |
| `.env` | Local dev environment variables (gitignored) |
| `.env.example` | Template for `.env` (committed) |
| `config/settings/base.py` | Shared settings + Redis channel layer logic |
| `config/settings/development.py` | Dev overrides (SQLite fallback removed) |
| `config/settings/production.py` | Production security hardening |
| `config/settings/test.py` | Test settings (SQLite in-memory OR Postgres via USE_POSTGRES_IN_TESTS=1) |
| `static/css/base.css` | Global stylesheet for all authenticated pages |
| `static/css/landing.css` | Landing page stylesheet |
| `requirements/base.txt` | Core dependencies (psycopg3, channels-redis) |
| `requirements/prod.txt` | Production extras (gunicorn, whitenoise) |
| `requirements/dev.txt` | Dev/test extras (pytest, ruff, mypy) |

---

## Architecture Decisions Made

| Decision | Reason |
|----------|--------|
| PostgreSQL 18 (local) | `select_for_update()` row-level locking; concurrent WebSocket safety |
| psycopg3 (`psycopg[binary]>=3.2`) | Newer async-ready driver; Django 5 compatible |
| Redis 7.0 via WSL Ubuntu | Only viable option on Windows without Docker |
| channels_redis 4.3.0 | Multi-process WebSocket support; required for PvP |
| HTMX 2.0.4 + Alpine.js 3.x | No build step; progressive enhancement; Django-template compatible |
| WhiteNoise for static files | Zero-config static serving; works with Daphne/gunicorn |
| CSS in static files | Maintainability; cacheable; allows design token updates without template edits |
