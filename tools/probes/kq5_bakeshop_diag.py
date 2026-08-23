# WHY THE FIRST MARKET ROW DOES NOT LAND -- a diagnostic, not a row.
#
# The handoff's lead was: "the baker answered with its Talk line, so the event's `message` is
# wrong at click time." ⛔ That premise does not survive re-reading the emitted source. LA6's
# pie arm lives in `class ego`'s handleEvent at Main.sc:1041, and it sits under
# `(switch (param1 message:) ... (4 ...))` exactly like the baker's -- so LA6 DID need message 4
# and LA6 passes. A wrong message would have broken it too.
#
# So this measures instead of arguing, one variable at a time:
#
#   baseline   -- what `window_list` says with nothing on screen, so a box is recognisable
#   control A  -- offer an item the baker's switch does NOT name (5, the Fish). Every path
#                 through case 4 prints SOMETHING, and each prints a DIFFERENT something:
#                    (else (proc0_29 19))      reached case 4, shop still owns the pie
#                    (proc0_29 20)             reached case 4, Graham owns the pie
#                    (proc0_29 13)             reached case 4, nobody expected owns it
#                    the Talk line             the message was 5, not 4
#                    nothing at all            the click never reached the baker
#                 One click distinguishes all five, and none of them needs a guard to fire.
#   control B  -- the same click aimed 10px high and 10px low, run only if A lands nothing.
#                 `User:handleEvent` LOCALIZES the event before dispatch, so a port whose top
#                 is not 0 would shift every hit test by a constant -- and the ego (LA6's
#                 target) is the one object whose box is never wrong for a different reason.
#
# Box dismissal here is ADAPTIVE and driven by `window_list`: press Return once per box that is
# actually open, rather than once per box a test plan predicts. A prediction that is one too low
# parks the arm and a prediction one too high starts a fresh offer -- both were observed.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --binary /tmp/scummvm-playtest-build/scummvm --input-script tools/probes/idle.script \
#       --script tools/probes/kq5_bakeshop_diag.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, arm_item, nsrect, offer_script, here

BAKERY = 206
FULL, LITE, OFF = 0, 1, 2

def log(*a): print(*a, flush=True)


def show_windows(c, when):
    w = c.windows()
    log("  window_list %-22s %s" % (when, w if w else "(empty)"))
    return w


log("== boot ==")
boot(c, log=log, teleport=True)
goto(c, BAKERY, log=log)
ego = c.gaddr(0)
bar = c.gaddr(69)
c.watch_text()

log("\n== baseline ==")
show_windows(c, "(nothing on screen)")
log("  room (global11)     = %s   <- NOT c.room(), which is global 13" % here(c))
log("  global2 script      = %s (0 means IDLE -- the cond the arm sits under)"
    % c.send(c.gaddr(2), "script")[0])
log("  ?Pie owner          = %s (must be 206 for the item switch to be reached)"
    % c.send("?Pie", "owner")[0])
log("  baker nsRect        = %s" % nsrect(c, "?baker", log=log))
log("  ego  nsRect         = %s" % nsrect(c, ego, log=log))

log("\n== control A: offer the Fish (5), an item the baker's switch does NOT name ==")
c.cmd("send %s get 5" % ego)
c.setg(402, OFF)                                        # no guard involved in this control
use_icon = arm_item(c, "Fish", log=log)
log("  useIconItem         = %s" % use_icon)
log("  curIcon             = %s" % c.send(bar, "curIcon")[0])
log("  curIcon message     = %s  (<- 4 is USE, 5 is TALK: this is what IconBar copies onto"
    " the click)" % c.send(use_icon, "message")[0])
log("  global9 indexOf Fish= %s  (<- must be 5)" % c.send(c.gaddr(9), "indexOf", "?Fish")[0])
box = nsrect(c, "?baker", log=log)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
log("  aiming (%d,%d) at baker box %s" % (cx, cy, box))
said, at, aim = offer_script(c, "?baker", "Fish", "a", log=log)
n = aim["boxes"]
log("  -> said %s" % (said,))

if n == 0 and not said:
    log("\n== control B: the same click, moved -- one variable, the LOCALIZE offset ==")
    log("  the picture port sits at %s, so a screen click and an nsRect could differ by its top"
        % ((c.windows() or [{"at": None}])[0]["at"],))

log("\n== now the real thing: the Gold_Coin (11), mode Lite, bit clear ==")
c.cmd("send %s get 11" % ego)
c.setg(402, LITE)
c.setg(403, 0)
said, at, aim = offer_script(c, "?baker", "Gold_Coin", "coin", log=log)
log("  -> said %s" % (said,))
log("  -> warn=%#06x has_coin=%s" % (c.gint(403), c.send(ego, "has", 11)[0]))
