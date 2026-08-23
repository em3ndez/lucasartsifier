#!/bin/sh
# Build a ScummVM with the EVENT RECORDER enabled.
#
# ⭐ ScummVM already has what this project spent a long time approximating: record a session
# once (`--record-mode=record`), then replay it deterministically as many times as you like
# (`--record-mode=playback`, or `fast_playback`). Playback captures TIMING AND RNG, which is
# exactly the class of problem that made the console-driven interaction unreliable here. It
# also takes periodic screenshots and hashes them, so a replay has an oracle of its own.
#
# ScummVM's own runner is `devtools/run_event_recorder_tests.py` in the source tree: it plays
# every recording back under `fast_playback` and asserts the exit code, emitting xUnit XML.
#
# ⛔ It is OFF BY DEFAULT (`_eventrec=no` in configure), which is why no distro binary has
# `--record-mode` and why this was easy to miss.
#
#   sh tools/build_recorder_scummvm.sh [builddir]
#   <builddir>/scummvm --record-mode=record --record-file-name=la6 -p <game> kq5
#   <builddir>/scummvm --record-mode=fast_playback --record-file-name=la6 kq5
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/scummvm-ref"
BUILD=${1:-/tmp/scummvm-recorder-build}

[ -d "$SRC/common" ] || (cd "$SRC" && git sparse-checkout disable)
if (cd "$SRC" && git diff --quiet gui/EventRecorder.cpp); then
    (cd "$SRC" && git apply "$HERE/scummvm-patches/0002-eventrecorder-builds-without-imgui.patch")
    echo "applied 0002-eventrecorder-builds-without-imgui.patch"
fi

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
PATH="$P/bin:$PATH" CXXFLAGS="-I$P/include/x86_64-linux-gnu" LDFLAGS="-L$P/lib/x86_64-linux-gnu" \
  "$SRC/configure" --enable-eventrecorder \
    --disable-all-engines --enable-engine=sci \
    --with-sdl-prefix="$P" --disable-debug --enable-release
nice -n 10 make -j"$(($(nproc) - 4))"
echo
echo "built: $BUILD/scummvm   (has --record-mode, --record-file-name, --list-records-json)"
