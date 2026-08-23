# THE CONTROL THAT SEPARATES THE TWO REMAINING FAILURES.
#
# The eagle (rm034) and the tailor (tailorShop) take a scripted click on the exact centre of the
# box `proc255_5` tests, and nothing at all comes back -- no box, no text, no bit. That reads as
# "the guard did not fire", but it is equally consistent with "the click never reached the
# object". Aim is already ruled out (`onMe:` answers 1 for the very point being clicked) and so
# is motion (the click now goes in 150ms of game time after the box is read).
#
# ⭐ Every one of these handlers has a LOOK arm that does nothing but print:
#
#     (instance eagle ...  (switch (param1 message:) (2 (proc0_29 456) (param1 claimed: 1)) ...
#     (instance tailor ... (switch (param1 message:) (2 (if (global0 has: 26) (proc0_29 824) ...
#
# and which verb a click carries is only which icon is current -- `IconBar:handleEvent` rewrites
# a mouse-down as `type: (curIcon type:) message: (curIcon message:)`. So arming the LOOK icon
# and clicking the SAME point asks one question with one variable:
#
#     a box comes back  -> the click reaches the object; the answer is inside its message-4 arm
#     nothing           -> the click never gets there at all, and no offer ever could
#
# The bakery is the positive control: the baker's look arm must answer.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import (arm_icon, arm_item, boot, drain_boxes, goto, icons, nsrect,
                  park_mouse, resolve)

CASES = [(206, "baker", 11, "Gold_Coin"), (34, "eagle", 2, "Pie"),
         (203, "tailor", 9, "Heart")]

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()
log("icon bar: %s" % [(i, m) for i, _, m in icons(c)])


def click_at(c, cx, cy, tag, delay=150, settle=2500):
    c.said()
    c.cmd("script clear")
    c.cmd("script add t=+%d click %d %d" % (delay, cx, cy))
    c.cmd("script add t=+%d mark %s" % (delay + settle, tag))
    c.cmd("script add t=+%d break" % (delay + settle + 100))
    c.resume(seconds=60, instructions=3000000)
    c.wait_mark(tag, timeout=10)
    said = c.said()
    more, n = drain_boxes(c, tag, log=log)
    return said + more, n


for room, owner, item_no, item in CASES:
    log("\n===== room %s, %s =====" % (room, owner))
    goto(c, room, force=True, log=log)
    obj = resolve(c, owner, None if room in (34, 203, 206) else room, log=log)
    c.cmd("send %s get %d" % (ego, item_no))

    for verb, arm in (("LOOK (message 2)", lambda: arm_icon(c, 2, log=log)),
                      ("USE  (message 4)", lambda: arm_item(c, item, log=log))):
        arm()
        park_mouse(c, log=lambda *a: None)
        box = nsrect(c, obj, log=log)
        cx = (box["nsLeft"] + box["nsRight"]) // 2
        cy = (box["nsTop"] + box["nsBottom"]) // 2
        said, n = click_at(c, cx, cy, "%s%s%s" % (room, verb[0], owner[0]))
        log("  %s at (%d,%d) -> %d box(es)  said=%s" % (verb, cx, cy, n, said))
