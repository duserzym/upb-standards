#!/usr/bin/env python3
"""Build the offline manual from the format-2 TOML library (Python 3.11+).

python3 site/build.py --out _site --check
python3 site/build.py --readme

No packages, network access, or UPbRPy installation are needed to build.
"""

import sys

sys.dont_write_bytecode = True

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
REPO_URL = "https://github.com/duserzym/upb-standards"
UPBRPY_URL = "https://github.com/duserzym/UPbRPy"
AUDIT_URL = f"{REPO_URL}/blob/main/docs/audit-2026-11.md"
ROLES = {
    "concentration": "concentration",
    "initial_ratio": "initial Pb",
    "radiogenic_ratio": "radiogenic ratio",
    "total_ratio": "total ratio",
    "isotope_ratio": "isotope ratio",
    "reference_age": "reference age",
    "delta_value": "delta value",
    "epsilon_value": "epsilon value",
}
UNCERTAINTIES = {
    "2sd": "2s", "expanded_95": "95% conf.", "1sd": "1s",
    "reported_unspecified": "unspecified", "": "unspecified",
}
UNITS = {"ug/g": "µg/g", "permil": "‰", "dimensionless": "dimensionless",
         "ratio": "ratio", "Ma": "Ma"}
SUMMARIES = {
    "apatite": "Phosphate reference materials for U–Pb and trace elements.",
    "carbonate": "Carbonate records with isotope and trace-element values.",
    "glass": "Glass reference materials for elemental and isotope measurements.",
    "hematite": "Iron-oxide reference-material records.",
    "rutile": "Titanium-oxide reference materials for U–Pb and trace elements.",
    "titanite": "Titanite reference materials for U–Pb and trace elements.",
    "zircon": "Zircon reference materials for U–Pb and trace elements.",
}


class StoredFloat(str):
    """Keep the TOML float token, including trailing zeroes and exponents."""


def esc(value):
    return html.escape(str(value), quote=True)


def read_toml(path):
    return tomllib.loads(path.read_text(encoding="utf-8"), parse_float=StoredFloat)


def resource(filename):
    """Match UPbRPy's case-insensitive manifest lookup on case-sensitive hosts."""
    path = ROOT
    relative = Path(filename)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Library path must stay inside the repository: {filename}")
    for part in relative.parts:
        matches = [child for child in path.iterdir() if child.name == part]
        if not matches:
            matches = [child for child in path.iterdir()
                       if child.name.casefold() == part.casefold()]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous library path: {filename}")
        path = matches[0]
    return path


def standard_id(name):
    # Exact, collision-free anchors even when names differ only in punctuation.
    return "standard-" + name.encode("utf-8").hex()


def load_library():
    manifest = read_toml(ROOT / "library.toml")
    if manifest.get("format_version") != 2:
        raise ValueError("library.toml must declare format_version = 2")
    sources = read_toml(resource(manifest["sources"]))["sources"]
    standards = []
    seen = set()
    unknown = []
    for filename in manifest["material_files"]:
        document = read_toml(resource(filename))
        material = document["material"]
        if not material or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
                               for c in material):
            raise ValueError(f"Unsupported material name in {filename}: {material!r}")
        for name, definition in document["standards"].items():
            if name in seen:
                raise ValueError(f"Duplicate standard {name!r} in {filename}")
            seen.add(name)
            item = {"name": name, "material": material, "filename": filename,
                    "definition": definition, "id": standard_id(name)}
            item["url"] = f"materials/{material}.html#{item['id']}"
            standards.append(item)
            for block in definition["measurements"]:
                for quantity, raw in block["values"].items():
                    meta = raw if isinstance(raw, dict) else {"value": raw}
                    source = meta.get("source", block.get("source"))
                    if source not in sources:
                        unknown.append(f"{filename}: {name}/{quantity} -> {source!r}")
    if unknown:
        raise ValueError("Measurements cite unknown sources:\n" + "\n".join(unknown))
    return manifest, sources, standards


def group_materials(standards):
    groups = {}
    for item in standards:
        groups.setdefault(item["material"], []).append(item)
    return dict(sorted(groups.items()))


def measurement_count(items):
    return sum(len(block["values"]) for item in items
               for block in item["definition"]["measurements"])


def short_citation(source):
    """Shorten literature authors before (year); retain other display text."""
    display = source["display"]
    if source.get("kind") == "lab_compilation":
        # "Laboratory name (year). Workbook description" -> "Laboratory name (year)"
        lab = re.match(r"^(.*?\(\d{4}\))\.", display)
        return lab.group(1) if lab else display
    if source.get("kind") not in {"journal_article", "book", "book_chapter"}:
        return display
    match = re.match(r"^(.*?)\s*\((\d{4}[a-z]?)\)", display)
    if not match:
        return display
    authors, year = match.groups()
    # Surname, initials pairs, including accents, surname particles and Jr.
    names = re.findall(r"(?:^|,\s*|&\s*)([^,&]+),\s*(?=[^\W\d_]\.)", authors)
    if not names:
        names = re.split(r"\s*(?:,|&|\band\b)\s*", authors)
    names = [name.strip() for name in names if name.strip()]
    label = names[0] if len(names) == 1 else (
        " & ".join(names) if len(names) == 2 else f"{names[0]} et al.")
    return f"{label} ({year})"


def source_link(source, sources, prefix="../"):
    return (f'<a href="{prefix}sources.html#{quote(source, safe="")}">'
            f'{esc(short_citation(sources[source]))}</a>')


def cited_sources(item):
    """Keep block and value citations in their first-seen order."""
    cited = {}
    for block in item["definition"]["measurements"]:
        if block.get("source"):
            cited[block["source"]] = None
        for raw in block["values"].values():
            if isinstance(raw, dict) and raw.get("source"):
                cited[raw["source"]] = None
    return list(cited)


def count_label(count, noun):
    return f"{count:,} {noun}{'' if count == 1 else 's'}"


def search_index(standards, sources):
    return [{key: item[key] for key in ("name", "material", "id", "url")} |
            {"aliases": item["definition"].get("aliases", []),
             "sources": [short_citation(sources[source]) for source in cited_sources(item)]}
            for item in standards]


def badge(label, kind="role"):
    return f'<span class="badge {esc(kind)}">{esc(label)}</span>'


