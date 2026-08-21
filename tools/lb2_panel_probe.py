"""LB2: boot the patched game, reach play, open the settings panel, screenshot it.

Run through tools/drive_scummvm.py (which supplies shot/move/click/key/time):

    .venv-x/bin/python tools/drive_scummvm.py --game /tmp/gt/dagger --id laurabow2 \
        --title Laura --script tools/lb2_panel_probe.py

The BOOT shot is load-bearing on its own: LB2 v1 crashed at `LB2::init` because its recompiled
script 0 renumbered `WrapMusic` (docs/LB2-ORACLE.md §7ak), and this patch ships script 0 again.

⛔ --game must be a COPY.
"""
import os
import time

OUT = os.environ.get("PANEL_OUT", "/tmp/panel_shots")
TAG = os.environ.get("PANEL_TAG", "lb2")
os.makedirs(OUT, exist_ok=True)


def snap(name):
    p = os.path.join(OUT, "%s-%s.png" % (TAG, name))
    shot(p)                                                    # noqa: F821 -- driver namespace
    print("shot", p)
    return p


time.sleep(12)
snap("00-boot")
# LB2 opens with a long cinematic. Escape skips a beat at a time; alternate with a click
# because some beats wait on a click rather than a key.
for i in range(30):
    key("Escape"); time.sleep(0.8)
    click(160, 120); time.sleep(0.8)
snap("01-play")
move(160, 2); time.sleep(1.5)         # the pointer at the top drops the icon bar
snap("02-iconbar")
click(267, 15); time.sleep(2.5)       # the sliders icon -- LB2's `showControls`
snap("03-panel")
click(85, 182); time.sleep(2.5)       # the guard control, under PLAY
snap("04-chooser")
click(160, 121); time.sleep(1.5)      # LITE
snap("05-after-pick")
move(160, 2); time.sleep(1.5)
click(267, 15); time.sleep(2.5)       # reopen: the plate must read the new mode
snap("06-panel-again")
