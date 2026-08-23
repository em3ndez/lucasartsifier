# ⛔ ONE CLICK AT THE TOYMAKER BOTH REFUSES AND SELLS. Seen in the Lite suite:
#
#   DENY : boxes=2 bit=True has=0 text=True
#          said=['Better not. You are going to need that.', 'You have been warned!']
#
# The first offer raised the refusal AND the warning AND spent the coin, in one attempt. At the
# bakery the same guard raises exactly one box and keeps the item, so this is not the harness.
#
# THE READING TO TEST. `wrap_forbidden_case` emits
#
#     (if (not (global0 has: 11))
#         <the original action, which ends (param1 claimed: 1)>
#      else
#         (if <allow>
#             (if (== global402 1) (proc255_0 {You have been warned!}))
#             <the original action, which ends (param1 claimed: 1)>
#          else
#             (proc255_0 {Better not. You are going to need that.})
#             (|= global403 $0010)))          ; <- NO (param1 claimed: 1)
#
# so the DENY path leaves the event UNCLAIMED. And the toy shop has four Props sitting on top of
# the toymaker that forward to him verbatim:
#
#     (instance rArm of Prop    ... (method (handleEvent param1) (toyMaker handleEvent: param1)))
#     (instance theMouth ...     same)   (instance lArm ... same)   (instance toyHead ... same)
#
# `User:handleEvent` keeps walking the cast while the event is unclaimed, so the second Prop
# hands the SAME click to `toyMaker:handleEvent` again -- by which time the refusal's own
# `(|= global403 $0010)` has run, `<allow>` is true, and the toymaker takes the coin. The player
# never gets the second click the Lite contract promises them.
#
# ⛔ TWO READINGS FIT THAT TRACE AND ONLY A CONTROL SEPARATES THEM. The other is that the RETURN
# which dismisses the box is itself re-dispatched as a fresh offer -- `IconBar:handleEvent`
# rewrites a Return into `type: (curIcon type:) message: (curIcon message:)`, and the item is
# still on the cursor.
#
# ⭐ MODE FULL (global402 = 0) SEPARATES THEM. In Full, `<allow>` is
# `(or (== global402 2) (and (== global402 1) (& global403 $0010)))` -- false whatever the bit
# does, so EVERY pass denies. Then:
#   * two "Better not." boxes from one click  => the guard was entered TWICE for that click, and
#     the forwarding Props are the only way that happens
#   * one box => the second offer in Lite came from the dismissal, not from the chain
# Either way the coin must survive Full, so the run also says whether Full holds.
#
# The bakery is the negative control: one baker, no forwarding Props, so it must show one box.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, offer_script, settle_room

FULL, LITE, OFF = 0, 1, 2
REFUSE = "Better not."
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()


def one(place, owner, item_no, item, mode, tag):
    goto(c, place, force=True, log=log)
    c.cmd("send %s get %d" % (ego, item_no))
    if place == 206:
        c.cmd("send %s put 2 206" % ego)         # the bakery's arm needs the shop to own the pie
        c.cmd("send ?Pie owner 206")
    c.setg(402, mode)
    c.setg(403, 0)
    said, at, aim = offer_script(c, "?" + owner, item, tag, log=log)
    has = c.send(ego, "has", item_no)[0]
    n_ref = sum(1 for s in said if REFUSE in s)
    n_warn = sum(1 for s in said if WARNED in s)
    log("  -> %d box(es)  refusals=%d warnings=%d  still has %s = %s  bit=%#06x"
        % (aim["boxes"], n_ref, n_warn, item, has, c.gint(403)))
    log("     said %s" % (said,))
    return aim["boxes"], n_ref, n_warn, has


log("\n===== CONTROL: the bakery, ONE handler, mode FULL =====")
b_boxes, b_ref, b_warn, b_has = one(206, "baker", 11, "Gold_Coin", FULL, "bf")

log("\n===== the toy shop, mode FULL -- the guard can NEVER allow here =====")
t_boxes, t_ref, t_warn, t_has = one(204, "toyMaker", 11, "Gold_Coin", FULL, "tf")

log("\n===== the toy shop, mode LITE -- the row as the suite runs it =====")
l_boxes, l_ref, l_warn, l_has = one(204, "toyMaker", 11, "Gold_Coin", LITE, "tl")

log("\n================ WHAT THAT SETTLES ================")
log("  bakery, Full : %d box(es), %d refusal(s) -- the single-handler baseline" % (b_boxes, b_ref))
log("  toyshop, Full: %d box(es), %d refusal(s), coin kept=%s" % (t_boxes, t_ref, t_has == 1))
if t_ref >= 2:
    log("  ⛔ THE GUARD WAS ENTERED TWICE FOR ONE CLICK. Mode Full cannot allow, so a second")
    log("     refusal cannot have come from the dismissal changing the verdict -- the event was")
    log("     dispatched to `toyMaker:handleEvent` again, through one of the four Props that")
    log("     forward to it, because the deny path never claims the event.")
elif t_ref == 1 and l_warn:
    log("  ⛔ ONE refusal in Full but a warning in Lite: the SECOND offer came from the")
    log("     dismissal, not from the cast chain. The harness is what needs fixing, not the arm.")
log("  toyshop, Lite: %d box(es), %d refusal(s), %d warning(s), coin spent=%s"
    % (l_boxes, l_ref, l_warn, l_has == 0))
if l_warn and l_has == 0:
    log("  ⛔⛔ AND IN LITE THE FIRST CLICK ALREADY SPENT THE COIN. The Lite contract is that")
    log("      the first offer is refused and the item kept; here one click does both halves,")
    log("      so at this site Lite gives the player no second thought at all.")
