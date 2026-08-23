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
| teleport | `room 5` — but check the target is a ROOM first, see below |
| every line the game PRINTS, verbatim | `bpk StrCpy log` |
| persistence questions | `save_game` / `restore_game` / `restart_game` |

The last two are worth dwelling on.

**`?Name` costs us nothing to use and is the reason this is cheap.** We decompile these games; we
already know the guard sites by object name and the items by instance name. `?toyMaker` and
`?Heart` resolve straight to the objects our own specs talk about.

**⛔ Not every number in a test plan is a room.** `room N` itself is fine — it writes global 13,
and KQ5's `Game:doit` polls `(if (!= global13 global11) (self newRoom: global13))` every cycle, so
the game performs its own `newRoom:`. That is the classic Sierra debug teleport and it works.

What does not work is pointing it at something that is not a room. Several KQ5 town interiors are
**Regions layered into one room**:

```
room 5's init switches on global313 --  1 -> setRegions 203 (tailor)
                                        2 -> setRegions 204 (toy shop)
                                        3 -> setRegions 205 (shoe shop)
```

So `room 204` sets global 13 to a number with no room behind it; the game calls `newRoom: 204`,
gets `toyShop of Rgn` as that script's export 0, and starts sending Room messages to a Region. It
dies — silently, seconds later — which reads as "teleporting is flaky" rather than "that was never
a room". The bakery next door *is* a real room (`bakeShop of KQ5Room`, script 206) and `room 206`
is fine, which is what makes the failure look arbitrary.

⭐ **This is checkable statically, from our own decompiled source.** `tools/probes/_rooms.py` reads
what export 0 of each script is an instance of; anything that is a `Rgn` is not a teleport target.
For KQ5 that flags nine places the test plans name by number — 200, 202, 203, 204, 205, 220, 550,
551, 552 — before a run rather than by killing a game. Note KQ5 spells some regions as `class`
rather than `instance`; a pattern that only knows `instance` reports them as unknown, which is the
same as reporting them safe.

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
3. **Not every number in a test plan is a room.** `room N` works; pointing it at a Region does
   not, and the game dies seconds later somewhere else. Check the target statically first
   (`_rooms.py`). I got this backwards at first and wrote down "`room N` is not a room change",
   which is false — the game polls global 13 every cycle and does its own `newRoom:`.
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

## Disposal is sometimes inline and sometimes deferred, and a one-shot oracle cannot tell

Script 0's EAT does `(global0 put: 2 1)` right in the handler — the pie is gone the instant
`handleEvent` returns. The toymaker's handler only does `setScript: getSled`, and the payment is
taken in that script's `changeState` state 0 (`(global0 put: 9 204)`), several cycles later.

Sampling `ego has:` once after a fixed sleep passes for the first shape, and passes for the second
only when the script happened to get its cycle in. In one run, at one site, it read OK for the
needle and WRONG for the heart — same guard, same code path. That is the signature of a timing
oracle, not a broken guard, and it is exactly the kind of flake that would get "fixed" by editing
the thing under test.

Which shape a site has is readable from the emitted source (`put:` in the handler vs `setScript:`),
but a probe should not have to encode that per site: **poll**. `wait_spent()` resumes the game a
slice at a time until the item is gone or a budget expires.

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
- `room N` moves rooms (the game polls global 13 and calls `newRoom:` itself); what breaks it is
  a target that is a Region rather than a room, which `_rooms.py` now catches before a run
- ⭐ **LA6 passes end to end, driven with no hands.** Under Lite with the warn word cleared:

  | attempt | `global403 & $0001` | `ego has: 2` | meaning |
  |---|---|---|---|
  | 1 | set | still held | the guard REFUSED and marked itself warned |
  | 2 | set | **gone** | the second try went through and the pie was really eaten |

  That is exactly the two-step the lite plan specifies for that row, checked as numbers rather
  than as a screenshot — and the whole interaction (hold the pie, EAT it) was synthesized.

