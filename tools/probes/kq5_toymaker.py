# LA1b/LA1c from KQ5-LITE-TESTPLAN, driven entirely from the SCI console -- no clicking,
# no screenshots, no OCR.
#
# The claim under test is the one the lite plan is built on: each guard SITE refuses ONCE,
# and the SECOND attempt at that same site prints "You have been warned!" and lets the stock
# behavior through -- while a DIFFERENT site on the same NPC still owes you its own refusal.
#
# How an inventory offer is made without a mouse: `toyMaker:handleEvent` wants an event that
# (a) is type 16384, (b) has message 4 ("use the held item on me"), and (c) lands inside the
# object's nsRect -- `proc255_5` is a bounding-box hit test. All three are writable, so the
# offer is: set the icon bar's curInvIcon, build an Event, send it.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --script tools/probes/kq5_toymaker.py
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto

ROOM, MODE_G, WARN_G = 204, 402, 403
SITES = {"Heart": (9, 0x1000), "Gold_Coin": (11, 0x0010), "Golden_Needle": (3, 0x0200)}

def log(*a): print(*a, flush=True)

def rect(obj):
    """(nsLeft, nsTop, nsRight, nsBottom) off `vo`."""
    txt = c.cmd("vo " + obj)
    got = {}
    for m in re.finditer(r"(nsLeft|nsTop|nsRight|nsBottom)\s*=\s*[0-9a-f]{4}:([0-9a-f]{4})", txt):
        got[m.group(1)] = int(m.group(2), 16)
    return got, txt

def offer(target, item, cx, cy):
    """Hand `item` to `target` the way a click would: an event of type 16384, message 4,
    landing inside the target's box, with the icon bar holding that item."""
    c.cmd("send %s curInvIcon ?%s" % (c.gaddr(69), item))
    ev = c.send("?Event", "new")[1]
    m = re.search(r"Value returned:\s*([0-9a-f]{4}:[0-9a-f]{4})", ev, re.I)
    if not m:
        raise RuntimeError("no Event returned:\n" + ev)
    e = m.group(1)
    for sel, val in (("type", 16384), ("message", 4), ("x", cx), ("y", cy), ("claimed", 0)):
        c.cmd("send %s %s %d" % (e, sel, val))
    c.said()                                      # drop anything the setup printed
    out = c.cmd("send %s handleEvent %s" % (target, e))
    return c.said(), out

# ---- boot -------------------------------------------------------------------------------
log("== boot ==")
boot(c, log=log)

# ---- put the VM in the state under test --------------------------------------------------
ego = c.gaddr(0)
for item, _ in SITES.values():
    c.cmd("send %s get %d" % (ego, item))
c.setg(MODE_G, 1)                                 # LITE
c.setg(WARN_G, 0)                                 # every site owes a fresh refusal
log("mode=%d warn=%#06x" % (c.gint(MODE_G), c.gint(WARN_G)))
c.watch_text()                                    # every printed line lands on stdout

got = goto(c, ROOM, log=log)
if got != ROOM:
    c.shot("/tmp/kq5_not_in_shop.png")
    raise SystemExit("newRoom %d landed in %s -- /tmp/kq5_not_in_shop.png" % (ROOM, got))

# ⛔ A Prop has NO bounding box until the room has actually drawn it: straight after `newRoom`
# every nsRect reads 0,0,0,0, and an event aimed at (0,0) fails `proc255_5` silently -- the
# handler simply returns and the probe reports "no refusal" for a guard that was never reached.
# So let the room run until the box is real.
for attempt in range(6):
    box, raw = rect("?toyMaker")
    if box.get("nsRight"):
        break
    log("  toyMaker not drawn yet (%s); letting the room run" % box)
    c.resume(2.5)
    c.open()
else:
    log("RAW vo:\n" + raw[:900])
    raise SystemExit("toyMaker never got an nsRect")
log("toyMaker box:", box)
cx = (box["nsLeft"] + box["nsRight"]) // 2
cy = (box["nsTop"] + box["nsBottom"]) // 2
log("aiming at (%d,%d)" % (cx, cy))

# ---- the actual assertions ----------------------------------------------------------------
for item, (num, bit) in SITES.items():
    log("\n===== site: %s (item %d, bit %#06x) =====" % (item, num, bit))
    for attempt in (1, 2):
        before_bit = c.gint(WARN_G) & bit
        before_has = c.send(ego, "has", num)[0]
        said, out = offer("?toyMaker", item, cx, cy)
        after_bit = c.gint(WARN_G) & bit
        after_has = c.send(ego, "has", num)[0]
        log("  attempt %d: warnbit %s->%s  has(%d) %s->%s"
            % (attempt, bool(before_bit), bool(after_bit), num, before_has, after_has))
        log("  said: %r" % (said,))
log("\n=== final warn word: %#06x ===" % c.gint(WARN_G))
