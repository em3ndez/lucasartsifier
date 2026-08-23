# ⛔ THE TELEPORT NEVER HAPPENED, and two instruments hid it.
#
# 1. `room` (and `c.room()`) prints ScummVM's `currentRoomNumber()`, which is GLOBAL 13 -- the
#    room the game has been ASKED for. Writing it and then reading it back always agrees, so
#    `goto()`'s "room 206 -> 206" was never evidence that anything moved. The room the game is
#    actually IN is global 11 (`Game:newRoom` sets `global12 = global11`, `global11 = param1`).
#    Measured: global11=1, global13=206, and the screenshot shows Graham's house.
#
# 2. A screenshot of the failure showed the ICON BAR drawn across the top. That is not cosmetic:
#    `IconBar:doit` is `(while (& state $0020) ... (GetEvent) ... dispatchEvent)`, a MODAL loop
#    inside the bar. While it spins, `Game:doit` never runs -- and `Game:doit` is what performs
#    `(if (!= global13 global11) (self newRoom: global13))` AND what dispatches events to the
#    room. So with the bar up, a teleport is inert and every click is eaten by the bar.
#
# The bar comes up on its own: `IconBar:handleEvent`'s first cond arm is "no event, and the mouse
# is inside the top strip", and the scripted input transport starts its virtual mouse at the top
# left. Nothing in `boot`/`goto` ever moved it, so the bar popped up and stayed.
#
# ⭐ Which is exactly why LA6 passed and the market row did not: `offer_script` begins with a
# `move` step, and a move to open ground is what `IconBar:dispatchEvent` treats as "mouse left the
# bar" -- it returns 1 and breaks the modal loop. LA6 dismissed the bar as a side effect of
# aiming. `goto()` has no click to aim, so nothing ever dismissed it.
#
# This is the control for that reading, one variable at a time:
#   A  ask for room 206 and let it run       -> expect global11 UNCHANGED (the bug)
#   B  move the mouse to open ground, run    -> expect global11 == 206  (the cure)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot

def log(*a): print(*a, flush=True)

def where(c, when):
    log("  %-28s global11=%-4s global13=%-4s iconbar state=%#06x"
        % (when, c.gint(11), c.gint(13), c.send(c.gaddr(69), "state")[0] or 0))

boot(c, log=log, teleport=True)
where(c, "after boot")
log("  window_list: %s" % c.windows())

log("\n== A: ask for room 206, run 6s of game time, change NOTHING else ==")
c.cmd("room 206")
c.resume(seconds=6)
where(c, "after the ask + a resume")

log("\n== B: same again, but move the virtual mouse off the icon-bar strip first ==")
c.cmd("script clear")
c.cmd("script add t=+200 move 160 150")
c.cmd("script add t=+2500 mark moved")
c.cmd("script add t=+2600 break")
c.resume(seconds=60, instructions=3000000)
c.wait_mark("moved", timeout=10)
where(c, "after one move step")
log("  window_list: %s" % c.windows())
c.resume(seconds=6)
where(c, "after a further resume")
c.shot("/tmp/kq5_after_move.png")
log("  shot -> /tmp/kq5_after_move.png")
