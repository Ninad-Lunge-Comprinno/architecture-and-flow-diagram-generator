"""Connection-aware placement planning, obstacle-aware orthogonal edge routing,
and a recursive conflict checker for the architecture layout.

Pipeline (see build_architecture_page):
    1. plan_region_service_order()  — order freely-placeable region services so
       connected pairs (e.g. API Gateway ↔ Lambda) end up close together and
       VPC-connected services sit closest to the VPC. Placement only; the
       house-style fixed structure (AZ rows, subnets, lanes, gutters) is kept.
    2. layout.build()               — deterministic geometry from the plan.
    3. route_all_edges()            — AFTER placement is final, compute an
       orthogonal path for every edge that avoids icon+label obstacles and
       minimises length; edges are ordered longest-first so short edges fill
       remaining channels.
    4. find_conflicts()             — edge-vs-icon and edge-vs-edge overlaps.
    5. bounded rework loop in the caller: route → check → nudge → re-check.

All coordinates are absolute page coordinates. A "box" is (x, y, w, h).
"""
from __future__ import annotations

from typing import Optional

ICON = 120
LABEL_BAND = 50
GRID = 20  # routing grid resolution (px)
CLEARANCE = 10  # min gap kept between an edge and an obstacle


# ---------------------------------------------------------------------------
# Stage 1: connection-aware placement of freely-placeable region services
# ---------------------------------------------------------------------------
def plan_region_service_order(page: dict) -> None:
    """Reorder ``region.services`` in-place to minimise connection length.

    Freely-placeable = region services (the region grid). Ordering rules,
    applied as a stable sort so unrelated services keep spec order:

      * services connected to a VPC element (or a VPC entry-gutter item such as
        ALB / API Gateway) are pulled to the END of the list so they land in
        the last service row, closest to the VPC/gutter;
      * among those, services connected to the API-Gateway/ALB gutter come
        LAST-most and left-biased, because the gutter sits at the VPC's top-left;
      * a service that connects to another region service is placed adjacent to
        it (kept in the same neighbourhood) when possible.

    This generalises the previous _reorder_services_for_vpc_proximity.
    """
    region_spec = page.get("region", {}) or {}
    services = region_spec.get("services", []) or []
    edges = page.get("edges", []) or []
    if not services or not edges:
        return

    svc_ids = {s["id"] for s in services}

    # Ids that live inside the VPC (subnets + compute groups + their AZ nodes).
    vpc = region_spec.get("vpc", {}) or {}
    vpc_ids: set = set()
    for az in vpc.get("azs", []) or []:
        for tier in ("public_subnet", "app_subnet", "db_subnet"):
            for r in (az.get(tier) or {}).get("resources", []) or []:
                vpc_ids.add(r.get("id"))
    for g in vpc.get("compute_groups", []) or []:
        vpc_ids.add(g.get("id"))
        for az in vpc.get("azs", []) or []:
            vpc_ids.add(f"{g.get('id')}-{az.get('id')}")

    # Entry-gutter ids (ALB / API Gateway live inside the VPC gutter; Shield/WAF
    # in the region gutter). Classify from the edge list.
    edge_items = page.get("edge", []) or []
    gutter_vpc_ids = {r["id"] for r in edge_items
                      if r.get("service") in ("application_load_balancer",
                                              "network_load_balancer", "api_gateway")}

    # Build adjacency for region services.
    def _neighbours(sid: str) -> set:
        out = set()
        for e in edges:
            s, t = e.get("source"), e.get("target")
            if s == sid:
                out.add(t)
            elif t == sid:
                out.add(s)
        return out

    # Score each region service: higher score => later in the list (closer to VPC).
    def _score(sid: str) -> int:
        nb = _neighbours(sid)
    # Score each region service to decide its column in the grid. The grid
    # fills left→right, top→bottom, so LOWER scores render earlier (left/top)
    # and HIGHER scores later (right/bottom, i.e. closest to the VPC).
    #
    # Scoring:
    #   * Services connected to APIGW/ALB gutter items (e.g. Lambda) → END
    #     of the list, so they land in the LAST row nearest the VPC where
    #     the gutter sits. The short APIGW→Lambda edge then has the minimum
    #     possible length.
    #   * VPC-element / cluster-connected services (e.g. ECR) → also END,
    #     right after the gutter-connected ones.
    #   * Services connected to another region service → middle (keep together).
    #   * Unconnected services → front.
    def _score(sid: str) -> int:
        nb = _neighbours(sid)
        if nb & gutter_vpc_ids:
            return 2          # APIGW/ALB-connected → END (last row, near VPC gutter)
        if nb & vpc_ids:
            return 3          # connected to a VPC element/cluster → very END
        if nb & svc_ids:
            return 1          # connected to another region service → middle
        return 0              # unconnected → front

    order = sorted(range(len(services)),
                   key=lambda i: (_score(services[i]["id"]), i))
    region_spec["services"] = [services[i] for i in order]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _rects_intersect(a, b, tol: float = 0.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax + aw - tol > bx and bx + bw - tol > ax
            and ay + ah - tol > by and by + bh - tol > ay)


