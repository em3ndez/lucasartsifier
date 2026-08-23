# LB3-shaped row: the BAKER and the Gold_Coin (bakeShop, g403 $0008), driven by scripted clicks.
#
# WHY THIS ROW NEXT, and not another market one: it is the DOMINANT arm shape, and LA6 is the
# odd one out. LA6 wraps only the DISPOSAL, so the action's own message plays first and the
# guard's second -- two boxes. Every other emitted site wraps the WHOLE action:
#
#     (if (not (global0 has: 11))
#         <the original action>                              ; guard not involved
#      else
#         (if <allow>
#             (if (== global402 1) (proc255_0 {You have been warned!}))
#             <the original action>
#          else
#             (proc255_0 {Better not. You are going to need that.})
#             (|= global403 $0008)))
#
# So the DENY path should raise exactly ONE box, not two, and the ALLOW path one plus whatever
# the original action prints. If that holds, the box count is derivable per site from the emitted
# arm and the remaining rows are mechanical.
#
# ⛔ The baker's `getPie` runs as a SCRIPT, so the coin leaves the inventory asynchronously --
# poll for it rather than sampling once.
#
# ⛔⛔ AND THE ARM HAS PRECONDITIONS THE TEST PLAN DOES NOT MENTION. In the emitted source the
# guard is not at the top of `baker:handleEvent` -- it is buried under a message test and two
# `cond`s, every one of which can make a perfectly good offer do nothing at all:
#
#     (method (handleEvent param1 ...)
#       (if (or (param1 claimed:) (not (== (param1 type:) 16384)) (not (proc255_5 self param1)))
#           (return)
#        else
#         (switch (param1 message:)
#           ...
#           (4                                                   ; <- USE, not Talk (5)
#             (cond
#               ((== (global9 indexOf: (global69 curInvIcon:)) 28) (param1 claimed: 0))
#               ((not (global2 script:))                         ; <- the ROOM must be IDLE
#                 (cond
#                   ((== ((global9 at: 2) owner:) 206)           ; <- the PIE must still be the shop's
#                     (switch (global9 indexOf: (global69 curInvIcon:))
#                       (11  ...the Gold_Coin guard...)))))))))
#
# So a row is not "click the item on the NPC". It is: the right MESSAGE, an IDLE room, and a
# world state that satisfies the enclosing conds. This probe checks each one before it clicks and
# says which is missing, because all three failure modes look identical from outside -- and look
# identical to a guard that did not fire.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --binary /tmp/scummvm-playtest-build/scummvm --input-script tools/probes/idle.script \
#       --script tools/probes/kq5_bakeshop_row.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, offer_script

COIN, BIT, MODE_G, WARN_G = 11, 0x0008, 402, 403
BAKERY = 206                                    # a REAL room -- the shops next door are Regions
FULL, LITE, OFF = 0, 1, 2
REFUSE = "Better not."
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log, teleport=True)
goto(c, BAKERY, log=log)
ego = c.gaddr(0)
c.watch_text()

def state():
    return c.gint(MODE_G), c.gint(WARN_G), c.send(ego, "has", COIN)[0]

def preconditions():
    """The enclosing conds of the emitted arm, read back from the live VM.

    ⛔ `send` takes an ADDRESS, not an expression: `send (global9 at: 2) owner` reads back None,
    and a check that treats None as "the cond is false" invents a finding. `(global9 at: 2)` is
    item 2, which is the Pie, so ask the object by name instead."""
    bar = c.gaddr(69)
    owner, out = c.send("?Pie", "owner")
    if owner is None:
        log("  ⚠️ could not read ?Pie owner: -- %s" % out.strip().splitlines()[-1:])
    return {
        "room_idle": c.send(c.gaddr(2), "script")[0] == 0,     # (not (global2 script:))
        "pie_owner": owner,                                    # must be 206
        "curInvIcon": c.send(bar, "curInvIcon")[0],
        "curIcon": c.send(bar, "curIcon")[0],
    }

log("\n== preconditions the emitted arm sits under ==")
pre = preconditions()
for k, v in sorted(pre.items()):
    log("  %-11s = %s" % (k, v))
if not pre["room_idle"]:
    log("  ⛔ the room is running a script -- the message-4 cond is SKIPPED, so no offer can land")
if pre["pie_owner"] is None:
    log("  ⚠️ the Pie's owner could not be read -- this check says NOTHING either way")
elif pre["pie_owner"] != 206:
    log("  ⛔ the Pie's owner is %s, not 206 -- the cond that guards this switch is FALSE, so no"
        % pre["pie_owner"])
    log("     offer of any item can reach the guard until Graham stops owning the shop's pie")

log("\n== deny path: Lite, bit clear -- predicted ONE box ==")
c.cmd("send %s get %d" % (ego, COIN))
c.setg(MODE_G, LITE)
c.setg(WARN_G, 0)
log("  before: mode=%d warn=%#06x has_coin=%s" % state())
said, at, aim = offer_script(c, "?baker", "Gold_Coin", "d1", boxes=1, log=log)
mode, warn, has = state()
log("  after : warn=%#06x has_coin=%s (t=%d)" % (warn, has, at))
log("  said  : %s" % (said,))
# ⛔ SEPARATE THE TWO FAILURES. An offer that never reached the handler looks exactly like a
# guard that did not fire, and calling the first the second is how a working guard gets reported
# broken. The guard's own sentence is the witness that the handler ran at all.
landed = any(REFUSE in s or WARNED in s for s in said) or bool(warn & BIT)
if not landed:
    log("  ⛔ THE OFFER NEVER LANDED -- no guard sentence, no bit. This says nothing about the")
    log("     guard. aimed %s; box before %s, after %s" % (aim["aimed"], aim["box_before"], aim["box_after"]))
deny_ok = landed and bool(warn & BIT) and has == 1 and any(REFUSE in s for s in said)
log("  == DENY %s == (want bit set, coin KEPT, %r)"
    % ("PASS" if deny_ok else ("NOT REACHED" if not landed else "FAIL"), REFUSE))

log("\n== allow path: Lite, bit now set -- ONE box, then the coin goes ==")
said, at, aim = offer_script(c, "?baker", "Gold_Coin", "a1", boxes=1, log=log)
mode, warn, has = state()
log("  after : warn=%#06x has_coin=%s (t=%d)" % (warn, has, at))
log("  said  : %s" % (said,))
if has:
    # getPie is a Script: the coin leaves asynchronously, so give the game more time rather than
    # calling this a failure on one sample.
    c.cmd("script clear")
    c.cmd("script add t=+8000 mark settle")
    c.cmd("script add t=+8100 break")
    c.resume(seconds=60, instructions=3000000)
    c.wait_mark("settle", timeout=5)
    has = c.send(ego, "has", COIN)[0]
    log("  after a further 8s of game time: has_coin=%s  said=%s" % (has, c.said()))
allow_ok = has == 0 and any(WARNED in s for s in said)
log("  == ALLOW %s == (want coin GONE, %r)" % ("PASS" if allow_ok else "FAIL", WARNED))

log("\n=== bakeShop $0008 (baker / Gold_Coin): %s ==="
    % ("PASS" if deny_ok and allow_ok else "FAIL"))
log("=== the one-box prediction for the wrap-the-whole-action shape: %s ==="
    % ("HOLDS" if deny_ok else
       ("UNTESTED -- the offer never reached the handler" if not landed else "DOES NOT HOLD")))