- ⭐ **LA1a passes, and the per-SITE independence with it.** In the toy shop (reached by
  `global313=2` + `room 5`), under Lite with the warn word cleared:

  | | `global403` | `ego has:` | |
  |---|---|---|---|
  | needle, try 1 | `$0200` set | needle held | refused |
  | needle, try 2 | `$0200` set | **needle gone** | went through |
  | *then* | `0x0200` | — | Heart and Gold_Coin still **unwarned** |
  | heart, try 1 | `$1000` set | heart held | **refused on its own account** |

  Being fully warned and spent at the needle did not buy anything at the heart. That is the
  property `KQ5-LITE-TESTPLAN` calls "the per-site bit's whole point, and the market is the only
  place it can be checked cheaply" — and it is now checked, by machine, in one run.

- ⭐ **The text oracle works.** A probe now reads the player-facing sentence back:

  ```
  attempt 1: bit=True has(9)=1 (want 1) -> OK
  said=['Better not. You are going to need that.', ...]
  ```

  which is verbatim the refusal `KQ5-LITE-TESTPLAN` specifies for that row. It returned `[]` for a
  long time for a reason worth keeping: **`cmd()` consumes the stream.** It reads ScummVM's stdout
  looking for its sentinel, so every `bpk StrCpy log` line was gone before `said()` could look.
  The channel had been working the whole time; the reader was eating it.

Not established:

- anything about a room reached by teleport rather than by walking
- ⚠️ **the harness is not yet reliable enough for a long unattended run.** Nine rows in one boot
  is roughly 30 minutes, and over that span a dropped keystroke eventually wedges it. The failure
  is always the same shape and now always diagnosable: the console screenshot showed `) versi` —
  the sentinel's last character *and* its Return lost, the line never submitted, the driver
  waiting for a reply that cannot come, and each retry typing into the leftover. `cmd()` and
  `is_open()` now send a bare Return first so a partial line is always flushed, but that fix has
  not yet carried a full nine-row run.

  The answer was not more retry tuning. See the next section.

## ⭐ ScummVM already has this, and it is off by default

Asked whether anyone had done this before, the answer is yes — **upstream, in the tree we already
vendor**:

* `--record-mode=record|playback|fast_playback` with `--record-file-name`. A session is recorded
  once and replayed **deterministically**, because the recording captures timing and RNG — which
  is precisely the class of problem that made console-driven interaction unreliable here.
* Periodic screenshots are hashed into the recording (`--screenshot-period`), so a replay carries
  its own oracle.
* `devtools/run_event_recorder_tests.py` is ScummVM's own runner: it replays every recording under
  `fast_playback`, asserts the exit code, and emits xUnit XML. `--list-records-json` enumerates
  them.

⛔ **`_eventrec=no` in `configure`** — that is why no distro binary has `--record-mode` and why
this was easy to miss. `tools/build_recorder_scummvm.sh` builds one (and carries patch 0002,
because at the current master the recorder does not compile without ImGui — an upstream break,
since ImGui is auto-disabled for an SCI-only build).

So the honest framing of everything below is: it is a hand-rolled approximation of a facility that
already exists. It found real things — the region/room trap, two errors in the lite plan, the
per-site independence result — but for **driving an interaction**, the recorder is the tool to
reach for first.

(For the record, ScummVM's engine testing is otherwise buildbot + screenshot-diff regression, and
the Director engine has its own corpus of test movies. It is not all manual.)

### Where the documentation is

There is no tutorial as such. What exists:

| source | what it gives |
|---|---|
| **`wiki.scummvm.org/index.php/Event_Recorder`** | the canonical page, linked from ScummVM's own docs. ⚠️ It sits behind Anubis anti-bot and would not fetch for me — read it in a browser. |
| `doc/docportal/advanced_topics/command_line.rst` (in-tree) | the authoritative option table, and the source of the wiki links. Also published at `docs.scummvm.org/en/latest/advanced_topics/command_line.html` |
| **`devtools/run_event_recorder_tests.py`** (in-tree) | the closest thing to a tutorial: its header comment is a working headless recipe — `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy SCUMMVM_BIN=./scummvm python3 devtools/run_event_recorder_tests.py --xunit-output=... --filter="*monkey*"` |
| `gui/EventRecorder.cpp`, `common/recorderfile.{h,cpp}` | the actual semantics, which is where the details below came from |
| GSoC 2012 blog (`jakimushka.blogspot.com`) and bug **#7247** | the design history: this began as a GSoC testing-framework project |

The modes: `record`, `playback`, `fast_playback`, `update`, `info`, `passthrough`. `info` prints a
recording's author/name/description. `update` replays and **re-writes the stored hashes**.

