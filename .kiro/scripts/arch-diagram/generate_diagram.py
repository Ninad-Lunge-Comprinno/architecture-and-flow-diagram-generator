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
EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=4;"


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


def title_block_value(meta: dict) -> str:
    """Build the standardized title-block HTML (raw HTML; escaped once by ET)."""
    project = str(meta.get("project", "Architecture Diagram"))
    lines = [f'<h1 style="text-align:left"><b style="font-size:32px;">{project}</b></h1>']
    for field_name in ("version", "date", "creator", "reviewer"):
        val = meta.get(field_name)
        if val:
            label = field_name.capitalize()
            lines.append(
                f'<div style="text-align:left;font-size:20px;">{label}: {val}</div>'
            )
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
            value=label if label else "",
            style=full_style,
            edge=True,
            source=source,
            target=target,
            waypoints=waypoints or [],
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
        except shapes.UnknownServiceError as exc:
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
                az_rows: Optional[list] = None):
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

    # 1. Source is above a tall container and horizontally offset:
    #    ECR-style — exit bottom, go horizontal at midpoint, enter top.
    if th > 240 and (sy + sh) < ty and abs(dx) > 200 and vpc_corridor_x is None:
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
                clear_y = row_top - 30   # 30px above the AZ row top (above subnets)
                exit_xy = (0.5, 0.0)     # exit TOP of source
                entry_xy = (0.5, 0.0)    # enter TOP of target
                waypoints = [(scx, clear_y), (tcx, clear_y)]
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
            # Multi-AZ skip: route via a right-side corridor to avoid
            # overlapping intermediate AZ rows.
            right_x = max(sx + sw, tx + tw) + 60  # corridor right of both icons
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



def build_architecture_page(page: dict, default_provider: str, diagram_id: str,
                            meta: Optional[dict] = None) -> Diagram:
    """Build an architecture page from the grid-model spec."""
    layout = _import_layout()

    elements = _collect_arch_ids(page)
    ids = _check_unique_ids(elements, page.get("name", "architecture"))
    _validate_services(elements, default_provider)
    _check_edges(page.get("edges", []), ids, page.get("name", "architecture"))

    diagram = Diagram(name=page.get("name", "Architecture Diagram"), diagram_id=diagram_id)

    lo = layout.build(page, default_provider)

    # Run overlap check — report warnings but don't block generation.
    _overlap_warnings: list[str] = overlap_check(lo)
    if _overlap_warnings:
        for w in _overlap_warnings:
            print(f"  ⚠  {w}", flush=True)

    # Title block: position from the layout's __title node (top-left).
    title_node = next((n for n in lo.nodes if n.node_id == "__title"), None)
    if meta and title_node is not None:
        diagram.add_title_block(meta, x=title_node.x, y=title_node.y)
    elif meta:
        diagram.add_title_block(meta)

    # Outer border enclosing the title block AND the cloud.
    diagram.add_outer_border(lo.border_x, lo.border_y, lo.border_w, lo.border_h, margin=0)

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
            diagram.cells.append(Cell(
                id=node.node_id,
                parent=node.parent,
                value=_label_html(node.label or container.label),
                style=container.style(),
                vertex=True,
                x=node.x, y=node.y, width=node.width, height=node.height,
            ))

    # Edges: routed with connection points using absolute boxes.
    boxes = lo.abs_boxes
    for edge in page.get("edges", []):
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None
        if src in boxes and tgt in boxes and not edge.get("style"):
            src_box = boxes[src]
            tgt_box = boxes[tgt]
            # Use the VPC corridor spine when the source is to the left of the VPC
            # (e.g. ALB/CloudFront in the edge strip routing into VPC compute nodes).
            use_spine = (lo.vpc_corridor_x > 0
                         and src_box[0] < lo.vpc_corridor_x
                         and tgt_box[0] > lo.vpc_corridor_x)
            exit_xy, entry_xy, waypoints = _route_edge(
                src_box, tgt_box,
                label_band=layout.LABEL_BAND,
                az_gaps=lo.az_gaps,
                vpc_corridor_x=lo.vpc_corridor_x if use_spine else None,
                az_rows=lo.az_rows,
            )
        # Allow spec to provide explicit waypoints (overrides computed ones)
        spec_wps = edge.get("waypoints")
        if spec_wps:
            waypoints = [tuple(p) for p in spec_wps]
        diagram.add_edge(
            source=src,
            target=tgt,
            label=edge.get("label", ""),
            style=_edge_style(edge),
            waypoints=waypoints,
            exit_xy=exit_xy,
            entry_xy=entry_xy,
        )
    return diagram


def build_flow_page(page: dict, default_provider: str, diagram_id: str,
                    meta: Optional[dict] = None) -> Diagram:
    """Build a flow page: a flat sequence of nodes with labeled edges."""
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
    if meta:
        diagram.add_title_block(meta)

    # Sequential placement: a horizontal row wrapping every N nodes. Row pitch
    # includes the label band so wrapped 2-line labels never touch the next row.
    step_x = ICON_SIZE + 150
    step_y = ICON_SIZE + layout.LABEL_BAND + 110
    per_row = 5
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for idx, node in enumerate(nodes):
        col = idx % per_row
        row = idx // per_row
        x = node.get("x", col * step_x + 40)
        y = node.get("y", row * step_y + 60)
        diagram.add_icon(
            provider=node.get("provider", default_provider),
            service=node["service"],
            label=node.get("label"),
            x=x,
            y=y,
            cell_id=node["id"],
        )
        boxes[node["id"]] = (x, y, ICON_SIZE, ICON_SIZE)

    for edge in page.get("edges", []):
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None
        if src in boxes and tgt in boxes and not edge.get("style"):
            exit_xy, entry_xy, waypoints = _route_edge(boxes[src], boxes[tgt],
                                                       label_band=layout.LABEL_BAND)
        diagram.add_edge(
            source=src,
            target=tgt,
            label=edge.get("label", ""),
            style=_edge_style(edge),
            waypoints=waypoints,
            exit_xy=exit_xy,
            entry_xy=entry_xy,
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


def build_document(spec: dict) -> ET.Element:
    """Validate a full spec and build the complete (possibly multi-page) mxfile."""
    if not isinstance(spec, dict):
        raise SpecError("Spec must be a mapping/object.")
    meta = spec.get("metadata") or {}
    if not meta.get("project"):
        raise SpecError("metadata.project is required (used in the title block).")
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
        # Only the first page carries the title block.
        page_meta = meta if idx == 1 else None
        if ptype == "architecture":
            diagrams.append(build_architecture_page(page, default_provider, page_id, page_meta))
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
    parser.add_argument("--output", required=True, help="Path to write .drawio.xml.")
    args = parser.parse_args(argv)

    import yaml  # local import so the module loads without PyYAML for unit tests

    with open(args.input, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    try:
        mxfile = build_document(spec)
    except (SpecError, ValidationError) as exc:
        parser.exit(2, f"error: {exc}\n")

    xml = render_xml(mxfile)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(xml)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
