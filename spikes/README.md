# Versioned isotope-dilution tracers

`registry.toml` is a format-1 manifest, independent of the material library.
It lists one solution TOML per stable spike ID, a citation registry, and a
version lock. IDs and sub-fraction IDs match
`^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$`. Version labels use the same syntax.
A calibration belongs to one physical sub-fraction (bottle, batch or aliquot).
Use `unassigned` when its identity is unknown; never infer a bottle name.

Each solution records its name, aliases, IDTIMS `spike_type`, enriched
isotopes, description, visibility, sub-fractions and versions. Each version
records its sub-fraction, unique version label, status (`current`,
`superseded`, `withdrawn`), source key and table/page `locator`. Optional
fields are `supersedes` (within the same sub-fraction), `calibrated`, `notes`
and `legacy = [{ name = "old-name", version = "old-version" }]` mappings.
Legacy mappings must resolve uniquely across all layers. Consumers must
request a sub-fraction/version when a name alone is ambiguous.

`concentrations` maps isotope labels such as `205Pb` to value tables with
`unit = "mol/g"`. `ratios` uses labels such as `206Pb/205Pb` and dimensionless
values. A measurement may include both `uncertainty` and `uncertainty_type`:
`1sd_rel_pct`, `2sd_rel_pct`, `1sd_abs`, or `2sd_abs`. Missing uncertainty means
unknown, never zero. Preserve source numbers and uncertainty coverage;
do not derive reciprocal or cross-ratios unless the source lists them.

## Public values and citations

Only published EARTHTIME values verified in the cited paper belong here.
Every stored public value is covered by its version's `locator`.
The initial `ET535/master/v3` and `ET2535/master/v3` records transcribe
Condon et al. (2015), **Table 3, p. 474 (PDF p. 11)**, including the printed
absolute 1-sigma uncertainties and actual solution concentrations. The DOI
in `../sources.toml` is printed on the paper's first page. No extra digits,
normalised concentrations, derived ratios or unpublished calibrations are
substituted for that table.

All laboratory-specific solutions and bottle/sub-fraction calibrations,
and any value not found in the publication, belong in a private overlay.
Concentrations normalised to nominal 1e-9 mol/g 235U are not published
concentrations. Put those records and their evidence only in private storage.

## Paths and overlays

Citation paths are relative to the manifest. The public manifest retains the
contract's `spikes/` prefix on `spike_files` and `lock`. The checker treats
this as a logical prefix and resolves the remainder within the manifest
directory, so the registry can also be copied to another directory name.
Other paths are relative to the manifest directory. Absolute paths and paths escaping the
registry root are rejected for spike files and locks.

An overlay directory has a `registry.toml`, solution files and its own
`versions.lock.json`. It uses the same format with `visibility = "private"`.
For example, its manifest can use `spike_files = ["ET535.toml"]` and
`lock = "versions.lock.json"`. It can include its own `sources.toml` or
reference source keys already loaded from the public registry. A standalone
overlay must supply every source it uses. Sources with the same key must
agree exactly.

Overlays may add solutions, aliases, sub-fractions and versions. Repeating a
spike ID extends that solution; repeating a version key is always an error,
even if its content matches. Repeated sub-fraction definitions must agree.
`supersedes` may reference a version in an earlier layer of the same
sub-fraction. Aliases cannot identify different spikes. Preserve an existing
spike's type when extending it. Visibility is retained per version and
sub-fraction; a private extension does not make a public version private.

```sh
python3 spikes/check.py
python3 spikes/check.py --overlay /path/to/private/overlay
python3 spikes/check.py --overlay /path/to/private/overlay --update-lock
```

The checker uses Python 3.11+ and only the standard library. `--registry PATH`
selects a different manifest or directory. Use `--overlay-only --overlay PATH`
to validate a self-contained private overlay without a public registry.

## Immutability and adding a calibration

A lock maps `<spike id>/<subfraction>/<version>` to a lowercase SHA-256 hex
digest. The hashed object is the **parsed TOML version table**, including all
nested measurements and legacy mappings, with only its top-level `status`
and `notes` removed. Serialize it with Python
`json.dumps(object, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
allow_nan=False)`, encode as UTF-8 (no trailing newline), and hash those bytes.
TOML floats use Python's JSON float representation. Whitespace and numeric
spelling do not affect the hash when they parse to the same number. Array
order does affect it. Solution/sub-fraction metadata are outside the version
hash; identity is supplied by the lock key.

1. Verify the paper and decide public versus private before writing values.
2. Add a sub-fraction if needed. Append a new version with a new label, exact
   source numbers, source key, locator and explicit uncertainty convention.
3. Optionally mark a prior version `superseded` or `withdrawn`. Do not alter
   its measurements, source, locator or legacy mappings. A correction is a
   new version. Set `supersedes` only when the evidence supports the link.
4. Run the checker with `--update-lock`, then without it, and review the diff.

`--update-lock` appends missing keys only. It refuses changed or deleted
locked versions, and validates the entire merge before writing any locks.
It never repairs a changed hash. Keep the lock in version control beside
its registry. The lock detects accidental edits; it is not a signature or
a substitute for reviewing changes to the lock itself.
