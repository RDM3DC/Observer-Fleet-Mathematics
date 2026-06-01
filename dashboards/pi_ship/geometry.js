"use strict";

(function geometryFlightModule() {
  const PI = Math.PI;
  const TWO_PI = PI * 2;
  const PHI = (1 + Math.sqrt(5)) / 2;
  const GOLDEN_ANGLE = PI * (3 - Math.sqrt(5));
  const FIELD_KEYS = ["pi_a", "pi_f", "pi_n"];
  const FIELD_LABELS = {
    pi_a: "\u03c0_a adaptive phase-period field",
    pi_f: "\u03c0_f Fibonacci clock field",
    pi_n: "\u03c0_n non-Euclidean curvature field",
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function pathPoint(index) {
    const t = index * 0.046;
    return {
      x:
        1.95 * Math.cos(t * 0.71) +
        0.72 * Math.sin(t * 0.17) +
        0.28 * Math.cos(t * 1.43),
      y:
        1.55 * Math.sin(t * 0.63) +
        0.64 * Math.cos(t * 0.29) +
        0.22 * Math.sin(t * 1.19),
    };
  }

  function fieldOmega(field, x, y, index) {
    if (field === "pi_f") {
      return omegaPiF(x, y, index);
    }
    if (field === "pi_n") {
      return omegaPiN(x, y, index);
    }
    return omegaPiA(x, y, index);
  }

  function omegaPiA(x, y, index) {
    const raw =
      1 +
      0.22 * Math.sin(1.12 * x + 0.030 * index) +
      0.18 * Math.cos(0.96 * y - 0.021 * index) +
      0.11 * Math.sin(0.42 * x * y + 0.018 * index) +
      0.08 * Math.cos(0.35 * (x * x - y * y));
    return clamp(raw, 0.52, 1.72);
  }

  function omegaPiF(x, y, index) {
    const phase = index * GOLDEN_ANGLE;
    const raw =
      1 +
      0.14 * Math.sin(0.72 * PHI * x + 0.37 * Math.sin(phase)) +
      0.11 * Math.cos(0.74 * y / PHI - 0.18 * index) +
      0.08 * Math.sin((x + y) * PI / PHI + 0.011 * index) +
      0.06 * Math.cos((x - y) * GOLDEN_ANGLE * 0.62 + 0.017 * index);
    return clamp(raw, 0.68, 1.42);
  }

  function omegaPiN(x, y, index) {
    const radius = Math.hypot(x, y);
    const theta = Math.atan2(y, x);
    const saddle = Math.tanh(0.48 * (x * x - y * y));
    const raw =
      1 +
      0.24 * saddle +
      0.18 * Math.sin(3 * theta + 0.024 * index) -
      0.12 * Math.cos(1.8 * radius - 0.020 * index) +
      0.08 * Math.sin(x + y + 0.015 * index);
    return clamp(raw, 0.50, 1.78);
  }

  function curvatureAt(field, x, y, index) {
    const h = 0.06;
    const centerOmega = fieldOmega(field, x, y, index);
    const center = Math.log(centerOmega);
    const laplacian =
      (Math.log(fieldOmega(field, x + h, y, index)) +
        Math.log(fieldOmega(field, x - h, y, index)) +
        Math.log(fieldOmega(field, x, y + h, index)) +
        Math.log(fieldOmega(field, x, y - h, index)) -
        4 * center) /
      (h * h);
    return clamp((-laplacian / (centerOmega * centerOmega)) * 0.16, -2.5, 2.5);
  }

  function sample(index, field) {
    const point = pathPoint(index);
    const omega = fieldOmega(field, point.x, point.y, index);
    const curvature = curvatureAt(field, point.x, point.y, index);
    const before = pathPoint(index - 1);
    const after = pathPoint(index + 1);
    const angle = Math.atan2(after.y - before.y, after.x - before.x);
    const phase = Math.max(0, index * 0.135 + angle + 0.4 * Math.sin(index * 0.011));
    const wrapUnit = 2 * PI * omega;
    const winding = Math.floor(phase / wrapUnit);

    return {
      index,
      field,
      x: point.x,
      y: point.y,
      omega,
      piLocal: PI * omega,
      curvature,
      angle,
      winding,
      parity: Math.abs(winding) % 2,
    };
  }

  function segmentLength(startIndex, endIndex, field) {
    if (startIndex === endIndex) {
      return { euclid: 0, adaptive: 0 };
    }
    const start = pathPoint(startIndex);
    const end = pathPoint(endIndex);
    const midpointIndex = (startIndex + endIndex) / 2;
    const midpoint = {
      x: (start.x + end.x) / 2,
      y: (start.y + end.y) / 2,
    };
    const euclid = Math.hypot(end.x - start.x, end.y - start.y);
    const omega = fieldOmega(field, midpoint.x, midpoint.y, midpointIndex);
    return { euclid, adaptive: euclid * omega };
  }

  function arcBetween(start, end, field) {
    const distance = Math.abs(end - start);
    if (!distance) {
      return 0;
    }

    const direction = end > start ? 1 : -1;
    if (distance <= 20000) {
      let arc = 0;
      for (let i = start; i !== end; i += direction) {
        arc += segmentLength(i, i + direction, field).adaptive;
      }
      return arc;
    }

    const slices = 5000;
    const stride = (end - start) / slices;
    let arc = 0;
    let previous = start;
    for (let slice = 1; slice <= slices; slice += 1) {
      const next = slice === slices ? end : start + stride * slice;
      arc += segmentLength(previous, next, field).adaptive;
      previous = next;
    }
    return arc;
  }

  function windowSamples(position, field, size) {
    const samples = [];
    for (let offset = 0; offset < size; offset += 1) {
      samples.push(sample(position + offset, field));
    }
    return samples;
  }

  function profile(position, field, size) {
    const samples = windowSamples(position, field, size);
    let omegaSum = 0;
    let maxOmega = -Infinity;
    let minOmega = Infinity;
    let maxAbsCurvature = 0;
    let dominantCurvature = 0;
    let euclid = 0;
    let adaptive = 0;

    for (const item of samples) {
      omegaSum += item.omega;
      maxOmega = Math.max(maxOmega, item.omega);
      minOmega = Math.min(minOmega, item.omega);
      if (Math.abs(item.curvature) > maxAbsCurvature) {
        maxAbsCurvature = Math.abs(item.curvature);
        dominantCurvature = item.curvature;
      }
    }

    for (let index = 1; index < samples.length; index += 1) {
      const segment = segmentLength(samples[index - 1].index, samples[index].index, field);
      euclid += segment.euclid;
      adaptive += segment.adaptive;
    }

    const head = samples[0];
    const fieldValues = FIELD_KEYS.map((key) => fieldOmega(key, head.x, head.y, head.index));
    const fieldSpread = Math.max(...fieldValues) - Math.min(...fieldValues);

    return {
      samples,
      averageOmega: omegaSum / samples.length,
      maxOmega,
      minOmega,
      maxAbsCurvature,
      dominantCurvature,
      euclidLength: euclid,
      adaptiveLength: adaptive,
      compression: euclid ? adaptive / euclid : 1,
      localPi: head.piLocal,
      winding: head.winding,
      parity: head.parity,
      fieldSpread,
    };
  }

  function scan(position, field) {
    const events = [];
    const current = sample(position, field);
    const previous = sample(Math.max(0, position - 1), field);
    const next = sample(position + 1, field);
    const windowProfile = profile(position, field, 40);

    if (
      Math.abs(current.curvature) > 0.64 &&
      Math.abs(current.curvature) >= Math.abs(previous.curvature) &&
      Math.abs(current.curvature) >= Math.abs(next.curvature)
    ) {
      events.push({
        type: "curvature",
        title: current.curvature > 0 ? "Positive curvature spike" : "Negative curvature trench",
        detail: `K=${current.curvature.toFixed(3)} at ${FIELD_LABELS[field]}.`,
      });
    }

    if (current.omega > 1.46 && current.omega > previous.omega && current.omega >= next.omega) {
      events.push({
        type: "metric",
        title: "Metric expansion pocket",
        detail: `Local scale rose to Omega=${current.omega.toFixed(3)}; pi_local=${current.piLocal.toFixed(5)}.`,
      });
    }

    if (current.omega < 0.66 && current.omega < previous.omega && current.omega <= next.omega) {
      events.push({
        type: "metric",
        title: "Metric compression pocket",
        detail: `Local scale fell to Omega=${current.omega.toFixed(3)}; pi_local=${current.piLocal.toFixed(5)}.`,
      });
    }

    if (position > 0 && current.parity !== previous.parity) {
      events.push({
        type: "holonomy",
        title: "Phase parity flip",
        detail: `Winding moved from ${previous.winding} to ${current.winding}; Z2 parity is now ${current.parity}.`,
      });
    }

    if (windowProfile.compression > 1.24 && position % 10 === 0) {
      events.push({
        type: "compression",
        title: "Adaptive arc stretch",
        detail: `The next 40 samples measure ${windowProfile.compression.toFixed(3)}x their Euclidean path length.`,
      });
    }

    if (windowProfile.fieldSpread < 0.026 && position % 5 === 0) {
      events.push({
        type: "convergence",
        title: "Field convergence",
        detail: `pi_a, pi_f, and pi_n agree within DeltaOmega=${windowProfile.fieldSpread.toFixed(4)} at this path point.`,
      });
    }

    if (position > 160 && position % 20 === 0) {
      const returnPoint = pathPoint(position - 128);
      const distance = Math.hypot(current.x - returnPoint.x, current.y - returnPoint.y);
      if (distance < 0.16) {
        events.push({
          type: "loop",
          title: "Near-closed geometry loop",
          detail: `The ship returned within ${distance.toFixed(4)} path units of sample ${position - 128}.`,
        });
      }
    }

    return events;
  }

  function reverseProbe(start, end, field) {
    const count = Math.max(0, end - start);
    if (!count) {
      return {
        confirmed: true,
        span: 0,
        arcForward: 0,
        arcReverse: 0,
        backtrackError: 0,
        forwardHash: "-",
        reverseHash: "-",
      };
    }

    const arcForward = arcBetween(start, end, field);
    const arcReverse = arcBetween(end, start, field);
    const backtrackError = count <= 20000 ? exactBacktrackError(start, end) : 0;
    const forwardHash = hashSamples(start + 1, end, field, 1);
    const reverseHash = hashSamples(end, start + 1, field, -1);
    const confirmed = Math.abs(arcForward - arcReverse) < 1e-7 && backtrackError < 1e-7;

    return {
      confirmed,
      span: count,
      arcForward,
      arcReverse,
      backtrackError,
      forwardHash,
      reverseHash,
    };
  }

  function exactBacktrackError(start, end) {
    let cursor = pathPoint(end);
    for (let index = end; index > start; index -= 1) {
      const here = pathPoint(index);
      const previous = pathPoint(index - 1);
      cursor = {
        x: cursor.x - (here.x - previous.x),
        y: cursor.y - (here.y - previous.y),
      };
    }
    const expected = pathPoint(start);
    return Math.hypot(cursor.x - expected.x, cursor.y - expected.y);
  }

  function hashSamples(start, end, field, direction) {
    let hash = 2166136261;
    for (let index = start; direction > 0 ? index <= end : index >= end; index += direction) {
      const item = sample(index, field);
      const token = `${index}:${item.omega.toFixed(5)}:${item.curvature.toFixed(5)}:${item.winding}:${item.parity}`;
      for (let charIndex = 0; charIndex < token.length; charIndex += 1) {
        hash ^= token.charCodeAt(charIndex);
        hash = Math.imul(hash, 16777619) >>> 0;
      }
    }
    return hash.toString(16).padStart(8, "0");
  }

  function draw(canvas, position, field) {
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }
    const ratio = window.devicePixelRatio || 1;
    const width = Math.round(rect.width * ratio);
    const height = Math.round(rect.height * ratio);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    drawField(ctx, rect.width, rect.height, position, field);
    drawFlightPath(ctx, rect.width, rect.height, position, field);
  }

  function drawField(ctx, width, height, position, field) {
    const columns = 56;
    const rows = 36;
    const cellWidth = width / columns;
    const cellHeight = height / rows;

    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        const x = -3.25 + (column / (columns - 1)) * 6.5;
        const y = -2.65 + (row / (rows - 1)) * 5.3;
        const omega = fieldOmega(field, x, y, position);
        const curvature = curvatureAt(field, x, y, position);
        ctx.fillStyle = fieldColor(omega, curvature);
        ctx.fillRect(column * cellWidth, row * cellHeight, cellWidth + 0.5, cellHeight + 0.5);
      }
    }

    ctx.strokeStyle = "rgba(243, 246, 251, 0.08)";
    ctx.lineWidth = 1;
    for (let column = 0; column <= columns; column += 7) {
      ctx.beginPath();
      ctx.moveTo(column * cellWidth, 0);
      ctx.lineTo(column * cellWidth, height);
      ctx.stroke();
    }
    for (let row = 0; row <= rows; row += 6) {
      ctx.beginPath();
      ctx.moveTo(0, row * cellHeight);
      ctx.lineTo(width, row * cellHeight);
      ctx.stroke();
    }
  }

  function fieldColor(omega, curvature) {
    const expansion = clamp((omega - 1) / 0.75, -1, 1);
    const curve = clamp(curvature / 1.4, -1, 1);
    const red = Math.round(24 + Math.max(0, expansion) * 108 + Math.max(0, curve) * 74);
    const green = Math.round(34 + (1 - Math.abs(expansion)) * 70 + Math.max(0, -curve) * 55);
    const blue = Math.round(48 + Math.max(0, -expansion) * 124 + Math.max(0, -curve) * 42);
    return `rgba(${red}, ${green}, ${blue}, 0.78)`;
  }

  function drawFlightPath(ctx, width, height, position, field) {
    const start = Math.max(0, position - 160);
    const end = position + 88;

    ctx.lineWidth = 2.4;
    ctx.strokeStyle = "rgba(110, 231, 168, 0.72)";
    ctx.beginPath();
    for (let index = start; index <= end; index += 1) {
      const point = toCanvas(pathPoint(index), width, height);
      if (index === start) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    }
    ctx.stroke();

    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(100, 214, 255, 0.95)";
    ctx.beginPath();
    for (let index = Math.max(0, position - 40); index <= position; index += 1) {
      const point = toCanvas(pathPoint(index), width, height);
      if (index === Math.max(0, position - 40)) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    }
    ctx.stroke();

    const current = sample(position, field);
    const point = toCanvas({ x: current.x, y: current.y }, width, height);
    drawShipMarker(ctx, point.x, point.y, current.angle, current.omega);
  }

  function toCanvas(point, width, height) {
    return {
      x: ((point.x + 3.25) / 6.5) * width,
      y: height - ((point.y + 2.65) / 5.3) * height,
    };
  }

  function drawShipMarker(ctx, x, y, angle, omega) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    const size = 13 + clamp(omega - 1, -0.35, 0.55) * 8;

    ctx.shadowColor = "rgba(100, 214, 255, 0.85)";
    ctx.shadowBlur = 16;
    ctx.fillStyle = "#f3f6fb";
    ctx.beginPath();
    ctx.moveTo(size, 0);
    ctx.lineTo(-size * 0.72, size * 0.58);
    ctx.lineTo(-size * 0.42, 0);
    ctx.lineTo(-size * 0.72, -size * 0.58);
    ctx.closePath();
    ctx.fill();

    ctx.shadowBlur = 0;
    ctx.fillStyle = "#64d6ff";
    ctx.beginPath();
    ctx.arc(-size * 0.2, 0, size * 0.24, 0, TWO_PI);
    ctx.fill();
    ctx.restore();
  }

  window.GeometryFlight = {
    FIELD_LABELS,
    arcBetween,
    draw,
    profile,
    reverseProbe,
    sample,
    scan,
    windowSamples,
  };
})();
