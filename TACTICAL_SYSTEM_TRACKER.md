# Pokémon Tactical System Tracker
## Naruto Online Inspired — Master Prompt Implementation

**Last Updated:** 2026-04-09
**Session:** 7 — Phase 6 Physical State System

---

## System Architecture

| Layer | Model/File | Status |
|-------|-----------|--------|
| Grid System | `apps/game/models.py` — GridPosition | PARTIAL (4v4 → needs 6v6) |
| Move Model | `apps/pokemon/models.py` — Move.slot_type | EXISTS (needs rename) |
| Element System | `apps/pokemon/models.py` — PokemonType | EXISTS (needs chakra overlay) |
| Held-Effect System | — | MISSING |
| Physical State System | `apps/effects/models.py` — StatusEffect | COMPLETE (Grounded/Airborne/Launched/Knockback + Shield/Hidden/Immune + Chain Breaker/State Locked) |
| Stat Model | `apps/pokemon/models.py` — Pokemon base_* | EXISTS (needs Critical/Combo/Control expansion) |
| Combo System | `apps/game/services.py` — ComboChainEngine | EXISTS (needs role tags) |
| Archetype System | `apps/pokemon/models.py` — Pokemon.primary_role | EXISTS (needs remap) |
| Turn System | `apps/game/models.py` — GRID_TURN_ORDER | EXISTS (needs 6-slot expansion) |

---

## Feature Progress

### ✅ Completed
- [x] Session 1: Full codebase exploration & gap analysis
- [x] Session 1: 7-phase implementation plan created
- [x] Session 1: Chakra Element system designed (Option C — dual identity)

### 🔄 In Progress
- Nothing yet

### 📋 Planned

#### Phase 1 — Rename & Align ✅ COMPLETE (Session 2, 2026-04-08)
- [x] Rename `special` → `mystery` in Move.slot_type choices
- [x] Rename `support` → `passive_1` in Move.slot_type choices
- [x] Rename `passive` → `passive_2` in Move.slot_type choices
- [x] Remap `primary_role`: dps→burst, assassin→combo, bruiser→tank
- [x] Add `combo_role` field to Move (starter/extender/amplifier/finisher)
- [x] Migration `0010_phase1_rename_slots_roles_combo_role` applied
- [x] Updated: services.py, ai.py, tutorial_service.py, views.py, backfill command, battle_detail.html

#### Phase 2 — Chakra Element System (Option C — Dual Identity) ✅ COMPLETE (Session 3, 2026-04-08)
- [x] Create `ChakraElement` model (fire/water/earth/lightning/wind)
- [x] Add `chakra_element` FK to PokemonType (maps 18 types → 5 elements)
- [x] Create fixture: `apps/pokemon/fixtures/chakra_elements.json`
- [x] Migration `0011_phase2_chakra_element` applied — all 18 types mapped, 0 unmapped
- [x] Add `CHAKRA_BEATS` constant to services.py (fire→wind→lightning→earth→water→fire)
- [x] Mastery bonus (+20%) when move chakra = attacker species chakra
- [x] Advantage bonus (+15%) when move chakra beats defender species chakra
- [x] Both stack (+35%) — mastery + advantage combined
- [x] Resistance penalty (−10%) when defender chakra beats move chakra
- [x] Species/move element derived via FK chain (no hardcoding)

#### Phase 3 — Grid Expansion (6v6) ✅ COMPLETE (Session 4, 2026-04-08)
- [x] Add FRONT_CENTER, BACK_CENTER to GridPosition choices (BENCH_1/2 kept for DB compat)
- [x] Update ACTIVE_GRID_POSITIONS (4 → 6: FL/FC/FR + BL/BC/BR)
- [x] Update POSITION_TO_GRID: 1→FL, 2→FC, 3→FR, 4→BL, 5→BC, 6→BR
- [x] Update GRID_TURN_ORDER (6-slot priority, bench pushed to 7/8)
- [x] Update BattleValidator._REQUIRED_SLOTS = 6
- [x] AI auto-fills all 6 grid positions (POSITION_TO_GRID maps all 6 to active now)
- [x] Template: .pokemon-grid-2x2 → 3-column layout (grid-template-columns: 1fr 1fr 1fr)
- [x] Team.get_active_six() added; get_active_four() kept as deprecated shim
- [x] django check: 0 issues

