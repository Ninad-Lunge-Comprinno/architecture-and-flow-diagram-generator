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
EDGE_STYLE = ("edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;""strokeWidth=4;fontStyle=1;fontSize=11;fontColor=#000000;")


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
                # exitX=0.75 (top-right of source) shifts this vertical segment
                # right of center so it doesn't overlap ECR->ECS which uses x=0.5
                exit_src_x = sx + sw * 0.75
                exit_xy = (0.75, 0.0)    # exit top-right of source
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


def build_architecture_page(page: dict, default_provider: str, diagram_id: str,
                            meta: Optional[dict] = None) -> Diagram:
    """Build an architecture page from the grid-model spec."""
    layout = _import_layout()

    # Auto-fix regional services before validation and layout.
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

            is_target_tall = tgt_box[3] > 240
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

            # Case 1: Ingress band → VPC or tall container
            if src_in_ingress_band and (is_target_tall or tgt_in_vpc) and not use_spine:
                exit_xy = (0.5, 1.0)
                entry_xy = (0.5, 0.0)
                if dx > layout.ICON:
                    mid_y = vpc_abs_top - 40
                    waypoints = [(src_cx, mid_y), (tgt_cx, mid_y)]
                else:
                    waypoints = []

            # Case 2: Region service → tall cluster (ECR→ECS/EKS deploy)
            elif (src_above_vpc and not src_in_ingress_band
                  and is_target_tall and not use_spine):
                exit_xy = (0.5, 1.0)
                entry_xy = (0.5, 0.0)
                mid_y = tgt_box[1] - 40
                waypoints = [(src_cx, mid_y), (tgt_cx, mid_y)]

            # Case 2b: Compute CLUSTER boundary → DB (cluster→DB, option (a)).
            # The DB sits to the RIGHT of the tall lane, in a db_subnet row.
            # Exit the lane's RIGHT side, run to a per-edge vertical corridor in
            # the gap between the lane and the DB column, then drop into the DB
            # TOP. Each edge in a shared-source or shared-target bundle gets its
            # OWN corridor x and DB entry column, so no two segments coincide —
            # this is robust even when the vertical gap above the DB row is thin.
            elif (kind_of.get(src) in _CLUSTER_KINDS
                  and svc_of.get(tgt) in _DB_SVCS
                  and tgt_box[0] > src_box[0]):
                # shared-source: this cluster → several DBs (index by target x)
                sibs_t = clusterdb_by_src.get(src, [tgt])
                ti = sibs_t.index(tgt) if tgt in sibs_t else 0
                # shared-target: several clusters → this DB (index by source x)
                sibs_s = clusterdb_by_tgt.get(tgt, [src])
                si = sibs_s.index(src) if src in sibs_s else 0
                ns = len(sibs_s)
                src_right = src_box[0] + src_box[2]
                # Exit the lane right side, staggered vertically a little by the
                # target index so the two edges from one lane leave at different
                # heights (prevents a shared exit stub).
                exit_fy = 0.30 + 0.20 * ti
                exit_fy = min(0.9, max(0.1, exit_fy))
                exit_py = src_box[1] + src_box[3] * exit_fy
                # Per-edge vertical corridor in the gap between lane and DB.
                gap = tgt_box[0] - src_right
                # spread corridors across the gap by a combined bundle index
                bundle_n = max(2, len(sibs_t) * ns)
                bundle_i = ti * ns + si
                corridor_x = src_right + gap * (bundle_i + 1) / (bundle_n + 1)
                # DB entry column staggered by source (shared-target split)
                entry_fx = ((si + 1) / (ns + 1)) if ns > 1 else 0.5
                drop_x = tgt_box[0] + tgt_box[2] * entry_fx
                exit_xy = (1.0, round(exit_fy, 3))
                entry_xy = (round(entry_fx, 3), 0.0)
                waypoints = [(corridor_x, exit_py),
                             (corridor_x, tgt_box[1] - 12),
                             (drop_x, tgt_box[1] - 12)]

            # Case 3: Lane → icon (Sadhaka geometry)
            elif (kind_of.get(src) in ("asg", "ecs_cluster", "eks_cluster", "cluster")
                    and kind_of.get(tgt) == "resource"
                    and tgt_box[0] > src_box[0]):
                src_right = src_box[0] + src_box[2]
                cand = None
                if abs(tgt_cy - src_cy) > 10:
                    bus_y = tgt_box[1] - 75 if tgt_cy < src_cy else tgt_box[1] - 160
                    fexit = (bus_y - src_box[1]) / src_box[3]
                    if 0.02 <= fexit <= 0.98:
                        exit_xy, entry_xy = (1.0, round(fexit, 2)), (0.5, 0.0)
                        waypoints = [(tgt_cx, bus_y)]
                        cand = [(src_right, bus_y), (tgt_cx, bus_y),
                                (tgt_cx, tgt_box[1])]
                else:
                    frac0 = (src_cy - tgt_box[1]) / tgt_box[3]
                    if 0.05 <= frac0 <= 0.95:
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
                band_up = row_top + 45 - n_up * 18
                band_lo = row_bot - 45 + n_lo * 18
                gx = src_right + 40
                picked = False

                # a. Straight
                frac = (src_cy - tgt_box[1]) / tgt_box[3] if tgt_box[3] else 0.5
                if 0.05 <= frac <= 0.95:
                    cand = [(src_right, src_cy), (tgt_left, src_cy)]
                    if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                        exit_xy, entry_xy = (1.0, 0.5), (0.0, round(frac, 2))
                        waypoints = []
                        picked = True

                # b. Upper-band jog
                if not picked and row_top + 20 < band_up < src_cy + tgt_box[3]:
                    if is_target_tall:
                        fup = min(0.95, max(0.05, (band_up - tgt_box[1]) / tgt_box[3]))
                        cand = [(src_right, src_cy), (gx, src_cy), (gx, band_up),
                                (tgt_left, band_up)]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy, entry_xy = (1.0, 0.5), (0.0, round(fup, 2))
                            waypoints = _dedup([(gx, src_cy), (gx, band_up),
                                                (tgt_left, band_up)])
                            _stagger_tracker[(src, "bandup")] = n_up + 1
                            picked = True
                    else:
                        cand = [(src_cx, src_box[1]), (src_cx, band_up),
                                (tgt_cx, band_up), (tgt_cx, tgt_box[1])]
                        if _seg_hits_resource(cand, boxes, kind_of, src, tgt) is None:
                            exit_xy, entry_xy = (0.5, 0.0), (0.5, 0.0)
                            waypoints = _dedup([(src_cx, band_up), (tgt_cx, band_up)])
                            _stagger_tracker[(src, "bandup")] = n_up + 1
                            picked = True

                # c. Lower-band jog
                if not picked and src_cy - tgt_box[3] < band_lo < row_bot - 20:
                    if is_target_tall:
                        flo = min(0.95, max(0.05, (band_lo - tgt_box[1]) / tgt_box[3]))
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

            # Case 5: Fallback
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
                    new_fx = min(0.85, max(0.15, exit_xy[0] + m * 0.18))
                    exit_xy = (round(new_fx, 3), 1.0)
                    lift = m * 22
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
            exit_xy = (parts[0], parts[1])
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


