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
| `build.py` | Embeds the data and fonts into the template and writes `site/index.html` |
| `fonts/` | Spectral, IBM Plex Sans and IBM Plex Mono (SIL Open Font License) |
| `desktop/` | Electron wrapper for the Windows app |

## Licence

Code: MIT, see [LICENSE](LICENSE). Fonts: SIL OFL 1.1, see `fonts/OFL-*.txt`.
Bundled DMT data: see [Data](#data).
