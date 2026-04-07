# Pokemon Combo Battle — Game Design Document
## Version 1.0 | Complete Design Reference
### Classification: Core Development Bible

---

> **How to use this document**
> This GDD is the authoritative source of truth for all design decisions. Every feature built, every piece of art created, and every UI screen designed should align with the vision stated here. When this document conflicts with existing code, the document wins — then the code gets updated, not ignored.

---

# TABLE OF CONTENTS

1. [Executive Summary & Vision](#1-executive-summary--vision)
2. [Game Identity & Unique Selling Points](#2-game-identity--unique-selling-points)
3. [Story, World & Lore](#3-story-world--lore)
4. [Core Gameplay Loop](#4-core-gameplay-loop)
5. [Battle System — Complete Mechanics](#5-battle-system--complete-mechanics)
6. [Combo Chain System — The Signature Mechanic](#6-combo-chain-system--the-signature-mechanic)
7. [Pokemon System — Species, Ownership & Teams](#7-pokemon-system--species-ownership--teams)
8. [Move System — The Five Technique Slots](#8-move-system--the-five-technique-slots)
9. [Status Effects Catalog](#9-status-effects-catalog)
10. [AI Opponent System](#10-ai-opponent-system)
11. [Economy — Ryo & Sticker Dust](#11-economy--ryo--sticker-dust)
12. [Sticker Collectible System](#12-sticker-collectible-system)
13. [Player Progression & Statistics](#13-player-progression--statistics)
14. [Quest & Mission System](#14-quest--mission-system)
15. [PvP Multiplayer & Ranked Seasons](#15-pvp-multiplayer--ranked-seasons)
16. [Visual Design & Branding](#16-visual-design--branding)
17. [UI/UX Design System](#17-uiux-design-system)
18. [Screen Map & Navigation](#18-screen-map--navigation)
19. [Features to REMOVE & Why](#19-features-to-remove--why)
20. [Features to ADD & Why](#20-features-to-add--why)
21. [Technical Architecture Notes](#21-technical-architecture-notes)
22. [Content Production Pipeline](#22-content-production-pipeline)
23. [Monetization Strategy](#23-monetization-strategy)
24. [Development Roadmap](#24-development-roadmap)

---

# 1. Executive Summary & Vision

## 1.1 Concept Statement

**Pokemon Combo Battle** is a free-to-play web-based tactical turn-based battle game that uses Generation 1 Pokemon species with a Naruto/shinobi-inspired battle philosophy. Players build teams of 6 Pokemon and fight in 4-active-plus-2-bench battles where the defining victory condition is not raw power, but the mastery of **Combo Chains** — cascading sequences of status effects that trigger automatic teammate attacks.

**Tagline:** *"Train. Chain. Conquer."*

**Sub-tagline:** *"Every battle tells a story. Make yours legendary."*

## 1.2 The One-Sentence Pitch

> A Pokemon fan game where your team wins not by being the strongest, but by creating the most elegant chain of coordinated attacks — up to 10 moves firing in one round from a single smart play.

## 1.3 Core Design Pillars

| Pillar | Description |
|--------|-------------|
| **Mastery over Luck** | The best players win through team-building strategy and status knowledge, not random crits |
| **Chain as Expression** | Your combo chain IS your personality as a trainer — what you chain says who you are |
| **Collect to Connect** | Stickers tell your story; collecting deepens your connection to your Pokemon |
| **Always Something To Do** | Daily rewards, missions, training timers, and battles give multiple engagement hooks |
| **Accessible Depth** | Simple enough to start (pick a Pokemon, pick a move), deep enough for 1000 hours |

## 1.4 Target Audience

**Primary:** Males and females aged 18–30 who grew up playing Pokemon and watch/read Naruto. They appreciate:
- Tactical depth over brainless grinding
- Collectible card systems (Pokemon TCG, Hearthstone)
- Web-based games accessible without installation
- Competitive rankings with a social leaderboard

**Secondary:** Hardcore tactical RPG players (Fire Emblem, Pokemon Showdown, Final Fantasy Tactics) who enjoy status-effect synergy team-building.

**Tertiary:** Casual collectors who may not battle much but enjoy filling their sticker album and trading with others.

## 1.5 Legal & IP Notes

This is a **fan project**, not affiliated with Nintendo, Game Freak, or The Pokemon Company. It uses Gen 1 Pokemon species data under the widely understood fan-game exception. Sprites are sourced from the official Pokemon website CDN for fan/educational use.

**Important:** The footer already reads *"Fan project, not affiliated with Nintendo or Game Freak"* — this must be visible on every page.

**Long-term recommendation:** Create original creature designs ("Ketsurai Companions") that draw inspiration from Gen 1 but are original IP. This protects the project and allows monetization. Until then, operate strictly as a non-commercial fan project.

---

# 2. Game Identity & Unique Selling Points

## 2.1 What Makes This Game Different

Every web Pokemon fan game is either:
1. A straight battle simulator (Pokemon Showdown clone)
2. A catching/walking game (Pokemon GO clone)
3. A card game (TCG simulator)

**Pokemon Combo Battle is none of these.** It is the first fan game to implement a **Naruto-inspired combo chain system** on top of Pokemon mechanics. The result is a game that feels like playing a choreographed battle sequence where you and your teammates all move together as one.

## 2.2 Competitive Differentiators

| Feature | Pokemon Showdown | Pokemon TCG Pocket | **This Game** |
|---------|-----------------|---------------------|---------------|
| Combo Chains | No | No | **Yes — up to 10 deep** |
| Naruto Status Effects | No | No | **30 including 11 Naruto-inspired** |
| Web-based, no install | Yes | No (mobile app) | **Yes** |
| Sticker Collection | No | Yes | **Yes (7 rarities × 6 variants)** |
| AI with difficulty tiers | Yes | No | **Yes (3 tiers)** |
| Grid positioning | No | No | **Yes (2×2 + bench)** |
| Story & Quests | No | Limited | **Planned — full narrative** |
| Training timers | No | No | **Yes (idle progression)** |
| P2P Sticker Trading | No | Yes | **Yes (atomic trade system)** |

## 2.3 The "Combo Chain" Unique Value Proposition

When a Jolteon uses Thunder Wave (applies Paralysis), and the player has a Gengar on the field whose trigger is Paralysis, Gengar automatically fires its Chase Technique. If Gengar's move also applies Confusion, and Alakazam triggers on Confusion, Alakazam fires. This chain can continue up to 10 links deep.

This creates a unique **"build-a-combo" team building puzzle** that no other Pokemon game offers. Players spend hours in the team builder testing chain combinations before they even battle. The strategy layer is in the preparation, not just in the battle.

---

# 3. Story, World & Lore

## 3.1 The World: The Ketsurai Region

**Ketsurai** (決意 — *Resolution*) is a mountainous, isolated region of the Pokemon world that developed a unique battle philosophy over centuries. Cut off from the wider world by jagged peaks on three sides and the Obsidian Sea on the fourth, Ketsurai's trainers evolved a fighting style that emphasizes **synchronization between trainer and Pokemon**.

They call this philosophy the **Kizuna Method** (絆法 — *Bond Method*). Where other regions train Pokemon to fight harder, Ketsurai trainers train teams to fight together. A single, perfectly executed Kizuna chain is considered more honorable than a brute-force knockout.

### Key Locations

| Location | Description | Function in Game |
|----------|-------------|-----------------|
| **Kurohane City** | The capital, built into a mountain face. Stone architecture, lanterns, waterfalls | Player starting area, Academy, main shops |
| **Hagane Ridge** | A mining district above the clouds. Steel-type Pokemon abundant | Mid-game story location; mining mini-quest |
| **The Verdant Hollow** | An ancient forest with mist that never clears | Late-game area; Grass/Ghost/Psychic Pokemon |
| **Shirogane Colosseum** | An ancient battle arena carved into a glacier | Tournament venue for ranked play |
| **The Sunken Ruins** | Partially submerged ruins with Water-type nests | Discovery quests, Legendary encounter |
| **The Void Rift** | A tear in reality created by the antagonists' forbidden technique | Final story location |

### The Kizuna Method Explained (In-World)

*"A single fist can break stone. But ten fists, striking as one? That breaks mountains. The Kizuna Method is not about making your Pokemon stronger. It is about making your team move as a single living thing."*
— Sensei Kira's Opening Lecture

In mechanical terms: The Kizuna Method IS the Combo Chain system. Players learn it as a story element before they learn it as a game mechanic, making the tutorial feel like discovering something, not being told something.

## 3.2 Main Story — Act Structure

### Prologue: Arrival in Ketsurai
The player character arrives at Kurohane City by ferry after receiving a letter of acceptance to the Ketsurai Pokemon Institute. They meet **Sensei Kira** (old, white-haired woman, former regional champion) who notices the player has an unusual bond with their starter Pokemon.

### Act 1: The Foundation (Tutorial)
- Sensei Kira teaches the basics of the Kizuna Method
- Player receives their Starter Pokemon (see Section 3.5)
- First battles against Academy classmates
- Rival "Shin" is introduced as a brilliant but dismissive classmate who views Kizuna chains as "cheap tricks"
- **Climax:** Academy qualifier battle — player executes their first 3+ chain combo

**Gameplay unlock:** Basic battles vs AI (Easy difficulty)

### Act 2: The Regional Circuit
- Player enters the Ketsurai Regional Tournament at Shirogane Colosseum
- Each tournament opponent specializes in different status strategies (teaching players about each status category through losing or narrowly winning)
- **The Severed appears** — mysterious trainers disrupting battles by releasing Chaos statuses mid-fight (introduced as saboteurs)
- Shin wins the tournament by brute force but looks troubled — he senses The Severed's intent
- **Climax:** Final tournament match interrupted by a Severed attack; player must fight a Severed agent

**Gameplay unlock:** Medium AI difficulty, Sticker packs, Trading

### Act 3: The Severed Revealed
- Investigating The Severed leads to the Sunken Ruins
- Player discovers The Severed's leader: **Commander Kurai** — a former Kizuna master who lost his bonded Pokemon and rejected the Method as "a lie"
- Kurai's power: He uses only Chaos-type status effects to BREAK enemy chains — the anti-Kizuna philosophy
- Shin joins as an uneasy ally after Kurai's agents attack him
- **Climax:** Infiltrate The Severed's underground base; battle Kurai's lieutenants

**Gameplay unlock:** Hard AI difficulty, Ranked PvP unlocked

### Act 4: The Corrupted Guardian
- The Severed have captured and corrupted a Legendary Pokemon (Mewtwo, flavor-wise re-named as **"Void-Mewtwo"** in the lore)
- Corrupted by Void energy, it attacks both sides
- Player must defeat it without killing it — a special "Restoration Battle" where you must land ONLY support/status moves that can purify it
- Shin admits Kizuna methods are real after witnessing the player's control
- **Climax:** First encounter with Void-Mewtwo; player fails, escapes, learns the purification technique

**Gameplay unlock:** Training system fully unlocked, team customization unlocked

### Act 5: Convergence — The True Bond
- Final assault on The Void Rift
- Player battles Commander Kurai one last time — he's integrated ALL 30 status effects into a single team
- Kurai's philosophy vs the player's: Breaking bonds vs Building bonds
- The player's TRUE chain — every Pokemon on their team working together — defeats Kurai
- Kurai is moved. He remembers why he loved the Kizuna Method. His lost Pokemon returns.
- **Ending:** Regional tournament re-held with full ceremony. Ranked season begins.

**Gameplay unlock:** Post-game content, Legendary encounter, seasonal events

## 3.3 Key Characters

### Player Character
- Customizable: Name, gender presentation, color scheme
- Background: Can be a returning trainer or a first-timer (flavor choice affecting some dialogue)
- Silent protagonist (no voiced dialogue) but expresses personality through team choices

### Sensei Kira
- Role: Mentor, quest giver, tutorial narrator
- Personality: Warm, patient, quietly powerful
- Visual: White hair in a high bun, traditional dark blue trainer's coat, a Ninetales always by her side
- Arc: She sees the player as the student who will prove the Kizuna Method's true power
- Quote: *"A chain is not a trap. It is a connection."*

### Shin (The Rival)
- Role: Rival, eventual ally
- Personality: Cold, analytical, dismissive of "soft" bond strategies
- Visual: Silver hair, black jacket, always arms crossed
- Signature Pokemon: Machamp (brute force first, no combos)
- Arc: Learns that power without connection has limits; his Machamp has always been trying to combo with him but he never set it up
- Quote: *"I don't need a chain. I just need to be stronger."*

### Commander Kurai
- Role: Main antagonist
- Background: Was once the greatest Kizuna master in Ketsurai history. His bonded Espeon died in a battle 20 years ago. He blames the Bond Method — if he hadn't cared so much, it wouldn't have hurt so much.
- Visual: Dark coat, tall, gaunt, pale, with one eye hidden by a scar
- Signature: Uses only Chaos-category statuses; his team syncs in ANTI-chains (breaks your combos)
- Quote: *"A bond is just another chain. I prefer to cut them all."*

### Zuri (The Collector)
- Role: Sticker system quest giver and shop keeper
- Personality: Enthusiastic, energetic, always has a rare sticker to trade
- Visual: Short, colorful clothes, collector badges all over her jacket, carries a massive sticker album
- Function: Introduces the sticker system, offers daily sticker missions, runs the in-game shop

---

## 3.4 Starter Pokemon

Players choose one of three starters from a curated set that each represents a different playstyle:

| Starter | Type | Tactical Role | Signature Chain Role | Why |
|---------|------|--------------|---------------------|-----|
| **Charmander** | Fire | DPS | Chain Starter (applies Burn) | Teaches offensive chain-starting |
| **Squirtle** | Water | Tank | Chain Sustainer (support moves that buff chain partners) | Teaches defensive/support team play |
| **Bulbasaur** | Grass/Poison | Control | Chain Extender (applies Poison/Sleep, long chains) | Teaches status control strategy |

Each starter has a pre-built team composition hint visible in the selection screen showing what a full chain with that starter looks like.

---

# 4. Core Gameplay Loop

## 4.1 The Engagement Cycle

```
Daily Login
    ↓
Claim Daily Ryo Reward (1,000 Ryo)
    ↓
Check Daily Missions (3 available)
    ↓
Battle (vs AI or PvP)
    ↓
Earn Ryo (Win: 200, Loss: 50) + EXP for Pokemon
    ↓
Level up Pokemon → Training timers → More EXP
    ↓
Accumulate Ryo → Buy Sticker Packs
    ↓
Open Packs → Get Stickers
    ↓
Complete missions (sticker rewards, more Ryo)
    ↓
Trade duplicates → Complete album
    ↓
Ranked season points → Season rewards
    ↓
(back to Battle)
```

## 4.2 Session Types

| Session Type | Duration | Activities |
|-------------|----------|-----------|
| **Quick Session** | 5–10 min | Claim daily, do one AI battle, check training |
| **Standard Session** | 20–40 min | Multiple battles, team management, sticker trading |
| **Deep Session** | 60+ min | Ranked battles, story quests, team rebuilding |

## 4.3 The Three Hooks

1. **Skill Hook** — "Can I build a longer combo chain today?"
2. **Collection Hook** — "Will I pull that Secret Rare Charizard today?"
3. **Social Hook** — "I want to trade for that Full Art Gengar"

A healthy game keeps all three hooks active simultaneously. Currently the game has Hooks 1 and 2. Hook 3 (trading) exists but needs discovery improvements.

---

# 5. Battle System — Complete Mechanics

## 5.1 Battle Format Overview

| Parameter | Value |
|-----------|-------|
| Team size | 6 Pokemon per trainer |
| Active on field | 4 (arranged in 2×2 grid) |
| Bench | 2 (can be swapped in as an action) |
| Battle format | Turn-based, simultaneous action selection |
| Win condition | All enemy active Pokemon fainted |
| Round structure | Both players select actions → resolve by speed priority → status effects tick |

## 5.2 The 2×2 Battle Grid

```
         PLAYER SIDE          |         OPPONENT SIDE
                              |
  [FRONT-LEFT] [FRONT-RIGHT]  |  [FRONT-LEFT] [FRONT-RIGHT]
  [BACK-LEFT]  [BACK-RIGHT]   |  [BACK-LEFT]  [BACK-RIGHT]
                              |
  [BENCH-1]  [BENCH-2]        |  [BENCH-1]  [BENCH-2]
```

### Grid Positional Rules (Current State → Required Update)

**Current state (as coded):** Grid positions exist in the model but have NO mechanical effect on damage or targeting.

**Required implementation (GDD mandate):**

| Position | Incoming Damage | Outgoing Damage | Notes |
|----------|----------------|-----------------|-------|
| Front Left/Right | 100% | 100% | Exposed — first line |
| Back Left/Right | 80% from direct attacks | 90% | Protected by front row |
| Bench | 0% (cannot be targeted) | 0% (cannot act) | Unless swapped in |

**Targeting rules:**
- Direct single-target attacks MUST target a front-row Pokemon first. Back row can only be targeted if all front-row allies on the same side are fainted.
- AoE (multi-target) moves hit all active Pokemon on the chosen side.
- Support moves (heals, buffs) can target any allied Pokemon including bench.

**Why this matters:** Position becomes a strategic decision. Do you put your combo starter (fragile DPS) in the back row for protection, or in the front row for faster combo access?

## 5.3 Turn Resolution Order

Within a single round, actions are resolved in this sequence:

1. **Always-First moves** (Quick Attack equivalent) — in speed order
2. **Normal priority moves** — sorted by speed stat (highest first)
   - Speed ties resolved by grid position (Front-Left > Front-Right > Back-Left > Back-Right)
3. **Always-Last moves** (Trick Room equivalent, low-priority moves)
4. **Combo chain triggers** — fire sequentially as part of step 2 resolution
5. **Status effect tick damage** — applied at end of round
6. **Training timer checks** — passive (server-side, not round-dependent)

## 5.4 Damage Formula

The standard damage formula (confirmed from code):

```
damage = ((2 × level / 5 + 2) × power × (attack / defense)) / 50 + 2
```

Then apply modifiers in this order:
1. **STAB** (Same Type Attack Bonus): ×1.5 if move type matches attacker's type
2. **Type effectiveness**: ×2.0 (super effective), ×1.0 (neutral), ×0.5 (not very effective), ×0 (immune)
3. **Random variance**: × random(0.85–1.00) — rolled each hit
4. **Position modifier**: ×0.80 if target is in back row (after grid rules implemented)
5. **Status modifiers**: Burns halve attack, Enfeebled halves attack + sp.attack, etc.
6. **Combo chain amplification** (see Section 6.3)

## 5.5 Move Cooldowns

When a move with `cooldown > 0` is used, it cannot be selected again for that many rounds. The system is already implemented via `MoveCooldown` model.

**Design guideline:** Cooldowns should be 2–4 rounds. A move with a 2-round cooldown should deal 30–50% more base damage than a comparable no-cooldown move. A 4-round cooldown should represent a game-changing effect (massive damage, full-team buff, or guaranteed status application).

## 5.6 Bench Switching

**This feature is currently modeled but not implemented. It is required for the grid to have full meaning.**

Rules:
- Switching is an action — the Pokemon that would have acted instead "passes" their turn
- The switch happens at the START of the round, before any attacks resolve
- Volatile status effects (Confused, Infatuated, etc.) are CLEARED on switch-out
- Persistent status effects (Burned, Poisoned, etc.) are KEPT through switch
- You cannot switch into a fainted slot
- You can switch from either bench position into any active grid position

---

# 6. Combo Chain System — The Signature Mechanic

## 6.1 Concept

The Combo Chain is the heart of this game. No other feature should be designed without asking: *"How does this interact with the combo chain?"*

**The Fundamental Rule:** When Move A applies status X to an enemy target, ANY allied Pokemon on the active field whose `trigger_status` matches X automatically fires their designated Chase Technique (CHASE slot move) on the same target. This happens immediately, as a continuation of the current resolution step.

## 6.2 Chain Resolution Algorithm

```
function resolve_combo_chain(initial_action, depth=0, fired_pairs=set()):
    if depth >= MAX_CHAIN_DEPTH (10):
        return  // anti-loop guard: max depth reached
    
    status_just_applied = initial_action.status_applied
    if status_just_applied is None:
        return  // no status = no trigger
    
    for ally_slot in active_allied_slots:
        if ally_slot == initial_action.attacker_slot:
            continue  // cannot trigger yourself
        
        trigger_move = ally_slot.get_chase_move()
        if trigger_move is None:
            continue
        if trigger_move.trigger_status != status_just_applied:
            continue
        
        pair = (ally_slot.id, trigger_move.id)
        if pair in fired_pairs:
            continue  // anti-loop: this pair already fired this round
        
        fired_pairs.add(pair)
        
        // Execute the triggered move
        new_action = execute_move(ally_slot, trigger_move, best_target)
        
        // Recurse: did the triggered move apply another status?
        resolve_combo_chain(new_action, depth + 1, fired_pairs)
```

## 6.3 Chain Amplification Bonus

Each link in a chain adds a damage amplification to ALL subsequent chain links:

| Chain Position | Damage Multiplier |
|---------------|------------------|
| Link 1 (initial move) | ×1.00 (base) |
| Link 2 | ×1.10 |
| Link 3 | ×1.20 |
| Link 4 | ×1.35 |
| Link 5 | ×1.50 |
| Link 6 | ×1.65 |
| Link 7 | ×1.80 |
| Link 8 | ×2.00 |
| Link 9 | ×2.25 |
| Link 10 (maximum) | ×2.50 |

**Note:** This amplification is NOT currently in the code. This is a NEW feature to add. It makes longer chains feel exponentially rewarding.

## 6.4 Chain Scoring & Record Keeping

| Achievement | How Tracked | Displayed |
|-------------|-------------|-----------|
| `max_combo_chain` on Battle model | Per-battle maximum | Battle summary screen |
| `longest_combo_chain` on User model | Career maximum | Trainer profile |
| Chain milestone popups | UI only | Battle screen overlay |

## 6.5 Visual Language of Chains (Design Requirements)

The combo chain MUST feel spectacular. Every chain link should trigger:

1. **Chain counter overlay** in top center of battle screen — large number that counts up with each link, glowing gold
2. **Particle burst** from the attacker's sprite with each triggered attack — color matches the move type
3. **Screen flash** on each combo link — subtle, never obscuring gameplay
4. **Chain label** in the battle log — e.g., "CHAIN ×4 — Paralysis → Shadow → Confusion → Psybeam!"
5. **Audio cue** (design for when audio is added): Building musical arpeggio that rises with each chain link; climactic chord at chain end
6. **"MAX CHAIN!"** special effect when a player beats their personal best combo record in a battle

## 6.6 Anti-Cheese Rules

The combo system must avoid infinite loops and degenerate strategies:

| Rule | Implementation |
|------|---------------|
| Max chain depth = 10 | `MAX_CHAIN_DEPTH = 10` (implemented) |
| Same attacker-move pair can only fire once per round | `fired_pairs` set (implemented) |
| A Pokemon cannot trigger its own initial move | Checked in chain resolution |
| Fainted Pokemon cannot trigger chains | Check `is_fainted` before triggering |
| On-cooldown Chase moves skip chain triggers | Check `MoveCooldown` before triggering |

---

# 7. Pokemon System — Species, Ownership & Teams

## 7.1 Species vs. Owned Pokemon

The game distinguishes two concepts:

- **Pokemon (species):** The template — base stats, available moves, types, Pokedex entry. This is shared data. One Charizard species entry exists.
- **OwnedPokemon:** YOUR Charizard. It has a level, experience, training history, and assigned moves from the species pool. Two players can own Charizard but their copies are separate.

This distinction is important for the sticker system: stickers represent the species, not the owned instance.

## 7.2 Base Stats

Six base stats are tracked per species:

| Stat | Combat Role |
|------|-------------|
| `base_hp` | Determines max HP at level |
| `base_attack` | Physical move damage |
| `base_defense` | Physical move damage reduction |
| `base_sp_attack` | Special move damage |
| `base_sp_defense` | Special move damage reduction |
| `base_speed` | Turn order within a round |

**HP Formula:** `(2 × base_hp × level) / 100 + level + 10`

**Other Stat Formula:** `(2 × base_stat × level) / 100 + 5`

## 7.3 Tactical Roles

Each species has a primary `TacticalRole` that describes its designed battle function:

| Role | Description | Design Intent |
|------|-------------|---------------|
| `DPS` | High attack, lower defense; primary damage dealer | Most common; pick for chain damage output |
| `ASSASSIN` | Very high speed + attack; targets weakened/isolated enemies | Chase kill-shot specialists |
| `TANK` | High HP + defense; front-row anchor | Put in front row to protect back-row DPS |
| `SUPPORT` | Heal, buff, debuff; doesn't need high damage | Chain supporters; apply status then trigger allies |
| `CONTROL` | Status-focused; low damage but high status accuracy | Chain starters; the engine of Kizuna teams |
| `BRUISER` | Balanced attack and defense; mid-range everything | Flexible; works in any grid position |

## 7.4 Pokemon Acquisition (Not Yet Implemented — Requires Building)

Players can obtain Pokemon through these methods:

| Method | Description | Rarity Control |
|--------|-------------|----------------|
| **Starter Selection** | One of three starter Pokemon at game start | Always available |
| **Battle Rewards** | Chance to encounter a wild Pokemon after winning a battle | Common tier only |
| **Story Quests** | Specific Pokemon guaranteed from quest completion | Curated; specific species |
| **Sticker-to-Pokemon** | Having a complete sticker set (all rarities) of a Pokemon unlocks it | Rare/Epic tier |
| **Shop** | Buy Pokemon encounters for Ryo | Uncommon/Rare tier |
| **Training Graduation** | At level milestones, Pokemon can teach you an evolution companion | Late-game |

**Important:** Pokemon catching must NEVER be purely random (no "roll for Pokemon"). Players should always know what they're working toward.

## 7.5 Leveling System

| Action | EXP Gained |
|--------|-----------|
| Win a battle | `battle_exp_gain` property (scales: Lv1-9=10, Lv10-19=20, etc.) |
| Lose a battle | 50% of win EXP |
| Complete training session | Training-tier bonus |
| Complete daily mission | Flat 50 EXP to all team members |

**EXP to next level formula:** `current_level × 10`
- Level 1 → 2: 10 EXP
- Level 50 → 51: 500 EXP
- Level 99 → 100: 990 EXP

**Level cap:** 100

## 7.6 Training System

The training system (modeled in `OwnedPokemon`) allows Pokemon to gain EXP while the player is offline.

| Training Tier | Duration | EXP Multiplier | Ryo Cost |
|--------------|----------|----------------|----------|
| Light Training | 15 min | 1.0× | Free |
| Standard Training | 1 hour | 1.5× | 100 Ryo |
| Intense Training | 4 hours | 2.0× | 300 Ryo |
| Elite Training | 8 hours | 3.0× | 600 Ryo |

**Rules:**
- Only one Pokemon can be training at a time (per player) in the current implementation. Upgrade path: allow multiple training slots unlockable with milestone achievements.
- Training ends automatically; the reward must be manually claimed (this creates a reason to return).
- A Pokemon in training cannot be used in battles.

## 7.7 Team Building

Each player has one persistent `Team` with 6 slots. The first 4 slots go to the active 2×2 grid. Slots 5–6 are bench.

**Team Builder UI requirements:**
- Show each slot with: Pokemon sprite, name, level, assigned moves, and their combo trigger/starter indicators
- Show a "chain preview" — highlight which Pokemon triggers which, drawing arrows between slots
- Warn if no Pokemon in the team can start a chain
- Warn if bench Pokemon's types/levels are significantly lower than active slots

---

# 8. Move System — The Five Technique Slots

## 8.1 Slot Types

Each OwnedPokemon is assigned exactly one move per slot type, drawn from the species' `SpeciesMovePool`:

| Slot | Display Name | Game Role | Combo Role |
|------|-------------|-----------|------------|
| `standard` | Basic Technique | Main attack; no cooldown | Can apply statuses to start chains |
| `chase` | Chase Technique | Auto-fires on combo trigger; medium cooldown | **THE combo trigger slot** |
| `special` | Secret Technique | High power; 3–4 round cooldown | Chain finisher; big damage |
| `support` | Support Technique | Heal/buff/shield; no damage | Sustain; keeps chain going |
| `passive` | Ninja Trait | Passive ability; fires automatically on conditions | Background always-on effect |

## 8.2 Move Assignment Rules

- Players CANNOT choose which Standard, Chase, etc. move to use in battle — they pre-assign one per slot during team management.
- In battle, the four active slots (Standard, Chase, Special, Support) are displayed as buttons. Passive fires automatically.
- Move can only be assigned to its designated slot type.
- The SpeciesMovePool tells you which moves are available per slot type for each species.

**Why this matters:** This forces team building to happen BEFORE the battle, not during. Battles become about execution, not improvisation. This also makes the Combo Chain predictable — you always know your Chase Technique, so chain planning is possible.

## 8.3 Move Priority Hierarchy

1. `always_first = True` moves execute before everything
2. Higher `priority` value (positive integers) executes before lower
3. Ties at same priority: highest `base_speed` goes first
4. `always_last = True` moves execute after everything
5. Charge moves (`is_charge_move = True`): spend round 1 charging (do nothing), execute on round 2

## 8.4 Move Type Effectiveness

Standard Pokemon type chart applies. 18 types with super-effective, not-very-effective, and immune relationships. The `_SUPER_EFFECTIVE` dictionary in `ai.py` is the current canonical reference.

**Player-facing type chart must be accessible in the Pokedex and team builder** — players need this for chain planning.

---

# 9. Status Effects Catalog

## 9.1 Three Categories

| Category | Behavior | Examples |
|----------|----------|---------|
| **Persistent** | Survives switching; only one can be active at a time | Burn, Poison, Paralysis, Frozen, Asleep |
| **Volatile** | Cleared when Pokemon switches out; multiple can coexist | Confused, Infatuated, Taunted, Encored |
| **Naruto-Inspired** | Game-original effects; the unique combo chain fuel | Ignited, Immobile, Chaos, Tagged, Corroded |

## 9.2 Complete Status Effect Reference

### Persistent Effects
| Status | Effect | Damage/Turn | Special Rule |
|--------|--------|-------------|--------------|
| **Burned** | Attack ×0.5 | 1/16 max HP | Fire types immune |
| **Poisoned** | — | 2/16 max HP | Poison/Steel types immune |
| **Badly Poisoned** | — | Escalates: 1/16 × turns_active | Poison/Steel types immune |
| **Paralyzed** | Speed ×0.5, 25% chance to skip action | — | Electric types immune |
| **Frozen** | Cannot act | — | Thawed by Fire moves; Ice types immune |
| **Asleep** | Cannot act | — | Wakes up randomly each turn (1–5 turns) |

### Volatile Effects
| Status | Effect | Duration |
|--------|--------|---------|
| **Confused** | 33% chance to hit self instead of target | Random 1–4 turns |
| **Infatuated** | 50% chance to skip action | Until attacker faints |
| **Flinched** | Cannot act this turn | 1 turn only |
| **Bound** | Cannot flee; takes 1/16 damage/turn | 4–5 turns |
| **Seeded** | HP drained to opponent each turn | Until switch-out |
| **Cursed** | 1/4 max HP damage each turn | Indefinite |
| **Nightmare** | 1/4 max HP damage while asleep | Until woken |
| **Taunted** | Cannot use Support/Passive moves | 3 turns |
| **Encored** | Must use last move used | 3 turns |
| **Tormented** | Cannot use same move twice in a row | Indefinite |
| **Heal Blocked** | Cannot recover HP | 5 turns |
| **Perish Song** | Faints in 3 turns | 3 turns |
| **Yawning** | Falls asleep next turn | 1 turn, then → Asleep |

### Naruto-Inspired Effects
| Status | Flavor Name | Effect | Duration |
|--------|-------------|--------|---------|
| **Ignited** | Hellfire Seal | DOT 1/16 + disables healing | Until cured |
| **Immobile** | Restriction Jutsu | Complete turn loss | 1 turn |
| **Chaos** | Chaos Technique | Attacks a random ally instead of enemy | 1 turn |
| **Blinded** | Blindness Seal | Cannot use Standard attacks | 3 turns |
| **Acupunctured** | Meridian Lock | Cannot use Special/Secret moves | 3 turns |
| **Imprisoned** | Cage Prison | Takes 2/16 damage when attempting special moves | Indefinite |
| **Tagged** | Marking Seal | Defense −30%, Sp.Defense −30%; special combos can trigger against this target | Indefinite |
| **Enfeebled** | Power Seal | Attack ×0.5, Sp.Attack ×0.5 | Indefinite |
| **Weakened** | Weakness Seal | All damage output ×0.5 | Indefinite |
| **Corroded** | Corrosion Jutsu | Sp.Defense stripped; worsens each turn | Indefinite |
| **Interrupted** | Cancel Jutsu | Current move cancelled; turn wasted | 1 turn |

## 9.3 Status Immunities

| Type | Immune To |
|------|-----------|
| Fire | Burned, Ignited |
| Electric | Paralyzed |
| Ice | Frozen |
| Poison | Poisoned, Badly Poisoned |
| Steel | Poisoned, Badly Poisoned |
| Water | Ignited |

## 9.4 Status Design Philosophy

The 11 Naruto-inspired statuses are the secret weapon of this game. They enable chains that feel uniquely powerful:

- **Tagged** is the combo enabler — once an enemy is Tagged, ALL your chain links against that target hit harder. A good team can Tag early, then unload a long chain for massive amplified damage.
- **Immobile + Blinded + Acupunctured** create a "lockdown" combo — Immobilize an enemy for a turn, then apply move restrictions. An opponent who can't act AND can't use their best moves is helpless.
- **Chaos** is the chaos wildcard — if your opponent has a Chaos-typed combo starter, you can waste their whole turn making them attack themselves. Counter-play: have Pokemon with Chaos immunity or resistance (not currently implemented — consider adding).

---

# 10. AI Opponent System

## 10.1 Philosophy

The AI must be beatable at Easy but genuinely challenging at Hard. The Hard AI should feel like fighting a skilled human who understands the combo chain system.

**Critical rule:** The AI must never feel "cheating" — it follows the same rules as the player. No hidden stat boosts. Its advantage is INFORMATION (it knows the player's full team) and DECISION-MAKING QUALITY.

## 10.2 Difficulty Tiers

### Easy AI
- Completely random move and target selection (while respecting cooldowns)
- Does not attempt to set up chains
- Targets random active opponent, not strategic low-HP targets
- Purpose: Teaches new players the mechanical flow of battle without pressure

### Medium AI
- Scores moves based on: base power + status bonus (if target doesn't have status already) + chain setup potential
- Slight preference for status-applying moves if it has combo partners
- Adds small random jitter to scoring to prevent perfect predictability
- Purpose: Introduces players to the idea that the AI is thinking about chains

### Hard AI
- Full scoring model:
  - Type effectiveness multiplier applied
  - Targets lowest-HP opponent for kill potential
  - Strongly prefers status-applying moves on clean targets (those without the status yet)
  - Checks if applying a status would trigger its own chain teammates
  - Applies "chaos baiting" — tries to apply Chaos/Confused statuses before the player's turn to disrupt player chains
  - Considers move cooldowns and plans 2–3 rounds ahead (greedy lookahead)
- Purpose: Forces players to counter-strategize, not just execute their planned chain

## 10.3 AI Team Composition

The AI trainer (`__ai_trainer__`) uses pre-built teams for each difficulty:

| Difficulty | Team Philosophy |
|-----------|----------------|
| Easy | Random mix of types; no chain coordination |
| Medium | 2–3 Pokemon that can form a 2-step chain |
| Hard | Full team designed around a 4–5 step chain with backup options |

**Design note:** Hard AI teams should be visible in the Pokedex under "Common Opponent Teams" so players can study them and counter-build. This is not hand-holding — it's strategic transparency.

---

# 11. Economy — Ryo & Sticker Dust

## 11.1 Ryo (Primary Currency)

Ryo (両) is the main currency, named after the traditional Japanese/Naruto coin.

| Source | Amount |
|--------|--------|
| Daily claim | 1,000 Ryo |
| Win a battle | 200 Ryo |
| Lose a battle | 50 Ryo |
| Complete a daily mission | 250–500 Ryo |
| Complete a weekly challenge | 1,000–2,000 Ryo |
| Sell a Pokemon | max(100, level × 50) Ryo |

| Expense | Cost |
|---------|------|
| Sticker Pack | 2,000 Ryo (proposed) |
| Standard Training | 100 Ryo/hr |
| Intense Training | 300 Ryo/4hrs |
| Elite Training | 600 Ryo/8hrs |

**Economy balance check:**
- Daily active player: 1,000 (daily) + 200×3 battles (win) + 250 (mission) = ~1,850 Ryo/day
- A pack costs 2,000 Ryo → roughly one pack per day for a daily active player
- This is good: players feel rewarded without feeling overwhelmed by packs

## 11.2 Sticker Dust (Secondary Currency)

Sticker Dust is earned by dismantling duplicate or unwanted stickers and used to craft specific stickers.

| Rarity | Dismantle Value | Craft Cost |
|--------|----------------|-----------|
| Common | 5 dust | 10 dust |
| Uncommon | 10 dust | 25 dust |
| Rare | 25 dust | 75 dust |
| Epic | 60 dust | 150 dust |
| Holographic | 120 dust | 300 dust |
| Full Art | 200 dust | 500 dust |
| Secret Rare | 300 dust | 1,000 dust |

**Design principle:** Crafting should cost roughly 2–3× the dismantle value. Players can't efficiently convert between rarities — this prevents grinding from devaluing rare stickers.

---

# 12. Sticker Collectible System

## 12.1 Overview

The sticker system is a collectible card game embedded within the battle game. Inspired by:
- **Pokemon TCG Pocket** — pack opening satisfaction and rare art reveals
- **Panini sticker albums** — filling a physical album creates completion satisfaction
- **Marvel Snap** — card variants as identity expression
- **Disney Lorcana** — beautiful art as the primary value driver

## 12.2 Rarity Tiers

| Rarity | Visual Indicator | Drop Rate (approx) | Notes |
|--------|-----------------|-------------------|-------|
| Common | No foil | 60% | Every pack has at least 2 |
| Uncommon | Slight shimmer | 25% | Every pack has at least 1 |
| Rare | Silver foil stamp | 10% | ~1 per 2 packs |
| Epic | Gold foil stamp | 3% | ~1 per 5 packs |
| Holographic | Full rainbow foil | 1.5% | ~1 per 10 packs |
| Full Art | Art covers entire card | 0.4% | ~1 per 30 packs |
| Secret Rare | Animated / Anime style | 0.1% | ~1 per 100 packs |

## 12.3 Variant Types

| Variant | Art Style | Notes |
|---------|-----------|-------|
| `base` | Official-style clean art | Default; most common |
| `shiny` | Alt color palette + metallic finish | Shiny Pokemon aesthetic |
| `battle_scene` | Pokemon mid-attack in dynamic pose | High-energy action art |
| `chibi` | Super-deformed cute style | Most popular with casual collectors |
| `manga_panel` | Black-and-white ink with speed lines | Serious/artistic feel |
| `full_illustration` | Landscape scene featuring the Pokemon | Beautiful environmental art |
| `anime` | **Only on Secret Rare** — animated CSS or GIF overlay | The most coveted sticker |

## 12.4 Pack Contents

Each pack contains exactly 5 stickers:
- 2× Common (guaranteed)
- 1× Uncommon (guaranteed)
- 1× Random (Common–Rare range)
- 1× Rare Roll (chance at Rare or better)

**Pity system (REQUIRED — currently missing from code):**
- Track cumulative packs opened without a Holographic or higher
- At 10 packs without Holographic: next pack guarantees Holographic slot
- At 50 packs without Full Art: next pack guarantees Full Art slot
- At 200 packs without Secret Rare: next pack guarantees Secret Rare slot
- Pity counter resets after each guaranteed pull

**Why pity matters:** Without it, players can go hundreds of packs without a top rarity, which feels hopeless and causes churn. Pity systems are now industry standard (Genshin Impact, Pokemon TCG Pocket, HSR).

## 12.5 Pack Opening Animation (REQUIRED — not yet implemented)

The pack opening experience IS the feature. It must be implemented before any monetization:

1. **Pack appears** — glowing in the player's hand (CSS animation)
2. **Tap to open** — pack tears from the top with a shine effect
3. **Cards reveal one by one** — player taps each card to flip it
4. **Rarity reveal moments:**
   - Common/Uncommon: Standard flip
   - Rare: Silver shine sweep before reveal
   - Epic: Gold particle burst
   - Holographic: Rainbow shimmer; screen briefly flashes
   - Full Art: Dramatic dark-to-reveal transition
   - Secret Rare: Full screen takeover; animated Pokemon
5. **Pack summary** — all 5 stickers shown; "NEW!" badge on first-time pulls
6. **Dust conversion prompt** — "You have 3 duplicates. Convert to 30 dust?"

## 12.6 Album System

The `StickerAlbum` model exists; the album page (`stickers/album.html`) exists. What it needs:

**Current:** Basic list view of owned stickers.

**Required:** A visual grid album where:
- Each Pokemon has a dedicated page showing all 7 rarities × 6 variants (42 slots total)
- Uncollected slots show a silhouette of the sticker art
- Collected slots show the full sticker
- Completion percentage shown per Pokemon and overall
- Filter by: Type, Rarity, Variant, "Missing only"
- Share button: Generate a shareable image of your favorite sticker page

## 12.7 Trading System

The `TradeOffer` model supports peer-to-peer atomic trading. The UI needs:

1. **Trade Board** — public listing of open trade offers, browseable by Pokemon or rarity
2. **Direct Trade** — offer a specific sticker to a specific player
3. **Trade Safety** — both stickers locked during pending offer (`is_trading` flag)
4. **Trade History** — "Recent Trades" for each player's profile
5. **Report system** — flag unfair trades for review

**Trading restrictions (to prevent market manipulation):**
- Secret Rare stickers cannot be traded until the receiving player has been active for 7+ days
- Maximum 5 pending trade offers per player at any time
- Trade cooldown: same two players can only trade once per 24 hours

## 12.8 Showcase System

Players can pin up to 6 stickers to their public profile as a "Showcase" (`is_showcase` flag).

The showcase is the game's primary social identity signal. A player's showcase tells you their taste, their collection level, and their favorite Pokemon.

**UI:** Showcase stickers appear as physical-style cards on the profile page, slightly tilted, with hover effects showing the full art.

---

# 13. Player Progression & Statistics

## 13.1 Profile Stats (Current)

| Stat | Storage | Display |
|------|---------|---------|
| Battles played | `User.battles_played` | Profile |
| Battles won | `User.battles_won` | Profile |
| Win rate | Computed property | Profile |
| Longest combo chain | `User.longest_combo_chain` | Profile + Leaderboard |
| Sticker dust | `User.sticker_dust` | Nav bar |
| Ryo | `User.ryo` | Nav bar |

## 13.2 Battle Statistics (To Add)

| New Stat | How to Track | Why |
|---------|-------------|-----|
| Favorite Pokemon (most battles with) | Count from BattleSlot | Profile flavor |
| Total combo links triggered | Sum from BattleAction | Shows dedication to the core mechanic |
| Average combo chain length | Avg per battle | Skill indicator |
| Stickers collected | Count | Collection progress |
| Stickers dismantled | Count | Investment indicator |
| Trades completed | Count from TradeHistory | Social indicator |

## 13.3 Trainer Rank / Prestige

Beyond the ranked PvP season tier, add a permanent **Trainer Prestige** level:

| Prestige Level | Name | Required Points | Reward |
|---------------|------|----------------|--------|
| 1 | Academy Student | 0 | Starter pack |
| 5 | Genin Trainer | 500 | Extra sticker pack slot |
| 10 | Chunin Trainer | 2,000 | Exclusive sticker border |
| 20 | Jonin Trainer | 8,000 | Animated profile banner |
| 30 | Elite Trainer | 20,000 | Title: "Chain Master" |
| 50 | Kizuna Master | 75,000 | Secret Rare guaranteed monthly |

Prestige points: 10 per battle, 25 per win, 50 per daily mission, 100 per weekly challenge.

---

# 14. Quest & Mission System

## 14.1 Daily Missions

Three missions refreshed every day at midnight (UTC). Players can complete all 3 for maximum rewards.

### Daily Mission Pool (examples)

| Mission | Reward |
|---------|--------|
| Win 1 battle | 250 Ryo |
| Win 2 battles | 400 Ryo |
| Achieve a 3-link combo chain | 300 Ryo + 20 Sticker Dust |
| Use a Fire-type move 5 times | 200 Ryo |
| Win a battle using only Naruto-status moves | 500 Ryo |
| Open 1 sticker pack | 100 Ryo |
| Complete a training session | 150 Ryo |
| Trade a sticker | 200 Ryo |

## 14.2 Weekly Challenges

One set of 3 harder missions reset every Monday:

| Challenge | Reward |
|-----------|--------|
| Win 5 battles | 2,000 Ryo + 1 Sticker Pack |
| Achieve a 6-link combo chain | 3,000 Ryo + Rare sticker craft voucher |
| Win against Hard AI 3 times | 2,500 Ryo + 100 Sticker Dust |
| Complete all daily missions 5 days in a row | 5,000 Ryo + Epic sticker |

## 14.3 Story Quests

Story quests unlock progressively as the player advances through Acts:

| Quest | Act | Reward | Unlocks |
|-------|-----|--------|---------|
| "First Steps" — Win your first battle | Act 1 | Starter sticker pack | Album page |
| "Chain Initiation" — Achieve a 2-link combo | Act 1 | Rare sticker of your starter | AI Medium difficulty |
| "The Method" — Win 5 battles total | Act 1 | Sensei Kira's signature Pokemon | Story Act 2 |
| "Tournament Ready" — Build a team of 6 | Act 2 | 3 Sticker Packs | Tournament mode |
| "Combo Mastery" — Achieve a 5-link chain | Act 2 | Exclusive Battle Scene sticker | Ranked PvP |
| "The Severed Revealed" — Defeat Act 3 story battle | Act 3 | Commander Kurai's signature move (learnable) | Hard AI |
| "Chain of Ten" — Achieve a 10-link chain | Any | Secret Rare sticker + Title "Kizuna Master" | Post-game content |
| "Purification" — Complete the Restoration Battle | Act 4 | Legendary encounter unlock | Post-game legendary |

## 14.4 Achievement Badges (Permanent)

Badges are displayed on the trainer profile page:

| Badge | Condition | Rarity |
|-------|-----------|--------|
| ⚡ Chain Initiate | First 2-link combo | Common |
| 🔥 Chain Warrior | 5-link combo | Uncommon |
| 🌀 Chain Master | 10-link combo | Rare |
| 🏆 First Victory | Win first battle | Common |
| 💯 Centurion | Win 100 battles | Rare |
| 📖 Collector | Own 50 stickers | Uncommon |
| 🌟 Archivist | Own 200 stickers | Rare |
| 💎 Secret Hunter | Own 1 Secret Rare | Epic |
| 🤝 Trader | Complete 10 trades | Uncommon |
| ☀️ Daily Devotion | Claim daily reward 30 days in a row | Rare |
| 🎯 Perfect Victory | Win a battle with no Pokemon fainted | Uncommon |
| 🤖 AI Breaker | Defeat Hard AI 10 times | Rare |
| 👑 Champion | Reach Diamond tier in PvP | Epic |

---

# 15. PvP Multiplayer & Ranked Seasons

## 15.1 Current State & Blockers

The WebSocket consumer exists (`game/consumers.py`). The current blocker is:
- No PvP matchmaking/lobby system
- InMemoryChannelLayer only supports single-process — no real multi-user WebSockets
- No ranked tier tracking model

**Required before PvP:** Deploy `channels_redis` in production (documented in memory).

## 15.2 PvP Architecture

### Matchmaking Queue
```
Player enters queue → Server finds opponent at similar rank → 
Creates Battle record → Both players redirected to battle room → 
WebSocket connection established → Battle begins
```

### Battle Room
- Both players see the same board state via WebSocket broadcast
- Each player selects their action privately; server reveals simultaneously
- Timeout: 90 seconds to select action; auto-pass on timeout
- Disconnection: 60-second grace period; forfeit if not reconnected

## 15.3 Ranked Season System

**Season duration:** 90 days (approximately quarterly)

**Tiers:**

| Tier | Rank Points Required | Battle Reward | Demotion |
|------|---------------------|---------------|---------|
| Bronze I–III | 0–299 | Standard | No demotion from Bronze |
| Silver I–III | 300–799 | +50 Ryo/win | Yes, can fall to Bronze III |
| Gold I–III | 800–1,499 | +100 Ryo/win | Yes |
| Platinum I–III | 1,500–2,499 | +150 Ryo/win | Yes |
| Diamond I–III | 2,500–3,999 | +200 Ryo/win | Yes |
| Champion | Top 100 players | +300 Ryo/win | Yes; must stay in top 100 |

**Points:**
- Win: +20 points
- Loss: −10 points (floor: can't drop below current tier floor)
- Win streak (3+): +5 bonus points per win

**Season-End Rewards:**

| End Tier | Reward |
|---------|--------|
| Bronze | 2,000 Ryo |
| Silver | 5,000 Ryo + Season-exclusive Common sticker |
| Gold | 10,000 Ryo + Season-exclusive Rare sticker |
| Platinum | 20,000 Ryo + Season-exclusive Epic sticker |
| Diamond | 40,000 Ryo + Season-exclusive Holographic sticker |
| Champion | 80,000 Ryo + Season-exclusive Secret Rare sticker + Champion frame |

**Season theme:** Each season is themed around a story chapter or event (e.g., "Season of Kizuna," "Season of the Void"). Sticker rewards match the theme art.

---

# 16. Visual Design & Branding

## 16.1 Game Title & Logo

**Game Name:** Pokemon Combo Battle (current, fan-project name)
**Logo Concept:** The word "Combo" in bold with a lightning chain graphic replacing the "o" — links of a chain that spark electricity. Color: #e94560 on #1a1a2e.

**Font for title/logo:** Chakra Petch Bold (free Google Font — has a tech/ninja aesthetic with geometric cuts)

## 16.2 Master Color Palette

### Primary Dark Theme (Current — Maintain & Refine)

| Token Name | Hex | Usage |
|-----------|-----|-------|
| `--bg-primary` | `#1a1a2e` | Page background, main surfaces |
| `--bg-secondary` | `#16213e` | Cards, nav bar, panels |
| `--bg-elevated` | `#0f3460` | Highlighted surfaces, modals, badges |
| `--accent-red` | `#e94560` | Primary CTA, borders, links, active states |
| `--accent-red-hover` | `#c73652` | Hover state for red elements |
| `--gold` | `#f5a623` | Ryo currency, combo chain counter, rewards |
| `--gold-pale` | `#fbbf24` | Secondary gold, chain text highlights |
| `--combo-blue` | `#00d4ff` | Combo chain visual effects, chain links |
| `--combo-glow` | `rgba(0, 212, 255, 0.4)` | Chain particle effects, glow halos |
| `--hp-green` | `#4ade80` | HP bar (> 50%) |
| `--hp-yellow` | `#facc15` | HP bar (25–50%) |
| `--hp-red` | `#ef4444` | HP bar (< 25%) |
| `--text-primary` | `#f1f5f9` | Main body text |
| `--text-secondary` | `#9ca3af` | Subtitles, captions |
| `--text-muted` | `#4b5563` | Footer, disabled states |
| `--border-dark` | `#0f3460` | Standard borders |
| `--border-accent` | `#e94560` | Featured/highlighted borders |

### Pokemon Type Colors

| Type | Background | Text |
|------|-----------|------|
| Normal | `#374151` | `#d1d5db` |
| Fire | `#7f1d1d` | `#fca5a5` |
| Water | `#1e3a5f` | `#93c5fd` |
| Grass | `#14532d` | `#86efac` |
| Electric | `#78350f` | `#fcd34d` |
| Ice | `#0f4c75` | `#bae6fd` |
| Fighting | `#7c2d12` | `#fdba74` |
| Poison | `#581c87` | `#d8b4fe` |
| Ground | `#451a03` | `#fde68a` |
| Flying | `#0c4a6e` | `#bae6fd` |
| Psychic | `#4a044e` | `#f0abfc` |
| Bug | `#365314` | `#bef264` |
| Rock | `#44403c` | `#d6d3d1` |
| Ghost | `#2d1b69` | `#c4b5fd` |
| Dragon | `#1e1b4b` | `#a5b4fc` |
| Dark | `#1c1917` | `#d6d3d1` |
| Steel | `#334155` | `#cbd5e1` |
| Fairy | `#701a75` | `#f5d0fe` |

## 16.3 Typography

| Role | Font | Weight | Size |
|------|------|--------|------|
| Game Title / Hero Headers | Chakra Petch | Bold (700) | 2rem–4rem |
| Section Headers | Plus Jakarta Sans | Bold (700) | 1.25rem–2rem |
| Body Text | Plus Jakarta Sans | Regular (400) | 0.875rem–1rem |
| Battle Log / Numbers | JetBrains Mono | Regular (400) | 0.8rem–0.9rem |
| Badges / Labels | Plus Jakarta Sans | SemiBold (600) | 0.65rem–0.75rem (uppercase) |

**Load from Google Fonts:**
```html
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@700&family=Plus+Jakarta+Sans:wght@400;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
```

## 16.4 Sticker Art Direction

Each variant has a distinct visual language:

| Variant | Art Direction | Key Element |
|---------|--------------|-------------|
| **Base** | Clean official style; white/gradient background | Centered Pokemon, clean outlines |
| **Shiny** | Alternate color palette; metallic finish overlay | Gold/silver sparkle particles |
| **Battle Scene** | High energy; motion blur; dramatic angle | Attack pose with speed lines |
| **Chibi** | Super-deformed; 2:1 head-to-body ratio; pastel colors | Cute expression; round eyes |
| **Manga Panel** | Black/white ink; screentone shading; panel border | Speed lines; halftone dots |
| **Full Illustration** | Environmental art; Pokemon in a meaningful landscape | No border; full bleed art |
| **Anime** | Animated CSS; glowing aura; color loop | Only on Secret Rare; 3+ second animation loop |

## 16.5 Rarity Visual Indicators

| Rarity | Card Border | Card Background | Special Effect |
|--------|------------|----------------|---------------|
| Common | Thin gray | Flat white | None |
| Uncommon | Green shimmer edge | Slight gradient | None |
| Rare | Silver foil edge | Silver gradient | Sweep shine on hover |
| Epic | Gold foil edge | Deep gold gradient | Gold particles |
| Holographic | Rainbow edge | Full rainbow gradient | CSS hue-rotate animation |
| Full Art | No border (art fills card) | Art-driven | Parallax tilt on hover |
| Secret Rare | Animated glowing edge | Animated | Full animation + screen pulse |

## 16.6 Combo Chain Visual Effect Specification

When a combo chain triggers during battle:

1. **Combo Counter** — Top-center of battle screen. Font: Chakra Petch Bold 3rem. Color cycles: white → yellow → gold → red as chain grows. Bounces with each new link.

2. **Chain Link Line** — A visible line draws from the triggering Pokemon to the triggered Pokemon across the screen. Color: `--combo-blue`. Animates like electricity (wobble effect).

3. **Attacker Glow** — The triggering Pokemon's card pulses with `--combo-glow` for 0.5 seconds.

4. **Hit Number** — Damage number flies out of the target. Color: orange for normal, red for super effective, blue for combo link.

5. **Chain Summary Bar** — After chain resolves, a banner slides in from the bottom: "COMBO ×4 — 1,247 total damage!" in gold.

6. **Personal Best** — If this chain exceeds the player's `longest_combo_chain`: entire screen flashes gold briefly, "NEW RECORD!" banner appears.

---

# 17. UI/UX Design System

## 17.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Information at a glance** | HP, status effects, move cooldowns must all be visible without clicking |
| **Action is obvious** | What to click next must never require guessing |
| **Fast battles** | A battle round should not take more than 30 seconds for an experienced player |
| **Mobile-first** | Most players will be on mobile — all critical actions must work on 375px width |
| **Accessible** | Color-blind friendly alternatives for HP bars; text labels alongside color indicators |

## 17.2 Component Library

### Pokemon Card (in battle)
```
╔══════════════════════════════╗
║  [Sprite 80×80]  Charizard   ║  ← Name + Level
║                  Lv. 52      ║
║  [████████░░] 340/420 HP     ║  ← HP bar (color-coded) + numbers
║  [🔥] [⚡PARA] [🌀CONFUSE]  ║  ← Status badges (icons + text)
║  FRONT-LEFT | Burn active    ║  ← Grid position
╚══════════════════════════════╝
```

### Move Button (player action)
```
╔══════════════════════════╗
║ ⚡ Thunder Wave          ║  ← Type icon + name
║ Basic Technique          ║  ← Slot type (sub-label)
║ PWR: 40 | Applies: PARA  ║  ← Power + status info
║ [Ready]                  ║  ← Cooldown state: Ready / Cooldown: 2
╚══════════════════════════╝
```

### Combo Chain Log Entry
```
[⚡ Chain ×3] Gengar → Shadow Ball → Confusion applied
[⚡ Chain ×4] Alakazam triggered by Confusion → Psychic (294 dmg)
```

## 17.3 Animation Principles

| Animation | Duration | Easing |
|-----------|----------|--------|
| Card hover lift | 150ms | ease-out |
| HP bar drain | 400ms | ease-in-out |
| Combo counter increment | 100ms | cubic-bezier(0.34, 1.56, 0.64, 1) (spring) |
| Chain line draw | 300ms | ease-in |
| Status badge appear | 200ms | ease-out (scale from 0) |
| Screen flash | 150ms | ease-out (fade to white, back) |
| Pack card flip | 600ms | ease-in-out (3D flip) |

**Performance rule:** All battle animations must complete in ≤ 600ms total so the game doesn't feel slow on mobile.

## 17.4 Responsive Breakpoints

| Breakpoint | Width | Layout Change |
|-----------|-------|--------------|
| Mobile | < 480px | Single column; battle grid stacks vertically |
| Tablet | 480–768px | 2-column grid; simplified nav |
| Desktop | > 768px | Full 2×2 grid side by side; full nav |

---

# 18. Screen Map & Navigation

## 18.1 Current Screens (Confirmed Built)

```
/ (landing)
├── /login
├── /register
├── /home (game hub)
├── /battles
│   ├── /battles/create (vs human — PvP placeholder)
│   ├── /battles/ai/create (vs AI — working)
│   ├── /battles/<id> (battle detail/view)
│   ├── /battles/<id>/action (submit move — working)
│   └── /battles/<id>/log (battle log)
├── /pokemon
│   ├── /pokemon/pokedex (browse all Pokemon)
│   ├── /pokemon/<id> (species detail)
│   ├── /pokemon/my (owned Pokemon)
│   ├── /pokemon/my/<id> (owned Pokemon detail)
│   └── /pokemon/team (team manager)
├── /stickers
│   ├── /stickers/album (collection viewer)
│   ├── /stickers/packs/buy (buy packs)
│   ├── /stickers/packs/open/<id> (open pack — animation needed)
│   ├── /stickers/dust/convert (dismantle → dust)
│   ├── /stickers/dismantle (new — needs wiring)
│   ├── /stickers/craft (craft from dust)
│   ├── /stickers/trade (trade board)
│   ├── /stickers/trade/create (new offer)
│   └── /stickers/trade/<id> (trade detail)
└── /users
    ├── /users/daily (claim daily Ryo)
    └── /users/profile/<username> (trainer profile — MISSING, needs building)
```

## 18.2 Missing Screens (Required to Build)

| Screen | Priority | Notes |
|--------|----------|-------|
| `/users/profile/<username>` | HIGH | Public trainer profile with showcase, stats, badges |
| `/quests` | HIGH | Daily/weekly/story mission tracker |
| `/leaderboard` | MEDIUM | Global and season leaderboard |
| `/pokemon/team/builder` | HIGH | Enhanced team builder with combo chain preview |
| `/ranked` | MEDIUM | PvP queue and ranked season tracker |
| Tutorial flow | HIGH | First-time experience overlay on home screen |

---

# 19. Features to REMOVE & Why

These are design problems in the current codebase that should be corrected. Brief explanation provided because you asked for short explanations on these.

---

### 19.1 The Legacy `pokemon.moves` Many-to-Many Field

**What it is:** The `Pokemon.moves` M2M field that links species directly to moves without slot assignments.

**Why remove it:** It duplicates the `SpeciesMovePool` model which does the same job better (with slot types, role tags, and generation tags). Having two systems means content must be entered twice and developers must remember to check both. The battle code that still reads from `pokemon.moves` should be migrated to read from `SpeciesMovePool` instead.

**Action:** Audit all code that reads `pokemon.moves.all()`. Migrate those reads to use `SpeciesMovePool`. Then remove the M2M field.

---

### 19.2 The `pp` Field on the Move Model

**What it is:** `Move.pp` tracks how many times a move can be used before PP is exhausted (classic Pokemon mechanic).

**Why remove it (or implement it):** The field exists on every Move but there is NO per-battle PP tracking. This means PP is stored but never consumed. Players could see `pp=10` in the UI and expect it to matter — it doesn't.

**Two options:**
1. **Remove the field** (recommended for now) — simplify the model until PP tracking is intentionally built
2. **Implement PP tracking** — add a `MovePP` model per `BattleSlot×Move`, decrement on use, enforce PP limit

**Why option 1 is right for now:** The game already has Move Cooldowns, which serve a similar "limited use" role. Adding PP tracking on top would double the complexity for new players without adding meaningful differentiation.

---

### 19.3 The 2×2 Grid With No Positional Mechanics

**What it is:** The `GridPosition` system (front_left, front_right, back_left, back_right) that exists in the model and presumably in the UI, but does not affect damage, targeting, or any mechanical outcome.

**Why this is a problem:** A UI that shows "FRONT-LEFT" or "BACK-RIGHT" implies those positions mean something to the player. If they don't, it creates confusion and wastes the player's cognitive bandwidth.

**Action:** Implement the positional damage rules described in Section 5.2, OR simplify to a flat ordered list (position 1–4) with no positional labels until positional mechanics are ready.

**Do NOT remove the grid model** — it's the right architecture. Just make it mechanically meaningful before exposing it.

---

### 19.4 Always-Showing Bench Slots When Switching Isn't Implemented

**What it is:** The bench slots (BENCH_1, BENCH_2) visible in team setup and potentially in battle UI.

**Why:** If players cannot switch mid-battle, showing bench slots creates the expectation that they can. This is a promise the game doesn't keep.

**Action:** Hide bench from the battle UI until bench switching is implemented. Keep the model (needed for future). During team setup, show bench as "Reserve (cannot switch in yet)" with a clear tooltip.

---

### 19.5 Missing Sticker Award Triggers in Battle Views

**What it is:** Sticker award services (`StickerService.award_sticker()`) and tests exist, but the views never call them. Players who win battles don't get stickers.

**Why this is a critical bug, not a design removal:** This feature is BUILT but not WIRED. It must be connected immediately — the sticker system is the collection loop, and if stickers are never awarded, the whole collection system is invisible.

**Action:** Wire sticker award calls into `BattleService._finish_battle()`. Award 1 sticker pack after every 10 wins (already the intended design per the `StickerPack` docstring).

---

# 20. Features to ADD & Why

These are new features that will make the game successful. Brief explanation provided; technical details in Section 21.

---

### 20.1 Combo Chain Damage Amplification ⭐ HIGH PRIORITY

**What:** Each link in a chain adds a damage multiplier (see Section 6.3 table).

**Why:** The combo chain is the signature mechanic but currently longer chains don't deal proportionally more damage than a single strong move. Players have no mathematical reason to prefer a 5-chain over a direct hit. The amplification makes chains feel exponentially rewarding — which is the whole point of the game.

---

### 20.2 Pack Opening Animation ⭐ HIGH PRIORITY

**What:** A card-by-card animated reveal when opening a sticker pack (see Section 12.5 for full spec).

**Why:** Pack opening is the primary dopamine moment of the sticker system. Without animation, it's just a database insert. WITH animation, it's an event. This single feature will increase sticker pack engagement by an estimated 3–5× based on similar games (Pokemon TCG Pocket's pack opening is a major social media content category).

---

### 20.3 Quest & Mission System ⭐ HIGH PRIORITY

**What:** Daily missions (3/day), weekly challenges, and story quests (see Section 14).

**Why:** Players currently have no structured reason to log in daily beyond the Ryo claim. Missions give goals, which gives sessions purpose. Purpose drives retention. This is the single highest-impact retention feature to build.

---

### 20.4 Grid Positional Mechanics ⭐ HIGH PRIORITY

**What:** Back row takes 80% damage from direct attacks; front row must be eliminated before back row can be targeted (see Section 5.2).

**Why:** Makes team positioning a real strategic decision that ties into combo chain planning. Should your combo starter be protected in back row? This unlocks a new layer of strategy the game currently lacks.

---

### 20.5 Pity System for Sticker Packs ⭐ HIGH PRIORITY

**What:** Guaranteed rare pulls after opening a certain number of packs without one (see Section 12.4).

**Why:** Without pity, players can go hundreds of packs with no top-rarity pull. This feels unfair and causes churn. Industry standard in all modern gacha games. Without this, the sticker system cannot be monetized ethically.

---

### 20.6 Trainer Profile Page ⭐ HIGH PRIORITY

**What:** Public profile page showing: showcase stickers, battle stats, achievement badges, recent trade history, and ranked tier.

**Why:** Social identity drives trading. Players need to see each other. Without profiles, the trading system has no social context — you're trading with a username, not a person.

---

### 20.7 Tutorial / First-Time Experience 🔴 HIGH PRIORITY

**What:** An interactive first-time experience that teaches the combo chain through a scripted battle. Pop-up tooltips, guided team building, first battle against a fixed-script AI that shows a combo in action.

**Why:** The combo chain system is non-obvious. New players who don't understand it will lose to the AI repeatedly and churn. The tutorial IS the most important onboarding investment.

---

### 20.8 Bench Switching in Battle

**What:** Players can spend their action to swap a bench Pokemon into an active slot (see Section 5.6).

**Why:** Makes the 6-Pokemon team relevant rather than just "first 4 win." Adds strategic depth: hold a counter-Pokemon on the bench for specific threats. Also creates interesting mid-battle pivots.

---

### 20.9 Leaderboard

**What:** Global leaderboard for: most wins (all-time), longest combo chain (all-time), current season rank.

**Why:** Competition is a massive engagement driver. Players will grind for position. The longest combo chain leaderboard specifically incentivizes mastering the core mechanic.

---

### 20.10 Combo Chain Chain Preview in Team Builder

**What:** A visual overlay in the team builder that shows which Pokemon trigger which. Arrows drawn between slots: "If Pokemon A applies [status], Pokemon B will trigger with [move]."

**Why:** Team building for combos is currently a puzzle you solve externally (pen and paper, spreadsheet). Bringing it in-game makes the team builder sticky — players spend time there discovering combinations. This also teaches new players HOW combos work through exploration.

---

### 20.11 Achievement Badge System

**What:** Permanent badges earned by milestones (see Section 14.4).

**Why:** Badges are collection items that don't expire. Players who've completed all badges have infinite replay value in earning them on new accounts or in showing them off. They're also social proof — a "Chain Master" badge immediately tells other players you're experienced.

---

### 20.12 Seasonal PvP Ranked System

**What:** 90-day ranked seasons with tiers (Bronze through Champion) and exclusive seasonal rewards (see Section 15).

**Why:** Ranked seasons are the engine of long-term engagement for competitive players. The season-end reward (exclusive Secret Rare sticker for top tiers) creates urgency every quarter. Season themes tied to story chapters extend the narrative.

---

### 20.13 Sticker Album Completion Rewards

**What:** When a player collects all stickers for a specific Pokemon (all 42 combinations), they receive a bonus reward. When they complete all Gen 1 Pokemon, they receive a legendary reward.

**Why:** Completion rewards give the album a meta-goal. Currently players collect stickers with no destination. Completion rewards convert collectors into goal-oriented players.

---

### 20.14 Type Advantage Chart in UI

**What:** An accessible in-game type chart showing all 18 type relationships, accessible from the Pokedex and Team Builder.

**Why:** Players need to know type matchups to plan chains effectively. Right now they need to consult external sources (Bulbapedia, etc.). Bringing it in-game keeps players in the game.

---

### 20.15 Spectator Mode

**What:** Ability to watch an ongoing battle between two other players in real-time (read-only WebSocket stream).

**Why:** Spectating teaches strategy better than any tutorial. Competitive spectating also builds community (team players cheer for guild members). When PvP content is streamed, it brings external players to the game.

---

# 21. Technical Architecture Notes

*These are observations for the development team, not change requests. Full implementation details belong in technical design docs.*

## 21.1 Current Architecture Summary

| Component | Technology | Status |
|-----------|-----------|--------|
| Backend | Django 5.0.6, Python 3.13 | Solid; maintain |
| Database | SQLite (dev), should be PostgreSQL (prod) | Migrate before production |
| Real-time | Django Channels + WebSocket | Works; needs Redis for multi-process |
| Frontend | Django templates + inline CSS/JS | Functional but needs component extraction |
| Auth | Django Auth + custom User model | Solid |
| Testing | pytest, 156 tests, factory_boy + Allure | Excellent |

## 21.2 Key Technical Debts

| Debt | Impact | Priority |
|------|--------|----------|
| InMemoryChannelLayer (no Redis) | PvP requires real multi-user WS | Block on PvP |
| No static file CDN | Production image serving undefined | Block on production |
| Legacy `pokemon.moves` M2M | Dual-entry for all moves | Medium |
| No positional damage rules | Grid UI is decorative | Medium |
| Sticker award not wired to battles | Collection loop broken | HIGH |
| No pity system | Sticker monetization unethical | HIGH |
| `pp` field unused | Model confusion | Low |

## 21.3 Recommended Production Stack

| Layer | Technology |
|-------|-----------|
| Web server | Nginx + Daphne (already Dockerized) |
| Channel layer | channels_redis (add to requirements) |
| Database | PostgreSQL (add `psycopg2-binary`) |
| Static files | WhiteNoise + S3/CloudFront |
| Secrets | Environment variables (already using `os.environ`) |

## 21.4 WebSocket Event Types

The combo chain system produces these WebSocket events (broadcast to battle room):

| Event | When | Data |
|-------|------|------|
| `round_start` | Beginning of each round | Round number |
| `action_resolved` | Each move executes | Attacker, move, target, damage, status |
| `combo_triggered` | Combo chain link fires | Chain position, chain total |
| `status_applied` | Status effect applied | Status name, target, duration |
| `pokemon_fainted` | HP reaches 0 | Slot ID |
| `battle_ended` | Win condition met | Winner ID |
| `round_complete` | All actions resolved | Round summary |

---

# 22. Content Production Pipeline

## 22.1 Pokemon Addition Checklist

When adding new Pokemon to the game, complete in this order:

1. [ ] Add `Pokemon` species record (name, types, base stats, pokedex_number, sprite_url)
2. [ ] Add `SpeciesMovePool` entries for ALL 5 slot types (standard, chase, special, support, passive)
3. [ ] Ensure each chase move has a `trigger_status` set
4. [ ] Ensure each standard move has an `applies_status` set (if it's a chain-starter species)
5. [ ] Set `primary_role` (tactical role for team builder filtering)
6. [ ] Add `Generation` link for the species
7. [ ] Run `check_move_pools` management command to verify all slot types covered
8. [ ] Add sticker entries for at least Common + Uncommon variants
9. [ ] Verify in team builder that chain preview shows correct arrows

## 22.2 Status Effect Addition Checklist

1. [ ] Add to `StatusName` enum in `effects/constants.py`
2. [ ] Add to appropriate category set (PERSISTENT / VOLATILE / NARUTO_STATUSES)
3. [ ] Add `DEFAULT_DURATIONS` entry
4. [ ] Add `STAT_MODIFIERS` entry if it modifies stats
5. [ ] Add `DAMAGE_PER_TURN_SIXTEENTHS` entry if it deals damage
6. [ ] Add type immunity to `TYPE_IMMUNITIES` if applicable
7. [ ] Create `StatusEffect` fixture entry
8. [ ] Implement the effect in `StatusEffectEngine`
9. [ ] Write tests for the new status behavior

---

# 23. Monetization Strategy

*Since this is a fan project, traditional monetization is not possible. These notes are for when original IP is developed.*

## 23.1 If Converted to Original IP

| Revenue Stream | Model | Notes |
|---------------|-------|-------|
| Sticker Packs | Ryo (earnable) + cosmetic only | Never pay-to-win |
| Battle Pass | Monthly subscription; seasonal rewards | Exclusive cosmetics, not stat advantages |
| Creator packs | Collaboration art packs | Limited time |
| Supporter tier | Cosmetic title + profile frame | Direct support option |

**Non-negotiable design principle:** The game must be fully enjoyable and competitive without spending any money. Spending only accelerates collection; it never improves battle performance.

## 23.2 Current Fan Project Approach

- No monetization
- No ads
- Server costs covered by creator
- All stickers earnable through gameplay only

---

# 24. Development Roadmap

## Phase 1 — Critical Fixes (Do First)

| Task | Rationale |
|------|-----------|
| Wire sticker award to battle wins | The collection loop is broken without this |
| Add pity system to pack opening | Required before any pack monetization discussion |
| Implement positional damage rules (80% back row) | Grid UI is misleading without mechanics |
| Add chain damage amplification (Section 6.3) | The core mechanic lacks exponential payoff |
| Fix pack opening with animation | Pack opening without animation is non-functional |

## Phase 2 — Core Experience Completion

| Task | Rationale |
|------|-----------|
| Tutorial / first-time experience | Churn prevention; most important retention feature |
| Quest & mission system | Daily engagement hook |
| Trainer profile page | Social foundation for trading |
| Combo preview in team builder | Makes team building sticky and educational |
| Type chart in UI | Removes reliance on external sites |
| Achievement badge system | Milestone satisfaction and collection completion |
| Bench switching in battle | Makes 6-Pokemon teams meaningful |

## Phase 3 — Competitive Layer

| Task | Rationale |
|------|-----------|
| Deploy Redis (channels_redis) | Required for PvP |
| PvP matchmaking queue | The main long-term content for competitive players |
| Ranked season system | 90-day engagement cycle |
| Leaderboard | Competition driver |
| Spectator mode | Community building |

## Phase 4 — Depth & Polish

| Task | Rationale |
|------|-----------|
| Story quest narrative (full 5 acts) | Long-term narrative for engaged players |
| Seasonal events | Fresh content every quarter |
| Album completion rewards | Converts collectors to goal-oriented players |
| Sticker album visual overhaul | Collection experience must match the art quality |
| Guild/clan system | Social retention |
| Original IP creature design | Future-proofing; removes IP risk |

## Phase 5 — Expansion

| Task | Rationale |
|------|-----------|
| Generation 2 Pokemon | Double the combo possibilities |
| New Naruto-inspired status effects | Combo chain depth expansion |
| Mobile app wrapper (PWA) | Accessibility on mobile |
| API for community tools | Team building calculators, combo databases |

---

# Appendix A: Combo Chain Design Examples

## Example Chain: "The Storm Setup"

**Team:** Jolteon (CONTROL) + Gengar (ASSASSIN) + Espeon (SUPPORT) + Alakazam (DPS)

| Link | Actor | Move | Status Applied | Triggers |
|------|-------|------|---------------|---------|
| 1 | Jolteon | Thunder Wave (Standard) | Paralysis | Gengar |
| 2 | Gengar | Shadow Sneak (Chase) | None | — |
| Chain ends | | | | |

**Chain length:** 2. Damage: ×1.10 on link 2.
**Lesson:** Even a 2-chain is +10% damage and forces the opponent to respond to Paralysis.

## Example Chain: "The Lockdown Chain"

**Team:** Hypno (CONTROL) + Arcanine (DPS) + Electrode (SUPPORT) + Alakazam (DPS)

| Link | Actor | Move | Status Applied | Triggers |
|------|-------|------|---------------|---------|
| 1 | Hypno | Hypnosis (Standard) | Sleep | Arcanine |
| 2 | Arcanine | Fire Spin (Chase) | Bound | Alakazam |
| 3 | Alakazam | Nightmare (Chase) | Nightmare | — |
| Chain ends | | | | |

**Chain length:** 3. The enemy is Asleep + Bound + experiencing Nightmare damage. Next round: Nightmare deals 1/4 max HP while they can't act. Brutal setup.

## Example Chain: "The Perfect Storm (MAX CHAIN GOAL)"

**Team:** Control starter + 4 status trigger Pokemon

For a player to achieve a 10-chain, they would need:
- 4 active Pokemon each capable of triggering and then applying a NEW status
- Target must survive long enough for all 10 links
- None of the (attacker, move) pairs repeat

This is the endgame mastery challenge. It requires specific team building, knowledge of all 30 statuses, and perfect execution. The player who hits a 10-chain has truly mastered the Kizuna Method.

---

# Appendix B: Status Effect → Trigger Move Mapping Guide

*For content creators when assigning trigger_status to Chase moves*

Each chase move should trigger on exactly one status. Design for chain synergy:

| Works Well Together | Reason |
|--------------------|--------|
| Burn → Fire-type Chase | Thematic; Fire trainer chain |
| Paralysis → Electric or Psychic Chase | Paralysis is electric-caused; psychic reads the locked mind |
| Sleep → Ghost or Dark Chase | Hit them while they're unconscious |
| Poison → Grass or Poison Chase | Synergistic DOT stacking |
| Tagged → High-power DPS Chase | Tagged drops defenses; capitalize with big damage |
| Chaos → Control Chase | Target is confused; restrict them further |
| Corroded → Special attacker Chase | Corroded drops Sp.Defense; Sp.Atk move hits enormously |

---

*End of Document*

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-06  
**Author:** Game Design Collective (Claude + Luis)  
**Status:** Living document — update as design evolves. When code changes contradict this doc, update the doc to reflect the intended design, then fix the code.
