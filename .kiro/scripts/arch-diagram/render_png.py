#!/usr/bin/env python3
"""Render a generated ``.drawio.xml`` to PNG for visual inspection.

Why this exists
---------------
The generator emits draw.io XML, which normally needs the draw.io desktop app
(Electron/Chromium) to rasterise — heavy and awkward to run headlessly. But we
*control* the XML: it is plain ``mxGraphModel`` with absolute geometry and
house-style colours in each cell's ``style`` string. So we can render a faithful
STRUCTURAL preview directly with Pillow — no browser, no network, fully
deterministic.

The output is not a pixel-perfect copy of the draw.io canvas (it does not draw
the AWS stencil glyphs); it reproduces the *layout that matters for review*:

    * container hierarchy (Cloud / Region / VPC / AZ / subnet) as nested boxes
      with their labels,
    * resource icons as rounded tiles filled with the service's category colour
      and captioned with the service label,
    * every edge as an orthogonal polyline through its real waypoints, with an
      arrowhead, so routing, overlaps, and grouping are all visible.

This is exactly what a reviewer (human or agent) needs to catch overlapping
arrows, bad grouping, or disconnected nodes.

Usage
-----
    python render_png.py --input outputs/foo/foo.drawio.xml
    python render_png.py --input foo.drawio.xml --output /tmp/foo.png --scale 0.5
    python render_png.py --input foo.drawio.xml --page 1   # second page only

By default every page is rendered to ``<stem>.p<N>.png`` next to the input (or
``<stem>.png`` when there is a single page). The resolved PNG path(s) are printed
to stdout, one per line, so the caller can read them back.
"""

from __future__ import annotations

import argparse
import html
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("arch_diagram.render")

# A soft neutral page background and sensible fallbacks for cells whose style
# does not name a colour.
PAGE_BG = (255, 255, 255)
DEFAULT_ICON_FILL = (35, 47, 62)       # AWS "general" slate
DEFAULT_STROKE = (120, 120, 120)
LABEL_COLOR = (20, 20, 20)
EDGE_COLOR = (70, 80, 95)
MARGIN = 40                             # px padding around content in the PNG


def _parse_style(style: str) -> dict:
    """Parse a draw.io ``k=v;`` style string into a dict (bare flags -> '1')."""
    out: dict = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
        else:
            out[part] = "1"
    return out


def _hex_to_rgb(value: Optional[str], fallback):
    """Convert ``#RRGGBB`` to an (r,g,b) tuple; return fallback on miss/none."""
    if not value or value in ("none", "default"):
        return fallback
    v = value.lstrip("#")
    if len(v) == 6:
        try:
            return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return fallback
    return fallback


def _strip_html(value: Optional[str]) -> str:
    """Reduce an HTML label to readable plain text."""
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", " ", value)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _load_font(size: int):
    """Best-effort TrueType font with a bitmap fallback."""
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


class _Cell:
    """A flattened cell with absolute geometry and parsed style."""

    __slots__ = ("id", "parent", "value", "style", "is_vertex", "is_edge",
                 "source", "target", "x", "y", "w", "h", "waypoints")

    def __init__(self, el: ET.Element):
        self.id = el.get("id")
        self.parent = el.get("parent")
        self.value = el.get("value")
        self.style = _parse_style(el.get("style", ""))
        self.is_vertex = el.get("vertex") == "1"
        self.is_edge = el.get("edge") == "1"
        self.source = el.get("source")
        self.target = el.get("target")
        self.x = self.y = self.w = self.h = 0.0
        self.waypoints: list[tuple[float, float]] = []
        geo = el.find("mxGeometry")
        if geo is not None:
            self.x = float(geo.get("x", 0) or 0)
            self.y = float(geo.get("y", 0) or 0)
            self.w = float(geo.get("width", 0) or 0)
            self.h = float(geo.get("height", 0) or 0)
            arr = geo.find("Array")
            if arr is not None:
                for p in arr.findall("mxPoint"):
                    self.waypoints.append((float(p.get("x", 0) or 0),
                                           float(p.get("y", 0) or 0)))


