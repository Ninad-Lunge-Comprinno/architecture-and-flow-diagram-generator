"""House-style grid layout engine.

Implements the firm's architecture layout (see references/house-style.md):

    Outer border (encloses the title block)
    AWS Cloud
      global row (centred, outside region): CloudFront, S3, IAM, Route 53
      edge strip (left, inside cloud):       WAF, CloudFront, ALB
        (a `user` renders just OUTSIDE the cloud)
      Region
        region-shared row (centred):         ACM, Secrets, ... + CI/CD icons
        VPC
          IGW on left VPC border aligned to AZ-1 centre
          AZ rows (horizontal repeated):     az1 / az2 / az3, each with
                                               public-subnet (green)
                                               app-subnet   (blue)  <- lanes
                                               db-subnet    (blue)
          compute-group lanes (vertical, span ALL AZ rows)
      edge strip icons aligned to AZ centres:
        IGW  aligned to AZ-1 centre
        ALB  aligned to middle-AZ centre (or VPC vertical midpoint)

Layout is produced as a flat node list with explicit `parent` per node. Absolute
page coords for every node are stored in `lo.abs_boxes` for edge routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
ICON = 120
ICON_GAP = 60
LABEL_BAND = 50          # clearance below an icon for its wrapped label text
                          # (used ONLY for edge-routing waypoints, NOT sizing)
LABEL_WIDTH = 160

# Subnet sizing: keep original compact height (label overflows outside the cell
# which is how draw.io renders verticalLabelPosition=bottom — expected behaviour)
SUBNET_MIN_W = 300
SUBNET_PAD_X = 40
SUBNET_PAD_TOP = 50
SUBNET_PAD_BOTTOM = 40
SUBNET_H = ICON + SUBNET_PAD_TOP + SUBNET_PAD_BOTTOM   # compact — 210px

TIER_GAP = 80
AZ_INNER_PAD_X = 35
AZ_INNER_PAD_TOP = 50
AZ_INNER_PAD_BOTTOM = 40
AZ_GAP = 120

LANE_W = ICON + 2 * 30
LANE_GAP = 40
LANE_OVERHANG = 20

VPC_PAD_X = 65
VPC_PAD_TOP = 80
VPC_PAD_BOTTOM = 65
VPC_LEFT_MARGIN = 80

REGION_PAD_X = 85
REGION_SERVICES_Y = 65    # top of services icon row within region
REGION_PAD_TOP = 240
REGION_PAD_BOTTOM = 80
REGION_RES_GAP = 45

CLOUD_PAD_X = 85
CLOUD_GLOBAL_Y = 65       # top of global icon row within cloud
CLOUD_PAD_TOP = 240
CLOUD_PAD_BOTTOM = 85
CLOUD_LEFT_EDGE = 190

EDGE_GAP = 80
USER_GAP = 100

TITLE_W = 460
TITLE_H = 210
TITLE_MARGIN = 40
BORDER_MARGIN = 40


@dataclass
class Node:
    node_id: str
    kind: str
    parent: str
    x: float
    y: float
    width: float
    height: float
    provider: Optional[str] = None
    service: Optional[str] = None
    label: Optional[str] = None


@dataclass
class Layout:
    nodes: list[Node] = field(default_factory=list)
    abs_boxes: dict = field(default_factory=dict)
    width: float = 0.0
    height: float = 0.0
    border_x: float = 0.0
    border_y: float = 0.0
    border_w: float = 0.0
    border_h: float = 0.0
    # AZ gap corridors: list of (y_top, y_bottom) in page coords for routing
    az_gaps: list[tuple[float, float]] = field(default_factory=list)
    # AZ rows: list of (abs_top, abs_bottom) for each AZ row in page coords
    az_rows: list[tuple[float, float]] = field(default_factory=list)
    # Left corridor x inside the VPC (between VPC left edge and public subnets)
    vpc_corridor_x: float = 0.0

    def add(self, node: Node, abs_x: float, abs_y: float):
        self.nodes.append(node)
        self.abs_boxes[node.node_id] = (abs_x, abs_y, node.width, node.height)


def _subnet_width(n_resources: int) -> float:
    n = max(1, n_resources)
    # A wrapped label (labelWidth=160) can be wider than the 120px icon, so the
    # effective per-resource footprint is max(ICON, LABEL_WIDTH). This prevents
    # 2-line labels (e.g. "RDS Primary") from overflowing the subnet box.
    effective_w = max(ICON, LABEL_WIDTH)
    content = n * effective_w + (n - 1) * ICON_GAP
    return max(SUBNET_MIN_W, content + 2 * SUBNET_PAD_X)


def _center_row(items_w: float, container_w: float, min_x: float) -> float:
    """Return the x-start so a row of `items_w` is centred in `container_w`."""
    return max(min_x, (container_w - items_w) / 2)


def build(page: dict, default_provider: str = "aws") -> Layout:
    lo = Layout()
    region = page.get("region", {}) or {}
    vpc = region.get("vpc", {}) or {}
    azs = vpc.get("azs", []) or []
    groups = vpc.get("compute_groups", []) or []
    az_ids = [az["id"] for az in azs]

    # ---- tier widths (uniform per tier) ----------------------------------
    pub_w = max((_subnet_width(len((az.get("public_subnet") or {}).get("resources", [])))
                 for az in azs), default=SUBNET_MIN_W)
    db_w = max((_subnet_width(len((az.get("db_subnet") or {}).get("resources", [])))
                for az in azs), default=SUBNET_MIN_W)
    lanes_w = (len(groups) * LANE_W + max(0, len(groups) - 1) * LANE_GAP) if groups else 0
    app_res_w = max((_subnet_width(len((az.get("app_subnet") or {}).get("resources", [])))
                     for az in azs), default=SUBNET_MIN_W)
    app_w = max(lanes_w + 2 * SUBNET_PAD_X, app_res_w, SUBNET_MIN_W)

    # ---- AZ column offsets (relative to AZ content origin) ---------------
    col_pub_x = AZ_INNER_PAD_X
    col_app_x = col_pub_x + pub_w + TIER_GAP
    col_db_x = col_app_x + app_w + TIER_GAP
    az_content_w = col_db_x + db_w + AZ_INNER_PAD_X
    az_row_h = AZ_INNER_PAD_TOP + SUBNET_H + AZ_INNER_PAD_BOTTOM

    # ---- VPC geometry ----------------------------------------------------
    vpc_content_x = VPC_LEFT_MARGIN
    az_y = {}
    y = VPC_PAD_TOP
    for az in azs:
        az_y[az["id"]] = y
        y += az_row_h + AZ_GAP
    vpc_content_h = (y - AZ_GAP) if azs else ICON
    vpc_width = vpc_content_x + az_content_w + VPC_PAD_X
    vpc_height = vpc_content_h + VPC_PAD_BOTTOM

    # ---- region / cloud dimensions ---------------------------------------
    region_x = REGION_PAD_X
    region_y = REGION_PAD_TOP
    # Region must be wide enough for BOTH the VPC and its shared-services row.
    services_list = region.get("services", []) or []
    n_services = len(services_list)
    services_row_w = (n_services * ICON + max(0, n_services - 1) * REGION_RES_GAP
                      if n_services else 0)
    region_width = max(vpc_width + 2 * REGION_PAD_X,
                       services_row_w + 2 * REGION_PAD_X)
    region_height = REGION_PAD_TOP + vpc_height + REGION_PAD_BOTTOM

    cloud_region_x = CLOUD_LEFT_EDGE
    cloud_region_y = CLOUD_PAD_TOP
    # Cloud must be wide enough for BOTH the region and its global-services row.
    global_row_list = page.get("global", []) or []
    n_global = len(global_row_list)
    global_row_w = (n_global * ICON + max(0, n_global - 1) * REGION_RES_GAP
                    if n_global else 0)
    cloud_width = max(cloud_region_x + region_width + CLOUD_PAD_X,
                      CLOUD_LEFT_EDGE + global_row_w + CLOUD_PAD_X)
    cloud_height = CLOUD_PAD_TOP + region_height + CLOUD_PAD_BOTTOM

    cloud_x = USER_GAP + ICON + USER_GAP
    cloud_y = TITLE_H + TITLE_MARGIN

    # ---- title block -----------------------------------------------------
    lo.add(Node("__title", "title", "1", cloud_x, 0, TITLE_W, TITLE_H, label=None),
           cloud_x, 0)

    # ---- cloud -----------------------------------------------------------
    lo.add(Node("cloud", "cloud", "1", cloud_x, cloud_y, cloud_width, cloud_height,
                label=page.get("cloud_label", "AWS Cloud")),
           cloud_x, cloud_y)

    # ---- global services row (centred within cloud) ----------------------
    global_list = page.get("global", []) or []
    if global_list:
        row_w = len(global_list) * ICON + (len(global_list) - 1) * REGION_RES_GAP
        content_w = cloud_width - CLOUD_LEFT_EDGE - CLOUD_PAD_X
        gx = CLOUD_LEFT_EDGE + max(0, (content_w - row_w) / 2)
        for res in global_list:
            n = Node(res["id"], "resource", "cloud", gx, CLOUD_GLOBAL_Y, ICON, ICON,
                     provider=res.get("provider", default_provider),
                     service=res["service"], label=res.get("label"))
            lo.add(n, cloud_x + gx, cloud_y + CLOUD_GLOBAL_Y)
            gx += ICON + REGION_RES_GAP

    # ---- region ----------------------------------------------------------
    lo.add(Node("region", "region", "cloud", cloud_region_x, cloud_region_y,
                region_width, region_height, label=region.get("label", "Region")),
           cloud_x + cloud_region_x, cloud_y + cloud_region_y)
    region_abs_x = cloud_x + cloud_region_x
    region_abs_y = cloud_y + cloud_region_y

    # ---- region-shared services row (centred within region) --------------
    services = region.get("services", []) or []
    if services:
        row_w = len(services) * ICON + (len(services) - 1) * REGION_RES_GAP
        content_w_r = region_width - 2 * REGION_PAD_X
        rx = REGION_PAD_X + max(0, (content_w_r - row_w) / 2)
        for res in services:
            n = Node(res["id"], "resource", "region", rx, REGION_SERVICES_Y, ICON, ICON,
                     provider=res.get("provider", default_provider),
                     service=res["service"], label=res.get("label"))
            lo.add(n, region_abs_x + rx, region_abs_y + REGION_SERVICES_Y)
            rx += ICON + REGION_RES_GAP

    # ---- VPC -------------------------------------------------------------
    lo.add(Node("vpc", "vpc", "region", region_x, region_y, vpc_width, vpc_height,
                label=vpc.get("label", "VPC")),
           region_abs_x + region_x, region_abs_y + region_y)
    vpc_abs_x = region_abs_x + region_x
    vpc_abs_y = region_abs_y + region_y

    # ---- AZ rows + subnets -----------------------------------------------
    for az in azs:
        ay = az_y[az["id"]]
        az_w = az_content_w
        lo.add(Node(az["id"], "az", "vpc", vpc_content_x, ay, az_w, az_row_h,
                    label=az.get("label", az["id"])),
               vpc_abs_x + vpc_content_x, vpc_abs_y + ay)
        az_abs_x = vpc_abs_x + vpc_content_x
        az_abs_y = vpc_abs_y + ay
        for tier, col_x, w in (("public_subnet", col_pub_x, pub_w),
                               ("app_subnet", col_app_x, app_w),
                               ("db_subnet", col_db_x, db_w)):
            subnet = az.get(tier)
            if subnet:
                _emit_subnet(lo, subnet, tier, parent=az["id"],
                             rel_x=col_x, rel_y=AZ_INNER_PAD_TOP,
                             width=w, height=SUBNET_H,
                             abs_x=az_abs_x + col_x,
                             abs_y=az_abs_y + AZ_INNER_PAD_TOP,
                             default_provider=default_provider)

    # ---- VPC left corridor x (spine for fan-out routing) ----------------
    # This is the x in the space between the VPC left border and the public subnets,
    # used as the trunk of fan-out connections (e.g. ALB -> all 3 AZ targets).
    pub_abs_x = vpc_abs_x + vpc_content_x + AZ_INNER_PAD_X + col_pub_x
    lo.vpc_corridor_x = vpc_abs_x + VPC_LEFT_MARGIN / 2

    # ---- AZ gap corridors + row bounds (for edge routing) ---------------
    for i in range(len(azs) - 1):
        top_az = azs[i]["id"]
        bot_az = azs[i + 1]["id"]
        gap_top = vpc_abs_y + az_y[top_az] + az_row_h
        gap_bot = vpc_abs_y + az_y[bot_az]
        lo.az_gaps.append((gap_top, gap_bot))
    for az in azs:
        row_top = vpc_abs_y + az_y[az["id"]]
        row_bot = row_top + az_row_h
        lo.az_rows.append((row_top, row_bot))

    # ---- compute-group vertical lanes ------------------------------------
    if groups and azs:
        first_y = az_y[az_ids[0]] + AZ_INNER_PAD_TOP
        last_y = az_y[az_ids[-1]] + AZ_INNER_PAD_TOP + SUBNET_H
        lane_top = first_y - LANE_OVERHANG
        # Ensure the lane bottom does not overlap the last AZ's bottom border
        az_last_bottom = az_y[az_ids[-1]] + az_row_h - AZ_INNER_PAD_BOTTOM
        lane_bottom = min(last_y + LANE_OVERHANG, az_last_bottom - 5)
        lane_height = lane_bottom - lane_top
        lane_x0 = vpc_content_x + col_app_x + SUBNET_PAD_X
        lane_x = lane_x0
        for g in groups:
            span = g.get("azs", az_ids)
            lo.add(Node(g["id"], g.get("kind", "ecs_cluster"), "vpc",
                        lane_x, lane_top, LANE_W, lane_height, label=g.get("label")),
                   vpc_abs_x + lane_x, vpc_abs_y + lane_top)
            lane_abs_x = vpc_abs_x + lane_x
            lane_abs_y = vpc_abs_y + lane_top
            for az_id in az_ids:
                if az_id not in span:
                    continue
                node_id = f"{g['id']}-{az_id}"
                icon_rel_y = (az_y[az_id] + AZ_INNER_PAD_TOP + SUBNET_PAD_TOP) - lane_top
                icon_rel_x = (LANE_W - ICON) / 2
                lo.add(Node(node_id, "resource", g["id"],
                            icon_rel_x, icon_rel_y, ICON, ICON,
                            provider=default_provider,
                            service=g["node_service"], label=g.get("node_label")),
                       lane_abs_x + icon_rel_x, lane_abs_y + icon_rel_y)
            lane_x += LANE_W + LANE_GAP

    # ---- edge strip: aligned to AZ centres, IGW at VPC border -----------
    edge_list = page.get("edge", []) or []
    edge_inner_x = 40

    # Compute y-positions for edge icons based on AZ geometry:
    # - non-IGW, non-user items: placed at the vertical centres of each AZ row
    #   starting from AZ1. IGW aligns with AZ1 centre; ALB with middle-AZ centre.
    az_mid_ys = [vpc_abs_y + az_y[aid] + az_row_h / 2 for aid in az_ids]
    middle_az_y = az_mid_ys[len(az_mid_ys) // 2] if az_mid_ys else cloud_y + cloud_region_y + REGION_PAD_TOP + 200

    # Separate IGW and user; remaining strip items get y-positions anchored on ALB.
    strip_items = [r for r in edge_list if r.get("service") not in ("internet_gateway", "user")]
    igw_item = next((r for r in edge_list if r.get("service") == "internet_gateway"), None)
    user_item = next((r for r in edge_list if r.get("service") == "user"), None)

    # ALB anchors at the middle-AZ centre; other strip items space evenly around it.
    alb_svc = ("application_load_balancer", "network_load_balancer")
    alb_idx = next((i for i, r in enumerate(strip_items)
                    if r.get("service", "") in alb_svc), None)
    middle_az_mid = az_mid_ys[len(az_mid_ys) // 2] if az_mid_ys else cloud_y + 400

    if alb_idx is not None and az_mid_ys:
        # Place ALB at the first AZ gap midpoint so its connecting line goes
        # cleanly through the gap corridor (horizontal line at gap y).
        if lo.az_gaps:
            alb_anchor_y = (lo.az_gaps[0][0] + lo.az_gaps[0][1]) / 2
        else:
            alb_anchor_y = middle_az_mid
        y_alb = alb_anchor_y - ICON / 2
        item_ys = {alb_idx: y_alb}
        for i in range(alb_idx - 1, -1, -1):
            item_ys[i] = item_ys[i + 1] - ICON - EDGE_GAP
        for i in range(alb_idx + 1, len(strip_items)):
            item_ys[i] = item_ys[i - 1] + ICON + EDGE_GAP
    else:
        item_ys = {i: az_mid_ys[min(i, len(az_mid_ys)-1)] - ICON/2
                   for i in range(len(strip_items))}

    for idx, res in enumerate(strip_items):
        ey = item_ys[idx]
        n = Node(res["id"], "resource", "cloud", edge_inner_x, ey - cloud_y, ICON, ICON,
                 provider=res.get("provider", default_provider),
                 service=res["service"], label=res.get("label"))
        lo.add(n, cloud_x + edge_inner_x, ey)

    # IGW: align to AZ1 centre, straddling the left VPC border
    if igw_item:
        az1_mid_y = az_mid_ys[0] if az_mid_ys else vpc_abs_y + vpc_height / 2
        igw_rel_x = -ICON / 2  # straddle VPC left edge
        igw_rel_y = az1_mid_y - vpc_abs_y - ICON / 2
        n = Node(igw_item["id"], "resource", "vpc", igw_rel_x, igw_rel_y, ICON, ICON,
                 provider=igw_item.get("provider", default_provider),
                 service="internet_gateway", label=igw_item.get("label"))
        lo.add(n, vpc_abs_x + igw_rel_x, vpc_abs_y + igw_rel_y)

    # User: outside the cloud, at the same y as the first strip item (WAF/top item)
    if user_item:
        # Align with first strip item so they are on the same horizontal line
        first_strip_y = item_ys.get(0, az_mid_ys[0] - ICON / 2) if item_ys else cloud_y + 200
        user_y = first_strip_y
        n = Node(user_item["id"], "resource", "1", USER_GAP, user_y, ICON, ICON,
                 provider=user_item.get("provider", default_provider),
                 service="user", label=user_item.get("label"))
        lo.add(n, USER_GAP, user_y)

    # ---- overall extents + border ----------------------------------------
    content_right = cloud_x + cloud_width
    content_bottom = cloud_y + cloud_height
    lo.width = content_right
    lo.height = content_bottom
    left_most = min(USER_GAP, cloud_x)
    lo.border_x = left_most - BORDER_MARGIN
    lo.border_y = 0 - BORDER_MARGIN
    lo.border_w = (content_right + BORDER_MARGIN) - lo.border_x
    lo.border_h = (content_bottom + BORDER_MARGIN) - lo.border_y
    return lo


def _emit_subnet(lo: Layout, subnet: dict, kind: str, parent: str,
                 rel_x: float, rel_y: float, width: float, height: float,
                 abs_x: float, abs_y: float, default_provider: str):
    lo.add(Node(subnet["id"], kind, parent, rel_x, rel_y, width, height,
                label=subnet.get("label", subnet["id"])),
           abs_x, abs_y)
    resources = subnet.get("resources", []) or []
    n = len(resources)
    if n == 0:
        return
    # centre the icon row horizontally within the subnet
    row_w = n * ICON + (n - 1) * ICON_GAP
    start_x = max(SUBNET_PAD_X, (width - row_w) / 2)
    x = start_x
    for res in resources:
        node = Node(res["id"], "resource", subnet["id"], x, SUBNET_PAD_TOP, ICON, ICON,
                    provider=res.get("provider", default_provider),
                    service=res["service"], label=res.get("label"))
        lo.add(node, abs_x + x, abs_y + SUBNET_PAD_TOP)
        x += ICON + ICON_GAP


def all_ids(lo: Layout) -> set:
    return {n.node_id for n in lo.nodes}
