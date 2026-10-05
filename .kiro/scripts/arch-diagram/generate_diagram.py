"""Architecture Diagram Generator — draw.io (.drawio.xml) emitter.

Turns a structured spec into a valid, uncompressed draw.io file that matches
the firm's house style (AWS 2020 icon set, nested containers, title block).

Task 2 scope: the emission core — mxfile/mxGraphModel/root skeleton, standalone
resource icons, orthogonal edges, and the standardized title block, plus an
internal validation pass following the official draw.io AI checklist.

Layout (containers) and spec parsing/validation are layered on in later tasks.

Usage:
    python generate_diagram.py --input spec.yaml --output my-project.drawio.xml
"""

from __future__ import annotations

import argparse
import base64
import html
from pathlib import Path
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import shapes
import layout

# --------------------------------------------------------------------------
# mxGraphModel page defaults (mirror the example diagrams).
# --------------------------------------------------------------------------
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
EDGE_STYLE = ("edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
              "strokeWidth=4;fontStyle=0;fontSize=14;fontColor=#232F3E;"
              "labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;")

# ---------------------------------------------------------------------------
# Architecture-page routing constants
# All numeric thresholds and offsets used in the arch-page edge-routing logic
# are defined here. Change them in one place; they propagate everywhere.
# ---------------------------------------------------------------------------

# Tall-container threshold: compute-group lanes (ECS/EKS/ASG) have height > this.
TALL_CONTAINER_H = 240

# Port fraction clamp: exit/entry fractions are kept within [PORT_MIN_FX, PORT_MAX_FX]
# so arrows always leave/enter on the icon's declared connection points.
PORT_MIN_FX: float = 0.15
PORT_MAX_FX: float = 0.85
FEXIT_MIN: float = 0.02    # minimum valid exit-y fraction on a lane side
FEXIT_MAX: float = 0.98    # maximum valid exit-y fraction on a lane side
FRAC_MIN:  float = 0.05    # minimum valid port fraction for direct side-entry
FRAC_MAX:  float = 0.95    # maximum valid port fraction for direct side-entry

# Clearances: how many pixels an edge must stay away from container borders
# and icon bounding boxes when computing waypoints.
CORRIDOR_CLEARANCE  = 40   # gap used for VPC corridor and mid_y offsets
ROW_ABOVE_CLEARANCE = 30   # clear-y above the AZ row top for same-row routes
SAME_Y_ABOVE_CLEARANCE = 50  # clear-y above source for same-y fan-out (global row)
STRAIGHT_BUMP_CLEARANCE = 40  # over-y offset when a straight line is blocked

# Sadhaka lane→DB geometry: bus_y offsets above the target icon.
# When target is ABOVE lane centre: bus_y = target.top - BUS_ABOVE_TARGET
# When target is BELOW lane centre: bus_y = target.top - BUS_BELOW_TARGET
BUS_ABOVE_TARGET = 75
BUS_BELOW_TARGET = 160

# Fan-in stagger (Case 2 — multiple region services → same cluster):
# each successive edge gets a corridor 28px higher and a different entry fraction.
FAN_STAGGER_STEP = 28

# Same-row band routing: jog bands within an AZ row for obstacle avoidance.
BAND_OFFSET  = 45   # distance from row edge to the band centre
BAND_STAGGER = 18   # amount band shifts per stagger increment
BAND_JOG_X   = 40   # x offset past source right edge before turning

# Bottom-fan stagger (multiple deploys from the same source to adjacent clusters):
BOTTOM_FAN_FX_STEP   = 0.18  # fraction step per additional fan edge
BOTTOM_FAN_LIFT_STEP = 22    # pixels to lift each successive corridor

# DB drop: how many pixels above a DB icon top to place the final horizontal.
DB_DROP_CLEARANCE = 12

# Same-row exit fraction for the top-right stagger variant.
SAME_ROW_EXIT_FX: float = 0.75


# --------------------------------------------------------------------------
# In-memory cell model
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Diagram builder
# --------------------------------------------------------------------------
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
        """Embed the supplied Comprinno logo in the page header."""
        logo_path = Path(__file__).resolve().parent / "assets" / "comprinno-logo.png"
        logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
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
        """Place the AWS ECS/EKS icon and name together in the cluster header."""
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
            value=_label_html(label or shape.label),
            style=shape.style(),
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


def _num(value: Optional[float]) -> str:
    if value is None:
        return "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# --------------------------------------------------------------------------
# File-level builder + validation
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Minimal flat-diagram builder (Task 2). Container layout arrives in Task 3.
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Full spec handling (Task 4): parsing + validation + architecture pages.
# --------------------------------------------------------------------------
class SpecError(Exception):
    """Raised when the input spec is invalid, with a human-readable message."""


def _import_layout():
    import layout
    return layout


def _collect_arch_ids(page: dict) -> list[tuple[str, dict]]:
    """Collect (id, node) for every element in an architecture page.

    Walks the grid-model sections: global[], entry[], region.services[],
    region.vpc.azs[].{public_subnet,db_subnet}.resources[], and
    region.vpc.compute_groups[] (expanding one node per spanned AZ), plus
    cicd[]. Validates required fields and compute-group kinds.
    """
    out: list[tuple[str, dict]] = []

    def add_resource(res: dict, where: str):
        if "id" not in res:
            raise SpecError(f"A resource in {where} is missing its 'id'.")
        if "service" not in res:
            raise SpecError(f"Resource {res.get('id')!r} in {where} is missing 'service'.")
        out.append((res["id"], res))

    for res in page.get("global", []) or []:
        add_resource(res, "global")
    for res in page.get("edge", []) or []:
        add_resource(res, "edge")

    region = page.get("region", {}) or {}
    for res in region.get("services", []) or []:
        add_resource(res, "region.services")

    vpc = region.get("vpc", {}) or {}
    az_ids = [az["id"] for az in vpc.get("azs", []) or [] if "id" in az]
    for az in vpc.get("azs", []) or []:
        if "id" not in az:
            raise SpecError("An availability zone is missing its 'id'.")
        out.append((az["id"], az))
        for tier in ("public_subnet", "app_subnet", "db_subnet"):
            subnet = az.get(tier)
            if subnet:
                if "id" not in subnet:
                    raise SpecError(f"A {tier} in {az['id']!r} is missing its 'id'.")
                out.append((subnet["id"], subnet))
                for res in subnet.get("resources", []) or []:
                    add_resource(res, f"{tier} {subnet['id']!r}")

    for g in vpc.get("compute_groups", []) or []:
        if "id" not in g:
            raise SpecError("A compute_group is missing its 'id'.")
        kind = g.get("kind", "ecs_cluster")
        if kind not in shapes.CLUSTER_KINDS:
            raise SpecError(
                f"Compute group {g['id']!r} has invalid kind {kind!r}; "
                f"expected one of {', '.join(shapes.CLUSTER_KINDS)}."
            )
        if "node_service" not in g:
            raise SpecError(f"Compute group {g['id']!r} is missing 'node_service'.")
        out.append((g["id"], g))
        for az_id in g.get("azs", az_ids):
            node = {"id": f"{g['id']}-{az_id}", "service": g["node_service"],
                    "provider": g.get("provider")}
            out.append((node["id"], node))

    return out


def _validate_provider(provider: str) -> str:
    provider = str(provider).lower()
    if provider not in shapes.PROVIDERS:
        raise SpecError(
            f"Unknown provider {provider!r}; expected one of {', '.join(shapes.PROVIDERS)}."
        )
    return provider


def _validate_services(elements: list[tuple[str, dict]], default_provider: str) -> None:
    for _id, node in elements:
        service = node.get("service")
        if service is None:
            continue  # containers have no service
        provider = _validate_provider(node.get("provider") or default_provider)
        try:
            shapes.get_shape(provider, service)
            # For AWS: get_shape_dynamic() is called automatically on unknown keys
            # and never raises, so any AWS service key is accepted.
        except shapes.UnknownServiceError as exc:
            # Only Azure/GCP catalog misses raise here; AWS uses dynamic fallback.
            raise SpecError(str(exc)) from exc


def _check_unique_ids(elements: list[tuple[str, dict]], page_name: str) -> set[str]:
    seen: set[str] = set()
    for eid, _node in elements:
        if eid in seen:
            raise SpecError(f"Duplicate id {eid!r} on page {page_name!r}.")
        seen.add(eid)
    return seen


def _check_edges(edges: list[dict], ids: set[str], page_name: str) -> None:
    for edge in edges:
        for endpoint in ("source", "target"):
            if endpoint not in edge:
                raise SpecError(f"An edge on page {page_name!r} is missing '{endpoint}'.")
            if edge[endpoint] not in ids:
                raise SpecError(
                    f"Edge {endpoint} {edge[endpoint]!r} on page {page_name!r} "
                    "references an id that does not exist on the page."
                )


def _architecture_connectivity_warnings(page: dict) -> list[str]:
    """Flag common missing paths and AZ-specific targets on shared ingress."""
    elements = _collect_arch_ids(page)
    pairs = {(edge.get("source"), edge.get("target"))
             for edge in (page.get("edges", []) or [])}
    warnings: list[str] = []

    def ids_for(service: str) -> list[str]:
        return [node_id for node_id, node in elements if node.get("service") == service]

    actors = [node_id for node_id, node in elements
              if node.get("service") in {"user", "users", "mobile_client", "iot_device"}]
    cdns = ids_for("cloudfront")
    wafs = ids_for("waf")
    shields = ids_for("shield")
    igws = ids_for("internet_gateway")
    albs = [node_id for node_id, node in elements
            if node.get("service") in {"application_load_balancer", "network_load_balancer"}]

    adjacency: dict[str, set[str]] = {}
    for source, target in pairs:
        adjacency.setdefault(source, set()).add(target)

    def has_path(source: str, target: str) -> bool:
        pending, visited = [source], set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, set()) - visited)
        return False

    public_entry_services = {
        "cloudfront", "route_53", "api_gateway", "shield", "waf",
        "application_load_balancer", "network_load_balancer",
    }
    public_entries = [node_id for node_id, node in elements
                      if node.get("service") in public_entry_services]
    if actors and public_entries:
        for actor in actors:
            if not any(has_path(actor, entry) for entry in public_entries):
                warnings.append(
                    f"External actor {actor!r} has no path to a public entry service."
                )
    elif actors and (wafs or shields or albs):
        for actor in actors:
            if not any(has_path(actor, target) for target in (shields or wafs or albs)):
                warnings.append(
                    f"External actor {actor!r} has no edge to the ingress path."
                )

    origins = [node_id for node_id, node in elements
               if "origin" in f"{node_id} {node.get('label', '')}".lower()]
    for cdn in cdns:
        if origins and not any((cdn, origin) in pairs for origin in origins):
            warnings.append(
                f"CloudFront {cdn!r} has no edge to a named origin."
            )

    if wafs and igws and albs:
        if (wafs[0], igws[0]) not in pairs:
            warnings.append("Ingress path is missing the WAF → Internet Gateway connection.")
        if (igws[0], albs[0]) not in pairs:
            warnings.append("Ingress path is missing the Internet Gateway → load balancer connection.")

    vpc = (page.get("region", {}) or {}).get("vpc", {}) or {}
    groups = vpc.get("compute_groups", []) or []
    for group in groups:
        group_id = group.get("id")
        if not group_id or group.get("kind") not in {"ecs_cluster", "eks_cluster"}:
            continue
        az_children = {f"{group_id}-{az.get('id')}"
                       for az in (vpc.get("azs", []) or []) if az.get("id")}
        for alb in albs:
            for target in az_children:
                if (alb, target) in pairs:
                    explicit_az_route = any(
                        edge.get("source") == alb and edge.get("target") == target
                        and edge.get("az_specific") is True
                        for edge in (page.get("edges", []) or [])
                    )
                    if explicit_az_route:
                        continue
                    warnings.append(
                        f"Load balancer {alb!r} targets AZ task {target!r}; "
                        f"use shared cluster {group_id!r} unless the route is AZ-specific."
                    )
    return warnings


def _edge_style(edge: dict) -> str:
    style = EDGE_STYLE
    if edge.get("dashed"):
        style += "dashed=1;"
    if edge.get("style"):
        style += str(edge["style"])
        if not style.endswith(";"):
            style += ";"
    return style