#### Phase 4 — Held-Effect System (Passive 2) ✅ COMPLETE (Session 5, 2026-04-08)
- [x] `HeldEffect` model in pokemon app (trigger_condition, effect_data JSONField, activation_chance, max_activations)
- [x] `BattleSlotHeldEffect` model in game app (OneToOneField → BattleSlot, activations_used, can_activate property)
- [x] Migration 0012 (pokemon): HeldEffect table + held_effect FK on OwnedPokemon
- [x] Migration 0008 (game): BattleSlotHeldEffect table
- [x] Fixture: 14 held effects across all 4 triggers (passive×3, on_hit×4, on_faint×3, on_status×4)
- [x] `_resolve_held_effect()` module-level fn in services.py — implements heal_fraction, damage_reflect, status_cleanse, revive_hp_fraction
- [x] on_hit: fires after damage lands in ComboChainEngine._execute_move
- [x] on_faint: fires if hit was lethal in _execute_move
- [x] on_status: fires after successful status application in _execute_move
- [x] passive: fires for all active slots at start of each round in execute_round
- [x] set_team_from_owned: creates BattleSlotHeldEffect rows on team build
- [x] django check: 0 issues

#### Phase 5 — Stat Expansion ✅ COMPLETE (Session 6, 2026-04-09)
- [x] `critical_rate` FloatField on BattleSlot (default 0.05) — ×1.5 on hit if roll passes
- [x] `combo_rate` FloatField on BattleSlot (default 0.10) — ×(1+combo_rate) on chain_position > 0
- [x] `control_resist` FloatField on BattleSlot (default 0.00) — chance to negate status application
- [x] Rename `base_sp_attack` → `base_ninjutsu` on Pokemon (migration 0013)
- [x] Rename `base_speed` → `base_initiative` on Pokemon (migration 0013)
- [x] Updated: services.py, admin.py, views.py, pokemon_detail.html, team_select.html, pokemon.json fixture
- [x] Back-row positional penalty extended to BACK_CENTER (Phase 3 grid)
- [x] django check: 0 issues

#### Phase 6 — Physical State System ✅ COMPLETE (Session 7, 2026-04-09)
- [x] Add StatusEffect entries: Grounded, Airborne, Launched, Knockback (pk 31-34)
- [x] Add Utility entries: Shielded, Hidden, Immune (pk 35-37)
- [x] Add Advanced entries: Chain Breaker, State Locked (pk 38-39)
- [x] New `StatusCategory.PHYSICAL / UTILITY / ADVANCED` choices
- [x] `PHYSICAL_STATUSES / UTILITY_STATUSES / ADVANCED_STATUSES` frozensets in constants.py
- [x] `chase_condition` TextField on Move (migration 0014) — null = no restriction
- [x] `engine.py`: physical states mutually exclusive on apply; `clear_physical_statuses()`; `is_grounded()`; remove_volatile_statuses now clears all categories on switch
- [x] `services.py` — SHIELDED: absorbs one hit (damage = 0, shield removed)
- [x] `services.py` — AIRBORNE → LAUNCHED: auto-transition on any damaging hit (skipped if STATE_LOCKED)
- [x] `services.py` — KNOCKBACK: shift grid_position front→back row on status apply
- [x] `services.py` — IMMUNE: skip status application block
- [x] `services.py` — CHAIN_BREAKER: combo chain halts after hit on this target
- [x] `services.py` — HIDDEN: excluded from target selection
- [x] `services.py` — chase_condition gating: grounded/airborne/launched/knockback checks in combo loop
- [x] `services.py` — `_apply_knockback_position()` helper on ComboChainEngine
- [x] django check: 0 issues

