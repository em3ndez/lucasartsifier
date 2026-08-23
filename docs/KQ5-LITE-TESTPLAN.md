# KQ5 patched-game test plan — **LITE** guard mode

Companion to `KQ5-TESTPLAN.md`, which covers **Full**. Same game, same obstacles; this one asks
only *"does each guard let me through on the second try?"*

Game: `~/sierra/patched/kq5` · Console: **Ctrl+Alt+D**, type lines, `exit`.
`C:` = console lines. **After `exit`, move the mouse OFF the icon bar** (the bar pauses the room).
`put N R` **no-ops unless you hold N** — always `get N` first. **Save before every one-way**
(kidnap, sled, roc, sail). Don't teleport straight into rooms 33, 35, 36, 42, 55–67, 86 — they
switch on where you came from; walk in from a neighbor.

## What Lite means

Set it in-game: control panel → **GUARDS** → **Lite**. Each guard **SITE refuses once**; from then
on it prints **"You have been warned!"** and runs the original behavior. So every row below is the
same two-step:

> **first** encounter at that site → the *normal Full refusal*
> **second** encounter → **"You have been warned!"**, then the stock action goes through

## ⛔⛔ Two ways a CORRECT build looks broken

1. **The warn bit is per SITE, and a refusal you already took in Full sets it.** Walk up to an
   obstacle that already refused you once, switch to Lite, and there is **no fresh refusal** — you
   go straight to the warning and through. That is correct. **Test each row at a site you have not
   yet been refused at**, or clear the bits first (below).
2. **At the 8 silent sites (§Q) Lite behaves exactly like Full.** Those guards have no refusal
   message to warn with, so "Lite changed nothing here" is the right answer, not a bug.

## Console shortcuts (derived from the emitted patch)

Mode lives in `global402`; the warn bits in `global403` (16 sites) and `global404` (9 sites).

| do | line |
|---|---|
| set **Lite** | `vmvars g 402 1` |
| set **Full** / **Off** | `vmvars g 402 0` · `vmvars g 402 2` |
| read the mode | `vmvars g 402` |
| **clear every warn bit** (re-arm all 25 sites for a fresh refusal) | `vmvars g 403 0` then `vmvars g 404 0` |
| read the warn words | `vmvars g 403` · `vmvars g 404` |

⭐ Clearing the two warn words is the fastest way to re-test a row you have already spent.

## ⛔ Three of the numbers below are NOT rooms

The town interiors are **Regions layered into room 5**, not rooms of their own — room 5's `init`
switches on `global313` to pick which shop you are standing in. So `room 204` points the game at a
script whose export 0 is a `Rgn`, and it dies a few seconds later somewhere unrelated.

| to reach | do |
|---|---|
| **tailor** (203) | `vmvars g 313 1` then `room 5` |
| **toy shop** (204) | `vmvars g 313 2` then `room 5` |
| **shoe shop** (205) | `vmvars g 313 3` then `room 5` |
| **bakery** (206) | `room 206` — this one really is a room (`bakeShop of KQ5Room`) |

The bakery being a genuine room next door to three that are not is what makes the failure look
arbitrary. Same trap for the other region scripts these plans name by number: **200** (witch),
**202** (owl), **220** (boatRegion), **550** (castle), **551** (toad), **552** (spider).
`python3 tools/probes/_rooms.py <patch_project>/src` lists them from the decompiled source.

## Items (alphabetical — `send ego get N`)

