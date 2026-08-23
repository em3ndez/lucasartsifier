# ⛔ THE AIM HAS BEEN OFF BY THE PORT'S ORIGIN ALL ALONG, and only short targets showed it.
#
# `window_list` says KQ5's picture window sits `at 0, 10`. `User:handleEvent` calls
# `(param1 localize:)` before handing the event to anything, which subtracts the current port's
# origin -- so a click authored at SCREEN y arrives at the handlers as PORT y - 10, while an
# object's nsRect is already in port coordinates. Aiming at the middle of an nsRect therefore
# tests a point 10 pixels ABOVE the intended one:
#
#   baker   box y 63..89  (26 tall)   centre 76  -> tested at 66   still inside   -> row passed
#   tailor  box y 98..143 (45 tall)   centre 120 -> tested at 110  still inside   -> row passed
#   eagle   box y 121..138 (17 tall)  centre 129 -> tested at 119  OUTSIDE by 2   -> nothing
#
# That is why every failure so far has been a SHORT target, and why a LOOK click at the eagle
# produced nothing either: the click was landing above him.
#
# ONE VARIABLE: the same click, plus the port's own top. If the eagle answers at cy+10 and not at
# cy, the offset is the whole story.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import (arm_icon, boot, drain_boxes, goto, nsrect, park_mouse, resolve)

CASES = [(34, "eagle"), (203, "tailor"), (206, "baker")]

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
c.watch_text()


def click_at(c, cx, cy, tag, delay=150, settle=2500):
    c.said()
    c.cmd("script clear")
    c.cmd("script add t=+%d click %d %d" % (delay, cx, cy))
    c.cmd("script add t=+%d mark %s" % (delay + settle, tag))
    c.cmd("script add t=+%d break" % (delay + settle + 100))
    c.resume(seconds=60, instructions=3000000)
    c.wait_mark(tag, timeout=10)
    said = c.said()
    more, n = drain_boxes(c, tag, log=lambda *a: None)
    return said + more, n


for room, owner in CASES:
    log("\n===== room %s, %s =====" % (room, owner))
    goto(c, room, force=True, log=log)
    port = (c.windows() or [{"at": (0, 0)}])[0]["at"]
    log("  picture window sits at %s" % (port,))
    obj = resolve(c, owner, None, log=log)
    for dy in (0, port[1]):
        arm_icon(c, 2, log=lambda *a: None)          # LOOK: it only prints, it changes nothing
        park_mouse(c, log=lambda *a: None)
        box = nsrect(c, obj, log=log)
        cx = (box["nsLeft"] + box["nsRight"]) // 2
        cy = (box["nsTop"] + box["nsBottom"]) // 2
        said, n = click_at(c, cx + port[0], cy + dy, "p%s%s%d" % (room, owner[0], dy))
        log("  LOOK at (%d,%d)  [nsRect centre %+d]  -> %d box(es)  said=%s"
            % (cx + port[0], cy + dy, dy, n, [s[:60] for s in said]))
