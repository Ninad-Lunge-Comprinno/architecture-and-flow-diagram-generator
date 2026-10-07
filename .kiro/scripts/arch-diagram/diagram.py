"""Core draw.io in-memory model and XML emitter.

This module contains the fundamental building blocks for generating draw.io
(.drawio.xml) files:

- **Cell** dataclass — the in-memory representation of an mxCell (vertex or edge).
- **Diagram** class — accumulates cells for a single page and renders them to
  an ElementTree ``<diagram>`` element.
- **build_mxfile** — wraps one or more Diagram pages into a complete ``<mxfile>``.
- **validate** — checks the generated XML against the draw.io validity checklist.
- **overlap_check** — detects icon/container overlaps in a layout tree.
- **render_xml** — serialises the mxfile ElementTree to a pretty XML string.
- **build_flat_diagram** — minimal single-page builder (icons + edges + title block).

Higher-level concerns (spec parsing/validation, architecture-page routing,
flow-page construction) live in separate modules that import from here.
"""

from __future__ import annotations

import base64
import html
import logging
import textwrap
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import shapes
import layout

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("arch_diagram")

# ---------------------------------------------------------------------------
# mxGraphModel page defaults (mirror the example diagrams).
# ---------------------------------------------------------------------------
PAGE_ATTRS = {
    "grid": "1",
    "gridSize": "10",
    "guides": "1",
    "tooltips": "1",
    "connect": "1",
    "arrows": "1",
    "fold": "1",
    "page": "1",
    "pageScale": "1",
    "pageWidth": "850",
    "pageHeight": "1100",
    "math": "0",
    "shadow": "0",
}

ICON_SIZE = 120
EDGE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
    "strokeWidth=4;fontStyle=0;fontSize=14;fontColor=#232F3E;"
    "labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;"
)


# ---------------------------------------------------------------------------
# In-memory cell model
# ---------------------------------------------------------------------------
@dataclass
class Cell:
    """A draw.io mxCell (vertex or edge)."""

    id: str
    parent: str = "1"
    value: str = ""
    style: str = ""
    vertex: bool = False
    edge: bool = False
    # geometry (vertex)
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    # edge endpoints
    source: Optional[str] = None
    target: Optional[str] = None
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    # Shift of the edge label away from draw.io's default path midpoint
    label_offset: Optional[tuple[float, float]] = None


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _label_html(text: str, font_size: int = 18, bold: bool = True) -> str:
    """Build a house-style HTML label as *raw* HTML.

    The returned string contains real HTML tags and real text. It is stored in
    the mxCell ``value`` attribute, where ElementTree performs exactly one
    XML-escaping pass on serialization (``<`` -> ``&lt;`` etc.), matching the
    single-escaped HTML seen in the example diagrams. Callers must therefore
    NOT pre-escape.
    """
    inner = f"<b>{text}</b>" if bold else text
    return f'<font style="font-size: {font_size}px;">{inner}</font>'


def _edge_label_html(text: str, width: int = 22) -> str:
    """Wrap edge labels into short, readable lines with a plain-text backing."""
    lines = textwrap.wrap(text, width=width, break_long_words=True,
                          break_on_hyphens=False) or [""]
    return '<div style="text-align:center;line-height:1.2;">' + "<br>".join(
        html.escape(line) for line in lines
    ) + "</div>"


def title_block_value(meta: dict) -> str:
    """Build the standardized title-block HTML (raw HTML; escaped once by ET)."""
    client_name = meta.get("client_name") or meta.get("project") or "To be filled"
    lines = [
        '<h1 style="text-align:left"><b style="font-size:32px;">'
        f'{client_name}</b></h1>'
    ]
    for field_name in ("version", "date", "creator", "reviewer"):
        val = meta.get(field_name) or "To be filled"
        label = field_name.capitalize()
        lines.append(f'<div style="text-align:left;font-size:20px;">{label}: {val}</div>')
    return "".join(lines)


