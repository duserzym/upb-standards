"""Validate format-1 spike registries and append-only calibration locks (stdlib only).

This file is also vendored by consumers; keep copies identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}\Z")
ISOTOPE = r"[1-9][0-9]*[A-Z][a-z]?"
UNCERTAINTIES = {"1sd_rel_pct", "2sd_rel_pct", "1sd_abs", "2sd_abs"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_toml(path, **kwargs):
    with Path(path).open('rb') as stream:
        return tomllib.load(stream, **kwargs)


def digest(version):
    """SHA-256 of UTF-8 json.dumps of the parsed version, except status/notes."""
    content = {k: v for k, v in version.items() if k not in {"status", "notes"}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode('utf-8')).hexdigest()


def manifest_path(path):
    path = Path(path)
    return path / 'registry.toml' if path.is_dir() else path


def local_path(manifest, value):
    # 'spikes/' is the contract's logical prefix, even when a registry
    # directory is copied or selected through an environment variable.
    require(isinstance(value, str) and value and not Path(value).is_absolute(),
            f'{manifest}: expected a relative registry path: {value!r}')
    base = manifest.parent
    relative = value.removeprefix('spikes/')
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), f'{manifest}: path escapes registry root: {value}')
    return path


def fields(record, required, optional, context):
    require(isinstance(record, dict), f'{context}: expected a table')
    require(set(required) <= record.keys(), f'{context}: missing fields {sorted(set(required) - record.keys())}')
    require(record.keys() <= set(required) | set(optional), f'{context}: unknown fields {sorted(record.keys() - set(required) - set(optional))}')


def identifier(value, context):
    require(isinstance(value, str) and ID.fullmatch(value), f'{context}: invalid identifier {value!r}')


def strings(values, context):
    require(isinstance(values, list) and all(isinstance(x, str) and x for x in values), f'{context}: expected nonempty strings in a list')
    require(len(values) == len(set(values)), f'{context}: duplicate entries')


def number(value, context):
    require(type(value) in (int, float) and value >= 0 and value < float('inf'), f'{context}: expected finite nonnegative number')


def read_registry(path, *, private=False, inherited_sources=None):
    """Read and validate one registry; return manifest, spike dictionaries, sources."""
    manifest = manifest_path(path)
    data = read_toml(manifest)
    fields(data, ['format_version', 'spike_files', 'lock'], ['sources'], str(manifest))
    require(type(data['format_version']) is int and data['format_version'] == 1, f'{manifest}: unsupported format_version')
    strings(data['spike_files'], f'{manifest}: spike_files')
    require(isinstance(data['lock'], str), f'{manifest}: lock must be a path')
    sources = dict(inherited_sources or {})
    if 'sources' in data:
        # Citations may intentionally live one directory above the manifest.
        source_data = read_toml(manifest.parent / data['sources'])
        require(isinstance(source_data.get('sources'), dict), f'{manifest}: invalid source registry')
        for key, citation in source_data['sources'].items():
            require(isinstance(citation, dict) and isinstance(citation.get('display'), str), f'{manifest}: invalid source {key}')
            require(key not in sources or sources[key] == citation, f'{manifest}: conflicting source {key}')
            sources[key] = citation
    spikes = []
    ids = set()
    for filename in data['spike_files']:
        document = read_toml(local_path(manifest, filename))
        fields(document, ['format_version', 'spike'], [], filename)
        require(type(document['format_version']) is int and document['format_version'] == 1, f'{filename}: unsupported format_version')
        spike = document['spike']
        fields(spike, ['id', 'name', 'aliases', 'spike_type', 'isotopes', 'description', 'visibility', 'subfractions', 'versions'], [], filename)
        sid = spike['id']
        identifier(sid, filename)
        require(sid not in ids, f'{manifest}: duplicate spike {sid}')
        ids.add(sid)
        for field in ('name', 'spike_type', 'description'):
            require(isinstance(spike[field], str) and spike[field], f'{sid}: invalid {field}')
        require(spike['visibility'] == ('private' if private else 'public'), f'{sid}: invalid visibility')
        strings(spike['aliases'], f'{sid}: aliases')
        strings(spike['isotopes'], f'{sid}: isotopes')
        require(bool(spike['isotopes']) and all(re.fullmatch(ISOTOPE, s) for s in spike['isotopes']), f'{sid}: invalid isotopes')
        require(isinstance(spike['subfractions'], list) and isinstance(spike['versions'], list), f'{sid}: expected subfractions/versions arrays')
        subids = set()
        for sub in spike['subfractions']:
            fields(sub, ['id', 'name'], ['notes'], sid)
            identifier(sub['id'], sid)
            require(sub['id'] not in subids, f'{sid}: duplicate subfraction {sub["id"]}')
            require(isinstance(sub['name'], str) and sub['name'], f'{sid}: invalid subfraction name')
            if 'notes' in sub:
                require(isinstance(sub['notes'], str), f'{sid}: invalid subfraction notes')
            subids.add(sub['id'])
        seen = set()
        for v in spike['versions']:
            fields(v, ['subfraction', 'version', 'status', 'source', 'locator'],
                   ['supersedes', 'calibrated', 'notes', 'legacy', 'concentrations', 'ratios'], sid)
            identifier(v['version'], sid)
            require(v['subfraction'] in subids, f'{sid}: unknown subfraction {v["subfraction"]}')
            key = (v['subfraction'], v['version'])
            require(key not in seen, f'{sid}: duplicate version {key}')
            seen.add(key)
            require(v['status'] in {'current', 'superseded', 'withdrawn'}, f'{sid}/{key}: invalid status')
            require(v['source'] in sources, f'{sid}/{key}: unknown source {v["source"]}')
            for field in ('locator', 'notes', 'calibrated'):
                if field in v:
                    require(isinstance(v[field], str) and v[field], f'{sid}/{key}: invalid {field}')
            require(v.get('concentrations') or v.get('ratios'), f'{sid}/{key}: empty composition')
            for group in ('concentrations', 'ratios'):
                require(isinstance(v.get(group, {}), dict), f'{sid}/{key}: invalid {group}')
                for label, measurement in v.get(group, {}).items():
                    pattern = ISOTOPE if group == 'concentrations' else ISOTOPE + '/' + ISOTOPE
                    require(re.fullmatch(pattern, label), f'{sid}/{key}: invalid isotope label {label}')
                    fields(measurement, ['value'] + (['unit'] if group == 'concentrations' else []),
                           ['uncertainty', 'uncertainty_type'], label)
                    number(measurement['value'], label)
                    if group == 'concentrations':
                        require(measurement['unit'] == 'mol/g', f'{label}: expected mol/g')
                    require(('uncertainty' in measurement) == ('uncertainty_type' in measurement), f'{label}: uncertainty and uncertainty_type must occur together')
                    if 'uncertainty' in measurement:
                        number(measurement['uncertainty'], label)
                        require(measurement['uncertainty_type'] in UNCERTAINTIES, f'{label}: invalid uncertainty_type')
            require(isinstance(v.get('legacy', []), list), f'{sid}/{key}: invalid legacy mappings')
            for legacy in v.get('legacy', []):
                fields(legacy, ['name', 'version'], [], sid)
                identifier(legacy['name'], sid)
                identifier(legacy['version'], sid)
        spikes.append(spike)
    return manifest, spikes, sources


def check_registries(public=None, overlays=(), *, update_lock=False):
    """Validate the entire merge before writing any append-only lock updates."""
    layers, sources, keys, names, legacy_keys, subfractions, types = [], {}, set(), {}, set(), {}, {}
    versions = {}
    paths = ([(public, False)] if public is not None else []) + [(p, True) for p in overlays]
    for path, private in paths:
        manifest, spikes, layer_sources = read_registry(path, private=private, inherited_sources=sources)
        sources.update(layer_sources)
        hashes = {}
        for spike in spikes:
            sid = spike['id']
            # An overlay may describe its own isotope list, but may not change the type.
            require(sid not in types or types[sid] == spike['spike_type'], f'{sid}: conflicting spike_type')
            types[sid] = spike['spike_type']
            for name in [sid, spike['name'], *spike['aliases']]:
                require(name not in names or names[name] == sid, f'ambiguous alias {name}')
                names[name] = sid
            for sub in spike['subfractions']:
                k = (sid, sub['id'])
                require(k not in subfractions or subfractions[k] == sub, f'{sid}: conflicting subfraction {sub["id"]}')
                subfractions[k] = sub
            for v in spike['versions']:
                key = f'{sid}/{v["subfraction"]}/{v["version"]}'
                require(key not in keys, f'overlay may never redefine an existing version: {key}')
                keys.add(key)
                versions[key] = v
                hashes[key] = digest(v)
                for legacy in v.get('legacy', []):
                    lk = (legacy['name'], legacy['version'])
                    require(lk not in legacy_keys, f'ambiguous legacy mapping {lk}')
                    require(legacy['name'] not in names or names[legacy['name']] == sid, f'ambiguous legacy name {legacy["name"]}')
                    names[legacy['name']] = sid
                    legacy_keys.add(lk)
        lock_path = local_path(manifest, read_toml(manifest)['lock'])
        lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
        require(isinstance(lock, dict) and all(isinstance(k, str) and isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for k, v in lock.items()), f'{lock_path}: invalid lock')
        for key, old in lock.items():
            require(key in hashes, f'{lock_path}: locked version removed: {key}')
            require(hashes[key] == old, f'{lock_path}: locked version changed: {key}; add a new version')
        missing = hashes.keys() - lock.keys()
        require(update_lock or not missing, f'{lock_path}: unlocked versions {sorted(missing)}; run --update-lock')
        layers.append((manifest, spikes, layer_sources, lock_path, lock, hashes))
    for key, v in versions.items():
        prefix = key.rsplit('/', 1)[0]
        chain, cursor = {key}, v
        while 'supersedes' in cursor:
            target = prefix + '/' + cursor['supersedes']
            require(target in versions, f'{key}: supersedes references unknown version {target}')
            require(target not in chain, f'{key}: supersedes cycle')
            chain.add(target)
            cursor = versions[target]
    if update_lock:
        for _, _, _, path, lock, hashes in layers:
            if lock.keys() != hashes.keys():
                path.write_text(json.dumps({**lock, **hashes}, sort_keys=True, indent=2) + '\n')
    return [(m, s, c) for m, s, c, *_ in layers]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--overlay', action='append', type=Path, default=[])
    parser.add_argument('--overlay-only', action='store_true', help='validate private layers without a public registry')
    parser.add_argument('--update-lock', action='store_true', help='append missing hashes; never replace existing hashes')
    args = parser.parse_args()
    try:
        layers = check_registries(None if args.overlay_only else args.registry,
                                  args.overlay, update_lock=args.update_lock)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'spike registry: {error}\n')
    count = sum(len(s['versions']) for _, spikes, _ in layers for s in spikes)
    print(f'Validated {count} versions in {len(layers)} registries.')


if __name__ == '__main__':
    main()
