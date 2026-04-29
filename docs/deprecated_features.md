# Deprecated Feature Inventory

This repo is moving away from battle-first progression and toward a collector loop centered on:

- Amigo XP
- sticker albums
- release bond / Ryo
- arcade games
- guild albums

The features below are now hidden or should be treated as deprecated until they are removed cleanly.

## Hidden in navigation

- `pokemon:team` (`My Team`)
- `pokemon:combo_atlas`
- `pokemon:combo_simulator`
- `ranked:home`
- ranked queue actions

## No longer part of the intended player loop

- battle tutorial onboarding
- PvP battle creation
- AI battle creation
- battle lists and battle logs
- spectator flows
- ranked seasons and ranked matchmaking
- combo-chain progression as a primary progression surface

## Pages and routes to remove after final verification

- `apps/game/views.py`
  - `BattleCreateView`
  - `AIBattleCreateView`
  - `BattleListView`
  - `BattleView`
  - `BattleLogView`
  - `SpectatorView`
  - `ActiveBattleListView`
  - `TutorialView`
  - `TutorialStarterSelectView`
  - `TutorialCompleteView`
- `apps/game/urls.py`
  - battle, tutorial, and spectate routes
- `apps/pokemon/views.py`
  - `TeamView`
  - `TeamSlotPickerView`
  - `ComboAtlasView`
  - `ComboSimulatorView`
  - combo simulator APIs
- `apps/pokemon/urls.py`
  - team and combo routes
- `apps/ranked/`
  - matchmaking and ranked season UI once no longer needed for data migration

## Templates that should be removed later

- `templates/game/home.html`
- `templates/game/battle_create.html`
- `templates/game/battle_detail.html`
- `templates/game/battle_list.html`
- `templates/game/battle_log.html`
- `templates/game/spectate.html`
- `templates/game/spectate_list.html`
- `templates/game/team_select.html`
- `templates/game/tutorial_starter_select.html`
- `templates/game/tutorial_complete.html`
- `templates/pokemon/team.html`
- `templates/pokemon/team_slot_picker.html`
- `templates/pokemon/combo_atlas.html`
- `templates/pokemon/combo_simulator.html`
- `templates/ranked/home.html`

## Follow-up cleanup notes

- Update landing and login marketing copy so it no longer sells battle/ranked features.
- Replace battle-oriented event copy with sticker, arcade, or guild-album goals.
- Review admin labels and help text that still say `trainer` or reference battle progression.
- Keep DB fields like `trainer_level` and battle stats for now to avoid risky migrations during the live-feedback phase.
