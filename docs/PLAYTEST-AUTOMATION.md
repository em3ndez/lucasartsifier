# Automating the play tests

Every end-to-end result this project claims came from a person at the keyboard. `docs/TESTING.md`
says so plainly, and names the gap: *"The suite checks the emitted source; it cannot see what the
patched game draws."* The existing harness (`tools/drive_scummvm.py`) narrowed it a little — it can
click a menu and photograph the result — but its only oracle is a picture, so it has never checked
a guard.

This document is about the half of that gap that needs no pictures at all.

## The enabling fact

**ScummVM's SCI debugger console is drawn in the game window, but everything it prints is mirrored
to ScummVM's stdout.** Verified 2026-08-22 against the stock Debian `scummvm 2.8.0` binary — no
rebuild, no patched engine.

That closes a text loop:

```
XTEST keystrokes  ->  console command  ->  plain text on stdout  ->  a regex
```

Both ends are machine-readable. No OCR, no screenshot diffing, no pixel thresholds.

The console is a full read/write window onto the live VM:

| want | console |
|---|---|
| read/write any global (mode, warn bits, flags) | `vv g 402` · `vv g 403 0` |
| call any method, write any property, get the return | `send ?toyMaker handleEvent 1a:0c` |
| dump every property of an object | `vo ?toyMaker` |
| resolve an object **by the name in our decompiled source** | `?Heart`, `?toyShop` |
| teleport | `send <game> newRoom 204` — **not** `room 204`, see below |
| every line the game PRINTS, verbatim | `bpk StrCpy log` |
| persistence questions | `save_game` / `restore_game` / `restart_game` |

The last two are worth dwelling on.

**`?Name` costs us nothing to use and is the reason this is cheap.** We decompile these games; we
already know the guard sites by object name and the items by instance name. `?toyMaker` and
`?Heart` resolve straight to the objects our own specs talk about.

**⛔ `room N` is not a room change.** The console's `room` command writes global 13 and nothing
else: no script load, no `init:`, no `prevRoom`. The number changes and the game does not. Use the
game's own room change — KQ5 spells it `(global2 newRoom: N)`, so a probe sends
`send <addr of global2> newRoom 204`. That distinction is also what makes it possible to leave the
intro without sitting through it.

**`bpk StrCpy log` prints the dialogue.** Sierra's print path copies its literal through `StrCpy`,
and ScummVM's kernel logger decodes reference arguments as text
(`scriptdebug.cpp:logParameters`). So a probe does not have to settle for "the warned bit moved" —
it can assert that the game said *"Better not. You are going to need that."* and then, on the
second try, *"You have been warned!"*. That is the sentence `KQ5-LITE-TESTPLAN.md` actually
specifies, checked as text.

## Four tiers of test, by how much of the game they need

### Tier 1 — pure state. No interaction at all.

Set globals, read globals. The whole mode/warn storage story is Tier 1:

- mode survives save/restore (`save_game s; vv g 402 2; restore_game s; vv g 402`)
- Restart resets to Full
- a warn bit set in Full is honored by Lite (the per-SITE rule the user ruled *required*)
- the 25 KQ5 bits are 25 distinct bits, and no two sites share one

`tools/kq6_mode_persist_probe.py` already asks the first two — with menu clicks and four
screenshots for a human to compare. The console asks them in four lines and answers with a number.

### Tier 2 — synthesized interaction. The bulk of the work.

An inventory offer is not magic: `toyMaker:handleEvent` wants an event that is type 16384, carries
message 4, and lands inside the object's `nsRect` (`proc255_5` is a bounding-box hit test). All
three are writable, so a click is reproducible:

```
send <iconbar> curInvIcon ?Heart     # what the player is holding
send ?Event new                      # -> the new event's address
send <ev> type 16384 ; message 4 ; x <cx> ; y <cy>
send ?toyMaker handleEvent <ev>
```

This is the shape of most of the guard estate: every *give / use item on NPC* guard. In KQ5's lite
plan that is the seven market rows (A), both cat/dog rows (B), the eagle (F1), the hermit (H2b),
and Mordack's grate (M2) — and the same shape covers the EAT retractions (A6/A7b), which are
`doVerb` on an inventory item rather than on an NPC.

### Tier 3 — positional guards. Move the ego, run a cycle.

The edge and wall guards test where the ego is standing: `onControl`, or a coordinate compare in
`doit`. Both are reachable — write `ego x:`/`y:`, `go` for a beat, reopen the console, read what
changed. That is LD1 (the temple exit strip), LS1 (the sled edge), LR2 (the roc), LC1 (the kidnap
zone).

⚠️ These are the rows where a probe most needs to be honest about what it drove. A teleported ego
is not a walked ego, and some of these rooms switch on `prevRoom`.

### Tier 4 — pixels. Still needs `drive_scummvm.py`, or a person.

- Does the picker plate read **Lite**? Does the press animation glitch? (This is what
  `drive_scummvm.py` was built for, and it did catch a real artifact.)
- Anything whose claim is about the rendered result.
- Anything whose claim is about how it *feels* — pacing, whether a refusal reads as confusing.

## What this changes about the test plans

`docs/KQ5-LITE-TESTPLAN.md` is 32 rows, every one marked ☐ *"still needs your hands"*. Most of
those rows are a four-line probe. The prize is not just doing them once — it is that a
**table-driven suite makes them a regression test**: rebuild the patch, run the suite, and every
guard site is re-checked without asking anyone to play. That is the loop `TESTING.md` says is open.

The row already reads like a data structure:

