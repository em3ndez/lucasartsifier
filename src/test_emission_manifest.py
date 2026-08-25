"""The suite's gate on the EMITTED SOURCE -- fails, naming the game and the file, when it moves.

Until 2026-08-24 nothing here failed when the emission changed: the goldens and the watched tier
freeze the ANALYSIS surface (verdicts, specs, placement rows, site counts), never the source text
a placement produced. Two shipped-emission changes landed green in one week because of it. This
test re-emits all five games through the canonical order (~7 min -- the emit is the cost, the
hashing is free) and compares every emitted file against the committed manifest
(`testdata/emission_manifest.json`).

⛔ THIS FILE NEVER SKIPS, per test_golden's doctrine: a missing IR, a missing manifest or an
absent install dir is a FAILURE naming the build step, not a `(skip ...)` line. A gate that can
quietly decline to run is not a gate -- the manual harness's whole failure mode was being
skippable.

IF THE EMISSION CHECK FAILS: the DEFAULT assumption is that your change moved the emission.
Review the delta (`tools/bless_emission.py` prints it; `tools/measure_emitted_bytes.py` against
a worktree gives the byte-level diff), get the user's sign-off, and only then refresh with
`tools/bless_emission.py --write` -- a refresh IS a bless. A pure bit renumbering fails here on
purpose; benign drift is still drift someone must see.

IF A SAVE-COMPAT CHECK FAILS, STOP: a changed script-0 size means EVERY existing save refuses to
load on that build (ScummVM savegame.cpp:1466-1469; the v19 KQ5 rebuild did it silently). Do not
install, do not bless past it without the user.
"""
import os
import sys

import emission_manifest as EM

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f"\n      {detail}" if detail and not cond else ""))


def _cap(paths, n=10):
    return ", ".join(paths[:n]) + (f" ... and {len(paths) - n} more" if len(paths) > n else "")


def run():
    manifest = EM.load()
    games = EM.games()

    print("  emitting %d game(s) into %s (the ~7-minute part) ..." % (len(games), EM.EMIT_DIR))
    EM.emit_all()

    for g in games:
        tree = os.path.join(EM.EMIT_DIR, g)
        got = EM.hash_game_tree(tree)
        check(f"emission: {g} emitted",
              bool(got),
              f"the emit produced nothing at {tree} -- most likely no IR for {g} "
              f"(build/ missing or the IR was never built). This is a failure, not a skip: "
              f"an unmeasured game is an unguarded game.")
        if not got:
            continue
        blessed = (manifest or {}).get("games", {}).get(g, {}).get("files")
        if blessed is None:
            check(f"emission: {g} matches manifest", False,
                  f"no manifest entry for {g} -- review the emission, then bless it with "
                  f"tools/bless_emission.py --write")
            continue
        changed, added, removed = EM.diff_files(blessed, got)
        detail = ""
        if changed or added or removed:
            parts = []
            if changed:
                parts.append(f"{len(changed)} changed: {_cap(changed)}")
            if added:
                parts.append(f"{len(added)} added: {_cap(added)}")
            if removed:
                parts.append(f"{len(removed)} removed: {_cap(removed)}")
            detail = ("the EMITTED SOURCE moved -- " + "; ".join(parts)
                      + ". Review the delta (tools/measure_emitted_bytes.py against a worktree "
                        "at the pre-change commit shows the bytes), then bless with "
                        "tools/bless_emission.py --write. A refresh is a BLESS.")
        check(f"emission: {g} matches manifest", not (changed or added or removed), detail)

    check("emission: manifest covers exactly the emitted game set",
          manifest is not None
          and set((manifest or {}).get("games", {})) == set(games),
          "the manifest's game set and measure_emitted_bytes.GAMES disagree (or the manifest "
          "is missing) -- a game silently leaving the manifest is how coverage rots. "
          "tools/bless_emission.py --write after review.")

    # -- save compatibility: script-0 size is stamped into every ScummVM save ------------------
    blessed_s0 = (manifest or {}).get("script0_installed", {})
    installed = EM.installed_script0()
    s0_lines = []
    for name in sorted(set(blessed_s0) | set(installed)):
        want, got_size = blessed_s0.get(name), installed.get(name)
        if want != got_size:
            s0_lines.append(f"{name}: blessed={want} installed={got_size}")
    check("save-compat: installed script-0 sizes match the blessed sizes",
          manifest is not None and not s0_lines,
          "; ".join(s0_lines)
          + " -- a changed script-0 SIZE means EVERY existing save refuses to load on that "
            "install (savegame.cpp:1466-1469; the v19 break). If an install is new or gone, "
            "that is also for the user to see. Bless only with sign-off.")

    lb_lines = []
    for game, (tree, size) in EM.latest_build_script0().items():
        want = blessed_s0.get(game)
        if want is not None and size != want:
            lb_lines.append(f"{tree}/patch/0.SCR is {size}, installed {game} is {want}")
    check("save-compat: newest build trees' script-0 sizes match the installed sizes",
          not lb_lines,
          "; ".join(lb_lines)
          + " -- INSTALLING THIS BUILD BREAKS EVERY EXISTING SAVE. Check stat -c%s before any "
            "install; do not install without the user.")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed" + (f"  FAILURES: {FAIL}" if FAIL else ""))
    return not FAIL


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
