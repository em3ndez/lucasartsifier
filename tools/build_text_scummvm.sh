#!/bin/sh
# Build a ScummVM whose SCI debugger reads STDIN instead of the game window.
#
# WHY: the default transport in `sci_console.py` types commands into the game with XTEST, and
# over a long run it drops characters. The signature failure is a console sitting at `) versi`
# -- the sentinel's last character AND its Return lost, the line never submitted, the driver
# waiting for a reply that cannot come. `--enable-text-console` removes typing from the command
# path entirely: the debugger does `fgets(stdin)` and prints a `debug> ` prompt, which is a
# delimiter no dropped keystroke can destroy.
#
# It also makes `debug_countdown N` usable: the debugger re-enters itself after N VM
# instructions, so handing control to the game and taking it back needs no keystroke either, and
# is deterministic rather than wall-clock.
#
#   sh tools/build_text_scummvm.sh [builddir]
#   .venv-x/bin/python tools/sci_console.py --binary <builddir>/scummvm ...
#
# NOTE the source tree is a SPARSE, blob:none clone of scummvm/scummvm holding only engines/sci.
# This widens it to the full tree the first time (a few hundred MB) and leaves it that way.
# ⛔ It is GPL and gitignored -- never commit it.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/scummvm-ref"
BUILD=${1:-/tmp/scummvm-text-build}

[ -d "$SRC/common" ] || (cd "$SRC" && git sparse-checkout disable)

# The local debugging patch: without it the text console stops the engine dead while it waits
# for a line, and anything the game is waiting on in real time never finishes. See the patch
# header for the backtrace that proves it.
if ! (cd "$SRC" && git diff --quiet gui/debugger.cpp); then
    echo "gui/debugger.cpp already patched"
else
    (cd "$SRC" && git apply "$HERE/scummvm-patches/0001-text-console-keep-the-engine-alive-while-waiting.patch")
    echo "applied 0001-text-console-keep-the-engine-alive-while-waiting.patch"
fi

# SDL2 headers without root: the runtime lib is already installed, only the dev package is
# missing, and it can be unpacked into a prefix. Its `libSDL2.so` symlink points at a file that
# only the RUNTIME package ships, so it dangles and the linker silently falls back to the static
# libSDL2.a -- which then wants Wayland symbols nothing provides. Repoint the symlinks.
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
    --disable-all-engines --enable-engine=sci \
    --with-sdl-prefix="$P" --disable-debug --enable-release
nice -n 10 make -j"$(($(nproc) - 4))"
echo
echo "built: $BUILD/scummvm"
echo "use:   .venv-x/bin/python tools/sci_console.py --binary $BUILD/scummvm ..."
