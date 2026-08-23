"""Getting KQ5 from a cold start to a playable room, without a person watching.

⛔ Do not try to open the console DURING the intro. The Ctrl+Alt+D hotkey is ignored until the
game reaches its ordinary event loop, so a boot loop that probes the console every round spends
its whole budget on a keystroke that cannot land. Click all the way in first, then open once.

⛔ (160, 120) is not a button. KQ5's cartoon warning has *Watch it* / *Skip it* down at y=129,
and a generic centre-screen click misses both -- which parks the game on that dialog forever.
That cost a full run before a failure screenshot showed the dialog still sitting there.
"""

PLAYED_YES = (184, 59)      # "Have you played King's Quest V before?" -> Yes
SKIP_IT    = (258, 129)     # the cartoon warning's "Skip it"
FIRST_ROOM = 2              # past the title/intro rooms means we are playing


def boot(c, rounds=12, log=print):
    """Click through the intro, then open the console once. Returns the room we landed in."""
    import time
    time.sleep(8)                                  # the Sierra logo takes no input at all
    c.click(*PLAYED_YES)
    time.sleep(2)
    for _ in range(rounds):
        c.key("Escape"); time.sleep(0.6)
        c.click(*SKIP_IT); time.sleep(0.4)
        c.click(160, 120); time.sleep(0.5)
    time.sleep(4)
    c.open()
    room = c.room()
    log("  booted to room %s" % room)
    if room is None:
        c.shot("/tmp/kq5_boot_stuck.png")
        raise RuntimeError("no room number after boot -- /tmp/kq5_boot_stuck.png")
    return room


# The town interiors that are REGIONS inside room 5, not rooms of their own. Room 5's `init`
# switches on global313 to pick the pic and the region -- so the way in is to set that first and
# then go to room 5. `room 203/204/205` points the game at a script whose export 0 is a `Rgn`,
# and it dies sending Room messages to a Region. See `_rooms.py`.
SHOP_REGIONS = {203: 1, 204: 2, 205: 3}      # script number -> the global313 value that loads it
SHOP_ROOM = 5
BOUNCE_ROOM = 4                              # the town square, room 5's own neighbour


def goto(c, room, settle=6.0, log=print):
    """Teleport, handling the room-5 shops.

    `room N` is a real room change -- KQ5's `Game:doit` polls `(if (!= global13 global11)
    (self newRoom: global13))` every cycle, so writing global 13 makes the game perform its own
    `newRoom:`. What it cannot do is reach something that is not a room; for those, this sets up
    room 5 instead and reports the room it actually landed in (5), not the region number."""
    target, region = room, None
    if room in SHOP_REGIONS:
        region = SHOP_REGIONS[room]
        c.setg(313, region)
        target = SHOP_ROOM
        log("  script %d is a REGION of room %d; global313=%d" % (room, SHOP_ROOM, region))

    # ⛔ A room change to the room you are ALREADY in is a no-op. The game acts on global 13 only
    # when it differs from global 11 (`(if (!= global13 global11) (self newRoom: global13))`), so
    # `room 5` while standing in room 5 changes nothing -- and for the shops that matters, because
    # the shop you are in is chosen by global313 AT init. Switching from the tailor to the toy shop
    # therefore silently leaves you in the tailor, with `?toyMaker` simply not existing. Bounce out
    # and back so init runs again.
    if c.room() == target:
        log("  already in room %d; bouncing via %d so init re-runs" % (target, BOUNCE_ROOM))
        c.cmd("room %d" % BOUNCE_ROOM)
        c.resume(settle)
        c.open()

    c.cmd("room %d" % target)
    c.resume(settle)
    c.open()
    got = c.room()
    log("  room %d -> %s" % (target, got))
    return got


def event_class(c):
    """The Event CLASS's address, pinned ONCE.

    ⛔ `?Event` resolves only until the first `Event new:`. After that the name matches the class
    AND every live instance, and the console answers an ambiguous name with a candidate list
    instead of an address -- so a probe that re-resolves the name works on its first interaction
    and fails on its second, which reads like the game hanging rather than like a name lookup.

    ⛔ And "resolve it before making one" does not work either: the resolving call IS a `new:`.
    So force one instance deliberately, then read the class off the ambiguity list, where index 0
    is the class (it lives in a script segment; the instances are clones)."""
    import re
    c.cmd("send ?Event new")                       # guarantee the name is ambiguous
    out = c.cmd("vo ?Event")
    m = re.search(r"0:\s*\[([0-9a-f]{4}:[0-9a-f]{4})\]", out, re.I)
    if not m:
        raise RuntimeError("could not pin the Event class from: %r" % out[:400])
    return m.group(1)


def nsrect(c, obj, tries=6, log=print):
    """An object's nsRect, waiting for the room to actually draw it.

    ⛔ Straight after a room change every Prop reads 0,0,0,0, an event aimed at (0,0) fails the
    hit test, the handler returns silently -- and the probe reports "no refusal" for a guard it
    never reached. The ego always has a box, which is why script-0 guards are the easy targets."""
    import re
    for _ in range(tries):
        txt = c.cmd("vo " + obj)
        got = {m.group(1): int(m.group(2), 16) for m in
               re.finditer(r"(nsLeft|nsTop|nsRight|nsBottom)\s*=\s*[0-9a-f]{4}:([0-9a-f]{4})", txt)}
        if got.get("nsRight"):
            return got
        if tries == 1:
            return got                             # diagnostic call -- report, do not wait
        log("  %s not drawn yet (%s); letting the room run" % (obj, got))
        c.resume(2.0)
        c.open()
    raise RuntimeError("%s never got an nsRect" % obj)


