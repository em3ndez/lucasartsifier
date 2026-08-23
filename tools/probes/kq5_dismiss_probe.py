# THE PRINT IS WHERE IT STOPS -- so look at the print, and try to end it.
#
# Established by measurement, not by reading: a scripted click reaches SCI and is dispatched
# (proved by clicking the game's own icon bar and reading curIcon), the arm runs and its text
# appears within one virtual second, and then NOTHING happens for 64 further seconds of game
# time -- the pie is still held, the warn bit still clear. Everything the emitted arm does after
# the print is unreached.
#
# So the print is a modal that is not ending. A virtual clock cannot help if it is waiting for
# INPUT rather than for time -- and now that scripted input works, that is testable: put a
# picture on the screen, then try each way a Sierra message box can be dismissed, sampling in
# between.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, nsrect, _ret

PIE, MODE_G, WARN_G = 2, 402, 403

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)
bar = c.gaddr(69)
c.watch_text()
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 0)                                   # OFF: the arm should just eat the pie
c.setg(WARN_G, 0)

box = nsrect(c, ego, log=log)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
use_icon = _ret(c.send(bar, "useIconItem")[1])
cursor = _ret(c.send("?Pie", "cursor")[1])
if not c.send(bar, "curInvIcon")[0]:
    c.cmd("send %s enable %s" % (bar, use_icon))
if cursor:
    c.cmd("send %s cursor %s" % (use_icon, cursor))
c.cmd("send %s curIcon %s" % (bar, use_icon))
c.cmd("send %s curInvIcon ?Pie" % bar)
c.said()

# offer, then four different dismissals, sampling after each
STEPS = [
    ("offer",        "move %d %d" % (cx, cy + 30)),
    (None,           "click %d %d" % (cx, cy)),
    ("printed",      None),
    ("click-mid",    "click 160 100"),
    ("key-return",   "key return"),
    ("key-escape",   "key escape"),
    ("key-space",    "key space"),
]
c.cmd("script clear")
t = 200
sample_tags = []
for tag, step in STEPS:
    if step:
        c.cmd("script add t=+%d %s" % (t, step))
        t += 400
    if tag:
        t += 2500
        c.cmd("script add t=+%d mark %s" % (t, tag))
        c.cmd("script add t=+%d break" % (t + 20))
        sample_tags.append(tag)
        t += 60

for tag in sample_tags:
    c.resume(seconds=60, instructions=3000000)
    try:
        at = c.wait_mark(tag, timeout=5)
    except Exception as e:                                  # noqa: BLE001
        log("  %-11s NO MARK: %s" % (tag, e))
        break
    has = c.send(ego, "has", PIE)[0]
    warn = c.gint(WARN_G)
    said = c.said()
    log("  %-11s t=%-6d has_pie=%s warn=%#06x  said=%s" % (tag, at, has, warn, said if said else ""))
    if tag == "printed":
        c.shot("/tmp/shot_print.png")
        log("               shot: /tmp/shot_print.png")
        # ⭐ The `break` step gives a prompt WHILE the dialog is on screen, which is the one
        # moment a backtrace can say what the print is actually waiting on. The cursor is an
        # hourglass, so it is not waiting for a click.
        log("               --- backtrace inside the print ---")
        for line in c.cmd("bt").splitlines():
            log("               %s" % line)
        log("               --- what the audio thinks ---")
        for probe in ("vv g 90", "vv g 91", "vv g 92"):
            log("               %s -> %s" % (probe, c.cmd(probe).strip()))
    if has == 0:
        log("\n=== the arm completed after '%s' ===" % tag)
        break
else:
    log("\n=== no dismissal let the arm finish ===")
