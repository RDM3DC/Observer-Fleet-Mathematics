# Pi Flight Deck

Static dashboard for flying an Observer Fleet ship through pi digits or through
adaptive non-Euclidean pi fields.

Run from this directory for endless/on-demand pi streaming:

```powershell
python .\server.py --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

Open directly into a geometry field:

```text
http://127.0.0.1:8765/?mode=geometry&field=pi_n
```

The dashboard starts with the bundled `assets/pi_50000.txt`, then asks the local
server for more digits through `/api/pi` as the ship approaches the loaded
horizon. Generated digits are cached in `assets/pi_dynamic_cache.txt`.

It starts in **Pi digits** mode. That mode shows a 40-digit flight window,
tracks digits traveled, and logs simple discovery events such as repeated runs,
palindromes, repeated trigrams, prime-digit dense pockets, low-entropy windows,
and checksum crossings.

Geometry mode:

- Switch to **Geometry field** to fly the same ship through a conformal metric
  field instead of the digit stream.
- Choose `pi_a`, `pi_f`, or `pi_n`.
- The field engine uses `Omega = pi_local / pi` and the conformal metric
  `g_ij = Omega^2 delta_ij`.
- The 40-cell corridor becomes a metric sample line, and the canvas shows the
  non-Euclidean sheet, path trace, and current ship marker.
- Geometry discoveries include curvature spikes, metric expansion/compression
  pockets, phase parity flips, adaptive arc stretch, near-closed path loops, and
  convergence between the three field definitions.

Reverse probes:

- Click **Reverse Probe** to send a verifier backward from the current ship
  coordinate to the last confirmed checkpoint.
- Leave **Auto probe** enabled to do this automatically every configured number
  of digits or geometry samples.
- In Pi digits mode, the probe compares the local flight line with the server pi
  stream and records forward/reverse hashes.
- In Geometry field mode, the probe recomputes the conformal metric integration
  backward, checks the adaptive arc length, and reports backtrack error.
- If it confirms, the verified frontier moves up to the ship, so the next probe
  only checks the newly traveled stretch.

Major discoveries:

- Routine events stay in the discovery feed.
- Higher-signal events are promoted to the major discovery banner. Current gates
  include long repeated runs, larger palindromes, very low entropy pockets,
  prime-digit dense pockets, cache horizon events, curvature spikes, holonomy
  events, strong metric stretch, field convergence, and any reverse-probe
  mismatch.

Static fallback:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

The static fallback still works, but it stops at the bundled cache instead of
generating more pi digits.