#### Phase 7 — Testing & Validation ✅ COMPLETE (Session 8, 2026-04-09)
- [x] All 18 types map to exactly 1 chakra element (data structure + migration verified)
- [x] Chakra bonus calculations correct (mastery/advantage/resistance/neutral/stacked)
- [x] CHAKRA_BEATS cycle complete and correct (all 5 elements, closed loop)
- [x] 6-slot battle creation and validation works (BattleValidator, set_team, start_battle)
- [x] Held-effect triggers fire on correct conditions (passive/on_hit/on_faint/on_status)
- [x] Physical state transitions work (Grounded→Airborne→Launched→Knockback, mutual exclusivity, STATE_LOCKED)
- [x] Phase 6 mechanics (SHIELDED, HIDDEN, IMMUNE, CHAIN_BREAKER, chase_condition, KNOCKBACK grid shift)
- [x] PokemonFactory fixed: base_sp_attack→base_ninjutsu, base_speed→base_initiative (migration 0013)

---

## Chakra Element System (Option C — Dual Identity)

### Element Groups
| Chakra Element | Pokémon Types |
|----------------|--------------|
| Fire | Fire, Dragon, Dark |
| Water | Water, Ice, Poison, Fairy |
| Earth | Ground, Rock, Fighting, Normal |
| Lightning | Electric, Steel, Psychic |
| Wind | Flying, Grass, Bug, Ghost |

### Advantage Cycle
```
Fire → beats → Wind
Wind → beats → Lightning
Lightning → beats → Earth
Earth → beats → Water
Water → beats → Fire
```

### Damage Bonus Rules
| Condition | Modifier |
|-----------|----------|
| Move chakra = species chakra (mastery) | +20% |
| Move chakra beats target species chakra (advantage) | +15% |
| Both mastery + advantage | +35% |
| Move chakra loses to target species chakra | −10% |
| Neutral | ×1.0 |

### Identity Rules
- **Species element** = derived from `primary_type.chakra_element` (automatic, no hardcoding)
- **Move element** = derived from `move_type.chakra_element` (automatic)
- Both are computed, not stored separately

---

## Move Slot Model (5-Talent)

| Master Name | Current Name | Description | Status |
|-------------|-------------|-------------|--------|
| Mystery | special | Manual, cooldown, high impact | RENAME Phase 1 |
| Standard | standard | Auto-fires, generates states | NO CHANGE |
| Chase | chase | Reaction-based, trigger → result | NO CHANGE |
| Passive 1 | support | Stat/team buff | RENAME Phase 1 |
| Passive 2 | passive | Held-effect system | RENAME Phase 1 |

---

## Combo System

### Combo Roles (Phase 1 — add `combo_role` field to Move)
| Role | Description |
|------|-------------|
| starter | Initiates chain, must have combo_starter=True |
| extender | Continues active chain, adds chain link |
| amplifier | Boosts chain damage for subsequent links |
| finisher | Closes chain, receives max amplification |

### Chain Amplification (live)
| Link | Multiplier |
|------|-----------|
| 1 | 1.00× |
| 2 | 1.10× |
| 3 | 1.20× |
| 4 | 1.35× |
| 5 | 1.50× |
| 6 | 1.65× |
| 7 | 1.80× |
| 8 | 2.00× |
| 9 | 2.25× |
| 10 | 2.50× |

---

## State Library

### Physical States (Phase 6)
| State | Trigger | Effect | Status |
|-------|---------|--------|--------|
| Grounded | default | Normal state, can be launched | PLANNED |
| Airborne | knocked up | Chase triggers available | PLANNED |
| Launched | combo hit while airborne | Extended juggle window | PLANNED |
| Knockback | finisher | Pushed back, position changes | PLANNED |

### Control States (live)
| State | Model Name | Status |
|-------|-----------|--------|
| Paralysis (50% chase fail) | paralyzed | LIVE |
| Acupuncture | acupunctured | LIVE |
| Immobile | immobile | LIVE |
| Blindness | blinded | LIVE |
| Chaos | chaos | LIVE |
| Sleep | asleep | LIVE |
| Interrupt | interrupted | LIVE |