| # | bit | Where | Do (twice) | Expect on the 2nd |
|---|---|---|---|---|
| LA1b | `403 $1000` | toymaker (204) | pay **Heart (9)** | warned, the heart is spent |

which is `{"room": 204, "target": "?toyMaker", "item": "Heart", "bit": 0x1000}` plus the two
sentences it should print.

## Five things that cost a run each, written down so they cost nobody else one

These are not incidental — every one of them makes a probe report a *wrong answer* rather than an
error, which is the failure mode worth paying to avoid.

1. **The Ctrl+Alt+D hotkey does nothing during the intro.** Over the Sierra logo, a cutscene or a
   modal game dialog it is simply dropped. Click all the way into the game first, then open once.
   `open()` writes a screenshot when it gives up, which is the fastest way to see what the game was
   actually sitting on.
2. **Ctrl+Alt+D is a TOGGLE.** Retrying it when the confirmation does not come back CLOSES the
   console that just opened. Probe several times per press; only press again when it is genuinely
   shut.
3. **`room N` is not a room change** — see above. And `newRoom` out of the opening scene into a
   town interior *killed the game outright*, so a probe that needs a specific room is better off
   restoring a save than teleporting.
4. **A freshly-loaded room's Props have no bounding box.** Straight after a room change every
   `nsRect` reads `0,0,0,0`, an event aimed at (0,0) fails the hit test, the handler returns
   silently — and the probe reports "no refusal" for a guard it never reached. Let the room run
   until the box is real. (The ego always has one, which is why the script-0 guards are the easiest
   first targets.)
5. **`?Name` goes ambiguous as soon as the game makes a second one** — see the section below. This
   one cost two runs, because the symptom (a `send` that returns nothing) reads as a hung game and
   invites an elaborate theory about re-entrancy. It was a name lookup. A screenshot on the
   failure path settled it in one run; guessing had not settled it in two.

## Housekeeping that is not optional

`timeout 300 python driver.py` sends SIGTERM to the *driver*, and without a handler Python dies
before any `finally` — orphaning ScummVM. Five of those accumulated across a debugging session and
pinned the machine. `sci_console.py` therefore puts the game in its own process group, tears it
down from `atexit` **and** from SIGTERM/SIGINT/SIGHUP, and reaps anything an earlier run leaked
(matched on `sci_console` in the command line, so a player's own ScummVM is never touched).

⛔ And `pkill -f <something>` matches the shell that is running it. Use `pkill -x scummvm`. This is
already written down in `drive_scummvm.py`; it was re-learned anyway.

## A name is only unambiguous until the game makes another one

`?Event` resolves fine on the first call and then stops: after one `Event new:` the name matches
the class *and* every live instance, and the console answers an ambiguous name with a candidate
list instead of an address. A probe that re-resolves `?Event` per interaction therefore works on
its first action and fails on its second — and the failure looks like the game hanging, not like a
name lookup. Resolve a class ONCE, keep the address, send to that.

This is worth stating as a general rule: `?Name` is a convenience for finding an address, not an
identity. Anything used more than once should be pinned to its `ssss:oooo` at the start of a run.

## What it does NOT become

**This is DRIVING, not PLAYING** — the distinction `guard-modes-play-verified` insists on. A
console-driven result is evidence about a *state*, which is exactly what the user has ruled console
writes to be. It is not evidence that a player walking in from the neighbouring room sees the same
thing, and a probe that teleports into a `prevRoom`-switching room is testing a state the game
cannot reach. No probe output should ever be written up as "play-tested".


## Where this stands today

Built on this branch:

- `tools/sci_console.py` — the driver. Launches a game, drives the console by keystroke, reads the
  answers off stdout, and exposes typed reads (`gint`, `gaddr`, `send`, `room`, `said`). Tears the
  game down from `atexit` and from a signal, and reaps instances an earlier run leaked.
- `tools/probes/_kq5.py` — booting KQ5 to a playable room, and `goto()` via the game's own
  `newRoom:`.
- `tools/probes/kq5_eat_pie.py` — LA6, the EAT-the-pie retraction, as a self-checking probe.
- `tools/probes/kq5_toymaker.py` — LA1a/b/c, the three independent toymaker sites. Reaches the
  shop but is blocked on the teleport question above.

Established by running it (KQ5, `~/sierra/patched/kq5` copied to a scratch dir, 2026-08-22):

- the console's answers reach stdout on the stock ScummVM 2.8.0 binary
- globals read and written (`vv g 402 1` etc.), object addresses resolved, `send` calls methods
- the game's own `newRoom:` moves rooms; `room N` does not
- ⭐ **LA6 passes end to end, driven with no hands.** Under Lite with the warn word cleared:

  | attempt | `global403 & $0001` | `ego has: 2` | meaning |
  |---|---|---|---|
  | 1 | set | still held | the guard REFUSED and marked itself warned |
  | 2 | set | **gone** | the second try went through and the pie was really eaten |

  That is exactly the two-step the lite plan specifies for that row, checked as numbers rather
  than as a screenshot — and the whole interaction (hold the pie, EAT it) was synthesized.

Not established:

- `bpk StrCpy log` capturing the refusal *text*. The mechanism is in ScummVM's source
  (`logParameters` decodes reference args) and the breakpoint registers, but no probe has yet read
  a game line out of it — so the probe grades on state and reports text as informational. Grading
  on a channel that has never produced output would have failed a guard that was behaving.
- anything about a room reached by teleport rather than by walking

⚠️ **Provenance.** Everything above is Claude DRIVING, and mostly driving *state*. No probe has
played a game. `guard-modes-play-verified` and the play-confirmed results in the test plans are the
user's own playing and stay that way.