# ---------------------------------------------------------------------------
# Diagram builder
# ---------------------------------------------------------------------------
class Diagram:
    """Accumulates cells for a single page and renders the XML."""

    def __init__(self, name: str, diagram_id: str):
        self.name = name
        self.diagram_id = diagram_id
        self.cells: list[Cell] = []
        self._counter = 0

    def _next_id(self, prefix: str = "n") -> str:
        self._counter += 1
        return f"{self.diagram_id}-{prefix}{self._counter}"

    # -- element adders ----------------------------------------------------
    def add_title_block(self, meta: dict, x: float = -40, y: float = -260) -> str:
        cell = Cell(
            id=self._next_id("title"),
            value=title_block_value(meta),
            style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;",
            vertex=True,
            x=x,
            y=y,
            width=440,
            height=200,
        )
        self.cells.append(cell)
        return cell.id

    def add_comprinno_mark(self, x: float, y: float) -> str:
        """Embed the supplied Comprinno logo in the page header.

        Degrades gracefully: if the logo asset is missing or unreadable, the
        diagram is still produced (just without the brand mark) and a warning
        is logged rather than aborting generation.
        """
        logo_path = Path(__file__).resolve().parent / "assets" / "comprinno-logo.png"
        try:
            logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        except OSError as exc:
            logger.warning(
                "brand logo unavailable (%s); emitting diagram without it.", exc
            )
            return ""
        cell = Cell(
            id=self._next_id("brand"),
            value="",
            # draw.io image URLs use a comma after the MIME type; a semicolon
            # here is parsed as a style separator and makes the image appear broken.
            style=f"shape=image;aspect=fixed;imageAspect=0;image=data:image/png,{logo_data};",
            vertex=True,
            x=x,
            y=y,
            width=240.9,
            height=50,
        )
        self.cells.append(cell)
        return cell.id

    def add_cluster_mark(self, cluster_id: str, kind: str,
                         label: Optional[str] = None) -> str:
        """Place the AWS ECS/EKS badge at the cluster lane's top-left.

        Only the small badge goes on top: a text row there would collide
        with the first lane icon. The lane name renders through the lane
        container's own bottom label instead.
        """
        service = {"ecs_cluster": "ecs", "eks_cluster": "eks"}.get(kind)
        if not service:
            return ""
        shape = shapes.get_shape("aws", service)
        cell = Cell(
            id=self._next_id("clusterlogo"),
            parent=cluster_id,
            value="",
            style=shape.style(font_size=1, label_width=1),
            vertex=True,
            x=8,
            y=8,
            width=42,
            height=42,
        )
        self.cells.append(cell)
        if label is None:
            return cell.id
        label_cell = Cell(
            id=self._next_id("clusterlabel"),
            parent=cluster_id,
            value=_label_html(label or shapes.get_container(kind).label, font_size=16),
            style="text;html=1;strokeColor=none;fillColor=none;align=left;"
                  "verticalAlign=middle;whiteSpace=wrap;rounded=0;fontStyle=1;",
            vertex=True,
            x=58,
            y=8,
            width=max(40, layout.LANE_W - 70),
            height=42,
        )
        self.cells.append(label_cell)
        return cell.id

    def add_icon(
        self,
        provider: str,
        service: str,
        label: Optional[str] = None,
        x: float = 0,
        y: float = 0,
        parent: str = "1",
        cell_id: Optional[str] = None,
        size: int = ICON_SIZE,
    ) -> str:
        shape = shapes.get_shape(provider, service)
        cid = cell_id or self._next_id("i")
        cell = Cell(
            id=cid,
            parent=parent,
            value=_label_html(label or shape.label, font_size=14),
            style=shape.style(font_size=14),
            vertex=True,
            x=x,
            y=y,
            width=size,
            height=size,
        )
        self.cells.append(cell)
        return cid

    def add_container(
        self,
        kind: str,
        label: Optional[str] = None,
        x: float = 0,
        y: float = 0,
        width: float = 400,
        height: float = 300,
        parent: str = "1",
        cell_id: Optional[str] = None,
    ) -> str:
        container = shapes.get_container(kind)
        cid = cell_id or self._next_id("c")
        cell = Cell(
            id=cid,
            parent=parent,
            value=_label_html(label or container.label),
            style=container.style(),
            vertex=True,
            x=x,
            y=y,
            width=width,
            height=height,
        )
        self.cells.append(cell)
        return cid

    def add_edge(
        self,
        source: str,
        target: str,
        label: str = "",
        style: Optional[str] = None,
        parent: str = "1",
        waypoints: Optional[list[tuple[float, float]]] = None,
        exit_xy: Optional[tuple[float, float]] = None,
        entry_xy: Optional[tuple[float, float]] = None,
        label_offset: Optional[tuple[float, float]] = None,
    ) -> str:
        cid = self._next_id("e")
        full_style = style or EDGE_STYLE
        if exit_xy is not None:
            ex, ey = exit_xy
            full_style += f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
        if entry_xy is not None:
            nx, ny = entry_xy
            full_style += f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
        cell = Cell(
            id=cid,
            parent=parent,
            value=_edge_label_html(label) if label else "",
            style=full_style,
            edge=True,
            source=source,
            target=target,
            waypoints=waypoints or [],
            label_offset=label_offset,
        )
        self.cells.append(cell)
        return cid

    # -- layout-tree emission ---------------------------------------------
    def add_outer_border(self, x: float, y: float, width: float, height: float,
                         margin: float = 40) -> str:
        """Emit an outermost plain rectangle enclosing the diagram content.

        Matches the house style (the example diagrams wrap the canvas in a
        border). Emitted as a plain rectangle on the base layer.
        """
        cid = f"{self.diagram_id}-border"
        cell = Cell(
            id=cid,
            parent="1",
            value="",
            style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#000000;strokeWidth=2;",
            vertex=True,
            x=x - margin,
            y=y - margin,
            width=width + 2 * margin,
            height=height + 2 * margin,
        )
        self.cells.append(cell)
        return cid

    def emit_layout_tree(self, node, parent: str = "1", provider_default: str = "aws") -> None:
        """Walk a layout.Placed tree, emitting containers and icons.

        Container kinds map to shapes.get_container(); "resource" nodes map to
        shapes.get_shape(). Child geometry is already relative to its parent in
        the layout tree, which matches draw.io's parent-relative coordinates.
        """
        if node.kind == "resource":
            self.add_icon(
                provider=node.provider or provider_default,
                service=node.service,
                label=node.label,
                x=node.x,
                y=node.y,
                parent=parent,
                cell_id=node.node_id,
            )
            return
        # container node
        container = shapes.get_container(node.kind)
        cell = Cell(
            id=node.node_id,
            parent=parent,
            value=_label_html(node.label or container.label),
            style=container.style(),
            vertex=True,
            x=node.x,
            y=node.y,
            width=node.width,
            height=node.height,
        )
        self.cells.append(cell)
        for child in node.children:
            self.emit_layout_tree(child, parent=node.node_id, provider_default=provider_default)

    # -- rendering ---------------------------------------------------------
    def to_element(self) -> ET.Element:
        diagram = ET.Element("diagram", {"name": self.name, "id": self.diagram_id})
        model = ET.SubElement(diagram, "mxGraphModel", dict(PAGE_ATTRS))
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        for cell in self.cells:
            self._render_cell(root, cell)
        return diagram

    @staticmethod
    def _render_cell(root: ET.Element, cell: Cell) -> None:
        attrs = {"id": cell.id, "parent": cell.parent}
        if cell.value:
            attrs["value"] = cell.value
        if cell.style:
            attrs["style"] = cell.style
        if cell.vertex:
            attrs["vertex"] = "1"
        if cell.edge:
            attrs["edge"] = "1"
            if cell.source:
                attrs["source"] = cell.source
            if cell.target:
                attrs["target"] = cell.target
        mxcell = ET.SubElement(root, "mxCell", attrs)
        if cell.vertex:
            ET.SubElement(
                mxcell,
                "mxGeometry",
                {
                    "x": _num(cell.x),
                    "y": _num(cell.y),
                    "width": _num(cell.width),
                    "height": _num(cell.height),
                    "as": "geometry",
                },
            )
        elif cell.edge:
            geo = ET.SubElement(mxcell, "mxGeometry", {"relative": "1", "as": "geometry"})
            if cell.waypoints:
                arr = ET.SubElement(geo, "Array", {"as": "points"})
                for wx, wy in cell.waypoints:
                    ET.SubElement(arr, "mxPoint", {"x": _num(wx), "y": _num(wy)})
            if cell.label_offset:
                ET.SubElement(geo, "mxPoint", {
                    "x": _num(cell.label_offset[0]),
                    "y": _num(cell.label_offset[1]),
                    "as": "offset",
                })


