# Torsion Explorer

An interactive viewer for relaxed 2D torsional energy surfaces. Drag a probe across the surface
and read the local Hessian, ∂²E/∂τᵢ∂τⱼ: its eigenvectors are the directions of strongest and
weakest curvature, and their signs separate a conformer from a transition state. The optimised
structure at each grid point floats over the landscape, so you can watch the molecule change as
you move.

It ships with one surface, N,N-dimethyltryptamine (DMT), and loads your own data in the browser.
Nothing is uploaded anywhere: files you load stay in that tab.

## Run it

All three are fully offline (data, code and fonts are embedded):

1. **Open `site/index.html`** in any browser.
2. **Docker:**

   ```bash
   docker build -t torsion-explorer .
   docker run --rm -p 8080:80 torsion-explorer   # then open http://localhost:8080
   ```

3. **Windows app:** see [Desktop app](#desktop-app).

After changing `src/template.html` or `data/`, rebuild the page with `python build.py`
(standard library only).

## Making a scan

The explorer doesn't run any chemistry. You make a relaxed 2D scan in your own quantum chemistry
software, then load the results. A relaxed scan means: freeze the two dihedrals at each grid
point and let every other coordinate optimise.

### 1. Pick your two dihedrals

Each dihedral is four atoms, and the bond you want to rotate is the middle two. Get the atom
numbers from GaussView, Avogadro or your input file. **Count from 1**, as those programs do; the
helper script converts where needed. The two dihedrals can share one bond (as χ1 and χ2 do in
DMT's side chain), but they can't be part of a ring.

### 2. Choose a grid

| Step | Points | Points if achiral (mirror symmetry) |
|---|---|---|
| 30° | 144 | 74 |
| 20° | 324 | 164 |
| 10° | 1296 | 650 |

30° is enough to see the shape of the surface and find the minima. 10° gives smooth barriers and
a smooth 3D animation, at about nine times the cost. If the molecule is achiral, (τ1, τ2) and
(−τ1, −τ2) are mirror images with the same energy, so you only need to compute half.

### 3. Make one input per grid point

[`scripts/torsion_scan.py`](scripts/torsion_scan.py) (needs only numpy) takes one starting
structure, rotates it to every grid point and writes a constrained optimisation for each:

```bash
# Gaussian (.gjf); --route is your usual route line, it must include opt=modredundant
python scripts/torsion_scan.py inputs start.xyz --d1 1 7 27 24 --d2 7 27 24 13 --step 30 --achiral \
  --engine gaussian \
  --route "#p opt=modredundant B3LYP/6-311G(d,p) EmpiricalDispersion=GD3BJ SCRF=(PCM,Solvent=Water)"

# ORCA (.inp); --route is your simple-input line, it must include Opt
python scripts/torsion_scan.py inputs start.xyz --d1 1 7 27 24 --d2 7 27 24 13 --step 30 \
  --engine orca --route "! B3LYP D3BJ def2-TZVP Opt CPCM(water)"
```

`start.xyz` should be a reasonable optimised structure (a Gaussian `.log` works too). Use
`--charge` and `--mult` if it isn't a neutral singlet. Files land in `scan_inputs/`, named by
grid point, e.g. `scan_-180_+030.gjf`. Each Gaussian input ends with the two frozen dihedrals:

```
D 1 7 27 24 F
D 7 27 24 13 F
```

and each ORCA input carries them as constraints (ORCA counts atoms from 0, the script handles it):

```
%geom
  Constraints
    { D 0 6 26 23 C }
    { D 6 26 23 12 C }
  end
end
```

Run them however you normally run jobs; they are independent, so they parallelise perfectly on a
cluster. If you'd rather do a single nested scan inside Gaussian (two `D … S n step` lines) or
ORCA, that works too: the collect step reads every converged structure in a log.

### 4. Collect the results

```bash
python scripts/torsion_scan.py collect outputs/*.log --d1 1 7 27 24 --d2 7 27 24 13 --step 30 --achiral \
  --name "My molecule" --n1 χ1 --n2 χ2 --csv scan.csv --json molecule.json
```

Use the same `--d1`, `--d2`, `--step` and `--achiral` as before. It reads Gaussian `.log`/`.out`
files (the last SCF energy at each converged structure, so GD3/GD3BJ dispersion is included) and
`.xyz` files with the energy in Hartree in the comment line, as ORCA writes them. It measures
both dihedrals on each final structure, puts it on the nearest grid point, keeps the lowest
energy if a point appears twice, and skips anything that drifted more than `--tol` degrees
(default 2°) from its grid value. With `--achiral` it fills the other half by reflection. Then:

- **`scan.csv`** goes into the scan loader (choose kJ/mol as the unit).
- **`molecule.json`** goes into the molecule loader and gives the full view, including the 3D
  structure at every grid point.

The molecule loader needs a complete grid. If some points failed, the script tells you how many;
rerun those or use the CSV, which is fitted with a Fourier series when points are missing.

### 5. Optional: add minima and barriers

The script fills in the surface and structures. The **DFT minima** and **Rotation barriers**
panels come from the `minima` and `barriers` lists in `molecule.json`, which you add by hand
from your own fully optimised minima (see the format below). Leave them empty and those panels
are simply blank; the surface, Hessian readout and stationary points work either way.

## Load your own data

Open **Load your own data** at the bottom of the page. Two options:

### 1. A 2D scan (CSV or text)

Three columns: τ1 (°), τ2 (°), energy. Commas, tabs or spaces; header lines are skipped. Pick
the energy unit (Hartree, kcal/mol, kJ/mol or eV). A complete regular grid is interpolated with
a periodic bicubic spline, exact at every point; anything else is fitted with a periodic Fourier
series and the RMS residual is reported. Try [`examples/example-scan.csv`](examples/example-scan.csv).

### 2. A molecule file (JSON)

For the full view: DFT minima, rotation barriers and, optionally, the 3D structure at every grid
point. Start from [`examples/example-molecule.json`](examples/example-molecule.json).

```jsonc
{
  "molecule": {
    "key": "mymol",                 // short id, letters/digits only
    "name": "My molecule",
    "sub": "Optional subtitle",
    "names": ["χ1", "χ2"],          // labels for the two dihedrals
    "spacing": 30,                  // grid step in degrees
    "achiral": false,               // true draws each minimum's mirror image too
    "grid": [[-180, -180, 5.41], …],        // complete regular grid: τ1 (°), τ2 (°), E (kJ/mol)
    "minima":   [{"x": -160.3, "y": -60.0, "dG": 0.0, "pop": 31.4, "label": "A"}],  // optional
    "barriers": [{"dih": "χ1", "grid": 14.7, "scan": 16.5}]                           // optional, kJ/mol
  },
  "geometry": {                     // optional: enables the 3D molecule
    "el": ["C", "C", "N", …],       // element symbols, one per atom
    "dih": [[0, 6, 26, 23], [6, 26, 23, 22]],   // the two dihedrals as atom-index quadruples
    "cells": {"-180,-180": [x0, y0, z0, x1, …], …},  // flat Å coordinates per grid point, key "τ1,τ2"
    "minima": [[x0, y0, z0, …], …], // one coordinate list per entry in molecule.minima
    "sym": ["-180,10", …]           // optional: cells filled by mirror symmetry
  }
}
```

Energies in `grid` are shifted so the lowest point is zero. Leave out a cell in `cells` to mark
that grid point as excluded (it is drawn hatched).

Two things that catch people out: angles are in degrees and energies in `grid` are in **kJ/mol**;
and atom indices in `geometry.dih` count from **0**, so Gaussian's `D 1 7 27 24` is
`[0, 6, 26, 23]`. The collect script writes both correctly.

## How the bundled surface was made

B3LYP-D3(BJ)/6-311G(d,p) with PCM water (Gaussian 16). χ1 and χ2 frozen on a 10° grid with every
other coordinate optimised at each point; DMT is achiral, so half the grid was computed and the
rest filled by mirror symmetry. Minima were fully re-optimised with frequencies; free energies
use Grimme's quasi-RRHO entropy (100 cm⁻¹ cutoff) at 298.15 K.

## Data

The DMT surface and structures in `data/` are from work in preparation by M. Salha, J. Kim and
G. Chass. They are shared here to demonstrate the tool and are **not** covered by the MIT licence.
Please don't reuse or cite them before the paper is out; contact the author instead.

## Desktop app

`desktop/` wraps the page in Electron (sandboxed window, no network).

```bash
cd desktop
npm install
npm approve-scripts electron && npm rebuild electron
npm run selftest   # loads the page in a hidden window and prints a check line
npm run dist       # -> desktop/dist/TorsionExplorer-<version>-portable.exe
```

The `.exe` is unsigned, so Windows SmartScreen warns on first run (More info → Run anyway).

## Layout

| Path | What it is |
|---|---|
| `src/template.html` | The page: styles, layout and all rendering and interaction code |
| `data/data.json` | The bundled surface, DFT minima and barriers |
| `data/geom.json` | The bundled structures, one per grid cell, plus the minima |
| `examples/` | A made-up scan and molecule file for trying the loaders |
| `scripts/torsion_scan.py` | Makes the grid of inputs and collects the outputs into the explorer's formats |
| `build.py` | Embeds the data and fonts into the template and writes `site/index.html` |
| `fonts/` | Spectral, IBM Plex Sans and IBM Plex Mono (SIL Open Font License) |
| `desktop/` | Electron wrapper for the Windows app |

## Licence

Code: MIT, see [LICENSE](LICENSE). Fonts: SIL OFL 1.1, see `fonts/OFL-*.txt`.
Bundled DMT data: see [Data](#data).
