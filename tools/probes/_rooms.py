"""Which script numbers are ROOMS you can teleport to, and which are not.

`room N` really is a room change: KQ5's `Game:doit` polls `(if (!= global13 global11)
(self newRoom: global13))` every cycle, so writing global 13 makes the game do its own
`newRoom:` on the next cycle. That is the classic Sierra debug teleport and it works.

What does NOT work is teleporting to a number that is not a room. Several of KQ5's town
interiors are **Regions layered into one room**, not rooms of their own:

    room 5's init switches on global313 -- 1 -> setRegions 203 (tailor),
                                           2 -> setRegions 204 (toy shop),
                                           3 -> setRegions 205 (shoe shop)

so `room 204` sets global13 to a number with no room behind it, the game calls
`newRoom: 204`, gets `toyShop of Rgn` as that script's export 0, and starts sending Room
messages to a Region. The game dies -- silently, several seconds later, which reads as
"teleporting is unreliable" rather than "that was never a room".

The distinction is visible in our own decompiled source, so it can be checked BEFORE a run
instead of by killing a game: look at what export 0 of the script is an instance OF.
"""
import os
import re

_EXPORT0 = re.compile(r"\(public\s+(\w+)\s+0\b")
# `(class castle of Rgn)` as well as `(instance toyShop of Rgn)` -- KQ5 spells some
# regions as classes, and a pattern that only knows `instance` reports them as unknown,
# which is the same as reporting them teleportable.
_INSTANCE = re.compile(r"^\((?:instance|class)\s+(\w+)\s+of\s+(\w+)", re.M)


def classify(src_dir):
    """{script number: (object name, base class)} for every script that publishes an export 0."""
    out = {}
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".sc"):
            continue
        text = open(os.path.join(src_dir, name), errors="replace").read()
        m = re.search(r"\(script#\s*(\d+)\)", text)
        e = _EXPORT0.search(text)
        if not m or not e:
            continue
        bases = dict((n, b) for n, b in _INSTANCE.findall(text))
        obj = e.group(1)
        out[int(m.group(1))] = (obj, bases.get(obj, "?"))
    return out


def teleportable(src_dir, room_classes=("Rm", "Room", "KQ5Room")):
    """The script numbers `room N` can be pointed at. Anything whose export 0 is a Region is
    excluded -- that is the whole failure mode this module exists for."""
    return {n: v for n, v in classify(src_dir).items() if v[1] in room_classes}


if __name__ == "__main__":
    import sys
    d = sys.argv[1]
    rooms = classify(d)
    regions = {n: v for n, v in rooms.items() if v[1] not in ("Rm", "Room", "KQ5Room")}
    print("%d scripts with an export 0; %d are NOT rooms:" % (len(rooms), len(regions)))
    for n in sorted(regions):
        print("  %4d  %-16s of %s" % (n, regions[n][0], regions[n][1]))
