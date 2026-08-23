# `?baker` answers "Invalid address passed" in room 206. Before anything is concluded from that,
# establish which of the two things it means -- the script is not loaded, or the object has no
# NAME the debugger can match. `findObjectByName` is an exact match on the object's `name`
# selector, and script 206 is one our patch RECOMPILES, so a lost name string is a real candidate.
#
# `segment_table` says whether script 206 is resident; `segment_info` on its segment lists the
# objects it holds WITH their names, which settles both at once and hands over addresses that
# work regardless. A screenshot says whether the room on screen is the bakery at all.
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto

def log(*a): print(*a, flush=True)

boot(c, log=log, teleport=True)
goto(c, 206, log=log)
log("room = %s   global11=%s global13=%s" % (c.room(), c.gint(11), c.gint(13)))
c.shot("/tmp/kq5_bakery.png")
log("shot -> /tmp/kq5_bakery.png")

seg = c.cmd("segtable")
log("\n---- segment_table ----\n%s" % seg)
# The script segments are listed as `<n>: script.<nr> ...`; find 206's.
m = re.search(r"(\d+):\s*Script\.0*206\b", seg, re.I) or re.search(r"(\d+):\s*script\s*206\b", seg, re.I)
log("\nscript-206 segment: %s" % (m.group(1) if m else "NOT FOUND in the table above"))
if m:
    log("\n---- segment_info %s ----\n%s" % (m.group(1), c.cmd("seginfo %s" % m.group(1))[:6000]))
