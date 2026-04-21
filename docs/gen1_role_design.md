# Gen 1 Role Design — Move Pool Blueprint

## Design Philosophy

### Core Rules
1. **Evolution shifts identity, not power.** Stats are equal across a line. What changes is *role* and *playstyle*.
2. **Each role owns a move slot behavior:**
   - **Burst** — Standard attack applies a status → auto-triggers a Chase move (the combo engine)
   - **Combo** — Standard attack chains into itself or amplifies the next Combo move in sequence
   - **Tank** — Standard attack heals self or applies a Shield; has a passive damage-reduction trigger
   - **Support** — Standard attack deals damage AND cleanses 1 debuff from a friendly; healing moves as cooldowns
   - **Control** — Standard attack applies crowd-control (sleep, confuse, paralyze, trap) with no self-damage
3. **Types reinforce roles, not replace them.** A Water Tank and a Rock Tank feel different but both fulfil the Tank contract.
4. **Evolution line patterns:** early stage = aggressive/mobile, mid stage = hybrid, final stage = specialized anchor.

### Type → Role Tendencies
| Type | Natural Lean |
|------|-------------|
| Fire | Burst / Combo |
| Water | Tank / Support |
| Grass | Control / Support |
| Electric | Combo / Burst |
| Psychic | Control / Combo |
| Ground | Tank / Burst |
| Rock | Tank |
| Ice | Control / Tank |
| Fighting | Burst / Combo |
| Poison | Control / Tank |
| Ghost | Combo / Control |
| Bug | Control / Burst |
| Normal | Flexible |
| Flying | Combo / Burst |
| Dragon | Burst / Tank |
| Fairy | Support / Control |
| Steel | Tank |

---

## Gen 1 Role Assignments

### Legend
`→` = evolution direction | Role in **bold** is recommended change from current

