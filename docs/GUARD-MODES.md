# Guard modes: full / lite / stock

The player toggles, in-game and at any moment, how a placed guard behaves. Detection,
spec derivation and placement are untouched — the mode is pure EMISSION (patcher/trigger)
plus a small per-dialect UI patch. Shipped first in LSL2/KQ4 mode builds and KQ6 v26.

## The three modes

| mode | value | shown as | behavior |
|---|---|---|---|
| **full** | 0 | `Full` | every guard refuses, exactly as before this feature (the default — uninitialized globals and stale saves read 0) |
| **lite** | 1 | `Lite` | each guard SITE refuses once; from then on it prints "You have been warned!" and lets the original behavior run. The bit is per SITE, so a refusal taken in **full** already counts — switching to lite does not buy a fresh refusal at an obstacle you have already hit |
| **stock** | 2 | **`Off`** | every guard lets the stock behavior through silently |

The internal name of mode 2 is **stock** — it is the stock game, and that is what `trigger.stock_or`
and the rest of this document call it. The player sees **`Off`**: mid-game the only question is
whether the guards are on [user, 2026-08-08]. All three player-facing names live in one place,
`patcher.MODE_NAMES`, because the label was previously written out six times across the two
dialects and a rename reaching five of them would leave the UI disagreeing with itself.

Silent guard kinds (arm-event, nav-assign, edge-exit closes, award gates) and the
register/flag holds (KQ4 nightfall, KQ6 wedding fuse) have no refusal to warn with, so
lite behaves as full there [user ruling at plan time]; stock bypasses them too.

## Storage (per game, derived)

- **Mode global** = the first index past everything the assembled game declares OR
  references (`patcher._init_mode`): LSL2 `global481` (stock rm63 already reads
  `global480` out of bounds), KQ4 `global401`, KQ6 `global171`, LB2 `global400`,
  KQ5 `global402`.
- **Warned bits** = one bit per guard site in trailing bitmask words after the mode
  global (`global482+` / `global402+` / `global172+`), allocated in emission order; a
  multi-clause placement shares one bit ("every guard fires once" is per guard).
- All are ordinary globals: declared by the existing `_declare_missing_globals` pass
  (re-run inside `install_mode_ui`, after every apply pass, because the globals exist
  only in emitted text), persisted through save/restore by the whole-heap SaveGame
  kernel, and reset to full/unwarned on Restart (script 0 reloads).

## The emitted dispatch

Refusal-bearing wraps (`trigger.guarded_wrap`, one builder for every kind that says no):

```
(if <guard>
    <body>
else
    (if (or (== gMode 2) (and (== gMode 1) (& gWarnWord $mask)))
        (if (== gMode 1) (<proc> {You have been warned!}))
        <body>                                  ; proceed
    else
        <mechanical deny lines, e.g. edgeHit resets>
        <refusal>
        (if (== gMode 1) (|= gWarnWord $mask))  ; mark warned
    )
)
```

The body is duplicated once so the guard condition stays verbatim at the site (nothing
hoisted into helpers — the patched source stays reviewable, and test_sci11_patch's
substring pins stay meaningful). Silent kinds and holds get only the stock bypass:
`(or (== gMode 2) <guard>)`.

Sink remedies no longer DELETE the disposal: the `put:` (and its adjacent negative
`changeScore:`) runs under the same allow test, the retraction speaks only when the
disposal was withheld — inline behind `(not <allow>)` on the appended path, via the
cue-object's `register` property on the rides-the-say path (an EXISTING selector on
Script, deliberately: a novel property name would need a vocab-997 entry the patch set
does not ship). Full mode is behaviorally identical to the deletion era: mode 0 never
takes the disposal branch.

## The in-game UI (`patcher.install_mode_ui`, derived by shape)

- **SCI0** (LSL2/KQ4): a `Guards...` item APPENDED to the last menu of the menu bar (the
  file with the most literal `AddMenu` declarations; appending cannot shift any existing
  menu code, including KQ4's runtime Debug menu). Its handler case (before the
  handleEvent switch's own `else`, reusing the switch's temp) runs a 3-button chooser on
  the derived display proc. LSL2 = menu code 776, KQ4 = 772 (computed, not declared) --
  the `Action` menu on both, since the user rejected the Sound menu the first cut appended
  to; the 1283/1284 this line used to name were that first cut's Sound-menu codes.
