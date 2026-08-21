"""KQ5: boot the patched game, reach play, open the settings panel, screenshot it.

Run through tools/drive_scummvm.py (which supplies shot/move/click/key/time):

    .venv-x/bin/python tools/drive_scummvm.py --game /tmp/gt/kq5 --id kq5 \
        --title Quest --script tools/kq5_panel_probe.py

⛔ --game must be a COPY. The panel is opened from the ICON BAR (KQ5 has no menu bar and no
F-key for it): the bar drops when the pointer reaches the top of the screen, and the controls
icon's `select` is what runs `((ScriptID 755) show:)` (Main.sc).
"""
import os
import time

OUT = os.environ.get("PANEL_OUT", "/tmp/panel_shots")
TAG = os.environ.get("PANEL_TAG", "kq5")
os.makedirs(OUT, exist_ok=True)


def snap(name):
    p = os.path.join(OUT, "%s-%s.png" % (TAG, name))
    shot(p)                                                    # noqa: F821 -- driver namespace
    print("shot", p)
    return p


time.sleep(10)
snap("00-boot")                       # the title screen: proof the patched script 0 booted
click(184, 59); time.sleep(3)         # "Yes, I have played KQ5" -> skip the long intro
for i in range(10):                   # ...and skip whatever still plays
    key("Escape"); time.sleep(1.5)
snap("01-play")
move(160, 2); time.sleep(1.2)         # the pointer at the top drops the icon bar
snap("02-iconbar")
click(268, 12); time.sleep(2.5)       # the slider icon -- KQ5's `controls`
snap("03-panel")
# the guard control sits under PLAY; clicking it must close the panel and open the chooser
click(117, 162); time.sleep(2.5)
snap("04-chooser")
click(165, 111); time.sleep(1.5)      # LITE is the middle button of the three
snap("05-after-pick")
move(160, 2); time.sleep(1.2)
click(268, 12); time.sleep(2.5)       # reopen the panel: the plate must read the new mode
snap("06-panel-again")
