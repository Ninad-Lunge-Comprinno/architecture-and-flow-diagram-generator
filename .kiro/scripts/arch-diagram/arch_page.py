"""Architecture-page builder: deterministic grid layout plus house-style orthogonal edge routing."""

from __future__ import annotations

import logging
from typing import Optional

import shapes
import layout
import routing

from diagram import Cell, Diagram, _label_html, overlap_check
from spec import (
    SpecError,
    _collect_arch_ids,
    _check_unique_ids,
    _validate_services,
    _check_edges,
    _architecture_connectivity_warnings,
    _edge_style,
)

logger = logging.getLogger("arch_diagram")


# ---------------------------------------------------------------------------
# Architecture routing constants
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


# ---------------------------------------------------------------------------
# Edge routing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pre-layout spec normalisation
# ---------------------------------------------------------------------------

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
                    logger.info(
                        "auto-fixed: moved %r (%r) from %s of %r to "
                        "region.services (regional service — not VPC-bound)",
                        res.get("id"), res.get("service"), tier, az.get("id"),
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
    """Add standard shared AWS services to every AWS architecture page once.

    Injection is skipped when the page (or its parent spec via the page dict)
    carries ``foundation_services: false``.  This lets specs that model their
    own observability / security tier remain free of auto-injected clutter.
    """
    if default_provider.lower() != "aws":
        return
    if page.get("foundation_services") is False:
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


def _prepare_arch_page(page: dict, default_provider: str,
                       strict_connectivity: bool) -> None:
    """Normalise, validate, and connectivity-check an architecture page in place.

    Runs the pre-layout auto-fixes (foundation services, regional placement,
    connection-aware ordering), validates ids/services/edges, logs connectivity
    warnings, and — in strict mode — raises ``SpecError`` if any remain.
    """
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
        logger.warning("architecture check: %s", warning)
    if strict_connectivity and connectivity_warnings:
        raise SpecError(
            "Architecture connectivity checks failed:\n  - "
            + "\n  - ".join(connectivity_warnings)
            + "\nResolve or clarify these paths before generating the diagram."
        )


def _emit_arch_frame(diagram: "Diagram", lo, meta: Optional[dict]) -> None:
    """Emit the title block, outer border, and brand mark around the cloud."""
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


def _emit_arch_nodes(diagram: "Diagram", lo, default_provider: str) -> None:
    """Emit every positioned node (icons, containers, cluster marks).

    The synthetic ``__title`` placeholder is skipped (handled by the frame).
    """
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
            is_named_cluster = node.kind in ("ecs_cluster", "eks_cluster", "asg")
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


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_architecture_page(page: dict, default_provider: str, diagram_id: str,
                            meta: Optional[dict] = None,
                            strict_connectivity: bool = False) -> Diagram:
    """Build an architecture page from the grid-model spec."""
    _prepare_arch_page(page, default_provider, strict_connectivity)

    diagram = Diagram(name=page.get("name", "Architecture Diagram"), diagram_id=diagram_id)

    lo = layout.build(page, default_provider)

    # Run overlap check — report warnings but don't block generation.
    for w in overlap_check(lo):
        logger.warning("%s", w)

    _emit_arch_frame(diagram, lo, meta)

    # Emit every positioned node (skip the synthetic title placeholder).
    _emit_arch_nodes(diagram, lo, default_provider)

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
    import routing as _routing
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
            logger.info(
                "bfs routing: %d residual icon, %d edge conflicts", n_ic, n_ee
            )

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
        logger.warning(
            "routing conflicts: %d edge-over-icon, %d edge-over-edge",
            n_icon, n_edge,
        )
        for c in conflicts[:12]:
            if c[0] == "edge_icon":
                logger.warning(
                    "  edge %s→%s crosses icon %r", c[1][0], c[1][1], c[2]
                )
            else:
                logger.warning(
                    "  edge %s→%s overlaps edge %s→%s",
                    c[1][0], c[1][1], c[2][0], c[2][1],
                )
    else:
        if computed_routes:
            logger.info(
                "routing: %d edges routed with no icon/edge conflicts",
                len(computed_routes),
            )

    _emit_arch_edges(diagram, all_edges, computed_routes, boxes)
    return diagram


def _emit_arch_edges(diagram: "Diagram", all_edges: list[dict],
                     computed_routes: dict, boxes: dict) -> None:
    """Emit every architecture edge, applying any spec geometry overrides.

    For each edge, the pre-computed route (exit/entry fractions + waypoints) is
    used unless the spec supplies explicit ``source_point``/``target_point``/
    ``waypoints`` overrides, which always win. House style: connector lines
    carry no text labels (spec labels are documentation only).
    """
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