### Debuff States (live)
| State | Model Name | Status |
|-------|-----------|--------|
| Ignition | ignited | LIVE |
| Poison | poisoned | LIVE |
| Mark | tagged | LIVE |

### Utility States
| State | Status |
|-------|--------|
| Shield | PLANNED Phase 6 |
| Hidden | PLANNED Phase 6 |
| Immunity | PLANNED Phase 6 |

### Advanced States
| State | Status |
|-------|--------|
| combo momentum | LIVE (BattleAction.order_in_chain) |
| chain amplifier | LIVE (COMBO_AMP in services.py) |
| chain breaker | PLANNED Phase 6 |
| state lock | PLANNED Phase 6 |

---

## Grid System

| Feature | Current | Target |
|---------|---------|--------|
| Active slots | 4 (2×2) | 6 (3×2) |
| Bench slots | 2 | 0 (implicit) |
| Battle size | 4v4 | 6v6 |

### Target Grid Layout
```
[FRONT_LEFT] [FRONT_CENTER] [FRONT_RIGHT]
[ BACK_LEFT] [ BACK_CENTER] [ BACK_RIGHT]
```

---

## Archetype Remap (Phase 1)

| Master | Current | Status |
|--------|---------|--------|
| burst | dps | RENAME Phase 1 |
| combo | assassin | RENAME Phase 1 |
| tank | bruiser + tank | MERGE Phase 1 |
| support | support | NO CHANGE |
| control | control | NO CHANGE |

---

## Held-Effect Library (Phase 4 — design placeholder)

| Name | Trigger | Effect | Status |
|------|---------|--------|--------|
| TBD | — | — | DESIGN PHASE |

---

## Session Log

