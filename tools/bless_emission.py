"""Show the emission delta against the committed manifest -- and, on sign-off, refresh it.

    python3 tools/bless_emission.py            # emit + show the delta (DRY RUN, writes nothing)
    python3 tools/bless_emission.py --reuse    # skip the ~7-min emit, hash build/emission_check
    python3 tools/bless_emission.py --write    # refresh testdata/emission_manifest.json

⛔ A REFRESH IS A BLESS. The contract is: present the delta -> get the user's yes -> ONLY THEN
--write. Running --write to make a red test green without that sign-off is exactly the failure
the manifest exists to prevent. The dry run prints what --write would change, so the delta can
be reviewed first; for byte-level review use tools/measure_emitted_bytes.py against a worktree
at the pre-change commit.

The save-compat half refreshes too: the blessed script-0 sizes are re-read from the INSTALLED
dirs (~/sierra/patched). If one changed, this tool says so loudly -- that size is stamped into
every ScummVM save, and blessing it means accepting that saves from before the change are dead.
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
import emission_manifest as EM                                       # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="refresh the manifest (ONLY after the user blessed the delta)")
    ap.add_argument("--reuse", action="store_true",
                    help="hash the existing %s instead of re-emitting" % EM.EMIT_DIR)
    a = ap.parse_args()

    if not a.reuse:
        rc = EM.emit_all()
        if rc != 0:
            print("⛔ at least one game emitted nothing -- refusing to bless a manifest that "
                  "would drop it. Fix the build (missing IR?) and rerun.")
            return 1
    fresh = EM.build_manifest()
    for g, entry in fresh["games"].items():
        if not entry["files"]:
            print("⛔ %s hashed to an EMPTY tree at %s -- with --reuse, did the emit ever run? "
                  "Refusing to bless." % (g, os.path.join(EM.EMIT_DIR, g)))
            return 1

    old = EM.load() or {"games": {}, "script0_installed": {}}
    moved = False
    for g in sorted(set(old["games"]) | set(fresh["games"])):
        o = old["games"].get(g, {}).get("files", {})
        n = fresh["games"].get(g, {}).get("files", {})
        changed, added, removed = EM.diff_files(o, n)
        if not (changed or added or removed):
            print("  %s: unchanged (%d files)" % (g, len(n)))
            continue
        moved = True
        print("  %s: %d changed, %d added, %d removed" % (g, len(changed), len(added), len(removed)))
        for label, paths in (("~", changed), ("+", added), ("-", removed)):
            for p in paths:
                print("      %s %s" % (label, p))

    o0, n0 = old.get("script0_installed", {}), fresh["script0_installed"]
    for name in sorted(set(o0) | set(n0)):
        if o0.get(name) != n0.get(name):
            moved = True
            print("  ⛔ SCRIPT-0 SIZE: %s blessed=%s installed=%s -- blessing this accepts that "
                  "every save from before the change is DEAD (savegame.cpp:1466-1469)."
                  % (name, o0.get(name), n0.get(name)))

    if not moved:
        print("manifest already matches the emission -- nothing to bless.")
        if a.write and not os.path.exists(EM.MANIFEST_PATH):
            EM.save(fresh)
            print("wrote the FIRST manifest to %s" % EM.MANIFEST_PATH)
        return 0
    if a.write:
        EM.save(fresh)
        print("manifest refreshed at %s -- this was a BLESS; the delta above is what the user "
              "signed off on." % EM.MANIFEST_PATH)
    else:
        print("DRY RUN -- nothing written. If the user blesses this delta, rerun with --write "
              "(add --reuse to skip the re-emit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
