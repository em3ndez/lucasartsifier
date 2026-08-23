#!/usr/bin/env python3
"""Talk to ScummVM's SCI debugger in TEXT, with nobody at the keyboard.

`drive_scummvm.py` drives the game the way a player does -- mouse, keys, screenshots -- and its
only oracle is a picture. This one is the other half: the SCI console is a full read/write
window onto the running VM (`vmvars`, `send`, `vo`, `bpk`, `room`), and every line it prints is
MIRRORED TO STDOUT even though the console itself is drawn in the game window. So the loop is:

    keystrokes in (XTEST)  ->  console command  ->  answer on ScummVM's stdout

which is machine-readable text at both ends. No OCR, no screenshot diffing, and no rebuild of
ScummVM -- the stock 2.8.0 Debian binary does this today (verified 2026-08-22).

    .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
        --script tools/probes/kq5_toymaker.py

The script file runs with `c` (this session) in its namespace, plus `time`.

Notes paid for in blood:
  * The console is MODAL -- while it is open the game is frozen. `c.resume()` ("go") lets it
    run; `c.open()` (Ctrl+Alt+D) gets it back.
  * `room N` only writes global 13. The room does not change until the game LOOP runs, so a
    teleport is: `room N`, `resume()`, wait, `open()`.
  * Output is delimited with a sentinel command, not by guessing when the game went quiet.
  * Point `--game` at a COPY. Never at the player's installed game.
"""
import argparse
import atexit
import os
import re
import signal
import subprocess
import sys
import time

try:
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    from PIL import Image
except ImportError as e:                         # the rest of the repo is stdlib-only on purpose
    raise SystemExit(
        "%s -- run this from the venv:\n"
        "    python3 -m venv .venv-x && .venv-x/bin/pip install python-xlib pillow\n" % e)

GAME_W, GAME_H = 320, 200

# XTEST needs a keysym NAME per character; the console takes commands in ASCII.
_SHIFTED = {":": "colon", "?": "question", "!": "exclam", "$": "dollar", "*": "asterisk",
            "(": "parenleft", ")": "parenright", "_": "underscore", "@": "at",
            "#": "numbersign", "%": "percent", "&": "ampersand", "+": "plus",
            '"': "quotedbl", "<": "less", ">": "greater", "{": "braceleft",
            "}": "braceright", "|": "bar", "~": "asciitilde", "^": "asciicircum"}
_PLAIN = {" ": "space", "-": "minus", ".": "period", ",": "comma", "/": "slash",
          "=": "equal", ";": "semicolon", "'": "apostrophe", "[": "bracketleft",
          "]": "bracketright", "\\": "backslash", "`": "grave", "\n": "Return"}

# A command whose answer is a fixed, unmistakable line. Every `cmd()` ends with this, so the
# reader knows the answer is complete instead of waiting out a silence that may never come.
# Short, because every character is an XTEST keystroke and every keystroke can be lost.
_SENTINEL = "version"
_SENTINEL_RE = re.compile(r"Game ID:")


_LIVE = []


def _register(c):
    """Every launched game, so `atexit` and the signal handlers can reach it."""
    if not _LIVE:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                signal.signal(sig, _bail)
            except (ValueError, OSError):         # not the main thread -- atexit still covers us
                pass
        atexit.register(_cleanup)
    _LIVE.append(c)


def _cleanup():
    while _LIVE:
        try:
            _LIVE.pop().stop()
        except Exception:                         # noqa: BLE001 -- teardown must not raise
            pass


def _bail(signum, frame):
    _cleanup()
    raise SystemExit(128 + signum)


def stale_instances():
    """PIDs of games a PREVIOUS driver run leaked -- matched on `sci_console` in the command
    line, so the player's own ScummVM is never in the list and never killed."""
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout
    except Exception:                             # noqa: BLE001
        return []
    return [int(ln.split(None, 1)[0]) for ln in out.splitlines()
            if "scummvm" in ln and "sci_console" in ln and "ps -eo" not in ln]


