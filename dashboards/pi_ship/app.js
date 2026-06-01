"use strict";

const WINDOW_SIZE = 40;
const MAX_FEED_ITEMS = 80;
const FALLBACK_PI =
  "14159265358979323846264338327950288419716939937510" +
  "58209749445923078164062862089986280348253421170679" +
  "82148086513282306647093844609550582231725359408128" +
  "48111745028410270193852110555964462294895493038196" +
  "44288109756659334461284756482337867831652712019091";

const state = {
  pi: "",
  piStatus: "Loading pi stream",
  mode: "digits",
  fieldKind: "pi_a",
  position: 0,
  traveled: 0,
  geometryArc: 0,
  verifiedPosition: 0,
  running: false,
  streaming: false,
  loadingMore: false,
  probing: false,
  lastProbe: null,
  autoProbe: true,
  probeInterval: 500,
  majorDiscoveries: [],
  speed: 18,
  lastFrame: 0,
  carry: 0,
  discoveries: [],
  seenDiscoveries: new Set(),
};

const el = {
  loadStatus: document.querySelector("#loadStatus"),
  runStatus: document.querySelector("#runStatus"),
  fieldCanvas: document.querySelector("#fieldCanvas"),
  coordinateLabel: document.querySelector("#coordinateLabel"),
  coordinate: document.querySelector("#coordinate"),
  distanceLabel: document.querySelector("#distanceLabel"),
  distance: document.querySelector("#distance"),
  corridorTitle: document.querySelector("#corridorTitle"),
  windowRange: document.querySelector("#windowRange"),
  digitWindow: document.querySelector("#digitWindow"),
  digitMode: document.querySelector("#digitMode"),
  geometryMode: document.querySelector("#geometryMode"),
  fieldControl: document.querySelector("#fieldControl"),
  fieldKind: document.querySelector("#fieldKind"),
  toggleRun: document.querySelector("#toggleRun"),
  stepOnce: document.querySelector("#stepOnce"),
  reverseProbe: document.querySelector("#reverseProbe"),
  resetFlight: document.querySelector("#resetFlight"),
  autoProbe: document.querySelector("#autoProbe"),
  probeInterval: document.querySelector("#probeInterval"),
  speed: document.querySelector("#speed"),
  speedValue: document.querySelector("#speedValue"),
  jumpLabel: document.querySelector("#jumpLabel"),
  jumpTo: document.querySelector("#jumpTo"),
  jumpButton: document.querySelector("#jumpButton"),
  meterCurrentLabel: document.querySelector("#meterCurrentLabel"),
  meterHorizonLabel: document.querySelector("#meterHorizonLabel"),
  meterEntropyLabel: document.querySelector("#meterEntropyLabel"),
  meterPrimeLabel: document.querySelector("#meterPrimeLabel"),
  currentDigit: document.querySelector("#currentDigit"),
  loadedHorizon: document.querySelector("#loadedHorizon"),
  entropyValue: document.querySelector("#entropyValue"),
  primeShare: document.querySelector("#primeShare"),
  observerPanelTitle: document.querySelector("#observerPanelTitle"),
  observerRowOneLabel: document.querySelector("#observerRowOneLabel"),
  observerRowTwoLabel: document.querySelector("#observerRowTwoLabel"),
  observerRowThreeLabel: document.querySelector("#observerRowThreeLabel"),
  observerRowFourLabel: document.querySelector("#observerRowFourLabel"),
  classification: document.querySelector("#classification"),
  entropyScout: document.querySelector("#entropyScout"),
  runDetector: document.querySelector("#runDetector"),
  repeatDetector: document.querySelector("#repeatDetector"),
  modChecksum: document.querySelector("#modChecksum"),
  geometryPanel: document.querySelector("#geometryPanel"),
  fieldStatus: document.querySelector("#fieldStatus"),
  localPi: document.querySelector("#localPi"),
  metricScale: document.querySelector("#metricScale"),
  curvatureValue: document.querySelector("#curvatureValue"),
  arcLength: document.querySelector("#arcLength"),
  windingValue: document.querySelector("#windingValue"),
  parityValue: document.querySelector("#parityValue"),
  probeStatus: document.querySelector("#probeStatus"),
  verifiedFrontier: document.querySelector("#verifiedFrontier"),
  probeSpan: document.querySelector("#probeSpan"),
  forwardHash: document.querySelector("#forwardHash"),
  reverseHash: document.querySelector("#reverseHash"),
  discoveryCount: document.querySelector("#discoveryCount"),
  majorBanner: document.querySelector("#majorBanner"),
  majorTitle: document.querySelector("#majorTitle"),
  discoveryFeed: document.querySelector("#discoveryFeed"),
};

