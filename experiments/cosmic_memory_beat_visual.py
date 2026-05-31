#!/usr/bin/env python3
"""Mission 009: Cosmic Memory Beat visual generator.

Generates a poster frame and a shareable GIF under 15 MB.

Visual metaphor:
    center pulse        = expansion heartbeat
    bright ring         = BAO fossil acoustic memory
    ripple field        = CMB background hum
    moving white sparks = Phi_MOC observer ticks scanning the beat

Run:
    python experiments/cosmic_memory_beat_visual.py --outdir results/cosmic_memory_beat_visual
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence


State = Tuple[int, int]


def moc_states(count: int, modulus: int = 101, a: int = 4, b: int = 3, seed: State = (1, 1)) -> List[State]:
    cur, prev = seed
    states: List[State] = []
    for _ in range(count):
        states.append((cur % modulus, prev % modulus))
        cur, prev = (a * cur + b * prev) % modulus, cur % modulus
    return states


def load_fonts():
    try:
        return (
            ImageFont.truetype("DejaVuSans.ttf", 34),
            ImageFont.truetype("DejaVuSans.ttf", 22),
            ImageFont.truetype("DejaVuSans.ttf", 16),
        )
    except Exception:
        return (None, None, None)


def render_frames(width: int, height: int, frame_count: int) -> List[Image.Image]:
    cx, cy = width // 2, height // 2
    states = moc_states(frame_count * 6)
    font_big, font_med, font_small = load_fonts()

    x = np.linspace(-1.15, 1.15, width)
    y = np.linspace(-1.15, 1.15, height)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)
    TH = np.arctan2(Y, X)

    frames: List[Image.Image] = []
    for f in range(frame_count):
        t = 2.0 * math.pi * f / frame_count

        expansion = np.sin(7.5 * R - 1.6 * t)
        bao_ring = np.exp(-((R - (0.56 + 0.025 * np.sin(t))) ** 2) / (2 * 0.018**2))
        cmb_hum = 0.55 * np.sin(34 * R + 9 * np.sin(3 * TH) + 2.4 * t)
        phase_scar = 0.65 * np.sin(5 * TH + 4 * R - 1.7 * t) * np.exp(-((R - 0.38) ** 2) / (2 * 0.09**2))

        field = 0.42 * expansion + 1.35 * bao_ring + 0.24 * cmb_hum + 0.33 * phase_scar
        F = (field - field.min()) / (field.max() - field.min() + 1e-9)
        vignette = np.clip(1.15 - R, 0, 1)

        red = np.clip(255 * (0.15 + 0.85 * F) * vignette, 0, 255)
        green = np.clip(255 * (0.08 + 0.65 * np.sqrt(F)) * vignette, 0, 255)
        blue = np.clip(255 * (0.22 + 0.95 * (1 - F) ** 0.7) * vignette, 0, 255)
        img = Image.fromarray(np.dstack([red, green, blue]).astype(np.uint8), "RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        for rr, alpha, line_width in [(0.56, 120, 4), (0.38, 70, 2), (0.75, 45, 2)]:
            rad = int(rr * width / 2.3 * (1 + 0.018 * np.sin(t + rr * 4)))
            draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(255, 255, 255, alpha), width=line_width)

        for j in range(18):
            cur, prev = states[(f * 6 + j * 7) % len(states)]
            phase = (cur / 101) * 2 * math.pi + 0.28 * t
            radius = 0.10 * width + 0.32 * width * (prev / 100)
            px = cx + int(radius * math.cos(phase))
            py = cy + int(radius * math.sin(phase))
            size = 2 + int(4 * ((cur + prev) % 7) / 6)
            alpha = 90 + int(145 * (j / 17))
            draw.ellipse((px - size, py - size, px + size, py + size), fill=(255, 255, 255, alpha))
            if j % 5 == 0:
                draw.line((cx, cy, px, py), fill=(255, 255, 255, 24), width=1)

        pulse = int(0.025 * width + 0.011 * width * np.sin(t * 2))
        draw.ellipse((cx - pulse, cy - pulse, cx + pulse, cy + pulse), fill=(255, 255, 255, 85))
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(255, 255, 255, 185))

        draw.rounded_rectangle((28, 24, width - 28, 116), radius=18, fill=(0, 0, 0, 95))
        draw.text((48, 40), "Cosmic Memory Beat", font=font_big, fill=(255, 255, 255, 240))
        draw.text((48, 82), "Hubble breath + BAO fossil ring + CMB hum + MOC observer sparks", font=font_small, fill=(255, 255, 255, 215))

        bottom_y = height - 118
        draw.rounded_rectangle((34, bottom_y, width - 34, height - 42), radius=18, fill=(0, 0, 0, 90))
        state = states[(f * 6) % len(states)]
        draw.text((54, bottom_y + 16), f"Phi_MOC tick {f:03d}  state={state}  memory scan: H(z) | BAO | CMB", font=font_med, fill=(255, 255, 255, 230))
        draw.text((54, bottom_y + 48), "The Fleet uses clock phases to read stable residual memory across cosmic layers.", font=font_small, fill=(255, 255, 255, 205))

        frames.append(img)
    return frames


def save_gif(frames: List[Image.Image], path: Path, duration: int, colors: int) -> None:
    quantized = [frame.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT) for frame in frames]
    quantized[0].save(
        path,
        save_all=True,
        append_images=quantized[1:],
        duration=duration,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="results/cosmic_memory_beat_visual")
    parser.add_argument("--size", type=int, default=648)
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument("--colors", type=int, default=128)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    frames = render_frames(args.size, args.size, args.frames)
    poster = outdir / "cosmic_memory_beat_poster.png"
    gif = outdir / "cosmic_memory_beat_under_15mb.gif"

    frames[0].save(poster)
    save_gif(frames, gif, args.duration, args.colors)

    print(f"Saved poster: {poster.resolve()}")
    print(f"Saved gif: {gif.resolve()}")
    print(f"GIF size MB: {gif.stat().st_size / (1024 * 1024):.2f}")


if __name__ == "__main__":
    main()
