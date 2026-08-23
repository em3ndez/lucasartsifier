# LA6 from KQ5-LITE-TESTPLAN, driven entirely from the SCI console.
#
#   ☐ LA6 | 403 $0001 | anywhere | EAT the Pie (2) | warned, then the pie is actually eaten
#
# Why this row and not a shop row: the EAT guard lives in `class ego`'s own `handleEvent`
# (script 0), so it is reachable from the FIRST playable room -- no teleport. That matters,
# because `newRoom`-ing out of the opening scene into a town interior kills the game outright.
# The ego is also always on screen, so its nsRect is always real (a freshly-loaded room's Props
# have a 0,0,0,0 box and every synthesized event at them misses silently).
#
# The oracle is the emitted source, read back as behavior:
#     attempt 1 -> "Just kidding! You hold on to it because you still need it." + bit $0001 set,
#                  and the pie is STILL HELD
#     attempt 2 -> "You have been warned!" and `(global0 put: 2 1)` -- the pie is GONE
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --script tools/probes/kq5_eat_pie.py
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, game_event, nsrect, offer

PIE, BIT, MODE_G, WARN_G = 2, 0x0001, 402, 403
REFUSE = "Just kidding!"
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log)

ego = c.gaddr(0)
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 1)                                  # LITE
c.setg(WARN_G, 0)                                  # this site owes a fresh refusal
c.watch_text()
log("mode=%d warn=%#06x has_pie=%s" % (c.gint(MODE_G), c.gint(WARN_G),
                                       c.send(ego, "has", PIE)[0]))

EVENT = game_event(c)
log("using %s as the event" % EVENT)
box = nsrect(c, ego, log=log)
log("ego box %s" % box)

# The verdict rests on STATE, which the VM answers directly. The text channel below is
# INFORMATIONAL: `bpk StrCpy log` registers, but no probe has yet read a game line out of it, and
# grading on a channel that has never produced output would fail a guard that is behaving.
ok = True
for attempt in (1, 2):
    said, _aim, claimed = offer(c, EVENT, ego, "Pie")
    bit = bool(c.gint(WARN_G) & BIT)
    has = c.send(ego, "has", PIE)[0]
    want_bit, want_has, want_msg = (True, 1, REFUSE) if attempt == 1 else (True, 0, WARNED)
    good = bit == want_bit and has == want_has
    log("\nattempt %d: bit=%s (want %s) has_pie=%s (want %d) -> %s"
        % (attempt, bit, want_bit, has, want_has, "OK" if good else "WRONG"))
    log("  text channel (informational): %r ; looking for %r" % (said, want_msg))
    ok = ok and good

log("\n=== LA6 state contract: %s ===" % ("PASS" if ok else "FAIL"))
log("    attempt 1 must refuse (bit set, pie KEPT); attempt 2 must let it through (pie GONE)")