def _route_edge(src_box, tgt_box, label_band: float = 50.0,
                az_gaps: Optional[list] = None,
                vpc_corridor_x: Optional[float] = None,
                az_rows: Optional[list] = None,
                region_right_x: Optional[float] = None):
    """Minimal waypoint routing matching the house style.

    Strategy (matching the reference diagrams):
    - Side-to-side (left/right): single mid-x waypoint only when the y levels
      differ significantly (avoids diagonal segments).
    - Same column: no waypoints — draw.io routes straight bottom→top.
    - Entry into a tall container from outside the VPC: use the corridor spine
      as a single waypoint (spine→container left edge at source y).
    - ECR→tall container: bottom exit → left waypoint → top entry.
    - Keep waypoints minimal; trust draw.io's orthogonal router for the rest.
    """
    sx, sy, sw, sh = src_box
    tx, ty, tw, th = tgt_box
    scx, scy = sx + sw / 2, sy + sh / 2
    tcx, tcy = tx + tw / 2, ty + th / 2
    dx = tcx - scx
    dy = tcy - scy

    # 0. Region-service → VPC element: route via the right corridor.
    #    The source is in the region services grid and the target is in the VPC.
    #    Route: exit source right → travel right to region_right_x corridor →
    #    drop to target y → enter target from the right.
    #    This completely avoids crossing the service icon grid.
    if region_right_x is not None and abs(dx) > 100:
        exit_xy, entry_xy = (1.0, 0.5), (1.0, 0.5)
        waypoints = [
            (region_right_x, scy),   # exit right to the region right corridor
            (region_right_x, tcy),   # travel down the corridor to target y
        ]
        seen: list = []
        for p in waypoints:
            if not seen or abs(p[0]-seen[-1][0]) > 1 or abs(p[1]-seen[-1][1]) > 1:
                seen.append(p)
        return exit_xy, entry_xy, seen

    # 1. Source is above a tall container and horizontally offset:
    #    ECR-style — exit bottom, go horizontal at midpoint, enter top.
    if th > TALL_CONTAINER_H and (sy + sh) < ty and abs(dx) > 200 and vpc_corridor_x is None:
        exit_xy, entry_xy = (0.5, 1.0), (0.5, 0.0)
        mid_y = (sy + sh + ty) / 2
        waypoints = [(scx, mid_y), (tcx, mid_y), (tcx, ty)]
        return exit_xy, entry_xy, _dedup(waypoints)

    # 2. Outside-VPC source connecting into VPC via corridor spine:
    #    ALB-style — exit right, single horizontal to container left at source y.
    if vpc_corridor_x is not None and abs(dx) > 40:
        exit_xy = (1.0, 0.5)
        # For tall containers, compute the exact entry Y as a fraction so the
        # arrow enters at the correct height (not the center).
        if th > 240:
            entry_y_frac = round(max(0.0, min(1.0, (scy - ty) / th)), 2)
        else:
            entry_y_frac = 0.5
        entry_xy = (0.0, entry_y_frac)
        waypoints = [(vpc_corridor_x, scy), (tx, scy)]
        return exit_xy, entry_xy, _dedup(waypoints)

    # 3a. Same AZ row + source left of target with a gap > 1 ICON width:
    #   "SQL-style" top-exit route. When the horizontal distance between
    #   source right-edge and target left-edge is > ICON (meaning there is
    #   at least one other icon in between), exit top and route through the
    #   lower part of the AZ row so the line doesn't cross sibling icons.
    #   For icons directly adjacent (gap <= ICON), a simple right-side exit
    #   is clean enough — no crossing occurs.
    ICON_SIZE = 120
    if az_rows and abs(dx) > 30:
        src_row = _row_containing(scy, az_rows)
        tgt_row = _row_containing(tcy, az_rows)
        if src_row is not None and src_row == tgt_row:
            direct_gap = tx - (sx + sw)  # space between src right edge and tgt left edge
            if direct_gap > ICON_SIZE * 2.5:  # gap spans more than 2 icon widths = icon in between
                # Non-adjacent in same row: exit TOP of source, route ABOVE the
                # AZ row, and enter the target from the TOP. This creates a clean
                # inverted-U that goes UP first (above all icons + labels),
                # across, then DOWN into the target — no sibling-icon crossings.
                row_top = src_row[0]     # top of this AZ row in abs coords
                clear_y = row_top - ROW_ABOVE_CLEARANCE   # 30px above the AZ row top (above subnets)
                # exitX=0.75 (top-right of source) shifts this vertical segment
                # right of center so it doesn't overlap ECR->ECS which uses x=0.5
                exit_src_x = sx + sw * SAME_ROW_EXIT_FX
                exit_xy = (SAME_ROW_EXIT_FX, 0.0)   # exit top-right of source
                entry_xy = (0.5, 0.0)    # enter top-center of target
                waypoints = [(exit_src_x, clear_y), (tcx, clear_y)]
                return exit_xy, entry_xy, _dedup(waypoints)
            # Adjacent icons in same row: fall through to simple side-exit.

    # 3b. Column-aligned (same x): straight top/bottom, no waypoints.
    #   For multi-AZ-skip (source and target separated by >1 AZ gap),
    #   use the right-side corridor pattern instead of a straight vertical.
    if abs(dx) < 30:
        n_gaps_crossed = 0
        if az_rows:
            src_row_idx = _row_index(scy, az_rows)
            tgt_row_idx = _row_index(tcy, az_rows)
            if src_row_idx is not None and tgt_row_idx is not None:
                n_gaps_crossed = abs(tgt_row_idx - src_row_idx)
        if n_gaps_crossed >= 2 and az_rows:
            # Multi-AZ skip: route via a right-side corridor.
            # Use a staggered x offset based on the target y so multiple
            # replication edges (to different AZs) don't share the same
            # vertical segment and cause visual overlap.
            base_right_x = max(sx + sw, tx + tw) + 40
            # Stagger: each target gets a unique corridor x based on its y position
            stagger = int(abs(tcy - scy) / 200) * 20  # 20px extra per AZ apart
            right_x = base_right_x + stagger
            exit_xy, entry_xy = (1.0, 0.5), (1.0, 0.5)
            waypoints = [(right_x, scy), (right_x, tcy)]
            return exit_xy, entry_xy, _dedup(waypoints)
        # Simple same-column: no waypoints needed.
        if dy >= 0:
            return (0.5, 1.0), (0.5, 0.0), []
        else:
            return (0.5, 0.0), (0.5, 1.0), []

    # 4. Horizontal preferred: side exits.
    if abs(dx) >= abs(dy):
        if dx >= 0:
            exit_xy, entry_xy = (1.0, 0.5), (0.0, 0.5)
        else:
            exit_xy, entry_xy = (0.0, 0.5), (1.0, 0.5)
        # Only add a waypoint if vertical offset is large enough to cause a
        # diagonal — otherwise let draw.io route directly.
        if abs(dy) > 40:
            mid_x = (sx + sw + tx) / 2
            waypoints = [(mid_x, scy), (mid_x, tcy)]
        else:
            waypoints = []
        return exit_xy, entry_xy, _dedup(waypoints)

    # 5. Vertical preferred: top/bottom exits with gap-corridor waypoints.
    if dy >= 0:
        exit_xy, entry_xy = (0.5, 1.0), (0.5, 0.0)
    else:
        exit_xy, entry_xy = (0.5, 0.0), (0.5, 1.0)

    if az_gaps and abs(dy) > 100:
        mid_y = (scy + tcy) / 2
        best = _nearest_az_gap(mid_y, az_gaps)
        if best:
            gap_y = (best[0] + best[1]) / 2
            waypoints = [(scx, gap_y), (tcx, gap_y)]
        else:
            waypoints = []
    else:
        waypoints = []
    return exit_xy, entry_xy, _dedup(waypoints)


def _route_flow_edge(src_box, tgt_box):
    """Choose directional anchors; Draw.io supplies the orthogonal path."""
    sx, sy, sw, sh = src_box
    tx, ty, tw, th = tgt_box
    source_cy = sy + sh / 2
    target_cy = ty + th / 2
    source_cx = sx + sw / 2
    target_cx = tx + tw / 2
    dx = target_cx - source_cx
    dy = target_cy - source_cy
    source_fraction = max(0.15, min(0.85, 0.5 + dy / 400))
    target_fraction = max(0.15, min(0.85, 0.5 - dy / 400))
    if abs(dx) >= abs(dy):
        exit_xy, entry_xy = ((1.0, source_fraction), (0.0, target_fraction)) if dx >= 0 else ((0.0, source_fraction), (1.0, target_fraction))
    else:
        source_fraction = max(0.15, min(0.85, 0.5 + dx / 400))
        target_fraction = max(0.15, min(0.85, 0.5 - dx / 400))
        exit_xy, entry_xy = ((source_fraction, 1.0), (target_fraction, 0.0)) if dy >= 0 else ((source_fraction, 0.0), (target_fraction, 1.0))
    return exit_xy, entry_xy, []


# ---------------------------------------------------------------------------
# Flow edge routing
# ---------------------------------------------------------------------------
# A flow page reads left to right, so a well-formed flow is mostly straight
# runs joined by a single bend. The router below keeps that property: a span
# whose two ends line up stays one segment, and every other edge takes a
# channel from the gutter it has to cross. Channels are tried from the gutter
# centre outwards, and one already claimed by another edge is only reused when
# the clean ones run out, so parallel arrows run side by side instead of
# stacking on top of each other.
FLOW_CHANNEL_STEP = 20.0   # pitch between parallel channels inside a gutter
FLOW_MIN_CHANNEL = 16.0    # keep channels this far clear of any box border
FLOW_PORT_MARGIN = 0.06    # keep ports inside this fraction of a box side
# Ports are allocated in 0..1 border fractions, so spacing is expressed in
# fractions too. 0.25 is one anchor step on the icon's declared connection
# points, which is what keeps two arrows off the same attachment point.
FLOW_PORT_STEP = 0.25
# Edge labels are drawn by draw.io at the path midpoint, so two arrows whose
# midpoints land in the same spot print their text on top of each other. The
# router shifts a label along its own segment instead, which keeps it on the
# line it belongs to.
FLOW_LABEL_FONT = 14.0
FLOW_LABEL_PAD = 10.0
FLOW_LABEL_LINE = 17.0
FLOW_LABEL_SLIDES = (0.0, 34.0, -34.0, 68.0, -68.0, 102.0, -102.0)


def _flow_label_size(label: str) -> tuple[float, float]:
    """Approximate the drawn size of a wrapped edge label.

    Mirrors :func:`_edge_label_html` so the estimate matches what draw.io wraps.
    """
    lines = textwrap.wrap(label, width=22, break_long_words=True,
                          break_on_hyphens=False) or [""]
    widest = max(len(line) for line in lines)
    return (widest * FLOW_LABEL_FONT * 0.55 + FLOW_LABEL_PAD,
            len(lines) * FLOW_LABEL_LINE + 8.0)


def _flow_path_length(path: list) -> float:
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
               for a, b in zip(path, path[1:]))


def _flow_point_at(path: list, distance: float) -> tuple:
    """Point ``distance`` arc-lengths along ``path``."""
    remaining = distance
    for a, b in zip(path, path[1:]):
        step = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if step <= 0:
            continue
        if remaining <= step:
            ratio = remaining / step
            return (a[0] + (b[0] - a[0]) * ratio,
                    a[1] + (b[1] - a[1]) * ratio)
        remaining -= step
    return path[-1]


def _flow_rects_overlap(a: tuple, b: tuple, gap: float = 0.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + gap and bx < ax + aw + gap
            and ay < by + bh + gap and by < ay + ah + gap)


def _flow_label_offsets(edges, boxes, paths) -> dict:
    """Pick a per-edge label nudge that keeps label boxes clear of each other.

    draw.io centres an edge label on the path midpoint, so two arrows that
    share a midpoint region print their text on top of one another. Each label
    slides along its own segment — which keeps it on its own line — until its
    box clears every label already placed and every icon.
    """
    obstacles: list = [tuple(box) for box in boxes.values()]
    offsets: dict = {}
    for index, edge in enumerate(edges):
        path = paths[index]
        if path is None or not edge.get("label"):
            continue
        width, height = _flow_label_size(edge["label"])
        half = width / 2
        length = _flow_path_length(path)
        if length <= 0:
            continue
        middle = length / 2
        centre = _flow_point_at(path, middle)
        chosen = None
        for slide in FLOW_LABEL_SLIDES:
            distance = min(max(middle + slide, 0.0), length)
            spot = _flow_point_at(path, distance)
            delta = (spot[0] - centre[0], spot[1] - centre[1])
            box = (spot[0] - half, spot[1] - height / 2, width, height)
            if any(_flow_rects_overlap(box, other) for other in obstacles):
                continue
            chosen = delta
            break
        if chosen is None:
            chosen = (0.0, 0.0)
            spot = centre
        else:
            spot = (centre[0] + chosen[0], centre[1] + chosen[1])
        offsets[index] = chosen
        obstacles.append((spot[0] - half, spot[1] - height / 2, width, height))
    return offsets
FLOW_BEND_COST = 260.0     # cost of an extra bend, in pixels of length
FLOW_CHANNEL_COST = 150.0  # cost of reusing a channel another edge already took
# An arrow drawn through an icon is worse than two arrows meeting at a point, so
# it outweighs several crossings and is never traded away for them.
FLOW_ICON_COST = 60000.0
FLOW_CROSS_COST = 6000.0   # cost of crossing or overlapping another arrow
FLOW_DETOUR_OFFSETS = (44.0, 74.0, 104.0)  # heights tried for a blocked span
FLOW_BAND_REACH = 260.0    # how far a blocked span may look for a clear row
# Free vertical band the flow layout leaves between stacked rows, on top of a
# node's label. It has to exceed the padded routing obstacle on both sides or
# a vertical run has nowhere to cross.
FLOW_ROW_GUTTER = 110.0


def _flow_obstacle(box) -> tuple:
    """Routing obstacle for a flow node: the icon plus its label band, padded."""
    x, y, w, h = box
    return (x - 10, y - 10, w + 20, h + layout.LABEL_BAND + 20)


def _flow_center(box) -> tuple:
    x, y, w, h = box
    return (x + w / 2, y + h / 2)


def _flow_side_span(box, side: str) -> tuple:
    """The (lo, hi) range a port can slide along on one side of a box."""
    x, y, w, h = box
    return (y, y + h) if side in ("left", "right") else (x, x + w)


# The AWS resourceIcon stencil declares its legal connection points on
# ``points=`` in the style string. Landing an arrow anywhere else makes draw.io
# push the exit off the shape's outline, so ports are snapped to these anchors.
# A side has 5 of them: the two corners, the centre, and two quarter points.
FLOW_PORT_ANCHORS = (0.0, 0.25, 0.5, 0.75, 1.0)
# The two end anchors are the icon's corners, and a corner belongs to two sides
# at once — an arrow leaving the right side there would sit on the same pixel
# as one leaving the bottom side. Ports are therefore allocated from the three
# interior anchors only, which no other side can reach.
FLOW_PORT_CHOICES = (0.25, 0.5, 0.75)


def _flow_snap(value: float) -> float:
    """Snap a 0..1 border position to the nearest declared connection point."""
    return min(FLOW_PORT_ANCHORS, key=lambda anchor: (abs(anchor - value), anchor))


def _flow_port_point(box, side: str, along: float) -> tuple:
    """Absolute point on ``box``'s border at ``along`` on the given side."""
    x, y, w, h = box
    if side == "right":
        return (x + w, along)
    if side == "left":
        return (x, along)
    if side == "bottom":
        return (along, y + h)
    return (along, y)


def _flow_port_fraction(box, side: str, along: float) -> tuple:
    """draw.io exit/entry fractions for a point on a box border.

    The cross-axis fraction is snapped to a declared connection point so the
    arrow attaches to the icon's outline instead of being pulled off it.
    """
    x, y, w, h = box
    if side in ("left", "right"):
        return ((1.0 if side == "right" else 0.0),
                _flow_snap((along - y) / h))
    return (_flow_snap((along - x) / w), (1.0 if side == "bottom" else 0.0))


