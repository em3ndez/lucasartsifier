# Does the guard MODE survive a save/restore, and does Restart put it back to Full?
#
# `docs/GUARD-MODES.md` asserts both, and both follow from the storage being ordinary globals --
# but `guard-modes-play-verified` has recorded them as "still unwatched" since the feature
# shipped. They need no interaction at all, only state, which makes them the natural first thing
# to run over the pipe transport.
#
# The test is set LITE -> save -> set OFF -> restore. If the restore did nothing the mode would
# still read OFF, so a pass cannot be faked by the mode simply never changing.
#
#   .venv-x/bin/python tools/sci_console.py --binary <text-console scummvm> \
#       --game <COPY> --id kq5 --title Quest --script tools/probes/kq5_mode_storage.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot

MODE_G, WARN_G = 402, 403
NAMES = {0: "Full", 1: "Lite", 2: "Off"}
SLOT = "modestore"

def log(*a): print(*a, flush=True)
def mode(): return c.gint(MODE_G)
def show(tag): log("  %-24s mode=%d (%s)  warn=%#06x"
                   % (tag, mode(), NAMES.get(mode(), "?"), c.gint(WARN_G)))

log("== boot ==")
boot(c, log=log)
ok = True

# --- 1. the mode is writable and reads back --------------------------------------------
c.setg(MODE_G, 1)
c.setg(WARN_G, 0x0240)                             # two arbitrary sites already warned
show("LITE + 2 warned bits")

# --- 2. save, then move the mode AWAY ---------------------------------------------------
log("  save ->", c.cmd("save_game %s" % SLOT)[:70].replace("\n", " "))
c.setg(MODE_G, 2)
c.setg(WARN_G, 0)
show("moved to OFF, bits cleared")
if mode() != 2:
    ok = False; log("  FAIL: could not move the mode away")

# --- 3. restore: both the mode AND the warn bits must come back --------------------------
log("  restore ->", c.cmd("restore_game %s" % SLOT)[:70].replace("\n", " "))
c.resume(1)                                        # takes effect on the next cycle
show("after restore")
if mode() != 1:
    ok = False; log("  FAIL: mode did not survive save/restore (want 1, got %d)" % mode())
if c.gint(WARN_G) != 0x0240:
    ok = False; log("  FAIL: warn bits did not survive (want 0x0240, got %#06x)" % c.gint(WARN_G))

# --- 4. restart must put it back to Full and unwarned ------------------------------------
log("  restart ->", c.cmd("restart_game")[:60].replace("\n", " "))
c.resume(4)                                        # script 0 reloads
show("after restart")
if mode() != 0:
    ok = False; log("  FAIL: restart left the mode at %d, not Full" % mode())
if c.gint(WARN_G) != 0:
    ok = False; log("  FAIL: restart left warn bits at %#06x" % c.gint(WARN_G))

log("\n=== mode storage: %s ===" % ("PASS" if ok else "FAIL"))
