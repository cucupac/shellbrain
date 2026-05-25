#!/usr/bin/env python3
"""Generate the ShellBrain memory ontology panel.

The visual model is a symmetric neural funnel:

- Outer ring: many source neurons.
- Relay rings: each layer halves the node count.
- Gate ring and center: a compact activation well.

Everything is generated from polar math. No scatter, no hand-tuned graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from pathlib import Path


WIDTH = 1440
HEIGHT = 820
OUTPUT = Path("docs/assets/shellbrain-memory-ontology-constellation.svg")

GREEN = "#6BDCFF"
MUTED = "#8A8A90"
TITLE_ZONE = (0, 0, 0, 0)

# Center of the full SVG canvas. The page-level section heading sits outside
# the SVG, so the graph can be mathematically centered.
CENTER = (720, 410)

RINGS = [
    {"name": "source", "count": 64, "radius": 315, "opacity": 0.12, "phase": -42.1875},
    {"name": "relay", "count": 32, "radius": 254, "opacity": 0.16, "phase": -39.375},
    {"name": "select", "count": 16, "radius": 193, "opacity": 0.20, "phase": -33.75},
    {"name": "gate", "count": 8, "radius": 132, "opacity": 0.24, "phase": -22.5},
    {"name": "core", "count": 4, "radius": 76, "opacity": 0.28, "phase": 0},
]

IMPULSE_DURATION = 0.52
IMPULSE_GAP = IMPULSE_DURATION * 4
PASS_STARTS = [0.06, 2.66, 5.26]
PASS_ENDS = [round(start + IMPULSE_DURATION, 2) for start in PASS_STARTS]
TOTAL_DURATION = round(PASS_ENDS[-1] + IMPULSE_GAP, 2)
SOURCE_STAGGER = 0.006

CENTER_NODE_ID = "recall_core"

SOURCE_WINDOW = [4, 5, 6, 7, 8, 9, 10, 11]
RELAY_WINDOW = [2, 3, 4, 5]
SELECT_WINDOW = [1, 2]
GATE_WINDOW = [0, 1]


@dataclass(frozen=True)
class Cell:
    id: str
    x: float
    y: float
    band: str
    ring: int | None = None
    index: int | None = None


@dataclass(frozen=True)
class Segment:
    a: str
    b: str
    start: float
    pass_index: int
    primary: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class PulseCell:
    cell_id: str
    start: float
    pass_index: int
    anchor: bool = False
    primary: bool = False


def pct(seconds: float) -> float:
    return max(0, min(100, seconds / TOTAL_DURATION * 100))


def angle_for_index(index: int, count: int, phase: float = 0) -> float:
    return -90 + phase + index * (360 / count)


def point_from_polar(angle: float, radius: float) -> tuple[float, float]:
    cx, cy = CENTER
    theta = radians(angle)
    return cx + cos(theta) * radius, cy + sin(theta) * radius


def in_rect(x: float, y: float, rect: tuple[float, float, float, float], pad: float = 0) -> bool:
    rx, ry, rw, rh = rect
    return rx - pad <= x <= rx + rw + pad and ry - pad <= y <= ry + rh + pad


def memory_band(angle: float) -> str:
    normalized = angle % 360
    if 260 <= normalized or normalized < 25:
        return "episodic"
    if 25 <= normalized < 115:
        return "associative"
    if 115 <= normalized < 185:
        return "semantic"
    return "procedural"


def node_id(ring: int, index: int) -> str:
    count = RINGS[ring]["count"]
    return f"r{ring}_{index % count}"


def build_cells() -> dict[str, Cell]:
    cells: dict[str, Cell] = {}
    for ring, spec in enumerate(RINGS):
        count = int(spec["count"])
        radius = float(spec["radius"])
        for index in range(count):
            angle = angle_for_index(index, count, float(spec["phase"]))
            x, y = point_from_polar(angle, radius)
            if in_rect(x, y, TITLE_ZONE, 18):
                raise ValueError(f"cell enters title zone: ring={ring} index={index} point=({x:.1f},{y:.1f})")
            cells[node_id(ring, index)] = Cell(node_id(ring, index), x, y, memory_band(angle), ring, index)

    cells[CENTER_NODE_ID] = Cell(CENTER_NODE_ID, CENTER[0], CENTER[1], "brief")
    return cells


def build_latent_edges(cells: dict[str, Cell]) -> list[tuple[Cell, Cell]]:
    edges: set[tuple[str, str]] = set()

    def add(a: str, b: str) -> None:
        edges.add(tuple(sorted((a, b))))

    for ring, spec in enumerate(RINGS):
        count = int(spec["count"])
        for index in range(count):
            add(node_id(ring, index), node_id(ring, index + 1))

    for ring in range(len(RINGS) - 1):
        outer_count = int(RINGS[ring]["count"])
        inner_count = int(RINGS[ring + 1]["count"])
        compression = max(1, outer_count // inner_count)
        for index in range(outer_count):
            parent = index // compression
            add(node_id(ring, index), node_id(ring + 1, parent))
            # Secondary fan edges make the layer compression legible without
            # introducing arbitrary long cross-graph lines.
            if index % compression == 0:
                add(node_id(ring, index), node_id(ring + 1, parent - 1))
            else:
                add(node_id(ring, index), node_id(ring + 1, parent + 1))

    for index in range(int(RINGS[-1]["count"])):
        add(node_id(len(RINGS) - 1, index), CENTER_NODE_ID)

    return [(cells[a], cells[b]) for a, b in sorted(edges)]


def sector_indices(ring: int, group: int, offsets: list[int]) -> list[int]:
    count = int(RINGS[ring]["count"])
    sector_width = count // 4
    base = group * sector_width
    return [(base + offset) % count for offset in offsets]


def replay_layers(_pass_index: int) -> list[tuple[list[int], list[int], list[int], list[int], int]]:
    layers = []
    for group in range(4):
        layers.append(
            (
                sector_indices(0, group, SOURCE_WINDOW),
                sector_indices(1, group, RELAY_WINDOW),
                sector_indices(2, group, SELECT_WINDOW),
                sector_indices(3, group, GATE_WINDOW),
                group,
            )
        )
    return layers


def active_timeline() -> tuple[list[Segment], list[PulseCell]]:
    segments: list[Segment] = []
    pulse_cells: dict[tuple[int, str], PulseCell] = {}
    for pass_index in range(3):
        layers = replay_layers(pass_index)
        pass_start = PASS_STARTS[pass_index]
        primary_group = 0

        for group, (outer, relay, select, gates, core_index) in enumerate(layers):
            outer_sources = [node_id(0, index) for index in outer]
            relay_ids = [node_id(1, index) for index in relay]
            select_ids = [node_id(2, index) for index in select]
            gate_ids = [node_id(3, index) for index in gates]
            core_id = node_id(4, core_index)
            primary = group == primary_group
            offset = group * 0.0125

            for source_index, source in enumerate(outer_sources):
                source_start = pass_start + offset + source_index * SOURCE_STAGGER
                pulse_cells[(pass_index, source)] = PulseCell(source, source_start, pass_index, primary=True)
                segments.append(Segment(source, relay_ids[source_index // 2], source_start, pass_index, primary))

            for relay_index, relay_id in enumerate(relay_ids):
                select_id = select_ids[relay_index // 2]
                pulse_cells[(pass_index, relay_id)] = PulseCell(relay_id, pass_start + 0.095 + offset, pass_index, primary=primary)
                segments.append(Segment(relay_id, select_id, pass_start + 0.10 + offset, pass_index, primary))

            for select_index, select_id in enumerate(select_ids):
                gate_id = gate_ids[select_index]
                pulse_cells[(pass_index, select_id)] = PulseCell(select_id, pass_start + 0.18 + offset, pass_index, primary=primary)
                segments.append(Segment(select_id, gate_id, pass_start + 0.19 + offset, pass_index, primary, terminal=True))

            for gate_id in gate_ids:
                pulse_cells[(pass_index, gate_id)] = PulseCell(gate_id, pass_start + 0.28 + offset, pass_index, anchor=True, primary=primary)
                segments.append(Segment(gate_id, core_id, pass_start + 0.295 + offset, pass_index, primary, terminal=True))
            pulse_cells[(pass_index, core_id)] = PulseCell(core_id, pass_start + 0.345 + offset, pass_index, anchor=True, primary=primary)
            segments.append(Segment(core_id, CENTER_NODE_ID, pass_start + 0.365 + offset, pass_index, primary, terminal=True))
            pulse_cells[(pass_index, CENTER_NODE_ID)] = PulseCell(CENTER_NODE_ID, pass_start + 0.42 + offset, pass_index, anchor=True)

    return segments, list(pulse_cells.values())


def path(a: Cell, b: Cell) -> str:
    return f"M{round(a.x)} {round(a.y)} L{round(b.x)} {round(b.y)}"


def keyframes_opacity(name: str, start: float, _hold_end: float, kind: str) -> str:
    warm = start + 0.0225
    peak = start + 0.0525
    half_fade = start + 0.18
    fade = start + 0.36
    p0, p1, p2, p3, p4 = pct(start), pct(warm), pct(peak), pct(half_fade), pct(fade)
    if kind == "cell":
        return f"""      @keyframes {name} {{
        0%, {p0:.3f}% {{ opacity: 0; transform: scale(0.82); }}
        {p1:.3f}% {{ opacity: 0.36; transform: scale(1.08); }}
        {p2:.3f}% {{ opacity: 0.50; transform: scale(1.14); }}
        {p3:.3f}% {{ opacity: 0.30; transform: scale(0.98); }}
        {p4:.3f}%, 100% {{ opacity: 0; transform: scale(0.86); }}
      }}"""
    if kind == "glow":
        return f"""      @keyframes {name} {{
        0%, {p0:.3f}% {{ opacity: 0; }}
        {p1:.3f}% {{ opacity: 0.08; }}
        {p2:.3f}% {{ opacity: 0.15; }}
        {p3:.3f}% {{ opacity: 0.06; }}
        {p4:.3f}%, 100% {{ opacity: 0; }}
      }}"""
    return f"""      @keyframes {name} {{
        0%, {p0:.3f}% {{ opacity: 0; }}
        {p1:.3f}% {{ opacity: 0.28; }}
        {p2:.3f}% {{ opacity: 0.50; }}
        {p3:.3f}% {{ opacity: 0.29; }}
        {p4:.3f}%, 100% {{ opacity: 0; }}
      }}"""


def brief_keyframes() -> str:
    parts = ["      @keyframes briefArrive {", "        0% { stroke-opacity: 0.21; filter: none; }"]
    for hold_end in PASS_ENDS:
        parts.extend(
            [
                f"        {pct(hold_end - 0.04):.3f}% {{ stroke-opacity: 0.31; filter: none; }}",
                f"        {pct(hold_end + 0.03):.3f}% {{ stroke-opacity: 0.50; filter: url(#brief-bloom); }}",
                f"        {pct(hold_end + 0.12):.3f}% {{ stroke-opacity: 0.33; filter: none; }}",
            ]
        )
    parts.append("        100% { stroke-opacity: 0.21; filter: none; }")
    parts.append("      }")
    parts.append("      @keyframes briefDot {")
    parts.append("        0% { opacity: 0.09; }")
    for hold_end in PASS_ENDS:
        parts.extend(
            [
                f"        {pct(hold_end - 0.04):.3f}% {{ opacity: 0.11; }}",
                f"        {pct(hold_end + 0.03):.3f}% {{ opacity: 0.46; }}",
                f"        {pct(hold_end + 0.13):.3f}% {{ opacity: 0.13; }}",
            ]
        )
    parts.append("        100% { opacity: 0.09; }")
    parts.append("      }")
    return "\n".join(parts)


def animation_css(segments: list[Segment], pulse_cells: list[PulseCell]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments):
        blocks.append(keyframes_opacity(f"edgeCore{index}", segment.start, PASS_ENDS[segment.pass_index], "core"))
        blocks.append(keyframes_opacity(f"edgeGlow{index}", segment.start, PASS_ENDS[segment.pass_index], "glow"))
    for index, pulse in enumerate(pulse_cells):
        blocks.append(keyframes_opacity(f"cellPulse{index}", pulse.start, PASS_ENDS[pulse.pass_index], "cell"))
    blocks.append(brief_keyframes())
    return "\n".join(blocks)


def latent_node_markup(cells: dict[str, Cell]) -> str:
    lines = []
    for cell in cells.values():
        if cell.band == "brief":
            continue
        opacity = RINGS[cell.ring or 0]["opacity"]
        radius = 2.6 if cell.ring == 0 else 3
        lines.append(
            f'    <circle class="latent-cell" cx="{round(cell.x)}" cy="{round(cell.y)}" r="{radius}" opacity="{opacity:.2f}"/>'
        )
    return "\n".join(lines)


def active_markup(segments: list[Segment], pulse_cells: list[PulseCell], cells: dict[str, Cell]) -> tuple[str, str, str]:
    glow_lines = []
    core_lines = []
    for index, segment in enumerate(segments):
        a = cells[segment.a]
        b = cells[segment.b]
        glow_width = 8 if segment.primary else 6
        core_width = 2.15 if segment.primary else 1.32
        if segment.terminal:
            core_width += 0.22
        d = path(a, b)
        glow_lines.append(
            f'    <path class="synapse-glow" style="stroke-width:{glow_width};animation-name:edgeGlow{index}" d="{d}"/>'
        )
        core_lines.append(
            f'    <path class="synapse-core" style="stroke-width:{core_width};animation-name:edgeCore{index}" d="{d}"/>'
        )

    cell_lines = []
    for index, pulse in enumerate(pulse_cells):
        cell = cells[pulse.cell_id]
        radius = 4.5 if pulse.anchor else (7.5 if pulse.primary else 6.0)
        cell_lines.append(
            f'    <circle class="active-cell" style="animation-name:cellPulse{index}" cx="{round(cell.x)}" cy="{round(cell.y)}" r="{radius}"/>'
        )
    return "\n".join(glow_lines), "\n".join(core_lines), "\n".join(cell_lines)


def label_markup() -> str:
    labels = [
        ("Episodic Knowledge", 720, 50, "middle"),
        ("Abstract Knowledge", 1064, 410, "start"),
        ("Semantic Knowledge", 720, 792, "middle"),
        ("Procedural Knowledge", 376, 410, "end"),
    ]
    lines = []
    for text, x, y, anchor in labels:
        lines.append(f'    <text class="memory-label" x="{x}" y="{y}" text-anchor="{anchor}">{text}</text>')
    return "\n".join(lines)


def render() -> str:
    cells = build_cells()
    edges = build_latent_edges(cells)
    segments, pulse_cells = active_timeline()
    latent_edges = " ".join(path(a, b) for a, b in edges)
    glow_edges, core_edges, active_cells = active_markup(segments, pulse_cells, cells)
    labels = label_markup()
    generated_css = animation_css(segments, pulse_cells)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" aria-hidden="true">
  <!-- Generated by scripts/generate_memory_ontology_constellation.py. -->
  <defs>
    <radialGradient id="field-vignette" cx="50%" cy="50%" r="68%">
      <stop offset="0%" stop-color="#102017" stop-opacity="0.22"/>
      <stop offset="52%" stop-color="#0b0b0c" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#0b0b0c" stop-opacity="0"/>
    </radialGradient>
    <filter id="synapse-glow" x="-80%" y="-220%" width="260%" height="540%">
      <feGaussianBlur stdDeviation="11"/>
    </filter>
    <filter id="cell-glow" x="-180%" y="-180%" width="460%" height="460%">
      <feGaussianBlur stdDeviation="9" result="blur"/>
      <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0.20 0 0 0 0 0.90 0 0 0 0 0.55 0 0 0 0.36 0"/>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="brief-bloom" x="-70%" y="-105%" width="240%" height="310%">
      <feGaussianBlur stdDeviation="13" result="blur"/>
      <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0.20 0 0 0 0 0.90 0 0 0 0 0.55 0 0 0 0.35 0"/>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .bg {{ fill: none; }}
      .latent-edge {{
        fill: none;
        stroke: {MUTED};
        stroke-width: 1;
        stroke-opacity: 0.048;
        stroke-linecap: butt;
        stroke-linejoin: miter;
      }}
      .latent-cell {{ fill: #3a3a40; }}
      .synapse-glow,
      .synapse-core {{
        fill: none;
        stroke: {GREEN};
        stroke-linecap: butt;
        stroke-linejoin: miter;
        opacity: 0;
        animation-duration: {TOTAL_DURATION}s;
        animation-timing-function: ease-in-out;
        animation-iteration-count: infinite;
        animation-fill-mode: both;
      }}
      .synapse-glow {{ filter: url(#synapse-glow); }}
      .active-cell {{
        fill: {GREEN};
        filter: url(#cell-glow);
        opacity: 0;
        transform-box: fill-box;
        transform-origin: center;
        animation-duration: {TOTAL_DURATION}s;
        animation-timing-function: ease-in-out;
        animation-iteration-count: infinite;
        animation-fill-mode: both;
      }}
      .recall-well {{
        fill: #101011;
        opacity: 0.46;
      }}
      .recall-halo {{
        fill: none;
        stroke: {GREEN};
        stroke-width: 1;
        animation: briefArrive {TOTAL_DURATION}s ease-in-out infinite;
      }}
      .brief-dot {{
        fill: {GREEN};
        opacity: 0.09;
        animation: briefDot {TOTAL_DURATION}s ease-in-out infinite both;
      }}
      .memory-label,
      .recall-label {{
        font-family: "Roboto Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        letter-spacing: 0;
        pointer-events: none;
        user-select: none;
      }}
      .memory-label {{
        fill: {MUTED};
        font-size: 28px;
        font-weight: 400;
        opacity: 0.72;
      }}
      .recall-label {{
        fill: #ffffff;
        font-family: "Roboto", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 18px;
        font-weight: 600;
        opacity: 0.92;
      }}
{generated_css}
      @media (prefers-reduced-motion: reduce) {{
        .active-cell,
        .synapse-glow,
        .synapse-core,
        .recall-halo,
        .brief-dot {{
          animation: none;
        }}
        .active-cell,
        .synapse-core {{
          opacity: 1;
        }}
        .synapse-glow {{
          opacity: 0.18;
        }}
        .brief-dot {{
          opacity: 0.35;
        }}
      }}
    </style>
  </defs>

  <rect class="bg" width="{WIDTH}" height="{HEIGHT}"/>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#field-vignette)"/>

  <g id="latent-field" aria-hidden="true">
    <path class="latent-edge" d="{latent_edges}"/>
{latent_node_markup(cells)}
  </g>

  <g id="activation-synapses-glow">
{glow_edges}
  </g>
  <g id="activation-synapses-core">
{core_edges}
  </g>
  <g id="activation-cells">
{active_cells}
  </g>
  <g id="memory-labels">
{labels}
  </g>

  <g id="recall-well" data-center="usable-graph-field">
    <circle class="recall-well" cx="{CENTER[0]}" cy="{CENTER[1]}" r="46"/>
    <circle class="recall-halo" cx="{CENTER[0]}" cy="{CENTER[1]}" r="62"/>
    <circle class="recall-halo" cx="{CENTER[0]}" cy="{CENTER[1]}" r="26"/>
    <circle class="brief-dot" cx="{CENTER[0] - 18}" cy="{CENTER[1]}" r="2.5"/>
    <circle class="brief-dot" cx="{CENTER[0]}" cy="{CENTER[1]}" r="3.5"/>
    <circle class="brief-dot" cx="{CENTER[0] + 18}" cy="{CENTER[1]}" r="2.5"/>
    <text class="recall-label" x="{CENTER[0]}" y="{CENTER[1] + 7}" text-anchor="middle">Recall</text>
  </g>
</svg>
'''


def main() -> None:
    cells = build_cells()
    edges = build_latent_edges(cells)
    segments, pulses = active_timeline()
    OUTPUT.write_text(render(), encoding="utf-8")
    print(
        f"wrote {OUTPUT} with {len([c for c in cells.values() if c.band != 'brief'])} cells, "
        f"{len(edges)} funnel edges, {len(segments)} active synapses, {len(pulses)} active nodes"
    )


if __name__ == "__main__":
    main()
