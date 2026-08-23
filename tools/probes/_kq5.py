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


# Somewhere off the icon bar's strip and inside the picture. See park_mouse.
PARK = (160, 150)


def here(c):
    """The room the game is actually IN. This is GLOBAL 11.

    ⛔ NOT `c.room()`. That prints ScummVM's `currentRoomNumber()`, which reads GLOBAL 13 -- the
    room last ASKED for. Writing 13 and reading it back always agrees, so it cannot witness a
    teleport, and it spent a whole row's worth of debugging confirming a room change that never
    happened (`room 206` answered "206" while Graham stood outside his house). `Game:newRoom` is
    what moves global 11, and `Game:doit` is what calls it."""
    return c.gint(11)


def park_mouse(c, at=PARK, tag="park", wait=1500, log=print):
    """Move the virtual mouse off the icon bar's top strip, and wait for the bar to go away.

    ⛔⛔ THIS IS NOT COSMETIC -- it is the precondition for the game running at all.

    `IconBar:handleEvent` opens the bar whenever there is NO event and the mouse is inside the
    top strip, and `IconBar:doit` then spins a loop of its own:

        (method (doit) (while (& state $0020) ... (GetEvent 32767 ibEvent) ...
                                                 (if (self dispatchEvent: ibEvent) (break))))

    While that loop runs, `Game:doit` never gets a cycle. `Game:doit` is BOTH the thing that
    performs `(if (!= global13 global11) (self newRoom: global13))` AND the thing that hands
    events to the room, so with the bar up a teleport is inert and every click is eaten.

    The scripted-input transport starts its virtual mouse at the top left, so the bar comes up by
    itself before a probe has done anything. Measured, one variable at a time:

        room 206, then 6s of game time      -> global11 = 1    (bar state $0420, i.e. shown)
        one `move 160 150` step             -> global11 = 206  (bar state $0404)

    ⭐ And this is exactly why LA6 passed while the first market row did not. `offer_script`
    happens to begin with a `move` step, and a move to open ground is what
    `IconBar:dispatchEvent` reads as "the mouse left the bar" -- it returns 1 and breaks the
    modal loop. LA6 dismissed the bar as a side effect of aiming. `goto` has nothing to aim, so
    nothing ever dismissed it, and every market row inherited that.
    """
    c.cmd("script clear")
    c.cmd("script add t=+200 move %d %d" % at)
    c.cmd("script add t=+%d mark %s" % (wait, tag))
    c.cmd("script add t=+%d break" % (wait + 100))
    c.resume(seconds=60, instructions=3000000)
    return c.wait_mark(tag, timeout=10)


def idle_windows(c):
    """How many SCI Windows are open when nothing is being said.

    A message box IS a Window, so "is a box up?" is `len(c.windows()) > this`. Measured once per
    session in a room known to be quiet rather than assumed, because it is a property of the game
    (KQ5 keeps its picture port in the window list; a game that does not would answer 0)."""
    return getattr(c, "_kq5_idle_windows", 1)


def _run(c, tag, key=None, wait=1200, settle=1200):
    """Give the game a measured stretch of GAME time, optionally pressing one key inside it.

    ⛔ The mouse is parked first even when nothing is pressed. If the click that opened a box
    left the pointer in the icon bar's top strip, the bar -- not the box -- is what receives the
    next Return: it selects an icon, the box stays, and the arm behind it stays parked. A move
    does not dismiss a box (`Dialog::doit` ends on a click or a Return, not on motion), so the
    park costs nothing but rules that out. See park_mouse."""
    c.cmd("script clear")
    c.cmd("script add t=+200 move %d %d" % PARK)
    if key:
        c.cmd("script add t=+%d key %s" % (wait, key))
    c.cmd("script add t=+%d mark %s" % (wait + settle, tag))
    c.cmd("script add t=+%d break" % (wait + settle + 100))
    c.resume(seconds=60, instructions=3000000)
    return c.wait_mark(tag, timeout=10)


def _press_return(c, tag, wait=1200, settle=1200):
    return _run(c, tag, key="return", wait=wait, settle=settle)


def box_open(c):
    """Is a message box on screen? One more Window than the room keeps when it is quiet."""
    return len(c.windows()) > idle_windows(c)


