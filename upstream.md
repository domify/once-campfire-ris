# Upstream

What this repo works around and should, once tested here, go to the
packages it depends on.

## iyi std/socket: `SO_REUSEPORT`

To use all cores, a server runs several kernel threads (or processes)
that listen on one port; on Linux each opens its own socket with
`SO_REUSEPORT` set before `bind`, and the kernel spreads the connections
across them.

`IyiSocket.listen` has no option for it. Until it does, domify/web's
`listen_reuse_port` (`web/server.ri`) builds the socket by hand from
`IyiSocket.__sys_socket`, `__sys_set_reuseaddr`, `__sys_bind`,
`__sys_listen` and its own `setsockopt(fd, SOL_SOCKET, 15, ...)`.

Proposal: `IyiSocket.listen(host, port, reuse_port: true)`, default
`false`. Crystal has the same as `TCPServer.new(host, port,
reuse_port: true)` and `HTTP::Server#bind_tcp(..., reuse_port: true)`.
Once it is in, `listen_reuse_port` becomes that one call.

Draft for the author:

> **`IyiSocket.listen`: option for `SO_REUSEPORT`**
>
> To use all cores, a server needs several kernel threads (or
> processes) listening on one port. On Linux each one opens its own
> socket with `SO_REUSEPORT` set before `bind`, and the kernel spreads
> incoming connections across them.
>
> `std/socket` can't do that yet; I build the socket by hand from
> `IyiSocket.__sys_*` plus my own `setsockopt`. Proposal:
> `IyiSocket.listen(host, port, reuse_port: true)`, default `false`, as
> Crystal's `TCPServer.new(host, port, reuse_port: true)`.
>
> With it, the Campfire messages page on the web package goes from one
> core to 8 threads: about 9,100 to 25,000 requests/s.

## domify/web: `Server#bind(..., reuse_port:)`

In `../rispacks/web` (d6295f1): `Server#bind(host,
port, reuse_port: true)` and a test that two servers share a port on
IPv4, IPv6 and a bracketed IPv6 host
(`web/server_lifecycle_test.ri`). Used by `bench/messages_page.ri`'s
`tape-threads` mode.

## iyi std/digest: SHA-256 at 125 MB/s (done)

`SHA256.hexdigest` over the 364 KB messages page takes 2.9 ms: it pads a
copy of the input into an `Array(UInt8)` and allocates the 64-word
schedule for every block. `Rack::ETag` digests every 200 body, so the kit
does too, and with it the app answered 250 requests/s instead of 1,800.
The app digests each cached fragment once instead
(`rils/template/recorded.ri`, `RecordedPage#etag`). Proposal: hash the string's
bytes in place, one schedule per call, and `SHA256.update` for input
that comes in parts.

## ris runtime: one spare tape a thread

Committed in `../ris`, not pushed: a thread kept one released tape
mapping warm, so when scopes were open at once - a handler that parks,
as the kit's action task does - all but one took a fresh mapping and
faulted in every page they wrote: 85 faults a request for the messages
page, 2,550 requests/s on one core. `IyiRegion` now keeps up to 64
first-size mappings a thread, newest first, each with its first MiB
resident, and drops them when the thread ends
(`test/ris/fibers/spares.ri`). The app: 3,950 requests/s.

## domify/sqlite: open in multi-thread mode

Committed in `../rispacks/sqlite`, not pushed: `SQLite3Connection.open`
passes `SQLITE_OPEN_NOMUTEX`, as rusqlite does, so SQLite does not lock
the connection on every call. A connection cannot be in two threads at
once (it is not `Share`; one thread's tasks take turns only where one
parks), so the serialized mode's lock guarded nothing. `mutexed?` and a
test say which mode a connection is in. Measured: no difference beyond
the noise, on one core or eight processes.

Committed in `../ris`, not pushed: `SHA256.hash_bytes` reads the
blocks where the string's bytes are, with the schedule and state on the
stack and the round constants made once; only the last block or two are
padded. The page: 2.9 ms to 1.1 ms. Checked on every length from 0 to 300
against Python's hashlib, and `bench/std_digest_exercise.sh` holds.

## ris runtime: a fiber list per thread

Committed in `../ris`, not pushed: every spawn and every fiber's end
linked the fiber into one list of all threads' fibers under the runtime
lock, which every thread's every task met at. Each thread now keeps its
own list (`IyiSchedulerState#fibers_head`); a fiber never leaves its
thread, and the collector reads the lists only while the others are
stopped. A stop is a signal that can land between two stores, so the
stores are ordered, the list is whole forwards after each, and the fiber
being linked waits in `registering` where the walk finds it. Eight
threads spawning and joining 200,000 tasks each: 775-817 ms to 161-179
ms. `test/ris/fibers/threads_spawn.ri` collects throughout four threads'
32,000 tasks; with registration broken it fails.

## ris runtime: GC helpers held to the cores the program leaves

Committed in `../ris`, not pushed. A collection beside the program
used every helper (cores less one); only Windows held them to the cores
the program's own threads leave. On Linux eight threads serving the page
on eight cores ran seven helpers beside them, 55 collections a second,
the helpers 12% of the samples. The rule is every platform's now
(`IyiMark.beside_program`), the sweep round's permits too, and Linux
wakes as many helpers as there are permits rather than all of them, each
of which spun 50 µs before parking again. Eight threads: 15,700-17,400 to
17,800-17,950 requests/s, CPU a request 481 to 406 µs. Binary trees
unchanged on one thread, 8-9% faster on four and eight. Every GC and
thread exercise holds.