def number(value):
    if value is None:
        return '<span class="empty" aria-label="not reported">–</span>'
    full = str(value)
    # Most values remain exactly as written. Only long tokens use a short face;
    # the complete stored token stays in the tooltip and accessible name.
    if isinstance(value, StoredFloat) and len(full) > 13:
        short = format(float(value.replace("_", "")), ".8g")
        return (f'<abbr class="number" tabindex="0" title="{esc(full)}" '
                f'aria-label="{esc(full)}">{esc(short)}</abbr>')
    return f'<span class="number">{esc(full)}</span>'


MINERALS = ROOT / "assets" / "minerals"


def mineral_mark(material, size=""):
    """A crystal from the Mineral Habit Atlas: a still SVG that CRYSTAL_SCRIPT spins live."""
    still = MINERALS / f"{material}.svg"
    if not still.is_file():
        still = MINERALS / "glass.svg"
    return (f'<span class="{" ".join(filter(None, ("mineral-mark", size)))}" data-crystal="{esc(still.stem)}">'
            f'{still.read_text(encoding="utf-8").strip()}</span>')


def crystal_data(body):
    """The crystals.json entries for the marks that appear in a page body."""
    used = sorted(set(re.findall(r'data-crystal="([a-z]+)"', body)))
    if not used:
        return ""
    crystals = json.loads((MINERALS / "crystals.json").read_text(encoding="utf-8"))
    data = json.dumps({name: crystals[name] for name in used if name in crystals}, separators=(",", ":"))
    return (f'<script id="crystals" type="application/json">{data}</script>\n'
            f'<script>{CRYSTAL_SCRIPT}</script>\n')


CRYSTAL_SCRIPT = r"""
(() => {
  // Live view of the Mineral Habit Atlas crystals. Each crystal is convex, so drawing
  // the faces that point at the viewer is a complete render; no depth sorting needed.
  const crystals = JSON.parse(document.getElementById('crystals').textContent);
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  const darkScheme = matchMedia('(prefers-color-scheme: dark)');
  const unit = v => { const n = Math.hypot(...v); return v.map(x => x / n); };
  const KEY = unit([2.5, 4, 5]), RIM = unit([-4, 1, -3]);  // atlas key and rim lights
  const rad = Math.PI / 180;
  const marks = [];
  function project(c, turn) {
    // Same chain as the atlas card: c axis up, turned about it, then tipped towards the viewer.
    const t = c.view.tilt * rad, u = turn * rad;
    const ct = Math.cos(t), st = Math.sin(t), cu = Math.cos(u), su = Math.sin(u);
    return c.vertices.map(([x, y, z]) => {
      const X = cu * x - su * y, Y = z, Z = -su * x - cu * y;
      return [X, ct * Y - st * Z, st * Y + ct * Z];
    });
  }
  function draw(m, turn) {
    const { canvas, ctx, c, radius } = m;
    const w = canvas.width, h = canvas.height, s = 0.98 * Math.min(w, h) / (2 * radius);
    const P = project(c, turn);
    const dark = darkScheme.matches;
    ctx.clearRect(0, 0, w, h);
    ctx.lineJoin = 'round';
    const front = [];
    for (const f of c.faces) {
      const [a, b, d] = f.loop.slice(0, 3).map(i => P[i]);
      const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [d[0] - a[0], d[1] - a[1], d[2] - a[2]];
      const n = unit([e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]);
      if (n[2] <= 1e-6) continue;
      const k = Math.max(0, n[0] * KEY[0] + n[1] * KEY[1] + n[2] * KEY[2]);
      const r = Math.max(0, n[0] * RIM[0] + n[1] * RIM[1] + n[2] * RIM[2]);
      const g = 0.58 + 0.5 * k + 0.12 * r;
      const rgb = [1, 3, 5].map(i => Math.min(255, Math.round(parseInt(f.color.slice(i, i + 2), 16) * g + 12.75)));
      front.push([f.loop, `rgb(${rgb.join(',')})`]);
    }
    const path = loop => {
      ctx.beginPath();
      loop.forEach((i, j) => ctx[j ? 'lineTo' : 'moveTo'](w / 2 + P[i][0] * s, h / 2 - P[i][1] * s));
      ctx.closePath();
    };
    for (const [loop, fill] of front) {
      path(loop); ctx.fillStyle = fill; ctx.strokeStyle = fill; ctx.lineWidth = 0.6; ctx.fill(); ctx.stroke();
    }
    ctx.strokeStyle = dark ? 'rgba(11, 10, 8, .75)' : 'rgba(42, 32, 24, .6)';
    ctx.lineWidth = Math.max(1, w / 90);
    for (const [loop] of front) { path(loop); ctx.stroke(); }
  }
  function size(m) {
    const box = m.el.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    m.canvas.width = Math.round(box.width * dpr);
    m.canvas.height = Math.round(box.height * dpr);
  }
  document.querySelectorAll('[data-crystal]').forEach((el, i) => {
    const c = crystals[el.dataset.crystal];
    if (!c) return;
    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    const m = { el, canvas, ctx: canvas.getContext('2d'), c, visible: true, phase: i * 37,
                radius: Math.max(...c.vertices.map(v => Math.hypot(...v))) };
    el.classList.add('live');
    el.append(canvas);
    size(m);
    marks.push(m);
  });
  if (!marks.length) return;
  const seen = new IntersectionObserver(entries => entries.forEach(e => {
    const m = marks.find(x => x.el === e.target); if (m) m.visible = e.isIntersecting;
  }));
  marks.forEach(m => seen.observe(m.el));
  const start = performance.now();
  let running = false;
  function frame(now) {
    const spin = still.matches ? 0 : (now - start) / 1000 * 18;  // 18 degrees a second
    for (const m of marks) {
      if (m.visible || !spin) draw(m, m.c.view.turn + (spin ? spin + m.phase : 0));
    }
    if (spin) requestAnimationFrame(frame); else running = false;
  }
  function kick() { if (!running) { running = true; requestAnimationFrame(frame); } }
  kick();
  const redraw = () => { marks.forEach(size); running = false; kick(); };
  window.addEventListener('resize', redraw);
  still.addEventListener('change', redraw);
  darkScheme.addEventListener('change', redraw);
})();
"""


