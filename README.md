# once-campfire-ris

Campfire ported to ris.

## Building

Rich text (sanitizing, auto-linking and mentions in message bodies) parses
HTML with htmlparse, a ris module checked out beside this repository at
`../rispacks/htmlparse`, as the other modules `ris.mod` names are:

```sh
ris build config/main.ri -o campfire --release
./campfire DB SECRET_KEY_BASE PORT [THREADS | shared]
```

An empty `DB` gets the schema on first start (`db:prepare`), and the
first visit sets up the account. `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`
(urlsafe Base64) turn Web Push on.

## Running

What it needs on the machine besides itself:

- `vips` and `ffmpeg`/`ffprobe`, for image variants, video previews and
  attachment analysis, as Active Storage uses them;
- `curl`, for outbound HTTP (webhooks, Web Push, link previews): ris'
  sockets speak no TLS. Requests are pinned to the address the private
  network guard checked (`--resolve`);
- `getent`, for name lookups: ris' sockets resolve numeric addresses only.

Action Cable is at `/cable`. With `THREADS` or `shared`, each thread or
process has its own connections, and broadcasts reach the others through
`DB-cable.sqlite3`, polled every 50 ms, as `solid_cable` does for Rails.
Jobs (`Room::PushMessageJob`, `Bot::WebhookJob`, purges, analysis) run in
the process, on each thread's own queue; nothing retries, as in the
reference.

## Speed

The busiest page, `GET /rooms/:id/messages?before=`: 40 messages, 364,500
bytes of HTML, a signed session cookie, the same SQLite database. Every
server below sends the same bytes, checked with `cmp` against the Rust
port's page before each run. Measured one after the other on 2026-10-24
with ris `6ae8a8e6c`, on a Ryzen 7 PRO 6850U (8 cores, 16 threads): the
server on core 0, or on CPUs 0-7 (four cores, two threads each),
`bench/loadgen` on the other four cores. Requests/s is the median of three
10 s runs with 64 connections; median and fastest with one connection;
slowest is p99 at 64 connections; memory is peak RSS. Details and how to
run it in [bench/README.md](bench/README.md).

### The whole app

Routes, authentication, the room check, the page query, the fragment
cache, the response cache and `fresh_when`, as Rails'
`MessagesController#index` does them (`config/main.ri`; the Rust port's
release binary).

One core:

| | ris | Rust | Rails¹ |
|---|---|---|---|
| Requests/s | 8,343 | 7,054 | 444 |
| Median | 0.164 ms | 0.221 ms | 5.5 ms |
| Fastest | 0.142 ms | 0.203 ms | - |
| Slowest (p99) | 9 ms | 16 ms | 226 ms |
| Memory | 54 MB | 51 MB | 309 MB |

Eight CPUs (ris as 8 processes on one port, `shared`, or as 8 threads in
one process):

| | ris, 8 processes | ris, 8 threads | Rust |
|---|---|---|---|
| Requests/s | 33,000 | 29,786 | 23,406 |
| Median | 0.165 ms | 0.168 ms | 0.239 ms |
| Fastest | 0.142 ms | 0.147 ms | 0.208 ms |
| Slowest (p99) | 6-8 ms | 7-9 ms | 6 ms |
| Memory | 428 MB (8 × 53) | 141 MB | 67 MB |

¹ From the Rust port's `bench/results/final-20260927/report.md`, another
machine and gzip on: an approximate comparison only.

### The page alone

The same page from the same database and fragment cache, without the
app around it: `bench/messages_page.ri` (ris on the web package, the
page sent from the tape) and `bench/go` (`net/http`).

| | ris, 1 core | Go, 1 core | ris, 8 threads | Go, `GOMAXPROCS=8` |
|---|---|---|---|---|
| Requests/s | 8,443 | 4,612 | 30,153 | 10,949 |
| Median | 0.171 ms | 0.379 ms | 0.180 ms | 0.466 ms |
| Fastest | 0.150 ms | 0.204 ms | 0.151 ms | 0.233 ms |
| Slowest (p99) | 9-11 ms | 193-332 ms | 7-9 ms | 26-28 ms |
| Memory | 21 MB | 16 MB | 60 MB | 60 MB |
