#!/usr/bin/env python3
"""Make and collect a relaxed 2D torsion scan for Torsion Explorer.

Two steps, one command each:

  1. inputs   one constrained-optimisation input per grid point, built from a single
              starting structure, with the two dihedrals set to the grid values and frozen.
  2. collect  read the finished outputs (Gaussian .log/.out, or ORCA/any .xyz with the
              energy in the comment line) and write the files the explorer loads:
              a scan CSV for the scan loader and a molecule JSON with structures.

Atom numbers on the command line count from 1, as in GaussView, Avogadro and Gaussian
input. The script converts them to 0-based indices where ORCA and the JSON need them.

Only numpy is required.

Examples
  python torsion_scan.py inputs start.xyz --d1 1 7 27 24 --d2 7 27 24 23 --step 30 \\
      --engine gaussian --route "#p opt=modredundant B3LYP/6-311G(d,p) EmpiricalDispersion=GD3BJ SCRF=(PCM,Solvent=Water)"
  python torsion_scan.py collect outputs/*.log --d1 1 7 27 24 --d2 7 27 24 23 --step 30 \\
      --name "My molecule" --csv scan.csv --json molecule.json
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

SYMBOLS = ["X", "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S",
           "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge",
           "As", "Se", "Br", "Kr"]
COVALENT = {"H": .31, "B": .84, "C": .76, "N": .71, "O": .66, "F": .57, "Si": 1.11, "P": 1.07, "S": 1.05,
            "Cl": 1.02, "Br": 1.20, "I": 1.39}
HARTREE_TO_KJ = 2625.4996


# ---------- geometry ----------
def dihedral(X, a, b, c, d):
    """Dihedral a-b-c-d in degrees, (-180, 180]."""
    b0, b1, b2 = X[a] - X[b], X[c] - X[b], X[d] - X[c]
    b1 = b1 / np.linalg.norm(b1)
    v, w = b0 - np.dot(b0, b1) * b1, b2 - np.dot(b2, b1) * b1
    return math.degrees(math.atan2(np.dot(np.cross(b1, v), w), np.dot(v, w)))


def bonds(el, X, scale=1.2):
    n = len(el)
    nb = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if np.linalg.norm(X[i] - X[j]) < (COVALENT.get(el[i], .8) + COVALENT.get(el[j], .8)) * scale:
                nb[i].append(j)
                nb[j].append(i)
    return nb


def side(nb, b, c):
    """Atoms reached from c without crossing the b-c bond (the part that rotates)."""
    seen, stack = {c}, [c]
    while stack:
        i = stack.pop()
        for j in nb[i]:
            if (i == c and j == b) or j in seen:
                continue
            seen.add(j)
            stack.append(j)
    if b in seen:
        sys.exit(f"Atoms {b + 1}-{c + 1} are in a ring, so this dihedral cannot be rotated freely.")
    return sorted(seen)


def set_dihedral(el, X, quad, target, nb):
    a, b, c, d = quad
    move = side(nb, b, c)
    delta = math.radians(target - dihedral(X, a, b, c, d))
    axis = (X[c] - X[b]) / np.linalg.norm(X[c] - X[b])
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    R = np.eye(3) + math.sin(delta) * K + (1 - math.cos(delta)) * K @ K
    Y = X.copy()
    Y[move] = (X[move] - X[c]) @ R.T + X[c]
    return Y


# ---------- reading ----------
def read_xyz_frames(path):
    """Frames from .xyz / ORCA .allxyz (frames may be separated by '>'). Energy from the comment line."""
    lines = [l for l in Path(path).read_text().splitlines() if l.strip() != ">"]
    frames, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        n = int(lines[i].split()[0])
        comment = lines[i + 1]
        el, X = [], []
        for l in lines[i + 2:i + 2 + n]:
            p = l.split()
            el.append(p[0])
            X.append([float(v) for v in p[1:4]])
        m = re.search(r"\bE\s*[=:]?\s*(-?\d+\.\d+)", comment) or re.search(r"(-?\d+\.\d{5,})", comment)
        frames.append((el, np.array(X), float(m.group(1)) if m else None))
        i += 2 + n
    return frames


def read_gaussian(path):
    """Every converged structure in a Gaussian log: one for a single optimisation, many for a scan.
    Energy is the last 'SCF Done' before 'Stationary point found' (includes GD3/GD3BJ dispersion)."""
    text = Path(path).read_text(errors="replace").splitlines()
    out, energy, geom = [], None, None
    i = 0
    while i < len(text):
        line = text[i]
        if "SCF Done:" in line:
            energy = float(line.split("=")[1].split()[0])
        elif "Standard orientation:" in line or "Input orientation:" in line:
            j, el, X = i + 5, [], []
            while not text[j].startswith(" ----"):
                p = text[j].split()
                el.append(SYMBOLS[int(p[1])])
                X.append([float(v) for v in p[3:6]])
                j += 1
            geom = (el, np.array(X))
            i = j
        elif "Stationary point found" in line and geom and energy is not None:
            out.append((geom[0], geom[1], energy))
        i += 1
    if not out and "Normal termination" in "\n".join(text[-5:]) and geom and energy is not None:
        out.append((geom[0], geom[1], energy))  # e.g. a single point
    return out


def read_any(path):
    p = str(path).lower()
    if p.endswith((".xyz", ".allxyz")):
        return read_xyz_frames(path)
    return read_gaussian(path)


# ---------- commands ----------
def grid_values(step):
    n = int(round(360 / step))
    if abs(n * step - 360) > 1e-6:
        sys.exit("--step must divide 360 (e.g. 10, 15, 20, 30, 45, 60).")
    return [-180 + k * step for k in range(n)]


def canonical_half(a, b):
    """For an achiral molecule (a, b) and (-a, -b) are mirror images: compute one of each pair."""
    m = ((-a + 180) % 360 - 180, (-b + 180) % 360 - 180)
    return (a, b) <= m


def cmd_inputs(args):
    frames = read_any(args.start)
    if not frames:
        sys.exit(f"No structure found in {args.start}.")
    el, X, _ = frames[-1]
    q1, q2 = [v - 1 for v in args.d1], [v - 1 for v in args.d2]
    nb = bonds(el, X)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    vals = grid_values(args.step)
    made = 0
    for a in vals:
        for b in vals:
            if args.achiral and not canonical_half(a, b):
                continue
            Y = set_dihedral(el, X, q1, a, nb)
            Y = set_dihedral(el, Y, q2, b, bonds(el, Y))
            if abs(((dihedral(Y, *q1) - a + 180) % 360) - 180) > 0.5 or abs(((dihedral(Y, *q2) - b + 180) % 360) - 180) > 0.5:
                sys.exit("Could not set both dihedrals independently. Check that they share at most one bond.")
            stem = f"{args.prefix}_{a:+04d}_{b:+04d}"
            coords = "\n".join(f"{e:<2} {x:14.8f} {y:14.8f} {z:14.8f}" for e, (x, y, z) in zip(el, Y))
            if args.engine == "gaussian":
                body = (f"%chk={stem}.chk\n{args.route}\n\n{stem} tau1={a} tau2={b}\n\n{args.charge} {args.mult}\n"
                        f"{coords}\n\nD {' '.join(map(str, args.d1))} F\nD {' '.join(map(str, args.d2))} F\n\n")
                (out / f"{stem}.gjf").write_text(body)
            else:
                cons = (f"%geom\n  Constraints\n    {{ D {' '.join(map(str, q1))} C }}\n"
                        f"    {{ D {' '.join(map(str, q2))} C }}\n  end\nend\n")
                body = f"{args.route}\n{cons}\n* xyz {args.charge} {args.mult}\n{coords}\n*\n"
                (out / f"{stem}.inp").write_text(body)
            made += 1
    print(f"Wrote {made} {args.engine} inputs to {out}/ ({args.step}° grid"
          f"{', half grid by mirror symmetry' if args.achiral else ''}).")


def cmd_collect(args):
    q1, q2 = [v - 1 for v in args.d1], [v - 1 for v in args.d2]
    vals = grid_values(args.step)
    snap = lambda v: int(round(v / args.step) * args.step + 180) % 360 - 180
    cells, el_ref, skipped = {}, None, 0
    for path in args.files:
        for el, X, E in read_any(path):
            if E is None:
                skipped += 1
                continue
            if el_ref is None:
                el_ref = el
            elif el != el_ref:
                sys.exit(f"{path}: atoms differ from the first file. All outputs must be the same molecule, same atom order.")
            t1, t2 = dihedral(X, *q1), dihedral(X, *q2)
            a, b = snap(t1), snap(t2)
            if abs(((t1 - a + 180) % 360) - 180) > args.tol or abs(((t2 - b + 180) % 360) - 180) > args.tol:
                skipped += 1
                continue
            if (a, b) not in cells or E < cells[(a, b)][0]:
                cells[(a, b)] = (E, X)
    if not cells:
        sys.exit("No converged structures found on the grid. Check --d1/--d2 and --step.")
    # superpose every structure on the lowest one using the atoms that don't rotate, so the viewer
    # shows only the flexible part moving (proper rotations only)
    ref = min(cells.values(), key=lambda t: t[0])[1]
    nb = bonds(el_ref, ref)
    moving = set(side(nb, q1[1], q1[2])) | set(side(nb, q2[1], q2[2]))
    core = [i for i in range(len(el_ref)) if i not in moving]
    if len(core) < 3:
        core = list(range(len(el_ref)))
    def align(X):
        P, Q = X[core], ref[core]
        pc, qc = P.mean(0), Q.mean(0)
        u, _, vt = np.linalg.svd((P - pc).T @ (Q - qc))
        r = u @ np.diag([1, 1, np.sign(np.linalg.det(u @ vt))]) @ vt
        return (X - pc) @ r + qc
    mirrored = set()
    if args.achiral:
        for (a, b), (E, X) in list(cells.items()):
            m = (snap(-a), snap(-b))
            if m not in cells:
                cells[m] = (E, X * np.array([1, 1, -1]))
                mirrored.add(m)
    cells = {k: (E, align(X)) for k, (E, X) in cells.items()}
    missing = [(a, b) for a in vals for b in vals if (a, b) not in cells]
    e0 = min(E for E, _ in cells.values())
    if args.csv:
        rows = ["tau1,tau2,energy_kJmol"] + [f"{a},{b},{(cells[(a, b)][0] - e0) * HARTREE_TO_KJ:.4f}"
                                              for a in vals for b in vals if (a, b) in cells]
        Path(args.csv).write_text("\n".join(rows) + "\n")
        print(f"Wrote {args.csv}: {len(rows) - 1} points, energies in kJ/mol relative to the lowest.")
    if args.json:
        if missing:
            print(f"Note: {len(missing)} grid points have no structure, so the molecule file has gaps. "
                  "The explorer needs a complete grid; rerun or fix those points first.", file=sys.stderr)
        key = re.sub(r"[^A-Za-z0-9_-]", "", args.name) or "mol"
        mol = {"key": key, "name": args.name, "sub": args.sub, "names": [args.n1, args.n2],
               "spacing": args.step, "achiral": bool(args.achiral),
               "grid": [[a, b, round((cells[(a, b)][0] - e0) * HARTREE_TO_KJ, 3)] for a in vals for b in vals if (a, b) in cells],
               "minima": [], "barriers": []}
        geo = {"el": el_ref, "dih": [q1, q2],
               "cells": {f"{a},{b}": [round(v, 3) for v in X.ravel()] for (a, b), (_, X) in cells.items()},
               "minima": [], "sym": sorted(f"{a},{b}" for a, b in mirrored)}
        Path(args.json).write_text(json.dumps({"molecule": mol, "geometry": geo}, ensure_ascii=False, separators=(",", ":")))
        print(f"Wrote {args.json}: {len(cells)} structures. Add DFT minima and barriers to 'minima' and "
              "'barriers' by hand if you have them (see README).")
    if skipped:
        print(f"Skipped {skipped} structures that were unconverged or off the grid (tolerance {args.tol}°).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--d1", type=int, nargs=4, required=True, metavar="ATOM", help="first dihedral, atoms numbered from 1")
    common.add_argument("--d2", type=int, nargs=4, required=True, metavar="ATOM", help="second dihedral, atoms numbered from 1")
    common.add_argument("--step", type=float, default=30, help="grid step in degrees (default 30)")
    common.add_argument("--achiral", action="store_true", help="molecule is achiral: use mirror symmetry for half the grid")

    p = sub.add_parser("inputs", parents=[common], help="write one constrained optimisation per grid point")
    p.add_argument("start", help="starting structure (.xyz, or a Gaussian .log)")
    p.add_argument("--engine", choices=["gaussian", "orca"], default="gaussian")
    p.add_argument("--route", required=True, help='Gaussian route line ("#p opt=modredundant ...") or ORCA simple input ("! ... Opt")')
    p.add_argument("--charge", type=int, default=0)
    p.add_argument("--mult", type=int, default=1)
    p.add_argument("--outdir", default="scan_inputs")
    p.add_argument("--prefix", default="scan")
    p.set_defaults(func=cmd_inputs)

    p = sub.add_parser("collect", parents=[common], help="read finished outputs and write the explorer's files")
    p.add_argument("files", nargs="+", help="Gaussian .log/.out, or .xyz/.allxyz with the energy (Hartree) in the comment line")
    p.add_argument("--csv", help="write a scan CSV for the scan loader")
    p.add_argument("--json", help="write a molecule file with structures for the molecule loader")
    p.add_argument("--name", default="My molecule")
    p.add_argument("--sub", default="")
    p.add_argument("--n1", default="χ1", help="label for the first dihedral")
    p.add_argument("--n2", default="χ2", help="label for the second dihedral")
    p.add_argument("--tol", type=float, default=2.0, help="how far (°) a dihedral may drift from its grid value")
    p.set_defaults(func=cmd_collect)

    args = ap.parse_args()
    if args.cmd == "collect" and not (args.csv or args.json):
        ap.error("collect needs --csv and/or --json")
    if args.step <= 0:
        ap.error("--step must be positive")
    args.step = int(args.step) if float(args.step).is_integer() else args.step
    args.func(args)


if __name__ == "__main__":
    main()
