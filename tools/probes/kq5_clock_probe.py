# WHERE DOES THE PRINT ACTUALLY STOP? Run the control before believing any story about it.
#
# `send <obj> handleEvent <ev>` over the pipe never returns once the arm PRINTS. The last
# session's diagnosis was "the game clock does not advance while the debugger holds stdin". With
# a virtual clock that the ENGINE drives, that diagnosis predicts the hang goes away. It did not:
# the run still never came back.
#
# Marks alone cannot say why, because a mark only prints from the event poll -- a frozen clock
# and an engine that has stopped polling events look identical from outside. `script trace`
# prints the clock from processMillis instead, which separates them:
#
#     clock line ADVANCING, no marks   -> time runs; the engine is not polling events
#     no clock line at all             -> the clock itself is frozen; nothing is running
#
# A countdown armed before the send gets us a prompt mid-hang, and with a prompt `bt` works.
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, game_event, nsrect

PIE, MODE_G, WARN_G = 2, 402, 403

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)

ego = c.gaddr(0)
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 0)                                  # OFF: no guard is in the way
c.setg(WARN_G, 0)
log("mode=%d warn=%#06x has_pie=%s" % (c.gint(MODE_G), c.gint(WARN_G),
                                       c.send(ego, "has", PIE)[0]))
log("script state: %s" % c.cmd("script").strip())
c.cmd("script trace 500")

ev = game_event(c)
box = nsrect(c, ego, log=log)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
for f, v in (("type", 16384), ("message", 4), ("x", cx), ("y", cy), ("claimed", 0)):
    c.cmd("send %s %s %s" % (ev, f, v))
c.cmd("send %s curInvIcon ?Pie" % c.gaddr(69))

# ⛔ Arm the countdown BEFORE the send. Once the arm prints, the debugger is not at a prompt and
# nothing we type can reach it; the countdown is decremented in the opcode loop, including inside
# `cmdSend`'s re-entrant run_vm, so it is the only way back in.
log("\n== arm a countdown, then send ==")
c.cmd("debug_countdown 400000")
c._read_new()
c._write("send %s handleEvent %s" % (ego, ev))
t0 = time.time()
try:
    out = c._await_prompt(timeout=60, dismiss=False)
    log("  back at a prompt after %.1fs" % (time.time() - t0))
    log("  %s" % out.strip().replace("\n", "\n  "))
    log("\n== backtrace ==")
    log(c.cmd("bt"))
    log("script state: %s" % c.cmd("script").strip())
    log("has_pie=%s claimed=%s" % (c.send(ego, "has", PIE)[0], c.send(ev, "claimed")[0]))
except Exception as e:                                     # noqa: BLE001
    log("  no prompt after %.1fs: %s" % (time.time() - t0, e))
