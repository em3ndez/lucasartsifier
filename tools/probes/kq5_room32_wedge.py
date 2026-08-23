# Room 32 WEDGES the game: after the suite visited it, every later `room N` left global 11 at 32
# and twelve rows reported the same failure for the same reason. Before guessing at a recovery,
# find out what is holding it -- `Game:doit` performs the teleport, and the two things that stop
# `Game:doit` are a non-empty global84 (its `(while global84 ...)` modal branch) and something
# else owning the loop entirely.
#
# rm032.sc has a `hungerDeath` script instance, so "Graham starved while the probe was setting up
# the row" is the first candidate, and a death in KQ5 is a modal Restore/Restart/Quit dialog.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, here, settle_room, drain_boxes, park_mouse

def log(*a): print(*a, flush=True)

def state(c, when):
    log("  %-26s global11=%-4s global13=%-4s global84=%-6s script=%-6s windows=%s"
        % (when, here(c), c.gint(13), c.gint(84), c.send(c.gaddr(2), "script")[0], c.windows()))

boot(c, log=log, teleport=True)
c.watch_text()
state(c, "after boot")

log("\n== into room 32 ==")
try:
    goto(c, 32, force=True, log=log)
except Exception as e:                              # noqa: BLE001
    log("  goto raised: %s" % e)
state(c, "after goto 32")
c.shot("/tmp/kq5_rm32_a.png")

log("\n== let it run, and watch ==")
for i in range(6):
    park_mouse(c, tag="w%d" % i, log=log)
    state(c, "round %d" % i)
    log("      said: %s" % (c.said(),))
c.shot("/tmp/kq5_rm32_b.png")

log("\n== can it still leave? ==")
c.cmd("room 4")
c.resume(seconds=6)
state(c, "asked for room 4")

log("\n== try dismissing whatever is up, then leave again ==")
said, n = drain_boxes(c, "wedge", log=log)
log("  drained %d box(es): %s" % (n, said))
c.cmd("room 4")
c.resume(seconds=6)
state(c, "asked for room 4 again")
c.shot("/tmp/kq5_rm32_c.png")