function isGeometryMode() {
  return state.mode === "geometry";
}

async function loadPi() {
  try {
    const response = await fetch("/api/pi?start=0&count=6000", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("pi API unavailable");
    }
    const payload = await response.json();
    state.pi = String(payload.digits || "").replace(/\D/g, "");
    state.streaming = true;
    state.piStatus = `${Number(payload.available).toLocaleString()} pi digits available`;
    el.loadStatus.textContent = state.piStatus;
  } catch (_error) {
    try {
      const response = await fetch("assets/pi_50000.txt", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("pi stream unavailable");
      }
      const text = await response.text();
      state.pi = text.replace(/\D/g, "");
      state.piStatus = `${state.pi.length.toLocaleString()} static pi digits loaded`;
      el.loadStatus.textContent = state.piStatus;
    } catch (_fallbackError) {
      state.pi = FALLBACK_PI;
      state.piStatus = `${state.pi.length.toLocaleString()} fallback digits loaded`;
      el.loadStatus.textContent = state.piStatus;
    }
  }

  el.loadedHorizon.textContent = state.pi.length.toLocaleString();
  el.jumpTo.max = state.streaming ? "999999999" : String(Math.max(1, state.pi.length - WINDOW_SIZE + 1));
  render();
  requestAnimationFrame(tick);
}

async function ensureDigits(targetLength) {
  if (!state.streaming || state.loadingMore || targetLength <= state.pi.length) {
    return;
  }

  state.loadingMore = true;
  state.piStatus = `Generating pi to ${targetLength.toLocaleString()}`;
  el.loadStatus.textContent = state.piStatus;
  try {
    while (state.pi.length < targetLength) {
      const start = state.pi.length;
      const count = Math.max(6000, targetLength - start);
      const response = await fetch(`/api/pi?start=${start}&count=${count}`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error("pi API request failed");
      }
      const payload = await response.json();
      const nextDigits = String(payload.digits || "").replace(/\D/g, "");
      if (!nextDigits) {
        throw new Error("pi API returned no digits");
      }
      state.pi += nextDigits;
      state.piStatus = `${state.pi.length.toLocaleString()} pi digits loaded`;
      el.loadStatus.textContent = state.piStatus;
      el.loadedHorizon.textContent = state.pi.length.toLocaleString();
    }
    state.piStatus = `${state.pi.length.toLocaleString()} pi digits loaded`;
    el.loadStatus.textContent = state.piStatus;
    el.loadedHorizon.textContent = state.pi.length.toLocaleString();
  } catch (_error) {
    state.streaming = false;
    state.piStatus = `${state.pi.length.toLocaleString()} pi digits loaded; stream paused`;
    el.loadStatus.textContent = state.piStatus;
  } finally {
    state.loadingMore = false;
    render();
  }
}

