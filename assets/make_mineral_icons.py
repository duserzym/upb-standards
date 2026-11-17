"""Draw the mineral marks from the Mineral Habit Atlas crystals.

    python assets/make_mineral_icons.py path/to/mineral-habit-matrix/site/data/atlas.json

The atlas file holds the crystal shown on each mineral card of
https://duserzym.github.io/mineral-habit-matrix/ (geometry, face colours per form
and the card view). Each one is projected with the atlas card view, shaded with
the atlas key and rim lights, and written as a flat SVG to assets/minerals/.
Glass has no crystal habit, so it is drawn here as a thin conchoidal shard in
the same style. It also writes assets/minerals/crystals.json, the face loops
and colours that site/build.py embeds so each page can spin the crystals live;
the SVGs are the still fallback without JavaScript or with reduced motion.
"""

import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "minerals"

# library material -> atlas mineral
ATLAS = {"zircon": "zircon", "apatite": "apatite", "titanite": "titanite", "rutile": "rutile",
         "hematite": "hematite", "carbonate": "calcite", "monazite": "monazite", "xenotime": "xenotime"}

# Card views that read better as a small still icon than the atlas defaults.
VIEWS = {"titanite": {"tilt": 30, "turn": 20}, "hematite": {"tilt": 40, "turn": -35}}

KEY = (2.5, 4.0, 5.0)    # atlas key light
RIM = (-4.0, 1.0, -3.0)  # atlas rim light
EDGE = "#2a2018"         # atlas edge colour (light theme)


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v)


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def rx(t):
    c, s = math.cos(t), math.sin(t)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(t):
    c, s = math.cos(t), math.sin(t)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def view_matrix(tilt=12, turn=-24):
    # three.js: holder quaternion from Euler(tilt, turn, 0, 'XYZ') applied after the
    # inner crystal.rotation.x = -pi/2 that stands the c axis up.
    return matmul(matmul(rx(math.radians(tilt)), ry(math.radians(turn))), rx(-math.pi / 2))


def hex2rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def rgb2hex(c):
    return "#" + "".join(f"{max(0, min(255, round(x))):02x}" for x in c)


def shade(colour, n):
    key, rim = unit(KEY), unit(RIM)
    k = max(0.0, sum(a * b for a, b in zip(n, key)))
    r = max(0.0, sum(a * b for a, b in zip(n, rim)))
    f = 0.58 + 0.5 * k + 0.12 * r
    return rgb2hex([x * f + 255 * 0.05 for x in hex2rgb(colour)])


def render(vertices, faces, colours, view, pad=2.0):
    m = view_matrix(**view)
    world = [apply(m, v) for v in vertices]
    drawn = []
    for f in faces:
        loop = [world[i] for i in f["loop"]]
        a, b, c = loop[0], loop[1], loop[2]
        u = [b[i] - a[i] for i in range(3)]
        w = [c[i] - a[i] for i in range(3)]
        n = unit((u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]))
        if n[2] <= 1e-6:  # camera looks down -z; keep faces turned towards it
            continue
        depth = sum(p[2] for p in loop) / len(loop)
        drawn.append((depth, [(p[0], -p[1]) for p in loop], shade(colours[f["form"]], n)))
    drawn.sort(key=lambda d: d[0])
    pts = [p for _, loop, _ in drawn for p in loop]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    scale = min((34 - 2 * pad) / (max(xs) - min(xs)), (42 - 2 * pad) / (max(ys) - min(ys)))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def fmt(loop):
        return " ".join(f"{(x - cx) * scale + 17:.2f},{(y - cy) * scale + 21:.2f}" for x, y in loop)

    faces_svg = "".join(f'<polygon points="{fmt(loop)}" fill="{col}"/>' for _, loop, col in drawn)
    edges_svg = "".join(f'<polygon points="{fmt(loop)}"/>' for _, loop, _ in drawn)
    return ('<svg viewBox="0 0 34 42" aria-hidden="true">'
            f'<g stroke="{EDGE}" stroke-opacity="0.18" stroke-width="0.4" stroke-linejoin="round">{faces_svg}</g>'
            f'<g fill="none" stroke="{EDGE}" stroke-opacity="0.6" stroke-width="0.7" stroke-linejoin="round">{edges_svg}</g>'
            '</svg>\n')


def glass_shard():
    """A thin shard with an irregular outline, extruded along c."""
    outline = [(-0.95, -0.35), (-0.2, -0.75), (0.55, -0.6), (1.0, -0.05),
               (0.6, 0.55), (-0.15, 0.7), (-0.75, 0.3)]
    h = 0.16
    vertices = [(x, y, h) for x, y in outline] + [(x, y, -h) for x, y in outline]
    n = len(outline)
    faces = [{"form": "top", "loop": list(range(n))},
             {"form": "top", "loop": list(range(2 * n - 1, n - 1, -1))}]
    for i in range(n):
        j = (i + 1) % n
        faces.append({"form": "side", "loop": [i, i + n, j + n, j]})
    # stand the slab on edge so the c-axis-up view shows its broad face
    vertices = [(x, z, y) for x, y, z in vertices]
    faces = [{**f, "loop": f["loop"][::-1]} for f in faces]
    return vertices, faces, {"top": "#a9c7cf", "side": "#7fa3ad"}, {"tilt": 14, "turn": -28}


def crystal(vertices, faces, colours, view):
    """Compact geometry for the live view: vertices rounded, faces with their colour."""
    return {"view": {"tilt": view.get("tilt", 12), "turn": view.get("turn", -24)},
            "vertices": [[round(x, 4) for x in v] for v in vertices],
            "faces": [{"loop": f["loop"], "color": colours[f["form"]]} for f in faces]}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    atlas = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    crystals = {}
    for material, mineral in ATLAS.items():
        card = atlas[mineral]
        colours = {f["key"]: f["color"] for f in card["forms"]}
        view = VIEWS.get(material) or card.get("view") or {}
        shape = (card["geometry"]["vertices"], card["geometry"]["faces"], colours, view)
        (OUT / f"{material}.svg").write_text(render(*shape), encoding="utf-8")
        crystals[material] = {"source": f"Mineral Habit Atlas {mineral} {card['id']}", **crystal(*shape)}
        print(f"{material}: atlas {mineral} {card['id']}")
    shape = glass_shard()
    (OUT / "glass.svg").write_text(render(*shape), encoding="utf-8")
    crystals["glass"] = {"source": "glass shard drawn for upb-standards", **crystal(*shape)}
    (OUT / "crystals.json").write_text(json.dumps(crystals, separators=(",", ":")) + "\n", encoding="utf-8")
    print("glass: shard")


if __name__ == "__main__":
    main()