| # | Name | Types | Role | Rationale |
|---|------|-------|------|-----------|
| 1 | Bulbasaur | Grass/Poison | **burst** | Aggressive vine whip striker, physical melee focus |
| 2 | Ivysaur | Grass/Poison | **control** | Sleep Powder, Leech Seed — crowd-control anchor |
| 3 | Venusaur | Grass/Poison | **tank** | Bulky wall; synthesis healing; petal absorb shield |
| 4 | Charmander | Fire | **burst** | Aggressive fire claw; ember applies burn → chase triggers |
| 5 | Charmeleon | Fire | **combo** | Slash combos that build heat stacks; mid-line fighter |
| 6 | Charizard | Fire/Flying | **burst** | Flamethrower + aerial dive; peak damage dealer |
| 7 | Squirtle | Water | **control** | Bubble slow; Water Gun applies wet → combos chain off |
| 8 | Wartortle | Water | **support** | Rapid Spin cleanses; heals teammates; tanky presence |
| 9 | Blastoise | Water | **tank** | Hydro Cannon shield wall; damage reduction passive |
| 10 | Caterpie | Bug | control | String Shot trap; low threat, control filler |
| 11 | Metapod | Bug | **tank** | Harden stacks; pure damage-absorb cocoon |
| 12 | Butterfree | Bug/Flying | **support** | Sleep Powder + Heal abilities; team debuff cleanser |
| 13 | Weedle | Bug/Poison | control | Poison Sting applies poison for combo setup |
| 14 | Kakuna | Bug/Poison | **tank** | Harden; cocooned tanker like Metapod |
| 15 | Beedrill | Bug/Poison | **burst** | Twin Needle physical burst; fastest bug attacker |
| 16 | Pidgey | Normal/Flying | control | Gust applies confused/flinch |
| 17 | Pidgeotto | Normal/Flying | **combo** | Wing Attack chains; mid-speed multi-hit |
| 18 | Pidgeot | Normal/Flying | **burst** | Sky Attack peak striker; fastest flyer |
| 19 | Rattata | Normal | control | Bite applies flinch; quick disruption |
| 20 | Raticate | Normal | **burst** | Hyper Fang high-power burst; Super Fang finisher |
| 21 | Spearow | Normal/Flying | control | Peck flinch; early disruption |
| 22 | Fearow | Normal/Flying | **burst** | Drill Peck aerial burst; high crit chance |
| 23 | Ekans | Poison | control | Wrap trap + Poison — control chain setup |
| 24 | Arbok | Poison | **control** | Glare paralyze; Coil self-buff then lock enemy down |
| 25 | Pikachu | Electric | combo | Thundershock chains; Nuzzle → Volt Tackle combo ✓ |
| 26 | Raichu | Electric | **burst** | Thunder finisher; peak electric damage ✓ |
| 27 | Sandshrew | Ground | control | Sand Attack blinds; defensive disruption |
| 28 | Sandslash | Ground | **burst** | Slash fury; high crit ground physical attacker |
| 29 | Nidoran-F | Poison | control | Poison Point setup; passive control |
| 30 | Nidorina | Poison | **support** | Bite threatens but cares for the line; team buffer |
| 31 | Nidoqueen | Poison/Ground | **tank** | Earth Power wall; Superpower anchor ✓ |
| 32 | Nidoran-M | Poison | control | Horn Attack poke; early control |
| 33 | Nidorino | Poison | **combo** | Horn Drill charge builds into Nidoking burst |
| 34 | Nidoking | Poison/Ground | burst | Earthquake burst finisher ✓ |
| 35 | Clefairy | Fairy | **control** | Sing sleep lock; Metronome wildcard; Minimize evasion — mischievous chaos, not yet a healer |
| 36 | Clefable | Fairy | support | Moonblast + Healing + Wish; the transformation payoff — control graduates into full support |
| 37 | Vulpix | Fire | control | Will-O-Wisp burn; Confuse Ray setup |
| 38 | Ninetales | Fire | **combo** | Nasty Plot → Fire Spin trap → Flamethrower combo chain |
| 39 | Jigglypuff | Normal/Fairy | **control** | Sing sleep lock; Disable control ✓→ better fit |
| 40 | Wigglytuff | Normal/Fairy | support | Hyper Voice + Heal Bell team cleanser ✓ |
| 41 | Zubat | Poison/Flying | control | Supersonic confuse; Leech Life drain setup |
| 42 | Golbat | Poison/Flying | **tank** | Leech Life sustain; Haze clears enemy buffs |
| 43 | Oddish | Grass/Poison | control | Absorb + Sleep Powder; control setup ✓ |
| 44 | Gloom | Grass/Poison | **support** | Aromatherapy cleanser; Moonlight self-heal |
| 45 | Vileplume | Grass/Poison | **control** | Stun Spore + Petal Dance spin-lock; heavy controller |
| 46 | Paras | Bug/Grass | control | Spore sleep; Leech Life chip |
| 47 | Parasect | Bug/Grass | **support** | Spore + Synthesis; healing spore support |
| 48 | Venonat | Bug/Poison | control | Sleep Powder setup |
| 49 | Venomoth | Bug/Poison | **control** | Psybeam confuse + Toxic; debuff stack controller |
| 50 | Diglett | Ground | control | Sand Attack blind; quick disruption |
| 51 | Dugtrio | Ground | **burst** | Earthquake fast burst; Arena Trap lock-in |
| 52 | Meowth | Normal | control | Pay Day chip; Growl/Screech debuff |
| 53 | Persian | Normal | **combo** | Slash crit chains; Technician multi-hit combos |
| 54 | Psyduck | Water | control | Confusion psychic control; Disable lock |
| 55 | Golduck | Water | **burst** | Hydro Pump + Psychic burst; swift attacker ✓ |
| 56 | Mankey | Fighting | **burst** | Karate Chop fury; pure physical aggression |
| 57 | Primeape | Fighting | **combo** | Rage stacks → Thrash chain; berserk combos |
| 58 | Growlithe | Fire | control | Roar displacement; Bite flinch |
| 59 | Arcanine | Fire | **burst** | Extreme Speed + Fire Blast; fastest fire burst ✓ |
| 60 | Poliwag | Water | control | Bubble slow; setup into Poliwhirl |
| 61 | Poliwhirl | Water | **combo** | Belly Drum + Hypnosis → Waterfall chain |
| 62 | Poliwrath | Water/Fighting | tank | Submission + Bulk Up tanky fighter ✓ |
| 63 | Abra | Psychic | control | Teleport disruption; fragile control |
| 64 | Kadabra | Psychic | **control** | Psychic wave control; Kinesis accuracy drop |
| 65 | Alakazam | Psychic | combo | Future Sight + Psychic chain; glass cannon combo ✓ |
| 66 | Machop | Fighting | **burst** | Karate Chop physical burst |
| 67 | Machoke | Fighting | **burst** | Dynamic Punch burst; power builder |
| 68 | Machamp | Fighting | tank | Cross Chop + Bulk Up; brawler tank ✓ |
| 69 | Bellsprout | Grass/Poison | control | Vine Whip trap; Wrap holds |
| 70 | Weepinbell | Grass/Poison | **control** | Razor Leaf + Acid debuff layer |
| 71 | Victreebel | Grass/Poison | **burst** | Solar Beam burst + Leaf Blade; glass cannon ✓ |
| 72 | Tentacool | Water/Poison | control | Poison chain; Wrap hold |
| 73 | Tentacruel | Water/Poison | tank | Barrier shield + Acid Spray; toxic tank ✓ |
| 74 | Geodude | Rock/Ground | **burst** | Rock Throw burst; Rollout escalating |
| 75 | Graveler | Rock/Ground | **burst** | Rock Slide AOE burst; Explosion potential |
| 76 | Golem | Rock/Ground | tank | Earthquake defensive anchor ✓ |
| 77 | Ponyta | Fire | control | Ember burn setup; Tail Whip debuff |
| 78 | Rapidash | Fire | **burst** | Fire Spin + Stomp burst; fastest horse ✓ |
| 79 | Slowpoke | Water/Psychic | **support** | Amnesia self-buff + Heal; slow but sustains ✓ |
| 80 | Slowbro | Water/Psychic | tank | Surf + Amnesia; psychic-water bulky wall ✓ |
| 81 | Magnemite | Electric/Steel | control | Thunder Wave paralyze; Sonic Boom chip |
| 82 | Magneton | Electric/Steel | **burst** | Discharge burst; Tri-Attack status combo ✓ |
| 83 | Farfetch'd | Normal/Flying | **combo** | Swords Dance → Slash crit chain; unique leek combo |
| 84 | Doduo | Normal/Flying | control | Growl/Fury Attack chip |
| 85 | Dodrio | Normal/Flying | combo | Tri Attack status chain; three-head combo ✓ |
| 86 | Seel | Water | control | Aurora Beam slow; Headbutt flinch |
| 87 | Dewgong | Water/Ice | tank | Ice Shard + Rest sustain; icy wall ✓ |
| 88 | Grimer | Poison | control | Disable lock; Poison Gas spread |
| 89 | Muk | Poison | tank | Minimize evasion + Toxic; sludge barrier ✓ |
| 90 | Shellder | Water | control | Supersonic confuse; Clamp trap |
| 91 | Cloyster | Water/Ice | tank | Spike Cannon + Shell Smash; fortress tank ✓ |
| 92 | Gastly | Ghost/Poison | **control** | Lick paralyze; Hypnosis sleep setup |
| 93 | Haunter | Ghost/Poison | **combo** | Shadow Ball chains + Mean Look trap; mid combo |
| 94 | Gengar | Ghost/Poison | combo | Dream Eater + Hypnosis; sleep-combo specialist ✓ |
| 95 | Onix | Rock/Ground | **tank** | Iron Tail + Rock Slide; stone wall anchor |
| 96 | Drowzee | Psychic | control | Hypnosis sleep; Disable lock |
| 97 | Hypno | Psychic | **control** | Dream Eater off sleep; Swagger confuse |
| 98 | Krabby | Water | control | Crabhammer chip; Guillotine threat |
| 99 | Kingler | Water | **burst** | Crabhammer high-power burst; crit machine ✓ |
| 100 | Voltorb | Electric | control | Thunder Wave paralyze; Screech defense drop |
| 101 | Electrode | Electric | **burst** | Thunder + Explosion burst gamble; fast attacker |
| 102 | Exeggcute | Grass/Psychic | control | Sleep Powder + Barrage chip |
| 103 | Exeggutor | Grass/Psychic | **burst** | Psychic + Solar Beam burst; big-brained nuker ✓ |
| 104 | Cubone | Ground | **control** | Bone Club flinch; Growl/Leer intimidation; grief and defensiveness — hiding behind the skull |
| 105 | Marowak | Ground | **burst** | Bone Rush burst with Thick Club power; trauma resolved into power — the breakthrough arc |
| 106 | Hitmonlee | Fighting | **burst** | High Jump Kick burst; Jump Kick physical striker |
| 107 | Hitmonchan | Fighting | **combo** | Mach Punch → Fire/Ice/Thunder Punch triple-element chain |
| 108 | Lickitung | Normal | support | Lick paralyze + Heal; sustain support ✓ |
| 109 | Koffing | Poison | control | Smog blind; Smokescreen debuff |
| 110 | Weezing | Poison | tank | Pain Split sustain + Toxic; gascloud tank ✓ |
| 111 | Rhyhorn | Ground/Rock | **burst** | Stomp + Horn Attack aggressive |
| 112 | Rhydon | Ground/Rock | tank | Earthquake + Hammer Arm; bulky bruiser ✓ |
| 113 | Chansey | Normal | **support** | Softboiled heal + Egg Bomb; pure support healer |
| 114 | Tangela | Grass | control | Bind trap + Absorb drain; control vine |
| 115 | Kangaskhan | Normal | tank | Double Edge + Fake Out; parental wall ✓ |
| 116 | Horsea | Water | control | Bubble slow; Smokescreen blind |
| 117 | Seadra | Water | **combo** | Twister → Dragon Rage combo escalation |
| 118 | Goldeen | Water | control | Horn Attack poke; Supersonic confuse |
| 119 | Seaking | Water | **burst** | Megahorn burst; Waterfall power striker |
| 120 | Staryu | Water | control | Water Gun chip; Minimize evasion |
| 121 | Starmie | Water/Psychic | combo | Rapid Spin + Psychic + Surf combo rotation ✓ |
| 122 | Mr. Mime | Psychic/Fairy | **support** | Barrier shield + Healing support; wall builder |
| 123 | Scyther | Bug/Flying | **burst** | Slash fury + Wing Attack; fast physical burst |
| 124 | Jynx | Ice/Psychic | **control** | Lovely Kiss sleep + Blizzard freeze lock |
| 125 | Electabuzz | Electric | burst | Thunderbolt + Thunder Punch burst ✓ |
| 126 | Magmar | Fire | burst | Flamethrower + Fire Punch burst ✓ |
| 127 | Pinsir | Bug | burst | Guillotine + Vicegrip burst ✓ |
| 128 | Tauros | Normal | **burst** | Body Slam + Giga Impact; rampaging bull striker |
| 129 | Magikarp | Water | control | Splash (fakeout)/Tackle chip; pre-evolution |
| 130 | Gyarados | Water/Flying | **burst** | Waterfall + Dragon Rage burst; rage stack Chase trigger — rewards the patience of evolving Magikarp |
| 131 | Lapras | Water/Ice | tank | Ice Beam + Surf sustain; gentle giant wall ✓ |
| 132 | Ditto | Normal | **combo** | Transform mirrors enemy combo; copycat chain |
| 133 | Eevee | Normal | **combo** | Adaptability; Quick Attack chains — evolution potential |
| 134 | Vaporeon | Water | support | Aqua Ring heal + Surf; water support ✓ |
| 135 | Jolteon | Electric | combo | Pin Missile + Thunderbolt chain ✓ |
| 136 | Flareon | Fire | **burst** | Flare Blitz physical burst; fire attacker (was tank — wrong) |
| 137 | Porygon | Normal | **combo** | Tri Attack status cycle; digital combo chain |
| 138 | Omanyte | Rock/Water | control | Water Gun chip; Withdraw defense |
| 139 | Omastar | Rock/Water | tank | Hydro Pump + Shell Smash threat; fortress tank ✓ |
| 140 | Kabuto | Rock/Water | control | Scratch poke; Harden defense |
| 141 | Kabutops | Rock/Water | **burst** | Slash + Aqua Jet; fossil blade striker ✓ |
| 142 | Aerodactyl | Rock/Flying | combo | Sky Attack + Ancient Power chain ✓ |
| 143 | Snorlax | Normal | tank | Rest + Body Slam; immovable wall ✓ |
| 144 | Articuno | Ice/Flying | **support** | Mist + Sheer Cold + Heal Wind; legendary healer |
| 145 | Zapdos | Electric/Flying | burst | Thunderstorm + Thunder burst ✓ |
| 146 | Moltres | Fire/Flying | burst | Fire Spin + Sky Attack burst ✓ |
| 147 | Dratini | Dragon | control | Dragon Rage setup; building toward power |
| 148 | Dragonair | Dragon | **combo** | Dragon Dance buff → Agility chain; speed builder |
| 149 | Dragonite | Dragon/Flying | **burst** | Outrage + Hyper Beam apex burst (was tank) |
| 150 | Mewtwo | Psychic | burst | Psystrike + Aura Sphere apex burst ✓ |
| 151 | Mew | Psychic | support | Transform + all-type versatility; utility support ✓ |