def _seg_intersects_rect(p1, p2, rect, tol: float = 0.0) -> bool:
    """True if the axis-aligned segment p1→p2 passes through rect."""
    rx, ry, rw, rh = rect
    rx -= tol; ry -= tol; rw += 2 * tol; rh += 2 * tol
    x1, y1 = p1
    x2, y2 = p2
    if abs(x1 - x2) < 1e-6:  # vertical segment
        if x1 <= rx or x1 >= rx + rw:
            return False
        lo, hi = min(y1, y2), max(y1, y2)
        return not (hi <= ry or lo >= ry + rh)
    if abs(y1 - y2) < 1e-6:  # horizontal segment
        if y1 <= ry or y1 >= ry + rh:
            return False
        lo, hi = min(x1, x2), max(x1, x2)
        return not (hi <= rx or lo >= rx + rw)
    # Non-orthogonal segment: sample.
    steps = int(max(abs(x2 - x1), abs(y2 - y1)) / 8) + 1
    for i in range(steps + 1):
        t = i / steps
        px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if rx < px < rx + rw and ry < py < ry + rh:
            return True
    return False


def _polyline_hits_rect(points, rect, tol: float = 0.0) -> bool:
    for i in range(len(points) - 1):
        if _seg_intersects_rect(points[i], points[i + 1], rect, tol):
            return True
    return False


def _segments_overlap(a1, a2, b1, b2) -> bool:
    """True if two orthogonal segments share a colinear overlapping run."""
    # vertical-vertical
    if abs(a1[0] - a2[0]) < 1e-6 and abs(b1[0] - b2[0]) < 1e-6:
        if abs(a1[0] - b1[0]) > 1e-6:
            return False
        alo, ahi = sorted((a1[1], a2[1]))
        blo, bhi = sorted((b1[1], b2[1]))
        return max(alo, blo) < min(ahi, bhi) - 1
    # horizontal-horizontal
    if abs(a1[1] - a2[1]) < 1e-6 and abs(b1[1] - b2[1]) < 1e-6:
        if abs(a1[1] - b1[1]) > 1e-6:
            return False
        alo, ahi = sorted((a1[0], a2[0]))
        blo, bhi = sorted((b1[0], b2[0]))
        return max(alo, blo) < min(ahi, bhi) - 1
    return False


