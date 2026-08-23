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


FIRST_PLAYABLE = 1          # KQ5 opens outside Graham's house; rm001.sc is a real room


def boot(c, rounds=12, log=print):
    """Get to a playable room. Returns the room we landed in.

    Over the PIPE there is nothing to click: the session starts at a debugger prompt before the
    game has run an instruction, so the intro is simply never entered -- run the VM briefly to
    let script 0 initialise, then go straight to the first playable room. That removes the whole
    Sierra-logo / "Skip it" dance, which was the most fragile part of the keystroke path and the
    one that needed a screenshot to debug.
    """
    import time
    if c.stdin_mode:
        c.resume(2)                                # let script 0 come up
        c.cmd("room %d" % FIRST_PLAYABLE)
        c.resume(3)
        room = c.room()
        log("  booted (pipe) to room %s" % room)
        return room

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


def _ret(out):
    """The `Value returned: ssss:oooo` a `send` prints, or None."""
    import re as _re
    m = _re.search(r"Value returned:\s*([0-9a-f]{4}:[0-9a-f]{4})", out, _re.I)
    return m.group(1) if m else None


USE_ICON = "?icon4"          # the icon bar's inventory-USE icon: its `message` is 4, and
                             # IconBar copies `(curIcon message:)` onto the event it dispatches


def offer_click(c, target, item, seconds=6.0, log=print):
    """Make the offer with a REAL CLICK, while the game runs normally.

    ⚠️ THIS DOES NOT YET COMPLETE A GUARD ROW, and is kept for the next attempt rather than for
    use. It gets remarkably far -- the click reaches the handler, the arm's first statement runs
    (flag 16 set) and its print appears -- and then stops, every time, at the same place:

        before: warn=0x0000 g130=0x0000 has_pie=1
        after : warn=0x0000 g130=0x0001 has_pie=1   <- arm entered, printed, then parked

    The guard's refusal is emitted AFTER the print, so a row that reads state here sees a guard
    that "did not fire" when it simply has not been reached. The print is a modal dialog and the
    game only runs in `debug_countdown` bursts with the clock frozen in between, so a real-time
    dialog never reaches its timeout no matter how many bursts are given; follow-up clicks do not
    dismiss it either. Same root cause as the `send` case: the clock does not advance while the
    debugger holds stdin.

    ⛔ This exists because `send <target> handleEvent <ev>` cannot be used on the text-console
    build: the guard's refusal is a TIMED dialog, and inside a debugger-nested `run_vm` the game
    clock never advances, so it waits forever (screenshot: dialog drawn, hourglass cursor, 45s and
    counting). Here the game is genuinely running -- countdown armed, debugger exited -- so the
    dialog is on its own clock and dismisses itself.

    Only ONE XTEST event is involved, a single click, which is a far smaller target for the
    flakiness that typing suffers from."""
    box = nsrect(c, target, log=log)
    cx = (box["nsLeft"] + box["nsRight"]) // 2
    cy = (box["nsTop"] + box["nsBottom"]) // 2
    # ⛔ Replicate what the INVENTORY WINDOW does when a player picks an item -- the tail of
    # `Inventory::showSelf`:
    #     (if (not (global69 curInvIcon:)) (global69 enable: (global69 useIconItem:)))
    #     (global69 curIcon: ((global69 useIconItem:) cursor: (curIcon cursor:) yourself:)
    #               curInvIcon: curIcon)
    # Poking curIcon/curInvIcon by hand is NOT the same state, and the difference does not show
    # up until execution gets far enough to matter -- as `IconBar::dispatchEvent: Send to invalid
    # selector claimed of object at <the item>`. The icon that belongs in curIcon is the bar's
    # OWN `useIconItem`, not `icon4` looked up by name.
    bar = c.gaddr(69)
    use_icon = _ret(c.send(bar, "useIconItem")[1])
    if use_icon is None:
        raise RuntimeError("icon bar has no useIconItem")
    cursor = _ret(c.send("?" + item, "cursor")[1])
    if not c.send(bar, "curInvIcon")[0]:
        c.cmd("send %s enable %s" % (bar, use_icon))
    if cursor:
        c.cmd("send %s cursor %s" % (use_icon, cursor))
    c.cmd("send %s curIcon %s" % (bar, use_icon))
    c.cmd("send %s curInvIcon ?%s" % (bar, item))
    log("  useIconItem=%s itemCursor=%s" % (use_icon, cursor))
    c.said()                                            # drop the setup's chatter
    def act():
        # ⛔ EXACTLY ONE CLICK. Extra "dismiss" clicks were added when prints could not finish;
        # with the local ScummVM patch they finish by themselves, and the extra clicks became
        # actively harmful -- they land on the icon bar, open the inventory window, and the next
        # one is delivered to an inventory ITEM, which is how
        # `IconBar::dispatchEvent: Send to invalid selector claimed of object at <item>` happens.
        c.click(cx, cy)

    import time as _t
    log("  click (%d,%d) on %s" % (cx, cy, target))
    c.resume(seconds, during=act)
    # ⛔ Let the handler FINISH -- and note WHERE the waiting has to happen. `debug_countdown`
    # re-enters wherever the VM is, which for a speaking guard is inside the print, waiting on CD
    # speech. The speech needs REAL TIME, and real time only passes at the debugger prompt (with
    # the local ScummVM patch; without it, not even there). Bursts alone never finish it, because
    # the driver returns to the prompt and immediately issues the next command. So: sit at the
    # prompt for a moment, THEN give it another burst to notice.
    for _ in range(6):
        _t.sleep(1.2)                                   # time passes here, thanks to the patch
        c.resume(2)
    return c.said(), (cx, cy)


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