def drain_boxes(c, tag, max_boxes=12, log=print):
    """Dismiss every message box that is actually OPEN, and return how many there were.

    ⭐ The count is READ, not predicted. `window_list` names the open Windows, so this presses
    Return once per box that exists instead of once per box a test plan expects -- and both ways
    of getting that number wrong were observed to fake a guard result:

      one too FEW  -- the arm stays parked at `Dialog::doit` and its effects land in the NEXT
                      attempt's window, which reads exactly like a guard that did not fire
      one too MANY -- the spare Return starts a FRESH offer, because the item is still on the
                      cursor, which reads like a guard that fired twice

    Returns (said, boxes). `said` is everything the game printed while draining.
    """
    said, n = [], 0
    while n < max_boxes:
        if not box_open(c):
            break
        n += 1
        _press_return(c, "%s_b%d" % (tag, n))
        said += c.said()
    else:
        log("  ⚠️ still a box open after %d dismissals -- something is talking in a loop" % n)
    return said, n


def settle_room(c, tag="settle", rounds=40, log=print):
    """Run the room until it is IDLE, dismissing whatever it says on the way.
    Returns (said, boxes).

    ⛔ Every market arm sits under `(not (global2 script:))`, so an offer made while the room is
    still running a script of its own is dropped in SILENCE -- indistinguishable, from outside,
    from a guard that did not fire. And the rooms that matter greet you at length: walking into
    the bakery starts `walkInScript` -> `doWinners`, a 22-state cutscene of dialogue boxes,
    `(= cycles 15)` pauses and two characters walking off, and only its successor `greet` ends
    with `(client setScript: 0)`.

    ⛔ So this cannot be a fixed number of Returns. Half of what the room is waiting for is TIME,
    not input: a round with no box open presses nothing and simply gives the room cycles.
    """
    said, boxes = [], 0
    for i in range(rounds):
        script = c.send(c.gaddr(2), "script")[0]
        if not script and not box_open(c):
            if i:
                log("  room %s settled after %d round(s), %d box(es)" % (here(c), i, boxes))
            return said, boxes
        if box_open(c):
            _press_return(c, "%s%d" % (tag, i))
            boxes += 1
        else:
            _run(c, "%s%d" % (tag, i))              # the room wants CYCLES, not a keystroke
        said += c.said()
    log("  ⚠️ room %s never went idle in %d rounds (global2 script: = %s)"
        % (here(c), rounds, c.send(c.gaddr(2), "script")[0]))
    return said, boxes


def boot(c, rounds=12, log=print, teleport=False):
    """Get to a playable room. Returns the room we landed in.

    Over the PIPE there is nothing to click: the session starts at a debugger prompt before the
    game has run an instruction, so the intro is simply never entered -- run the VM briefly to
    let script 0 initialise, then go straight to the first playable room. That removes the whole
    Sierra-logo / "Skip it" dance, which was the most fragile part of the keystroke path and the
    one that needed a screenshot to debug.
    """
    import time
    if c.stdin_mode:
        if not teleport:
            # PLAY the intro rather than jumping over it: alternate short bursts with clicks on
            # the two decision points. Teleporting lands in a room whose state was never built by
            # the intro, and that difference is not always visible until much later.
            for i in range(rounds):
                c.resume(2.5, during=lambda: [c.click(*PLAYED_YES), c.click(*SKIP_IT)], at=0.8)
                r = c.room()
                log("  intro round %d: room %s" % (i, r))
                if r == FIRST_PLAYABLE:
                    c.resume(3)
                    return r
            log("  intro did not settle; falling back to a teleport")
        c.resume(2)                                # let script 0 come up
        c.cmd("room %d" % FIRST_PLAYABLE)
        c.resume(3)
        if getattr(c, "input_script", None):
            # ⛔ The very first thing after a boot has to be to get the icon bar out of the way,
            # or nothing that follows runs -- see park_mouse. Everything downstream of this line
            # depends on `Game:doit` getting cycles.
            park_mouse(c, log=log)
            c._kq5_idle_windows = len(c.windows())     # the quiet-room baseline, MEASURED
            log("  idle window count = %d (a message box is one MORE than this)"
                % c._kq5_idle_windows)
            settle_room(c, tag="boot", log=log)
        room = here(c)
        log("  booted (pipe, teleport) to room %s" % room)
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