SEARCH_SCRIPT = r"""
(() => {
  // This is the same data as search-index.json, embedded for file:// use.
  const index = JSON.parse(document.getElementById('search-index').textContent);
  const fold = text => text.toLowerCase().replace(/[^a-z0-9]/g, '');
  const keys = new Map(index.map(item => [item.id, fold([item.name, ...item.aliases, ...item.sources].join(' '))]));
  const noun = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
  const global = document.getElementById('library-search');
  const local = document.getElementById('standard-search');
  const navToggle = document.getElementById('nav-toggle');
  const menu = document.getElementById('menu-button');
  // Upgrade the CSS-only fallback to a button with an announced state.
  document.getElementById('menu-fallback').hidden = true;
  navToggle.hidden = true;
  menu.hidden = false;
  function closeMenu() {
    navToggle.checked = false;
    menu.setAttribute('aria-expanded', 'false');
  }
  menu.addEventListener('click', () => {
    navToggle.checked = !navToggle.checked;
    menu.setAttribute('aria-expanded', String(navToggle.checked));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navToggle.checked) { closeMenu(); menu.focus(); }
  });
  const groups = [...document.querySelectorAll('.mineral-group')];
  const initiallyOpen = groups.map(group => group.open);
  const panels = [...document.querySelectorAll('.standard')];
  function filter() {
    const query = fold(global.value);
    let sidebarCount = 0;
    document.querySelectorAll('[data-nav-title]').forEach(link => {
      link.hidden = query !== '' && !fold(link.dataset.navTitle).includes(query);
    });
    groups.forEach((group, i) => {
      let count = 0;
      group.querySelectorAll('[data-standard-key]').forEach(link => {
        const match = keys.get(link.dataset.standardKey).includes(query);
        link.hidden = !match;
        count += Number(match);
      });
      group.hidden = count === 0;
      group.querySelector('.count').textContent = count;
      group.open = query ? count > 0 : initiallyOpen[i];
      sidebarCount += count;
    });
    const status = document.getElementById('sidebar-results');
    status.hidden = !query;
    status.textContent = `${sidebarCount} matching ${sidebarCount === 1 ? 'standard' : 'standards'}`;
    const localQuery = local ? fold(local.value) : '';
    let visible = 0;
    panels.forEach(panel => {
      const key = keys.get(panel.id);
      panel.hidden = !key.includes(query) || !key.includes(localQuery);
      visible += Number(!panel.hidden);
    });
    const count = document.getElementById('standard-count');
    if (count) count.textContent = `${visible} of ${noun(panels.length, 'standard')}`;
    document.querySelectorAll('[data-summary-key]').forEach(row => {
      const key = keys.get(row.dataset.summaryKey);
      row.hidden = !key.includes(query) || !key.includes(localQuery);
    });
    document.querySelectorAll('[data-source-search]').forEach(source => {
      source.hidden = !fold(source.dataset.sourceSearch).includes(query);
    });
    const empty = document.getElementById('no-standards');
    if (empty) empty.hidden = visible !== 0;
  }
  global.addEventListener('input', filter);
  if (local) local.addEventListener('input', filter);
  // A source backlink must reveal its target even after a previous filter.
  function revealTarget() {
    const target = document.getElementById(location.hash.slice(1));
    if (target && target.classList.contains('standard')) {
      global.value = ''; if (local) local.value = ''; filter();
      target.scrollIntoView();
    }
  }
  window.addEventListener('hashchange', revealTarget);
  document.querySelectorAll('.standard-links a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });
  filter();
})();
"""


