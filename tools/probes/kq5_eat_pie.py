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
from _kq5 import boot

PIE, BIT, MODE_G, WARN_G = 2, 0x0001, 402, 403
REFUSE = "Just kidding!"
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

def box(obj, tries=6):
    """The object's nsRect, waiting for the room to actually draw it."""
    for _ in range(tries):
        txt = c.cmd("vo " + obj)
        got = {m.group(1): int(m.group(2), 16) for m in
               re.finditer(r"(nsLeft|nsTop|nsRight|nsBottom)\s*=\s*[0-9a-f]{4}:([0-9a-f]{4})", txt)}
        if got.get("nsRight"):
            return got
        log("  not drawn yet (%s); letting the room run" % got)
        c.resume(2.0)
        c.open()
    raise SystemExit("%s never got an nsRect" % obj)

def event_class():
    """The Event CLASS's address, pinned ONCE.

    ⛔ `?Event` resolves only until the first `Event new:`. After that the name matches the class
    AND every live instance, and the console answers an ambiguous name with a candidate list
    instead of an address -- so a probe that re-resolves the name works on its first interaction
    and fails on its second, which reads like the game hanging rather than like a name lookup.

    ⛔ And "resolve it before making one" does not work either: the resolving call IS a `new:`.
    So force one instance deliberately, then read the class off the ambiguity list, where index 0
    is the class (it lives in a script segment; the instances are clones)."""
    c.cmd("send ?Event new")                       # guarantee the name is ambiguous
    out = c.cmd("vo ?Event")
    m = re.search(r"0:\s*\[([0-9a-f]{4}:[0-9a-f]{4})\]", out, re.I)
    if not m:
        raise SystemExit("could not pin the Event class from: %r" % out[:400])
    return m.group(1)


def eat(ego, cx, cy):
    """EAT the held item: the event `ego:handleEvent` wants is type 16384, message 4, inside
    the ego's own box -- `proc255_5 self param1` is a bounding-box test against `self`."""
    c.cmd("send %s curInvIcon ?Pie" % c.gaddr(69))
    raw = c.send(EVENT_CLASS, "new")[1]
    m = re.search(r"Value returned:\s*([0-9a-f]{4}:[0-9a-f]{4})", raw, re.I)
    if not m:
        c.shot("/tmp/kq5_eat_blocked.png")
        raise SystemExit("Event new: returned nothing (%r) -- /tmp/kq5_eat_blocked.png" % raw[:200])
    ev = m.group(1)
    for sel, val in (("type", 16384), ("message", 4), ("x", cx), ("y", cy), ("claimed", 0)):
        c.cmd("send %s %s %d" % (ev, sel, val))
    c.said()                                       # drop whatever the setup printed
    c.cmd("send %s handleEvent %s" % (ego, ev))
    # ⛔ A refusal is a MODAL print. `proc255_0` opens a Dialog and blocks the interpreter until
    # it is dismissed -- so a probe that fires a second attempt without dismissing the first one
    # hangs the game, and the symptom is a later `send` that simply never returns. Dismiss it the
    # way a player does before doing anything else.
    c.resume(1.2)
    c.key("Return", n=2, settle=0.6)
    time.sleep(1.0)
    c.open()
    return c.said()

log("== boot ==")
boot(c, log=log)

ego = c.gaddr(0)
c.cmd("send %s get %d" % (ego, PIE))
c.setg(MODE_G, 1)                                  # LITE
c.setg(WARN_G, 0)                                  # this site owes a fresh refusal
c.watch_text()
log("mode=%d warn=%#06x has_pie=%s" % (c.gint(MODE_G), c.gint(WARN_G),
                                       c.send(ego, "has", PIE)[0]))

EVENT_CLASS = event_class()
log("Event class at %s" % EVENT_CLASS)

b = box(ego)
cx, cy = (b["nsLeft"] + b["nsRight"]) // 2, (b["nsTop"] + b["nsBottom"]) // 2
log("ego box %s -> aiming at (%d,%d)" % (b, cx, cy))

# The verdict rests on STATE, which the VM answers directly. The text channel below is
# INFORMATIONAL: `bpk StrCpy log` registers, but no probe has yet read a game line out of it, and
# grading on a channel that has never produced output would fail a guard that is behaving.
ok = True
for attempt in (1, 2):
    said = eat(ego, cx, cy)
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
