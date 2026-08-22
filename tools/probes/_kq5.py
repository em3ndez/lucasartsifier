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


def goto(c, room, settle=6.0, log=print):
    """Change rooms the way the GAME does.

    ⛔ The console's `room N` only writes global 13. It does not load the script, does not run
    `init:`, and does not touch `prevRoom` -- so the number changes and nothing else does. KQ5's
    own room change is `(global2 newRoom: N)`, so that is what a probe should send. It is also
    what makes teleporting out of the intro work at all."""
    c.cmd("send %s newRoom %d" % (c.gaddr(2), room))
    c.resume(settle)
    c.open()
    got = c.room()
    log("  newRoom %d -> room %s" % (room, got))
    return got