def goto(c, room, settle=6.0, tries=3, force=False, log=print):
    """Teleport, handling the room-5 shops, and VERIFY that the game moved.

    `room N` only writes global 13. KQ5's `Game:doit` polls
    `(if (!= global13 global11) (self newRoom: global13))` every cycle, so the game performs the
    change itself -- but only while `Game:doit` is getting cycles at all, which the icon bar's
    modal loop can prevent outright (see park_mouse). What it can never reach is something that
    is not a room; for those this sets up room 5 instead and reports the room actually landed in.

    ⛔ The check is `here(c)` (global 11), never `c.room()` (global 13). Global 13 is the room
    ASKED for, so reading it back after writing it confirms nothing: it reported a bakery that
    the game had not moved to, and every offer aimed into that bakery was landing in room 1.
    """
    target, region = room, None
    if room in SHOP_REGIONS:
        region = SHOP_REGIONS[room]
        target = SHOP_ROOM
        log("  script %d is a REGION of room %d; global313=%d" % (room, SHOP_ROOM, region))

    if here(c) == target and region is None and not force:
        # Already there, and there is no region to re-pick: re-entering would only replay the
        # room's welcome cutscene, which costs a minute of game time per row.
        log("  already in room %d" % target)
        settle_room(c, log=log)
        return target
    if region is not None:
        c.setg(313, region)

    # ⛔ A room change to the room you are ALREADY in is a no-op, because the game acts on global
    # 13 only when it differs from global 11. That matters most for the shops: which one you are
    # in is chosen by global313 AT init, so `room 5` while standing in the tailor silently leaves
    # you in the tailor, with `?toyMaker` simply not existing. Bounce out and back so init reruns.
    if here(c) == target:
        # ⛔ A room change to the room you are ALREADY in is a no-op, so bounce out and back --
        # which is also how a room's LOCALS get re-initialised. Rows in the same room otherwise
        # inherit each other's leftovers (the cat remembers it has been fed).
        log("  already in room %d; bouncing via %d so init re-runs" % (target, BOUNCE_ROOM))
        _land(c, BOUNCE_ROOM, settle, tries, log)

    got = _land(c, target, settle, tries, log)
    log("  room %d -> %s" % (target, got))
    settle_room(c, log=log)
    return got


def _land(c, target, settle, tries, log):
    """Ask for `target` and keep the game running until global 11 says it arrived.

    ⛔ A MESSAGE BOX BLOCKS A TELEPORT. `Game:doit` is what performs
    `(if (!= global13 global11) (self newRoom: global13))`, and while a box is up the game is
    inside `Dialog::doit` instead. Room 32 raises one on its own -- it is the mountain where
    Graham starves, and its warning came up a few seconds after the room settled -- and once
    that box was on screen NOTHING moved again: twelve consecutive rows reported "the game never
    entered room N" and read as twelve broken guards. Dismissing the box freed it immediately.
    """
    for attempt in range(tries):
        if getattr(c, "input_script", None):
            park_mouse(c, log=log)                 # a shown icon bar swallows the whole teleport
            drain_boxes(c, "land%d" % attempt, log=log)   # and so does an undismissed box
        c.cmd("room %d" % target)
        c.resume(settle)
        c.open()
        if here(c) == target:
            return target
        log("  room %d did not take (global11=%s, global13=%s); attempt %d/%d"
            % (target, here(c), c.gint(13), attempt + 1, tries))
    raise RuntimeError("the game never entered room %d (global11=%s, global13=%s)"
                       % (target, here(c), c.gint(13)))


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
    # ONE long free run with the click inside it. Proven on the stock binary: the interaction
    # completes exactly as in real play. ⛔ Do not chop this into short bursts -- see below.
    c.resume(seconds, during=act, at=1.5)
    # ⛔ USE THE STOCK BINARY FOR THIS. On the text-console build the interaction stops dead at
    # the print, every time, in every mode -- proven by running this identical code on both:
    #     stock binary        after: has_pie=0   <- eaten, i.e. the arm completed
    #     text-console build  after: has_pie=1   <- parked at the print
    # No amount of countdown tuning, dismissal clicking, real-time waiting or event pumping
    # changed the second one. The pipe transport is for STATE; interaction needs the stock build.
    return c.said(), (cx, cy)


