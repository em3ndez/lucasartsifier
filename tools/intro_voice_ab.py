"""Measure the ACT 1 INTRO's voices -- the part the newsroom probe skipped.

⛔ WHY THIS EXISTS. `voice_ab.py` pressed Escape and clicked 30 times to REACH the newsroom,
so everything it measured happened after the intro was thrown away. It scored the fixed build
8 == stock and I reported the voices fixed; the user was testing the intro, which that probe
never played. Same input, both builds, and NOTHING skipped.
"""
import os, subprocess, sys, time
sys.path.insert(0, "/home/hayati/coding/sierra_softlock/tools")
import drive_scummvm as D

TAGS = sys.argv[1:] or ["ab_stock", "ab_fixed"]
INI = "/home/hayati/coding/sierra_softlock/tools/audio_ab.ini"
OUT = "/tmp/panel_shots"
os.makedirs(OUT, exist_ok=True)

for tag in TAGS:
    log = open("/tmp/intro_%s.log" % tag, "w")
    p = subprocess.Popen(["scummvm", "--config=" + INI, "--debugflags=Sound", "--debuglevel=3",
                          "-p", "/tmp/gt/" + tag, "--no-fullscreen", "laurabow2"],
                         stdout=log, stderr=subprocess.STDOUT)
    try:
        s = D.Screen("Laura")
        s.focus()
        time.sleep(12)
        s.shot(os.path.join(OUT, "intro-%s-00.png" % tag))
        # ONE click to leave the title card, then HANDS OFF for the whole intro.
        s.click(160, 120)
        for i in range(1, 7):
            time.sleep(25)
            s.shot(os.path.join(OUT, "intro-%s-%02d.png" % (tag, i)))
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    n = sum(1 for l in open("/tmp/intro_%s.log" % tag) if "kDoAudio: play" in l)
    print("%-12s kDoAudio play = %d" % (tag, n))