---

## Evolution Line Summary

| Line | Stage 1 | Stage 2 | Stage 3 | Pattern |
|------|---------|---------|---------|---------|
| Bulbasaur | burst | control | tank | Aggressor → Controller → Wall |
| Charmander | burst | combo | burst | Striker → Chain-builder → Apex Striker |
| Squirtle | control | support | tank | Disruptor → Healer → Wall |
| Caterpie | control | tank | support | Setup → Endure → Heal |
| Weedle | control | tank | burst | Setup → Endure → Strike |
| Pidgey | control | combo | burst | Disruptor → Chain → Apex |
| Nidoran-F | control | support | tank | Setup → Buffer → Wall |
| Nidoran-M | control | combo | burst | Setup → Builder → Apex |
| Gastly | control | combo | combo | Setup → Chain → Dream-chain |
| Dratini | control | combo | burst | Setup → Speed-builder → Apex |
| Abra | control | control | combo | Fragile control → Combo burst |
| Poliwag | control | combo | tank | Setup → Chain → Fighter-wall |

---

## Move Slot Templates Per Role

### Burst
- **Standard**: Physical/special attack that applies a minor status (burn, poison, flinch)
- **Chase**: Fires automatically when the status from Standard lands (the "follow-up strike")
- **Combo**: A charged finisher with higher power, long cooldown
- **Passive**: +crit chance or +damage when HP > 70%