def _flow_layout(nodes: list[dict], edges: list[dict]) -> dict[str, tuple[float, float]]:
    """Compute a layered (top-down) layout for flow nodes.

    Nodes with no incoming edges form the first layer (top).
    Each subsequent layer contains nodes whose predecessors are all placed.
    Within a layer, nodes are spread horizontally centred on the canvas.
    If a node has an explicit x/y in its spec dict those override the computed position.

    Returns: {node_id: (x, y)} in absolute page coordinates.
    """
    STEP_X = ICON_SIZE + 220   # horizontal spacing
    STEP_Y = ICON_SIZE + layout.LABEL_BAND + 160   # vertical spacing
    PAD_X = 60
    PAD_Y = 60

    # Build adjacency
    incoming: dict[str, set] = {n["id"]: set() for n in nodes}
    for e in edges:
        if e["target"] in incoming:
            incoming[e["target"]].add(e["source"])

    # Topological layers
    placed: set = set()
    layers: list[list[str]] = []
    remaining = [n["id"] for n in nodes]
    while remaining:
        layer = [nid for nid in remaining if incoming[nid] <= placed]
        if not layer:
            # Cycle or disconnected — put remaining in a layer
            layer = remaining[:]
        layers.append(layer)
        for nid in layer:
            placed.add(nid)
        remaining = [nid for nid in remaining if nid not in placed]

    # Compute max layer width for centering
    max_layer_w = max(len(l) for l in layers) if layers else 1
    canvas_w = max_layer_w * STEP_X

    positions: dict[str, tuple[float, float]] = {}
    y = PAD_Y
    for layer in layers:
        layer_w = len(layer) * STEP_X - (STEP_X - ICON_SIZE)
        x_start = PAD_X + (canvas_w - layer_w) / 2
        for col_i, nid in enumerate(layer):
            positions[nid] = (x_start + col_i * STEP_X, y)
        y += STEP_Y

    return positions


def build_flow_page(page: dict, default_provider: str, diagram_id: str,
                    meta: Optional[dict] = None) -> Diagram:
    """Build a flow page using a layered top-down layout.

    Nodes are arranged in topological layers (sources at top, sinks at bottom).
    An outer border encloses the whole page. Edges use connection-point routing.
    Spec nodes may override position with explicit 'x' and 'y' fields.
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

    # Compute layered positions (spec x/y overrides if provided)
    auto_pos = _flow_layout(nodes, page.get("edges", []))
    boxes: dict[str, tuple[float, float, float, float]] = {}

    for node in nodes:
        nid = node["id"]
        auto_x, auto_y = auto_pos.get(nid, (40, 60))
        x = node.get("x", auto_x)
        y = node.get("y", auto_y)
        diagram.add_icon(
            provider=node.get("provider", default_provider),
            service=node["service"],
            label=node.get("label"),
            x=x,
            y=y,
            cell_id=nid,
        )
        boxes[nid] = (x, y, ICON_SIZE, ICON_SIZE)

    # Title block (page 1 only, meta provided by build_document)
    if meta:
        # Place title above the flow nodes (negative y so it sits above)
        diagram.add_title_block(meta, x=40, y=-220)

    # Outer border enclosing all flow nodes
    if boxes:
        all_x = [b[0] for b in boxes.values()]
        all_y = [b[1] for b in boxes.values()]
        bx = min(all_x) - 40
        by = min(all_y) - 40
        bw = max(b[0] + b[2] for b in boxes.values()) - bx + 40
        bh = max(b[1] + b[3] for b in boxes.values()) - by + 40 + layout.LABEL_BAND
        diagram.add_outer_border(bx, by, bw, bh, margin=0)

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