# ---------------------------------------------------------------------------
# Numeric formatting helper
# ---------------------------------------------------------------------------

def _num(value: Optional[float]) -> str:
    if value is None:
        return "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ---------------------------------------------------------------------------
# File-level builder + validation
# ---------------------------------------------------------------------------

def build_mxfile(diagrams: list[Diagram]) -> ET.Element:
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net"})
    if len(diagrams) > 1:
        mxfile.set("pages", str(len(diagrams)))
    for d in diagrams:
        mxfile.append(d.to_element())
    return mxfile


class ValidationError(Exception):
    """Raised when generated XML fails the draw.io validity checklist."""


def validate(mxfile: ET.Element) -> None:
    """Validate against the official draw.io AI-generation checklist."""
    diagrams = mxfile.findall("diagram")
    if not diagrams:
        raise ValidationError("mxfile contains no <diagram> pages.")
    seen_diagram_ids: set[str] = set()
    for diagram in diagrams:
        did = diagram.get("id")
        if not did:
            raise ValidationError("A <diagram> is missing its id attribute.")
        if did in seen_diagram_ids:
            raise ValidationError(f"Duplicate diagram id {did!r}.")
        seen_diagram_ids.add(did)

        root = diagram.find("mxGraphModel/root")
        if root is None:
            raise ValidationError(f"Diagram {did!r} has no mxGraphModel/root.")

        cells = root.findall("mxCell")
        ids = [c.get("id") for c in cells]
        # structural cells
        if "0" not in ids or "1" not in ids:
            raise ValidationError(f"Diagram {did!r} missing structural cells id=0/id=1.")
        # unique ids
        if len(ids) != len(set(ids)):
            raise ValidationError(f"Diagram {did!r} has duplicate cell ids.")
        id_set = set(ids)
        for c in cells:
            cid = c.get("id")
            if cid == "0":
                continue
            parent = c.get("parent")
            if parent is None or parent not in id_set:
                raise ValidationError(
                    f"Cell {cid!r} in diagram {did!r} has invalid parent {parent!r}."
                )
            is_vertex = c.get("vertex") == "1"
            is_edge = c.get("edge") == "1"
            if is_vertex and is_edge:
                raise ValidationError(f"Cell {cid!r} is both vertex and edge.")
            if is_edge:
                for endpoint in ("source", "target"):
                    ref = c.get(endpoint)
                    if ref is not None and ref not in id_set:
                        raise ValidationError(
                            f"Edge {cid!r} {endpoint} {ref!r} references a missing cell."
                        )


