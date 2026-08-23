# LA6 from KQ5-LITE-TESTPLAN, driven end to end by SCRIPTED CLICKS -- no person at the keyboard.
#
#   ☐ LA6 | 403 $0001 | anywhere | EAT the Pie (2) | warned, then the pie is actually eaten
#
# THE ARM, read from the emitted patch source (build/kq5_patch_guardpicker/.../Main.sc), because
# every rule below is derived from it rather than guessed:
#
#     (2  (proc0_9 16)
#         (proc0_29 141)                                   ; BOX 1 -- "Mmmmmmm! ...eaten!"
#         (if <allow>
#             (if (== global402 1) (proc255_0 {You have been warned!}))   ; BOX 2, lite only
#             (global0 put: 2 1))                          ; the pie is consumed
#         (param1 claimed: 1)
#         (if (not <allow>)
#             (proc255_0 {Just kidding! You hold on to it because you still need it.})  ; BOX 2
#             (|= global403 $0001)))                       ; the warn bit
#
#     <allow> = (or (== global402 2) (and (== global402 1) (& global403 $0001)))
#
# ⭐ So the MODE ENCODING is 0=Full, 1=Lite, 2=Off -- read off `<allow>`, not assumed. A run that
# used 0 for "off" measured the Full guard and reported its own control as a failure.
#
# ⛔ THREE THINGS ABOUT THE MESSAGE BOXES, each one measured and each one able to fake a guard
# result on its own (tools/probes/kq5_whatdismisses.py, and a backtrace taken from inside a box):
#
#   1. A box is `Dialog::doit` polling kGetEvent -- it waits for INPUT, not for time. No amount
#      of clock control ends it, which is why "the game clock does not advance" was the wrong
#      diagnosis for a whole session. Everything after it in the arm is unreached until it goes.
#   2. RETURN or a mouse click ends a box. SPACE does not.
#   3. THE COUNT MATTERS. Box 1 always plays; a second box plays whenever the guard has something
#      to say (Full and both Lite paths), and Off raises only one. One dismissal too FEW leaves
#      the arm parked and its effects land in the next attempt's window -- which reads exactly
#      like a guard that did not fire. One too MANY starts a fresh offer, because the item is
#      still on the cursor -- which reads like a guard that fired twice.
#
# Dismiss with RETURN, not a click: a dismissing click would also be an offer wherever it lands.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --binary /tmp/scummvm-playtest-build/scummvm --input-script tools/probes/idle.script \
#       --script tools/probes/kq5_eat_pie_scripted.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, offer_script

PIE, BIT, MODE_G, WARN_G = 2, 0x0001, 402, 403
FULL, LITE, OFF = 0, 1, 2
EATEN = "best custard pie"
REFUSE = "Just kidding!"
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()

def attempt(tag, boxes):
    said, at, _aim = offer_script(c, ego, "Pie", tag, boxes=boxes, log=lambda *a: None)
    return said, at

def show(name, want_has, want_msg, said, at):
    warn, has = c.gint(WARN_G), c.send(ego, "has", PIE)[0]
    state_ok = has == want_has
    text_ok = any(want_msg in s for s in said)
    log("  %-22s t=%-6d warn=%#06x has_pie=%s (want %d) -> %s"
        % (name, at, warn, has, want_has, "OK" if state_ok else "WRONG"))
    log("      said %s" % (said,))
    log("      looking for %-24r -> %s" % (want_msg, "OK" if text_ok else "MISSING"))
    return state_ok, text_ok

rows = []

log("\n== the CONTROL: mode Off (2) -- one box, and the pie is simply eaten ==")
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, OFF)
c.setg(WARN_G, 0)
said, at = attempt("ctl", boxes=1)
control = show("control (Off)", 0, EATEN, said, at)

log("\n== LA6: mode Lite (1) -- refuse and keep, then warn and spend ==")
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, LITE)
c.setg(WARN_G, 0)
said, at = attempt("a1", boxes=2)
rows.append(show("attempt 1 (refuse)", 1, REFUSE, said, at))
said, at = attempt("a2", boxes=2)
rows.append(show("attempt 2 (warn+spend)", 0, WARNED, said, at))

log("\n=== control (Off, pie eaten):  %s ===" % ("PASS" if all(control) else "FAIL"))
log("=== LA6 state contract:        %s ===" % ("PASS" if all(s for s, _t in rows) else "FAIL"))
log("=== LA6 text contract:         %s ===" % ("PASS" if all(t for _s, t in rows) else "FAIL"))