def _absolutise(cells: dict) -> dict:
    """Return id -> (abs_x, abs_y) for every vertex, summing parent offsets."""
    abs_xy: dict = {}

    def resolve(cid: str):
        if cid in abs_xy:
            return abs_xy[cid]
        cell = cells.get(cid)
        if cell is None or not cell.is_vertex:
            abs_xy[cid] = (0.0, 0.0)
            return abs_xy[cid]
        parent = cell.parent
        if parent in cells and cells[parent].is_vertex:
            px, py = resolve(parent)
        else:
            px, py = 0.0, 0.0
        abs_xy[cid] = (px + cell.x, py + cell.y)
        return abs_xy[cid]

    for cid, cell in cells.items():
        if cell.is_vertex:
            resolve(cid)
    return abs_xy


def _endpoint(cell: _Cell, abs_xy, which: str) -> tuple[float, float]:
    """Absolute point where an edge leaves/enters a vertex, honouring exit/entry."""
    ax, ay = abs_xy.get(cell.id, (cell.x, cell.y))
    fx = cell.style.get(f"{which}X")
    fy = cell.style.get(f"{which}Y")
    fxv = float(fx) if fx is not None else 0.5
    fyv = float(fy) if fy is not None else 0.5
    return (ax + cell.w * fxv, ay + cell.h * fyv)


def _is_container(cell: _Cell) -> bool:
    """Containers are group stencils or plain rectangles (not resource icons)."""
    style = cell.style
    if "resIcon" in style or style.get("shape", "").startswith("mxgraph.aws4.resourceIcon"):
        return False
    if "grIcon" in style or style.get("shape") == "mxgraph.aws4.group":
        return True
    # Plain rectangle used as the outer border / cloud.
    if cell.w > 400 and cell.h > 300 and style.get("fillColor", "none") == "none":
        return True
    return False


def _draw_arrowhead(draw, start, end, color, size=12):
    """Draw a small filled triangle at ``end`` pointing away from ``start``."""
    import math
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    # Base points perpendicular to the direction.
    bx, by = end[0] - ux * size, end[1] - uy * size
    px, py = -uy, ux
    p1 = (bx + px * size * 0.5, by + py * size * 0.5)
    p2 = (bx - px * size * 0.5, by - py * size * 0.5)
    draw.polygon([end, p1, p2], fill=color)


def render_page(diagram_el: ET.Element, out_path: str, scale: float = 0.5) -> str:
    """Render one <diagram> page to a PNG at ``out_path``. Returns the path."""
    root = diagram_el.find("mxGraphModel/root")
    if root is None:
        raise ValueError("diagram has no mxGraphModel/root")

    cells = {}
    for el in root.findall("mxCell"):
        if el.get("id") in (None, "0", "1"):
            continue
        cells[el.get("id")] = _Cell(el)

    abs_xy = _absolutise(cells)

    # Compute content bounds across all vertices.
    xs, ys, xe, ye = [], [], [], []
    for cid, cell in cells.items():
        if cell.is_vertex and cell.w and cell.h:
            ax, ay = abs_xy[cid]
            xs.append(ax); ys.append(ay); xe.append(ax + cell.w); ye.append(ay + cell.h)
    if not xs:
        raise ValueError("no drawable vertices on page")
    min_x, min_y, max_x, max_y = min(xs), min(ys), max(xe), max(ye)

    def tx(x): return int((x - min_x) * scale) + MARGIN
    def ty(y): return int((y - min_y) * scale) + MARGIN

    width = int((max_x - min_x) * scale) + 2 * MARGIN
    height = int((max_y - min_y) * scale) + 2 * MARGIN
    img = Image.new("RGB", (max(width, 1), max(height, 1)), PAGE_BG)
    draw = ImageDraw.Draw(img)

    font_sm = _load_font(max(9, int(13 * scale * 2)))
    font_md = _load_font(max(10, int(16 * scale * 2)))

    # --- Pass 1: containers (largest first so children paint on top) --------
    containers = [c for c in cells.values() if c.is_vertex and _is_container(c)]
    containers.sort(key=lambda c: c.w * c.h, reverse=True)
    for cell in containers:
        ax, ay = abs_xy[cell.id]
        box = [tx(ax), ty(ay), tx(ax + cell.w), ty(ay + cell.h)]
        stroke = _hex_to_rgb(cell.style.get("strokeColor"), DEFAULT_STROKE)
        draw.rectangle(box, outline=stroke, width=2)
        label = _strip_html(cell.value)
        if label:
            draw.text((box[0] + 6, box[1] + 4), label, fill=stroke, font=font_sm)

    # --- Pass 2: resource icons --------------------------------------------
    for cell in cells.values():
        if not cell.is_vertex or _is_container(cell):
            continue
        if cell.style.get("shape") == "image":   # brand logo — skip
            continue
        ax, ay = abs_xy[cell.id]
        box = [tx(ax), ty(ay), tx(ax + cell.w), ty(ay + cell.h)]
        fill = _hex_to_rgb(cell.style.get("fillColor"), DEFAULT_ICON_FILL)
        if cell.style.get("fillColor", "none") == "none":
            # Title/text cells: render as label only.
            label = _strip_html(cell.value)
            if label:
                draw.text((box[0], box[1]), label, fill=LABEL_COLOR, font=font_md)
            continue
        radius = max(4, int(14 * scale))
        draw.rounded_rectangle(box, radius=radius, fill=fill)
        label = _strip_html(cell.value)
        if label:
            # Caption under the tile.
            tx0 = box[0]
            cap_y = box[3] + 2
            draw.text((tx0, cap_y), label, fill=LABEL_COLOR, font=font_sm)

    # --- Pass 3: edges ------------------------------------------------------
    for cell in cells.values():
        if not cell.is_edge:
            continue
        src = cells.get(cell.source)
        tgt = cells.get(cell.target)
        if src is None or tgt is None:
            continue
        start = _endpoint(src, abs_xy, "exit")
        end = _endpoint(tgt, abs_xy, "entry")
        pts = [start] + cell.waypoints + [end]
        screen = [(tx(x), ty(y)) for x, y in pts]
        dashed = cell.style.get("dashed") == "1"
        if len(screen) >= 2:
            if dashed:
                _draw_dashed_path(draw, screen, EDGE_COLOR)
            else:
                draw.line(screen, fill=EDGE_COLOR, width=2, joint="curve")
            _draw_arrowhead(draw, screen[-2], screen[-1], EDGE_COLOR,
                            size=max(6, int(12 * scale * 2)))

    img.save(out_path, "PNG")
    logger.info("rendered %s (%dx%d)", out_path, img.width, img.height)
    return out_path


