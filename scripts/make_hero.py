#!/usr/bin/env python3
"""
Generate the home-page architecture graphic: docs/assets/gaiakeep-architecture.svg

    python3 scripts/make_hero.py

External AI agents on the left reach the GaiaKeep core through the Cresco mesh in the middle; every
block is chunked, hashed, deduplicated and encrypted at the origin, then erasure coded across three
sites whose durable tier is tape. The SVG is self-contained (no scripts, no external fonts) so it
works as an <img>; its motion stops for readers who ask for reduced motion.
"""
from pathlib import Path

W, H = 1600, 900
OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "gaiakeep-architecture.svg"

TEXT, MUTED, DIM = "#e8f4f6", "#93b6c1", "#5f8794"
TEAL, TEAL2, CYAN, BLUE, AMBER, VIOLET, PINK, GREEN = (
    "#2dd4bf", "#5eead4", "#38bdf8", "#60a5fa", "#fbbf24", "#a78bfa", "#f472b6", "#4ade80")
FONT = "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

out = []
add = out.append


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=14, fill=TEXT, weight=400, anchor="start", spacing=0, extra=""):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
        f'text-anchor="{anchor}"{ls}{extra}>{esc(s)}</text>')


# ---------------------------------------------------------------- icons (drawn in a 40 x 40 box at cx, cy)
def icon(kind, cx, cy, color):
    add(f'<circle cx="{cx}" cy="{cy}" r="22" fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-opacity="0.55"/>')
    c = f'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "spark":        # a language-model agent
        add(f'<path d="M{cx} {cy-12} C{cx+2} {cy-3} {cx+3} {cy-2} {cx+12} {cy} C{cx+3} {cy+2} {cx+2} {cy+3} {cx} {cy+12} '
            f'C{cx-2} {cy+3} {cx-3} {cy+2} {cx-12} {cy} C{cx-3} {cy-2} {cx-2} {cy-3} {cx} {cy-12}Z" fill="{color}" fill-opacity="0.9"/>')
    elif kind == "chip":       # GPU pipelines
        add(f'<rect x="{cx-8}" y="{cy-8}" width="16" height="16" rx="3" {c}/>')
        for d in (-4, 0, 4):
            add(f'<path d="M{cx+d} {cy-8}v-4M{cx+d} {cy+8}v4M{cx-8} {cy+d}h-4M{cx+8} {cy+d}h4" {c}/>')
    elif kind == "scan":       # clinical imaging
        add(f'<circle cx="{cx}" cy="{cy}" r="11" {c}/>')
        add(f'<circle cx="{cx}" cy="{cy}" r="5" {c}/>')
        add(f'<path d="M{cx-11} {cy}h4M{cx+7} {cy}h4" {c}/>')
    elif kind == "campus":     # partner institutions
        add(f'<path d="M{cx-12} {cy-3}L{cx} {cy-11}L{cx+12} {cy-3}Z M{cx-9} {cy-1}v9M{cx-3} {cy-1}v9M{cx+3} {cy-1}v9'
            f'M{cx+9} {cy-1}v9M{cx-12} {cy+11}h24" {c}/>')
    elif kind == "shield":     # lifecycle and compliance
        add(f'<path d="M{cx} {cy-12}L{cx+10} {cy-8}V{cy}C{cx+10} {cy+7} {cx+5} {cy+11} {cx} {cy+13}'
            f'C{cx-5} {cy+11} {cx-10} {cy+7} {cx-10} {cy}V{cy-8}Z M{cx-4} {cy}l3 3l6 -6" {c}/>')


# ---------------------------------------------------------------- canvas
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}" '
    'role="img" aria-labelledby="t d">')
add('<title id="t">GaiaKeep GFS: how the distributed system fits together</title>')
add('<desc id="d">External AI agents send signed requests through the Cresco mesh to the replicated GaiaKeep core, '
    'which chunks, hashes, deduplicates and encrypts every block at the origin and erasure codes it across three '
    'sites whose durable tier is a tape library. Versions stream back out to agents, GPU pipelines and partners.</desc>')
