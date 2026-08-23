# THE CONTROL. Before asking why an arm does not complete, ask whether the click reaches the game
# AT ALL. The timeline probe showed the ego frozen at (140,136) through 64 seconds of game time
# with the icon bar untouched -- which is what "the click never arrived" looks like, and also
# what "the click arrived and did nothing" looks like. One sample cannot tell them apart.
#
# So: walk cursor, click on open ground, watch ego x/y. No guards, no items, no prints. Then the
# same click through XTEST, the transport already known to work. The PAIR is the measurement --
# either half on its own is a story.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)

def pos():
    return (c.send(ego, "x")[0], c.send(ego, "y")[0])

log("start %s   room=%s" % (pos(), c.room()))

log("\n-- scripted click at (60,150) --")
p0 = pos()
c.cmd("script clear")
c.cmd("script add t=+400 click 60 150")
c.cmd("script add t=+6000 mark walked")
c.cmd("script add t=+6100 break")
c.resume(seconds=40, instructions=1500000)
try:
    at = c.wait_mark("walked", timeout=5)
except Exception as e:                                      # noqa: BLE001
    at = None
    log("  no mark: %s" % e)
p1 = pos()
log("  %s -> %s  (t=%s)  %s" % (p0, p1, at, "MOVED" if p1 != p0 else "did not move"))

log("\n-- XTEST click at (250,150), the transport already known to work --")
p2 = pos()
c.resume(seconds=8, during=lambda: c.click(250, 150), at=1.5)
p3 = pos()
log("  %s -> %s  %s" % (p2, p3, "MOVED" if p3 != p2 else "did not move"))

log("\n=== scripted: %s | XTEST: %s ==="
    % ("reaches the game" if p1 != p0 else "DOES NOT reach the game",
       "reaches the game" if p3 != p2 else "DOES NOT reach the game"))