def overlap_check(lo) -> list[str]:
    """Detect icon/container overlaps using the layout's abs_boxes.

    Returns a list of human-readable warning strings. Empty list = no overlaps.
    Two boxes overlap when their rectangles intersect. We check:
      - resource icon vs resource icon (siblings in the same parent container)
      - container vs container (sibling containers at the same nesting level)
    Compute-group lanes intentionally overlap AZ rows — these are excluded.
    Edge routing boxes are not checked (edges have no geometry box).
    """
    if lo is None or not hasattr(lo, "abs_boxes") or not hasattr(lo, "nodes"):
        return []

    boxes = lo.abs_boxes  # id -> (abs_x, abs_y, w, h)
    # Build parent map from nodes
    parent_of = {n.node_id: n.parent for n in lo.nodes}
    kind_of = {n.node_id: n.kind for n in lo.nodes}

    # Intentional overlaps: compute-group lanes over AZ rows — skip these pairs.
    lane_kinds = {"asg", "ecs_cluster", "eks_cluster", "cluster"}
    az_kinds = {"az", "public_subnet", "app_subnet", "db_subnet"}

    warnings: list[str] = []

    ids = list(boxes.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a_id, b_id = ids[i], ids[j]
            # Only check elements sharing the same parent (siblings)
            if parent_of.get(a_id) != parent_of.get(b_id):
                continue
            a_kind = kind_of.get(a_id, "")
            b_kind = kind_of.get(b_id, "")
            # Skip intentional lane-over-AZ overlaps
            if (a_kind in lane_kinds and b_kind in az_kinds) or \
               (b_kind in lane_kinds and a_kind in az_kinds):
                continue
            # Skip lane vs lane (side-by-side; may share edges of bounding box)
            if a_kind in lane_kinds and b_kind in lane_kinds:
                continue
            ax, ay, aw, ah = boxes[a_id]
            bx, by, bw, bh = boxes[b_id]
            # Check rectangle intersection (with 2px tolerance)
            tol = 2
            if ax + aw - tol > bx and bx + bw - tol > ax and \
               ay + ah - tol > by and by + bh - tol > ay:
                overlap_w = min(ax + aw, bx + bw) - max(ax, bx)
                overlap_h = min(ay + ah, by + bh) - max(ay, by)
                warnings.append(
                    f"OVERLAP: {a_id!r} ({a_kind}) and {b_id!r} ({b_kind}) "
                    f"overlap by {int(overlap_w)}×{int(overlap_h)}px "
                    f"at abs ({int(max(ax,bx))},{int(max(ay,by))})"
                )
    return warnings


def render_xml(mxfile: ET.Element) -> str:
    """Serialize to a pretty, uncompressed XML string with declaration."""
    ET.indent(mxfile, space="  ")
    body = ET.tostring(mxfile, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


# ---------------------------------------------------------------------------
# Minimal flat-diagram builder (Task 2). Container layout arrives in Task 3.
# ---------------------------------------------------------------------------

def build_flat_diagram(spec: dict) -> ET.Element:
    """Build a single-page flat diagram (icons + edges + title block)."""
    meta = spec.get("metadata", {})
    provider = spec.get("provider", "aws")
    diagram = Diagram(name=meta.get("project", "Architecture Diagram"), diagram_id="page-1")
    diagram.add_title_block(meta)

    id_map: dict[str, str] = {}
    for res in spec.get("resources", []):
        cid = diagram.add_icon(
            provider=res.get("provider", provider),
            service=res["service"],
            label=res.get("label"),
            x=res.get("x", 0),
            y=res.get("y", 0),
            cell_id=res["id"],
        )
        id_map[res["id"]] = cid

    for edge in spec.get("edges", []):
        diagram.add_edge(
            source=edge["source"],
            target=edge["target"],
            label=edge.get("label", ""),
        )

    mxfile = build_mxfile([diagram])
    validate(mxfile)
    return mxfile
