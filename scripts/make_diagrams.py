#!/usr/bin/env python3
"""
Generate the live-tier and stability diagrams in docs/assets/:

    live-tier-flow.svg       a version's way from a write to a native copy on a live node, holds, and deletion
    planned-stop.svg         a planned stop of the core's leader: refusals, hand-over, safe resends
    store-restart.svg        a storage node restarted under writes (a rolling upgrade)

    python3 scripts/make_diagrams.py

Same palette and dark card as the home-page graphic (scripts/make_hero.py), so each reads the same in the light and
dark themes. Self-contained SVG: no scripts, no external fonts. Edit this script and run it, never the SVGs.
"""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"

TEXT, MUTED, DIM = "#e8f4f6", "#93b6c1", "#6f97a4"
TEAL, TEAL2, CYAN, BLUE, AMBER, VIOLET, PINK, GREEN = (
    "#2dd4bf", "#5eead4", "#38bdf8", "#60a5fa", "#fbbf24", "#a78bfa", "#f472b6", "#4ade80")
FONT = "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
KINDS = {  # line kinds: colour, width, dash, legend text
    "ctl": (TEAL2, 2.0, None, "request or control message (signed)"),
    "data": (CYAN, 4.0, None, "data on the dataplane (encrypted)"),
    "sig": (AMBER, 2.2, None, "the node's signed attestation"),
    "drop": (PINK, 2.4, "7 5", "deletion: a signed drop"),
    "refuse": (PINK, 2.2, "7 5", "refusal: retry elsewhere (status 12)"),
    "ok": (GREEN, 2.2, None, "accepted"),
}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, w, h, title, desc):
        self.w, self.h, self.out = w, h, []
        self.title, self.desc = title, desc

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=15, fill=TEXT, weight=400, anchor="start", spacing=0, halo=False):
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        # a halo in the background colour keeps a label legible where it crosses a line
        hs = ' stroke="#08202b" stroke-width="6" stroke-linejoin="round" paint-order="stroke"' if halo else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
                 f'text-anchor="{anchor}"{ls}{hs}>{esc(s)}</text>')

    def lines(self, x, y, rows, size=15, fill=TEXT, weight=400, anchor="start", lh=None):
        lh = lh or round(size * 1.35)
        for i, r in enumerate(rows):
            self.text(x, y + i * lh, r, size, fill, weight, anchor)

    def box(self, x, y, w, h, color, fill_op=0.045, stroke_op=0.45, rx=14, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="#ffffff" '
                 f'fill-opacity="{fill_op}" stroke="{color}" stroke-opacity="{stroke_op}" stroke-width="1.4"{d}/>')

    def chip(self, cx, cy, s, color, size=13, pad=12, bold=True):
        w = len(s) * size * 0.62 + 2 * pad
        self.add(f'<rect x="{cx - w / 2:.1f}" y="{cy - 13:.1f}" width="{w:.1f}" height="26" rx="13" fill="{color}" '
                 f'fill-opacity="0.16" stroke="{color}" stroke-opacity="0.75"/>')
        self.text(cx, cy + size * 0.36, s, size, TEXT, 650 if bold else 400, "middle")
        return w

    def badge(self, cx, cy, n, color):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="12" fill="#06141d" stroke="{color}" stroke-width="1.8"/>')
        self.text(cx, cy + 4.8, n, 13, color, 700, "middle")

    def line(self, d, kind, extra=""):
        color, width, dash, _ = KINDS[kind]
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round" '
                 f'marker-end="url(#ah-{kind})"{ds}{extra}/>')

    def legend(self, x, y, kinds):
        for i, k in enumerate(kinds):
            k, label = k if isinstance(k, tuple) else (k, KINDS[k][3])
            color, width, dash, _ = KINDS[k]
            xx = x + (i % 2) * 420
            yy = y + (i // 2) * 28
            ds = f' stroke-dasharray="{dash}"' if dash else ""
            self.add(f'<path d="M{xx} {yy}h44" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{ds}/>')
            self.text(xx + 56, yy + 5, label, 14, MUTED)

    def render(self, path):
        head = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
            f'height="{self.h}" font-family="{FONT}" role="img" aria-labelledby="t d">',
            f'<title id="t">{esc(self.title)}</title>',
            f'<desc id="d">{esc(self.desc)}</desc>',
            '<defs>',
            '  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#051019"/>'
            '<stop offset="0.55" stop-color="#0a1f2e"/><stop offset="1" stop-color="#071824"/></linearGradient>',
            '  <pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">'
            '<circle cx="1" cy="1" r="1" fill="#6fb9c6" fill-opacity="0.10"/></pattern>',
            '  <linearGradient id="core" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f3a44"/>'
            '<stop offset="1" stop-color="#0a2530"/></linearGradient>',
        ]
        for k, (color, _, _, _) in KINDS.items():
            head.append(f'  <marker id="ah-{k}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="11" '
                        f'markerHeight="11" markerUnits="userSpaceOnUse" orient="auto-start-reverse">'
                        f'<path d="M0 0.5L10 5L0 9.5z" fill="{color}"/></marker>')
        head += ['</defs>',
                 f'<rect width="{self.w}" height="{self.h}" rx="22" fill="url(#bg)"/>',
                 f'<rect width="{self.w}" height="{self.h}" rx="22" fill="url(#dots)"/>']
        tail = [f'<rect x="0.75" y="0.75" width="{self.w - 1.5}" height="{self.h - 1.5}" rx="22" fill="none" '
                'stroke="#5eead4" stroke-opacity="0.25" stroke-width="1.5"/>', '</svg>']
        path.write_text("\n".join(head + self.out + tail) + "\n", encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size // 1024} KiB)")


# ===================================================================== a sequence diagram (time runs down)
def sequence(name, title, subtitle, desc, lanes, steps, footer, legend, W=900):
    """lanes: [(name, sub, colour)]; steps: dicts with kind phase | msg | note, see below."""
    gutter, right = 104, 22
    n = len(lanes)
    lw = (W - gutter - right) / n
    xs = [gutter + lw * (i + 0.5) for i in range(n)]
    body = []
    probe = Svg(W, 0, "", "")          # draws the steps into body to measure the height
    probe.out = body
    y = 214
    for st in steps:
        k = st["kind"]
        t = st.get("t")
        if k == "phase":
            probe.add(f'<path d="M24 {y + 18}H{W - 24}" stroke="#5eead4" stroke-opacity="0.18"/>')
            probe.text(28, y + 38, st["text"].upper(), 12.5, TEAL2, 700, spacing=1.6)
            y += 54
            continue
        if k == "msg":
            a, b = st["a"], st["b"]
            rows = st["label"] if isinstance(st["label"], list) else [st["label"]]
            ya = y + 20 * len(rows) + 8
            x1, x2 = xs[a], xs[b]
            sgn = 1 if x2 > x1 else -1
            probe.line(f"M{x1 + sgn * 8:.1f} {ya}H{x2 - sgn * 10:.1f}", st.get("style", "ctl"))
            mid = (x1 + x2) / 2
            for i, r in enumerate(rows):
                probe.text(mid, y + 14 + i * 20, r, 15, TEXT if i == 0 else MUTED, 600 if i == 0 else 400, "middle",
                           halo=True)
            if t:
                probe.text(24, ya + 5, t, 13, AMBER, 600)
            y = ya + 22
            continue
        if k == "note":
            rows = st["text"]
            span = st["span"] if "span" in st else (st["lane"], st["lane"])
            color = st.get("color", MUTED)
            x0 = xs[span[0]] - lw / 2 + 10
            x1 = xs[span[1]] + lw / 2 - 10
            need = max(len(r) for r in rows) * 14.5 * 0.56 + 34      # widen a note to its text, centred
            if need > x1 - x0:
                c = (x0 + x1) / 2
                x0, x1 = max(gutter - 6, c - need / 2), min(W - right, c + need / 2)
                if x1 - x0 < need - 0.5:
                    x0, x1 = (W - right - need, W - right) if c > W / 2 else (gutter - 6, gutter - 6 + need)
            h = 20 * len(rows) + 18
            probe.add(f'<rect x="{x0:.1f}" y="{y + 4:.1f}" width="{x1 - x0:.1f}" height="{h}" rx="10" fill="#08202b" '
                      f'stroke="{color}" stroke-opacity="0.7" stroke-width="1.3"/>')
            probe.add(f'<rect x="{x0:.1f}" y="{y + 10:.1f}" width="4" height="{h - 12}" rx="2" fill="{color}"/>')
            for i, r in enumerate(rows):
                probe.text(x0 + 16, y + 26 + i * 20, r, 14.5, TEXT if i == 0 else "#cfe3e8", 600 if i == 0 else 400)
            if t:
                probe.text(24, y + 26, t, 13, AMBER, 600)
            y += h + 14
            continue
        raise ValueError(k)
    end = y + 10
    fh = 26 * len(footer) + 34 + 28 * ((len(legend) + 1) // 2)
    H = int(end + fh + 24)

    s = Svg(W, H, title, desc)
    s.text(40, 58, title, 26, TEXT, 700)
    s.text(40, 88, subtitle, 15.5, MUTED)
    # lane headers and lifelines
    for (ln, sub, color), x in zip(lanes, xs):
        bw = lw - 18
        s.add(f'<rect x="{x - bw / 2:.1f}" y="120" width="{bw:.1f}" height="72" rx="14" fill="#ffffff" '
              f'fill-opacity="0.05" stroke="{color}" stroke-opacity="0.55"/>')
        s.add(f'<rect x="{x - bw / 2 + 14:.1f}" y="120" width="{bw - 28:.1f}" height="3" rx="1.5" fill="{color}"/>')
        s.text(x, 151, ln, 16, TEXT, 700, "middle")
        s.text(x, 174, sub, 13, MUTED, 400, "middle")
        s.add(f'<path d="M{x:.1f} 196V{end}" stroke="{color}" stroke-opacity="0.32" stroke-width="1.5" '
              'stroke-dasharray="3 6"/>')
    s.out += body
    fy = end + 22
    for i, r in enumerate(footer):
        s.text(40, fy + i * 26, r, 14.5, "#cfe3e8" if i == 0 else MUTED)
    s.legend(40, fy + 26 * len(footer) + 18, legend)
    s.render(ASSETS / name)


# ===================================================================== the live tier, as a picture
def live_tier_flow():
    W, H = 1200, 860
    s = Svg(W, H, "The live tier: from a write to a native copy, and back out",
            "An agent publishes a version to the replicated core, which writes encrypted blocks to the durable tier. "
            "Only when the tape copies are verified does the version commit; a realise asked earlier waits, the "
            "writer's included. The core then registers a row in its journaled inventory, decrypts the version and "
            "pushes it over AES-256-GCM node streams to a live node, which verifies every file, places it as ordinary "
            "files and signs an attestation; the row becomes LIVE. Holds (lease, extend, pin) keep a copy; a legal "
            "deletion is journaled with its cause, sent to every node holding a copy as a signed drop, and ends only "
            "on the node's signed attestation that the files are gone.")
    s.text(40, 56, "The live tier: from a write to a native copy, and back out", 26, TEXT, 700)
    s.text(40, 86, "Every copy is registered before a byte moves, made only after the version commits, "
                   "and deleted on the node's signed word.", 15.5, MUTED)

    # ---- left column: agent, holds, deletion
    s.box(40, 128, 290, 98, VIOLET)
    s.text(62, 162, "Agent", 17, TEXT, 700)
    s.lines(62, 188, ["writes a version; asks for a", "copy at a live node"], 14, MUTED)
    s.box(40, 254, 290, 116, TEAL2)
    s.text(62, 286, "Holds", 17, TEXT, 700)
    s.lines(62, 311, ["a lease (7 days by default),", "extend, pin, unpin; a pin also", "keeps the version from pruning"],
            14, MUTED, lh=19)
    s.box(40, 396, 290, 108, PINK, stroke_op=0.6)
    s.text(62, 430, "Deletion reaches every copy", 17, TEXT, 700)
    s.lines(62, 456, ["FORGET · legal order · withdraw ·", "destroy · grant end · expiry · release"], 14, MUTED)

    # ---- the core
    cx, cy, cw, ch = 420, 120, 380, 384
    s.add(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="20" fill="url(#core)" stroke="{TEAL2}" stroke-width="1.8"/>')
    s.text(cx + cw / 2, cy + 32, "REPLICATED CORE", 12.5, TEAL2, 700, "middle", 2.2)
    s.text(cx + cw / 2, cy + 60, "Versions and the live inventory", 19, TEXT, 700, "middle")
    s.text(cx + 24, cy + 102, "version v7", 14, MUTED, 600)
    s.chip(cx + 186, cy + 97, "COMMITTING", AMBER)
    s.add(f'<path d="M{cx + 252} {cy + 97}h22" stroke="{TEAL2}" stroke-width="1.8" marker-end="url(#ah-ctl)"/>')
    s.chip(cx + 318, cy + 97, "committed", GREEN)
    s.add(f'<rect x="{cx + 22}" y="{cy + 124}" width="{cw - 44}" height="52" rx="10" fill="{AMBER}" fill-opacity="0.08" '
          f'stroke="{AMBER}" stroke-opacity="0.45"/>')
    s.lines(cx + 38, cy + 145, ["No early copy: no row and no byte before", "the commit, for anyone, the writer included"],
            13.5, "#f5deb0")
    s.text(cx + 24, cy + 210, "a row per copy, journaled", 14, MUTED, 600)
    chain = [("REALISING", CYAN), ("LIVE", GREEN), ("DROPPING", PINK), ("gone", DIM)]
    xx = cx + 24
    for i, (lab, col) in enumerate(chain):
        w = len(lab) * 13 * 0.62 + 20
        s.chip(xx + w / 2, cy + 240, lab, col, 13, 10)
        xx += w
        if i < 3:
            s.add(f'<path d="M{xx + 3} {cy + 240}h12" stroke="{TEAL2}" stroke-width="1.6" marker-end="url(#ah-ctl)"/>')
            xx += 20
    s.lines(cx + 24, cy + 282, ["REALISING: registered before any byte moves",
                                "LIVE: the node's signed root matches the core's",
                                "DROPPING: journaled with its cause; gone only",
                                "on the node's signed attestation"], 13.5, "#cfe3e8", lh=21)
    s.text(cx + cw / 2, cy + ch - 16, "decrypted only here · never counted toward durability", 12.5, MUTED, 400, "middle")

    # ---- the durable tier
    s.box(890, 128, 270, 112, AMBER, stroke_op=0.55)
    s.text(912, 162, "Durable tier", 17, TEXT, 700)
    s.lines(912, 188, ["three sites · disk and tape", "encrypted; the only non-native tier"], 14, MUTED)
    s.box(890, 292, 270, 132, "#8fd3dc", stroke_op=0.25)
    s.text(912, 324, "What the live tier is not", 15, TEXT, 650)
    s.lines(912, 350, ["not durable: a live node is never", "a site, and losing every live copy",
                       "loses nothing; not a server: copies", "are read where they sit"], 13.5, MUTED, lh=20)

    # ---- live nodes
    nodes = [(250, "LIVE NODE A · GPU HOST", ["v7/  copy, leased", "ws/  workspace: edit, then", "      publish a new version"]),
             (640, "LIVE NODE B · SITE COMPUTE", ["v7/  copy, pinned", "read in place by jobs and", "tools at local-disk speed"])]
    for x, lab, rows in nodes:
        s.box(x, 600, 330, 150, CYAN, fill_op=0.06, stroke_op=0.6)
        s.text(x + 22, 632, lab, 13, CYAN, 700, spacing=1.6)
        # a folder holding a tree of files: a live copy is a file system, any file type
        fx, fy = x + 22, 652
        s.add(f'<rect x="{fx}" y="{fy}" width="18" height="10" rx="2" fill="#0b2a36" stroke="{CYAN}" stroke-opacity="0.75"/>')
        s.add(f'<rect x="{fx}" y="{fy + 5}" width="46" height="40" rx="4" fill="#0b2a36" stroke="{CYAN}" stroke-opacity="0.9"/>')
        s.add(f'<path d="M{fx + 11} {fy + 15}V{fy + 37}M{fx + 11} {fy + 20}h8M{fx + 11} {fy + 28}h8M{fx + 11} {fy + 37}h8" '
              f'stroke="{CYAN}" stroke-opacity="0.8" stroke-width="1.6" fill="none"/>')
        for k in range(3):
            s.add(f'<rect x="{fx + 21}" y="{fy + 17 + k * 8.5}" width="14" height="6" rx="1.5" fill="{CYAN}" fill-opacity="{0.35 + 0.2 * k}"/>')
        s.lines(x + 84, 668, rows, 14, "#cfe3e8", lh=21)
    s.text(40, 640, "Unencrypted", 15, TEXT, 650)
    s.lines(40, 664, ["native files, any", "type, by owner", "decision (2026-10-27)"], 14, MUTED, lh=20)
    s.lines(1000, 640, ["The operating", "system is the", "boundary on the", "node; reads there", "are not audited"], 14, MUTED, lh=20)

    # ---- arrows: write path
    s.line("M332 158H416", "ctl")
    s.badge(374, 146, "1", TEAL2)
    s.line("M804 158H884", "data")
    s.badge(846, 144, "2", CYAN)
    s.line("M886 210H808", "ctl")
    s.badge(846, 222, "3", TEAL2)
    s.text(846, 256, "tape copies", 12.5, MUTED, 400, "middle")
    s.text(846, 272, "VERIFIED", 12.5, AMBER, 700, "middle")
    # holds and deletion into the core
    s.line("M332 311H416", "ctl")
    s.badge(374, 299, "6", TEAL2)
    s.line("M332 450H416", "drop")
    s.badge(374, 438, "7", PINK)
    # core <-> live nodes: push (data), attestation (sig), drop
    for nx, px in ((415, 470), (805, 750)):
        s.line(f"M{px - 26} 508 L{nx - 26} 594", "data")
        s.line(f"M{nx} 596 L{px} 510", "sig")
        s.line(f"M{px + 26} 508 L{nx + 26} 594", "drop")
    s.badge(430, 552, "4", CYAN)
    s.badge(470, 552, "5", AMBER)
    s.badge(512, 552, "8", PINK)
    s.lines(560, 536, ["4 push · 5 attest · 8 drop"], 13, MUTED)
    s.text(560, 556, "AES-256-GCM node streams;", 13, MUTED)
    s.text(560, 574, "no path or byte in clear", 13, MUTED)

    # ---- legend and the steps
    s.legend(40, 786, ["ctl", "data", "sig", "drop"])
    s.text(1160, 846, "1 publish · 2 blocks to the durable tier · 3 commit · 4 register and push · 5 LIVE · "
                      "6 holds · 7 deletion · 8 drop, then attested gone", 12.5, DIM, 400, "end")
    s.render(ASSETS / "live-tier-flow.svg")


def planned_stop():
    lanes = [("Client", "Python or Java CoreClient", VIOLET),
             ("Peer A", "leader, being stopped", AMBER),
             ("Peer B", "most caught-up voter", TEAL2),
             ("Peer C", "voter", TEAL2)]
    steps = [
        {"kind": "phase", "text": "The stop begins: refuse, drain, hand over"},
        {"kind": "note", "lane": 1, "t": "t = 0", "color": AMBER,
         "text": ["SIGTERM: a restart or upgrade", "refuses every request but raft", "traffic from this moment"]},
        {"kind": "msg", "a": 0, "b": 1, "label": "write (signed request)"},
        {"kind": "msg", "a": 1, "b": 0, "style": "refuse",
         "label": ["12 · stopping=true", "names the other core peers"]},
        {"kind": "note", "lane": 1, "color": AMBER,
         "text": ["requests it admitted finish", "(at most 3 s); no new proposals"]},
        {"kind": "msg", "a": 1, "b": 2, "label": ["TIMEOUT_NOW", "to the most caught-up voter"]},
        {"kind": "msg", "a": 2, "b": 3, "label": "request votes"},
        {"kind": "msg", "a": 1, "b": 2, "style": "ok", "label": ["vote granted", "a retired peer still votes"]},
        {"kind": "note", "lane": 2, "t": "≈ 0.73 s", "color": GREEN,
         "text": ["new leader, serving", "0.726–0.740 s after", "the signal (measured)"]},
        {"kind": "phase", "text": "Clients follow; nothing fails"},
        {"kind": "note", "lane": 1, "color": AMBER,
         "text": ["retired: appends and applies", "nothing, never campaigns;", "answers votes and appends"]},
        {"kind": "msg", "a": 0, "b": 1, "label": "retry"},
        {"kind": "msg", "a": 1, "b": 0, "style": "refuse", "label": ["12 · leader is B", "retry_after_ms"]},
        {"kind": "msg", "a": 0, "b": 2, "style": "ok", "label": ["the same request at B: done", "a cut job is resubmitted by its request_id"]},
        {"kind": "note", "span": (0, 1), "color": VIOLET,
         "text": ["A write whose leadership ended under it answers outcome_unknown:",
                  "the next leader decides it. Clients resend only what is safe twice:",
                  "reads, requests keyed by request_id, livehold extend, pin, unpin."]},
        {"kind": "note", "lane": 1, "t": "+ 3 s", "color": AMBER,
         "text": ["lingers 3 s answering its", "refusal, then lets go"]},
        {"kind": "note", "lane": 1, "t": "3.3–3.9 s", "color": AMBER,
         "text": ["the JVM exits by itself;", "the whole stop is bounded", "at 25 s"]},
    ]
    footer = ["Measured on a local fabric with a live node, 2026-10-28 (E18 LT-C3): 10 planned stops of the",
              "leader, 0 failed client calls, no halted log, no spontaneous election. Before the fix: 5 to 36",
              "failed calls per stop, and every JVM killed after 60 s. On the HPC test bed: in progress."]
    sequence("planned-stop.svg", "A planned stop of the core's leader",
             "The stopping peer refuses with directions, hands the leadership over, and clients carry on.",
             "Sequence: at t=0 the leader receives SIGTERM and refuses every request but raft traffic with status 12 "
             "and stopping=true, naming the other core peers. Admitted requests finish within 3 s, then the leader "
             "sends TIMEOUT_NOW to the most caught-up voter, which is elected with the retired peer's vote and serves "
             "about 0.73 s after the signal. The retired peer keeps answering votes and appends, and redirects clients "
             "to the new leader. Clients resend only operations that are safe to send twice; a write cut by the "
             "leader change answers outcome_unknown. The old peer lingers 3 s, then its JVM exits in 3.3 to 3.9 s.",
             lanes, steps, footer, ["ctl", "refuse", "ok"])


def store_restart():
    lanes = [("Writer", "an upload in progress", VIOLET),
             ("Core leader", "placement and commit", TEAL2),
             ("Store S", "site B, being restarted", AMBER),
             ("Stores", "sites A and C", BLUE)]
    steps = [
        {"kind": "phase", "text": "The store announces its stop"},
        {"kind": "note", "lane": 2, "t": "stop", "color": AMBER,
         "text": ["upgrade: plugin removed", "or agent stopped"]},
        {"kind": "note", "lane": 2, "color": AMBER,
         "text": ["refuses new writes: signed,", "retryable, marked draining"]},
        {"kind": "msg", "a": 2, "b": 1, "style": "sig",
         "label": ["signed departure notice", "to every core peer, bound to this boot"]},
        {"kind": "note", "lane": 1, "color": TEAL2,
         "text": ["site B DOWN for new work", "at once, no quarantine;", "an older boot's notice", "is ignored"]},
        {"kind": "phase", "text": "Writes carry on without it"},
        {"kind": "msg", "a": 0, "b": 1, "style": "data", "label": "next part of the upload"},
        {"kind": "msg", "a": 1, "b": 3, "style": "data", "label": ["open writes placed again", "on the other stores"]},
        {"kind": "note", "lane": 1, "color": GREEN,
         "text": ["commits on two sites", "(minimum copies 2 of 3", "on the test bed)"]},
        {"kind": "msg", "a": 1, "b": 0, "style": "ok", "label": "committed"},
        {"kind": "phase", "text": "The store comes back"},
        {"kind": "note", "lane": 2, "t": "start", "color": AMBER,
         "text": ["new boot of the", "upgraded build"]},
        {"kind": "msg", "a": 2, "b": 1, "style": "ctl", "label": ["registration naming", "the new boot"]},
        {"kind": "note", "lane": 1, "color": TEAL2,
         "text": ["UP again once its", "description verifies"]},
        {"kind": "msg", "a": 1, "b": 2, "style": "data", "label": ["repair restores", "the third copy"]},
        {"kind": "note", "span": (0, 3), "color": MUTED,
         "text": ["A write that meets a silent store is undone and placed again by the core",
                  "(an older build, a crash, a lost notice). When no other store may take it, it waits",
                  "only for a store that failed under that very write or announced its stop: at most",
                  "30 s and 4 failed stores an episode, and 120 s an upload, then it fails, retryable.",
                  "A store that is simply down fails such a write at once."]},
    ]
    footer = ["Built and tested on the development branch (2026-10-28); nothing is journaled, so mixed",
              "builds are safe. After 120 s without a new boot the store is judged by its silence again.",
              "On the HPC test bed: in progress."]
    sequence("store-restart.svg", "A storage node restarted under writes",
             "A rolling upgrade: the store says it is leaving, the core places writes elsewhere, repair catches up.",
             "Sequence: a storage node being stopped for an upgrade sends every core peer a signed departure notice "
             "bound to its current boot and refuses new writes as retryable. The leader counts its site down for new "
             "work at once, places the open writes on the other sites and commits them on two sites. When the "
             "upgraded store starts, it registers under its new boot, is counted up once its description verifies, "
             "and repair restores the third copy.",
             lanes, steps, footer, ["ctl", "data", ("sig", "signed notice from the stopping store"), "ok"])


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    live_tier_flow()
    planned_stop()
    store_restart()