| Session | Date | Completed |
|---------|------|-----------|
| 1 | 2026-04-08 | Codebase exploration, gap analysis, 7-phase plan, chakra element design (Option C), tracker created |
| 2 | 2026-04-08 | Phase 1 complete — slot_type renamed (mystery/passive_1/passive_2), roles remapped (burst/combo/tank), combo_role field added, migration applied |
| 3 | 2026-04-08 | Phase 2 complete — ChakraElement model, FK on PokemonType, migration 0011 (all 18 types mapped), CHAKRA_BEATS constant, mastery/advantage/resistance modifiers in _calculate_damage |
| 4 | 2026-04-08 | Phase 3 complete — FRONT_CENTER/BACK_CENTER added, ACTIVE_GRID_POSITIONS→6, POSITION_TO_GRID remapped, GRID_TURN_ORDER updated, _REQUIRED_SLOTS=6, template 3-col grid, get_active_six() |
| 5 | 2026-04-08 | Phase 4 complete — HeldEffect + BattleSlotHeldEffect models, migrations, 14-effect fixture, _resolve_held_effect() wired to on_hit/on_faint/on_status/_execute_move and passive/execute_round |
| 6 | 2026-04-09 | Phase 5 complete — critical_rate/combo_rate/control_resist on BattleSlot, base_sp_attack→base_ninjutsu, base_speed→base_initiative, all references updated |
| 7 | 2026-04-09 | Phase 6 complete — Physical State System (Airborne/Launched/Knockback/Grounded), Utility states (Shield/Hidden/Immune), Advanced states (Chain Breaker/State Locked), chase_condition on Move, all wired into ComboChainEngine |
| 8 | 2026-04-09 | Phase 7 complete — 88 new tests across 5 files: physical states, Phase 6 mechanics, chakra system, battle validation, held effects. Fixed PokemonFactory stat rename. 474 tests passing. |
| 9 | 2026-04-13 | NEW PLAN SESSION — Full audit against Naruto Online mechanics. 8 new phases defined (P0–P7). P0 implemented: Sensei Kira localStorage persistence, battle round logs wired, grid tooltip corrected (3×2), Pokemon sprites on grid, CSS slot classes updated (mystery/passive_1/passive_2). |
| 10 | 2026-04-13 | Phase 1 complete — New Battle Action Model. prepare_player_actions() rewritten to accept mystery toggles (use_mystery bool per slot). Standard auto-fires, mystery fires on toggle if not on cooldown. Target auto-selected (front-row-first, HIDDEN-aware). UI redesigned: mystery toggle button per unit + passive badges. Old move buttons/target clicking removed. django check: 0 issues. |
| 10b | 2026-04-13 | Phase 2 complete — Missing Status Mechanic Enforcement. BLINDED (skip standard), ACUPUNCTURED/TAUNTED (block mystery in prepare_player_actions), CONFUSED (33% self-hit in execute_round), INFATUATED (50% skip in can_act), SEEDED drain (applied_by_slot FK + heal in tick). Migration 0003. django check: 0 issues. |
| 11 | 2026-04-13 | Phase 3 complete — Control + Penetration stats. `control`/`penetration` on BattleSlot. Proper CC formula (control / control + resist×1000). Penetration ignores fraction of defense. Both derived in set_team_from_owned (ninjutsu→control, role→penetration). Migration 0011. django check: 0 issues. |
| 11b | 2026-04-13 | Phase 4 complete — Role/Archetype cleanup. SPECIES_POOLS + determine_role() remapped (dps→burst, assassin→combo, bruiser→tank). seed_move_pools --clear re-run. 1619 pool entries valid. All Pokemon.primary_role verified against TacticalRole choices. |
| 12 | 2026-04-14 | Phase 5 complete — Battle UI feedback. Physical state badges (airborne/launched/knockback/grounded) with distinct CSS colors + icons. All status badges show icons + remaining turns + HTML tooltips. Round log: chain-link indentation + AUTO → prefix + [pos/total] counter. WS updateSlot updated. battle_tags.py: status_icon + min_five filters added. django check: 0 issues. |
| 13 | 2026-04-14 | Phase 6 complete — Charge Move system. CHARGING status (pk 40, advanced category, 1 round). _execute_move(): round 1 enters charging (0 damage, CHARGING applied, early return); round 2 releases (CHARGING removed, full damage). ⚡ badge with amber pulse animation. django check: 0 issues. |
| 14 | 2026-04-14 | Phase 7 complete — 33 new tests across 4 files. test_action_model (8): standard auto-fire, mystery toggle, ACUPUNCTURED/TAUNTED blocking. test_status_enforcement (11): BLINDED skip, CONFUSED self-hit+mock, INFATUATED can_act+mock, SEEDED drain/heal. test_stats (5): control formula (resist=0 always applies, high resist with mock), penetration damage comparison. test_charge_moves (9): round 1 zero damage + CHARGING applied, round 2 full damage + CHARGING removed, non-charge immediate. 527 passing total. |

---

## NEW PHASE PLAN (Sessions 9+) — Naruto Online Mechanics Alignment

### ✅ Phase 0 — Bug Fixes + Visual Polish (Session 9 — 2026-04-13) COMPLETE
- [x] **Sensei Kira**: localStorage persistence — dismissed state saved per battle PK, restored on page load
- [x] **Battle round log**: `context["logs"]` added to `BattleDetailView.get_context_data()` — all log types now render in Round Log section
- [x] **Grid tooltip**: corrected from "2×2" to "3×2, 6 Pokémon per side"
- [x] **Pokemon sprites**: `sprite_url` rendered as `<img>` on every player and opponent grid card
- [x] **CSS slot classes**: renamed `slot-special`→`slot-mystery`, `slot-support`→`slot-passive_1`, added `slot-passive_2`
- [x] **Seed script**: fixed SPECIES_POOLS and TYPE_POOLS keys (special→mystery, support→passive_1, passive→passive_2)
- [x] **Tutorial service**: `_get_moves_for_species` now reads SpeciesMovePool (not M2M moves)
- [x] **Battle validator**: error labels updated to mystery/passive_1

**DB commands needed after this phase:**
```bash
python manage.py seed_move_pools --clear
python manage.py backfill_pokemon_moves --force
```

---

### ✅ Phase 1 — New Battle Action Model (Naruto Online-style) COMPLETE (Session 10, 2026-04-13)
**Goal:** Remove manual move selection. Player only activates Mystery moves per unit.

