# THE HERMIT'S LITE TWO-STEP, counted click by click.
#
# [USER, play-tested 2026-08-23: "the hermit is buggy. it refuses twice. the second time it says
# you have been warned AND not yet, then the third time it goes through"]
#
# rm046 stacks TWO guards on one offer (give the Shell), and before the fix each owned a warned
# bit: clearing the outer's bit let the player past the outer while its condition was still
# false, which exposed the inner. This counts the boxes and the sentences on each of three
# clicks, with the refusal state set up explicitly:
#   * ego HOLDS the Shell (23) and NOT the Iron Bar (30) / Fishhook (31) -- so the outer's
#     `(and (has 30) (has 31))` is false
#   * flag 55 clear -- so the inner's `(or (not (not (flag 55))) ...)` is false too
# Both guards would therefore refuse. Lite's contract is ONE refusal, then through.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, offer_script, resolve, settle_room

FULL, LITE, OFF = 0, 1, 2
FLAG_BASE = 129

def log(*a): print(*a, flush=True)

def set_flag(c, n, on):
    g = FLAG_BASE + n // 16
    bit = 1 << (n % 16)
    v = c.gint(g)
    c.setg(g, (v | bit) if on else (v & ~bit & 0xffff))

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()

goto(c, 46, force=True, log=log)
# ⛔ SETTLE FIRST. The hermit is init:ed by the room's own intro; clicking before it
# finishes aims at an nsRect that is still 0,0,0,0 and the offer never lands.
settle_room(c, log=log)
c.cmd("send %s get 23" % ego)                 # the Shell
for it in (30, 31):                           # NOT the Iron Bar, NOT the Fishhook
    c.cmd("send %s put %d 1" % (ego, it))
set_flag(c, 55, False)
c.setg(402, LITE)
c.setg(403, 0)
c.setg(404, 0)

target = resolve(c, "hermit_a", script=46, log=log)
log("  ego has Shell=%s IronBar=%s Fishhook=%s   g403=%#06x g404=%#06x"
    % (c.send(ego, "has", 23)[0], c.send(ego, "has", 30)[0], c.send(ego, "has", 31)[0],
       c.gint(403), c.gint(404)))

for click in (1, 2, 3):
    said, at, aim = offer_script(c, target, "Shell", "h%d" % click, log=log)
    has = c.send(ego, "has", 23)[0]
    log("  CLICK %d -> %d box(es)  Shell kept=%s  g403=%#06x g404=%#06x"
        % (click, aim["boxes"], has == 1, c.gint(403), c.gint(404)))
    log("     said %s" % (said,))
    if has == 0:
        log("  -> the Shell went through on click %d" % click)
        break