def _draw_dashed_path(draw, pts, color, dash=8, gap=6):
    """Draw a polyline as dashes (per segment)."""
    import math
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg == 0:
            continue
        ux, uy = (x2 - x1) / seg, (y2 - y1) / seg
        pos = 0.0
        while pos < seg:
            a = (x1 + ux * pos, y1 + uy * pos)
            b = (x1 + ux * min(pos + dash, seg), y1 + uy * min(pos + dash, seg))
            draw.line([a, b], fill=color, width=2)
            pos += dash + gap


def render_file(input_path: str, output: Optional[str] = None,
                page: Optional[int] = None, scale: float = 0.5) -> list[str]:
    """Render all (or one) page(s) of a .drawio.xml file to PNG(s)."""
    tree = ET.parse(input_path)
    mxfile = tree.getroot()
    diagrams = mxfile.findall("diagram")
    if not diagrams:
        raise ValueError(f"{input_path!r} contains no <diagram> pages")

    stem = input_path
    for suffix in (".drawio.xml", ".xml"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    outputs: list[str] = []
    selected = [(page - 1, diagrams[page - 1])] if page else list(enumerate(diagrams))
    single = len(selected) == 1
    for idx, dia in selected:
        if output and single:
            out_path = output
        elif len(diagrams) == 1:
            out_path = f"{stem}.png"
        else:
            out_path = f"{stem}.p{idx + 1}.png"
        outputs.append(render_page(dia, out_path, scale=scale))
    return outputs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a generated .drawio.xml to PNG for visual inspection.")
    parser.add_argument("--input", required=True, help="Path to the .drawio.xml file.")
    parser.add_argument("--output", help="Explicit PNG path (single-page only).")
    parser.add_argument("--page", type=int, help="Render only this 1-based page.")
    parser.add_argument("--scale", type=float, default=0.5,
                        help="Scale factor (default 0.5 keeps large diagrams readable).")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr,
    )

    try:
        paths = render_file(args.input, args.output, args.page, args.scale)
    except (OSError, ValueError, ET.ParseError) as exc:
        logger.error("%s", exc)
        return 2

    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
