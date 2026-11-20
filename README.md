<p align="center">
  <img src="assets/icon-256.png" width="112" alt="">
</p>

<h1 align="center">upb-standards</h1>

<p align="center">Reference-material values with full citations for LA-ICP-MS U-Pb and trace-element reduction</p>

<p align="center">
  <a href="https://duserzym.github.io/upb-standards/">Browse the library</a> ·
  <a href="https://duserzym.github.io/upb-standards/sources.html">Sources</a> ·
  <a href="https://github.com/duserzym/grainatlas">GrainAtlas</a> ·
  <a href="https://github.com/duserzym/upblab">UPb Lab</a> ·
  <a href="https://github.com/duserzym/UPbRPy">UPbRPy</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/materials-1440x900-dark.png">
  <img src="docs/images/materials-1440x900-light.png" width="100%" alt="Reference materials in the library">
</picture>

A format-2 TOML library of reference-material values for UPbRPy. It records
source quantities, uncertainties, measurement conventions and citations for
zircon, apatite, titanite, rutile, glass, carbonate and hematite. UPbRPy derives
reciprocal and linked ratios from these inputs.

## What is in it

This table is generated from `library.toml` and the material files. Imported
records keep their own names and may share aliases with other standards.

<!-- materials:start -->
| Mineral | Standards | Count |
| --- | --- | ---: |
| apatite | AFB1, BR5, IOLITE_A_DURANGO, IOLITE_A_MAD, MADUCSB, IOLITE_A_MCCLURE, OL2 | 7 |
| carbonate | IOLITE_C_MMC, IOLITE_WC_1 | 2 |
| glass | BCR, BIR, GSD, GSE, IOLITE_G_BCR2G, IOLITE_G_BHVO2G, IOLITE_G_GSD1G, IOLITE_NIST_16, IOLITE_G_NIST610, IOLITE_G_NIST611, IOLITE_G_NIST612, IOLITE_G_NIST614, IOLITE_NIST_614_NEW, IOLITE_G_NIST616, NIST610, NIST612 | 16 |
| hematite | IOLITE_H_HFO | 1 |
| rutile | KNW, R632 | 2 |
| titanite | BLR, ElMuerto, KHAN, MKED, OLT | 5 |
| zircon | 91500, AUSZ2, FC1, IOLITE_Z_91500, IOLITE_FC1, IOLITE_Z_FCTUFF, IOLITE_Z_GJ1, IOLITE_Z_MANIITSOQ, IOLITE_Z_OG1, IOLITE_Z_PLESOVICE, IOLITE_Z_TEMORA2, LTSE, OG1, PL, R33, S513, Seiland, Temora | 18 |
<!-- materials:end -->

Regenerate the table with `python3 site/build.py --readme`.

## How UPbRPy uses it

UPbRPy bundles a copy of the library. To load another checkout, pass its
directory or `library.toml` to `UPbRPy.load_standard_measurements(path)`.
In Studio, choose **File → Reference Material Library** and select
`library.toml` to adopt a reviewed library. The older wide CSV remains a
separate compatibility archive.

Keep a clone at `~/UPbRPy/upb-standards` for the desktop apps, or set
`UPB_STANDARDS_DIR` before launching an app to use another clone.
Git must be on the app’s path.

In Updates, **Check standards** fetches Git metadata and compares the clone’s
TOML files with GitHub main. It lists differences and checks whether the
active library digest differs from the clone. If GitHub is unavailable,
it uses the last checked revision when available, otherwise local HEAD.
Checking never adopts or edits values.

Record the Git revision and library digest when archiving a reduction.
[Usage and provenance details](https://duserzym.github.io/upb-standards/upbrpy.html).

## Conventions

Keep isotope systems, initial Pb, radiogenic ratios, total ratios and
uncertainty conventions distinct. Missing uncertainties are not zero.
Each measurement records its role, unit, status and source.
[Read the conventions and derivation rules](https://duserzym.github.io/upb-standards/conventions.html).

[The 2026-11 audit lists what was checked and what is not yet verified.](https://github.com/duserzym/upb-standards/blob/main/docs/audit-2026-11.md)

## ID-TIMS tracers

The separate [versioned spike registry](spikes/README.md) records published
EARTHTIME tracer compositions, sub-fractions, calibration versions and
append-only locks. Private calibrations extend it through private overlays.
Run `python3 spikes/check.py` to validate the public records.

## How to cite

Cite this library as **upb-standards**,
<https://github.com/duserzym/upb-standards>, with the Git revision used.
Always also cite the original publications listed for each value in the
[source registry](https://duserzym.github.io/upb-standards/sources.html).
Keep the full library digest with the archived reduction.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/sources-1440x900-dark.png">
  <img src="docs/images/sources-1440x900-light.png" width="100%" alt="Source registry with full literature citations">
</picture>

## Contributing a material

Add documented source quantities in a material TOML file, register it in
`library.toml`, and link each measurement to a full citation in
`sources.toml`. Include the source locator, uncertainty convention and
status. Run UPbRPy’s library checks and regenerate the manual and this
table. [Instructions and a complete example](https://duserzym.github.io/upb-standards/contributing.html).

Build and check the manual locally with Python 3.11 or later:

```sh
python3 site/build.py --out _site --check
```

Open `_site/index.html` directly; no server is needed. Generate the icon SVGs
from the mineral crystals with `python3 assets/make_icon.py`, then render the
PNGs with `sh assets/make_icons.sh` (requires `rsvg-convert`).
The mineral marks are crystals from the
[Mineral Habit Atlas](https://duserzym.github.io/mineral-habit-matrix/); the site
spins them live and falls back to still SVGs. Redraw them with
`python3 assets/make_mineral_icons.py <mineral-habit-matrix>/site/data/atlas.json`.
The Pages
workflow runs by hand with `gh workflow run pages`.

## Related apps

- **[GrainAtlas](https://github.com/duserzym/grainatlas)**: stitch SEM images of grain mounts, find grains, place laser spots and print sheets.
- **[UPb Lab](https://github.com/duserzym/upblab)**: one window for the lab workflow: sessions, images and review of stored results.
- **[UPbRPy](https://github.com/duserzym/UPbRPy)**: data reduction engine and desktop Studio for LA-ICP-MS U-Pb and trace elements.
- **UPbDB**: the lab database server for sessions, spots and stored reductions (private).

## License

[MIT](LICENSE).