def arm_item(c, item, log=print):
    """Put `item` on the cursor as the USE action, the way Inventory:showSelf leaves it.

    ⛔ Replicate the tail of `Inventory::showSelf`, do not poke curIcon/curInvIcon by hand:

        (if (not (global69 curInvIcon:)) (global69 enable: (global69 useIconItem:)))
        (global69 curIcon: ((global69 useIconItem:) cursor: (curIcon cursor:) yourself:)
                  curInvIcon: curIcon)

    The icon that belongs in curIcon is the bar's OWN `useIconItem`, not `icon4` looked up by
    name; the difference does not show until execution gets far enough to matter, as
    `IconBar::dispatchEvent: Send to invalid selector claimed of object at <the item>`.
    """
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
    return use_icon


def offer_script(c, target, item, tag, boxes=None, settle=2500, delay=1000, log=print):
    """Hand `item` to `target` with a SCRIPTED CLICK, dismiss whatever it says, and come back at
    a known point in GAME time. Returns (said, virtual_time, aim).

    This is the shape every guard row wants. Needs a build carrying
    tools/scummvm-patches/0004 and a session started with --input-script.

    ⭐ THE BOX COUNT IS MEASURED, not passed in. `drain_boxes` reads `window_list` and presses
    Return once per box that is actually open, so neither of the two ways of getting it wrong can
    happen any more: too few parks the arm at `Dialog::doit` and its effects land in the NEXT
    attempt's window (which reads as a guard that did not fire), too many starts a FRESH offer
    because the item is still on the cursor (which reads as a guard that fired twice). Both were
    observed while the count was a hand-written argument. `boxes`, if given, is an EXPECTATION
    from the emitted arm's shape and is only reported against -- it never drives the run.

    Dismissal is RETURN, not a click: a dismissing click would also be an offer wherever it
    lands, and SPACE does not dismiss at all.

    `tag` must be unique per attempt -- a mark from a previous attempt is still in the buffer and
    would satisfy the wait instantly.

    `aim` carries where the click went and the target's box before and after, so a caller can
    tell an offer that MISSED apart from a guard that did not fire.
    """
    arm_item(c, item, log=log)
    # ⛔ Re-read the box for EVERY offer. Half these targets are Actors, and an Actor walks.
    box = nsrect(c, target, log=log)
    cx = (box["nsLeft"] + box["nsRight"]) // 2
    cy = (box["nsTop"] + box["nsBottom"]) // 2
    c.said()                                            # drop the setup's chatter
    base = len(c.windows())
    if base != idle_windows(c):
        log("  ⚠️ %d window(s) open before the offer, expected %d -- something is still talking"
            % (base, idle_windows(c)))

    # Authored HERE, not in a file: where to click is a live nsRect.
    # Step 1 is a PARK, not an approach: it puts the mouse below the icon bar's strip so the
    # bar's modal loop is not holding the game when the click arrives (see park_mouse). `click`
    # emits its own move, so nothing is lost by aiming this step elsewhere.
    c.cmd("script clear")
    c.cmd("script add t=+200 move %d %d" % PARK)
    c.cmd("script add t=+%d click %d %d" % (delay, cx, cy))
    c.cmd("script add t=+%d mark %s_c" % (delay + settle, tag))
    c.cmd("script add t=+%d break" % (delay + settle + 100))
    log("  click (%d,%d) on %s" % (cx, cy, target))
    # The countdown is only a backstop: `break` is what should bring us back. If it does not,
    # wait_mark says so instead of the probe hanging.
    c.resume(seconds=60, instructions=3000000)
    at = c.wait_mark("%s_c" % tag, timeout=10)
    said = c.said()
    drained, n = drain_boxes(c, tag, log=log)
    said += drained
    if boxes is not None and n != boxes:
        log("  ⚠️ %d box(es) raised, the arm's shape predicted %d" % (n, boxes))
    log("  -> %d box(es) dismissed at t=%d" % (n, at))
    return said, at, {"aimed": (cx, cy), "boxes": n, "box_before": box,
                      "box_after": nsrect(c, target, tries=1, log=lambda *a: None)}


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