### The constraint that looked fatal, and the measurement that retired it

A recording stores the **MD5 of the game's own files**, and on playback a mismatch is not a
warning — it is fatal (`processGameDescription` → `error("playback:action=error …")`).
`fast_playback` is `kRecorderPlayback` plus a speed flag, so it is checked too. That reads like a
hard blocker: every patch build changes the game, so every recording would be single-use.

⭐ **It is not, and the reason is how we install patches.** They go in as **loose `*.SCR` patch
files** beside an untouched `RESOURCE.000/.001/.MAP`, and the detection MD5s cover the volumes.
So the hash is *identical across patch builds*. Measured, not assumed: one recording replayed
against two game dirs whose `0/12/18/203/204/206.SCR` all differ — the gate did not fire and
playback proceeded.

`tools/scummvm-patches/0003-*.patch` makes the gate optional anyway
(`--record_ignore_game_hash=true`), as insurance for a build that ever rewrites the volumes. It
defaults to upstream behaviour.

⚠️ What that does **not** buy: a replay is not automatically *meaningful* across a script change.
The events replay identically; the game's responses may not. It is evidence only where the
interaction sites are unchanged — which for guard wraps (they wrap in place, they do not move
objects) is usually true, and is checkable from the emitted source.

### ⛔ Its ORACLE is the wrong kind, and that decides how to use it

The recorder answers **"is this the same as last time?"** — a regression question. Its check is a
screenshot MD5 against the recording. Record a session in which a guard is broken and the replay
passes forever, happily, because the recording *is* the specification.

What this project needs is the other kind: **"does this match what the spec says?"** — conformance.
The expectation comes from the derived guard specs in the emitted patch source
(`tools/probes/_sites.py` reads them), not from an earlier run of the same thing.

That is not a small difference in emphasis, it decides the architecture:

| | recorder's model | what a lite row needs |
|---|---|---|
| expectation | a previous run | the emitted source: bit, item, owner, refusal text |
| per-row setup | whatever was recorded | different item, mode, warn word, room — **authored** |
| verdict | screenshot hashes match | `has:` moved, warn bit moved, the right sentence printed |

So "record each row once and replay it" — which is what I suggested last message, and ranked first
— is the wrong shape. Twenty-five rows are not twenty-five recordings; they are twenty-five
*parameterisations*, and a replay of any one of them would confirm only that the game still does
what it did when the tape was made.

### What is worth taking from it

The **transport**, not the oracle. Two hooks, and they are exactly what the console-driven
harness lacks:

* **`EventRecorder` is a `Common::EventSource`.** During playback its `pollEvent()` *supplies*
  events to the engine, and it `warpMouse`es to match. That is deterministic input injection
  through the engine's own pipeline — no XTEST, no window focus, no dropped keystrokes.
* **`processMillis()` intercepts `getMillis()`** and returns `_fakeTimer`, driving
  `_timerManager->handler()` itself. The engine's clock becomes *controllable* — which is
  precisely the thing that made the guard interaction unreliable, since a timed dialog could never
  be made to expire on demand.

A recording also stores `randomSourceRecords` (RNG seeds), which is the third leg of determinism.

⭐ **So the shape is: keep this project's oracle, borrow the recorder's transport.** Expectations
derived from the emitted source (built), state set up over the SCI console (built, reliable),
verdicts from `has:`/warn-bit/`said()` (built) — and the one missing piece, deterministic input
with a controllable clock, extracted from `pollEvent()` + `processMillis()` rather than driven by
XTEST. A row becomes a *script* (`t=1200 click 141 124`), authored from the site table, not a tape.

⚠️ **Practical detail learned the hard way**: record a session that ends by QUITTING the game.
Playback does not stop when the events run out — it keeps running — so a recording made by killing
the process never terminates on replay, and the exit-code oracle that
`run_event_recorder_tests.py` relies on is meaningless.

Also captured: the recording stores `randomSourceRecords` (RNG seeds) and periodic screenshots
with their MD5s, which is what makes a replay deterministic.

## Two transports, and the line between them

`tools/build_text_scummvm.sh` builds a ScummVM with `--enable-text-console`, whose SCI debugger
does `fgets(stdin)` and prints a `debug> ` prompt instead of drawing a console in the game window.
`sci_console.py --binary <that build>` switches the whole command path to a pipe. Built and
working, 2026-08-22.