def page(title, body, path, groups, index, material=None):
    prefix = "../" if "/" in path else ""

    def nav(label, target):
        active = ' aria-current="page"' if path == target else ''
        return (f'<a class="nav-link" data-nav-title="{esc(label)}" '
                f'href="{prefix}{target}"{active}>{label}</a>')

    material_nav = []
    for name, items in groups.items():
        active = name == material
        links = ''.join(f'<a class="nav-link" data-standard-key="{item["id"]}" '
                        f'href="{prefix}{item["url"]}">{esc(item["name"])}</a>'
                        for item in items)
        material_nav.append(
            f'<details class="mineral-group{" current" if active else ""}"{ " open" if active else ""}>'
            f'<summary><span class="mineral-name">{esc(name.title())}</span>'
            f'<span class="count">{len(items)}</span></summary><div class="standard-links">'
            f'<a class="nav-link all-link" href="{prefix}materials/{name}.html">All {esc(name)} standards</a>'
            f'{links}</div></details>')
    data = json.dumps(index, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    crumb = (f'<a href="{prefix}index.html">Library</a> <span aria-hidden="true">/</span> '
             + ("Materials / " if material else "") + esc(title))
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="Reference-material values, sources and conventions for LA-ICP-MS U–Pb and trace-element reduction.">
  <title>{esc(title)} · upb-standards</title>
  <link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{prefix}favicon-32.png" type="image/png" sizes="32x32">
  <link rel="stylesheet" href="{prefix}static/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<input class="visually-hidden" type="checkbox" id="nav-toggle" aria-label="Show library navigation" aria-controls="sidebar">
<div class="mobile-bar"><label class="menu-toggle" id="menu-fallback" for="nav-toggle">Menu</label><button class="menu-toggle" id="menu-button" type="button" aria-expanded="false" aria-controls="sidebar" hidden>Menu</button><span class="mobile-brand">upb-standards</span></div>
<aside class="sidebar" id="sidebar" aria-label="Library navigation">
  <a class="brand" href="{prefix}index.html"><img src="{prefix}favicon.svg" width="42" height="42" alt="">upb-standards</a>
  <label class="search-label" for="library-search">Search the library</label>
  <input id="library-search" type="search" placeholder="Standard, alias or source" autocomplete="off" aria-describedby="search-help">
  <span id="search-help" class="visually-hidden">Filters the navigation, standards and source records on this page. Requires JavaScript.</span>
  <p class="block-note" id="sidebar-results" role="status" hidden></p>
  <noscript><p class="block-note">Search needs JavaScript. All pages and values are available below.</p></noscript>
  <nav aria-label="Manual">
    <p class="nav-section">Library</p>
    {nav("Overview", "index.html")}
    <p class="nav-section">Materials · {count_label(sum(map(len, groups.values())), 'standard')}</p>
    {''.join(material_nav)}
    <p class="nav-section">Reference</p>
    {nav("Sources", "sources.html")}
    {nav("Conventions", "conventions.html")}
    {nav("Using with UPbRPy", "upbrpy.html")}
    {nav("Contributing", "contributing.html")}
  </nav>
  <div class="sidebar-foot">Format 2 · MIT license<br><a href="{REPO_URL}">View on GitHub</a></div>
</aside>
<main id="main" tabindex="-1">
  <p class="breadcrumb">{crumb}</p>
  {body}
  <footer class="page-foot"><span>upb-standards · Generated from the TOML library</span><a href="{REPO_URL}">Repository</a><a href="{prefix}contributing.html">Suggest a correction</a></footer>
</main>
<script id="search-index" type="application/json">{data}</script>
<script>{SEARCH_SCRIPT}</script>
{crystal_data(body)}</body>
</html>
'''


def overview(groups, sources, standards):
    stats = ''.join(f'<div class="stat"><strong>{count:,}</strong><span>{label}{"" if count == 1 else "s"}</span></div>'
                    for label, count in (("material", len(groups)), ("standard", len(standards)),
                                         ("measurement", measurement_count(standards)), ("source", len(sources))))
    cards = ''.join(
        f'<a class="card" href="materials/{name}.html"><div class="card-top">{mineral_mark(name)}'
        f'<h3>{esc(name.title())}</h3></div><p>{esc(SUMMARIES.get(name, "Reference-material values."))}</p>'
        f'<div class="card-meta"><span>{count_label(len(items), "standard")} · {count_label(measurement_count(items), "value")}</span>'
        '<span aria-hidden="true">→</span></div></a>' for name, items in groups.items())
    return f'''<p class="eyebrow">Reference material library</p>
<h1>Overview</h1>
<p class="lede">Source values for LA-ICP-MS U–Pb and trace-element reduction. Browse materials, check a value’s publication, and keep its measurement convention in view.</p>
<div class="stats" aria-label="Library counts">{stats}</div>
<h2>Materials</h2>
<div class="mineral-grid">{cards}</div>
<h2>How values reach a reduction</h2>
<div class="flow" role="group" aria-label="TOML file to UPbRPy loader to derived ratios to reduction">
  <div class="flow-step"><strong>TOML file</strong><span>Source values, units and citations</span></div><span class="flow-arrow" aria-hidden="true">→</span>
  <div class="flow-step"><strong>UPbRPy loader</strong><span>Validate and expand measurements</span></div><span class="flow-arrow" aria-hidden="true">→</span>
  <div class="flow-step"><strong>Derived ratios</strong><span>Fill missing linked values</span></div><span class="flow-arrow" aria-hidden="true">→</span>
  <div class="flow-step"><strong>Reduction</strong><span>Calibration and fractionation</span></div>
</div>
<div class="callout"><p><strong>Read the convention with the value.</strong> Initial Pb, radiogenic ratios, total ratios and separate isotope systems stay distinct. A missing uncertainty means it was not reported here.</p><p><a href="conventions.html">Read the conventions</a> · <a href="upbrpy.html">Use a library in UPbRPy</a></p></div>'''


def uncertainty_type(meta):
    if meta.get("uncertainty") is None:
        return "–"
    kind = meta.get("uncertainty_type", "")
    return UNCERTAINTIES.get(kind, kind)


def block_notes(note):
    note = note.replace("the {quantity}", "each").replace("{quantity}", "each")
    if not note:
        return ""
    if len(note) > 220:
        # Sentence punctuation followed by a capital avoids splitting wt.% or
        # decimal tokens in the audited notes.
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", note, maxsplit=1)
        remainder = f'<p>{esc(sentences[1])}</p>' if len(sentences) > 1 else ''
        return (f'<details class="block-note"><summary>{esc(sentences[0])}</summary>'
                f'{remainder}</details>')
    return f'<p class="block-note">{esc(note)}</p>'


def reference_ages(item):
    ages = []
    for block in item["definition"]["measurements"]:
        for quantity, raw in block["values"].items():
            meta = raw if isinstance(raw, dict) else {"value": raw}
            if meta.get("role", block["role"]) != "reference_age":
                continue
            label = quantity.replace("_", " ")
            if quantity == "concordia_age":
                label = ("concordia (assumed)" if meta.get("notes", block.get("notes", ""))
                         .startswith("Concordance assumption") else "concordia age")
            unit = meta.get("unit", block.get("unit", ""))
            value = number(meta["value"])
            if meta.get("uncertainty") is not None:
                value += f' ± {number(meta["uncertainty"])}'
            value += f' {esc(UNITS.get(unit, unit))}'
            if meta.get("uncertainty") is not None:
                value += f' ({esc(uncertainty_type(meta))})'
            ages.append(f'<div>{esc(label)} {value}</div>')
    return ''.join(ages) or number(None)


def material_page(material, items, sources):
    panels = []
    summaries = []
    for item in items:
        definition = item["definition"]
        aliases = definition.get("aliases", [])
        alias_html = ', '.join(esc(alias) for alias in aliases) if aliases else 'None recorded'
        citations = ''.join(f'<div>{source_link(source, sources)}</div>'
                            for source in cited_sources(item))
        summaries.append(
            f'<tr data-summary-key="{item["id"]}"><th scope="row">'
            f'<a href="#{item["id"]}">{esc(item["name"])}</a></th>'
            f'<td>{alias_html}</td><td class="age-summary">{reference_ages(item)}</td>'
            f'<td>{citations}</td></tr>')
        intro = ''.join(f'<p class="{field}">{"Origin: " if field == "origin" else ""}{esc(definition[field])}</p>'
                        for field in ("description", "origin") if definition.get(field))
        blocks = []
        for i, block in enumerate(definition["measurements"], 1):
            rows = []
            for quantity, raw in block["values"].items():
                meta = raw if isinstance(raw, dict) else {"value": raw}
                overrides = []
                if "source" in meta:
                    overrides.append(source_link(meta["source"], sources))
                for key in ("locator", "status", "notes"):
                    if key in meta:
                        overrides.append(esc(meta[key].replace("the {quantity}", "each").replace("{quantity}", "each")))
                extra = (f'<span class="value-note">{" · ".join(overrides)}</span>'
                         if overrides else '')
                rows.append(
                    f'<tr><th scope="row"><span class="quantity">{esc(quantity)}</span>{extra}</th>'
                    f'<td>{number(meta["value"])}</td><td>{number(meta.get("uncertainty"))}</td>'
                    f'<td>{esc(uncertainty_type(meta))}</td></tr>')
            role = ROLES.get(block["role"], block["role"])
            status = block.get("status", "")
            unit = block.get("unit", "")
            citation = source_link(block["source"], sources) if block.get("source") else ''
            locator = f'<span class="locator">{esc(block["locator"])}</span>' if block.get("locator") else ''
            blocks.append(
                f'<section class="measurement" aria-labelledby="{item["id"]}-block-{i}">'
                f'<h3 class="block-header" id="{item["id"]}-block-{i}">'
                f'{badge(role)}{badge(status, status)}<span class="unit">{esc(UNITS.get(unit, unit))}</span>'
                f'{citation}{locator}<span class="visually-hidden">Block {i}</span></h3>'
                + block_notes(block.get("notes", "")) +
                '<div class="table-scroll" tabindex="0" role="region" '
                f'aria-label="{esc(item["name"])} block {i} measurements"><table class="values">'
                f'<caption class="visually-hidden">{esc(item["name"])}: measurement block {i}</caption>'
                '<thead><tr><th scope="col">Quantity</th><th scope="col">Value</th>'
                '<th scope="col">Uncertainty</th><th scope="col">Type</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div></section>')
        panels.append(
            f'<article class="standard" id="{item["id"]}"><header class="standard-head"><div>'
            f'<h2>{esc(item["name"])}</h2><p class="aliases"><strong>Aliases:</strong> {alias_html}</p></div>'
            f'<a class="file-link" href="{REPO_URL}/blob/main/{quote(item["filename"], safe="/")}">{esc(item["filename"])}</a>'
            f'</header>{intro}{"".join(blocks)}</article>')
    summary = (
        '<div class="table-scroll material-summary" tabindex="0" role="region" aria-label="Standard summary">'
        f'<table><caption class="visually-hidden">{esc(material.title())} standards at a glance</caption>'
        '<thead><tr><th scope="col">Standard</th><th scope="col">Aliases</th>'
        '<th scope="col">Reference ages</th><th scope="col">Sources</th></tr></thead>'
        f'<tbody>{"".join(summaries)}</tbody></table></div>')
    return f'''<div class="material-head">{mineral_mark(material, "hero")}<div><p class="eyebrow">Materials</p><h1>{esc(material.title())}</h1></div></div>
{summary}
<p class="lede">{esc(SUMMARIES.get(material, "Reference-material values."))} Each panel records the stored source measurements.</p>
<div class="toolbar"><label><span class="search-label">Filter {esc(material)} standards</span><input type="search" id="standard-search" placeholder="Name, alias or source" autocomplete="off"></label>
<p class="result-count" id="standard-count" role="status">{len(items)} of {count_label(len(items), "standard")}</p></div>
<p class="block-note">Uncertainties are absolute in the listed unit. A dash means not reported. Dotted values show 8 significant figures; focus or hover for the complete stored value.</p>
<p id="no-standards" class="callout" hidden>No matching standards. Clear the library search or the page filter to show more.</p>
<div class="standards-list">{''.join(panels)}</div>'''


def sources_page(sources, standards):
    used_by = {source: [] for source in sources}
    for item in standards:
        for source in cited_sources(item):
            used_by[source].append(item)
    panels = []
    for source, meta in sources.items():
        citation = short_citation(meta)
        fields = [('Kind', esc(meta.get('kind', '').replace('_', ' ')))]
        if meta.get("doi"):
            doi = meta["doi"]
            fields.append(('DOI', f'<a href="https://doi.org/{quote(doi, safe="/()")}">{esc(doi)}</a>'))
        if meta.get("no_doi_reason"):
            fields.append(('No DOI', esc(meta['no_doi_reason'])))
        fields.append(('Source status', badge(meta['status'], meta['status']) if meta.get('status') else 'Not specified'))
        for field, label in (("url", "Source link"), ("file", "Source file"), ("notes", "Notes")):
            if meta.get(field):
                value = esc(meta[field])
                if field == "url":
                    url = urlsplit(meta[field])
                    if url.scheme in {"http", "https"}:
                        value = f'<a href="{esc(meta[field])}">{esc(meta[field])}</a>'
                fields.append((label, value))
        metadata = ''.join(f'<dt>{label}</dt><dd>{value}</dd>' for label, value in fields)
        backlinks = ''.join(f'<li><a href="{item["url"]}" title="{esc(citation)} in {esc(item["name"])}">'
                            f'{esc(item["name"])}</a></li>' for item in used_by[source])
        search_text = ' '.join([citation, meta["display"], *(
            ' '.join([item["name"], *item["definition"].get("aliases", [])]) for item in used_by[source])])
        panels.append(f'<article class="source" id="{esc(source)}" data-source-search="{esc(search_text)}"><h2>{esc(citation)}</h2>'
                      f'<p>{esc(meta["display"])}</p><dl>{metadata}</dl>'
                      '<p class="block-note">Cited by</p>'
                      + (f'<ul class="backlinks" aria-label="Standards citing {esc(citation)}">{backlinks}</ul>'
                         if backlinks else '<p class="block-note">No standards currently cite this source.</p>') + '</article>')
    return (f'<p class="eyebrow">Reference</p><h1>Sources</h1><p class="lede">{count_label(len(sources), "source record")}. '
            'Follow a standard’s source link to its citation, then return through the links below each record.</p>'
            f'<p><a href="{AUDIT_URL}">The 2026-11 audit lists what was checked and what is not yet verified.</a></p>'
            '<div class="callout"><p>Cite the original publications for the values you use. A compilation record may draw on several publications; read its notes. Source status and measurement status are separate fields.</p></div>' + ''.join(panels))


def conventions_page():
    rows = [
        ("concentration", "µg/g", "Elemental mass fraction assigned to a measurement channel. Read the block notes; it is not multiplied by isotope abundance."),
        ("initial_ratio", "ratio", "Initial or common-Pb composition, kept apart from radiogenic Pb."),
        ("radiogenic_ratio", "ratio", "Ratio for radiogenic Pb, marked with * in the quantity name."),
        ("total_ratio", "ratio", "Ratio including total Pb, marked with _total."),
        ("isotope_ratio", "ratio", "A reported isotope ratio, including systems other than U–Pb."),
        ("reference_age", "Ma", "Reported system age or concordia age. One Ma is one million years."),
        ("delta_value", "‰", "Reported delta value. Its reference scale belongs in the source and notes."),
        ("epsilon_value", "dimensionless", "Reported epsilon value. Its reference convention belongs in the source and notes."),
    ]
    table = ''.join(f'<tr><td class="role-code"><code>{role}</code></td><td>{unit}</td><td>{meaning}</td></tr>' for role, unit, meaning in rows)
    return '''<p class="eyebrow">Reference</p><h1>Conventions</h1><div class="prose">
<p class="lede">Read each value with its role, unit, uncertainty type, status and source. These fields travel together.</p>
<h2>Roles and units</h2><div class="table-scroll" tabindex="0" role="region" aria-label="Roles and units"><table><thead><tr><th scope="col">Stored role</th><th scope="col">Unit</th><th scope="col">Meaning</th></tr></thead><tbody>''' + table + '''</tbody></table></div>
<p class="block-note">The TOML unit tokens are <code>ug/g</code>, <code>ratio</code>, <code>Ma</code>, <code>permil</code> and <code>dimensionless</code>. The manual displays µg/g and ‰ for readability.</p>
<h2>Quantity names and suffixes</h2>
<p><code>206Pb/204Pb_i</code> uses <code>_i</code> for initial/common Pb. <code>206Pb/238U*</code> uses <code>*</code> for a radiogenic ratio. <code>206Pb/238U_total</code> uses <code>_total</code> for a total ratio. These are separate quantities. A channel such as <code>29Si</code> names the measurement channel; its concentration can represent elemental Si.</p>
<div class="callout"><p>Keep isotope systems, initial Pb, radiogenic and total ratios, and uncertainty conventions distinct. Do not substitute a total ratio for a radiogenic ratio or treat a missing uncertainty as zero.</p></div>
<h2>What UPbRPy derives</h2>
<p><code>load_standard_measurements(path)</code> expands source quantities into one row per measurement. <code>build_standard_archive(..., include_derived=True)</code> pivots those rows and fills missing derived values. Documented values always take precedence. The material pages show the stored measurements.</p>
<h3>Initial Pb</h3>
<p>From <code>206Pb/204Pb_i</code>, <code>207Pb/204Pb_i</code> and <code>208Pb/204Pb_i</code>, UPbRPy fills their <code>204Pb/206Pb_i</code>, <code>204Pb/207Pb_i</code> and <code>204Pb/208Pb_i</code> reciprocals. It also forms <code>206Pb/207Pb_i</code>, <code>207Pb/206Pb_i</code> and <code>206Pb/208Pb_i</code> by dividing the corresponding ratios to 204Pb. It skips nonfinite inputs and zero denominators.</p>
<h3>Concordance assumptions</h3>
<p>Some records repeat a published system age as a provisional <code>concordia_age</code> so UPbRPy can derive ratios that are not stored. Their notes start with “Concordance assumption” and explain the repeated age. The summary tables label these entries “concordia (assumed)”.</p>
<h3>Ages and radiogenic ratios</h3>
<p>A finite <code>206Pb/238U_age</code> supplies the age for <code>206Pb/238U*</code>; otherwise a finite <code>concordia_age</code> is used. The same rule applies independently to <code>207Pb/235U_age</code> and <code>207Pb/235U*</code>. Each ratio is <code>exp(λt) − 1</code>, with ages converted from Ma to years.</p>
<p>A separately reported <code>207Pb/206Pb_age</code> supplies <code>207Pb/206Pb*</code> from the concordant age equation. A <code>concordia_age</code> also supplies <code>208Pb/232Th*</code>. The constants used are λ238 = <code>1.55125e-10</code>, λ235 = <code>9.8485e-10</code> and λ232 = <code>4.94752e-11</code> per year.</p>
<p>The linked U–Pb ratios use <strong>238U/235U = 137.818</strong> (<code>common_U238_U235</code>). With R68 = <code>206Pb/238U*</code>, R75 = <code>207Pb/235U*</code> and R76 = <code>207Pb/206Pb*</code>:</p>
<ul><li><code class="formula">R76 = R75 / R68 / 137.818</code></li>
<li><code class="formula">R75 = R76 × R68 × 137.818</code></li>
<li><code class="formula">R68 = R75 / R76 / 137.818</code></li></ul>
<p>After filling age-based ratios, UPbRPy tries the R75/R68 link for a missing R76 before falling back to the concordia age. It then tries the other two links using the values available at that stage. It fills <code>238U/206Pb*</code> and <code>206Pb/207Pb*</code> as reciprocals. It does not solve a general isotope network or replace a documented value.</p>
<h3>Total ratios</h3>
<p>Only <code>238U/206Pb_total</code> from <code>206Pb/238U_total</code>, and <code>206Pb/207Pb_total</code> from <code>207Pb/206Pb_total</code>, are filled as reciprocals. Total ratios are not linked through the radiogenic equations.</p>
<p>The wide archive contains numeric values, not propagated uncertainties for these derived entries. Source uncertainties remain in the normalized measurement table. Use <code>include_derived=False</code> to obtain only documented values in the wide archive.</p>
<p>Implementation: <a href="https://github.com/duserzym/UPbRPy/blob/main/UPbRPy/standards.py">UPbRPy/standards.py</a> and <a href="https://github.com/duserzym/UPbRPy/blob/main/UPbRPy/constants.py">constants.py</a>.</p>
<h2>Uncertainty types</h2>
<ul><li><code>1sd</code> → <strong>1s</strong>: one standard deviation.</li>
<li><code>2sd</code> → <strong>2s</strong>: two standard deviations.</li>
<li><code>expanded_95</code> → <strong>95% conf.</strong>: reported expanded 95% uncertainty. Keep the source’s coverage convention.</li>
<li><code>reported_unspecified</code> → <strong>unspecified</strong>: an uncertainty is supplied, but its convention was not specified in the record.</li>
<li>No uncertainty → a dash in both the uncertainty and type columns. The loader represents a missing uncertainty as NaN.</li></ul>
<p>Uncertainties are absolute in the quantity’s unit. UPbRPy requires an uncertainty and its type together; it does not silently convert between these conventions.</p>
<h2>Status</h2>
<p><strong>Recommended</strong> marks a value currently recommended in this library. <strong>Provisional</strong> marks a record retained pending confirmation or further review, including imported working values. Neither label replaces the publication or its stated limits. Status can be overridden for an individual value. A source may also have its own status; an omitted source status is shown as “Not specified”.</p>
<h2>Display and provenance</h2>
<p>Values retain their stored numeric spelling, including trailing zeroes. Tokens longer than 13 characters display 8 significant figures; hover or focus to read the complete stored token. A measurement inherits its role, unit, status, source, locator and notes from its block unless a value-level field overrides it. Block notes replace the literal <code>{quantity}</code> with “each”.</p>
</div>'''


def upbrpy_page():
    return '''<p class="eyebrow">Using the library</p><h1>Using with UPbRPy</h1><div class="prose">
<p class="lede">UPbRPy bundles a copy of the format-2 library. Select another checkout explicitly when a reduction needs reviewed values from a different revision.</p>
<h2>The bundled copy</h2>
<p>With no path, <code>UPbRPy.load_standard_measurements()</code> loads the package’s <code>reference_materials</code> directory. The manifest controls the file order and the source registry supplies the citations. The older wide CSV remains a separate compatibility archive. Studio combines its TOML-derived archive with that legacy archive to fill gaps.</p>
<h2>Load another checkout</h2>
<p>Pass either the library directory or its <code>library.toml</code>. Expand a home-directory shortcut before passing a path in Python.</p>
<pre><code>from pathlib import Path
import UPbRPy

path = Path("~/UPbRPy/upb-standards").expanduser()
measurements = UPbRPy.load_standard_measurements(path)
# Equivalently:
measurements = UPbRPy.load_standard_measurements(path / "library.toml")
archive = UPbRPy.build_standard_archive(measurements)</code></pre>
<p>The loader validates roles, units, statuses, uncertainties, sources and duplicate standard/quantity rows. Loading returns normalized source measurements; building the archive adds missing derived ratios.</p>
<h2>Select a library in Studio</h2>
<p>Choose <strong>File → Reference Material Library</strong> and select <code>library.toml</code> to adopt a reviewed library explicitly.</p>
<h2>Desktop checks</h2>
<p>Keep a clone at <code>~/UPbRPy/upb-standards</code> for the desktop apps, or set <code>UPB_STANDARDS_DIR</code> before launching an app to use another clone. Git must be on the app’s path.</p>
<pre><code>git clone https://github.com/duserzym/upb-standards.git ~/UPbRPy/upb-standards</code></pre>
<p>In Updates, <strong>Check standards</strong> fetches Git metadata and compares the clone’s TOML files with GitHub main, including untracked TOML files. It also compares the active library digest with the clone’s digest. It reports differences without adopting or editing values.</p>
<p>If GitHub is unavailable, the comparison uses the last checked GitHub revision when available, otherwise the clone’s local HEAD, and reports that the online check was unavailable.</p>
<h2>Archive a reduction</h2>
<p>Record the exact Git revision and the library digest with the reduction. A revision identifies the repository state; the digest identifies the library files actually used, including local changes.</p>
<pre><code>git -C ~/UPbRPy/upb-standards rev-parse HEAD</code></pre>
<pre><code>info = UPbRPy.reference_library_info(path)
print(info["version"])
print(info["sha256"])</code></pre>
<p><code>reference_library_info(path)</code> hashes the manifest, source registry and listed material files with SHA-256, normalizing CRLF line endings to LF. Its version label includes the declared version, or format version, plus a short digest. Keep the full SHA-256 for the archive.</p>
<p>Code references: <a href="https://github.com/duserzym/UPbRPy/blob/main/UPbRPy/standards.py">loader and digest</a>, <a href="https://github.com/duserzym/UPbRPy/blob/main/GUI/standards_updates.py">desktop comparison</a>, <a href="https://github.com/duserzym/UPbRPy/blob/main/GUI/services.py">Studio library selection</a>.</p>
</div>'''


def contributing_page():
    example = '''# library.toml: retain existing entries and append this path.
format_version = 2
sources = "sources.toml"
material_files = ["zircon/Example.toml"]

# sources.toml: illustrative metadata; replace with the real publication.
format_version = 2
[sources.example2026]
display = "Author, A. (2026), Full article title, Journal, volume, pages."
kind = "journal_article"
doi = "10.xxxx/replace-with-real-doi"
url = "https://doi.org/10.xxxx/replace-with-real-doi"

# zircon/Example.toml: illustrative values, not a reference material.
format_version = 2
material = "zircon"
[standards.Example]
aliases = ["Example zircon"]
description = "Description of the reference material."
origin = "Documented locality or supplier."

[[standards.Example.measurements]]
role = "reference_age"
unit = "Ma"
status = "provisional"
source = "example2026"
locator = "Table 2, p. 10"
notes = "Reported concordia age; illustrative example only."
[standards.Example.measurements.values]
concordia_age = { value = 100.0, uncertainty = 0.2, uncertainty_type = "2sd" }
'''
    return '''<p class="eyebrow">Maintaining the library</p><h1>Contributing a material</h1><div class="prose">
<p class="lede">Add documented source quantities and enough context for someone else to verify them.</p>
<ol><li><strong>Create a material file.</strong> Use <code>&lt;mineral&gt;/&lt;name&gt;.toml</code>, declare <code>format_version = 2</code> and the material, then add a unique standard name. Include aliases, description and origin where known.</li>
<li><strong>Register the file.</strong> Add its exact relative path to <code>material_files</code> in <code>library.toml</code>. File order determines the loader’s stable row order.</li>
<li><strong>Register the publication once.</strong> Reuse an existing source ID when possible. Otherwise add a source in <code>sources.toml</code> with a full citation (authors, year, title, venue, volume and pages), kind and DOI. If there is no DOI, document why in <code>no_doi_reason</code>.</li>
<li><strong>Record the measurement context.</strong> Each block needs a role, unit, status and source ID. Add a table/page locator, notes, and the reported absolute uncertainty and its type. Use <code>provisional</code> while a value awaits confirmation. Do not convert a reported uncertainty convention without documenting the change.</li>
<li><strong>Keep primary quantities.</strong> Store the reported ratio or age and let UPbRPy derive missing reciprocal and linked ratios. Keep initial Pb, radiogenic and total ratios, and different isotope systems separate.</li>
<li><strong>Run the checks.</strong> Load this checkout with UPbRPy, audit its sources, build its archive, then rebuild and check the manual. Review the source text as well as the numeric values.</li></ol>
<h2>A complete minimal example</h2>
<p>The three sections below are separate files. Merge the manifest and source entries into the existing files. The citation, DOI and measurements are placeholders for the example; replace them before contributing.</p>
<pre><code>''' + esc(example) + '''</code></pre>
<p>A scalar value is allowed when no uncertainty is reported. With an uncertainty, use an inline table containing <code>value</code>, <code>uncertainty</code> and <code>uncertainty_type</code>. Individual values can override a block’s status, source, locator or notes. Use those overrides to keep a mixed block’s provenance accurate.</p>
<h2>Check with UPbRPy</h2>
<p>In a Python environment where UPbRPy is installed, point these checks at this checkout:</p>
<pre><code>from pathlib import Path
import UPbRPy

path = Path("~/Github/upb-standards").expanduser()
UPbRPy.check_reference_sources(path)
measurements = UPbRPy.load_standard_measurements(path)
archive = UPbRPy.build_standard_archive(measurements)</code></pre>
<p>The source check rejects unknown source IDs and warns when a source has neither a DOI nor a documented reason for its absence. It does not look up DOIs or verify the publication’s numerical values.</p>
<h2>Update the manual and README</h2>
<pre><code>python3 site/build.py --out _site --check
python3 site/build.py --readme</code></pre>
<p>The builder reads every file in the manifest. Its link check verifies internal targets and anchors and confirms that every standard appears. Open <code>_site/index.html</code> directly to review the site. No server or network is needed.</p>
<p>Send the change to <a href="https://github.com/duserzym/upb-standards">the repository</a> with a short explanation of the source and any interpretation. See <a href="conventions.html">Conventions</a> for roles, units and derivation rules.</p>
</div>'''


def update_readme(groups):
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    start, end = "<!-- materials:start -->", "<!-- materials:end -->"
    if original.count(start) != 1 or original.count(end) != 1:
        raise ValueError("README.md needs exactly one materials:start / materials:end marker pair")
    before, rest = original.split(start)
    _, after = rest.split(end)
    rows = ['| Mineral | Standards | Count |', '| --- | --- | ---: |']
    for name, items in groups.items():
        names = ', '.join(item['name'].replace('|', '\\|') for item in items)
        rows.append(f'| {name} | {names} | {len(items)} |')
    updated = before + start + '\n' + '\n'.join(rows) + '\n' + end + after
    if updated != original:
        path.write_text(updated, encoding="utf-8")
    print(f"README materials table: {count_label(sum(map(len, groups.values())), 'standard')}")


class Links(HTMLParser):
    """Collect internal links and anchors without a browser or dependencies."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.targets = []
        self.duplicates = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.duplicates.append(attrs["id"])
            self.ids.add(attrs["id"])
        for attribute in ("href", "src"):
            if attrs.get(attribute):
                self.targets.append(attrs[attribute])


def check_site(out, sources, standards):
    pages = {}
    failures = []
    for path in out.rglob("*.html"):
        parser = Links()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path.resolve()] = parser
        failures.extend(f"{path}: duplicate id {anchor}" for anchor in parser.duplicates)
    expected = ["index.html", "sources.html", "conventions.html", "upbrpy.html", "contributing.html"]
    expected.extend(f"materials/{material}.html" for material in group_materials(standards))
    for filename in expected:
        if (out / filename).resolve() not in pages:
            failures.append(f"Missing page: {filename}")
    for path, parser in pages.items():
        for target in parser.targets:
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not destination.is_relative_to(out.resolve()):
                failures.append(f"{path.name}: link escapes output: {target}")
            elif not destination.is_file():
                failures.append(f"{path.name}: missing target: {target}")
            elif url.fragment and destination in pages and unquote(url.fragment) not in pages[destination].ids:
                failures.append(f"{path.name}: missing anchor: {target}")
    for item in standards:
        destination = (out / f'materials/{item["material"]}.html').resolve()
        if destination not in pages or item['id'] not in pages[destination].ids:
            failures.append(f"Standard missing from site: {item['name']}")
    stored_index = json.loads((out / 'search-index.json').read_text(encoding="utf-8"))
    if stored_index != search_index(standards, sources):
        failures.append("search-index.json differs from the manifest's standards")
    if failures:
        raise ValueError("Site check failed:\n" + '\n'.join(failures))
    print(f"Checked {count_label(len(pages), 'page')}, all internal links and {count_label(len(standards), 'standard')}")


def build(out, sources, standards, groups):
    out = out.resolve()
    if out == ROOT or out == SITE or ROOT.is_relative_to(out) or out.is_relative_to(SITE):
        raise ValueError("Choose a separate output directory, such as _site")
    out.mkdir(parents=True, exist_ok=True)
    index = search_index(standards, sources)
    bodies = {"index.html": ("Overview", overview(groups, sources, standards)),
              "sources.html": ("Sources", sources_page(sources, standards)),
              "conventions.html": ("Conventions", conventions_page()),
              "upbrpy.html": ("Using with UPbRPy", upbrpy_page()),
              "contributing.html": ("Contributing", contributing_page())}
    for material, items in groups.items():
        bodies[f"materials/{material}.html"] = (material.title(), material_page(material, items, sources))
    for filename, (title, body) in bodies.items():
        destination = out / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        material = Path(filename).stem if filename.startswith("materials/") else None
        destination.write_text(page(title, body, filename, groups, index, material), encoding="utf-8")
    for source in (SITE / "static").rglob("*"):
        if source.is_file():
            destination = out / "static" / source.relative_to(SITE / "static")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    for filename in ("favicon.svg", "favicon-32.png"):
        (out / filename).write_bytes((SITE / filename).read_bytes())
    (out / "search-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
    print(f"Built {count_label(len(bodies), 'page')} in {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Output directory (default: _site when building)")
    parser.add_argument("--readme", action="store_true", help="Regenerate the README materials table")
    parser.add_argument("--check", action="store_true", help="Check links and standard coverage after building")
    args = parser.parse_args()
    try:
        _, sources, standards = load_library()
        groups = group_materials(standards)
        if args.readme:
            update_readme(groups)
        if args.out is not None or not args.readme or args.check:
            out = args.out or ROOT / "_site"
            build(out, sources, standards, groups)
            if args.check:
                check_site(out, sources, standards)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"build.py: {error}\n")


if __name__ == "__main__":
    main()