| item | # | item | # | item | # |
|---|---|---|---|---|---|
| Amulet | 27 | Golden Needle | 3 | Pie | 2 |
| Bag of Peas | 24 | Hairpin | 36 | Pouch | 13 |
| Beeswax | 18 | Hammer | 22 | Rain Spell | 40 |
| Brass Bottle | 6 | Harp | 10 | Rope | 20 |
| Bunny Spell | 39 | Heart | 9 | Shell | 23 |
| Cat Fish | 37 | Honeycomb | 17 | Shoe | 8 |
| Cloak | 26 | Iron Bar | 30 | Sled | 29 |
| Coin (silver) | 4 | Key | 1 | Spinning Wheel | 15 |
| Crystal | 21 | Leg of Lamb | 19 | Staff | 7 |
| Elf Shoes | 33 | Locket | 25 | Stick | 16 |
| Emeralds | 14 | Marionette | 12 | Tambourine | 34 |
| Fish | 5 | Moldy Cheese | 32 | Tiger Spell | 41 |
| Fishhook | 31 | Mongoose Spell | 38 | Wand (Crispin's) | 28 |
| Gold Coin | 11 | Mordack's Wand | 35 | | |

**Flags** (read `vmvars g N`; write `vmvars g N <value>`): 15 = cloak WORN (g129 & $8000) ·
16 = has eaten (g130 & $0001; `vmvars g 130 1` fakes it) · 54 = harpy island departed once ·
62 = cat took fish (g132 & $4000) · 63 = henchman pea'd (g132 & $8000) · 96 = hole-rescue state
(g135 & $0001) · 105 = hermit give committed

Legend: ✅ = verified by your play · ☐ = still needs your hands · ⚠️ = read the note first.
**Every row below is ☐ — none of Lite has been played.**

The **bit** column is that site's warn bit, so a row can be re-armed on its own if you would
rather not clear all 25 (`vmvars g 403 <old & ~bit>`).

## A — Town & market (7 sites) — Full-mode rows A1–A3
Refusal at all seven is **"Better not. You are going to need that."**

| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LA1a | 403 $0200 | toymaker (204) | pay **Golden Needle (3)** | warned, **the needle is spent** |
| ☐ | LA1b | 403 $1000 | toymaker (204) | pay **Heart (9)** | warned, the heart is spent |
| ☐ | LA1c | 403 $0010 | toymaker (204) | pay **Gold Coin (11)** | warned, the coin is spent |
| ☐ | LA2a | 403 $0008 | bakery (206) | pay **Gold Coin (11)** | warned, the coin is spent |
| ☐ | LA2b | 403 $0100 | bakery (206) | pay **Golden Needle (3)** | warned, the needle is spent |
| ☐ | LA2c | 403 $0400 | bakery (206) | pay **Heart (9)** | warned, the heart is spent |
| ☐ | LA3 | 403 $0800 | tailor (203) | pay **Heart (9)** | warned, the heart is spent |

⭐ These seven are the cleanest rows to test: three shops, three separate bits each, all reachable
in the first ten minutes, and nothing one-way. **LA1a–LA1c are three INDEPENDENT sites** — being
warned at the needle must NOT let the coin through without its own refusal first. That is the
per-site bit's whole point, and the market is the only place it can be checked cheaply.

## A6/A7b — the EAT retraction (2 sites, script 0)
Refusal is **"Just kidding! You hold on to it because you still need it."**

| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LA6 | 403 $0001 | anywhere | **EAT the Pie (2)** | warned, then **the pie is actually eaten/gone** |
| ☐ | LA7b | 403 $0002 | anywhere | **EAT the Lamb (19)** past the first bite | warned, then the half leg is **actually consumed** |

⚠️ Both of these DESTROY an item that later rows need (the pie feeds the yeti, the lamb feeds the
eagle). Save first, or do them last.

## B — Cat & dog scenes (3 sites)

⛔ **Corrected 2026-08-22.** LB1 and LB2 had their items the wrong way round here: the emitted
source puts the **Lamb** on `$0040` and the **Fish** on `$2000`, not the reverse. Derived from
`build/<patch>/patch_project/src/rm006.sc` via `tools/probes/_sites.py`, which is where this table
should have come from in the first place.
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LB1 | 403 $0040 | rm6, during the chase | offer the **Leg of Lamb (19)** | warned, the lamb goes to the cat |
| ☐ | LB2 | 403 $2000 | rm6 | offer the **Fish (5)** | warned, **the fish goes to the cat** (and the bear at rm11 then has none); this bit is shared with `catStrip` |
| ☐ | LB6 | 403 $0020 | rm12 dog | offer the **Lamb (19)** | warned, the lamb is spent |

## C — Kidnap (1 site)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LC1 | 404 $0100 | inn rm85 north zone, **without Hammer (22)** + a banked throwable | walk into the zone | warned, then **kidnapped anyway** — ⚠️ ONE-WAY, save first. Guard is `has 22 ∧ (Fish 5 / Shoe 8 / Stick 16 banked in rm6)` |

## D — Desert temple (1 site)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LD1 | 403 $8000 | rm18, **Brass Bottle (6) and Gold Coin (11) left on the floor** | walk the exit strip | warned, then **you leave without them** |

## E / S — Mountains and the sled commit (2 sites)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LE2 | 403 $0004 | rm30 | use the **Rope (20)** on the branch | warned, the rope is spent |
| ☐ | LS1 | 404 $0001 | rm32, missing any of **Pie (2) / Harp (10) / Beeswax (18) / Hammer (22) / Lamb (19)** | use the **Sled (29)** on the slope — *or* walk east | warned, then **the ride happens underequipped** — ⚠️ ONE-WAY into rm33, save first. **One bit covers both the click and the walked edge**: refuse on the click, then the *walk* should already be warned |

⭐ LS1 is the best single row for the "one bit, many clauses" property — rm32 has 3 clauses on
one bit, so the refusal you take on the sled click must also warn (not re-refuse) at the edge.

## F / R — Above the sled (2 sites)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LF1 | 403 $0080 | rm34 eagle | offer the **Pie (2)** | warned, the pie goes to the eagle |
| ☐ | LR2 | 404 $0002 | rm40, missing the **Crystal (21)** *or* with the **Lamb (19)** still in hand | walk the top strip (~148,144 — cliff room, walk carefully) | warned, then **the roc carries you off underequipped** — ⚠️ ONE-WAY. Guard is `has 21 ∧ owner(19)==34` |

## H — Coast, hermit, harpy island (6 sites)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LH0 | 404 $0040 | harpy island rm49, first visit, missing **Shell (23)** or **Fishhook (31)** | click the boat / walk the sea edge | warned, then **you sail off** — ⚠️ the island is ONE SAFE VISIT; departing writes flag 54 and the return patrol can kill you |
| ☐ | LH2b | 403 $4000 | rm46 hermit, missing **Iron Bar (30)** or **Fishhook (31)** | click the **Shell (23)** on the hermit | warned, then **the give chain starts underequipped** |
| ☐ | LH2b2 | 404 $0020 | rm46, same state | the second hermit clause | warned; ⚠️ a **separate bit** from LH2b — being warned on one must not silence the other |
| ☐ | LH2c1 | 404 $0004 | coast rm44/45/46, **flag 105 SET**, items missing | board / click the boat | warned, then it sails |
| ☐ | LH2c2 | 404 $0008 | 〃 second boat site | 〃 | warned, then it sails |
| ☐ | LH2c3 | 404 $0010 | 〃 third boat site | 〃 | warned, then it sails |

⚠️ LH2c1–3 are only reachable with **flag 105 set** (`vmvars g` per the flag list) — with 105 clear
the guard passes and there is nothing to warn about. See KQ5-TESTPLAN H2c/H2d.

## M — Mordack's island (1 site)
| ✓ | # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|---|
| ☐ | LM2 | 404 $0080 | rm54, **without the Cat Fish (37)** | click the grate | warned, then **into the castle without the fish** — ⚠️ this is the state the cat guard (§Q) exists to survive |

## Q — Silent sites: **Lite must behave exactly like Full** (8 clauses, 5 files)
No refusal message ⇒ nothing to warn with ⇒ lite = full, by design (`GUARD-MODES.md`).
**Off (mode 2) still bypasses these.** A "Lite let me through here" result on any Q row is a BUG.

| ✓ | # | Where | Check |
|---|---|---|---|
| ☐ | LQ1 | castle (550) ×3 | the **cat** still does not spawn until `flag63 ∧ own(24) ∧ (flag62 ∨ own(37))`; the henchman capture still does not arm early (Full-mode M4 / M6c) |
| ☐ | LQ2 | rm6 ×2 | the chase **re-arm window** still behaves (B4/B5): lose → re-enter re-arms; win → never replays |
| ☐ | LQ3 | rm42 nest | the eggs still do not crack until the **Locket (25)** is taken (R4) |
| ☐ | LQ4 | rm46 hermit | the un-walled hermit scenes still play stock (H4) |
| ☐ | LQ5 | boatRegion (220) | the remaining silent boat clause still gates as in Full (H2c) |

## Z — Must-stay-stock under Lite
Gypsy rm13 (pay the **Needle (3)** → Amulet 27) and girl rm9 (give the **Heart (9)** → Harp 10) are
**never guarded** in any mode — no refusal, no warning, in Full or Lite. Snake at rm2 still wants
the **Tambourine (34)**; witch forest still wants the worn **Amulet (27)**.

## What to report back
For any row that misbehaves: the room, **whether it was your first refusal at that exact site**
(rule 1 above is the usual explanation), and what `vmvars g 402`, `vmvars g 403` and `vmvars g 404`
read at the time. Those three numbers say which sites think they have already warned you.
