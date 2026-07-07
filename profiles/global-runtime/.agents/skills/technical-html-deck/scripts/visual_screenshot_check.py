#!/usr/bin/env python3
"""Basic PNG screenshot readiness checks for HTML presentation artifacts."""

from __future__ import annotations

import argparse
import math
import struct
import sys
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def read_png_rgb(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("only PNG screenshots are supported")

    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    compressed = bytearray()

    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if bit_depth != 8 or color_type not in {0, 2, 6} or compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("unsupported PNG format; use Chrome 8-bit non-interlaced screenshots")
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None:
        raise ValueError("missing PNG IHDR")

    channels = {0: 1, 2: 3, 6: 4}[color_type]
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    rows: list[bytearray] = []
    cursor = 0

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        previous = rows[-1] if rows else bytearray(stride)

        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + up) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (row[index] + paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter: {filter_type}")
        rows.append(row)

    pixels: list[tuple[int, int, int]] = []
    step_x = max(1, width // 180)
    step_y = max(1, height // 120)
    for y in range(0, height, step_y):
        row = rows[y]
        for x in range(0, width, step_x):
            base = x * channels
            if color_type == 0:
                gray = row[base]
                pixels.append((gray, gray, gray))
            else:
                pixels.append((row[base], row[base + 1], row[base + 2]))

    return width, height, pixels


def luminance(pixel: tuple[int, int, int]) -> float:
    red, green, blue = pixel
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a PNG deck screenshot for obvious visual failures.")
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("--min-width", type=int, default=1200)
    parser.add_argument("--min-height", type=int, default=700)
    parser.add_argument("--max-near-white", type=float, default=0.82)
    parser.add_argument("--min-entropy", type=float, default=2.6)
    args = parser.parse_args()

    path = args.screenshot.expanduser().resolve()
    if not path.exists():
        print(f"FAIL screenshot not found: {path}")
        return 2

    try:
        width, height, pixels = read_png_rgb(path)
    except Exception as exc:
        print(f"FAIL {exc}")
        return 2

    near_white = sum(1 for pixel in pixels if min(pixel) >= 242 and luminance(pixel) >= 245) / len(pixels)
    luma = [round(luminance(pixel)) for pixel in pixels]
    histogram = [0] * 256
    for value in luma:
        histogram[min(255, max(0, value))] += 1
    total = len(luma)
    entropy = -sum((count / total) * math.log2(count / total) for count in histogram if count)
    mean_rgb = tuple(round(sum(pixel[channel] for pixel in pixels) / len(pixels), 2) for channel in range(3))
    variance_rgb = tuple(
        round(sum((pixel[channel] - mean_rgb[channel]) ** 2 for pixel in pixels) / len(pixels), 2)
        for channel in range(3)
    )

    failures: list[str] = []
    warnings: list[str] = []

    if width < args.min_width or height < args.min_height:
        failures.append(f"dimensions {width}x{height} below {args.min_width}x{args.min_height}")
    if near_white > args.max_near_white:
        failures.append(f"near-white area {near_white:.1%} > {args.max_near_white:.0%}; screenshot may be too sparse")
    if entropy < args.min_entropy:
        failures.append(f"luminance entropy {entropy:.2f} < {args.min_entropy:.2f}; screenshot may be visually empty")
    if max(variance_rgb) < 300:
        warnings.append("low channel variance; verify the screenshot is not a blank or nearly flat page")

    print(f"screenshot: {path}")
    print(f"dimensions: {width}x{height}")
    print(f"near_white: {near_white:.3f}")
    print(f"entropy: {entropy:.3f}")
    print(f"mean_rgb: {mean_rgb}")
    print(f"variance_rgb: {variance_rgb}")

    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")

    if failures:
        return 1

    print("PASS visual screenshot checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