### Combo
- **Standard**: Multi-hit or quick attack that builds a "chain counter"
- **Chase**: Fires when chain counter ≥ 2; resets counter
- **Combo**: Consumes chain counter for massive burst
- **Passive**: Each consecutive hit to same target boosts chain counter

### Tank
- **Standard**: Attack that heals self for 25% of damage dealt
- **Chase**: Fires when self HP drops below 50%; applies a Shield (absorbs next hit)
- **Combo**: AOE attack that taunts enemies to target this Pokemon for 1 round
- **Passive**: Damage reduction when HP < 40%

### Support
- **Standard**: Attack that deals damage AND removes 1 debuff from a friendly
- **Chase**: Fires when a friendly receives a negative status; heals that ally
- **Combo**: AOE cleanse + small heal to all friendlies; long cooldown
- **Passive**: Friendly AOE status resist aura

### Control
- **Standard**: Attack that applies a CC (sleep/confuse/paralyze/trap)
- **Chase**: Fires when target is CC'd; deals bonus damage or extends CC duration
- **Combo**: Multi-target CC wave; long cooldown
- **Passive**: CC duration +1 round on all inflictions

---

## Next Steps

1. **Review this table** — override any role that doesn't feel right for your vision
2. **Build the generator script** — uses this table + type rules to filter moves.json candidates
3. **Claude API fills gaps** — for any evolution line you don't have time to hand-pick
4. **Seed command** — outputs a Django management command to load all SpeciesMovePool entries
