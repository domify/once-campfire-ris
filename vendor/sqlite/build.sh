#!/usr/bin/env bash
# SQLite 3.53.2 as the Rust port links it: the amalgamation `rusqlite`'s
# `libsqlite3-sys` 0.38.2 bundles, compiled with its `bundled` flags
# (its build.rs) at `-O3`, into a static library. Link a ris build with it
# instead of the system's libsqlite3.so:
#
#   bash vendor/sqlite/build.sh
#   export IYI_LIBRARY_PATH=$PWD/vendor/sqlite/build
#   ris build config/main.ri -o campfire --release
#   ris test
#
# IYI_LIBRARY_PATH puts this directory ahead of the system's (`-L`), and
# `-lsqlite3` finds `libsqlite3.so` here: a linker script naming the static
# archive and the libm its FTS5 ranking needs, so nothing else has to be
# said on the link line. The source comes from the cargo registry's copy (SQLITE_SRC
# to point elsewhere) and is checked against the file the Rust port built.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
src=${SQLITE_SRC:-$(ls -d "$HOME"/.cargo/registry/src/*/libsqlite3-sys-0.38.2/sqlite3 2>/dev/null | head -1)}
want=0a409f1633283fa31a9126b11fbfd64a1991c5d30defad07e5745d4667f5e23d
if [ -z "$src" ] || [ ! -f "$src/sqlite3.c" ]; then
  echo "no sqlite3.c: set SQLITE_SRC to libsqlite3-sys 0.38.2's sqlite3 directory" >&2
  exit 1
fi
got=$(sha256sum "$src/sqlite3.c" | cut -d' ' -f1)
if [ "$got" != "$want" ]; then
  echo "$src/sqlite3.c is not SQLite 3.53.2 as libsqlite3-sys 0.38.2 bundles it ($got)" >&2
  exit 1
fi
mkdir -p "$here/build"
${CC:-cc} -O3 -w -fPIC -ffunction-sections -fdata-sections -c "$src/sqlite3.c" -o "$here/build/sqlite3.o" \
  -DSQLITE_CORE \
  -DSQLITE_DEFAULT_FOREIGN_KEYS=1 \
  -DSQLITE_ENABLE_API_ARMOR \
  -DSQLITE_ENABLE_COLUMN_METADATA \
  -DSQLITE_ENABLE_DBSTAT_VTAB \
  -DSQLITE_ENABLE_FTS3 \
  -DSQLITE_ENABLE_FTS3_PARENTHESIS \
  -DSQLITE_ENABLE_FTS5 \
  -DSQLITE_ENABLE_JSON1 \
  -DSQLITE_ENABLE_LOAD_EXTENSION=1 \
  -DSQLITE_ENABLE_MEMORY_MANAGEMENT \
  -DSQLITE_ENABLE_RTREE \
  -DSQLITE_ENABLE_STAT4 \
  -DSQLITE_SOUNDEX \
  -DSQLITE_THREADSAFE=1 \
  -DSQLITE_USE_URI \
  -DHAVE_USLEEP=1 \
  -DHAVE_ISNAN \
  -D_POSIX_THREAD_SAFE_FUNCTIONS \
  -DHAVE_LOCALTIME_R
rm -f "$here/build/libsqlite3-3.53.2.a"
ar rcs "$here/build/libsqlite3-3.53.2.a" "$here/build/sqlite3.o"
rm -f "$here/build/sqlite3.o" "$here/build/libsqlite3.a"
printf 'INPUT ( %s -lm )\n' "$here/build/libsqlite3-3.53.2.a" > "$here/build/libsqlite3.so"
echo "$here/build/libsqlite3.so"
