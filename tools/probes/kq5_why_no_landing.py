# Four rows do not land: rm030's branch, rm034's eagle, tailorShop's tailor, rm046's hermit.
# `proc255_5` is a plain bounding-box test, so the aim is not the suspect -- and the bakery, the
# dog and the toymaker all take the same click at the same kind of target. So something upstream
# of the handler is eating these events, and there are only a few candidates in `User:handleEvent`:
#
#     (if (and (== (param1 type:) 16384) input)          <- canInput OFF drops every click
#         (cond
#           ((and (== (param1 message:) 1) controls (alterEgo handleEvent: param1)) 1)
#           (global34                                    <- ONE object gets it: the lowest on
#              (OnMeAndLowY init:)                          screen whose `onMe:` is true, which
#              (global5 eachElementDo: #perform OnMeAndLowY param1)   is NOT the same test as
#              (global32 eachElementDo: #perform OnMeAndLowY param1)  proc255_5
#              (if (OnMeAndLowY theObj:) ((OnMeAndLowY theObj:) handleEvent: param1)))
#           ((global5 handleEvent: param1) 1)
#           ((global32 handleEvent: param1) 1)))
#
# So this reports, for each failing room: whether input is on, whether global34 routes to a single
# object, which object `OnMeAndLowY` would pick for our exact aim, and where the ego is standing.
# Then it clicks and says what happened. One click, four rooms, no guesses.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, here, nsrect, offer_script, settle_room, PARK

CASES = [(30, "branch", 20, "Rope"), (34, "eagle", 2, "Pie"),
         (203, "tailor", 9, "Heart"), (46, "hermit_a", 23, "Shell")]

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()
user = c.gaddr(80)

for room, owner, item_no, item in CASES:
    log("\n===== room %s, target %s =====" % (room, owner))
    try:
        goto(c, room, force=True, log=log)
    except Exception as e:                                  # noqa: BLE001
        log("  goto failed: %s" % e)
        continue
    c.cmd("send %s get %d" % (ego, item_no))
    log("  here=%s  global2 script=%s  global34=%s"
        % (here(c), c.send(c.gaddr(2), "script")[0], c.gint(34)))
    log("  User canInput=%s canControl=%s"
        % (c.send(user, "canInput")[0], c.send(user, "canControl")[0]))
    log("  ego posn=(%s,%s)  ego nsRect=%s"
        % (c.send(ego, "x")[0], c.send(ego, "y")[0], nsrect(c, ego, tries=1, log=log)))
    try:
        box = nsrect(c, "?" + owner, log=log)
    except Exception as e:                                  # noqa: BLE001
        log("  %s: %s" % (owner, e))
        continue
    cx = (box["nsLeft"] + box["nsRight"]) // 2
    cy = (box["nsTop"] + box["nsBottom"]) // 2
    log("  %s box=%s  aim=(%d,%d)" % (owner, box, cx, cy))
    # ⭐ Ask the game itself who owns that point, with its OWN test -- `OnMeAndLowY` is what
    # routes a click when global34 is set, and `onMe:` is not `proc255_5`.
    ev = "?uEvt"
    c.cmd("send %s type 16384" % ev)
    c.cmd("send %s message 4" % ev)
    c.cmd("send %s x %d" % (ev, cx))
    c.cmd("send %s y %d" % (ev, cy))
    c.cmd("send %s claimed 0" % ev)
    c.cmd("send ?OnMeAndLowY init")
    c.cmd("send %s eachElementDo perform ?OnMeAndLowY %s" % (c.gaddr(5), ev))
    c.cmd("send %s eachElementDo perform ?OnMeAndLowY %s" % (c.gaddr(32), ev))
    who, out = c.send("?OnMeAndLowY", "theObj")
    log("  OnMeAndLowY would route that point to: %s" % (who if who else out.strip()[-90:]))
    log("  %s onMe: %s" % (owner, c.send("?" + owner, "onMe", ev)[0]))
    c.cmd("send %s type 0" % ev)                            # ⛔ never leave a live synthetic event

    said, at, aim = offer_script(c, "?" + owner, item, "x%d" % room, log=log)
    log("  -> %d box(es); said=%s" % (aim["boxes"], said))
