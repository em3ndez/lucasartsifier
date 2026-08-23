# WHEN does the arm finish? One click, then sample repeatedly at known points in GAME time.
#
# The scripted click reaches the handler -- the arm's print turns up -- but by the time the probe
# samples 4 virtual seconds later, nothing has changed, and the print itself only appears in a
# LATER window. That is either (a) the arm needs more game time than it was given, or (b) it is
# waiting on something a virtual clock does not drive. The two look identical from one sample.
#
# So: take many. `break` hands the console back at a stated virtual time, the pending steps stay
# pending, and resuming carries on -- so a script of breaks is a time series through one
# interaction.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --binary /tmp/scummvm-playtest-build/scummvm --input-script tools/probes/idle.script \
#       --script tools/probes/kq5_arm_timeline.py
# Env: KQ5_CLOCK=<ms per getMillis query, default the build's 10>
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, nsrect, _ret

PIE, MODE_G, WARN_G = 2, 402, 403
SAMPLES = [1000, 2000, 4000, 8000, 16000, 32000, 64000]

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 0)                                   # OFF: the arm should just eat the pie
c.setg(WARN_G, 0)

clock = os.environ.get("KQ5_CLOCK")
if clock:
    c.cmd("script clock %s" % clock)
log("clock: %s" % c.cmd("script").splitlines()[0])

box = nsrect(c, ego, log=log)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
bar = c.gaddr(69)
use_icon = _ret(c.send(bar, "useIconItem")[1])
cursor = _ret(c.send("?Pie", "cursor")[1])
if not c.send(bar, "curInvIcon")[0]:
    c.cmd("send %s enable %s" % (bar, use_icon))
if cursor:
    c.cmd("send %s cursor %s" % (use_icon, cursor))
c.cmd("send %s curIcon %s" % (bar, use_icon))
c.cmd("send %s curInvIcon ?Pie" % bar)
c.said()

c.cmd("script clear")
# ⛔ MOVE FIRST, to somewhere else. In the run that produced no print at all, the script's only
# pointer step was a move to the click point itself -- the cursor was already sitting elsewhere
# and the icon bar was showing. The icon-bar control that proved clicks DO reach SCI moved the
# pointer to the top first and then clicked, i.e. it moved between two DIFFERENT places. Until
# that difference is ruled out it is a variable, so hold it fixed the way the working case had
# it.
c.cmd("script add t=+200 move %d %d" % (cx, cy + 30))
c.cmd("script add t=+800 click %d %d" % (cx, cy))
for ms in SAMPLES:
    c.cmd("script add t=+%d mark s%d" % (800 + ms, ms))
    c.cmd("script add t=+%d break" % (800 + ms + 20))
log("move, then click (%d,%d); sampling at +%s ms of game time" % (cx, cy, SAMPLES))

# ⭐ Sample the STATE THE CLICK DEPENDS ON, not only the outcome. `has_pie` alone cannot tell
# "the arm ran and stopped" from "the click never became an offer" -- and the icon bar is the
# obvious suspect, because curIcon/curInvIcon are poked from the console at a prompt and the
# game's own User:doit runs every cycle once we resume.
def snap():
    return dict(x=c.send(ego, "x")[0], y=c.send(ego, "y")[0],
                curIcon=_ret(c.send(bar, "curIcon")[1]),
                curInv=_ret(c.send(bar, "curInvIcon")[1]),
                has=c.send(ego, "has", PIE)[0])

log("  before  %s" % snap())
for ms in SAMPLES:
    c.resume(seconds=60, instructions=4000000)
    try:
        at = c.wait_mark("s%d" % ms, timeout=5)
    except Exception as e:                                  # noqa: BLE001
        log("  +%-6d NO MARK: %s" % (ms, e))
        break
    st = snap()
    has = st["has"]
    said = c.said()
    log("  +%-6d (t=%d) %s  said=%s" % (ms, at, st, said if said else ""))
    if has == 0:
        log("\n=== the arm completed by +%d ms of game time ===" % ms)
        break
else:
    log("\n=== the arm never completed, out to +%d ms of game time ===" % SAMPLES[-1])