| Slot | Old behavior | New behavior |
|---|---|---|
| Standard | Player selects | Auto-fires every round |
| Chase | Player selects | Auto-fires on condition |
| Mystery | Player selects | Player toggles ON/OFF per unit |
| Passive_1 | Shown as selectable | Always-on badge, not clickable |
| Passive_2 | Shown as selectable | Always-on badge, not clickable |

**Tasks:**
- [x] **P1-1**: New round submission: `mystery_{slot_pk}=on` checkbox — no move_id/target_id from player
- [x] **P1-2**: `prepare_player_actions()` in services.py — mystery toggle → mystery move; fallback → standard; target auto-selected (lowest-HP front-row, HIDDEN-aware)
- [x] **P1-3**: UI redesign — 6 unit tabs each showing a "Unleash Mystery" toggle button (greyed if on cooldown) + passive badges (non-interactive)
- [x] **P1-4**: Removed old move selector buttons and target click logic; opponent cards no longer clickable
- [x] **P1-5**: Auto-target uses front-row-first / lowest-HP / HIDDEN-aware logic directly in `prepare_player_actions()`
- **Files**: `apps/game/services.py`, `apps/game/views.py`, `templates/game/battle_detail.html`

---

### ✅ Phase 2 — Missing Status Mechanic Enforcement COMPLETE (Session 10, 2026-04-13)
**Goal:** Implement statuses that are declared but never actually enforced.

- [x] **P2-1 BLINDED**: In `execute_round()` — skip if `move.slot_type == STANDARD` and attacker has BLINDED
- [x] **P2-2 ACUPUNCTURED**: In `prepare_player_actions()` — mystery blocked if ACUPUNCTURED
- [x] **P2-3 CONFUSED self-hit**: In `execute_round()` — 33% chance hit self (40 power, typeless, own defense formula)
- [x] **P2-4 INFATUATED**: In `can_act()` — 50% skip using `_INFATUATION_REFUSE_CHANCE`
- [x] **P2-5 TAUNTED**: In `prepare_player_actions()` — mystery blocked if TAUNTED
- [x] **P2-6 SEEDED drain**: `applied_by_slot` FK on `ActiveStatusEffect`; healer restored in `_tick_single()`; `apply_status()` accepts `applied_by_slot`; migration `0003_phase2_seeded_applied_by_slot` applied
- **Files**: `apps/effects/engine.py`, `apps/game/services.py`, `apps/effects/models.py`, new migration

---

### ✅ Phase 3 — Stats: Add Control + Penetration COMPLETE (Session 11, 2026-04-13)
**Goal:** Add two missing stats from the design document.

- [x] **P3-1**: Add `control` FloatField to BattleSlot (default=100.0) — CC success rate
- [x] **P3-2**: Add `penetration` FloatField to BattleSlot (default=0.0) — % defense ignored (0.0–1.0)
- [x] **P3-3**: Wire `control` into status application: `success = control / (control + target.control_resist * 1000)`
- [x] **P3-4**: Wire `penetration` into `_calculate_damage()`: `effective_defense = defense * (1.0 - attacker.penetration)`
- [x] **P3-5**: control derived from base_ninjutsu (50 + ninjutsu/255 × 100 → range 50–150); penetration derived from primary_role (combo→0.10, burst→0.05, control→0.08, tank/support→0.0)
- **Files**: `apps/game/models.py`, `apps/game/migrations/0011_phase3_control_penetration.py`, `apps/game/services.py`

---

### ✅ Phase 4 — Role/Archetype Cleanup COMPLETE (Session 11, 2026-04-13)
**Goal:** Fix TacticalRole enum mismatch between models and seed data.

- [x] **P4-1**: SPECIES_POOLS roles remapped: dps→burst, assassin→combo, bruiser→tank (30 entries)
- [x] **P4-1**: `determine_role()` updated: assassin→combo, bruiser→tank, dps→burst (fallback logic)
- [x] **P4-2**: `seed_move_pools --clear` re-run — 1619 pool entries recreated, 0 invalid roles
- [x] **P4-3**: All Pokemon.primary_role values verified valid (burst/combo/tank/support/control)
- **Files**: `apps/pokemon/management/commands/seed_move_pools.py`