What that buys, all verified:

- **No typing, so no wedges.** The prompt is the delimiter — no sentinel command, and nothing a
  dropped character can destroy. The failure that stopped the nine-row suite cannot occur.
- **Boot with zero clicks.** The session starts at a prompt *before the game has run an
  instruction*, so the intro is never entered: run the VM briefly, `room 1`, done. The Sierra
  logo and the "Skip it" dialog — the most fragile part of the keystroke path, the one that
  needed a screenshot to debug — are simply not in the picture.
- **Deterministic time.** `debug_countdown N` re-enters the debugger after N VM instructions
  (it is decremented in the opcode loop, not once per drawn frame), so `resume()` is a bounded
  run rather than a wall-clock guess, and it needs no keystroke to get control back.

⛔ **Where it stops: a `send` that makes the game PRINT does not return.**

A screenshot taken during the block settles what is happening, and it is not what it looks like.
The dialog is **fully drawn** — *"Mmmmmmm! That was the best custard pie Graham has ever eaten!"* —
with an **hourglass cursor**. So the dialog's own loop is running and input is disabled: it is
waiting on a TIMER, not on a click. And inside a debugger-nested `run_vm` the game clock does not
advance, so that timer never expires. It waited 45 seconds for a `#time 4` dialog.

That rules out the obvious repairs. Clicking does not help (nothing is waiting for a click).
Building with `--enable-readline` does not help either: `readline_eventFunction` pumps only while
readline is waiting AT THE PROMPT, and the block is inside `cmdSend`, after readline has already
returned a line. Injecting into the game's own event object and letting the normal loop deliver it
does not help: `User:doit` explicitly zeroes `curEvent` before every `GetEvent`.

Nor does going around `send` entirely. Setting the icon bar to its inventory-USE icon (`icon4`,
whose `message` is 4) and injecting a REAL mouse click while the game runs under a countdown gets
remarkably far — the click reaches the handler, the arm's first statement runs, its text appears —
and then stops at exactly the same place:

```
before: warn=0x0000 g130=0x0000 has_pie=1
after : warn=0x0000 g130=0x0001 has_pie=1     <- arm entered, printed, then parked
```

⭐ **The single root cause: the game clock does not advance while the debugger holds stdin.** The
guard's refusal is emitted *after* the print, the print is a real-time modal, and the game only
ever runs in `debug_countdown` bursts with the clock frozen between them — so the modal never
reaches its timeout however many bursts it is given, and follow-up clicks do not dismiss it. That
explains the `send` case and the click case together.

The graphical build does not have the problem — `_debuggerDialog->runModal()` keeps the engine
turning while it waits — which is why every guard result above was obtained on the stock binary.

### The patch, and what a backtrace found

We only use ScummVM locally for debugging, so it can be patched. Before writing any C++ the
console was asked where the VM actually was — the countdown fires mid-dialog, which leaves a
prompt, which means `bt` works:

```
6: script 0   - ego::handleEvent      <- the guarded arm
7: script 0   - call 62b              <- the message printer
8: script 300 - export 0              <- PrintScript's proc300_0
9: script 300 - call 8d
a: script 300 - call 1f6
```

`proc300_0` is `(DoAudio 2 ...)` followed by a wait guarded by `(if (> temp0 0))` — it is the
**CD speech**. The engine advances only during `debug_countdown` bursts, and between every burst
the debugger sits in `fgets` with the clock stopped, so the speech never finishes. Muting speech
does not help; neither does un-muting it. (Both were tried.)

`tools/scummvm-patches/0001-*.patch` makes the plain-`fgets` branch of `Debugger::enter()` poll
stdin instead of blocking, pumping events and letting time pass between polls —
`readline_eventFunction`'s idea, in the place that needs it. `build_text_scummvm.sh` applies it.

**It works, measurably**: with the patch the click path runs *past* the print and reaches
`IconBar::dispatchEvent`, which it never did before.

⚠️ **It does not rescue `send`.** A print raised inside `cmdSend`'s re-entrant `run_vm` happens
while the debugger is *not* at a prompt, so the patch never runs — `send <obj> handleEvent <ev>`
on a speaking handler still hangs. Only the click path benefits.

⚠️ **And the click path is still not finished.** After reading the engine source and a long
series of controlled runs, here is exactly what is known:

