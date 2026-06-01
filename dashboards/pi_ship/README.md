# Pi Flight Deck

Static dashboard for flying an Observer Fleet ship through the digits of pi.

Run from this directory for endless/on-demand pi streaming:

```powershell
python .\server.py --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

The dashboard starts with the bundled `assets/pi_50000.txt`, then asks the local
server for more digits through `/api/pi` as the ship approaches the loaded
horizon. Generated digits are cached in `assets/pi_dynamic_cache.txt`.

It shows a 40-digit flight window, tracks digits traveled, and logs simple
discovery events such as repeated runs, palindromes, repeated trigrams,
prime-digit dense pockets, low-entropy windows, and checksum crossings.

Reverse probes:

- Click **Reverse Probe** to send a verifier backward from the current ship
  coordinate to the last confirmed checkpoint.
- Leave **Auto probe** enabled to do this automatically every configured number
  of digits.
- The probe compares the local flight line with the server pi stream and records
  forward/reverse hashes.
- If it confirms, the verified frontier moves up to the ship, so the next probe
  only checks the newly traveled stretch.

Major discoveries:

- Routine events stay in the discovery feed.
- Higher-signal events are promoted to the major discovery banner. Current gates
  include long repeated runs, larger palindromes, very low entropy pockets,
  prime-digit dense pockets, cache horizon events, and any reverse-probe
  mismatch.

Static fallback:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

The static fallback still works, but it stops at the bundled cache instead of
generating more pi digits.
