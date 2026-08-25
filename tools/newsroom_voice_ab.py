"""A/B: drive stock LB2 and patched LB2 into the newsroom and count the VOICE calls.

Music was already proved identical at boot; what has to be compared is `kDoAudio` playback,
which is how an SCI1.1 CD game speaks. Launch scummvm ourselves so its stderr can be captured
(drive_scummvm sends it to /dev/null), then drive the window with the same helpers.
"""
import os, subprocess, sys, time
sys.path.insert(0, "/home/hayati/coding/sierra_softlock/tools")
import drive_scummvm as D

TAGS = (sys.argv[1:] or ["ab_stock", "ab_patched"])
INI = "/home/hayati/coding/sierra_softlock/tools/audio_ab.ini"
OUT = "/tmp/panel_shots"
os.makedirs(OUT, exist_ok=True)

for tag in TAGS:
    log = open("/tmp/voice_%s.log" % tag, "w")
    p = subprocess.Popen(["scummvm", "--config=" + INI, "--debugflags=Sound", "--debuglevel=3",
                          "-p", "/tmp/gt/" + tag, "--no-fullscreen", "laurabow2"],
                         stdout=log, stderr=subprocess.STDOUT)
    try:
        s = D.Screen("Laura")
        s.focus()
        time.sleep(10)
        for i in range(30):                       # through the cinematic into the newsroom
            s.key("Escape"); time.sleep(0.8)
            s.click(160, 120); time.sleep(0.8)
        # ...then HANDS OFF. Clicking skips a spoken line, so a probe that keeps clicking
        # measures its own timing, not the game. The newsroom conversation plays by itself.
        time.sleep(75)
        s.shot(os.path.join(OUT, "voice-%s.png" % tag))
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    print("done", tag)