- **SCI1 / SCI1.1** (KQ6, LB2, KQ5): an `iconGuards` ControlIcon added to the `of
  GameControls` panel, one row below the deepest existing row (pitch derived from the row
  ladder, window grown to fit), its face a blank plate out of the panel's own art — every
  button face in it has a word baked in, so borrowing one ships a control that lies about
  what it does.

  ### ⭐ ONE CONSTRUCT, FIVE SPELLINGS (2026-08-21)

  KQ5 and LB2 shipped with **no picker at all** — `install_mode_chooser` found no host,
  retracted the mode, and every guard emitted permanently full-strength. Both games have
  the panel. The installer knew exactly one spelling of each part of it, KQ6's:

  | part | KQ6 | KQ5 | LB2 |
  |---|---|---|---|
  | the panel | `(instance X of GameControls)` | **`(class KQ5Controls of GameControls)`**, instantiated twice (fast/slow window) | instance |
  | the row ladder | `(= nsTop (+ 0 (if (== global107 256) 103 else 104) 10))` | same idiom, **unparenthesised `if`** and a second term in front | **literal `nsTop 108` properties** |
  | the face | a blank plate the panel DRAWS at the deepest row | **never drawn at all** — 76×16 art the panel carries and does not use | drawn beside a different control |
  | the chooser | `Print … addButton:` | **no `addButton:` anywhere in KQ5** — asks with `(proc255_0 <text> 81 {label} value)` | `Print` |
  | the window | one, taking a `bottom:` send | **two** windows | **assigns `(= bottom …)`** and draws its own bevel at literal coordinates |

  So each part is now read off the game rather than matched against KQ6's spelling:
  `_panel_host` (a GameControls that parks itself in the global `ControlIcon` hides it
  through — which is also what tells the settings panel apart from KQ5's save-game
  selector, a GameControls too), `_panel_controls` (the ladder off the CONTROLS, with
  `_balanced_span` doing the paren walk), `_is_blank_cel` (a plate is recognised by BEING
  BLANK: inset past the bevel, one colour — unique in all three games, and it reproduces
  KQ6's shipped 947/1/2), the game's own vocabulary for the dialog form, and every window
  in either spelling for the growth.

  Two capabilities underneath had to be added to ask those questions. `sci_gfx.decode_view`
  had no SCI1 path — KQ5's views are VGA with SCI0's loop tables and SCI1.1's byte-run
  pixels, and read through the EGA nibble decoder they came back as structured noise with
  the right sizes and nothing thrown. And `sci_gfx.view_palette`, because **two different
  palette indices can be the same colour**: KQ5's panel writes text in index 0 and the only
  blank plate its art carries is a text-entry field whose interior is index 254, and both
  are `(0, 0, 0)`. The label drew and could not be seen. The rule is now that the label may
  not be the colour of what it is written on; where it is, it takes the plate's own bevel
  colour, which is legible on that interior by construction.

  ### The window grows by what the row NEEDS, not by a pitch

  A pitch is the natural growth and is enough while the new row is no taller than a rung.
  The plates are not: KQ6's is 22 against a pitch of 20, LB2's is 23. KQ6 had slack to
  absorb the overhang; LB2 did not, and its plate lost its bottom bevel to the window edge.
  So the window is MEASURED — `bottom - top`, evaluated out of the game's own art
  (`_const_eval` resolves `CelWide`/`CelHigh` and takes the larger arm of an `(if …)`) — and
  the growth is `max(pitch, what the row needs)`: KQ6 **20** (unchanged), LB2 **22**, KQ5
  **20** (its rect is per-print-language and not constant, and its 16px plate needs nothing
  more).

  ### ⭐ THE ONE BIT: a borrowed face must not ask for a press animation

  `IconI::select` animates a press by drawing **cel 1** of the icon's own loop while the
  mouse is held and **cel 0** on release — the SCI convention that a control's loop is a
  two-cel `{0: up, 1: down}` pair. Every real button here obeys it (KQ6 loops 2–9 are each
  exactly two 50×15 cels). Our face does not: it is cel 2 of the window's decorative loop,
  and KQ6's loop 1 is `[0: a 12×43 slider arrow strip, 1: the 58×122 left-hand inset,
  2: the 58×22 plate]`. So a press painted the arrow strip and the big inset at the
  control's position. **That single bit is the whole of every visual defect reported in
  v29, v30 and v31**, which all carried it ($0183 and $01C1 both set $0001):

  | report | what it actually was |
  |---|---|
  | v29 "a + − slider artifact" | cel 0 — the strip's top rows are a `+`, its bottom rows a `−` |
  | v30 "looks weird on click" | cel 1, clipped by the window edge, plus cel 0 on release |
  | v31 "same behavior" | nothing in v31 touched the bit, so nothing changed |

  Measured, not inferred: the artifact's pixels in the play screenshot are cel 0 and cel 1
  at `nsLeft`/`nsTop` to within a pixel, and the whole thing was then reproduced and cured
  under ScummVM. Two earlier diagnoses were wrong and are recorded here so they are not
  re-run: it is **not** nested modals (v31 hid the panel first, no change) and **not** the
  window growth (v29 grows it too and is clean at rest).

  So `_install_panel_chooser` clears the press bit unless the face really is a two-cel
  button pair. Both halves are read out of the game — the bit off the condition guarding
  that first `DrawCel` in `IconI::select` (`_icon_press_bit`), the pair off the decoded
  art. KQ6: 449 → **448**.

  ### The chooser, and the two orderings that matter

  It opens a 3-button `Print`, cloning `iconAbout` — the panel's own dialog-opening
  control, found by shape (`_dialog_icon`: a `select` that hides the panel, then prints)
  rather than named. That template also supplies the rest of the signal, including the
  $0040 that makes the icon bar's modal loop exit. Two orderings, both load-bearing:

  - **the panel is hidden before the chooser draws** (`(<panel> hide:)` first), and
  - **`select` returns 1** — `IconBar::dispatchEvent` only reaches its exit flag inside
    `(if (self select: …))`, so a 0 there leaves the modal loop spinning over a window it
    has just disposed.

  And the control must never call `(<panel> show:)`: that re-enters `GameControls::show`,
  running the panel's whole modal loop a second time from inside itself, so dismissing only
  ever returns to the outer loop — **that**, not the dialog, is why v29 never closed.

  The label is two lines — `GUARDS` over the current mode — so the state is legible without
  clicking, which is also the only way to read it back after the chooser has closed the
  panel behind itself. The layout is MEASURED (`sci_gfx.decode_font`): plate 58×22, font 4
  is 9px, `GUARDS` 31px, `STOCK` 27px — two 9px lines fit in 22px, where one line reading
  `GUARDS: FULL` measures 56px against a 58px plate.
- The SCI0 menu chooser keeps its 3-button `Print`: LSL2 and KQ4 open it from a menu bar,
  not from inside a modal panel. Its buttons use values 1/2/3 and store `value - 1` only
  when nonzero, so dismissing keeps the current mode.

## What is pinned

`src/test_mode.py`: wrapper structure per mode (guard verbatim, body duplicated, mark in
deny only, classic v25 shape when unconfigured), allocator word rollover, UI installers
against the real game files (codes 776/772, balance), surface neutrality (guards.py /
missability.py never touch the mode machinery), and the mini-project declaration flow.
Plus, for the panel control: **the press animation is only asked for when the face is a
two-cel button pair** — checked against the decoded art and the class constant, not
against a signal number, with the sibling half asserting the pair test still recognises
the panel's own buttons (or the check would pass by always saying "no pair"). Also the
hide-before-print order, the `(return 1)`, and that the control never re-shows the panel.
Full-surface gates at the introduction: LSL2 golden green; KQ4/Dagger/KQ6 snapshots
byte-identical to the pre-feature worktree baseline; KQ6 v26 compiled 341/341 with
verify "fixed 10 + 1 group(s), NEW: none"; LSL2/KQ4 mode builds compiled and emitted.

## Installing v32 over the installed build (KQ6)

**Only `903.SCR`/`903.HEP` differ** from what is installed at `/mnt/i/sierra/patched/kq6`
(verified file-by-file). So this is a two-file drop-in, NOT the usual delete-then-copy:

    cp build/kq6_patch_v32/patch/903.{SCR,HEP} /mnt/i/sierra/patched/kq6/

which also avoids having to re-restore Sierra's own 425/460/470 afterwards (see the
correction in `docs/KQ6-RETEST-V22-CONSOLE-SHEET.md`). A full delete-then-copy install is
still correct if you prefer it; it just costs that extra step.

⚠️ The two-file drop-in makes it easy to lose track of what is actually installed — the
build that was in place when v31 was reported as "same behavior" was **v30**. Check before
believing a play report:

    for v in 30 31 32; do cmp -s build/kq6_patch_v$v/patch/903.SCR \
        /mnt/i/sierra/patched/kq6/903.SCR && echo "installed == v$v"; done

## Play-verification

The UI half is **verified under ScummVM on v32** (KQ6 CD, `/usr/games/scummvm`, driven
with python-xlib XTEST + Xlib window capture — the game runs headless-ish on `:0`, so this
loop needs nobody at the keyboard):

- panel at rest: `GUARDS` over `FULL`, no artifact, window sized right ✔
- click: panel closes, chooser opens over the room, no artifact in the press frame
  (captured 50 ms after ButtonPress) ✔
- pick LITE / STOCK → reopen → plate reads `GUARDS / LITE`, `GUARDS / STOCK` ✔
- ESC on the chooser → mode unchanged ✔
- PLAY closes the panel and the game resumes ✔
- the panel's own controls (SPEECH, sliders) still work ✔
- **control**: reinstalling v31's `903` and holding the mouse on the control reproduces the
  artifact exactly as reported, and v32 does not ✔

### LB2 and KQ5, driven under ScummVM 2026-08-21 (NOT play-tested)

Both games' choosers were built, installed into scratch copies and driven with the same
XTEST harness (`tools/kq5_panel_probe.py`, `tools/lb2_panel_probe.py`):

- **both BOOT** with a recompiled script 0 — which for LB2 is the §7ak crash not recurring;
- the panel carries `GUARDS / FULL` in its icon column, below `PLAY`, framed like the
  panel's own buttons and inside a window that grew to hold it;
- clicking it closes the panel and opens the chooser — `Softlock guards: / now: full` with
  Full/Lite/Off on LB2 (a `Print`), `Softlock guards -- now: full` with the same three on
  KQ5 (a `proc255_0` button dialog, because KQ5 has no `addButton:`);
- picking **Lite** and reopening the panel reads `GUARDS / LITE`.

⚠️ **That is a driven check, not a play test**, and it moves emissions that ARE play-confirmed
(`v3.1-kq5`, `v1.0-lb2`). Nothing here says the guards themselves still behave.

### Confirmed by the user in play, 2026-08-08

- KQ6's panel control **works** — the artifact is gone.
- **The SCI0 (LSL2/KQ4) menu chooser looks right and works properly.**
- ⭐ **Lite counts attempts made while in full.** The warned bit is per SITE, not per
  site-per-mode, so a guard that already refused you in full is *already warned* when you
  switch to lite: it lets you through immediately rather than spending a second refusal on
  the same obstacle. That is the intended reading of "each guard site refuses once" and it is
  now confirmed to be what the player experiences.
- **Restart resets the mode to full**, as the storage section claims.
- **W1 — the sacred water.** Wasting it is retracted; the mode-conditional sink remedy behaves.
- *"everything there works as expected"* — the mode machinery is play-confirmed on all three
  games.

Measured here rather than played: **the mode survives save/restore** — set lite, save, set stock,
restore, and the panel reads lite again (`tools/kq6_mode_persist_probe.py`; the detour through
stock is what stops a no-op restore passing).

⚠️ One caveat recorded against my own overreach: a probe run of mine appeared to show restart
NOT resetting the mode, and it was wrong — the run never established that the restart it was
measuring had happened. The user's play settles it. A driven run that cannot prove its own
precondition is worth less than no run.