# ---------------------------------------------------------------------------
# Stage 3: obstacle-aware orthogonal routing (Lee / BFS on a coarse grid)
# ---------------------------------------------------------------------------
class Router:
    """Routes orthogonal polylines on a coarse grid, avoiding obstacle rects."""

    def __init__(self, obstacles: list, bounds: tuple, grid: int = GRID,
                 clearance: float = CLEARANCE):
        self.grid = grid
        self.clearance = clearance
        self.minx, self.miny, self.maxx, self.maxy = bounds
        self.cols = int((self.maxx - self.minx) / grid) + 2
        self.rows = int((self.maxy - self.miny) / grid) + 2
        # Blocked cells from obstacles (inflated by clearance).
        self.blocked = [[False] * self.cols for _ in range(self.rows)]
        for (ox, oy, ow, oh) in obstacles:
            c0 = self._cx(ox - clearance)
            c1 = self._cx(ox + ow + clearance)
            r0 = self._cy(oy - clearance)
            r1 = self._cy(oy + oh + clearance)
            for r in range(max(0, r0), min(self.rows, r1 + 1)):
                for c in range(max(0, c0), min(self.cols, c1 + 1)):
                    self.blocked[r][c] = True

    def _cx(self, x: float) -> int:
        return int(round((x - self.minx) / self.grid))

    def _cy(self, y: float) -> int:
        return int(round((y - self.miny) / self.grid))

    def _wx(self, c: int) -> float:
        return self.minx + c * self.grid

    def _wy(self, r: int) -> float:
        return self.miny + r * self.grid

    def _free(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols and not self.blocked[r][c]

    def route(self, start, goal, start_dir=None, soft=None) -> Optional[list]:
        """BFS with a turn penalty → orthogonal path minimising length+turns.

        start/goal are absolute (x, y). Returns a simplified list of waypoints
        (absolute), or None if no path is found. ``soft`` is an optional set of
        grid cells (r, c) that remain traversable but are penalised — used to
        pass in cells already occupied by previously-routed edges so nets spread
        into separate channels instead of stacking. This is a general multi-net
        routing technique, not tied to any particular diagram.
        """
        import heapq
        soft = soft or set()
        sc, sr = self._cx(start[0]), self._cy(start[1])
        gc, gr = self._cx(goal[0]), self._cy(goal[1])
        # Temporarily unblock start/goal cells (endpoints sit on icon borders).
        saved = {}
        for (rr, cc) in [(sr, sc), (gr, gc)]:
            if 0 <= rr < self.rows and 0 <= cc < self.cols:
                saved[(rr, cc)] = self.blocked[rr][cc]
                self.blocked[rr][cc] = False
        try:
            # State: (r, c, dir). dir: 0=none,1=H,2=V. Cost = steps + turns*2.
            dirs = [(-1, 0, 2), (1, 0, 2), (0, -1, 1), (0, 1, 1)]
            pq = [(0, sr, sc, 0, [(sr, sc)])]
            best = {}
            while pq:
                cost, r, c, d, path = heapq.heappop(pq)
                if (r, c) == (gr, gc):
                    return self._simplify(path, start, goal)
                key = (r, c, d)
                if key in best and best[key] <= cost:
                    continue
                best[key] = cost
                for dr, dc, nd in dirs:
                    nr, nc = r + dr, c + dc
                    if not self._free(nr, nc):
                        continue
                    turn = 2 if (d != 0 and d != nd) else 0
                    penalty = 4 if (nr, nc) in soft else 0
                    heapq.heappush(pq, (cost + 1 + turn + penalty, nr, nc, nd,
                                        path + [(nr, nc)]))
            return None
        finally:
            for (rr, cc), v in saved.items():
                self.blocked[rr][cc] = v

    def cells_for(self, path) -> set:
        """Return the grid cells a routed polyline occupies (for soft-obstacle
        accumulation across nets)."""
        occupied = set()
        for i in range(len(path) - 1):
            c1, r1 = self._cx(path[i][0]), self._cy(path[i][1])
            c2, r2 = self._cx(path[i + 1][0]), self._cy(path[i + 1][1])
            if r1 == r2:
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    occupied.add((r1, c))
            else:
                for r in range(min(r1, r2), max(r1, r2) + 1):
                    occupied.add((r, c1))
        return occupied

    def _simplify(self, cell_path, start, goal) -> list:
        """Collapse colinear runs and convert to absolute waypoints."""
        pts = [(self._wx(c), self._wy(r)) for (r, c) in cell_path]
        pts[0] = start
        pts[-1] = goal
        out = [pts[0]]
        for i in range(1, len(pts) - 1):
            ax, ay = out[-1]
            bx, by = pts[i]
            cx, cy = pts[i + 1]
            # keep only corner points
            if (abs(ax - bx) < 1e-6 and abs(bx - cx) < 1e-6) or \
               (abs(ay - by) < 1e-6 and abs(by - cy) < 1e-6):
                continue
            out.append(pts[i])
        out.append(pts[-1])
        return out


# ---------------------------------------------------------------------------
# Stage 4: conflict detection (edge-vs-icon, edge-vs-edge)
# ---------------------------------------------------------------------------
def find_conflicts(routes: dict, icon_boxes: dict, tol: float = 2.0) -> list:
    """Return a list of conflict descriptions.

    routes: {edge_key: [ (x,y), ... ]}
    icon_boxes: {id: (x,y,w,h)} — icons only (labels handled by clearance).
    """
    conflicts: list = []
    # edge-vs-icon
    for ekey, pts in routes.items():
        s_id, t_id = ekey
        for iid, box in icon_boxes.items():
            if iid in (s_id, t_id):
                continue
            if _polyline_hits_rect(pts, box, tol):
                conflicts.append(("edge_icon", ekey, iid))
    # edge-vs-edge (colinear overlap of segments from different edges)
    keys = list(routes.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            pa, pb = routes[keys[i]], routes[keys[j]]
            hit = False
            for x in range(len(pa) - 1):
                for y in range(len(pb) - 1):
                    if _segments_overlap(pa[x], pa[x + 1], pb[y], pb[y + 1]):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                conflicts.append(("edge_edge", keys[i], keys[j]))
    return conflicts


# ---------------------------------------------------------------------------
# Deterministic HOUSE-STYLE rule-based router
# ---------------------------------------------------------------------------
# Instead of a generic pathfinder (which produces organic, messy lines), we
# pick connection points and waypoints from the *relationship type* and the
# relative geometry of the two endpoints — reproducing the conventions in the
# hand-authored reference. Every rule yields orthogonal, predictable paths.
#
# meta[id] = {"service": str, "kind": str, "parent": str, "az": Optional[str]}
# ---------------------------------------------------------------------------

_DB_SERVICES = {"rds", "aurora", "elasticache", "memorydb", "documentdb",
                "neptune", "timestream", "keyspaces", "redshift", "dynamodb"}
_COMPUTE_NODE_SERVICES = {"ec2", "fargate"}
_INGRESS_SERVICES = {"shield", "waf", "application_load_balancer",
                     "network_load_balancer"}


def _center(box):
    return (box[0] + box[2] / 2, box[1] + box[3] / 2)


def route_all_edges_rulebased(edges, boxes, meta, az_gap_x=None):
    """Return (routes, endpoints) using house-style connection rules.

    edges: list of edge dicts (need source/target; may carry service info via meta).
    boxes: {id: (x,y,w,h)} absolute.
    meta:  {id: {service, kind, parent, az}}.
    az_gap_x: optional x of a vertical corridor between AZ columns (unused hook).

    routes:    {(s,t): [abs waypoints incl. endpoints]}
    endpoints: {(s,t): (exit_xy, entry_xy)}
    """
    routes, endpoints = {}, {}
    # Pre-count task→DB edges per source so we can give each a distinct exit
    # fraction and clear-y band (prevents shared-source lines from overlapping).
    taskdb_by_src: dict = {}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        sm, tm = meta.get(s, {}), meta.get(t, {})
        if sm.get("service") in _COMPUTE_NODE_SERVICES and tm.get("service") in _DB_SERVICES:
            taskdb_by_src.setdefault(s, []).append(t)

    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s not in boxes or t not in boxes:
            continue
        sb, tb = boxes[s], boxes[t]
        sm = meta.get(s, {})
        tm = meta.get(t, {})
        s_svc = sm.get("service", "")
        t_svc = tm.get("service", "")
        scx, scy = _center(sb)
        tcx, tcy = _center(tb)

        exit_xy, entry_xy, wps = _rule_for(
            s, t, sb, tb, s_svc, t_svc, sm, tm)

        # Stagger multiple task→DB edges from the same source: spread their exit
        # fractions across the top border and give each its own clear-y band so
        # the over-the-top segments never overlap.
        if (s_svc in _COMPUTE_NODE_SERVICES and t_svc in _DB_SERVICES
                and len(taskdb_by_src.get(s, [])) > 1):
            sibs = taskdb_by_src[s]
            # order targets by x so fractions increase left→right
            sibs_sorted = sorted(sibs, key=lambda tid: boxes[tid][0])
            idx = sibs_sorted.index(t)
            n = len(sibs_sorted)
            frac = (idx + 1) / (n + 1)              # e.g. 0.33/0.66 or 0.25/0.5/0.75
            clear_y = min(sb[1], min(boxes[x][1] for x in sibs)) - (60 + idx * 30)
            exit_px = sb[0] + sb[2] * frac
            exit_xy = (round(frac, 3), 0.0)
            wps = [(exit_px, clear_y), (tcx, clear_y)]

        pts = [(_ex(sb, exit_xy))] + wps + [(_ex(tb, entry_xy))]

        # Same-row straight edge: if an intervening icon sits on the segment,
        # bump the path up over the row so it doesn't cross that icon.
        if len(pts) == 2 and abs(pts[0][1] - pts[1][1]) < 1:
            blocker = _intervening_icon(pts[0], pts[1], boxes, {s, t})
            if blocker is not None:
                over_y = min(sb[1], tb[1]) - 40
                exit_xy = (0.5, 0.0)
                entry_xy = (0.5, 0.0)
                pts = [(_ex(sb, exit_xy)), (scx, over_y), (tcx, over_y),
                       (_ex(tb, entry_xy))]

        routes[(s, t)] = pts
        endpoints[(s, t)] = (exit_xy, entry_xy)
    return routes, endpoints


def _intervening_icon(p1, p2, boxes, skip):
    """Return an icon id that a horizontal segment p1→p2 passes through, or None."""
    y = p1[1]
    lo_x, hi_x = sorted((p1[0], p2[0]))
    for iid, (x, yy, w, h) in boxes.items():
        if iid in skip:
            continue
        if w > 200 or h > 200:  # skip containers
            continue
        if yy < y < yy + h and lo_x < x + w and x < hi_x:
            # segment's x-range overlaps the icon and y is within its band
            if lo_x < x and x + w < hi_x:
                return iid
    return None


def _ex(box, frac):
    """Absolute point on box border at fraction (fx, fy)."""
    x, y, w, h = box
    return (x + w * frac[0], y + h * frac[1])


def _rule_for(s, t, sb, tb, s_svc, t_svc, sm, tm):
    """Return (exit_xy, entry_xy, waypoints) for one edge by house-style rules.

    RELATIONSHIP-SPECIFIC rules are checked FIRST (they encode the intended
    semantic routing), then generic geometry rules as a fallback. Order matters:
    e.g. a compute→DB edge on the same row must use the over-the-top rule, not
    the generic straight side-exit.
    """
    scx, scy = _center(sb)
    tcx, tcy = _center(tb)
    dx, dy = tcx - scx, tcy - scy
    is_tall_target = tb[3] > 240  # a compute-group lane / cluster

    # === RELATIONSHIP-SPECIFIC RULES (highest priority) ===================

    # R-A: compute task → DB : exit TOP, route up-and-over, entry TOP.
    if s_svc in _COMPUTE_NODE_SERVICES and t_svc in _DB_SERVICES:
        clear_y = min(sb[1], tb[1]) - 70
        if tcx < scx:
            exit_fx = 0.25
        elif tcx > scx + sb[2]:
            exit_fx = 0.75
        else:
            exit_fx = 0.5
        exit_px = sb[0] + sb[2] * exit_fx
        return (exit_fx, 0.0), (0.5, 0.0), [(exit_px, clear_y), (tcx, clear_y)]

    # R-B: DB replication (DB → DB).
    if s_svc in _DB_SERVICES and t_svc in _DB_SERVICES:
        adjacent = _az_adjacent(sm.get("az"), tm.get("az"))
        if abs(dx) < 40 and adjacent:
            return (0.5, 1.0), (0.5, 0.0), []       # straight vertical
        corridor_x = max(sb[0] + sb[2], tb[0] + tb[2]) + 40
        return (1.0, 0.5), (0.5, 0.0), [(corridor_x, scy), (corridor_x, tb[1] - 30),
                                        (tcx, tb[1] - 30)]

    # R-C: ALB / NLB → compute cluster : side entry via the AZ gap.
    if s_svc in ("application_load_balancer", "network_load_balancer") and is_tall_target:
        entry_frac_y = max(0.0, min(1.0, (scy - tb[1]) / tb[3]))
        return (1.0, 0.5), (0.0, round(entry_frac_y, 3)), [(tb[0] - 40, scy)]

    # R-D: API Gateway → Lambda / region service : exit TOP → entry LEFT.
    if s_svc == "api_gateway":
        return (0.5, 0.0), (0.0, 0.5), [(scx, tcy)]

    # R-E: deploy into a tall cluster from above (e.g. ECR → ECS/EKS).
    if is_tall_target and sb[1] + sb[3] <= tb[1] + 5:
        mid_y = (sb[1] + sb[3] + tb[1]) / 2
        return (0.5, 1.0), (0.5, 0.0), [(scx, mid_y), (tcx, mid_y)]

    # === GENERIC GEOMETRY RULES (fallback) ================================

    # G-1: same row, straight side-exit (ingress chain, ecs→cache adjacent).
    if abs(dy) <= 30 and abs(dx) > 0:
        return ((1.0, 0.5), (0.0, 0.5), []) if dx >= 0 else ((0.0, 0.5), (1.0, 0.5), [])

    # G-2: same column, straight vertical.
    if abs(dx) < 40:
        if dy >= 0:
            return (0.5, 1.0), (0.5, 0.0), []
        return (0.5, 0.0), (0.5, 1.0), []

    # G-3: horizontal-preferred side exit with mid-x bend.
    if abs(dx) >= abs(dy):
        exit_xy = (1.0, 0.5) if dx >= 0 else (0.0, 0.5)
        entry_xy = (0.0, 0.5) if dx >= 0 else (1.0, 0.5)
        if abs(dy) > 40:
            mid_x = (sb[0] + sb[2] + tb[0]) / 2 if dx >= 0 else (sb[0] + tb[0] + tb[2]) / 2
            return exit_xy, entry_xy, [(mid_x, scy), (mid_x, tcy)]
        return exit_xy, entry_xy, []

    # G-4: vertical-preferred with mid-y bend.
    if dy >= 0:
        return (0.5, 1.0), (0.5, 0.0), [(scx, (scy + tcy) / 2), (tcx, (scy + tcy) / 2)]
    return (0.5, 0.0), (0.5, 1.0), [(scx, (scy + tcy) / 2), (tcx, (scy + tcy) / 2)]


def _az_adjacent(a, b):
    """Return True if two AZ ids are adjacent (az1↔az2, az2↔az3)."""
    if not a or not b:
        return True  # unknown → treat as adjacent (straight vertical)
    import re
    ma = re.search(r"(\d+)$", a)
    mb = re.search(r"(\d+)$", b)
    if not ma or not mb:
        return True
    return abs(int(ma.group(1)) - int(mb.group(1))) == 1


def _border_point(box, toward):
    """Return the point on ``box``'s border facing ``toward`` (a point), plus
    the (exitX, exitY) fraction for draw.io."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    tx, ty = toward
    dx, dy = tx - cx, ty - cy
    # Choose the dominant axis to pick a side (keeps connections orthogonal).
    if abs(dx) >= abs(dy):
        if dx >= 0:   # exit right
            return (x + w, cy), (1.0, 0.5)
        else:          # exit left
            return (x, cy), (0.0, 0.5)
    else:
        if dy >= 0:   # exit bottom
            return (cx, y + h), (0.5, 1.0)
        else:          # exit top
            return (cx, y), (0.5, 0.0)


def route_all_edges(edges, boxes, icon_ids, bounds,
                    max_iters: int = 4):
    """Route every edge with the obstacle-aware router, with bounded rework.

    edges: list of (source_id, target_id) tuples (only auto-routable ones).
    boxes: {id: (x,y,w,h)} for ALL nodes (icons + containers).
    icon_ids: set of ids that are icon obstacles (resources), not containers.
    bounds: (minx, miny, maxx, maxy) page bounds.

    Returns (routes, endpoints, conflicts):
      routes:    {ekey: [waypoints incl. endpoints]}
      endpoints: {ekey: (exit_xy, entry_xy)}
      conflicts: final list of unresolved conflicts.

    Rework strategy across iterations: obstacles start as icon+label boxes;
    each edge is routed longest-first (long edges claim channels first). If
    conflicts remain, clearance is increased and routing retried.
    """
    icon_boxes = {i: boxes[i] for i in icon_ids if i in boxes}

    # Obstacles = icon boxes inflated downward by the label band (labels render
    # below the icon), so routes avoid label text too.
    def _obstacles():
        obs = []
        for i, (x, y, w, h) in icon_boxes.items():
            obs.append((x, y, w, h + LABEL_BAND))
        return obs

    # Order edges longest-first (Manhattan distance between centres).
    def _dist(ek):
        s, t = ek
        if s not in boxes or t not in boxes:
            return 0
        sb, tb = boxes[s], boxes[t]
        return abs((sb[0] + sb[2] / 2) - (tb[0] + tb[2] / 2)) + \
               abs((sb[1] + sb[3] / 2) - (tb[1] + tb[3] / 2))

    ekeys = [tuple(e) for e in edges if e[0] in boxes and e[1] in boxes]
    ekeys.sort(key=_dist, reverse=True)

    clearance = CLEARANCE
    best_routes, best_endpoints, best_conflicts = {}, {}, None
    for _ in range(max_iters):
        router = Router(_obstacles(), bounds, clearance=clearance)
        routes, endpoints = {}, {}
        # Track how many edges already exit/enter a given (node, side) so we can
        # fan them out along that border and avoid shared/overlapping segments.
        exit_count: dict = {}
        # Cells already used by routed edges — passed as soft obstacles so later
        # nets spread into separate channels (general multi-net technique).
        used_cells: set = set()
        for ek in ekeys:
            s, t = ek
            sb, tb = boxes[s], boxes[t]
            scx, scy = sb[0] + sb[2] / 2, sb[1] + sb[3] / 2
            tcx, tcy = tb[0] + tb[2] / 2, tb[1] + tb[3] / 2
            start, exit_xy = _border_point(sb, (tcx, tcy))
            goal, entry_xy = _border_point(tb, (scx, scy))
            # Fan out multiple edges sharing the same source/target border.
            start, exit_xy = _fan_out(sb, start, exit_xy, s, exit_count)
            goal, entry_xy = _fan_out(tb, goal, entry_xy, t, exit_count)
            path = router.route(start, goal, soft=used_cells)
            if path is None:
                # Relax: retry on a router with reduced clearance so a congested
                # net can still find an orthogonal detour before giving up.
                for relaxed in (max(0, clearance - GRID), 0):
                    relaxed_router = Router(_obstacles(), bounds, clearance=relaxed)
                    path = relaxed_router.route(start, goal, soft=used_cells)
                    if path is not None:
                        break
            if path is None:
                path = [start, (goal[0], start[1]), goal]
            routes[ek] = path
            endpoints[ek] = (exit_xy, entry_xy)
            used_cells |= router.cells_for(path)
        conflicts = find_conflicts(routes, icon_boxes)
        if best_conflicts is None or len(conflicts) < len(best_conflicts):
            best_routes, best_endpoints, best_conflicts = routes, endpoints, conflicts
        if not conflicts:
            break
        clearance += GRID  # widen clearance and retry

    return best_routes, best_endpoints, best_conflicts or []


def _fan_out(box, point, xy_frac, node_id, counter):
    """Offset an endpoint along its border so multiple edges sharing the same
    (node, side) don't overlap. Returns (new_point, new_fraction)."""
    x, y, w, h = box
    fx, fy = xy_frac
    side = (node_id, fx, fy)
    n = counter.get(side, 0)
    counter[side] = n + 1
    if n == 0:
        return point, xy_frac
    # Alternate offsets: +1, -1, +2, -2 ... in grid steps, clamped to the border.
    step = ((n + 1) // 2) * GRID
    sign = 1 if n % 2 else -1
    off = sign * step
    px, py = point
    if fy in (0.0, 1.0) and fx == 0.5:      # top/bottom border → shift x
        nx = min(x + w - 4, max(x + 4, px + off))
        new_frac = (round((nx - x) / w, 2), fy)
        return (nx, py), new_frac
    if fx in (0.0, 1.0) and fy == 0.5:      # left/right border → shift y
        ny = min(y + h - 4, max(y + 4, py + off))
        new_frac = (fx, round((ny - y) / h, 2))
        return (px, ny), new_frac
    return point, xy_frac

