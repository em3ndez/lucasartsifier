# THE CLEANEST CONTROL AVAILABLE: click the game's OWN icon bar and read what it did.
#
# Everything else tried so far needs an assumption -- that the ego can walk from where it is,
# that curIcon was poked into the right state, that the arm would print. Clicking an icon needs
# none: the bar is drawn by the game, it handles its own clicks, and the result is one readable
# property. If curIcon changes, a click reached SCI and was dispatched. If it does not, the
# transport is not delivering and nothing downstream is worth measuring.
#
# Icon geometry, read off a screenshot at scale 2: eight icons across the top, screen y~30,
# x centres ~28,100,170,240,310,380,450,520 -- so in GAME coordinates y~15 and
# x ~14,50,85,120,155,190,225,260. Second icon (the eye) is (50,15).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, _ret

WALK, EYE, HAND = (14, 15), (50, 15), (85, 15)

def log(*a): print(*a, flush=True)

log("== boot (teleport) ==")
boot(c, log=log, teleport=True)
bar = c.gaddr(69)

def cur():
    return _ret(c.send(bar, "curIcon")[1])

log("curIcon at boot: %s" % cur())

def try_click(kind, gx, gy, tag):
    before = cur()
    if kind == "script":
        c.cmd("script clear")
        # Show the bar first (it drops down when the pointer reaches the top), then click it.
        c.cmd("script add t=+200 move %d 2" % gx)
        c.cmd("script add t=+1200 click %d %d" % (gx, gy))
        c.cmd("script add t=+4000 mark %s" % tag)
        c.cmd("script add t=+4100 break" )
        c.resume(seconds=40, instructions=1500000)
        try:
            c.wait_mark(tag, timeout=5)
        except Exception as e:                                  # noqa: BLE001
            log("    no mark: %s" % e)
    else:
        def act():
            c.move(gx, 2)
            c.click(gx, gy)
        c.resume(seconds=8, during=act, at=1.5)
    after = cur()
    log("  %-7s click (%d,%d): curIcon %s -> %s  %s"
        % (kind, gx, gy, before, after, "CHANGED" if after != before else "unchanged"))
    return after != before

log("\n-- scripted --")
s_eye = try_click("script", *EYE, tag="e1")
s_hand = try_click("script", *HAND, tag="h1")
log("\n-- XTEST --")
x_eye = try_click("xtest", *EYE, tag="e2")
x_hand = try_click("xtest", *HAND, tag="h2")

c.shot("/tmp/shot_iconbar.png")
log("\n=== scripted clicks reach SCI: %s | XTEST clicks reach SCI: %s ==="
    % (bool(s_eye or s_hand), bool(x_eye or x_hand)))