---

### ✅ Phase 5 — Battle UI: Physical States + Status Feedback COMPLETE (Session 12, 2026-04-14)
**Goal:** Make combo/state mechanics visible in the UI.

- [x] **P5-1**: Physical state badges with color-coded CSS per state (airborne→purple, launched→red, knockback→orange, grounded→green); utility badges (shielded/hidden/immune/chain_breaker/state_locked)
- [x] **P5-2**: All status badges show icon prefix + remaining turns inline + HTML tooltip on hover
- [x] **P5-3**: Mystery cooldown already rendered ("Cooldown: Xr") — added `font-weight:700` highlight
- [x] **P5-4**: Round log chain links indented by chain_position (1–5+) with `.chain-link-N` CSS classes, colored gold
- [x] **P5-5**: Chain-triggered actions get "AUTO →" prefix in round log; [pos/total] counter appended
- [x] WS `updateSlot` JS updated to render physical/utility icons + tooltips from live payloads
- [x] `status_icon` filter + `min_five` filter added to `battle_tags.py`
- **Files**: `templates/game/battle_detail.html`, `apps/game/templatetags/battle_tags.py`

---

### ✅ Phase 6 — Charge Move Implementation COMPLETE (Session 13, 2026-04-14)
**Goal:** `is_charge_move=True` moves work as 2-round charge → release.

- [x] **P6-1**: `CHARGING` added to `StatusName` (advanced category), `ADVANCED_STATUSES` frozenset, `DEFAULT_DURATIONS` (1 round)
- [x] **P6-2**: In `_execute_move()`: if charge move and not CHARGING, apply CHARGING + log "is charging...", return early BattleAction (0 damage)
- [x] **P6-3**: Round 2: if CHARGING, remove status + log "released!", fall through to normal damage calc
- [x] **P6-4**: StatusEffect pk 40 added to fixture and loaded. UI: ⚡ icon in `battle_tags.py`, amber pulsing CSS `.badge-util-charging`, JS `UTILITY_ICONS` updated
- **Files**: `apps/effects/constants.py`, `apps/effects/fixtures/status_effects.json`, `apps/game/services.py`, `apps/game/templatetags/battle_tags.py`, `templates/game/battle_detail.html`

---

### ✅ Phase 7 — Test Suite Update COMPLETE (Session 14, 2026-04-14)
**Goal:** Tests covering all new mechanics from Phases 1–6.

- [x] Tests for Naruto-style action model (standard auto / mystery toggle / ACUPUNCTURED / TAUNTED blocking)
- [x] Tests for BLINDED skip, CONFUSED self-hit, INFATUATED can_act, SEEDED drain+heal
- [x] Tests for Control/Penetration stat calculations (formula + deterministic mock)
- [x] Tests for charge move 2-round flow (charge round 0 dmg, release round full dmg, non-charge immediate)
- [x] 33 new tests, all passing. Total suite: 527 passing.
- **Files**: `tests/test_game/test_action_model.py`, `tests/test_game/test_stats.py`, `tests/test_game/test_charge_moves.py`, `tests/test_effects/test_status_enforcement.py`

---

## NEXT CHAT PROMPT (Phase 7)

Copy this into a new chat to continue:

