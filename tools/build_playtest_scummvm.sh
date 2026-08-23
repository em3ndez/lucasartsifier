#!/bin/sh
# Build the ScummVM this project's play tests run on: a TEXT console for state, and SCRIPTED
# INPUT on a virtual clock for interaction.
#
# ⭐ WHY BOTH IN ONE BINARY. The harness needs two things at once and they used to live in
# different builds. Reading and writing the VM -- globals, warn bits, `has:`, the printed
# sentence -- is the SCI console, and over a pipe (`--enable-text-console`) it is reliable in a
# way XTEST keystrokes never were. Performing an interaction is an EVENT, and the only transport
# that ever completed one was a real click into the game window, which needs a window, focus and
# wall-clock luck. `--enable-eventrecorder` plus scummvm-patches/0004 gives the second half
# without any of that: events are fed straight into the engine's own pipeline from a text script,
# on a clock that advances only when the engine asks the time.
#
#   sh tools/build_playtest_scummvm.sh [builddir]
#   .venv-x/bin/python tools/sci_console.py --binary <builddir>/scummvm \
#       --input-script <a script> --game <COPY> --id kq5 --script tools/probes/<probe>.py
#
# ⛔ tools/scummvm-ref is GPL and gitignored. Never commit it.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/scummvm-ref"
BUILD=${1:-/tmp/scummvm-playtest-build}

[ -d "$SRC/common" ] || (cd "$SRC" && git sparse-checkout disable)

# The patch stack, in order. 0002 must precede 0003 -- 0003 used to carry a copy of 0002's ImGui
# fix, which meant only one of them could ever apply; the copy is gone, so the stack composes.
# Each patch is skipped if its first file is already modified, so re-running is safe.
apply() {                                  # apply <patch-glob> <a file it touches>
    if (cd "$SRC" && git diff --quiet "$2"); then
        (cd "$SRC" && git apply "$HERE/scummvm-patches/$1")
        echo "applied $1"
    else
        echo "already applied: $1"
    fi
}
apply "0001-text-console-keep-the-engine-alive-while-waiting.patch" gui/debugger.cpp
apply "0002-eventrecorder-builds-without-imgui.patch"                gui/EventRecorder.h
apply "0003-optional-game-hash-gate-on-playback.patch"               base/commandLine.cpp
apply "0004-scripted-input-and-a-controllable-clock.patch"           base/main.cpp

# SDL2 headers without root: the runtime lib is installed, only the dev package is missing, and
# it unpacks into a prefix. Its `libSDL2.so` symlink points at a file only the RUNTIME package
# ships, so it dangles and the linker falls back to the static libSDL2.a -- which then wants
# Wayland symbols nothing provides. Repoint the symlinks.
SDL="$BUILD/sdl"
if [ ! -f "$SDL/prefix/usr/include/SDL2/SDL.h" ]; then
    mkdir -p "$SDL" && cd "$SDL"
    apt-get download libsdl2-dev
    dpkg-deb -x libsdl2-dev_*.deb prefix
    L="$SDL/prefix/usr/lib/x86_64-linux-gnu"
    ln -sf /usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0 "$L/libSDL2.so"
    ln -sf /usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0 "$L/libSDL2-2.0.so"
fi
P="$SDL/prefix/usr"

mkdir -p "$BUILD" && cd "$BUILD"
PATH="$P/bin:$PATH" \
CXXFLAGS="-I$P/include/x86_64-linux-gnu" \
LDFLAGS="-L$P/lib/x86_64-linux-gnu" \
  "$SRC/configure" \
    --enable-text-console \
    --disable-readline \
    --enable-eventrecorder \
    --disable-all-engines --enable-engine=sci \
    --with-sdl-prefix="$P" --disable-debug --enable-release
nice -n 10 make -j"$(($(nproc) - 4))"
echo
echo "built: $BUILD/scummvm"
echo "check: $BUILD/scummvm --help | grep script-input"
