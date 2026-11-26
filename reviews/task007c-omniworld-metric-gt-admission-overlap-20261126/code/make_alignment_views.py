"""CPU diagnostic thumbnails only; no GT remapping, alignment fitting or mask tuning."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "evidence/CANDIDATE_INTAKE.json").read_text("utf-8"))["candidates"]
out = ROOT / "figures"; out.mkdir(exist_ok=True)
for c in data:
    uid = c["uid"]
    sheet = Image.new("RGB", (1200, 3 * 253 + 35), "#171b22"); draw = ImageDraw.Draw(sheet)
    draw.text((10, 10), uid + " | RGB / declared-scale depth / depth-edge overlay (diagnostic only)", fill="white")
    for k, frame in enumerate(c["frames"]):
        with Image.open(ROOT / "raw_inputs" / uid / "color" / f"{frame:06d}.png") as im: rgb = np.asarray(im.convert("RGB"))
        with Image.open(ROOT / "raw_inputs" / uid / "depth" / f"{frame:06d}.png") as im: raw = np.asarray(im)
        x = raw.astype(np.float64) / 65535
        valid = (x >= .0015) & (raw <= 65500)
        d = x / (1000 - 999 * x) / .004 * c["metric_scale"]
        # p1/p99 color stretch affects visualization only, never the GT mask.
        lo, hi = np.percentile(np.log(d[valid]), [1, 99]); t = np.clip((np.log(np.maximum(d, 1e-9)) - lo) / (hi - lo), 0, 1)
        colored = np.stack([255 * t, 255 * (1 - np.abs(2*t - 1)), 255 * (1 - t)], -1).astype(np.uint8)
        colored[~valid] = 0
        edge = np.zeros(valid.shape, bool)
        edge[:, 1:] |= valid[:, 1:] & valid[:, :-1] & (np.abs(np.diff(np.log(np.maximum(d, 1e-9)), axis=1)) > .04)
        edge[1:, :] |= valid[1:, :] & valid[:-1, :] & (np.abs(np.diff(np.log(np.maximum(d, 1e-9)), axis=0)) > .04)
        overlay = rgb.copy(); overlay[edge] = [255, 235, 0]
        for j, a in enumerate([rgb, colored, overlay]):
            small = Image.fromarray(a).resize((400, 225), Image.Resampling.BILINEAR)
            y = 35 + k * 253; sheet.paste(small, (j * 400, y)); draw.text((j*400+5, y+228), f"RGB {frame:06d} | " + ["source RGB", "p1-p99 display; invalid black", "source depth edges, no warp"][j], fill="white")
    sheet.save(out / (uid + "_ALIGNMENT_AUDIT.jpg"), quality=92)
print("Generated3 derived thumbnail audit sheets; no raw GT/RGB modified.")