async function fetchPiSegment(start, count) {
  if (state.streaming) {
    const response = await fetch(`/api/pi?start=${start}&count=${count}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("reverse probe could not fetch pi segment");
    }
    const payload = await response.json();
    return String(payload.digits || "").replace(/\D/g, "").slice(0, count);
  }
  return state.pi.slice(start, start + count);
}

function tick(timestamp) {
  if (!state.lastFrame) {
    state.lastFrame = timestamp;
  }

  const elapsedSeconds = Math.min(0.25, (timestamp - state.lastFrame) / 1000);
  state.lastFrame = timestamp;

  if (state.running) {
    state.carry += elapsedSeconds * state.speed;
    const steps = Math.floor(state.carry);
    if (steps > 0) {
      state.carry -= steps;
      moveBy(steps);
    }
  }

  requestAnimationFrame(tick);
}

function moveBy(steps) {
  if (isGeometryMode()) {
    moveGeometryBy(steps);
    return;
  }

  if (!state.pi) {
    return;
  }
  const maxPosition = Math.max(0, state.pi.length - WINDOW_SIZE);
  const previous = state.position;
  const desired = state.position + steps;
  if (state.streaming && desired + WINDOW_SIZE + 1000 > state.pi.length) {
    ensureDigits(desired + WINDOW_SIZE + 7000);
  }
  state.position = Math.min(maxPosition, desired);
  state.traveled += Math.max(0, state.position - previous);

  for (let pos = previous + 1; pos <= state.position; pos += 1) {
    scanAt(pos);
  }

  if (!state.streaming && state.position >= maxPosition) {
    state.running = false;
    addDiscovery("horizon", state.position, "Loaded horizon reached", "The ship reached the end of the local pi cache.");
  }
  maybeAutoProbe();
  render();
}

function moveGeometryBy(steps) {
  const previous = state.position;
  const desired = Math.max(0, state.position + steps);
  state.position = desired;
  state.traveled += Math.max(0, state.position - previous);
  state.geometryArc += GeometryFlight.arcBetween(previous, state.position, state.fieldKind);

  for (let pos = previous + 1; pos <= state.position; pos += 1) {
    scanAt(pos);
  }

  maybeAutoProbe();
  render();
}

function scanAt(position) {
  if (isGeometryMode()) {
    scanGeometryAt(position);
    return;
  }

  const segment = windowAt(position);
  if (segment.length < WINDOW_SIZE) {
    return;
  }

  const run = longestRun(segment);
  if (run.length >= 4) {
    addDiscovery(
      "run",
      position + run.offset,
      `Run of ${run.length} ${run.digit}s`,
      `Digits ${position + run.offset + 1}..${position + run.offset + run.length} repeat the same symbol.`
    );
  }

  const palindrome = firstPalindrome(segment, 7) || firstPalindrome(segment, 6) || firstPalindrome(segment, 5);
  if (palindrome) {
    addDiscovery(
      "palindrome",
      position + palindrome.offset,
      `${palindrome.value.length}-digit palindrome`,
      `${palindrome.value} appears inside the forward window.`
    );
  }

  const repeated = strongestRepeat(segment, 3);
  if (repeated.count >= 3) {
    addDiscovery(
      "repeat",
      position,
      `Repeated trigram ${repeated.value}`,
      `${repeated.value} appears ${repeated.count} times in the 40-digit flight line.`
    );
  }

  const profile = profileSegment(segment);
  if (profile.primeShare >= 0.6) {
    addDiscovery(
      "prime",
      position,
      "Prime-digit dense pocket",
      `${Math.round(profile.primeShare * 100)}% of this window is 2, 3, 5, or 7.`
    );
  }
  if (profile.entropy < 3.05) {
    addDiscovery(
      "entropy",
      position,
      "Low-entropy pocket",
      `Window entropy fell to ${profile.entropy.toFixed(3)} bits per digit.`
    );
  }
  if (profile.sum % 37 === 0) {
    addDiscovery(
      "mod",
      position,
      "Mod-37 checksum crossing",
      `The 40-digit window sum is ${profile.sum}, exactly divisible by 37.`
    );
  }
}

function scanGeometryAt(position) {
  const events = GeometryFlight.scan(position, state.fieldKind);
  for (const event of events) {
    addDiscovery(event.type, position, event.title, event.detail);
  }
}

function addDiscovery(type, position, title, detail) {
  const key = `${state.mode}:${state.fieldKind}:${type}:${position}:${title}`;
  if (state.seenDiscoveries.has(key)) {
    return;
  }
  state.seenDiscoveries.add(key);
  state.discoveries.unshift({ type, position, title, detail, mode: state.mode, fieldKind: state.fieldKind });
  if (state.discoveries.length > MAX_FEED_ITEMS) {
    state.discoveries.pop();
  }

  const major = majorDiscoveryLevel(type, title, detail);
  if (major) {
    state.majorDiscoveries.unshift({ type, position, title, detail, level: major, mode: state.mode, fieldKind: state.fieldKind });
    addDiscoveryToConsole(position, title, detail, major);
  }
}

function majorDiscoveryLevel(type, title, detail) {
  if (type === "horizon") {
    return "major";
  }
  if (type === "probe" && title.includes("mismatch")) {
    return "super major";
  }
  if (type === "run") {
    const match = title.match(/Run of (\d+)/);
    const length = match ? Number(match[1]) : 0;
    return length >= 6 ? "super major" : length >= 5 ? "major" : "";
  }
  if (type === "palindrome") {
    const match = title.match(/(\d+)-digit/);
    const length = match ? Number(match[1]) : 0;
    return length >= 7 ? "major" : "";
  }
  if (type === "entropy") {
    const match = detail.match(/([0-9]+\.[0-9]+)/);
    const entropy = match ? Number(match[1]) : 4;
    return entropy < 2.8 ? "super major" : "";
  }
  if (type === "prime") {
    const match = detail.match(/(\d+)%/);
    const share = match ? Number(match[1]) : 0;
    return share >= 70 ? "major" : "";
  }
  if (type === "curvature") {
    const match = detail.match(/K=([-0-9.]+)/);
    const curvature = match ? Math.abs(Number(match[1])) : 0;
    return curvature >= 1.1 ? "super major" : curvature >= 0.75 ? "major" : "";
  }
  if (type === "metric") {
    const match = detail.match(/Omega=([0-9.]+)/);
    const omega = match ? Number(match[1]) : 1;
    return omega >= 1.58 || omega <= 0.58 ? "major" : "";
  }
  if (type === "holonomy" || type === "loop") {
    return "major";
  }
  if (type === "convergence") {
    return "major";
  }
  if (type === "compression") {
    const match = detail.match(/([0-9.]+)x/);
    const ratio = match ? Number(match[1]) : 1;
    return ratio >= 1.36 ? "super major" : ratio >= 1.28 ? "major" : "";
  }
  return "";
}

function addDiscoveryToConsole(position, title, detail, level) {
  const coordinate = isGeometryMode() ? `sample[${position + 1}]` : `pi[${position + 1}]`;
  console.info(`[${level}] ${coordinate} ${title}: ${detail}`);
}

function maybeAutoProbe() {
  if (!state.autoProbe || state.probing || state.loadingMore || !state.running) {
    return;
  }
  const unchecked = state.position - state.verifiedPosition;
  if (unchecked >= state.probeInterval) {
    runReverseProbe({ automatic: true });
  }
}

async function runReverseProbe(options = {}) {
  if (isGeometryMode()) {
    runGeometryReverseProbe(options);
    return;
  }

  if (state.probing || !state.pi) {
    return;
  }

  const end = state.position;
  const start = Math.min(state.verifiedPosition, end);
  const count = end - start;
  if (count <= 0) {
    state.lastProbe = {
      status: "Confirmed",
      forwardHash: "-",
      reverseHash: "-",
      span: 0,
    };
    if (!options.automatic) {
      addDiscovery("probe", end, "Reverse probe already current", "The verified checkpoint is already at the ship.");
    }
    render();
    return;
  }

  state.probing = true;
  state.lastProbe = {
    status: "Returning",
    forwardHash: "...",
    reverseHash: "...",
    span: count,
  };
  render();

  try {
    await ensureDigits(end + WINDOW_SIZE);
    const localSegment = state.pi.slice(start, end);
    const serverSegment = await fetchPiSegment(start, count);
    const forwardHash = rollingHash(localSegment);
    const reverseHash = reverseRollingHash(localSegment);
    const serverHash = rollingHash(serverSegment);
    const confirmed = localSegment === serverSegment && forwardHash === serverHash;

    state.lastProbe = {
      status: confirmed ? "Confirmed" : "Mismatch",
      forwardHash,
      reverseHash,
      span: count,
    };

    if (confirmed) {
      state.verifiedPosition = end;
      if (!options.automatic || count >= state.probeInterval) {
        addDiscovery(
          "probe",
          end,
          options.automatic ? "Auto reverse probe confirmed" : "Reverse probe confirmed",
          `Checked ${count.toLocaleString()} digits backward to pi[${(start + 1).toLocaleString()}]. Next probe only returns to pi[${(end + 1).toLocaleString()}].`
        );
      }
    } else {
      state.running = false;
      addDiscovery(
        "probe",
        start,
        "Reverse probe mismatch",
        "The local flight line did not match the server pi segment. Flight paused for inspection."
      );
    }
  } catch (error) {
    state.running = false;
    state.lastProbe = {
      status: "Error",
      forwardHash: "-",
      reverseHash: "-",
      span: count,
    };
    addDiscovery("probe", start, "Reverse probe error", error.message || "Probe failed before confirmation.");
  } finally {
    state.probing = false;
    render();
  }
}

function runGeometryReverseProbe(options = {}) {
  if (state.probing) {
    return;
  }

  const end = state.position;
  const start = Math.min(state.verifiedPosition, end);
  const count = end - start;
  if (count <= 0) {
    state.lastProbe = {
      status: "Confirmed",
      forwardHash: "-",
      reverseHash: "-",
      span: 0,
    };
    if (!options.automatic) {
      addDiscovery("probe", end, "Geometry probe already current", "The verified checkpoint is already at the ship.");
    }
    render();
    return;
  }

  state.probing = true;
  state.lastProbe = {
    status: "Returning",
    forwardHash: "...",
    reverseHash: "...",
    span: count,
  };
  render();

  window.setTimeout(() => {
    try {
      const probe = GeometryFlight.reverseProbe(start, end, state.fieldKind);
      state.lastProbe = {
        status: probe.confirmed ? "Confirmed" : "Mismatch",
        forwardHash: probe.forwardHash,
        reverseHash: probe.reverseHash,
        span: count,
      };

      if (probe.confirmed) {
        state.verifiedPosition = end;
        if (!options.automatic || count >= state.probeInterval) {
          addDiscovery(
            "probe",
            end,
            options.automatic ? "Auto geometry probe confirmed" : "Geometry reverse probe confirmed",
            `Checked ${count.toLocaleString()} samples back to sample ${(start + 1).toLocaleString()}; arc=${probe.arcForward.toFixed(4)}, backtrack error=${probe.backtrackError.toExponential(2)}.`
          );
        }
      } else {
        state.running = false;
        addDiscovery(
          "probe",
          start,
          "Geometry reverse probe mismatch",
          `Forward and reverse metric integration disagreed over ${count.toLocaleString()} samples.`
        );
      }
    } catch (error) {
      state.running = false;
      state.lastProbe = {
        status: "Error",
        forwardHash: "-",
        reverseHash: "-",
        span: count,
      };
      addDiscovery("probe", start, "Geometry reverse probe error", error.message || "Probe failed before confirmation.");
    } finally {
      state.probing = false;
      render();
    }
  }, 0);
}

function render() {
  if (isGeometryMode()) {
    renderGeometry();
    return;
  }

  document.body.classList.remove("geometry-mode");
  el.digitMode.classList.add("selected");
  el.geometryMode.classList.remove("selected");
  el.fieldControl.hidden = true;
  el.fieldKind.value = state.fieldKind;
  el.geometryPanel.hidden = true;
  el.coordinateLabel.textContent = "Pi coordinate";
  el.distanceLabel.textContent = "Digits traveled";
  el.loadStatus.textContent = state.piStatus;
  el.corridorTitle.textContent = "40-digit flight line";
  el.meterCurrentLabel.textContent = "Current digit";
  el.meterHorizonLabel.textContent = "Loaded horizon";
  el.meterEntropyLabel.textContent = "Window entropy";
  el.meterPrimeLabel.textContent = "Prime digit share";
  el.observerPanelTitle.textContent = "Observer Ships";
  el.observerRowOneLabel.textContent = "Entropy scout";
  el.observerRowTwoLabel.textContent = "Run detector";
  el.observerRowThreeLabel.textContent = "Repeat detector";
  el.observerRowFourLabel.textContent = "Mod checksum";
  el.jumpLabel.textContent = "Jump to digit";

  const segment = windowAt(state.position);
  renderDigits(segment);

  const profile = profileSegment(segment);
  const run = longestRun(segment);
  const repeat = strongestRepeat(segment, 2);
  const end = Math.min(state.position + WINDOW_SIZE, state.pi.length);

  el.coordinate.textContent = `pi[${(state.position + 1).toLocaleString()}]`;
  el.distance.textContent = `${state.traveled.toLocaleString()} digits`;
  el.windowRange.textContent = `pi[${(state.position + 1).toLocaleString()}..${end.toLocaleString()}]`;
  el.currentDigit.textContent = segment[0] || "-";
  el.entropyValue.textContent = segment ? profile.entropy.toFixed(3) : "-";
  el.primeShare.textContent = segment ? `${Math.round(profile.primeShare * 100)}%` : "-";
  el.entropyScout.textContent = entropyLabel(profile.entropy);
  el.runDetector.textContent = run.length > 1 ? `${run.digit} x ${run.length}` : "quiet";
  el.repeatDetector.textContent = repeat.count > 1 ? `${repeat.value} x ${repeat.count}` : "quiet";
  el.modChecksum.textContent = segment ? `sum ${profile.sum} / mod9 ${profile.sum % 9}` : "-";
  el.classification.textContent = classifyWindow(profile, run, repeat);
  el.runStatus.textContent = state.loadingMore ? "Extending pi" : state.running ? "Cruising" : "Docked";
  el.runStatus.classList.toggle("muted", !state.running && !state.loadingMore);
  el.toggleRun.textContent = state.running ? "Pause" : "Launch";
  el.speedValue.textContent = `${state.speed} digits/s`;
  el.jumpTo.value = String(state.position + 1);
  el.reverseProbe.disabled = state.probing;
  el.autoProbe.checked = state.autoProbe;
  el.probeInterval.value = String(state.probeInterval);
  el.verifiedFrontier.textContent = `pi[${(state.verifiedPosition + 1).toLocaleString()}]`;
  el.probeSpan.textContent = `${Math.max(0, state.position - state.verifiedPosition).toLocaleString()} / ${state.probeInterval.toLocaleString()} digits`;
  el.probeStatus.textContent = state.probing ? "Returning" : state.lastProbe?.status || "Waiting";
  el.forwardHash.textContent = state.lastProbe?.forwardHash || "-";
  el.reverseHash.textContent = state.lastProbe?.reverseHash || "-";

  renderFeed();
}

function renderGeometry() {
  const profile = GeometryFlight.profile(state.position, state.fieldKind, WINDOW_SIZE);
  const current = profile.samples[0];
  renderGeometryWindow(profile.samples);
  GeometryFlight.draw(el.fieldCanvas, state.position, state.fieldKind);

  document.body.classList.add("geometry-mode");
  el.digitMode.classList.remove("selected");
  el.geometryMode.classList.add("selected");
  el.fieldControl.hidden = false;
  el.fieldKind.value = state.fieldKind;
  el.geometryPanel.hidden = false;

  el.coordinateLabel.textContent = "Geometry coordinate";
  el.distanceLabel.textContent = "Samples traveled";
  el.loadStatus.textContent = `${state.fieldKind} geometry field active`;
  el.coordinate.textContent = `${state.fieldKind}[${(state.position + 1).toLocaleString()}]`;
  el.distance.textContent = `${state.traveled.toLocaleString()} samples`;
  el.corridorTitle.textContent = "40-sample metric line";
  el.windowRange.textContent = `${state.fieldKind}[${(state.position + 1).toLocaleString()}..${(state.position + WINDOW_SIZE).toLocaleString()}]`;

  el.meterCurrentLabel.textContent = "Field";
  el.meterHorizonLabel.textContent = "Path horizon";
  el.meterEntropyLabel.textContent = "Metric Omega";
  el.meterPrimeLabel.textContent = "Curvature";
  el.currentDigit.textContent = state.fieldKind;
  el.loadedHorizon.textContent = "unbounded";
  el.entropyValue.textContent = profile.averageOmega.toFixed(3);
  el.primeShare.textContent = profile.dominantCurvature.toFixed(3);

  el.observerPanelTitle.textContent = "Geometry Observers";
  el.observerRowOneLabel.textContent = "Arc stretch";
  el.observerRowTwoLabel.textContent = "Curvature scout";
  el.observerRowThreeLabel.textContent = "Holonomy";
  el.observerRowFourLabel.textContent = "Field compare";
  el.entropyScout.textContent = `${profile.compression.toFixed(3)}x Euclid`;
  el.runDetector.textContent = Math.abs(profile.dominantCurvature) > 0.64 ? "spike" : "quiet";
  el.repeatDetector.textContent = `w=${profile.winding} / z2=${profile.parity}`;
  el.modChecksum.textContent = `DeltaOmega ${profile.fieldSpread.toFixed(4)}`;
  el.classification.textContent = classifyGeometry(profile);

  el.fieldStatus.textContent = state.fieldKind;
  el.localPi.textContent = current.piLocal.toFixed(5);
  el.metricScale.textContent = `Omega ${current.omega.toFixed(3)}`;
  el.curvatureValue.textContent = current.curvature.toFixed(3);
  el.arcLength.textContent = state.geometryArc.toFixed(3);
  el.windingValue.textContent = String(current.winding);
  el.parityValue.textContent = current.parity ? "odd" : "even";

  el.runStatus.textContent = state.running ? "Cruising geometry" : "Docked";
  el.runStatus.classList.toggle("muted", !state.running);
  el.toggleRun.textContent = state.running ? "Pause" : "Launch";
  el.speedValue.textContent = `${state.speed} samples/s`;
  el.jumpLabel.textContent = "Jump to sample";
  el.jumpTo.value = String(state.position + 1);
  el.jumpTo.max = "999999999";
  el.reverseProbe.disabled = state.probing;
  el.autoProbe.checked = state.autoProbe;
  el.probeInterval.value = String(state.probeInterval);
  el.verifiedFrontier.textContent = `sample[${(state.verifiedPosition + 1).toLocaleString()}]`;
  el.probeSpan.textContent = `${Math.max(0, state.position - state.verifiedPosition).toLocaleString()} / ${state.probeInterval.toLocaleString()} samples`;
  el.probeStatus.textContent = state.probing ? "Returning" : state.lastProbe?.status || "Waiting";
  el.forwardHash.textContent = state.lastProbe?.forwardHash || "-";
  el.reverseHash.textContent = state.lastProbe?.reverseHash || "-";

  renderFeed();
}

function renderDigits(segment) {
  el.digitWindow.replaceChildren();
  for (let index = 0; index < WINDOW_SIZE; index += 1) {
    const digit = segment[index] || "";
    const cell = document.createElement("span");
    cell.className = "digit-cell";
    if (index === 0) {
      cell.classList.add("current");
    } else if ("2357".includes(digit)) {
      cell.classList.add("prime");
    } else if (index % 10 === 9) {
      cell.classList.add("hot");
    }
    cell.textContent = digit || "-";
    el.digitWindow.appendChild(cell);
  }
}

function renderGeometryWindow(samples) {
  el.digitWindow.replaceChildren();
  for (let index = 0; index < WINDOW_SIZE; index += 1) {
    const sample = samples[index];
    const cell = document.createElement("span");
    const level = Math.max(0.08, Math.min(1, (sample.omega - 0.5) / 1.3));
    cell.className = "digit-cell metric-cell";
    cell.style.setProperty("--metric-level", level.toFixed(3));
    if (index === 0) {
      cell.classList.add("current");
    }
    if (sample.omega > 1.25 || Math.abs(sample.curvature) > 0.7) {
      cell.classList.add("metric-hot");
    } else if (sample.omega < 0.82) {
      cell.classList.add("metric-cold");
    }
    const label = document.createElement("span");
    label.textContent = index % 5 === 0 || index === 0 ? sample.omega.toFixed(2) : "";
    cell.title = `sample ${sample.index + 1}: Omega=${sample.omega.toFixed(3)}, K=${sample.curvature.toFixed(3)}`;
    cell.appendChild(label);
    el.digitWindow.appendChild(cell);
  }
}

function renderFeed() {
  el.discoveryCount.textContent = `${state.discoveries.length} found`;
  if (state.majorDiscoveries.length) {
    const latest = state.majorDiscoveries[0];
    const coordinate = latest.mode === "geometry" ? "sample" : "pi";
    const prefix = latest.mode === "geometry" ? `${latest.fieldKind} ` : "";
    el.majorBanner.hidden = false;
    el.majorTitle.textContent = `${latest.level}: ${latest.title} at ${prefix}${coordinate}[${(latest.position + 1).toLocaleString()}]`;
  } else {
    el.majorBanner.hidden = true;
    el.majorTitle.textContent = "-";
  }

  el.discoveryFeed.replaceChildren();
  if (!state.discoveries.length) {
    const item = document.createElement("li");
    item.className = "empty-feed";
    item.textContent = "Launch the ship to start scanning pi.";
    el.discoveryFeed.appendChild(item);
    return;
  }

  for (const discovery of state.discoveries) {
    const item = document.createElement("li");
    item.className = discovery.type;

    const time = document.createElement("time");
    time.textContent = discovery.mode === "geometry"
      ? `${discovery.fieldKind} sample ${Math.max(1, discovery.position + 1).toLocaleString()}`
      : `pi digit ${Math.max(1, discovery.position + 1).toLocaleString()}`;
    const title = document.createElement("strong");
    title.textContent = discovery.title;
    const detail = document.createElement("p");
    detail.textContent = discovery.detail;

    item.append(time, title, detail);
    el.discoveryFeed.appendChild(item);
  }
}

function windowAt(position) {
  return state.pi.slice(position, position + WINDOW_SIZE);
}

function profileSegment(segment) {
  if (!segment) {
    return { entropy: 0, primeShare: 0, sum: 0 };
  }
  const counts = new Map();
  let primeDigits = 0;
  let sum = 0;
  for (const digit of segment) {
    counts.set(digit, (counts.get(digit) || 0) + 1);
    if ("2357".includes(digit)) {
      primeDigits += 1;
    }
    sum += Number(digit);
  }
  let entropy = 0;
  for (const count of counts.values()) {
    const p = count / segment.length;
    entropy -= p * Math.log2(p);
  }
  return {
    entropy,
    primeShare: primeDigits / segment.length,
    sum,
  };
}

function longestRun(segment) {
  let best = { digit: "", length: 0, offset: 0 };
  let currentDigit = "";
  let currentLength = 0;
  let currentOffset = 0;

  for (let index = 0; index < segment.length; index += 1) {
    const digit = segment[index];
    if (digit === currentDigit) {
      currentLength += 1;
    } else {
      currentDigit = digit;
      currentLength = 1;
      currentOffset = index;
    }
    if (currentLength > best.length) {
      best = { digit, length: currentLength, offset: currentOffset };
    }
  }
  return best;
}

function strongestRepeat(segment, size) {
  const counts = new Map();
  for (let index = 0; index <= segment.length - size; index += 1) {
    const value = segment.slice(index, index + size);
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  let best = { value: "", count: 0 };
  for (const [value, count] of counts.entries()) {
    if (count > best.count) {
      best = { value, count };
    }
  }
  return best;
}

function firstPalindrome(segment, size) {
  for (let index = 0; index <= segment.length - size; index += 1) {
    const value = segment.slice(index, index + size);
    if (value === value.split("").reverse().join("")) {
      return { value, offset: index };
    }
  }
  return null;
}

function rollingHash(segment) {
  let hash = 2166136261;
  for (let index = 0; index < segment.length; index += 1) {
    hash ^= segment.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function reverseRollingHash(segment) {
  let hash = 2166136261;
  for (let index = segment.length - 1; index >= 0; index -= 1) {
    hash ^= segment.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function entropyLabel(entropy) {
  if (!entropy) {
    return "-";
  }
  if (entropy < 3.05) {
    return "structured";
  }
  if (entropy > 3.27) {
    return "high";
  }
  return "balanced";
}

function classifyWindow(profile, run, repeat) {
  if (run.length >= 4 || repeat.count >= 3 || profile.entropy < 3.05) {
    return "Interesting window";
  }
  if (profile.primeShare >= 0.6) {
    return "Prime dense";
  }
  return "Quiet flight";
}

function classifyGeometry(profile) {
  if (Math.abs(profile.dominantCurvature) > 0.75) {
    return "Curved pocket";
  }
  if (profile.compression > 1.24) {
    return "Metric stretch";
  }
  if (profile.fieldSpread < 0.026) {
    return "Field convergence";
  }
  if (profile.parity) {
    return "Odd parity sector";
  }
  return "Smooth geometry";
}

async function setPosition(value) {
  if (isGeometryMode()) {
    const next = Math.max(0, Math.floor(value));
    state.traveled += Math.abs(next - state.position);
    state.geometryArc += GeometryFlight.arcBetween(state.position, next, state.fieldKind);
    state.position = next;
    scanAt(state.position);
    render();
    return;
  }

  if (state.streaming && value + WINDOW_SIZE > state.pi.length) {
    await ensureDigits(value + WINDOW_SIZE + 7000);
  }
  const maxPosition = Math.max(0, state.pi.length - WINDOW_SIZE);
  const next = Math.max(0, Math.min(maxPosition, value));
  state.traveled += Math.abs(next - state.position);
  state.position = next;
  scanAt(state.position);
  render();
}

function resetFlightState() {
  state.position = 0;
  state.traveled = 0;
  state.geometryArc = 0;
  state.verifiedPosition = 0;
  state.running = false;
  state.carry = 0;
  state.lastProbe = null;
}

function setMode(mode) {
  if (state.mode === mode) {
    render();
    return;
  }
  state.mode = mode;
  resetFlightState();
  render();
}

function setFieldKind(fieldKind) {
  state.fieldKind = fieldKind;
  resetFlightState();
  render();
}

el.digitMode.addEventListener("click", () => {
  setMode("digits");
});

el.geometryMode.addEventListener("click", () => {
  setMode("geometry");
});

el.fieldKind.addEventListener("change", () => {
  setFieldKind(el.fieldKind.value);
});

el.toggleRun.addEventListener("click", () => {
  state.running = !state.running;
  state.lastFrame = 0;
  render();
});

el.stepOnce.addEventListener("click", () => {
  moveBy(1);
});

el.reverseProbe.addEventListener("click", () => {
  runReverseProbe();
});

el.resetFlight.addEventListener("click", () => {
  resetFlightState();
  render();
});

el.speed.addEventListener("input", () => {
  state.speed = Number(el.speed.value);
  render();
});

el.autoProbe.addEventListener("change", () => {
  state.autoProbe = el.autoProbe.checked;
  maybeAutoProbe();
  render();
});

el.probeInterval.addEventListener("change", () => {
  const value = Number(el.probeInterval.value || 500);
  state.probeInterval = Math.max(10, Math.min(1000000, Math.floor(value)));
  maybeAutoProbe();
  render();
});

el.jumpButton.addEventListener("click", () => {
  setPosition(Number(el.jumpTo.value || 1) - 1);
});

el.jumpTo.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    setPosition(Number(el.jumpTo.value || 1) - 1);
  }
});

function applyInitialRoute() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  const field = params.get("field");
  if (mode === "geometry") {
    state.mode = "geometry";
  }
  if (["pi_a", "pi_f", "pi_n"].includes(field)) {
    state.fieldKind = field;
  }
}

applyInitialRoute();
loadPi();
