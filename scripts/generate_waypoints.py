#!/usr/bin/env python3
"""
Generate lawn‑mower survey waypoints for each site footprint from sites.yaml.
Outputs: one CSV per site and a combined CSV.
Usage:
  python3 generate_waypoints.py --yaml sites.yaml --outdir out/
"""
import argparse, math, os, yaml, csv
from typing import Dict, Tuple, List

def rot2d(x, y, yaw_rad):
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    return c*x - s*y, s*x + c*y

def inside_shape(px, py, cx, cy, spec) -> bool:
    t = spec["type"]
    yaw = math.radians(spec.get("yaw_deg", 0.0))
    lx, ly = rot2d(px - cx, py - cy, -yaw)
    if t == "rectangle":
        hx, hy = spec["size_x"]/2.0, spec["size_y"]/2.0
        return abs(lx) <= hx and abs(ly) <= hy
    if t == "square":
        h = spec["size"]/2.0
        return abs(lx) <= h and abs(ly) <= h
    if t == "circle":
        r = spec["diameter"]/2.0
        return (lx*lx + ly*ly) <= r*r
    if t == "ellipse":
        a, b = spec["size_x"]/2.0, spec["size_y"]/2.0
        return (lx*lx)/(a*a) + (ly*ly)/(b*b) <= 1.0
    return False

def stripe_bounds(spec) -> Tuple[float,float]:
    t = spec["type"]
    if t == "rectangle":
        return spec["size_x"]/2.0, spec["size_y"]/2.0
    if t == "square":
        return spec["size"]/2.0, spec["size"]/2.0
    if t == "circle":
        r = spec["diameter"]/2.0
        return r, r
    if t == "ellipse":
        return spec["size_x"]/2.0, spec["size_y"]/2.0
    return 0.0, 0.0

def generate_stripes(cx, cy, z, yaw_deg, spec, spacing, turn_buffer):
    hx, hy = stripe_bounds(spec)
    min_x = cx - hx - turn_buffer
    max_x = cx + hx + turn_buffer
    min_y = cy - hy - turn_buffer
    max_y = cy + hy + turn_buffer
    x = min_x
    stripe_id = 0
    pts: List[Tuple[float,float,float,float]] = []
    while x <= max_x + 1e-6:
        if stripe_id % 2 == 0:
            ends = [(x, min_y), (x, max_y)]
        else:
            ends = [(x, max_y), (x, min_y)]
        for (sx, sy) in ends:
            yaw = math.radians(yaw_deg)
            pts.append((sx, sy, z, yaw))
        x += spacing
        stripe_id += 1
    return pts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", required=True)
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--spacing", type=float, default=None, help="Override stripe spacing (m)")
    args = ap.parse_args()
    with open(args.yaml, "r") as f:
        cfg = yaml.safe_load(f)
    spacing = args.spacing if args.spacing else float(cfg["survey"]["stripe_spacing"])
    turn_buffer = float(cfg["survey"]["turn_buffer"])
    speed = float(cfg["survey"]["speed_mps"])
    altitude = float(cfg["survey"]["altitude_m"])
    os.makedirs(args.outdir, exist_ok=True)
    frames: Dict[str, Dict] = cfg["frames"]
    fps: Dict[str, Dict] = cfg["footprints"]
    all_rows = []
    for name, spec in fps.items():
        center = spec["center"]
        cx, cy, z = frames[center]["x"], frames[center]["y"], frames[center]["z"]
        yaw_deg = float(spec.get("yaw_deg", 0.0))
        pts = generate_stripes(cx, cy, z + altitude, yaw_deg, spec, spacing, turn_buffer)
        csv_path = os.path.join(args.outdir, f"{name}_survey.csv")
        with open(csv_path, "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(["site", "x_m", "y_m", "z_m", "yaw_rad", "speed_mps"])
            for (x, y, zc, yaw) in pts:
                w.writerow([name, x, y, zc, yaw, speed])
                all_rows.append([name, x, y, zc, yaw, speed])
    combo = os.path.join(args.outdir, "all_sites_survey.csv")
    with open(combo, "w", newline="") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(["site", "x_m", "y_m", "z_m", "yaw_rad", "speed_mps"])
        for row in all_rows:
            w.writerow(row)

if __name__ == "__main__":
    main()
