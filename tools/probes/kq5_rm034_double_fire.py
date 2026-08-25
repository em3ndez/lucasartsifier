# The FOURTH site the deny-path leak was measured at: rm034's eagle, offered the Pie ($0080).
#
# Same shape as the toy shop and the same reason -- `eagleWing` and `eagleHead` are Props whose
# whole `handleEvent` is `(eagle handleEvent: param1)`, so an unclaimed refusal is handed straight
# back to the guard that just refused, its own `(|= global403 $0080)` already written.
#
# The bakery is the negative control (one handler, no forwarding Props): it must show ONE box on
# every build. MODE FULL is the discriminator -- its allow test
# `(or (== global402 2) (and (== global402 1) (& global403 $0080)))` can never be true, so a
# second refusal cannot come from the dismissal changing the verdict.
#
# ⛔ THIS ROW IS WHY THE PROBE EXISTS. `kq5_lite_scripted.py` cannot reach it: the row dies with
# "ScummVM exited while waiting for a prompt" on the PRE-CHANGE build and on the fixed one alike,
# so the suite says nothing about it either way (measured 2026-08-23, both builds, row in
# isolation and in the full run).
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
        c.cmd("send %s put 2 206" % ego)
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
b_boxes, b_ref, _bw, b_has = one(206, "baker", 11, "Gold_Coin", FULL, "bf")

log("\n===== rm034's eagle, mode FULL -- the guard can NEVER allow here =====")
e_boxes, e_ref, _ew, e_has = one(34, "eagle", 2, "Pie", FULL, "ef")

log("\n===== rm034's eagle, mode LITE -- the row as the suite would run it =====")
l_boxes, l_ref, l_warn, l_has = one(34, "eagle", 2, "Pie", LITE, "el")

log("\n================ WHAT THAT SETTLES ================")
log("  bakery, Full: %d box(es), %d refusal(s) -- the single-handler baseline" % (b_boxes, b_ref))
log("  eagle,  Full: %d box(es), %d refusal(s), Pie kept=%s" % (e_boxes, e_ref, e_has == 1))
if e_ref >= 2:
    log("  ⛔ THE GUARD WAS ENTERED TWICE FOR ONE CLICK -- eagleWing/eagleHead handed the same")
    log("     click back to `eagle:handleEvent` because the refusal never claimed the event.")
log("  eagle,  Lite: %d box(es), %d refusal(s), %d warning(s), Pie kept=%s"
    % (l_boxes, l_ref, l_warn, l_has == 1))
if l_warn and l_has == 0:
    log("  ⛔⛔ AND IN LITE THE FIRST CLICK ALREADY SPENT THE PIE -- no second thought at all.")
elif l_ref == 1 and not l_warn and l_has == 1:
    log("  ✅ LITE'S TWO-STEP HOLDS: one refusal, no warning, the Pie kept.")
