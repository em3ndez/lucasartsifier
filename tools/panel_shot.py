"""Open a game's settings panel and screenshot it -- the guard-picker's own look test.

Run through `drive_scummvm.py`, which supplies `shot/move/click/key/...`:

    .venv-x/bin/python tools/drive_scummvm.py --game /tmp/gt/kq5 --id kq5 \
        --script tools/panel_shot.py

Environment knobs (a script run by `drive_scummvm` takes no argv of its own):
  PANEL_OUT   where to write the shots (default: /tmp/panel_shots)
  PANEL_KEY   the key that opens the panel (default: F2, which is `controls` in SCI1/1.1)
  PANEL_TAG   filename prefix

⛔ Point `--game` at a COPY. This clicks around in a real game window.
"""
import os
import time

OUT = os.environ.get("PANEL_OUT", "/tmp/panel_shots")
TAG = os.environ.get("PANEL_TAG", "panel")
KEY = os.environ.get("PANEL_KEY", "F2")
os.makedirs(OUT, exist_ok=True)


def snap(name):
    p = os.path.join(OUT, "%s-%s.png" % (TAG, name))
    shot(p)                                                    # noqa: F821 -- driver namespace
    print("shot", p)
    return p


# Boot. SCI title/intro screens want a keypress or two before the game is interactive; the
# BOOT shot is the evidence that a patched script 0 did not crash on the way in.
time.sleep(9)
snap("00-boot")
for _ in range(6):
    key("Escape")                                              # noqa: F821
    time.sleep(1.2)
snap("01-after-escapes")
key(KEY)                                                       # noqa: F821
time.sleep(2.0)
snap("02-panel")
