# A LOOK click on the eagle and on the tailor produces nothing, while the same click on the baker
# produces his description. So the event is not reaching those two objects at all -- the question
# is who or what is in the way, and `User:handleEvent` has only a few places for it to go:
#
#     (cond ((& (param1 type:) $0040) ...)
#           ((== temp0 4) (if global72 (global72 handleEvent: param1)))     ; temp0 = the type
#           ((and (== temp0 1) global73) (global73 handleEvent: param1)))   ;   BEFORE the rewrite
#     (if (not (param1 claimed:))
#         (if global69 (global69 handleEvent: param1))                      ; the icon bar rewrite
#         (if (and (== (param1 type:) 16384) input)
#             (cond ((and (== (param1 message:) 1) controls (alterEgo handleEvent: param1)) 1)
#                   (global34 <OnMeAndLowY: ONE object gets it>)
#                   ((global5 handleEvent: param1) 1)                       ; the CAST, in order
#                   ((global32 handleEvent: param1) 1))                     ; then the features
#             ...))
#
# So: is the object even in the cast? Is something earlier in the cast claiming? Is `input` on at
# the moment of the click rather than at the moment we measured it? This reports the cast in its
# actual order with each member's box, so "who is on top of that point, and who comes first" is
# a reading rather than a guess.
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, nsrect, resolve, _signed

CASES = [(206, "baker"), (34, "eagle"), (203, "tailor")]

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
ego = c.gaddr(0)
user = c.gaddr(80)

for room, owner in CASES:
    log("\n===== room %s, %s =====" % (room, owner))
    goto(c, room, force=True, log=log)
    obj = resolve(c, owner, None, log=log)
    box = nsrect(c, obj, log=log)
    cx = (box["nsLeft"] + box["nsRight"]) // 2
    cy = (box["nsTop"] + box["nsBottom"]) // 2
    log("  %s box=%s aim=(%d,%d)" % (owner, box, cx, cy))
    log("  in the cast (global5 contains:)   = %s" % c.send(c.gaddr(5), "contains", obj)[0])
    log("  in the features (global32)        = %s" % c.send(c.gaddr(32), "contains", obj)[0])
    log("  global34=%s global72=%s global73=%s  canInput=%s"
        % (c.gint(34), c.gaddr(72), c.gaddr(73), c.send(user, "canInput")[0]))
    # The cast in its real order, with the boxes -- `firstTrue: #handleEvent` stops at the first
    # member that claims, so order is the whole story.
    al = c.cmd("al")
    log("  animate list:")
    for line in al.splitlines():
        if re.search(r"\[[0-9a-f]{4}:[0-9a-f]{4}\]", line):
            log("    %s" % line.strip()[:120])
