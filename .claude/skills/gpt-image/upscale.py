#!/usr/bin/env python3
"""Upscale an image with Real-ESRGAN (CPU), e.g. a cover to 3000x3000 for music distributors.

Usage: upscale.py input.png output.png [--size 3000]
"""
import argparse
import os
import urllib.request

import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader

WEIGHTS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
WEIGHTS = os.path.expanduser("~/.cache/upscale/RealESRGAN_x4plus.pth")
TILE, PAD = 256, 16


def load_model():
    if not os.path.exists(WEIGHTS):
        os.makedirs(os.path.dirname(WEIGHTS), exist_ok=True)
        urllib.request.urlretrieve(WEIGHTS_URL, WEIGHTS)
    model = ModelLoader().load_from_file(WEIGHTS)
    model.eval()
    return model


@torch.inference_mode()
def upscale(model, img):
    # Process in overlapping tiles to keep memory flat on large images.
    x = torch.from_numpy(np.asarray(img, dtype=np.float32) / 255).permute(2, 0, 1)[None]
    _, _, h, w = x.shape
    s = model.scale
    out = torch.zeros(1, 3, h * s, w * s)
    for y0 in range(0, h, TILE):
        for x0 in range(0, w, TILE):
            y1, x1 = min(y0 + TILE, h), min(x0 + TILE, w)
            py0, px0 = max(y0 - PAD, 0), max(x0 - PAD, 0)
            py1, px1 = min(y1 + PAD, h), min(x1 + PAD, w)
            tile = model(x[:, :, py0:py1, px0:px1])
            out[:, :, y0 * s:y1 * s, x0 * s:x1 * s] = tile[
                :, :, (y0 - py0) * s:(y0 - py0 + y1 - y0) * s, (x0 - px0) * s:(x0 - px0 + x1 - x0) * s]
    arr = (out[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
    return Image.fromarray(arr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--size", type=int, default=3000, help="longest side of the output in pixels")
    a = p.parse_args()

    torch.set_num_threads(os.cpu_count() or 4)
    img = Image.open(a.input).convert("RGB")
    big = upscale(load_model(), img)
    ratio = a.size / max(big.size)
    big = big.resize((round(big.width * ratio), round(big.height * ratio)), Image.LANCZOS)
    big.save(a.output, quality=95) if a.output.lower().endswith((".jpg", ".jpeg")) else big.save(a.output)
    print(f"{os.path.abspath(a.output)} {big.width}x{big.height}")


if __name__ == "__main__":
    main()