```
I am building a Django Pokémon tactical battle game inspired by Naruto Online.
Read TACTICAL_SYSTEM_TRACKER.md for full context. Phases 0–6 are complete.

We are starting Phase 7 — Test Suite Update.

COMPLETED SO FAR (do NOT redo):
- Phase 0: Bug fixes + visual polish (sprites, localStorage, grid tooltip, CSS slot classes)
- Phase 1: New Battle Action Model — mystery toggle UI, prepare_player_actions() rewritten
- Phase 2: Status enforcement — BLINDED, ACUPUNCTURED, CONFUSED, INFATUATED, TAUNTED, SEEDED drain
- Phase 3: Stats — control + penetration fields on BattleSlot, wired into CC formula and damage calc
- Phase 4: Role/Archetype cleanup — SPECIES_POOLS remapped, seed_move_pools re-run
- Phase 5: Battle UI — physical state badges, status icons + tooltips, round log chain indentation
- Phase 6: Charge Move system — CHARGING status, 2-round wind-up in _execute_move(), ⚡ badge

KEY FILES:
- apps/game/services.py → ComboChainEngine, execute_round(), prepare_player_actions(), _execute_move()
- apps/effects/engine.py → StatusEffectEngine, can_act(), apply_status(), has_status()
- apps/effects/constants.py → StatusName, all frozensets
- apps/game/models.py → BattleSlot (critical_rate, combo_rate, control_resist, control, penetration)
- tests/framework/factories/pokemon_factory.py → PokemonFactory (use base_ninjutsu, base_initiative — NOT base_sp_attack/base_speed)
- tests/test_game/ → existing test files for reference

PHASE 7 TASKS — write tests for all mechanics added in Phases 1–6:

P7-1: Naruto-style action model
  - standard move auto-fires every round (no player selection needed)
  - mystery fires when mystery toggle is True, skipped when False
  - mystery blocked when ACUPUNCTURED or TAUNTED
  - File: tests/test_game/test_action_model.py

P7-2: Status enforcement
  - BLINDED: standard move is skipped (log created, no BattleAction damage)
  - CONFUSED: 33% self-hit produces self-damage BattleLog
  - INFATUATED: 50% chance can_act returns False
  - SEEDED: applied_by_slot heals each tick
  - File: tests/test_effects/test_status_enforcement.py

P7-3: Control + Penetration
  - control formula: success_prob = control / (control + control_resist * 1000)
  - penetration: effective_defense = defense * (1 - penetration); more damage with higher penetration
  - File: tests/test_game/test_stats.py

P7-4: Charge move 2-round flow
  - Round 1: CHARGING status applied to attacker; BattleAction.damage_dealt == 0
  - Round 2: CHARGING removed; full damage dealt
  - Round 1 with non-charge move: no CHARGING applied, damage dealt normally
  - File: tests/test_game/test_charge_moves.py

CONSTRAINTS:
- ALL tests must be in classes inheriting BaseTest (see existing test files for the pattern)
- Use PokemonFactory from tests/framework/factories/pokemon_factory.py
- Use base_ninjutsu and base_initiative (NOT base_sp_attack/base_speed — renamed in Phase 5)
- Each test class should have a setUp that creates a minimal battle with 2 slots
- Run: python manage.py test tests/ after writing to verify all pass
```

We are starting Phase 3 — Stats: Add Control + Penetration.

COMPLETED SO FAR (do NOT redo):
- Phase 1: New Battle Action Model — mystery toggle UI, prepare_player_actions() rewritten
- Phase 2: Status enforcement — BLINDED, ACUPUNCTURED, CONFUSED, INFATUATED, TAUNTED, SEEDED drain

KEY FILES:
- apps/game/models.py → BattleSlot model (already has critical_rate, combo_rate, control_resist)
- apps/game/services.py → _calculate_damage(), execute_round(), status application in _execute_move()

PHASE 3 TASKS:
P3-1: Add `control` FloatField to BattleSlot (default=100.0) — CC success rate multiplier
P3-2: Add `penetration` FloatField to BattleSlot (default=0.0) — fraction of defense ignored (0.0–1.0)
P3-3: Replace `control_resist` raw random check with proper formula:
      success = random.random() < (attacker.control / (attacker.control + target.control_resist * 1000))
      (currently: `resisted = target.control_resist > 0 and random.random() < target.control_resist`)
P3-4: Wire penetration into _calculate_damage():
      effective_defense = defense_stat * (1.0 - attacker.penetration)
P3-5: Populate control + penetration when building BattleSlots in set_team_from_owned():
      - control: derive from base_ninjutsu (higher ninjutsu → higher CC rate, scale 50–150)
      - penetration: derive from primary_role (combo→0.10, burst→0.05, tank→0.0, support→0.0, control→0.08)
      Migration needed.

Read the tracker and key files before implementing.
```