def game_event(c, names=("?uEvt", "?ibEvent")):
    """The address of a PERMANENT Event instance belonging to the game.

    ⛔ Do not build events with `Event new:`. That returns a CLONE, and every console `send` runs
    the VM re-entrantly, which can run SCI's garbage collector -- which reclaims a clone that
    nothing references, i.e. exactly the event a probe just made. The handler then receives a
    dead address and the game dies with

        [kq5 5/203 tailor::handleEvent]: lookupSelector: Attempt to send to non-object
        or invalid script. Address 0028:00a2!

    several commands after the create, intermittently, which reads as "the harness is flaky".
    Caching one clone across rows dies the same way for the extra reason that a room change frees
    clones outright.

    `uEvt` is the User's own event and `ibEvent` is the icon bar's: static instances in loaded
    scripts, so neither is collectable and neither goes stale across a room change."""
    for n in names:
        out = c.cmd("vo " + n)
        if "not an object" not in out and "Invalid address" not in out and out.strip():
            return n
    raise RuntimeError("no permanent Event instance found (tried %s)" % (names,))


def offer(c, ev, target, item, box=None, aim=None, log=print):
    """Hand `item` to `target` the way a click does.

    A handler wants an event that is type 16384, carries message 4, and lands inside the target's
    nsRect (`proc255_5` is a bounding-box test). All three are writable, so a click is
    constructible. `aim` is the (x, y) already set on this event, so a run of offers at the SAME
    target does not re-send them. Returns whatever the game printed (see Console.said)."""
    # ⛔ Re-read the box for EVERY offer. Half these targets are Actors, and an Actor walks: the
    # box read at the top of a row is stale by the second attempt, the event lands outside it,
    # `proc255_5` rejects it, and the row reports a guard that "did not fire" when in fact the
    # handler was never reached. It made the tailor row pass in one run and fail in the next.
    box = nsrect(c, target, log=log)
    cx = (box["nsLeft"] + box["nsRight"]) // 2
    cy = (box["nsTop"] + box["nsBottom"]) // 2
    # `ev` is a PERMANENT instance (see game_event), so every field is set fresh each time.
    c.cmd("send %s type 16384" % ev)
    c.cmd("send %s message 4" % ev)
    c.cmd("send %s x %d" % (ev, cx))
    c.cmd("send %s y %d" % (ev, cy))
    c.cmd("send %s claimed 0" % ev)                # a handler that ran will set this to 1
    c.cmd("send %s curInvIcon ?%s" % (c.gaddr(69), item))
    c.said()                                       # drop whatever the setup printed
    c.cmd("send %s handleEvent %s" % (target, ev))
    # ⛔ NEUTRALISE THE EVENT BEFORE RESUMING. `uEvt` is the User's own event object, so a
    # synthetic one left in it is picked up by the game's normal loop on the very next cycle and
    # DELIVERED AGAIN. That showed up as a row where the guard both refused (warn bit set) and
    # sold (item spent) on the same attempt -- the first delivery was ours, the second the game's.
    c.cmd("send %s type 0" % ev)
    c.resume(1.2)
    c.key("Return", n=2, settle=0.5)               # a refusal is a print; dismiss it
    import time as _t
    _t.sleep(0.8)
    c.open()
    # ⭐ `claimed` separates the two ways an offer can look like nothing happened: 1 means the
    # handler RAN and this is a real verdict about the guard; 0 means the event never got past
    # `(or (param1 claimed:) (not (== (param1 type:) 16384)) (not (proc255_5 self param1)))` --
    # a probe aiming problem, not a guard problem. Without it the two are indistinguishable and
    # an aiming bug reads as a failing guard.
    claimed, _ = c.send(ev, "claimed")
    if not claimed:                                # say WHERE it was aimed and where the target is
        now = nsrect(c, target, tries=1, log=log)
        log("    aimed (%d,%d); %s box was %s, now %s" % (cx, cy, target, box, now))
    return c.said(), (cx, cy), claimed


def wait_spent(c, ego, item, cycles=6, slice_s=1.5, log=print):
    """Poll `ego has: item` while letting the game run. Returns True once the item is gone.

    ⛔ Disposal is not always inline. Script 0's EAT does `(global0 put: 2 1)` right in the
    handler, so the item is gone the instant `handleEvent` returns -- but the toymaker's handler
    only does `setScript: getSled`, and the payment is taken in that script's `changeState` state
    0 (`(global0 put: 9 204)`). Between those two shapes sits a race: sampling `has:` once after a
    fixed sleep passes for the first, and passes for the second only when the script happened to
    get its cycle in. It read OK for the needle and WRONG for the heart in the same run, at the
    same site, which is the signature of a timing oracle rather than a broken guard.

    Which shape a site has is readable from the emitted source: `put:` in the handler is inline,
    `setScript:` is deferred. Rather than encode that per site, poll."""
    for i in range(cycles):
        if c.send(ego, "has", item)[0] == 0:
            return True
        c.resume(slice_s)
        c.open()
    log("  item %d still held after %d cycles" % (item, cycles))
    return False