class Console:
    def __init__(self, game, game_id, title=None, ini=None, log=None, display_name=":0"):
        self.game, self.id = os.path.abspath(game), game_id
        self.title = title or game_id
        self.ini = ini or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "sci_console.ini")
        self.log_path = log or os.path.join("/tmp", "sci_console_%d.log" % os.getpid())
        self.display_name = display_name
        self.proc = self.d = self.win = None
        self._fh = None
        self._said_buf = ""
        self.transcript = []

    # ---- lifecycle ---------------------------------------------------------------
    def start(self, attach_at_start=False, timeout=60):
        if not os.path.exists(self.ini):
            with open(self.ini, "w") as f:
                f.write("[scummvm]\nfullscreen=false\nscale_factor=2\nmusic_driver=null\n"
                        "music_volume=0\nsfx_volume=0\nspeech_volume=0\n")
        env = dict(os.environ, DISPLAY=self.display_name)
        # No graphics-backend flag on purpose: nothing here needs one, and the CPU problem it
        # was once added for (a pinned box) was LEAKED instances, which `stop()` now prevents.
        argv = ["scummvm", "--config=" + self.ini, "-p", self.game, "--no-fullscreen"]
        if attach_at_start:
            argv.append("--debugflags=OnStartup")
        argv.append(self.id)
        self._fh = open(self.log_path, "wb")
        # Its OWN process group, so teardown can kill the whole thing even if ScummVM has
        # forked helpers, and a stray kill can never reach the caller's shell.
        self.proc = subprocess.Popen(argv, stdout=self._fh, stderr=subprocess.STDOUT, env=env,
                                     start_new_session=True)
        _register(self)
        self._reader = open(self.log_path, "r", errors="replace")
        self.d = display.Display(self.display_name)
        root = self.d.screen().root
        deadline = time.time() + timeout
        while time.time() < deadline and self.win is None:
            self.win = self._find(root, self.title)
            if self.win is None:
                time.sleep(0.5)
        if self.win is None:
            self.stop()
            raise SystemExit("no window whose title contains %r appeared" % self.title)
        g = self.win.get_geometry()
        self.size = (g.width, g.height)
        t = self.win.translate_coords(root, 0, 0)
        self.origin = (-t.x, -t.y)
        self.focus()
        return self

    def _find(self, w, needle):
        try:
            for c in w.query_tree().children:
                n = c.get_wm_name()
                if n and needle.lower() in n.lower():
                    return c
                r = self._find(c, needle)
                if r:
                    return r
        except Exception:                        # noqa: BLE001 -- window died mid-walk
            pass
        return None

    def stop(self):
        """Tear the game down. Safe to call twice, and called from `atexit` and on SIGTERM --
        `timeout 300 python sci_console.py ...` sends SIGTERM to the DRIVER, and without a
        handler Python dies before any `finally`, orphaning ScummVM. Five of those ran at once
        before this was fixed."""
        p, self.proc = self.proc, None
        if p is not None:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                if p.poll() is not None:
                    break
                try:
                    os.killpg(os.getpgid(p.pid), sig)
                except (ProcessLookupError, PermissionError):
                    break
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    continue
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # ---- raw input ---------------------------------------------------------------
    def focus(self):
        self.win.set_input_focus(X.RevertToParent, X.CurrentTime)
        self.d.sync()

    def _kc(self, name):
        return self.d.keysym_to_keycode(XK.string_to_keysym(name))

    def tap(self, name, mods=(), hold=0.018, settle=0.022):
        mk = [self._kc(m) for m in mods]
        for m in mk:
            xtest.fake_input(self.d, X.KeyPress, m)
        kc = self._kc(name)
        xtest.fake_input(self.d, X.KeyPress, kc)
        self.d.sync()
        time.sleep(hold)
        xtest.fake_input(self.d, X.KeyRelease, kc)
        for m in reversed(mk):
            xtest.fake_input(self.d, X.KeyRelease, m)
        self.d.sync()
        time.sleep(settle)

    def key(self, name, n=1, settle=0.25):
        for _ in range(n):
            self.tap(name, settle=settle)

    def type(self, s, settle=0.022):
        for ch in s:
            if ch in _SHIFTED:
                self.tap(_SHIFTED[ch], mods=("Shift_L",), settle=settle)
            elif ch in _PLAIN:
                self.tap(_PLAIN[ch], settle=settle)
            elif ch.isupper():
                self.tap(ch.lower(), mods=("Shift_L",), settle=settle)
            else:
                self.tap(ch, settle=settle)

    def move(self, gx, gy, settle=0.12):
        ax = self.origin[0] + int(gx * self.size[0] / float(GAME_W))
        ay = self.origin[1] + int(gy * self.size[1] / float(GAME_H))
        xtest.fake_input(self.d, X.MotionNotify, x=ax, y=ay)
        self.d.sync()
        time.sleep(settle)

    def click(self, gx=None, gy=None, hold=0.10, settle=0.25):
        if gx is not None:
            self.move(gx, gy)
        xtest.fake_input(self.d, X.ButtonPress, 1)
        self.d.sync()
        time.sleep(hold)
        xtest.fake_input(self.d, X.ButtonRelease, 1)
        self.d.sync()
        time.sleep(settle)

    # ---- the console -------------------------------------------------------------
    def _read_new(self):
        """Everything ScummVM has printed since the last call.

        ⛔ Whatever this returns is CONSUMED. `cmd()` reads the stream to find its sentinel, so
        anything the game printed in the meantime -- including every `bpk StrCpy log` line, i.e.
        all the dialogue -- was gone before `said()` could look at it, and the text oracle
        silently returned []. Keep a copy for `said()` to scan."""
        chunk = self._reader.read()
        if chunk:
            self._said_buf += chunk
        return chunk

    def shot(self, path):
        """The window's pixels, straight off the X server. For diagnosing a probe that got
        lost -- the console answers in text, but "why did it not open" is a picture."""
        raw = self.win.get_image(0, 0, self.size[0], self.size[1], X.ZPixmap, 0xFFFFFFFF)
        Image.frombytes("RGB", self.size, raw.data, "raw", "BGRX").save(path)
        return path

    def is_open(self, probes=3):
        """Ask the console something only it can answer. Repeated, because a DROPPED KEYSTROKE
        looks exactly like a closed console and the two want opposite responses."""
        for _ in range(probes):
            self.tap("Return")                     # flush any half-typed line (see cmd())
            self._read_new()
            self.type(_SENTINEL + "\n")
            deadline, out = time.time() + 4, ""
            while time.time() < deadline:
                out += self._read_new()
                if _SENTINEL_RE.search(out):
                    return True
                time.sleep(0.05)
        return False

    def open(self, settle=1.5, tries=4):
        """Ctrl+Alt+D, CONFIRMED open before returning.

        ⛔ Ctrl+Alt+D is a TOGGLE, not an idempotent "open". The first cut retried it whenever
        the confirmation did not come back -- so a dropped confirmation KEYSTROKE (not a dropped
        Ctrl+Alt+D) made the retry CLOSE the console that had just opened, and four retries
        converged on nothing. Hence: probe several times per press, and only press again when
        the console is genuinely not there.

        ⛔ The hotkey does nothing until the game is in its ordinary event loop. Pressing it over
        the Sierra logo, a cutscene, or a modal game dialog is simply ignored -- so `open()`
        failing usually means the BOOT is stuck, not that the console is broken, and the
        screenshot it writes on failure is the fastest way to see which."""
        # ⛔ Do not probe before pressing. `is_open` types into whatever has focus, and if the
        # console is CLOSED that goes to the GAME as gameplay keystrokes. Press first.
        for _ in range(tries):
            self.focus()
            self._read_new()
            self.tap("d", mods=("Control_L", "Alt_L"), settle=settle)
            if self.is_open():
                return "opened"
        try:
            self.shot("/tmp/sci_console_stuck.png")
            where = " -- window pixels in /tmp/sci_console_stuck.png"
        except Exception:                         # noqa: BLE001
            where = ""
        raise RuntimeError("the SCI console did not open (Ctrl+Alt+D x%d)%s" % (tries, where))

    _LOST = "Unknown command or variable"

    def cmd(self, line, timeout=25, tries=3):
        """Send one console command; return everything it printed.

        XTEST keystrokes are not guaranteed delivery -- the console polls the event queue once
        a frame, and a dropped character turns `vmvars g 403` into a command that does not
        exist. A lost keystroke is therefore RETRIED, not returned: silently answering
        "Unknown command" for a state read would make a probe report the wrong state."""
        for attempt in range(tries):
            # ⛔ FLUSH FIRST. A dropped Return leaves a half-typed line sitting at the prompt --
            # the console showed `) versi` with the sentinel's last character and its newline
            # both lost -- and the driver then waits forever for a reply to a line that was never
            # submitted, while every retry types INTO the leftover, making it worse. A bare
            # Return submits whatever is there (at worst an "Unknown command") and guarantees a
            # clean prompt. One keystroke; it turns a wedge into a retry.
            self.tap("Return")
            self._read_new()                      # discard anything still in flight
            self.type(line + "\n")
            self.type(_SENTINEL + "\n")
            out, deadline = "", time.time() + timeout
            while time.time() < deadline:
                out += self._read_new()
                if _SENTINEL_RE.search(out):
                    break
                time.sleep(0.05)
            answer = _SENTINEL_RE.split(out)[0].strip("\r\n")
            if self._LOST not in answer and answer.strip():
                self.transcript.append((line, answer))
                return answer
            time.sleep(0.4)
        self.transcript.append((line, answer))
        return answer

    # ---- what the game SAID ---------------------------------------------------------
    # Every literal the game prints is copied through kStrCpy, and ScummVM's kernel logger
    # decodes reference arguments as text (`scriptdebug.cpp: logParameters`). So `logkernel
    # StrCpy` turns the player-facing dialogue into lines on stdout -- which upgrades a guard
    # assertion from "the warned bit moved" to "it said *Better not. You are going to need
    # that.*", which is the sentence the test plan actually specifies.
    # Every quoted argument on a kStrCpy line -- both the destination's current contents and the
    # literal being copied in, because which position holds the new text varies with the call.
    _SAID_LINE = re.compile(r"^kStrCpy:.*$", re.M)
    _SAID_STR = re.compile(r"\('([^']*)'\)")

    def watch_text(self, on=True):
        return self.cmd("bpk StrCpy log" if on else "bc *")

    def said(self):
        """Every string the game moved through kStrCpy since the last call to this method.

        Reads the accumulator, not the stream -- see `_read_new`."""
        self._read_new()                           # pull anything still in flight
        buf, self._said_buf = self._said_buf, ""
        out = []
        for line in self._SAID_LINE.findall(buf):
            for s in self._SAID_STR.findall(line):
                if s not in out:                   # StrCpy names src and dest; same text twice
                    out.append(s)
        return out

    def resume(self, seconds=0.0):
        """`go` -- hand control back to the game, optionally for a fixed wall-clock slice."""
        self.type("go\n")
        if seconds:
            time.sleep(seconds)

    # ---- typed reads -------------------------------------------------------------
    _REG = re.compile(r"([0-9a-f]{4}):([0-9a-f]{4})", re.I)

    def gvar(self, n):
        """global<n> as (segment, offset). `vmvars g N` prints `global var N == ssss:oooo`."""
        m = self._REG.search(self.cmd("vv g %d" % n))
        if not m:
            raise RuntimeError("could not read global%d" % n)
        return int(m.group(1), 16), int(m.group(2), 16)

    def gint(self, n):
        """global<n> as a plain integer (segment 0 -- what every flag/counter global is)."""
        seg, off = self.gvar(n)
        return off

    def gaddr(self, n):
        seg, off = self.gvar(n)
        return "%04x:%04x" % (seg, off)

    def setg(self, n, value, tries=3):
        """Write a global and READ IT BACK.

        ⛔ A dropped keystroke does not always produce an error. `vv g 313 1` with one character
        lost is `vv g 31 1` -- a perfectly valid command that writes a DIFFERENT global, and the
        retry-on-"Unknown command" net does not see it. Verifying the write is the only thing that
        catches that class, and a corrupted write to an arbitrary global is exactly the kind of
        thing that kills a game several steps later."""
        for _ in range(tries):
            self.cmd("vv g %d %d" % (n, value))
            if self.gint(n) == value:
                return value
            time.sleep(0.3)
        raise RuntimeError("global%d would not take the value %d" % (n, value))

    def errors(self, n=6):
        """Recent ScummVM error lines from the game's own stdout -- the precise reason a probe's
        window vanished, which the X error alone never tells you."""
        try:
            txt = open(self.log_path, errors="replace").read()
        except Exception:                          # noqa: BLE001
            return []
        return [l for l in txt.splitlines()
                if "invalid selector" in l or l.startswith("[kq") or "Error" in l][-n:]

    def send(self, obj, selector, *args):
        """`send`, returning the printed 'Value returned' as an int where there is one."""
        out = self.cmd("send %s %s%s" % (obj, selector,
                                         "".join(" " + str(a) for a in args)))
        m = re.search(r"Value returned:\s*([0-9a-f]{4}):([0-9a-f]{4})", out, re.I)
        return (int(m.group(2), 16) if m else None), out

    def room(self):
        m = re.search(r"Current room number is (\d+)", self.cmd("room"))
        return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True, help="game directory -- USE A COPY")
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--script", required=True)
    ap.add_argument("--ini", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--attach", action="store_true",
                    help="--debugflags=OnStartup. NOTE: the console attaches before the event loop "
                         "exists, so it prints its banner but accepts NO input. Kept for "
                         "experiments; boot the game and use open() instead.")
    a = ap.parse_args(argv)
    stale = stale_instances()
    if stale and not a.keep:
        sys.stderr.write("note: killing %d leaked game(s) from an earlier run: %s\n"
                         % (len(stale), stale))
        for pid in stale:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(1)
    c = Console(a.game, a.id, a.title, a.ini, a.log).start(attach_at_start=a.attach)
    try:
        ns = {"c": c, "time": time, "__file__": os.path.abspath(a.script),
              "__name__": "__console__"}
        exec(compile(open(a.script).read(), a.script, "exec"), ns)   # noqa: S102
    finally:
        if not a.keep:
            c.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
