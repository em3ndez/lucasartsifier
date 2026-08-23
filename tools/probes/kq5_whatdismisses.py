# WHAT DISMISSES THE MESSAGE BOX? One offer, then one candidate at a time, sampling in between.
#
# The box is `Dialog::doit` polling kGetEvent (backtrace taken from inside it), so SOME event
# ends it -- and the arm's remaining statements run when it does. Which event is the whole
# question, because a probe that dismisses with the wrong thing reads a guard that "did not
# fire".
#
# LITE mode, and the signal is the WARN BIT: unlike has_pie it is not reset between attempts and
# nothing else in the run touches it. warn flipping to 0x0001 means the arm's tail ran, i.e. the
# box that was in its way is gone.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, nsrect, _ret

PIE, BIT, MODE_G, WARN_G = 2, 0x0001, 402, 403

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)
bar = c.gaddr(69)
c.watch_text()
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 1)                                   # LITE: the first offer must refuse
c.setg(WARN_G, 0)

use_icon = _ret(c.send(bar, "useIconItem")[1])
cursor = _ret(c.send("?Pie", "cursor")[1])
if not c.send(bar, "curInvIcon")[0]:
    c.cmd("send %s enable %s" % (bar, use_icon))
if cursor:
    c.cmd("send %s cursor %s" % (use_icon, cursor))
c.cmd("send %s curIcon %s" % (bar, use_icon))
c.cmd("send %s curInvIcon ?Pie" % bar)
box = nsrect(c, ego, log=lambda *a: None)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
c.said()

# One offer, then each candidate dismissal in turn, with a sample between every pair.
CANDIDATES = [
    ("offer",   ["move %d %d" % (cx, cy + 30), "click %d %d" % (cx, cy)]),
    ("space",   ["key space"]),
    ("return",  ["key return"]),
    ("move",    ["move 30 30"]),
    ("clickfar",["click 300 180"]),
]
c.cmd("script clear")
t = 200
tags = []
for tag, steps in CANDIDATES:
    for st in steps:
        c.cmd("script add t=+%d %s" % (t, st))
        t += 500
    t += 2000
    c.cmd("script add t=+%d mark %s" % (t, tag))
    c.cmd("script add t=+%d break" % (t + 20))
    tags.append(tag)
    t += 60

log("  warn before: %#06x" % c.gint(WARN_G))
for tag in tags:
    c.resume(seconds=60, instructions=3000000)
    try:
        at = c.wait_mark(tag, timeout=5)
    except Exception as e:                                  # noqa: BLE001
        log("  %-9s NO MARK: %s" % (tag, e))
        break
    warn, has, said = c.gint(WARN_G), c.send(ego, "has", PIE)[0], c.said()
    log("  after %-9s t=%-6d warn=%#06x has_pie=%s  said=%s" % (tag, at, warn, has, said))
    if warn & BIT:
        log("\n=== the arm's tail ran after: %s ===" % tag)
        break
else:
    log("\n=== nothing tried let the arm's tail run ===")
