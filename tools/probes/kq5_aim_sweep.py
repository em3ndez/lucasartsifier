# WHICH AIM IS RIGHT? Settle it with the GUARD'S OWN BIT, not with a box.
#
# ⛔ The box count was the wrong witness and I used it once already. A LOOK click ten pixels below
# the eagle's centre produced a box with no text -- and a box with no text could be the eagle's
# own description (some `proc0_29` messages do not travel through kStrCpy, so `said()` is silent
# for them) or it could be any other object under that point. Two readings, same observation.
#
# ⭐ The bit has no such ambiguity: `global403 $0080` is written by exactly one statement in the
# whole game, inside the eagle's message-4 arm. If it moves, the click reached the eagle. If it
# does not, it did not -- whatever a box may or may not have shown.
#
# So: sweep the aim from the nsRect centre downwards a few pixels at a time, with the item armed,
# Lite mode and the bit clear each time, and report the first offset at which the bit moves. That
# is the offset every row should use, measured rather than reasoned about.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import (arm_item, boot, drain_boxes, goto, nsrect, park_mouse, port_origin,
                  resolve, resume_play)

# room, target, item number, item name, warn word, bit -- all derived elsewhere, repeated here
# only so this probe is readable on its own.
CASES = [(34, "eagle", 2, "Pie", 403, 0x0080),
         (30, "branch", 20, "Rope", 403, 0x0004),
         (206, "baker", 11, "Gold_Coin", 403, 0x0008)]
LITE = 1

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()

for room, owner, item_no, item, word, mask in CASES:
    log("\n===== room %s, %s, bit g%d $%04x =====" % (room, owner, word, mask))
    goto(c, room, force=True, log=log)
    obj = resolve(c, owner, None, log=log)
    ox, oy = port_origin(c)
    log("  picture window origin %s" % ((ox, oy),))
    for dy in (0, 5, 10, 15, -5):
        c.cmd("send %s get %d" % (ego, item_no))
        if room == 206:
            c.cmd("send %s put 2 206" % ego)
            c.cmd("send ?Pie owner 206")
        c.setg(402, LITE)
        c.setg(word, 0)
        # ⛔ Each attempt after a successful one starts from a cutscene the last attempt left
        # running -- input off, icon bar disabled -- and every click after that is inert. That
        # made the first sweep read as "only +5 works" when +10 had simply never been tried
        # under the same conditions. See _kq5.resume_play.
        resume_play(c, log=log)
        arm_item(c, item, log=lambda *a: None)
        park_mouse(c, log=lambda *a: None)
        box = nsrect(c, obj, log=lambda *a: None)
        cx = (box["nsLeft"] + box["nsRight"]) // 2
        cy = (box["nsTop"] + box["nsBottom"]) // 2
        c.said()
        tag = "s%s%s%d" % (room, owner[0], dy + 100)
        c.cmd("script clear")
        c.cmd("script add t=+150 click %d %d" % (cx, cy + dy))
        c.cmd("script add t=+2650 mark %s" % tag)
        c.cmd("script add t=+2750 break")
        c.resume(seconds=60, instructions=3000000)
        c.wait_mark(tag, timeout=10)
        said = c.said()
        more, n = drain_boxes(c, tag, log=lambda *a: None)
        said += more
        moved = bool(c.gint(word) & mask)
        log("  aim (%d,%3d)  dy=%+3d  box=%s  -> bit %s   %d box(es)  said=%s"
            % (cx, cy + dy, dy, (box["nsTop"], box["nsBottom"]),
               "SET" if moved else "unchanged", n, [s[:48] for s in said]))