def _flow_simplify(points: list) -> list:
    """Drop duplicate and colinear waypoints so a path shows only real bends."""
    result: list = []
    for point in points:
        if result and abs(point[0] - result[-1][0]) < 0.01 \
                and abs(point[1] - result[-1][1]) < 0.01:
            continue
        result.append(point)
    index = 1
    while index < len(result) - 1:
        a, b, c = result[index - 1], result[index], result[index + 1]
        if (abs(a[0] - b[0]) < 0.01 and abs(b[0] - c[0]) < 0.01) or \
           (abs(a[1] - b[1]) < 0.01 and abs(b[1] - c[1]) < 0.01):
            del result[index]
            continue
        index += 1
    return result


def _flow_channels(band: tuple, used: set,
                   step: float = FLOW_CHANNEL_STEP) -> list:
    """Candidate offsets inside a gutter band, centre-out and reuse-last.

    A band is the free stretch of a gutter between the icon an edge leaves and
    the icon it enters, so a channel picked from it always clears both ends.
    """
    lo, hi = band
    if hi <= lo:
        return [round(lo, 1)]
    values = [lo + index * step for index in range(int((hi - lo) / step) + 1)]
    if hi - values[-1] > step * 0.4:
        values.append(hi)
    mid = (lo + hi) / 2
    return sorted({round(value, 1) for value in values},
                  key=lambda value: (value in used, abs(value - mid), value))


def _flow_shape(index, edges, boxes, forced: Optional[str] = None) -> str:
    """Pick the routing shape for one edge: ``"h"`` for a side-to-side run,
    ``"v"`` for a top-to-bottom one.

    The house bias prefers ``"h"`` for left-to-right flows so the main lane of
    the page stays one straight horizontal run. ``forced`` overrides that, which
    the rework loop uses to flip an edge whose preferred shape has nowhere to
    cross.

    Threshold: prefer "h" only when the horizontal distance clearly dominates
    (dx >= dy), so diagonally-placed icons (e.g. client above-left of cognito)
    get a "v" routing that exits top/bottom rather than side-to-side.
    """
    if forced:
        return forced
    scx, scy = _flow_center(boxes[edges[index]["source"]])
    tcx, tcy = _flow_center(boxes[edges[index]["target"]])
    dx, dy = tcx - scx, tcy - scy
    if abs(dx) < 1:
        return "v"
    if abs(dy) < 1:
        return "h"
    return "h" if abs(dx) >= abs(dy) else "v"


def _flow_sides(shape: str, dx: float, dy: float) -> tuple:
    """Source and target sides for a shape, facing each other."""
    if shape == "h":
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def _flow_side_size(box, side: str) -> float:
    return _flow_side_span(box, side)[1] - _flow_side_span(box, side)[0]


