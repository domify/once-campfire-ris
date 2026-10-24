# Rust port against ris

`run` copies the fixture of
[once-campfire-verification](https://github.com/basecamp/once-campfire-verification)
(`fixtures/default`) twice, serves one copy from the Rust port's release binary
(port 4401) and the other from ris (4402), signs in as David on both and compares:

- `compare.py`: about 60 pages, signed in and signed out: status, type,
  `Location` and body (CSRF tokens and the host removed). `WS` means the
  bodies differ only in whitespace;
- `compare2.py`: every `/assets` and Active Storage URL those pages reference,
  and the bot API;
- `blobs.py`: the Active Storage redirects followed to the file;
- `writes.py`: posting, boosting, a new room, involvement, searches, with ids
  and times masked, then the rows they wrote.

Differences known on 2026-10-18, where ris follows Rails: `/rooms/:id/settings`
(a route without a controller: 404, the Rust port 500), the empty lines Rails
leaves for `csrf_meta_tags` and `csp_meta_tag`, and the `turbo-visit-control`
meta on its own line. Ports inside base64 (QR codes) and transfer ids made at
request time differ by nature.

```sh
bench/compare/run          # VERIFICATION_ROOT, RUST_ROOT: the checkouts, beside this one by default
```
