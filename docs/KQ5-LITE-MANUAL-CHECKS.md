# KQ5 Lite — what automation cannot drive (v20 bits, 2026-08-24)

✅ **CHECKLIST COMPLETE 2026-08-24.** 6 of 7 play-verified by the USER; LH2c ruled not reachable
in real play (see its row). One residual defect declared red from LS1-edge (the mid-cliff
double-dispatch, `tools/run_tests.py` KNOWN_RED).

The scripted suite (`tools/probes/kq5_lite_scripted.py`) drives all 21 INVENTORY-OFFER sites:
14/16 rows PASS on v20 and the two non-passes (rm006 lamb, rm046 hermit) are cutscene-staging
limits of the RIG, both play-verified by hand on 2026-08-24. What remains is the 9 sites a click
transport cannot reach: POSITIONAL guards (a `doit` watching where Graham stands) and bare-click
sites with no inventory item to arm.

⛔ THE OLD `KQ5-LITE-TESTPLAN.md` BIT NUMBERS ARE STALE. The one-bit-per-action merge
(2026-08-24) renumbered g404: the three boat bits are ONE bit now, and LH2b2 no longer exists.
This file's bits are read from the v20 emission (`tools/probes/_sites.py`).

Setup, once: `vmvars g 402 1` (Lite) · re-arm all sites: `vmvars g 403 0` + `vmvars g 404 0`.
Expected everywhere: refusal on the FIRST trigger, "You have been warned!" + the stock outcome
on the SECOND. A warning and a refusal on the SAME trigger is the stacked-bit bug come back.

## The seven manual rows (9 sites)

| # | bit | where | do (twice) | ⚠️ |
|---|-----|-------|------------|----|
| ✅ LD1 (USER 2026-08-24) | 403 $8000 | rm18, Brass Bottle (6) + Gold Coin (11) left on the floor | walk the exit strip | leaves without them on the 2nd |
| ⚠️ LS1-edge (USER 2026-08-24: works, but see the declared red — mid-cliff sled click double-fires: refuse+warn from one click, then noop; stock silently refuses there) | 404 $0001 | rm32, missing any of Pie/Harp/Beeswax/Hammer/Lamb | **walk east** (the click half already passed in the suite) | ⭐ the bit is SHARED with the sled click: a refusal taken on the click must make the WALK warn, not re-refuse. ONE-WAY, save first |
| ✅ LR2 (USER 2026-08-24) | 404 $0002 | rm40, missing Crystal (21) or Lamb (19) in hand | walk the top strip (~148,144) | ONE-WAY, save first |
| 🚫 LH2c — USER RULING 2026-08-24: the refusal state is NOT REACHABLE in real play ("I don't think is real"). Source agrees: the flag-105 scene chains straight into rm044's iron-bar grant (`rm046.sc:384` newRoom 44 → `rm044.sc:616` get 30), and the fishhook (31) comes from the island loop itself — by the time 105 is set the demand holds. The guard stays installed: an unreachable refusal costs nothing, and removal would be a hand-analysis, not a derivation. | 404 $0004 | coast rm44/45/46 with flag 105 SET, items missing | click the boat / the sail | ONE bit now (was 3); check ONE refusal then through |
| ✅ LH0 (USER 2026-08-24) | 404 $0008 | harpy island rm49 first visit, missing Shell (23) or Fishhook (31) | click the boat / walk the sea edge | island is ONE SAFE VISIT |
| ✅ LM2 (USER 2026-08-24) | 404 $0010 | rm54 without the Cat Fish (37) | click the grate | 2nd goes in without the fish |
| ✅ LC1 (USER 2026-08-24) | 404 $0020 | inn rm85 north zone, without Hammer (22) + a banked throwable | walk the zone | ONE-WAY (kidnap), save first |

## Silent sites (LQ) and never-guarded rows (LZ) — LOW value under Lite
The silent kinds (arm-event, edge closes, register holds) carry NO lite arm by construction
(`stock_or` — lite behaves as full there, user ruling 2026-08-06), and their conditions were
play-verified in the 2026-08-18 great playtest. Re-checking them under Lite verifies the
compiler, not the design. If time is short, skip; if being thorough, LQ1 (castle cat spawn) and
LZ (gypsy needle→amulet, girl heart→harp stay unguarded) are the two worth a glance.