def _flow_place_ports(desired: list, lo: float, hi: float, step: float,
                      pinned: list) -> dict:
    """Place ports along one box side, keeping room between them.

    ``pinned`` lists the positions that must keep their exact coordinate — an
    end that sits directly opposite its partner needs it to stay a straight
    arrow. Everything else takes the nearest free spot, so a fan-out opens up
    without pushing a straight run out of line.

    Results are snapped to the icon's declared connection points, so two arrows
    that land close together still leave from two distinct anchors.
    """
    def to_fraction(value: float) -> float:
        return _flow_snap((min(hi, max(lo, value)) - lo) / (hi - lo)
                           if hi > lo else 0.5)

    placed: dict = {}
    taken: list = []
    for index in pinned:
        value = to_fraction(desired[index])
        # Two ends can both be pinned to the same spot when several partners
        # line up. Only the first keeps it; the rest step aside, otherwise both
        # arrows leave from one connection point.
        if any(abs(value - other) < step for other in taken):
            value = next((anchor for anchor in FLOW_PORT_CHOICES
                          if all(abs(anchor - other) >= step
                                 for other in taken)), value)
        placed[index] = value
        taken.append(value)
    for index in sorted(set(range(len(desired))) - set(pinned)):
        # Prefer the anchor nearest the wanted spot, otherwise the first free
        # anchor scanning outwards, so a fan-out spreads while a lone arrow
        # still points straight at its partner.
        wanted = to_fraction(desired[index])
        candidates = sorted(FLOW_PORT_CHOICES,
                            key=lambda anchor: (abs(anchor - wanted), anchor))
        free = [anchor for anchor in candidates
                if all(abs(anchor - other) >= step for other in taken)]
        if not free:
            continue
        placed[index] = free[0]
        taken.append(free[0])
    if len(placed) < len(desired):
        # More arrows than anchors on this side: share anchors evenly rather
        # than dropping arrows off the icon altogether.
        slots = sorted(range(len(desired)), key=lambda i: (desired[i], i))
        count = len(slots)
        for position, index in enumerate(slots):
            placed[index] = FLOW_PORT_CHOICES[
                min(len(FLOW_PORT_CHOICES) - 1,
                    position * len(FLOW_PORT_CHOICES) // max(1, count))]
    return placed


def _plan_flow_ports(edges, boxes, order, shapes) -> dict:
    """Choose a side, and a position on that side, for both ends of every edge.

    Ports are allocated per (node, side) so several arrows leaving the same
    border fan out instead of stacking, while an end whose partner sits
    directly opposite stays pinned and keeps a single straight segment.
    """
    slots: dict = {}
    for index in order:
        edge = edges[index]
        s, t = edge.get("source"), edge.get("target")
        if s not in boxes or t not in boxes:
            continue
        sb, tb = boxes[s], boxes[t]
        scx, scy = _flow_center(sb)
        tcx, tcy = _flow_center(tb)
        shape = shapes[index]
        s_side, t_side = _flow_sides(shape, tcx - scx, tcy - scy)
        if shape == "h":
            wants, cross = (tcy, scy), abs(tcy - scy)
        else:
            wants, cross = (tcx, scx), abs(tcx - scx)
        for which, node_id, side, want in (
                ("source", s, s_side, wants[0]),
                ("target", t, t_side, wants[1])):
            slots.setdefault((node_id, side), []).append(
                (index, which, want, cross < 1))
    plan: dict = {}
    for (node_id, side), keys in slots.items():
        box = boxes[node_id]
        span = _flow_side_span(box, side)
        size = span[1] - span[0]
        lo, hi = span[0] + size * FLOW_PORT_MARGIN, \
            span[1] - size * FLOW_PORT_MARGIN
        desired = [want for _, _, want, _ in keys]
        pinned = [position for position, key in enumerate(keys) if key[3]]
        fractions = _flow_place_ports(desired, lo, hi, FLOW_PORT_STEP, pinned)
        for position, key in enumerate(keys):
            plan[(key[0], key[1])] = (side, lo + (hi - lo) * fractions[position])
    return plan


def _flow_options(index, edges, boxes, plan, rects, used_channels):
    """Candidate ``(channel, points)`` routes for one edge.

    An aligned pair gets a single segment plus a few over/under detours. Any
    other pair gets a one-bend route through a channel taken from the gutter it
    has to cross, ordered from the gutter centre outwards. When that channel
    would have to cross another arrow, a two-bend variant steps sideways into
    the gutter of a neighbouring row first, so the edge goes around the
    crossing instead of through it.
    """
    edge = edges[index]
    s, t = edge["source"], edge["target"]
    sb, tb = boxes[s], boxes[t]
    s_side, s_along = plan[(index, "source")]
    t_side, t_along = plan[(index, "target")]
    # Snap s_along / t_along to the nearest declared connection-point anchor
    # on their respective box side.  _flow_port_fraction does the same snap
    # when computing exit/entry fractions, so the path endpoint and the
    # draw.io connection-point fraction always agree — eliminating the
    # sub-pixel y-mismatch that caused diagonal attachment at icon borders.
    def _snap_along(box, side, along):
        span = _flow_side_span(box, side)
        lo_s, hi_s = span
        size = hi_s - lo_s
        if size <= 0:
            return along
        frac = _flow_snap((along - lo_s) / size)
        return lo_s + frac * size

    s_along = _snap_along(sb, s_side, s_along)
    t_along = _snap_along(tb, t_side, t_along)
    start = _flow_port_point(sb, s_side, s_along)
    goal = _flow_port_point(tb, t_side, t_along)
    so, to = rects[s], rects[t]
    found: list = []
    if s_side in ("left", "right"):
        if start[0] <= goal[0]:
            lo, hi = so[0] + so[2] + FLOW_MIN_CHANNEL, to[0] - FLOW_MIN_CHANNEL
            near, far = so, to
        else:
            lo, hi = to[0] + to[2] + FLOW_MIN_CHANNEL, so[0] - FLOW_MIN_CHANNEL
            near, far = to, so
        if hi < lo:  # the two icons touch: cross the seam itself
            lo = hi = (lo + hi) / 2
        if abs(start[1] - goal[1]) < 0.01:
            found.append((None, [start, goal]))
            mid_x = (start[0] + goal[0]) / 2
            for offset in FLOW_DETOUR_OFFSETS:
                for level in (start[1] - offset, start[1] + offset):
                    found.append((None, [start, (mid_x, start[1]), (mid_x, level),
                                         (goal[0], level), goal]))
            # A node sitting between two aligned ends blocks the straight shot
            # for good. Step out into a free column, use a free row band, then
            # step back in, so the span goes around the blocker.
            for column in _flow_columns(rects, start[0], goal[0], used_channels):
                for level in _flow_bands(rects, start[1], used_channels):
                    found.append((("y", level),
                                  [start, (column, start[1]), (column, level),
                                   (goal[0], level), goal]))
        else:
            channels = _flow_channels((lo, hi), used_channels)
            for value in channels:
                found.append((("x", value),
                              [start, (value, start[1]), (value, goal[1]), goal]))
            # Escape routes: leave the gutter sideways at once, run along a
            # free row band, then come back in. Two extra bends, but they pass
            # arrows that a straight channel would have to cross.
            for level in _flow_rows(rects, min(start[1], goal[1]),
                                    max(start[1], goal[1]), used_channels):
                found.append((("y", level),
                              [start, (start[0], level), (goal[0], level), goal]))
    else:
        if start[1] <= goal[1]:
            lo, hi = so[1] + so[3] + FLOW_MIN_CHANNEL, to[1] - FLOW_MIN_CHANNEL
        else:
            lo, hi = to[1] + to[3] + FLOW_MIN_CHANNEL, so[1] - FLOW_MIN_CHANNEL
        if hi < lo:
            lo = hi = (lo + hi) / 2
        if abs(start[0] - goal[0]) < 0.01:
            found.append((None, [start, goal]))
            mid_y = (start[1] + goal[1]) / 2
            for offset in FLOW_DETOUR_OFFSETS:
                for column in (start[0] - offset, start[0] + offset):
                    found.append((None, [start, (start[0], mid_y), (column, mid_y),
                                         (column, goal[1]), goal]))
        else:
            channels = _flow_channels((lo, hi), used_channels)
            for value in channels:
                found.append((("y", value),
                              [start, (start[0], value), (goal[0], value), goal]))
            for column in _flow_columns(rects, min(start[0], goal[0]),
                                        max(start[0], goal[0]), used_channels):
                found.append((("x", column),
                              [start, (column, start[1]), (column, goal[1]), goal]))
    return found


def _flow_rows(rects, lo: float, hi: float, used: set,
               step: float = FLOW_CHANNEL_STEP) -> list:
    """Horizontal bands between stacked icons that span the y range ``lo..hi``.

    These are the clear rows an edge can duck into to get around an arrow
    crossing its gutter.
    """
    return _flow_corridors(rects, lo, hi, used, 1, step)


def _flow_bands(rects, around: float, used: set,
                reach: float = FLOW_BAND_REACH,
                step: float = FLOW_CHANNEL_STEP) -> list:
    """Free row bands within ``reach`` of ``around``, used to bypass a blocker.

    A straight span with a node in the middle of it has to leave its own row to
    get past, so the candidate heights come from every clear horizontal band
    near the row rather than a fixed set of offsets that may all be occupied.
    """
    return _flow_corridors(rects, around - reach, around + reach, used, 1, step)


def _flow_columns(rects, lo: float, hi: float, used: set,
                  step: float = FLOW_CHANNEL_STEP) -> list:
    """Vertical corridors between side-by-side icons spanning ``lo..hi``."""
    return _flow_corridors(rects, lo, hi, used, 0, step)


def _flow_corridors(rects, lo: float, hi: float, used: set, axis: int,
                    step: float) -> list:
    """Free offsets along one axis between the icons, for the other axis's
    detours. ``axis`` 0 is a column corridor (a free x), 1 a row band (a free
    y). Only offsets that no icon occupies within the span are returned, so a
    detour never needs to be checked against the source or the target again.
    """
    if hi - lo < 1:
        return []
    blocked: list = []
    for rx, ry, rw, rh in rects.values():
        if axis == 0:
            blocked.append((rx, rx + rw))
        else:
            blocked.append((ry, ry + rh))
    free: list = []
    cursor = lo
    for begin, end in sorted(blocked):
        if end <= cursor or begin >= hi:
            continue
        # An obstacle that starts above the range still blocks from ``cursor``
        # onwards, so the free gap before it is the one already collected.
        if begin - FLOW_MIN_CHANNEL >= cursor:
            free.append((cursor, begin - FLOW_MIN_CHANNEL))
        cursor = max(cursor, end + FLOW_MIN_CHANNEL)
    if hi - FLOW_MIN_CHANNEL >= cursor:
        free.append((cursor, hi - FLOW_MIN_CHANNEL))
    values: list = []
    for begin, end in free:
        if end < begin:
            continue
        count = int((end - begin) / step) + 1
        for index in range(count):
            values.append(begin + index * step)
    mid = (lo + hi) / 2
    return sorted({round(value, 1) for value in values},
                  key=lambda value: (value in used, abs(value - mid), value))


def _flow_crossing_edges(paths, order, clashes) -> set:
    """Edges taking part in a crossing, keeping the longer one of each pair.

    The longer edge of a pair is the one worth re-planning: it has more room to
    step aside than the short hop that both arrows want to make.
    """
    out: set = set()
    for a in range(len(order)):
        for b in range(a + 1, len(order)):
            if clashes(paths[order[a]], paths[order[b]]):
                out.add(order[b])
    return out


def _flow_penalty(points, source, target, others, over_icon, clashes) -> float:
    """Cost of one candidate route: length, bends, and every conflict it makes.

    Routing, the repair pass, and the pass selection all rank candidates with
    this one function. A single scale is what keeps them from disagreeing — a
    repair that lowers the total here is never rejected by the outer loop for
    moving a crossing from one arrow to another.
    """
    cost = sum(abs(a[0] - b[0]) + abs(a[1] - b[1])
               for a, b in zip(points, points[1:]))
    cost += FLOW_BEND_COST * (len(points) - 2)
    cost += FLOW_ICON_COST * int(over_icon(points, source, target))
    cost += FLOW_CROSS_COST * sum(1 for other in others if clashes(points, other))
    return cost


def _flow_conflict_score(paths, usable, edges, over_icon, clashes) -> float:
    """Total conflict cost of a whole set of routed paths."""
    routed = [paths[index] for index in usable]
    total = 0.0
    for position, index in enumerate(usable):
        total += FLOW_ICON_COST * int(
            over_icon(paths[index], edges[index]["source"],
                      edges[index]["target"]))
        total += FLOW_CROSS_COST * sum(
            1 for other in routed[position + 1:] if clashes(paths[index], other))
    return total


def _flow_repair(paths, order, edges, boxes, plan, rects, over_icon, clashes,
                 rounds: int = 3):
    """Re-pick the route of every clashing edge against the finished routes.

    Routing one edge at a time lets an early, long edge claim the only clean
    channel and leave a later one with nothing better than a crossing. Here the
    paths are already fixed, so each clashing edge is re-evaluated against all
    the others and only moved when that lowers the conflict cost.
    """
    for _ in range(rounds):
        improved = False
        for position, index in enumerate(order):
            s, t = edges[index]["source"], edges[index]["target"]
            others = [paths[other] for other in order if other != index]
            if not over_icon(paths[index], s, t) and \
                    not any(clashes(paths[index], path) for path in others):
                continue
            current = _flow_penalty(paths[index], s, t, others,
                                    over_icon, clashes)
            best = None
            for _, points in _flow_options(index, edges, boxes, plan, rects, set()):
                points = _flow_simplify(points)
                cost = _flow_penalty(points, s, t, others, over_icon, clashes)
                if best is None or cost < best[0]:
                    best = (cost, points)
            if best is not None and best[0] < current:
                paths[index] = best[1]
                improved = True
        if not improved:
            break
    return paths


def _route_flow_edges(edges, boxes, max_passes: int = 3):
    """Route flow edges through the gutters between nodes.

    Each pass picks a routing shape per edge, allocates ports on the borders
    those shapes need, and then lets every edge choose between the channels of
    its gutter. A pass that still leaves an edge crossing an icon is retried
    with that edge's shape flipped, so a target sitting in an occupied column
    is approached from the side instead. The best pass wins.

    Returns a list aligned with ``edges`` holding
    ``(exit_xy, entry_xy, waypoints)`` for every edge whose endpoints are
    placed, or None for an edge that references an unknown node.
    """
    import routing as shared_routing

    rects = {node_id: _flow_obstacle(box) for node_id, box in boxes.items()}
    usable = [index for index, edge in enumerate(edges)
              if edge.get("source") in boxes and edge.get("target") in boxes]

    def span(index) -> float:
        scx, scy = _flow_center(boxes[edges[index]["source"]])
        tcx, tcy = _flow_center(boxes[edges[index]["target"]])
        return abs(tcx - scx) + abs(tcy - scy)

    def over_icon(points, source, target) -> bool:
        return any(node_id not in (source, target)
                   and shared_routing._polyline_hits_rect(points, rect)
                   for node_id, rect in rects.items())

    def clashes(points, other) -> bool:
        for a, b in zip(points, points[1:]):
            for c, d in zip(other, other[1:]):
                if shared_routing._segments_overlap(a, b, c, d) or \
                        shared_routing._segments_cross(a, b, c, d):
                    return True
        return False

    by_span = sorted(usable, key=lambda i: -span(i))
    forced: dict = {}
    best = None
    for _ in range(max_passes):
        shapes = {index: _flow_shape(index, edges, boxes, forced.get(index))
                  for index in usable}
        plan = _plan_flow_ports(edges, boxes, by_span, shapes)

        def straight(index) -> bool:
            return abs(plan[(index, "source")][1]
                       - plan[(index, "target")][1]) < 0.01

        # Straight spans go down first: they are the backbone every detour has
        # to dodge, so they should not have to move for a longer edge later on.
        order = sorted(usable, key=lambda i: (0 if straight(i) else 1, -span(i)))
        used_channels: set = set()
        routed: list = []
        paths: dict = {}
        for index in order:
            s, t = edges[index]["source"], edges[index]["target"]
            best_edge = None
            for channel, points in _flow_options(
                    index, edges, boxes, plan, rects, used_channels):
                points = _flow_simplify(points)
                cost = _flow_penalty(points, s, t, routed, over_icon, clashes)
                if channel is not None and channel[1] in used_channels:
                    cost += FLOW_CHANNEL_COST
                if best_edge is None or cost < best_edge[0]:
                    best_edge = (cost, channel, points)
            _, channel, points = best_edge
            if channel is not None:
                used_channels.add(channel[1])
            routed.append(points)
            paths[index] = points

        # Repair first: it can clear crossings that another pass would only
        # shuffle around, and it runs against the same cost the passes use.
        paths = _flow_repair(paths, order, edges, boxes, plan, rects,
                             over_icon, clashes)
        score = _flow_conflict_score(paths, usable, edges, over_icon, clashes)
        if best is None or score < best[0]:
            best = (score, plan, paths, shapes)
        if score == 0:
            break
        # Edges still in conflict are candidates for a shape flip: an arrow that
        # has to cross another one on this axis may clear it on the other. Only
        # the longer edge of a crossing pair is flipped, so short backbone runs
        # stay put.
        blocked = {index for index in usable
                   if over_icon(paths[index], edges[index]["source"],
                                edges[index]["target"])}
        stuck = set(blocked) | _flow_crossing_edges(paths, order, clashes)
        progressed = False
        for index in sorted(stuck, key=lambda i: -span(i)):
            if forced.get(index) != shapes[index]:
                forced[index] = "v" if shapes[index] == "h" else "h"
                progressed = True
        if not progressed:
            break

    _, plan, paths, _ = best
    label_offsets = _flow_label_offsets(edges, boxes, paths)
    result: list = [None] * len(edges)
    for index in usable:
        sb, tb = boxes[edges[index]["source"]], boxes[edges[index]["target"]]
        s_side, s_along = plan[(index, "source")]
        t_side, t_along = plan[(index, "target")]
        # Snap to the nearest icon anchor so exit/entry fractions exactly
        # match the first/last path segment — preventing diagonal attachment.
        def _snap_along(box, side, along):
            lo_s, hi_s = _flow_side_span(box, side)
            size = hi_s - lo_s
            if size <= 0:
                return along
            frac = _flow_snap((along - lo_s) / size)
            return lo_s + frac * size
        s_along = _snap_along(sb, s_side, s_along)
        t_along = _snap_along(tb, t_side, t_along)
        points = paths[index]
        result[index] = (_flow_port_fraction(sb, s_side, s_along),
                         _flow_port_fraction(tb, t_side, t_along),
                         points[1:-1],
                         label_offsets.get(index))

    routed = [paths[index] for index in usable]
    icon_hits = sum(1 for index in usable
                    if over_icon(paths[index], edges[index]["source"],
                                 edges[index]["target"]))
    edge_hits = sum(1 for a in range(len(routed)) for b in range(a + 1, len(routed))
                    if clashes(routed[a], routed[b]))
    if icon_hits or edge_hits:
        print(f"  ⚠  FLOW ROUTING: {len(routed)} edges routed with "
              f"{icon_hits} icon and {edge_hits} edge crossings",
              flush=True)
    else:
        print(f"  ✓  FLOW ROUTING: {len(routed)} edges routed with no "
              f"icon/edge conflicts", flush=True)
    return result


def _row_containing(y: float, az_rows: list) -> Optional[tuple]:
    """Return the (top, bottom) AZ row that contains y, or None."""
    for row in az_rows:
        if row[0] <= y <= row[1]:
            return row
    return None


def _row_index(y: float, az_rows: list) -> Optional[int]:
    """Return the index of the AZ row containing y, or None."""
    for i, row in enumerate(az_rows):
        if row[0] <= y <= row[1]:
            return i
    return None


def _dedup(pts: list) -> list:
    seen: list = []
    for p in pts:
        if not seen or abs(p[0]-seen[-1][0]) > 1 or abs(p[1]-seen[-1][1]) > 1:
            seen.append(p)
    return seen


def _nearest_az_gap(y: float, gaps: list) -> Optional[tuple]:
    return min(gaps, key=lambda g: abs((g[0]+g[1])/2 - y)) if gaps else None


def _same_row(y1: float, y2: float, az_rows: list):
    """Return the (top, bottom) AZ row containing both y-values, or None."""
    if not az_rows:
        return None
    for row in az_rows:
        if row[0] <= y1 <= row[1] and row[0] <= y2 <= row[1]:
            return row
    return None


def _seg_hits_resource(points: list, boxes: dict, kind_of: dict,
                       src: str, tgt: str, margin: float = 4.0):
    """Return the id of a resource icon crossed by the polyline, or None.

    Used to verify a candidate routed path before committing to it.
    Container boxes are ignored (lines must cross container borders);
    only resource-icon crossings count. Endpoints are excluded.
    """
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        for nid, (bx, by, bw, bh) in boxes.items():
            if nid in (src, tgt) or kind_of.get(nid) != "resource":
                continue
            if abs(x1 - x2) < 1e-6:  # vertical
                if (bx + margin < x1 < bx + bw - margin
                        and max(y1, y2) > by + margin
                        and min(y1, y2) < by + bh - margin):
                    return nid
            elif abs(y1 - y2) < 1e-6:  # horizontal
                if (by + margin < y1 < by + bh - margin
                        and max(x1, x2) > bx + margin
                        and min(x1, x2) < bx + bw - margin):
                    return nid
    return None


# Services that are REGIONAL or GLOBAL and must never be placed inside VPC subnets.
# The engine auto-migrates them to region.services when found in a subnet.
_REGIONAL_ONLY = frozenset({
    "dynamodb", "sqs", "sns", "s3", "s3_glacier", "cloudfront",
    "route_53", "ses", "pinpoint", "eventbridge", "step_functions",
    "athena", "glue", "emr", "quicksight", "lake_formation",
    "bedrock", "sagemaker", "lambda", "api_gateway", "cloudwatch_2",
    "cloudtrail", "config", "systems_manager", "organizations",
    "identity_and_access_management", "single_sign_on", "codepipeline",
    "codebuild", "codedeploy", "codecommit", "kinesis",
    "kinesis_data_streams", "kinesis_data_firehose",
    "kinesis_data_analytics", "redshift", "timestream", "keyspaces",
    "elasticsearch_service", "managed_streaming_for_kafka", "appflow",
    "connect", "mq",
})


def _fix_regional_placement(page: dict) -> None:
    """Mutate the page spec in-place: move regional/global services out of VPC subnets.

    AWS services like DynamoDB, SQS, Kinesis, Athena are regional/serverless —
    they are NOT deployed inside a VPC subnet. When the spec incorrectly places
    them in a subnet (a common authoring mistake), this function silently moves
    them to ``region.services`` before layout and validation run.

    This fixes the ROOT CAUSE at the spec level rather than just warning.
    """
    region_spec = page.get("region", {}) or {}
    existing_ids = {r.get("id") for r in (region_spec.get("services", []) or [])}
    promoted: list[dict] = []

    for az in (region_spec.get("vpc", {}) or {}).get("azs", []) or []:
        for tier in ("public_subnet", "app_subnet", "db_subnet"):
            subnet = az.get(tier)
            if not subnet:
                continue
            resources = subnet.get("resources", []) or []
            keep, move = [], []
            for res in resources:
                if res.get("service", "") in _REGIONAL_ONLY and res.get("id") not in existing_ids:
                    move.append(res)
                    existing_ids.add(res.get("id"))
                else:
                    keep.append(res)
            if move:
                subnet["resources"] = keep
                promoted.extend(move)
                for res in move:
                    print(
                        f"  ℹ  AUTO-FIXED: moved {res.get('id')!r} "
                        f"({res.get('service')!r}) from {tier} of {az.get('id')!r} "
                        f"to region.services (regional service — not VPC-bound)",
                        flush=True,
                    )

    if promoted:
        if "services" not in region_spec or region_spec["services"] is None:
            region_spec["services"] = []
        region_spec["services"].extend(promoted)


def _reorder_services_for_vpc_proximity(page: dict) -> None:
    """Move region services that connect to VPC elements to the end of the list.

    Services like ECR that have "deploy" connections into the VPC should be
    placed in the last row of region services, as close to the VPC as possible.
    This minimises the length and crossing potential of those edges.
    """
    edges = page.get("edges", []) or []
    services = (page.get("region", {}) or {}).get("services", []) or []
    if not services or not edges:
        return

    # Collect all IDs of elements inside the VPC
    vpc_ids: set = set()
    vpc = (page.get("region", {}) or {}).get("vpc", {}) or {}
    for az in vpc.get("azs", []) or []:
        for tier in ("public_subnet", "app_subnet", "db_subnet"):
            subnet = az.get(tier) or {}
            for r in subnet.get("resources", []) or []:
                vpc_ids.add(r.get("id"))
    for g in vpc.get("compute_groups", []) or []:
        vpc_ids.add(g.get("id"))
        for az in (vpc.get("azs", []) or []):
            vpc_ids.add(f"{g.get('id')}-{az.get('id')}")

    # Find region services that connect to VPC elements
    svc_ids = {s["id"] for s in services}
    vpc_connected: set = set()
    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        if src in svc_ids and tgt in vpc_ids:
            vpc_connected.add(src)
        if tgt in svc_ids and src in vpc_ids:
            vpc_connected.add(tgt)

    if not vpc_connected:
        return

    # Reorder: non-connected first, VPC-connected last
    region_spec = page.get("region", {}) or {}
    region_spec["services"] = (
        [s for s in services if s["id"] not in vpc_connected] +
        [s for s in services if s["id"] in vpc_connected]
    )


def _ensure_aws_foundation_services(page: dict, default_provider: str) -> None:
    """Add standard shared AWS services to every AWS architecture page once."""
    if default_provider.lower() != "aws":
        return

    placements = (
        ("identity_and_access_management", "global", "baseline_iam", "IAM"),
        ("s3", "global", "baseline_s3", "S3"),
        ("secrets_manager", "regional", "baseline_secrets_manager", "Secrets Manager"),
        ("cloudwatch_2", "regional", "baseline_cloudwatch", "CloudWatch"),
        ("cloudtrail", "regional", "baseline_cloudtrail", "CloudTrail"),
        ("key_management_service", "regional", "baseline_kms", "KMS"),
    )

    present_services: set[str] = set()
    def visit(value: object) -> None:
        if isinstance(value, dict):
            service = value.get("service")
            if isinstance(service, str):
                present_services.add(service)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(page)

    global_services = page.setdefault("global", [])
    region = page.setdefault("region", {})
    regional_services = region.setdefault("services", [])
    used_ids = {item_id for item_id, _ in _collect_arch_ids(page)}
    for service, scope, base_id, label in placements:
        if service in present_services:
            continue
        target = global_services if scope == "global" else regional_services
        node_id = base_id
        suffix = 2
        while node_id in used_ids:
            node_id = f"{base_id}_{suffix}"
            suffix += 1
        target.append({"id": node_id, "service": service, "label": label})
        used_ids.add(node_id)
        present_services.add(service)


def build_architecture_page(page: dict, default_provider: str, diagram_id: str,
                            meta: Optional[dict] = None,
                            strict_connectivity: bool = False) -> Diagram:
    """Build an architecture page from the grid-model spec."""
    layout = _import_layout()

    # Auto-fix regional services before validation and layout.
    _ensure_aws_foundation_services(page, default_provider)
    _fix_regional_placement(page)
    # Connection-aware placement: order freely-placeable region services so
    # connected pairs (e.g. API Gateway ↔ Lambda) land close together and
    # VPC-connected services sit closest to the VPC.
    import routing as _routing
    _routing.plan_region_service_order(page)

    elements = _collect_arch_ids(page)
    ids = _check_unique_ids(elements, page.get("name", "architecture"))
    _validate_services(elements, default_provider)
    _check_edges(page.get("edges", []), ids, page.get("name", "architecture"))
    connectivity_warnings = _architecture_connectivity_warnings(page)
    for warning in connectivity_warnings:
        print(f"  ⚠  ARCHITECTURE CHECK: {warning}", flush=True)
    if strict_connectivity and connectivity_warnings:
        raise SpecError(
            "Architecture connectivity checks failed:\n  - "
            + "\n  - ".join(connectivity_warnings)
            + "\nResolve or clarify these paths before generating the diagram."
        )

    diagram = Diagram(name=page.get("name", "Architecture Diagram"), diagram_id=diagram_id)

    lo = layout.build(page, default_provider)

    # Run overlap check — report warnings but don't block generation.
    _overlap_warnings: list[str] = overlap_check(lo)
    if _overlap_warnings:
        for w in _overlap_warnings:
            print(f"  ⚠  {w}", flush=True)

    # Title block: position from the layout's __title node (top-left).
    title_node = next((n for n in lo.nodes if n.node_id == "__title"), None)
    brand_x = lo.border_x + 10 + layout.BORDER_LEFT_MARGIN - layout.BORDER_MARGIN
    brand_width = 240.9
    title_x = max(title_node.x if title_node is not None else lo.border_x,
                  brand_x + brand_width + 20)
    if meta is not None and title_node is not None:
        diagram.add_title_block(meta, x=title_x, y=title_node.y)
    elif meta is not None:
        diagram.add_title_block(meta, x=title_x)

    # Outer border enclosing the title block AND the cloud.
    border_right = max(lo.border_x + lo.border_w, title_x + 440 + layout.BORDER_MARGIN)
    diagram.add_outer_border(lo.border_x, lo.border_y,
                             border_right - lo.border_x, lo.border_h, margin=0)
    diagram.add_comprinno_mark(
        x=brand_x,
        y=(title_node.y + 50) if title_node is not None else lo.border_y + 10,
    )

    # Emit every positioned node (skip the synthetic title placeholder).
    for node in lo.nodes:
        if node.node_id == "__title":
            continue
        if node.kind == "resource":
            diagram.add_icon(
                provider=node.provider or default_provider,
                service=node.service,
                label=node.label,
                x=node.x,
                y=node.y,
                parent=node.parent,
                cell_id=node.node_id,
            )
        else:
            container = shapes.get_container(node.kind)
            is_named_cluster = node.kind in ("ecs_cluster", "eks_cluster")
            diagram.cells.append(Cell(
                id=node.node_id,
                parent=node.parent,
                value="" if is_named_cluster else _label_html(node.label or container.label),
                style=container.style(),
                vertex=True,
                x=node.x, y=node.y, width=node.width, height=node.height,
            ))
            if is_named_cluster:
                diagram.add_cluster_mark(node.node_id, node.kind, node.label)

    # ---- Edges: routed LAST, with DETERMINISTIC HOUSE-STYLE rules ----------
    # Uses the inline obstacle-aware routing approach (ported from the reference
    # implementation). Key cases in priority order:
    #   1. Ingress band → VPC/tall-container (bottom exit → top entry)
    #   2. Region service → tall cluster (ECR→ECS deploy: bottom → top)
    #   3. Lane → icon (Sadhaka geometry: buses at AZ-gap centres, top entry)
    #   4. Same-row: straight → upper-band jog → lower-band jog (obstacle-checked)
    #   5. Fallback: _route_edge() with corridor / AZ-gap routing
    # After all edges are routed, routing.find_conflicts() validates the result.
    # House style: label="" on all edges (spec labels are documentation only).
    boxes = lo.abs_boxes
    kind_of = {n.node_id: n.kind for n in lo.nodes}
    svc_of = {n.node_id: n.service for n in lo.nodes}
    _stagger_tracker: dict = {}
    vpc_abs_top = getattr(lo, "vpc_abs_top", lo.abs_boxes.get("vpc", (0, 0, 0, 0))[1])

    # DB services that a compute cluster boundary may connect to (cluster→DB).
    _CLUSTER_KINDS = ("asg", "ecs_cluster", "eks_cluster", "cluster")
    _DB_SVCS = {"rds", "aurora", "elasticache", "memorydb", "documentdb",
                "neptune", "timestream", "keyspaces", "redshift", "dynamodb"}

    # Pre-index cluster→DB edges so shared-source (one cluster → many DBs) and
    # shared-target (many clusters → one DB) bundles can each be spread into
    # distinct lanes. Keyed independently so both fan-outs are separated.
    _all_edges_pre = page.get("edges", []) or []
    clusterdb_by_src: dict = {}   # cluster id → [db ids] (ordered by db x)
    clusterdb_by_tgt: dict = {}   # db id → [cluster ids] (ordered by cluster x)
    for _e in _all_edges_pre:
        _s, _t = _e.get("source"), _e.get("target")
        if (kind_of.get(_s) in _CLUSTER_KINDS
                and svc_of.get(_t) in _DB_SVCS
                and _s in boxes and _t in boxes):
            clusterdb_by_src.setdefault(_s, []).append(_t)
            clusterdb_by_tgt.setdefault(_t, []).append(_s)
    for _k, _v in clusterdb_by_src.items():
        _v.sort(key=lambda i: boxes[i][0])
    for _k, _v in clusterdb_by_tgt.items():
        _v.sort(key=lambda i: boxes[i][0])

    # Build icon_ids and meta for the conflict checker.
    icon_ids = {n.node_id for n in lo.nodes
                if n.kind == "resource" and n.node_id in boxes}
    parent_of = {n.node_id: n.parent for n in lo.nodes}

    def _az_of(nid):
        if "-" in nid:
            tail = nid.rsplit("-", 1)[-1]
            if tail.startswith("az"):
                return tail
        cur = nid
        seen: set = set()
        while cur and cur not in seen:
            seen.add(cur)
            if cur.startswith("az") and cur[2:].isdigit():
                return cur
            cur = parent_of.get(cur)
        return None

    meta = {n.node_id: {"service": n.service, "kind": n.kind,
                        "parent": n.parent, "az": _az_of(n.node_id)}
            for n in lo.nodes}

    all_edges = page.get("edges", []) or []
    computed_routes: dict = {}   # (src,tgt) → (exit_xy, entry_xy, waypoints)

    # ---- Pre-compute BFS routes for all non-semantic edges --------------------
    # Cases 1-4 handle edges with intentional visual patterns (ingress→VPC,
    # lane→DB Sadhaka geometry, same-row jog). Everything else — region service
    # connections, global row fan-outs, cross-container general paths — goes
    # through the obstacle-aware BFS router (routing.route_all_edges) which
    # finds the shortest orthogonal path around all icon obstacles.
    #
    # This is the classical approach: discretise the diagram to a 20px grid,
    # mark icon+label boxes as blocked, run BFS/Dijkstra with a turn penalty
    # (shortest path minimising length + direction changes) for each edge,
    # longest-first so long edges claim corridors first and shorter edges fill
    # the remaining channels. Previously-routed edge cells become soft obstacles
    # so subsequent routes spread into separate lanes automatically.
    def _edge_matches_semantic_case(src, tgt, src_box, tgt_box):
        """Return True if the edge will be handled by Cases 0-4 (not BFS)."""
        is_target_tall = tgt_box[3] > TALL_CONTAINER_H
        region_box2 = lo.abs_boxes.get("region", (0, 9e9, 0, 0))
        in_band = src_box[1] < region_box2[1]
        above_vpc = src_box[1] < vpc_abs_top
        tgt_in_vpc2 = tgt_box[1] >= vpc_abs_top
        use_spine2 = (lo.vpc_corridor_x > 0
                      and src_box[0] < lo.vpc_corridor_x
                      and tgt_box[0] > lo.vpc_corridor_x
                      and not in_band)
        src_cx2 = src_box[0] + src_box[2] / 2
        src_cy2 = src_box[1] + src_box[3] / 2
        tgt_cy2 = tgt_box[1] + tgt_box[3] / 2
        # Case 0: same-y straight horizontal (or above-row if blocked) —
        # always handled here, never sent to BFS
        src_cy_c = src_box[1] + src_box[3] / 2
        tgt_cy_c = tgt_box[1] + tgt_box[3] / 2
        if (abs(src_cy_c - tgt_cy_c) < 5
                and tgt_box[0] > src_box[0] + src_box[2] - 5
                and not in_band):
            return True
        # Case 1
        if in_band and (is_target_tall or tgt_in_vpc2) and not use_spine2:
            return True
        # Case 2
        if above_vpc and not in_band and is_target_tall and not use_spine2:
            return True
        # Case 2b (cluster→DB)
        if kind_of.get(src) in _CLUSTER_KINDS and svc_of.get(tgt) in _DB_SVCS:
            return True
        # Case 2c (cluster→region-service above VPC — upward left-corridor route)
        if (kind_of.get(src) in _CLUSTER_KINDS
                and kind_of.get(tgt) == "resource"
                and tgt_box[1] + tgt_box[3] < src_box[1]):
            return True
        # Case 3 (lane→icon) — only when target is not above the source top
        if (kind_of.get(src) in ("asg", "ecs_cluster", "eks_cluster", "cluster")
                and kind_of.get(tgt) == "resource"
                and tgt_box[0] > src_box[0]
                and tgt_box[1] + tgt_box[3] / 2 >= src_box[1]):
            return True
        # Case 4 (same-row)
        src_cy2 = src_box[1] + src_box[3] / 2
        tgt_cy2 = tgt_box[1] + tgt_box[3] / 2
        if (not in_band and tgt_box[0] > src_box[0]
                and _same_row(src_cy2, tgt_cy2, lo.az_rows) is not None):
            return True
        # Spine routing (also semantic)
        if use_spine2:
            return True
        return False

    # Collect edges that need BFS routing.
    bfs_edge_pairs = []
    for edge in all_edges:
        src, tgt = edge["source"], edge["target"]
        if src not in boxes or tgt not in boxes or edge.get("style"):
            continue
        # Skip edges that have explicit spec overrides — BFS computes paths from
        # the default border point, not the override fraction, which would create
        # a mismatch between the exit fraction and the first waypoint.
        if edge.get("source_point") or edge.get("target_point") or edge.get("waypoints"):
            continue
        sb, tb = boxes[src], boxes[tgt]
        if not _edge_matches_semantic_case(src, tgt, sb, tb):
            bfs_edge_pairs.append((src, tgt))

    # Run the BFS router on all non-semantic edges together so they compete
    # for channels globally rather than being routed one-at-a-time.
    bfs_routes: dict = {}
    bfs_endpoints: dict = {}
    if bfs_edge_pairs:
        bx_vals = [b[0] for b in boxes.values()] + [b[0]+b[2] for b in boxes.values()]
        by_vals = [b[1] for b in boxes.values()] + [b[1]+b[3] for b in boxes.values()]
        bounds = (min(bx_vals)-40, min(by_vals)-40, max(bx_vals)+40, max(by_vals)+40)
        bfs_routes, bfs_endpoints, bfs_conflicts = _routing.route_all_edges(
            bfs_edge_pairs, boxes, icon_ids, bounds)
        if bfs_conflicts:
            n_ic = sum(1 for c in bfs_conflicts if c[0] == "edge_icon")
            n_ee = sum(1 for c in bfs_conflicts if c[0] == "edge_edge")
            print(f"  ℹ  BFS ROUTING: {n_ic} residual icon, {n_ee} edge conflicts",
                  flush=True)

    for edge in all_edges:
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None
        if src in boxes and tgt in boxes and not edge.get("style"):
            src_box = boxes[src]
            tgt_box = boxes[tgt]
            src_cx = src_box[0] + src_box[2] / 2
            src_cy = src_box[1] + src_box[3] / 2
            tgt_cx = tgt_box[0] + tgt_box[2] / 2
            tgt_cy = tgt_box[1] + tgt_box[3] / 2
            dx = abs(tgt_cx - src_cx)

            is_target_tall = tgt_box[3] > TALL_CONTAINER_H
            region_box = lo.abs_boxes.get("region", (0, 9e9, 0, 0))
            src_in_ingress_band = src_box[1] < region_box[1]
            src_above_vpc = src_box[1] < vpc_abs_top
            tgt_in_vpc = tgt_box[1] >= vpc_abs_top

            use_spine = (lo.vpc_corridor_x > 0
                         and src_box[0] < lo.vpc_corridor_x
                         and tgt_box[0] > lo.vpc_corridor_x
                         and not src_in_ingress_band)

            use_right_corridor = (
                lo.region_right_x > 0
                and src_above_vpc
                and tgt_in_vpc
                and not use_spine
                and not src_in_ingress_band
                and dx > 100
            )

            # Case 0: Same y-level, source left of target → clean straight horizontal.
            # Covers region-service-to-region-service connections (e.g. apigw→lambda)
            # that share the same row but aren't in an AZ row (so Case 4 misses them).
            # Only used when the straight path is clear and there are no spec overrides
            # (source_point overrides imply the caller wants explicit exit control).
            has_spec_override = bool(edge.get("source_point") or edge.get("target_point")
                                     or edge.get("waypoints"))
            if (not has_spec_override
                    and abs(src_cy - tgt_cy) < 5
                    and tgt_box[0] > src_box[0] + src_box[2] - 5
                    and not src_in_ingress_band):
                cand_straight = [(src_box[0] + src_box[2], src_cy), (tgt_box[0], src_cy)]
                if _seg_hits_resource(cand_straight, boxes, kind_of, src, tgt) is None:
                    # Clear path — simple straight horizontal.
                    exit_xy = (1.0, 0.5)
                    entry_xy = (0.0, 0.5)
                    waypoints = []
                else:
                    # Blocked by an icon in between — route ABOVE the row.
                    # This is cleaner than falling to BFS which struggles in
                    # the tight gap between the region services row and the cloud top.
                    above_y = src_box[1] - SAME_Y_ABOVE_CLEARANCE
                    exit_xy = (0.5, 0.0)   # exit top of source
                    entry_xy = (0.5, 0.0)  # enter top of target
                    waypoints = [(src_cx, above_y), (tgt_cx, above_y)]

            # Case 1: Ingress band → VPC or tall container
            elif src_in_ingress_band and (is_target_tall or tgt_in_vpc) and not use_spine:
                exit_xy = (0.5, 1.0)
                entry_xy = (0.5, 0.0)
                if dx > layout.ICON:
                    mid_y = vpc_abs_top - CORRIDOR_CLEARANCE
                    waypoints = [(src_cx, mid_y), (tgt_cx, mid_y)]
                else:
                    waypoints = []

            # Case 2: Region service → tall cluster (ECR→ECS/EKS deploy).
            # Multiple region services connecting to the same cluster (e.g.
            # api_gateway, cognito, ecr all → eks) would overlap because each
            # source is independent. Stagger keyed per TARGET so successive
            # sources fan out symmetrically across the cluster top border.
            elif (src_above_vpc and not src_in_ingress_band
                  and is_target_tall and not use_spine):
                fan_key = (tgt, "fan_into")
                fan_n = _stagger_tracker.get(fan_key, 0)
                _stagger_tracker[fan_key] = fan_n + 1
                _fan_offsets = [0.0, -0.2, +0.2, -0.35, +0.35]
                fan_offset = _fan_offsets[min(fan_n, len(_fan_offsets)-1)]
                exit_fx = round(min(PORT_MAX_FX, max(PORT_MIN_FX, 0.5 + fan_offset)), 2)
                entry_fx = exit_fx
                exit_px = src_box[0] + src_box[2] * exit_fx
                entry_px = tgt_box[0] + tgt_box[2] * entry_fx
                # Place the corridor ABOVE the VPC boundary so the horizontal
                # segment does not share space with BFS routes that also use
                # the narrow band between the region services row and VPC top.
                # Use a fixed clear band: midway between the source bottom and
                # the VPC top, staggered by 28px per fan index.
                vpc_top_abs = vpc_abs_top
                services_bottom = src_box[1] + src_box[3] + layout.LABEL_BAND
                # Target: corridor well above VPC top
                base_mid_y = (services_bottom + vpc_top_abs) / 2
                mid_y = base_mid_y - fan_n * FAN_STAGGER_STEP
                exit_xy = (exit_fx, 1.0)
                entry_xy = (entry_fx, 0.0)
                waypoints = [(exit_px, mid_y), (entry_px, mid_y)]

            # Case 2b: Compute cluster → data store. Route above the subnet
            # contents, then use the free gap before each target for its drop.
            # This keeps a path to a later store from crossing earlier stores.
            elif (kind_of.get(src) in _CLUSTER_KINDS
                  and svc_of.get(tgt) in _DB_SVCS
                  and tgt_box[0] > src_box[0]):
                sibs_t = clusterdb_by_src.get(src, [tgt])
                ti = sibs_t.index(tgt) if tgt in sibs_t else 0
                src_right = src_box[0] + src_box[2]
                target_row = _same_row(tgt_cy, tgt_cy, lo.az_rows)
                row_top = target_row[0] if target_row else tgt_box[1] - 100
                exit_py = row_top + 20 + 10 * min(ti, 2)
                exit_fy = min(FEXIT_MAX, max(FEXIT_MIN,
                                       (exit_py - src_box[1]) / src_box[3]))

                # Place the drop in the gap between this store and the nearest
                # store before it; the first store uses the lane-to-subnet gap.
                preceding = [
                    boxes[n.node_id]
                    for n in lo.nodes
                    if n.parent == parent_of.get(tgt)
                    and n.kind == "resource"
                    and svc_of.get(n.node_id) in _DB_SVCS
                    and boxes[n.node_id][0] + boxes[n.node_id][2] <= tgt_box[0]
                ]
                if preceding:
                    previous_right = max(b[0] + b[2] for b in preceding)
                    corridor_x = (previous_right + tgt_box[0]) / 2
                else:
                    corridor_x = (src_right + tgt_box[0]) / 2

                drop_x = tgt_cx
                exit_xy = (1.0, round(exit_fy, 3))
                entry_xy = (0.5, 0.0)
                waypoints = [(corridor_x, exit_py),
                             (corridor_x, tgt_box[1] - DB_DROP_CLEARANCE),
                             (drop_x, tgt_box[1] - DB_DROP_CLEARANCE)]

            # Case 3: Lane → icon (Sadhaka geometry).
            # Only applies when target is to the RIGHT of the lane AND is at
            # or below the lane's top edge (same AZ row or DB subnet). Targets
            # that are ABOVE the source box (e.g. a cluster connecting upward
            # to a region service like Bedrock) are excluded — those go to BFS.

            # Case 2c: Cluster → region service above the VPC (e.g. eks→bedrock).
            # Exit from the TOP of the cluster (clear of DB icons at mid-height),
            # go up through the gap between region services and VPC, then across
            # to the target. This avoids the DB subnet icons at mid-cluster height.
            elif (kind_of.get(src) in _CLUSTER_KINDS
                  and kind_of.get(tgt) == "resource"
                  and not tgt_in_vpc
                  and src_box[1] + src_box[3] / 2 > tgt_box[1] + tgt_box[3]):
                # Stagger x slightly so multiple upward edges from adjacent
                # clusters don't share the same vertical.
                up_key = (src, "upward")
                up_n = _stagger_tracker.get(up_key, 0)
                _stagger_tracker[up_key] = up_n + 1
                exit_fx = round(min(PORT_MAX_FX, max(PORT_MIN_FX, SAME_ROW_EXIT_FX - up_n * 0.15)), 2)
                exit_px = src_box[0] + src_box[2] * exit_fx
                # Use a corridor JUST BELOW the region services icons
                # (svc_row_bottom = region.y + REGION_SERVICES_Y + ICON + LABEL_BAND).
                # The midpoint of the gap often falls inside icon bounding boxes.
                # Placing the corridor 10px below icon+label bottom clears all icons.
                region_box3 = lo.abs_boxes.get("region", (0, 0, 0, 0))
                svc_row_bottom = (region_box3[1] + layout.REGION_SERVICES_Y
                                  + layout.ICON + layout.LABEL_BAND)
                # Route below all icons in the row, above the VPC top.
                gap_centre_y = svc_row_bottom + 10 - up_n * FAN_STAGGER_STEP
                exit_xy = (exit_fx, 0.0)    # exit from TOP of cluster
                entry_xy = (0.5, 1.0)       # enter target from bottom
                waypoints = [
                    (exit_px, gap_centre_y),  # rise to mid-gap corridor
                    (tgt_cx, gap_centre_y),   # cross right to target
                ]

            elif (kind_of.get(src) in ("asg", "ecs_cluster", "eks_cluster", "cluster")
                    and kind_of.get(tgt) == "resource"
                    and tgt_box[0] > src_box[0]
                    and tgt_box[1] + tgt_box[3] / 2 >= src_box[1]):  # target not above src top
                src_right = src_box[0] + src_box[2]
                cand = None
                if abs(tgt_cy - src_cy) > 10:
                    bus_y = tgt_box[1] - BUS_ABOVE_TARGET if tgt_cy < src_cy else tgt_box[1] - BUS_BELOW_TARGET
                    fexit = (bus_y - src_box[1]) / src_box[3]
                    # If the target is above the source box top, fexit < 0 and
                    # the guard below would reject it, falling back to a
                    # diagonal. Clamp bus_y to just inside the source box top
                    # so the exit is always valid.
                    if fexit < FEXIT_MIN:
                        bus_y = src_box[1] + src_box[3] * FEXIT_MIN
                        fexit = FEXIT_MIN
                    if FEXIT_MIN <= fexit <= FEXIT_MAX:
                        exit_xy, entry_xy = (1.0, round(fexit, 2)), (0.5, 0.0)
                        waypoints = [(tgt_cx, bus_y)]
                        cand = [(src_right, bus_y), (tgt_cx, bus_y),
                                (tgt_cx, tgt_box[1])]
                else:
                    frac0 = (src_cy - tgt_box[1]) / tgt_box[3]
                    if FRAC_MIN <= frac0 <= FRAC_MAX:
                        exit_xy, entry_xy = (1.0, 0.5), (0.0, round(frac0, 2))
                        waypoints = []
                        cand = [(src_right, src_cy), (tgt_box[0], src_cy)]
                if cand is not None and _seg_hits_resource(
                        cand, boxes, kind_of, src, tgt) is None:
                    pass  # use exit/entry/waypoints set above
                else:
                    exit_xy, entry_xy, waypoints = _route_edge(
                        src_box, tgt_box,
                        label_band=layout.LABEL_BAND,
                        az_gaps=lo.az_gaps,
                        vpc_corridor_x=lo.vpc_corridor_x if use_spine else None,
                        az_rows=lo.az_rows,
                        region_right_x=lo.region_right_x if use_right_corridor else None,
                    )

            # Case 4: Same-row left→right with obstacle avoidance
            elif (not src_in_ingress_band
                    and tgt_box[0] > src_box[0]
                    and _same_row(src_cy, tgt_cy, lo.az_rows) is not None):
                row_top, row_bot = _same_row(src_cy, tgt_cy, lo.az_rows)
                src_right = src_box[0] + src_box[2]
                tgt_left = tgt_box[0]
                n_up = _stagger_tracker.get((src, "bandup"), 0)
                n_lo = _stagger_tracker.get((src, "bandlo"), 0)
                band_up = row_top + BAND_OFFSET - n_up * BAND_STAGGER
                band_lo = row_bot - BAND_OFFSET + n_lo * BAND_STAGGER
                gx = src_right + BAND_JOG_X
                picked = False

                # a. Straight
                frac = (src_cy - tgt_box[1]) / tgt_box[3] if tgt_box[3] else 0.5
                if FRAC_MIN <= frac <= FRAC_MAX:
                    cand = [(src_right, src_cy), (tgt_left, src_cy)]
                    if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                        # Keep the target port at the exact source y. Rounding
                        # this fraction can create a small vertical jog on an
                        # otherwise straight ALB-to-cluster connection.
                        exit_xy, entry_xy = (1.0, 0.5), (0.0, frac)
                        waypoints = []
                        picked = True

                # b. Upper-band jog
                if not picked and row_top + 20 < band_up < src_cy + tgt_box[3]:
                    if is_target_tall:
                        fup = min(FRAC_MAX, max(FRAC_MIN, (band_up - tgt_box[1]) / tgt_box[3]))
                        cand = [(src_right, src_cy), (gx, src_cy), (gx, band_up),
                                (tgt_left, band_up)]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy, entry_xy = (1.0, 0.5), (0.0, round(fup, 2))
                            waypoints = _dedup([(gx, src_cy), (gx, band_up),
                                                (tgt_left, band_up)])
                            _stagger_tracker[(src, "bandup")] = n_up + 1
                            picked = True
                    else:
                        # A compute-task edge that must pass a sibling store
                        # leaves near the task's upper-right corner. This keeps
                        # its short vertical stub clear of the subnet label and
                        # lets the shared horizontal segment pass above icons.
                        task_in_cluster = (
                            kind_of.get(src) == "resource"
                            and kind_of.get(parent_of.get(src)) in _CLUSTER_KINDS
                        )
                        source_x = (src_box[0] + src_box[2] * 0.9
                                    if task_in_cluster else src_cx)
                        cand = [(source_x, src_box[1]), (source_x, band_up),
                                (tgt_cx, band_up), (tgt_cx, tgt_box[1])]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy = (0.9 if task_in_cluster else 0.5, 0.0)
                            entry_xy = (0.5, 0.0)
                            waypoints = _dedup([(source_x, band_up),
                                                (tgt_cx, band_up)])
                            _stagger_tracker[(src, "bandup")] = n_up + 1
                            picked = True

                # c. Lower-band jog
                if not picked and src_cy - tgt_box[3] < band_lo < row_bot - 20:
                    if is_target_tall:
                        flo = min(FRAC_MAX, max(FRAC_MIN, (band_lo - tgt_box[1]) / tgt_box[3]))
                        cand = [(src_right, src_cy), (gx, src_cy), (gx, band_lo),
                                (tgt_left, band_lo)]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy, entry_xy = (1.0, 0.5), (0.0, round(flo, 2))
                            waypoints = _dedup([(gx, src_cy), (gx, band_lo),
                                                (tgt_left, band_lo)])
                            _stagger_tracker[(src, "bandlo")] = n_lo + 1
                            picked = True
                    else:
                        bot = src_box[1] + src_box[3]
                        cand = [(src_cx, bot), (src_cx, band_lo),
                                (tgt_cx, band_lo), (tgt_cx, tgt_box[1] + tgt_box[3])]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy, entry_xy = (0.5, 1.0), (0.5, 1.0)
                            waypoints = _dedup([(src_cx, band_lo), (tgt_cx, band_lo)])
                            _stagger_tracker[(src, "bandlo")] = n_lo + 1
                            picked = True

                if not picked:
                    exit_xy, entry_xy, waypoints = _route_edge(
                        src_box, tgt_box,
                        label_band=layout.LABEL_BAND,
                        az_gaps=lo.az_gaps,
                        vpc_corridor_x=lo.vpc_corridor_x if use_spine else None,
                        az_rows=lo.az_rows,
                        region_right_x=lo.region_right_x if use_right_corridor else None,
                    )

            # Case 5: Fallback — use BFS path if available, otherwise _route_edge.
            # BFS provides an obstacle-aware orthogonal path computed globally
            # (all non-semantic edges routed together, longest-first). For the
            # rare case where BFS finds no path, _route_edge gives a geometric
            # approximation. Same-y icon-crossing detection is kept as a
            # lightweight check before invoking _route_edge.
            else:
                ekey = (src, tgt)
                if ekey in bfs_routes and bfs_routes[ekey]:
                    # BFS path: full absolute waypoints including endpoints.
                    # Strip first/last points (icon border contacts); those are
                    # expressed via exit_xy/entry_xy fractions.
                    path = bfs_routes[ekey]
                    exit_xy, entry_xy = bfs_endpoints[ekey]
                    waypoints = [tuple(p) for p in path[1:-1]] if len(path) > 2 else []
                else:
                    # BFS unavailable — geometric fallback with same-y check.
                    clear_y_above = src_box[1] - SAME_Y_ABOVE_CLEARANCE
                    if abs(src_box[1] - tgt_box[1]) < 5 and tgt_box[0] > src_box[0]:
                        cand_straight = [(src_box[0] + src_box[2], src_cy),
                                         (tgt_box[0], src_cy)]
                        if _seg_hits_resource(cand_straight, boxes, kind_of, src, tgt) is not None:
                            exit_xy = (0.5, 0.0)
                            entry_xy = (0.5, 0.0)
                            waypoints = [(src_cx, clear_y_above), (tgt_cx, clear_y_above)]
                        else:
                            exit_xy, entry_xy, waypoints = _route_edge(
                                src_box, tgt_box,
                                label_band=layout.LABEL_BAND,
                                az_gaps=lo.az_gaps,
                                vpc_corridor_x=lo.vpc_corridor_x if use_spine else None,
                                az_rows=lo.az_rows,
                                region_right_x=lo.region_right_x if use_right_corridor else None,
                            )
                    else:
                        exit_xy, entry_xy, waypoints = _route_edge(
                            src_box, tgt_box,
                            label_band=layout.LABEL_BAND,
                            az_gaps=lo.az_gaps,
                            vpc_corridor_x=lo.vpc_corridor_x if use_spine else None,
                            az_rows=lo.az_rows,
                            region_right_x=lo.region_right_x if use_right_corridor else None,
                        )

            # Stagger top-exit corridors to prevent overlapping arrows.
            if waypoints and exit_xy and exit_xy[1] == 0.0:
                key = (src, round(waypoints[0][1] / 5) * 5)
                n = _stagger_tracker.get(key, 0)
                _stagger_tracker[key] = n + 1
                if n > 0:
                    waypoints = [(p[0], p[1] - n * 20) for p in waypoints]

            # Stagger BOTTOM-exit fan-outs (shared source → multiple tall
            # clusters, e.g. ECR→[ecs,eks] deploy or a source feeding two
            # cluster boundaries). Two such edges share the same source bottom
            # stub and drop-band; offset each edge's exit x + band-y so the
            # vertical stubs and horizontal bands never coincide. General:
            # keyed on the source's bottom side, independent of the diagram.
            if (waypoints and exit_xy and exit_xy[1] == 1.0
                    and kind_of.get(tgt) in _CLUSTER_KINDS):
                bkey = (src, "botfan")
                m = _stagger_tracker.get(bkey, 0)
                _stagger_tracker[bkey] = m + 1
                if m > 0:
                    # shift exit x-fraction and lift the drop-band so this edge
                    # rides its own lane into the target cluster top.
                    new_fx = min(PORT_MAX_FX, max(PORT_MIN_FX, exit_xy[0] + m * BOTTOM_FAN_FX_STEP))
                    exit_xy = (round(new_fx, 3), 1.0)
                    lift = m * BOTTOM_FAN_LIFT_STEP
                    new_exit_px = src_box[0] + src_box[2] * new_fx
                    if waypoints:
                        first_y = waypoints[0][1] - lift
                        waypoints = [(new_exit_px, first_y)] + \
                            [(p[0], p[1] - lift) for p in waypoints[1:]]

            computed_routes[(src, tgt)] = (exit_xy, entry_xy, waypoints)

    # Run conflict check on the computed routes for validation report.
    def _route_pts(src, tgt, exit_xy, entry_xy, waypoints):
        sb, tb = boxes[src], boxes[tgt]
        def _ep(box, fxy):
            return (box[0] + box[2] * (fxy[0] if fxy else 0.5),
                    box[1] + box[3] * (fxy[1] if fxy else 0.5))
        return [_ep(sb, exit_xy)] + list(waypoints or []) + [_ep(tb, entry_xy)]

    icon_boxes = {i: boxes[i] for i in icon_ids}
    route_dict = {}
    endpoint_dict = {}
    for (src, tgt), (ex, en, wps) in computed_routes.items():
        pts = _route_pts(src, tgt, ex, en, wps)
        route_dict[(src, tgt)] = pts
        endpoint_dict[(src, tgt)] = (ex, en)

    conflicts = _routing.find_conflicts(route_dict, icon_boxes)
    if conflicts:
        n_icon = sum(1 for c in conflicts if c[0] == "edge_icon")
        n_edge = sum(1 for c in conflicts if c[0] == "edge_edge")
        print(f"  ⚠  ROUTING CONFLICTS: {n_icon} edge-over-icon, "
              f"{n_edge} edge-over-edge", flush=True)
        for c in conflicts[:12]:
            if c[0] == "edge_icon":
                print(f"       edge {c[1][0]}→{c[1][1]} crosses icon {c[2]!r}",
                      flush=True)
            else:
                print(f"       edge {c[1][0]}→{c[1][1]} overlaps edge "
                      f"{c[2][0]}→{c[2][1]}", flush=True)
    else:
        if computed_routes:
            print(f"  ✓  ROUTING: {len(computed_routes)} edges routed with no "
                  f"icon/edge conflicts", flush=True)

    for edge in all_edges:
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None

        route = computed_routes.get((src, tgt))
        if route:
            exit_xy, entry_xy, waypoints = route

        # Spec overrides always win.
        spec_src_point = edge.get("source_point")
        spec_tgt_point = edge.get("target_point")
        if spec_src_point:
            parts = [float(x) for x in spec_src_point.split(",")]
            old_exit = exit_xy
            exit_xy = (parts[0], parts[1])
            # When the exit x-fraction changes, the first waypoint's x must be
            # updated to the new absolute exit x so the first segment stays
            # orthogonal (no diagonal from icon border to waypoint).
            if waypoints and old_exit and abs(parts[0] - old_exit[0]) > 0.01:
                src_box2 = boxes.get(src)
                if src_box2 is not None:
                    new_exit_abs_x = src_box2[0] + parts[0] * src_box2[2]
                    waypoints = [(new_exit_abs_x, waypoints[0][1])] + list(waypoints[1:])
        if spec_tgt_point:
            parts = [float(x) for x in spec_tgt_point.split(",")]
            entry_xy = (parts[0], parts[1])
        spec_wps = edge.get("waypoints")
        if spec_wps:
            waypoints = [tuple(p) for p in spec_wps]

        diagram.add_edge(
            source=src,
            target=tgt,
            # House style: no text labels on connector lines.
            # Spec labels are documentation only.
            label="",
            style=_edge_style(edge),
            waypoints=waypoints,
            exit_xy=exit_xy,
            entry_xy=entry_xy,
        )
    return diagram


def _flow_layout(nodes: list[dict], edges: list[dict],
                 groups: Optional[list[dict]] = None) -> dict[str, tuple[float, float]]:
    """Lay out a directed flow in left-to-right ranks and scope lanes.

    Connected peers are ordered to reduce crossings. Non-VPC AWS nodes use the
    main left-to-right lane; VPC members use a right-hand lane so the VPC frame
    never encloses unrelated Cloud services. Shared external clients stay on
    the left even when response edges point back to them; terminal external
    destinations sit beyond the Cloud boundary.
    """
    # Keep a readable gutter for labels without stretching simple flows across
    # the page. Rows must clear a node's whole routing obstacle (icon plus its
    # wrapped label, padded) with room to spare, otherwise vertically adjacent
    # icons leave no free band for an edge to cross and every vertical run is
    # forced through a neighbour.
    step_x = ICON_SIZE + 160
    step_y = ICON_SIZE + layout.LABEL_BAND + FLOW_ROW_GUTTER
    pad_x = pad_y = 100
    ids = [node["id"] for node in nodes]
    node_by_id = {node["id"]: node for node in nodes}
    order = {nid: i for i, nid in enumerate(ids)}
    incoming = {nid: [] for nid in ids}
    outgoing = {nid: [] for nid in ids}
    actor_services = {"user", "users", "mobile_client", "iot_device"}
    scope = {}
    for nid, node in node_by_id.items():
        declared = node.get("scope")
        if declared is not None and declared not in {"external", "cloud", "vpc"}:
            raise SpecError(f"Node {nid!r} has invalid flow scope {declared!r}.")
        scope[nid] = declared or (
            "external" if node.get("service") in actor_services else "cloud"
        )
    vpc_members = {nid for nid, node_scope in scope.items() if node_scope == "vpc"}
    for group in groups or []:
        if group.get("kind", "vpc") == "vpc":
            vpc_members.update(group.get("members", []) or [])
    for nid in vpc_members:
        if nid in scope:
            scope[nid] = "vpc"

    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src in outgoing and tgt in incoming:
            outgoing[src].append(tgt)
            incoming[tgt].append(src)

    # A client actor can both initiate requests and receive responses/events.
    # Treat its incoming response edges as feedback for ranking so they do not
    # turn an otherwise left-to-right flow into a cycle. Keep the full graph
    # below for branch ordering, placement, and routing.
    rank_incoming = {nid: [] for nid in ids}
    rank_outgoing = {nid: [] for nid in ids}
    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src not in rank_outgoing or tgt not in rank_incoming:
            continue
        if scope[tgt] == "external" and outgoing[tgt]:
            continue
        rank_outgoing[src].append(tgt)
        rank_incoming[tgt].append(src)

    indegree = {nid: len(rank_incoming[nid]) for nid in ids}
    queue = [nid for nid in ids if indegree[nid] == 0]
    external_sources = {nid for nid in queue if scope[nid] == "external"}
    rank = {nid: (1 if external_sources and nid not in external_sources else 0)
            for nid in queue}
    placed = []
    while queue:
        nid = queue.pop(0)
        placed.append(nid)
        for child in rank_outgoing[nid]:
            rank[child] = max(rank.get(child, 0), rank[nid] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    cyclic = [nid for nid in ids if nid not in placed]
    if cyclic:
        final_rank = max((rank[nid] for nid in placed), default=-1) + 1
        rank.update({nid: final_rank for nid in cyclic})

    layers: dict[int, list[str]] = {}
    for nid in ids:
        layers.setdefault(rank.get(nid, 0), []).append(nid)
    layer_ids = sorted(layers)
    order_in_layer = {nid: i for layer in layers.values()
                      for i, nid in enumerate(layer)}

    # Stable barycenter sweeps keep connected branches near each other.
    for _ in range(4):
        for layer_index in layer_ids[1:]:
            layer = layers[layer_index]
            layer.sort(key=lambda nid: (
                sum(order_in_layer.get(p, 0) for p in incoming[nid]) /
                max(1, len(incoming[nid])), order[nid]))
            order_in_layer.update({nid: i for i, nid in enumerate(layer)})
        for layer_index in reversed(layer_ids[:-1]):
            layer = layers[layer_index]
            layer.sort(key=lambda nid: (
                sum(order_in_layer.get(c, 0) for c in outgoing[nid]) /
                max(1, len(outgoing[nid])), order[nid]))
            order_in_layer.update({nid: i for i, nid in enumerate(layer)})

    # Carry each chain's row through the graph, then pack siblings only when
    # they share a rank and scope. Cross-scope edges inherit the parent's row,
    # which keeps a Cloud-to-VPC path aligned instead of stretching it across
    # a separate vertical band.
    #
    # Rows are whole steps apart. Averaging two parents' rows would otherwise
    # place a node half a step from its neighbour, and half a step is less than
    # an icon plus its label — the two obstacles then overlap and an edge has
    # no clear band left to cross between them.
    row_pos: dict[str, float] = {}
    for layer_index in layer_ids:
        layer = layers[layer_index]
        for node_scope in ("external", "cloud", "vpc"):
            members = [nid for nid in layer if scope[nid] == node_scope]
            if not members:
                continue
            desired = {}
            for row, nid in enumerate(members):
                parents = [p for p in incoming[nid] if p in row_pos]
                if parents:
                    parent_row = sum(row_pos[p] for p in parents) / len(parents)
                    # When a VPC producer has parallel outputs, put its Cloud
                    # dependency on a neighboring row. This keeps the VPC frame
                    # external and leaves the main horizontal continuation clear.
                    vpc_parents = [p for p in parents if scope[p] == "vpc"]
                    leaves_vpc = node_scope == "cloud" and bool(vpc_parents)
                    has_sibling_path = any(len(outgoing[p]) > 1 for p in vpc_parents)
                    if leaves_vpc and has_sibling_path:
                        desired[nid] = (parent_row - 2 if parent_row >= 2
                                        else parent_row + 2)
                    else:
                        desired[nid] = parent_row
                else:
                    desired[nid] = float(row)
            occupied_rows: list[int] = []
            for nid in sorted(members, key=lambda item: (desired[item],
                                                         order_in_layer[item])):
                target_row = max(0, int(round(desired[nid])))
                candidates = [target_row]
                for offset in range(1, len(members) + 2):
                    candidates.extend((target_row - offset, target_row + offset))
                row = next(candidate for candidate in sorted(
                    candidates, key=lambda value: (abs(value - target_row), value)
                ) if candidate >= 0 and all(
                    abs(candidate - placed) >= 1 for placed in occupied_rows
                ))
                row_pos[nid] = float(row)
                occupied_rows.append(row)

    cloud_nodes = [nid for nid in ids if scope[nid] == "cloud"]
    vpc_nodes = [nid for nid in ids if scope[nid] == "vpc"]
    cloud_max_rank = max((rank[nid] for nid in cloud_nodes), default=0)
    vpc_min_rank = min((rank[nid] for nid in vpc_nodes), default=0)
    # Keep the complete VPC frame to the right of non-VPC AWS services. This
    # preserves scope without reserving a tall, empty band beneath every flow.
    vpc_rank_offset = max(0, cloud_max_rank + 1 - vpc_min_rank)
    positions: dict[str, tuple[float, float]] = {}
    for nid in cloud_nodes:
        positions[nid] = (pad_x + rank[nid] * step_x,
                          pad_y + row_pos[nid] * step_y)
    for nid in vpc_nodes:
        positions[nid] = (pad_x + (rank[nid] + vpc_rank_offset) * step_x,
                          pad_y + row_pos[nid] * step_y)

    # Shared client actors remain on the left even when response/event edges
    # point back to them. Only terminal external destinations sit beyond AWS.
    external_targets = [nid for nid in ids if scope[nid] == "external"
                        and incoming[nid] and not outgoing[nid]]
    internal_right = max((x + ICON_SIZE for nid, (x, _) in positions.items()
                          if scope[nid] != "external"), default=pad_x + ICON_SIZE)
    target_x = internal_right + step_x - ICON_SIZE
    for nid in ids:
        if scope[nid] != "external":
            continue
        # A client that both receives content and sends telemetry belongs
        # between all adjacent steps, not on top of only its return path.
        neighbors = incoming[nid] + outgoing[nid]
        neighbor_ys = [positions[n][1] for n in neighbors if n in positions]
        y = (sum(neighbor_ys) / len(neighbor_ys)) if neighbor_ys else pad_y
        x = target_x if nid in external_targets else pad_x
        positions[nid] = (x, y)

    return positions


def build_flow_page(page: dict, default_provider: str, diagram_id: str,
                    meta: Optional[dict] = None) -> Diagram:
    """Build a flow page using a layered left-to-right layout.

    Nodes follow topological ranks, with branches stacked in rows and VPC
    members separated from other AWS services. Spec nodes may override layout
    positions with explicit 'x' and 'y' fields.
    """
    nodes = page.get("nodes", [])
    if not nodes:
        raise SpecError(f"Flow page {page.get('name')!r} has no 'nodes'.")

    elements: list[tuple[str, dict]] = []
    for node in nodes:
        if "id" not in node:
            raise SpecError(f"A node on flow page {page.get('name')!r} is missing 'id'.")
        if "service" not in node:
            raise SpecError(f"Node {node.get('id')!r} is missing 'service'.")
        elements.append((node["id"], node))
    ids = _check_unique_ids(elements, page.get("name", "flow"))
    _validate_services(elements, default_provider)
    _check_edges(page.get("edges", []), ids, page.get("name", "flow"))

    diagram = Diagram(name=page.get("name", "Flow Diagram"), diagram_id=diagram_id)

    # Compute left-to-right layered positions (spec x/y overrides if provided).
    auto_pos = _flow_layout(nodes, page.get("edges", []), page.get("groups", []))
    header_y = 280 if meta is not None else 0
    boxes: dict[str, tuple[float, float, float, float]] = {}
    frame_boxes: list[tuple[float, float, float, float]] = []

    for node in nodes:
        nid = node["id"]
        auto_x, auto_y = auto_pos.get(nid, (40, 60))
        x = node.get("x", auto_x)
        y = node.get("y", auto_y + header_y)
        boxes[nid] = (x, y, ICON_SIZE, ICON_SIZE)

    # AWS flow pages use the same cloud boundary as the architecture examples.
    # Source actors stay outside; AWS service nodes sit within the boundary.
    aws_boxes = [boxes[node["id"]] for node in nodes
                 if node.get("provider", default_provider) == "aws"
                 and node.get("scope") != "external"
                 and node.get("service") not in {
                     "user", "users", "mobile_client", "iot_device",
                 }]
    if aws_boxes:
        cloud_left = min(box[0] for box in aws_boxes) - 80
        cloud_top = max(20, min(box[1] for box in aws_boxes) - 120)
        cloud_right = max(box[0] + box[2] for box in aws_boxes) + 80
        cloud_bottom = max(box[1] + box[3] for box in aws_boxes) + layout.LABEL_BAND + 60
        diagram.add_container(
            "cloud", label=page.get("cloud_label", "AWS Cloud"),
            x=cloud_left, y=cloud_top,
            width=cloud_right - cloud_left, height=cloud_bottom - cloud_top,
            cell_id=f"{diagram_id}-cloud",
        )
        frame_boxes.append((cloud_left, cloud_top,
                            cloud_right - cloud_left, cloud_bottom - cloud_top))

    node_ids = {node["id"] for node in nodes}
    for group in page.get("groups", []) or []:
        members = group.get("members", []) or []
        missing = set(members) - node_ids
        if not members or missing:
            raise SpecError(
                f"Flow group {group.get('id')!r} needs valid member node ids; "
                f"unknown: {', '.join(sorted(missing)) or '(no members)'}."
            )
        kind = group.get("kind", "vpc")
        try:
            shapes.get_container(kind)
        except shapes.UnknownContainerError as exc:
            raise SpecError(f"Flow group {group.get('id')!r} has invalid kind {kind!r}.") from exc
        member_boxes = [boxes[nid] for nid in members]
        left = min(box[0] for box in member_boxes) - 55
        top = min(box[1] for box in member_boxes) - 75
        right = max(box[0] + box[2] for box in member_boxes) + 55
        bottom = max(box[1] + box[3] + layout.LABEL_BAND for box in member_boxes) + 45
        diagram.add_container(
            kind, label=group.get("label"), x=left, y=top,
            width=right - left, height=bottom - top,
            cell_id=f"{diagram_id}-{group.get('id', 'group')}",
        )
        frame_boxes.append((left, top, right - left, bottom - top))

    for node in nodes:
        nid = node["id"]
        x, y, _, _ = boxes[nid]
        diagram.add_icon(
            provider=node.get("provider", default_provider),
            service=node["service"],
            label=node.get("label"),
            x=x,
            y=y,
            cell_id=nid,
        )

    # Keep the branded title in the page header, as in the flow examples.
    if meta is not None:
        brand_x, brand_width = 40, 240.9
        diagram.add_comprinno_mark(x=brand_x, y=45)
        diagram.add_title_block(meta, x=brand_x + brand_width + 20, y=0)

    # Outer border enclosing all flow nodes
    if boxes:
        content = list(boxes.values()) + frame_boxes
        bx = 0 if meta is not None else min(b[0] for b in content) - 40
        by = 0 if meta is not None else min(b[1] for b in content) - 40
        right = max([b[0] + b[2] for b in content] + ([780] if meta is not None else []))
        bottom = max(
            max(b[1] + b[3] + layout.LABEL_BAND for b in boxes.values()),
            max((b[1] + b[3] for b in frame_boxes), default=0),
        )
        diagram.add_outer_border(bx, by, right - bx + 40, bottom - by + 40, margin=0)

    flow_routes = _route_flow_edges(page.get("edges", []), boxes)
    for edge_index, edge in enumerate(page.get("edges", [])):
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None
        label_offset = None
        if edge_index < len(flow_routes) and flow_routes[edge_index] is not None:
            exit_xy, entry_xy, waypoints, label_offset = flow_routes[edge_index]
            if edge.get("waypoints"):
                waypoints = [tuple(point) for point in edge["waypoints"]]
            if edge.get("source_point") or edge.get("target_point") \
                    or edge.get("waypoints"):
                # Hand-placed geometry wins, and it no longer matches the route
                # the label offset was measured against.
                label_offset = None
            if edge.get("source_point"):
                exit_xy = tuple(float(value) for value in edge["source_point"].split(","))
            if edge.get("target_point"):
                entry_xy = tuple(float(value) for value in edge["target_point"].split(","))
        solid_edge = dict(edge)
        solid_edge.pop("dashed", None)
        if solid_edge.get("style"):
            style_parts = str(solid_edge["style"]).split(";")
            solid_edge["style"] = ";".join(
                part for part in style_parts
                if part and not part.startswith("dashed=")
            )
        diagram.add_edge(
            source=src,
            target=tgt,
            label=edge.get("label", ""),
            style=_edge_style(solid_edge),
            waypoints=waypoints,
            exit_xy=exit_xy,
            entry_xy=entry_xy,
            label_offset=label_offset,
        )
    return diagram


def _normalize_pages(spec: dict) -> list[dict]:
    """Return a list of page dicts, supporting the single-page shorthand."""
    if "pages" in spec:
        pages = spec["pages"]
        if not pages:
            raise SpecError("Spec 'pages' is empty.")
        return pages
    # single-page shorthand: cloud/edges or nodes/edges at top level
    if "region" in spec:
        return [{"name": spec.get("metadata", {}).get("project", "Architecture Diagram"),
                 "type": "architecture",
                 "global": spec.get("global", []),
                 "edge": spec.get("edge", []),
                 "region": spec["region"],
                 "edges": spec.get("edges", [])}]
    if "nodes" in spec:
        return [{"name": "Flow Diagram", "type": "flow",
                 "nodes": spec["nodes"], "edges": spec.get("edges", [])}]
    raise SpecError("Spec must contain 'pages', or a top-level 'region'/'nodes'.")


def build_document(spec: dict, strict_connectivity: bool = False) -> ET.Element:
    """Validate a full spec and build the complete (possibly multi-page) mxfile."""
    if not isinstance(spec, dict):
        raise SpecError("Spec must be a mapping/object.")
    meta = spec.get("metadata") or {}
    default_provider = _validate_provider(spec.get("provider", "aws"))

    pages = _normalize_pages(spec)
    diagrams: list[Diagram] = []
    seen_page_ids: set[str] = set()
    for idx, page in enumerate(pages, start=1):
        ptype = page.get("type", "architecture")
        page_id = page.get("id", f"page-{idx}")
        if page_id in seen_page_ids:
            raise SpecError(f"Duplicate page id {page_id!r}.")
        seen_page_ids.add(page_id)
        # Every page carries the same client and document metadata in its header.
        page_meta = dict(meta)
        if ptype == "architecture":
            diagrams.append(build_architecture_page(
                page, default_provider, page_id, page_meta,
                strict_connectivity=strict_connectivity,
            ))
        elif ptype == "flow":
            diagrams.append(build_flow_page(page, default_provider, page_id, page_meta))
        else:
            raise SpecError(
                f"Page {page.get('name', page_id)!r} has invalid type {ptype!r}; "
                "expected 'architecture' or 'flow'."
            )

    mxfile = build_mxfile(diagrams)
    validate(mxfile)
    return mxfile


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a draw.io diagram from a spec.")
    parser.add_argument("--input", required=True, help="Path to spec YAML/JSON.")
    parser.add_argument(
        "--output",
        help="Path to write .drawio.xml. Required unless --output-dir is given.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help=(
            "Root output directory. The diagram is written to "
            "DIR/<project-slug>/<spec-stem>.drawio.xml, creating the folder "
            "automatically. Ignored when --output is also supplied. "
            "Default: outputs/ (relative to the current working directory)."
        ),
    )
    parser.add_argument(
        "--strict-connectivity", action="store_true",
        help="Do not emit diagrams with unresolved architecture connectivity warnings.",
    )
    args = parser.parse_args(argv)

    if not args.output and not args.output_dir:
        # Default to outputs/ when neither flag is given
        args.output_dir = "outputs"

    import yaml  # local import so the module loads without PyYAML for unit tests
    import re as _re

    with open(args.input, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    # Resolve output path
    if args.output:
        output_path = args.output
    else:
        # Derive project slug from the spec metadata.project, falling back to
        # the input filename stem.
        project_name = (spec.get("metadata") or {}).get("project", "")
        if project_name:
            slug = _re.sub(r"[^a-zA-Z0-9]+", "-", project_name).strip("-").lower()
        else:
            import os as _os
            slug = _os.path.splitext(_os.path.basename(args.input))[0]
        import os as _os
        stem = _os.path.splitext(_os.path.basename(args.input))[0]
        # Strip a trailing .spec suffix so "acme-orders.spec.yaml" → "acme-orders"
        if stem.endswith(".spec"):
            stem = stem[:-5]
        client_dir = _os.path.join(args.output_dir, slug)
        _os.makedirs(client_dir, exist_ok=True)
        output_path = _os.path.join(client_dir, f"{stem}.drawio.xml")

    try:
        mxfile = build_document(spec, strict_connectivity=args.strict_connectivity)
    except (SpecError, ValidationError) as exc:
        parser.exit(2, f"error: {exc}\n")

    xml = render_xml(mxfile)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(xml)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