**The arm runs, and then stops at the print.** In the emitted source the eat arm is four
statements with no branch between them:

```
(2  (proc0_9 16)          ; flag 16  -- OBSERVED: set
    (proc0_29 141)        ; the text -- OBSERVED: printed
    (if <allow> ... (global0 put: 2 1))   ; <- never runs
    (param1 claimed: 1)
    (if (not <allow>) ... (|= global403 $0001)))   ; <- never runs
```

⭐ **This is not a guard problem at all.** Running the same click in **Off** mode, where `<allow>`
is true and the arm should simply eat the pie, leaves the pie *still held*. Nothing after the
print executes, in any mode. The guard was never the variable.

And it is not ordinary control flow: a backtrace taken afterwards shows a normal game loop
(`KQ5::play → doit → Game::doit → User::doit`), so the handler's frame is *gone*. Something
abandons it inside the print.

Ruled out by experiment, so nobody repeats them:

| tried | result |
|---|---|
| `--enable-readline` | its event hook only runs at the readline prompt, never inside `cmdSend` |
| muting speech / un-muting speech | no change |
| extra clicks to dismiss the print | no change (and they were suspected of the IconBar fault; removing them did not fix that either) |
| waiting at the prompt so real time passes | no change |
| ONE long uninterrupted burst, so the debugger never breaks mid-print | no change |
| removing the event **drain** from the patch (it was eating the game's input — a real bug, now fixed) | no change |
| hand-set `curIcon`/`curInvIcon` vs. replicating `Inventory::showSelf` exactly | fixed one crash, did not fix this |

⭐ **The fork is settled, and the answer is the build.** The identical probe code, same game copy,
same click, differing only in which ScummVM runs it:

| binary | Off mode, click the pie on Graham | |
|---|---|---|
| **stock** (graphical console) | `has_pie=0` | the arm completes — the pie is eaten |
| **text-console build** | `has_pie=1` | parked at the print, every time |

So the click path is sound and the text-console build is what breaks interaction. Nothing tried
changed the second row: countdown tuning, one 40-second free run, dismissal clicks in both
regimes, real-time waits at the prompt, the event-pumping patch, removing its drain, muting or
un-muting speech.

The user also confirmed by playing: **with guards Off, Graham eats the pie.** That is what made
the comparison above worth running, and it ruled out the game and the patch set in one move.

⛔ **Two of my own conclusions here were wrong, and controls caught both.** `bpx put` never firing
looked like proof the disposal is never called — until `bpx doit`, on a method that runs every
cycle, also never fired: **breakpoints do not work in this setup at all**. And a "the game stalls
after a bare `exit`" reading came from misreading *incremental* counts as cumulative; the game
actually runs steadily at ~97 cycles/s. Run the control first.

**Where the click path stands on the stock binary.** It reaches the guard: in Lite mode the game
prints *"Just kidding! You hold on to it because you still need it."* and correctly keeps the pie.
But the warn bit does not read as set, and the refusal text turns up in the *next* attempt's
window — so the arm is completing asynchronously with respect to when the probe samples. A late
re-read six seconds on does not catch it either. That is the open thread.

**The working interaction path today is still `send <obj> handleEvent <event>` on the stock
binary**, which is how all four verified rows were driven.

**Bottom line: no guard row has completed over the pipe.** The four verified rows remain the ones
driven on the stock binary with XTEST.

So the honest split today is **pipe for state, stock binary for interaction**:

| | pipe (text console) | XTEST (stock) |
|---|---|---|
| boot to a playable room | ✅ no clicks | fragile click sequence |
| read/write globals, resolve objects, read `nsRect` | ✅ | ✅ (slower, can wedge) |
| advance the game | ✅ deterministic | wall-clock |
| **offer an item / trigger a guard that speaks** | ⛔ blocks | ✅ |

Also unresolved on the text build: `restore_game` exits ScummVM rather than returning (it ends in
`cmdExit`, and arming a countdown first does not save it). Save/restore persistence therefore
remains unverified — it is still the oldest open item in `GUARD-MODES.md`.

⚠️ **Provenance.** Everything above is Claude DRIVING, and mostly driving *state*. No probe has
played a game. `guard-modes-play-verified` and the play-confirmed results in the test plans are the
user's own playing and stay that way.
