"""Generate the library icon from the stored Mineral Habit Atlas geometry.

Run from the repository root (Python 3, standard library only):
    python3 assets/make_icon.py
    sh assets/make_icons.sh

Reads assets/minerals/crystals.json; writes assets/icon.svg (four catalogue
rows) and assets/icon-small.svg (one large zircon beside three thick value
bars). No atlas.json is needed. Projection, culling, painter order and KEY/RIM
shading are shared with make_mineral_icons.py. Stored views are fitted uniformly
into their boxes. make_icons.sh uses the small variant for 32/64 px and the
site favicon, which also serves as the 42 px header mark.
"""

import json
from pathlib import Path

from make_mineral_icons import EDGE, project_faces

ASSETS = Path(__file__).resolve().parent
MATERIALS = ("zircon", "apatite", "titanite", "rutile")


def crystal_svg(data, box, small=False):
    """Fit a stored crystal into (x, y, width, height), preserving its aspect."""
    faces = [{"loop": f["loop"], "form": i} for i, f in enumerate(data["faces"])]
    colours = {i: f["color"] for i, f in enumerate(data["faces"])}
    drawn = project_faces(data["vertices"], faces, colours, data["view"])
    points = [p for _, loop, _ in drawn for p in loop]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    x, y, width, height = box
    scale = min(width / (max(xs) - min(xs)), height / (max(ys) - min(ys)))

    def fmt(loop):
        return " ".join(f"{x + width / 2 + (px - cx) * scale:.2f},"
                        f"{y + height / 2 + (py - cy) * scale:.2f}" for px, py in loop)

    fills = "".join(f'<polygon points="{fmt(loop)}" fill="{colour}"/>'
                    for _, loop, colour in drawn)
    edges = "".join(f'<polygon points="{fmt(loop)}"/>' for _, loop, _ in drawn)
    # The mineral marks use 0.4 / 0.7 strokes in a 34 x 42 viewBox.
    stroke_scale = height / 38
    faint_opacity = "0" if small else "0.18"
    edge_opacity = "0.35" if small else "0.7"
    edge_width = (0.8 if small else 1.2) * stroke_scale
    return (f'<g stroke="{EDGE}" stroke-linejoin="round">'
            f'<g fill="none" stroke-opacity="0.85" stroke-width="{3 * edge_width:.2f}">{edges}</g>'
            f'<g stroke-opacity="{faint_opacity}" stroke-width="{0.4 * stroke_scale:.2f}">{fills}</g>'
            f'<g fill="none" stroke-opacity="{edge_opacity}" stroke-width="{edge_width:.2f}">{edges}</g>'
            '</g>')


def render(crystals, small=False):
    title = ("upb-standards: Mineral Habit Atlas zircon habit" if small else
             "upb-standards: Mineral Habit Atlas zircon, apatite, titanite and rutile habits")
    desc = ("A large blue-tipped, doubly terminated Mineral Habit Atlas zircon habit beside three thick grey value bars on a white catalogue card and light rounded tile."
            if small else "Mineral Habit Atlas zircon, apatite, titanite and rutile habits, top to bottom, beside grey value bars on a white catalogue card and light rounded tile.")
    card = ((64, 64, 384, 384) if small else (88, 72, 336, 368))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title desc">',
             f'<title id="title">{title}</title>',
             f'<desc id="desc">{desc}</desc>',
             '<defs>',
             '<linearGradient id="tile" x2="0.8" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#e9eef5"/></linearGradient>',
             '<linearGradient id="paper" x2="0.8" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#f1f5f9"/></linearGradient>',
             '<filter id="shadow" x="-25%" y="-25%" width="150%" height="150%"><feDropShadow dx="0" dy="9" stdDeviation="10" flood-color="#0f1b2d" flood-opacity="0.25"/></filter>',
             '</defs>',
             '<rect x="36" y="36" width="440" height="440" rx="88" fill="url(#tile)" stroke="#d9e1ec" stroke-width="10"/>',
             '<g filter="url(#shadow)">',
             f'<rect x="{card[0]}" y="{card[1]}" width="{card[2]}" height="{card[3]}" rx="22" fill="url(#paper)" stroke="#cbd5e1" stroke-width="3"/>']
    if small:
        parts.append(crystal_svg(crystals["zircon"], (85, 102, 170, 308), small=True))
        for y, width in ((146, 124), (238, 96), (330, 112)):
            parts.append(f'<rect x="276" y="{y}" width="{width}" height="38" rx="10" fill="#94a3b8"/>')
    else:
        for i, material in enumerate(MATERIALS):
            cy = 118 + 92 * i
            # 71 px plus the 6.73 px silhouette leaves a 14.27 px row gap.
            parts.append(crystal_svg(crystals[material], (110, cy - 35.5, 100, 71)))
            parts.append(f'<rect x="228" y="{cy - 14}" width="{(150, 128, 144, 134)[i]}" height="14" rx="5" fill="#94a3b8"/>')
            parts.append(f'<rect x="228" y="{cy + 12}" width="{(98, 112, 90, 104)[i]}" height="10" rx="4" fill="#cbd5e1"/>')
    parts.extend(['</g>', '</svg>'])
    return "\n".join(parts) + "\n"


def main():
    crystals = json.loads((ASSETS / "minerals" / "crystals.json").read_text(encoding="utf-8"))
    (ASSETS / "icon.svg").write_text(render(crystals), encoding="utf-8")
    (ASSETS / "icon-small.svg").write_text(render(crystals, small=True), encoding="utf-8")


if __name__ == "__main__":
    main()