add(f'''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#051019"/><stop offset="0.55" stop-color="#0a1f2e"/><stop offset="1" stop-color="#071824"/>
  </linearGradient>
  <radialGradient id="halo" cx="0.5" cy="0.48" r="0.5">
    <stop offset="0" stop-color="{TEAL}" stop-opacity="0.22"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="core" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0f3a44"/><stop offset="1" stop-color="#0a2530"/>
  </linearGradient>
  <linearGradient id="fA" x1="0" x2="1"><stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{TEAL2}"/></linearGradient>
  <linearGradient id="fB" x1="0" x2="1"><stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
  <linearGradient id="fC" x1="0" x2="1"><stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{AMBER}"/></linearGradient>
  <linearGradient id="out" x1="1" x2="0"><stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
  <pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="1" fill="#6fb9c6" fill-opacity="0.10"/>
  </pattern>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="10"/>
  </filter>
  <clipPath id="frame"><rect width="{W}" height="{H}" rx="22"/></clipPath>
</defs>
<style>
  .flow {{ stroke-dasharray: 6 10; animation: run 1.6s linear infinite; }}
  .flow.slow {{ animation-duration: 2.8s; }}
  .flow.back {{ animation-direction: reverse; }}
  .pulse {{ animation: pulse 3.2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
  @keyframes run {{ to {{ stroke-dashoffset: -32; }} }}
  @keyframes pulse {{ 0%, 100% {{ opacity: .55; }} 50% {{ opacity: 1; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .flow, .pulse {{ animation: none; }}
    .motion {{ display: none; }}
  }}
</style>''')
add('<g clip-path="url(#frame)">')
add(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
add(f'<rect width="{W}" height="{H}" fill="url(#dots)"/>')
add('<ellipse cx="770" cy="440" rx="430" ry="330" fill="url(#halo)"/>')

# ---------------------------------------------------------------- header
text(48, 66, "GaiaKeep GFS", 34, TEXT, 700)
text(48, 98, "A global file system for AI agents: versioned datasets, durable on tape, streamed anywhere over the Cresco mesh",
     17, MUTED)
# legend
lx, ly = 1186, 52
add(f'<rect x="{lx-18}" y="{ly-26}" width="392" height="80" rx="12" fill="#ffffff" fill-opacity="0.03" stroke="#8fd3dc" stroke-opacity="0.15"/>')
add(f'<path d="M{lx} {ly}h46" stroke="{TEAL2}" stroke-width="1.6" class="flow slow"/>')
text(lx + 58, ly + 5, "control plane: signed requests and events", 12.5, MUTED)
add(f'<path d="M{lx} {ly+30}h46" stroke="{BLUE}" stroke-width="4" stroke-linecap="round"/>')
text(lx + 58, ly + 35, "dataplane: encrypted blocks on many flows", 12.5, MUTED)

# ---------------------------------------------------------------- column headers
for x, s in ((48, "EXTERNAL AI AGENTS"), (492, "CRESCO MESH"), (1110, "DURABLE TIER · THREE SITES")):
    text(x, 152, s, 12.5, TEAL2, 700, spacing=2.2)

# ---------------------------------------------------------------- mesh region (drawn first, under everything)
add('<rect x="470" y="128" width="606" height="642" rx="26" fill="#0b2a36" fill-opacity="0.35" '
    'stroke="#5eead4" stroke-opacity="0.18" stroke-dasharray="2 6"/>')

nodes = {
    "G": (520, 430), "n1": (566, 232), "n2": (700, 196), "n3": (858, 200), "n4": (1004, 252), "n5": (1040, 390),
    "n6": (1026, 548), "n7": (936, 676), "n8": (772, 706), "n9": (612, 680), "n10": (536, 566),
}
ring = ["G", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "G"]
chords = [("n1", "n3"), ("n2", "n4"), ("n3", "n5"), ("n5", "n7"), ("n6", "n8"), ("n7", "n9"), ("n8", "n10"), ("n10", "n1"),
          ("G", "n2"), ("G", "n9"), ("n4", "n6")]
core = (615, 290, 310, 282)   # x, y, w, h
cx0, cy0 = core[0] + core[2] / 2, core[1] + core[3] / 2
for a, b in chords:
    (x1, y1), (x2, y2) = nodes[a], nodes[b]
    add(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#5eead4" stroke-opacity="0.13" stroke-width="1.2"/>')
for a, b in zip(ring, ring[1:]):
    (x1, y1), (x2, y2) = nodes[a], nodes[b]
    add(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#5eead4" stroke-opacity="0.32" stroke-width="1.5"/>')
    add(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{TEAL2}" stroke-opacity="0.75" stroke-width="1.5" class="flow slow"/>')
# spokes from the ring into the core (the core's peers sit on mesh nodes)
for k in ("G", "n2", "n3", "n5", "n8", "n10"):
    x, y = nodes[k]
    tx = min(max(x, core[0] + 20), core[0] + core[2] - 20)
    ty = min(max(y, core[1] + 20), core[1] + core[3] - 20)
    add(f'<path d="M{x} {y}L{tx} {ty}" stroke="{TEAL2}" stroke-opacity="0.45" stroke-width="1.3" class="flow"/>')

# ---------------------------------------------------------------- agents column
agents = [
    ("spark", VIOLET, "Language-model agents", "call the core's verbs as tools"),
    ("chip", CYAN, "Training and inference", "stream any version to GPUs"),
    ("scan", PINK, "Clinical imaging pipelines", "DICOM · whole-slide · NIfTI"),
    ("campus", GREEN, "Partner institutions", "federated tenants and grants"),
    ("shield", AMBER, "Compliance agents", "retention · legal orders · audit"),
]
gx, gy = nodes["G"]
for i, (kind, color, title, sub) in enumerate(agents):
    y = 172 + i * 98
    cy = y + 42
    # request (into the mesh) and, for the training card, the version streamed back out
    add(f'<path d="M338 {cy}C410 {cy} 430 {gy} {gx-14} {gy}" stroke="{TEAL2}" stroke-opacity="0.25" stroke-width="1.4" fill="none"/>')
    add(f'<path d="M338 {cy}C410 {cy} 430 {gy} {gx-14} {gy}" stroke="{color}" stroke-opacity="0.9" stroke-width="1.6" fill="none" class="flow slow"/>')
    add(f'<rect x="48" y="{y}" width="290" height="84" rx="14" fill="#ffffff" fill-opacity="0.045" stroke="{color}" stroke-opacity="0.35"/>')
    icon(kind, 88, cy, color)
    text(124, cy - 5, title, 15.5, TEXT, 650)
    text(124, cy + 17, sub, 12.8, MUTED)
# the stream back out to the training card
ty = 172 + 98 + 42
add(f'<path d="M{gx-14} {gy+8}C440 {gy+8} 420 {ty+10} 340 {ty+10}" stroke="url(#out)" stroke-width="4.5" fill="none" stroke-linecap="round" opacity="0.9"/>')
add(f'<path d="M{gx-14} {gy+8}C440 {gy+8} 420 {ty+10} 340 {ty+10}" stroke="#ffffff" stroke-opacity="0.65" stroke-width="2" fill="none" class="flow"/>')
# verbs
add('<rect x="48" y="668" width="290" height="44" rx="22" fill="#2dd4bf" fill-opacity="0.12" stroke="#5eead4" stroke-opacity="0.5"/>')
text(193, 696, "prospect  →  realise  →  publish", 15, TEXT, 650, "middle")
text(193, 738, "Agents ask what a move costs, then ask for it", 12.5, DIM, 400, "middle")

# ---------------------------------------------------------------- mesh nodes (over the links)
for k, (x, y) in nodes.items():
    big = k in ("n2", "n5", "n8", "G")
    r = 10 if big else 7
    if big:
        add(f'<circle cx="{x}" cy="{y}" r="{r+7}" fill="none" stroke="{TEAL2}" stroke-opacity="0.35" class="pulse"/>')
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#0b2a36" stroke="{TEAL2}" stroke-width="2.2" filter="url(#glow)"/>')
    add(f'<circle cx="{x}" cy="{y}" r="{r-4}" fill="{TEAL2}"/>')
text(gx, gy - 24, "agent gateway", 12, MUTED, 600, "middle")
text(nodes["n2"][0], nodes["n2"][1] - 22, "global controller", 11.5, DIM, 400, "middle")
text(nodes["n8"][0] + 18, nodes["n8"][1] + 4, "regional controller", 11.5, DIM)

# mesh capability chips
chips = ["zero-trust identity", "tenant isolation", "QoS tiers", "multi-flow dataplane"]
x = 492
for s in chips:
    w = 6.9 * len(s) + 22
    add(f'<rect x="{x}" y="728" width="{w:.0f}" height="26" rx="13" fill="#5eead4" fill-opacity="0.08" stroke="#5eead4" stroke-opacity="0.3"/>')
    text(x + w / 2, 745.5, s, 12, TEAL2, 500, "middle")
    x += w + 8

# ---------------------------------------------------------------- the core
x, y, w, h = core
add(f'<rect x="{x-10}" y="{y-10}" width="{w+20}" height="{h+20}" rx="28" fill="{TEAL}" opacity="0.18" filter="url(#soft)"/>')
add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="url(#core)" stroke="{TEAL2}" stroke-width="1.8"/>')
text(cx0, y + 34, "GAIAKEEP GFS CORE", 12.5, TEAL2, 700, "middle", 2.4)
text(cx0, y + 62, "Replicated storage core", 21, TEXT, 700, "middle")
rows = ["Raft-replicated journal and audit", "Versions, extracts and citations", "Placement, repair and lifecycle"]
for i, s in enumerate(rows):
    yy = y + 96 + i * 27
    add(f'<circle cx="{x+30}" cy="{yy-5}" r="3.5" fill="{TEAL2}"/>')
    text(x + 44, yy, s, 14, "#cfe9ee")
# block pipeline
steps = ["chunk", "hash", "dedup", "encrypt"]
bx, by = x + 18, y + 190
for i, s in enumerate(steps):
    xx = bx + i * 70
    add(f'<rect x="{xx}" y="{by}" width="60" height="30" rx="8" fill="#ffffff" fill-opacity="0.06" stroke="{TEAL2}" stroke-opacity="0.6"/>')
    text(xx + 30, by + 20, s, 12.5, TEXT, 600, "middle")
    if i < 3:
        add(f'<path d="M{xx+62} {by+15}h6" stroke="{TEAL2}" stroke-width="1.6"/>')
text(cx0, by + 56, "every block sealed at the origin", 12, MUTED, 400, "middle")

# ---------------------------------------------------------------- sites
sites = [("SITE A", "data share 1", TEAL2, "fA"), ("SITE B", "data share 2", BLUE, "fB"), ("SITE C", "parity share", AMBER, "fC")]
src = [nodes["n4"], nodes["n5"], nodes["n6"]]
paths = []
for i, (name, share, color, grad) in enumerate(sites):
    sx, sy, sw, sh = 1110, 172 + i * 186, 450, 168
    my = sy + sh / 2
    nx, ny = src[i]
    d = f"M{cx0+w/2-4} {cy0-30+i*30}C{nx-40} {ny} {nx} {ny} {nx} {ny}C{nx+40} {ny} {sx-50} {my} {sx} {my}"
    paths.append((d, color))
    add(f'<path d="{d}" stroke="url(#{grad})" stroke-width="4.5" fill="none" stroke-linecap="round" opacity="0.85"/>')
    add(f'<path d="{d}" stroke="#ffffff" stroke-opacity="0.6" stroke-width="1.8" fill="none" class="flow"/>')
    # card
    add(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="16" fill="#ffffff" fill-opacity="0.045" stroke="{color}" stroke-opacity="0.45"/>')
    text(sx + 22, sy + 32, name, 14, TEXT, 700, spacing=2)
    add(f'<rect x="{sx+sw-138}" y="{sy+15}" width="118" height="24" rx="12" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-opacity="0.7"/>')
    add(f'<rect x="{sx+sw-129}" y="{sy+22}" width="10" height="10" rx="2" fill="{color}"/>')
    text(sx + sw - 72, sy + 31.5, share, 11.5, TEXT, 600, "middle")
    # tiers
    ty0 = sy + 52
    tiles = [(sx + 20, 92, "NVMe"), (sx + 122, 92, "Disk"), (sx + 224, 206, "Tape library")]
    for tx, tw, label in tiles:
        primary = label == "Tape library"
        add(f'<rect x="{tx}" y="{ty0}" width="{tw}" height="98" rx="12" fill="#ffffff" fill-opacity="{0.07 if primary else 0.035}" '
            f'stroke="{color if primary else "#8fd3dc"}" stroke-opacity="{0.6 if primary else 0.18}"/>')
        icx = tx + tw / 2
        if label == "NVMe":
            for k in range(3):
                add(f'<rect x="{icx-18}" y="{ty0+18+k*9}" width="36" height="6" rx="2" fill="{CYAN}" fill-opacity="{0.85-k*0.2}"/>')
            text(icx, ty0 + 70, "NVMe", 13, TEXT, 600, "middle")
            text(icx, ty0 + 87, "hot", 11.5, DIM, 400, "middle")
        elif label == "Disk":
            add(f'<ellipse cx="{icx}" cy="{ty0+20}" rx="17" ry="6" fill="none" stroke="{BLUE}" stroke-width="2"/>')
            add(f'<path d="M{icx-17} {ty0+20}v20a17 6 0 0 0 34 0v-20" fill="none" stroke="{BLUE}" stroke-width="2"/>')
            add(f'<path d="M{icx-17} {ty0+30}a17 6 0 0 0 34 0" fill="none" stroke="{BLUE}" stroke-opacity="0.6" stroke-width="1.5"/>')
            text(icx, ty0 + 70, "Disk", 13, TEXT, 600, "middle")
            text(icx, ty0 + 87, "warm", 11.5, DIM, 400, "middle")
        else:
            rx0 = tx + 16
            add(f'<rect x="{rx0}" y="{ty0+12}" width="58" height="74" rx="5" fill="none" stroke="{color}" stroke-width="1.8"/>')
            for r in range(5):
                for c in range(2):
                    add(f'<rect x="{rx0+7+c*24}" y="{ty0+19+r*13}" width="20" height="9" rx="2" fill="{color}" '
                        f'fill-opacity="{0.9 if (r+c+i) % 3 else 0.35}"/>')
            text(tx + 88, ty0 + 30, "Tape library", 14, TEXT, 650)
            text(tx + 88, ty0 + 50, "LTO-10 · primary", 12, MUTED)
            text(tx + 88, ty0 + 68, "verified before", 12, MUTED)
            text(tx + 88, ty0 + 84, "commit", 12, MUTED)
text(1335, 742, "Erasure coded 2 + 1: any one site can be lost", 13.5, MUTED, 500, "middle")

# shares travelling to their sites (hidden when motion is reduced)
add('<g class="motion">')
for i, (d, color) in enumerate(paths):
    for k in range(2):
        add(f'<rect x="-6" y="-6" width="12" height="12" rx="2.5" fill="{color}" filter="url(#glow)">'
            f'<animateMotion dur="3.4s" begin="{i*0.45 + k*1.7:.2f}s" repeatCount="indefinite" path="{d}" rotate="0"/></rect>')
add('</g>')

# ---------------------------------------------------------------- the five properties
props = [("Programmatic", "no filesystem: agents call tools", VIOLET), ("Versioned", "every read names a version", CYAN),
         ("Resilient", "erasure coded, tape primary", TEAL2), ("Secure", "encrypted at origin, zero trust", AMBER),
         ("Distributed", "federated over the Cresco mesh", GREEN)]
for i, (t, s, color) in enumerate(props):
    px = 48 + i * 304
    add(f'<rect x="{px}" y="796" width="288" height="66" rx="14" fill="#ffffff" fill-opacity="0.04" stroke="{color}" stroke-opacity="0.4"/>')
    add(f'<rect x="{px}" y="806" width="4" height="46" rx="2" fill="{color}"/>')
    text(px + 22, 824, t, 16, TEXT, 700)
    text(px + 22, 847, s, 12.8, MUTED)

add('</g>')
add(f'<rect x="0.75" y="0.75" width="{W-1.5}" height="{H-1.5}" rx="22" fill="none" stroke="#5eead4" stroke-opacity="0.25" stroke-width="1.5"/>')
add('</svg>')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KiB)")
