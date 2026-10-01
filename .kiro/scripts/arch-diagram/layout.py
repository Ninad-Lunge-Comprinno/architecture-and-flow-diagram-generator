"""House-style grid layout engine.

Implements the firm's architecture layout (see references/house-style.md):

    Outer border (encloses the title block)
    AWS Cloud
      Global row  (centred, top of cloud): CloudFront, S3, IAM, Route 53
      Ingress band (horizontal, between global row and region):
          External actors (Users, Mobile) sit LEFT of the cloud.
          Ingress-path services (Shield, WAF, ALB, APIGW) are placed
          LEFT-TO-RIGHT in traffic order inside the cloud.
          WAF and ALB are SIDE-BY-SIDE at the same y level.
          IGW straddles the left VPC border at AZ-1 centre.
      Region
        region-shared row (centred):  ACM, Cognito, Lambda, ECR, …
        VPC
          AZ rows (horizontal): public / app / db subnets + compute lanes

Layout philosophy
-----------------
Landscape-first: the diagram must be WIDER than it is tall (≥1.3:1 ratio).
The ingress band is HORIZONTAL rather than a vertical left strip, which is
the main structural change that achieves landscape orientation.

The ingress band sits inside the AWS Cloud boundary, between the global row
and the region box. External actors sit LEFT of the cloud, at the same y level
as their connected ingress service (e.g. Users aligns with Shield).

Edge services that are part of the ingress path (Shield, WAF, ALB, API Gateway)
are placed in the ingress band. IGW and non-ingress VPC-border services are
placed as before (straddling the VPC border at the appropriate AZ centre).

Spacing tokens
--------------
All layout distances are defined as constants at module level and are used
consistently throughout. Do not use magic numbers in the build() function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Spacing tokens — all layout distances derive from these.
# ---------------------------------------------------------------------------
ICON = 120
ICON_GAP = 60
LABEL_BAND = 50          # clearance below an icon for its wrapped label text
                          # (used ONLY for edge-routing waypoints, NOT sizing)
LABEL_WIDTH = 160

# Subnet sizing
SUBNET_MIN_W = 300
SUBNET_PAD_X = 40
SUBNET_PAD_TOP = 50
SUBNET_PAD_BOTTOM = 40
SUBNET_H = ICON + SUBNET_PAD_TOP + SUBNET_PAD_BOTTOM + 40  # 250px baseline

TIER_GAP = 80             # gap between subnet columns inside an AZ
AZ_INNER_PAD_X = 35      # x padding inside AZ box
AZ_INNER_PAD_TOP = 50    # y padding above subnets (for AZ label)
AZ_INNER_PAD_BOTTOM = 40 # y padding below subnets
AZ_GAP = 120             # gap between AZ rows

LANE_W = ICON + 140      # leaves room for the cluster icon and its header label
LANE_GAP = 50             # gap between lane columns
LANE_OVERHANG = 50        # lane top extends above first AZ

VPC_PAD_X = 65
VPC_PAD_TOP = 80
VPC_PAD_BOTTOM = 65
VPC_LEFT_MARGIN = 80      # space left of first AZ column

REGION_PAD_X = 85        # left/right padding inside region box
# Entry gutters: left columns that hold ingress services INSIDE their container.
#   Region gutter holds Shield + WAF (regional, outside the VPC).
#   VPC gutter holds ALB + API Gateway (traffic entry points inside the VPC).
# Each gutter fits two icons side-by-side plus padding on both sides.
REGION_ENTRY_GUTTER_W = 2 * ICON + 80 + 2 * ICON_GAP
VPC_ENTRY_GUTTER_W = 2 * ICON + 80 + 2 * ICON_GAP
ENTRY_PAIR_GAP = 80  # horizontal gap within a side-by-side ingress pair
REGION_SERVICES_Y = 65   # top of services grid within region
REGION_PAD_BOTTOM = 80   # bottom padding inside region
REGION_RES_GAP = 45      # gap between icons in the region services grid
REGION_ROW_ICONS = 9     # cap regional service rows at a readable width
GLOBAL_ROW_ICONS = 21
REGION_ROW_MAX_W = (REGION_ROW_ICONS * ICON
                    + (REGION_ROW_ICONS - 1) * REGION_RES_GAP)

CLOUD_PAD_X = 85         # right padding inside cloud
CLOUD_GLOBAL_Y = 65      # top of global icon row within cloud
CLOUD_PAD_BOTTOM = 85    # bottom padding inside cloud

# Routing corridor: how many pixels outside the region's right edge the
# routing corridor sits. Edges that need to travel from inside the region to
# a global service use this corridor to exit cleanly without crossing icons.
REGION_CORRIDOR_OFFSET = 30

# Ingress band — sits BETWEEN the global row and the region box, spanning
# the full cloud width. Items are spaced horizontally left-to-right.
INGRESS_BAND_PAD_X = 60  # x of first ingress item (cloud-relative)
INGRESS_ITEM_GAP = 80    # horizontal gap between consecutive ingress items
INGRESS_BAND_MARGIN = 25 # vertical gap between global row bottom and band y
INGRESS_BAND_BELOW_GAP = 25 # vertical gap between band bottom and region top
REGION_SERVICES_VPC_GAP = 25 # gap from regional service labels to VPC top

# WAF + ALB side-by-side offset (ALB is INGRESS_ITEM_GAP px right of WAF).
# They share the same y; the connector WAF→ALB goes horizontally.
WAF_ALB_PAIR_GAP = ICON + INGRESS_ITEM_GAP  # gap WAF right-edge to ALB left-edge

# External actors (outside cloud boundary, to the left)
ACTOR_LEFT_X = 60        # left edge of actor icons (page-absolute)
ACTOR_TO_CLOUD_GAP = 80  # gap from actor right edge to cloud left edge
ACTOR_BETWEEN_GAP = 80   # vertical gap between stacked actor icons

# Legacy constants (kept for edge-routing compatibility)
EDGE_GAP = 80
USER_GAP = 100

TITLE_W = 460
TITLE_H = 210
TITLE_MARGIN = 40
BORDER_MARGIN = 40
BORDER_LEFT_MARGIN = 60
BORDER_TOP_MARGIN = 20
BORDER_RIGHT_MARGIN = BORDER_MARGIN * 2
BORDER_BOTTOM_MARGIN = BORDER_RIGHT_MARGIN


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
    # Right corridor x: just right of the Region box, for routing region→VPC edges
    region_right_x: float = 0.0
    # Ingress band y-centre (page-absolute); used by routing code
    ingress_band_y: float = 0.0
    # VPC abs top (page coords): helps routing code distinguish above-VPC from in-VPC
    vpc_abs_top: float = 0.0

    def add(self, node: Node, abs_x: float, abs_y: float):
        self.nodes.append(node)
        self.abs_boxes[node.node_id] = (abs_x, abs_y, node.width, node.height)


def _subnet_width(n_resources: int, cols: int = 0, is_db_subnet: bool = False) -> float:
    """Compute subnet width for n icons in a grid.

    If is_db_subnet=True, use single-row layout (all icons horizontal).
    Otherwise, use 2-column layout.
    """
    n = max(1, n_resources)
    if cols == 0:
        cols = n if is_db_subnet else 2
    effective_w = max(ICON, LABEL_WIDTH)
    grid_cols = min(cols, n)
    content = grid_cols * effective_w + (grid_cols - 1) * ICON_GAP
    return max(SUBNET_MIN_W, content + 2 * SUBNET_PAD_X)


def _subnet_height(n_resources: int, cols: int = 0, is_db_subnet: bool = False) -> float:
    """Compute subnet height for n icons in a grid."""
    n = max(0, n_resources)
    if n == 0:
        return SUBNET_H
    if cols == 0:
        cols = n if is_db_subnet else 2
    rows = (n + cols - 1) // cols
    grid_h = rows * ICON + (rows - 1) * ICON_GAP
    return max(SUBNET_H, grid_h + SUBNET_PAD_TOP + SUBNET_PAD_BOTTOM)


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

    # All region services render in the region services grid.
    grid_services = region.get("services", []) or []

    # ---- Tier widths (uniform across AZs) and per-AZ heights ---------------
    def _az_res(az, tier):
        return (az.get(tier) or {}).get("resources", []) or []

    pub_w = max((_subnet_width(len(_az_res(az, "public_subnet")))
                 for az in azs), default=SUBNET_MIN_W)
    db_w = max((_subnet_width(len(_az_res(az, "db_subnet")), is_db_subnet=True)
                for az in azs), default=SUBNET_MIN_W)

    pub_h_by_az = {az["id"]: _subnet_height(len(_az_res(az, "public_subnet"))) for az in azs}
    app_h_by_az = {az["id"]: _subnet_height(len(_az_res(az, "app_subnet"))) for az in azs}
    db_h_by_az  = {az["id"]: _subnet_height(len(_az_res(az, "db_subnet")), is_db_subnet=True) for az in azs}

    def _az_row_height(az):
        aid = az["id"]
        return AZ_INNER_PAD_TOP + max(pub_h_by_az[aid], app_h_by_az[aid],
                                      db_h_by_az[aid]) + AZ_INNER_PAD_BOTTOM

    az_row_h_by_az = {az["id"]: _az_row_height(az) for az in azs}
    app_h_max = max(app_h_by_az.values(), default=SUBNET_H)
    lanes_w = (len(groups) * LANE_W + max(0, len(groups) - 1) * LANE_GAP) if groups else 0
    app_res_w = max((_subnet_width(len((az.get("app_subnet") or {}).get("resources", [])))
                     for az in azs), default=SUBNET_MIN_W)
    app_w = max(lanes_w + 2 * SUBNET_PAD_X, app_res_w, SUBNET_MIN_W)

    # ---- AZ column offsets (relative to AZ content origin) ---------------
    col_pub_x = AZ_INNER_PAD_X
    col_app_x = col_pub_x + pub_w + TIER_GAP
    col_db_x = col_app_x + app_w + TIER_GAP
    az_content_w = col_db_x + db_w + AZ_INNER_PAD_X

    # ---- VPC geometry ----------------------------------------------------
    # The VPC gets a LEFT ENTRY GUTTER holding ALB + API Gateway (traffic entry
    # points that live inside the VPC). AZ content is shifted right by the
    # gutter width so the entry icons have their own readable column.
    has_vpc_gutter = any(r.get("service") in
                         {"application_load_balancer", "network_load_balancer",
                          "api_gateway"}
                         for r in (page.get("edge", []) or []))
    vpc_gutter_w = VPC_ENTRY_GUTTER_W if has_vpc_gutter else 0
    vpc_content_x = vpc_gutter_w + VPC_LEFT_MARGIN
    az_y: dict[str, float] = {}
    y = VPC_PAD_TOP
    for az in azs:
        az_y[az["id"]] = y
        y += az_row_h_by_az[az["id"]] + AZ_GAP
    vpc_content_h = (y - AZ_GAP) if azs else ICON
    vpc_width = vpc_content_x + az_content_w + VPC_PAD_X
    vpc_height = vpc_content_h + VPC_PAD_BOTTOM

    # Balance regional services across readable rows. The row count follows
    # the actual service count and the available region width; the final rows
    # differ by at most one icon and are centered within the same grid.
    n_services = len(grid_services)
    service_content_w = vpc_width
    service_row_w = min(REGION_ROW_MAX_W, service_content_w)
    service_row_capacity = max(
        1, min(REGION_ROW_ICONS,
               int((service_row_w + REGION_RES_GAP) // (ICON + REGION_RES_GAP))),
    )
    service_row_capacity = min(service_row_capacity, n_services) if n_services else 1
    n_service_rows = ((n_services + service_row_capacity - 1) // service_row_capacity
                      if n_services else 1)
    row_pitch = ICON + LABEL_BAND + REGION_RES_GAP
    services_block_h = n_service_rows * row_pitch
    dynamic_region_pad_top = REGION_SERVICES_Y
    if n_services:
        dynamic_region_pad_top += (
            services_block_h - REGION_RES_GAP + REGION_SERVICES_VPC_GAP
        )

    # ---- Region dimensions -----------------------------------------------
    # Shield and WAF are global services in the AWS Cloud, before the Region.
    edge_list = page.get("edge", []) or []
    outside_region_items = [r for service in ("shield", "waf")
                            for r in edge_list if r.get("service") == service]
    outside_region_w = (len(outside_region_items) * ICON
                        + max(0, len(outside_region_items) - 1) * ICON_GAP)
    cloud_region_x = max(INGRESS_BAND_PAD_X, CLOUD_PAD_X)
    if outside_region_items:
        cloud_region_x += outside_region_w + REGION_PAD_X // 2

    # The region must be wide enough for the services row AND the gutter+VPC.
    icons_per_row = service_row_capacity if n_services else 0
    services_row_w = (icons_per_row * ICON + max(0, icons_per_row - 1) * REGION_RES_GAP
                      if icons_per_row else 0)
    region_width = max(vpc_width + 2 * REGION_PAD_X,
                       services_row_w + 2 * REGION_PAD_X)
    region_x = 0               # region is left-flush inside the cloud (we add padding in cloud)
    region_y = dynamic_region_pad_top  # VPC starts at this y within region
    region_height = dynamic_region_pad_top + vpc_height + REGION_PAD_BOTTOM

    # ---- Global services row width for cloud sizing ----------------------
    global_row_list = page.get("global", []) or []
    n_global = len(global_row_list)
    icons_per_global_row = min(n_global, GLOBAL_ROW_ICONS) if n_global else 0
    global_row_w = (icons_per_global_row * ICON + max(0, icons_per_global_row - 1) * REGION_RES_GAP
                    if icons_per_global_row else 0)

    # ---- Ingress classification ------------------------------------------
    # New placement model (see house-style):
    #   actors (users/devices)        -> OUTSIDE the cloud (left)
    #   IGW                           -> straddles the left VPC border
    #   Shield, WAF                   -> AWS Cloud lane before the Region
    #   ALB, API Gateway              -> VPC ENTRY GUTTER (inside the VPC),
    #                                     side-by-side; APIGW aligns near Lambda
    #   any other edge items          -> horizontal band above the Region
    actor_services_set = {"user", "users", "mobile_client", "iot_device"}
    igw_svc = "internet_gateway"
    region_gutter_services = {"shield", "waf"}
    vpc_gutter_services = {"application_load_balancer", "network_load_balancer",
                           "api_gateway"}

    actor_items = [r for r in edge_list if r.get("service") in actor_services_set]
    igw_item    = next((r for r in edge_list if r.get("service") == igw_svc), None)
    region_gutter_items = outside_region_items
    vpc_gutter_items = [r for r in edge_list
                        if r.get("service") in vpc_gutter_services]
    # Anything left over (e.g. a cloudfront placed in edge) stays in the band.
    _classified = (actor_services_set | {igw_svc}
                   | region_gutter_services | vpc_gutter_services)
    ingress_items = [r for r in edge_list
                     if r.get("service") not in _classified]

    # Named lookups for pairing / edge alignment.
    shield_item = next((r for r in region_gutter_items if r.get("service") == "shield"), None)
    waf_item    = next((r for r in region_gutter_items if r.get("service") == "waf"), None)
    alb_item    = next((r for r in vpc_gutter_items
                        if r.get("service") in ("application_load_balancer",
                                                "network_load_balancer")), None)
    apigw_item  = next((r for r in vpc_gutter_items if r.get("service") == "api_gateway"), None)

    # Remaining band items (rare) keep the old horizontal-band behaviour.
    _ingress_order = ["cloudfront"]
    def _ingress_sort_key(r):
        svc = r.get("service", "")
        try:
            return _ingress_order.index(svc)
        except ValueError:
            return len(_ingress_order)  # unknown items go after the chain
    ingress_items = sorted(ingress_items, key=_ingress_sort_key)

    # Band now holds only leftover edge items (not shield/waf/alb/apigw), placed
    # left-to-right. Shield/WAF and ALB/APIGW are positioned on the ingress row.
    ingress_x_offsets: dict[str, float] = {}
    cur_x = 0.0
    for item in ingress_items:
        ingress_x_offsets[item["id"]] = cur_x
        cur_x += ICON + INGRESS_ITEM_GAP

    ingress_band_w = max(cur_x - INGRESS_ITEM_GAP, ICON) if ingress_items else 0

    # ---- Cloud dimensions ------------------------------------------------
    # Global row height
    global_row_h = (ICON + LABEL_BAND) if global_row_list else 0
    # Ingress band height (only leftover band items, if any)
    ingress_band_h = (ICON + LABEL_BAND) if ingress_items else 0

    # Vertical layout of cloud content (top to bottom):
    # [CLOUD_GLOBAL_Y]    global row
    # [+INGRESS_BAND_MARGIN]  ingress band (leftover items only)
    # [+INGRESS_BAND_BELOW_GAP] region top
    cloud_global_y = CLOUD_GLOBAL_Y
    cloud_ingress_y = cloud_global_y + global_row_h + INGRESS_BAND_MARGIN
    cloud_region_y  = cloud_ingress_y + ingress_band_h + INGRESS_BAND_BELOW_GAP

    # ---- Cloud width: fit contents without a duplicated right-side gutter --
    # Centering the VPC in the cloud duplicates the region's own whitespace on
    # the right, leaving a wide empty strip in diagrams with entry gutters.
    # Minimum cloud left padding must still fit the region-services row and any
    # leftover band, which are left-flush at cloud_region_x.
    min_side = max(INGRESS_BAND_PAD_X, CLOUD_PAD_X)
    cloud_content_left = cloud_region_x  # leftover band / global row share this origin

    cloud_width_min = max(
        cloud_region_x + region_width + CLOUD_PAD_X,
        cloud_content_left + global_row_w + CLOUD_PAD_X,
        cloud_content_left + ingress_band_w + CLOUD_PAD_X,
    )
    cloud_width = cloud_width_min
    cloud_height = cloud_region_y + region_height + CLOUD_PAD_BOTTOM

    # cloud_x: must leave room for actors on the left
    n_actors = len(actor_items) if actor_items else 0
    cloud_x = ACTOR_LEFT_X + ICON + ACTOR_TO_CLOUD_GAP
    cloud_y = TITLE_H + TITLE_MARGIN

    # ---- Title block -----------------------------------------------------
    lo.add(Node("__title", "title", "1", cloud_x, 0, TITLE_W, TITLE_H, label=None),
           cloud_x, 0)

    # ---- Cloud -----------------------------------------------------------
    lo.add(Node("cloud", "cloud", "1", cloud_x, cloud_y, cloud_width, cloud_height,
                label=page.get("cloud_label", "AWS Cloud")),
           cloud_x, cloud_y)

    # ---- Global services row (centred within cloud) ----------------------
    if global_row_list:
        row_w = len(global_row_list) * ICON + (len(global_row_list) - 1) * REGION_RES_GAP
        gx = cloud_content_left + max(0, (region_width - row_w) / 2)
        for res in global_row_list:
            n = Node(res["id"], "resource", "cloud", gx, cloud_global_y, ICON, ICON,
                     provider=res.get("provider", default_provider),
                     service=res["service"], label=res.get("label"))
            lo.add(n, cloud_x + gx, cloud_y + cloud_global_y)
            gx += ICON + REGION_RES_GAP

    # ---- Ingress band (horizontal strip) ---------------------------------
    # All ingress-path services are placed LEFT-TO-RIGHT at y = cloud_ingress_y.
    # WAF and ALB share the same y (side-by-side). APIGW is placed after ALB.
    ingress_band_abs_y = cloud_y + cloud_ingress_y + ICON / 2   # y-centre of band icons

    for item in ingress_items:
        iid = item["id"]
        ix = cloud_content_left + ingress_x_offsets.get(iid, 0)
        iy = cloud_ingress_y     # y within cloud
        n = Node(iid, "resource", "cloud", ix, iy, ICON, ICON,
                 provider=item.get("provider", default_provider),
                 service=item["service"], label=item.get("label"))
        lo.add(n, cloud_x + ix, cloud_y + iy)

    lo.ingress_band_y = ingress_band_abs_y

    # ---- Region ----------------------------------------------------------
    region_abs_x = cloud_x + cloud_region_x
    region_abs_y = cloud_y + cloud_region_y
    lo.add(Node("region", "region", "cloud", cloud_region_x, cloud_region_y,
                region_width, region_height, label=region.get("label", "Region")),
           region_abs_x, region_abs_y)

    # ---- Region-shared services rows (balanced, width-aware rows) ----------
    services = grid_services
    if services:
        content_w_r = region_width - 2 * REGION_PAD_X
        row_y = REGION_SERVICES_Y
        row_count = (len(services) + service_row_capacity - 1) // service_row_capacity
        base, extra = divmod(len(services), row_count)
        row_start = 0
        for row_index in range(row_count):
            row_size = base + (1 if row_index < extra else 0)
            row = services[row_start:row_start + row_size]
            row_start += row_size
            row_w = len(row) * ICON + (len(row) - 1) * REGION_RES_GAP
            rx = REGION_PAD_X + max(0, (content_w_r - row_w) / 2)
            for res in row:
                n = Node(res["id"], "resource", "region", rx, row_y, ICON, ICON,
                         provider=res.get("provider", default_provider),
                         service=res["service"], label=res.get("label"))
                lo.add(n, region_abs_x + rx, region_abs_y + row_y)
                rx += ICON + REGION_RES_GAP
            row_y += ICON + LABEL_BAND + REGION_RES_GAP

    # ---- VPC -------------------------------------------------------------
    vpc_region_x = REGION_PAD_X
    vpc_region_y = region_y   # = dynamic_region_pad_top (VPC y within region)
    lo.add(Node("vpc", "vpc", "region", vpc_region_x, vpc_region_y, vpc_width, vpc_height,
                label=vpc.get("label", "VPC")),
           region_abs_x + vpc_region_x, region_abs_y + vpc_region_y)
    vpc_abs_x = region_abs_x + vpc_region_x
    vpc_abs_y = region_abs_y + vpc_region_y
    lo.vpc_abs_top = vpc_abs_y

    # ---- Ingress row alignment -------------------------------------------
    # Align the ingress chain (Shield/WAF before the Region, ALB in the VPC
    # gutter) to the MIDDLE AZ's vertical centre, and API Gateway to the AZ
    # above it. This makes Users→Shield→WAF→ALB a single straight horizontal
    # line and lets ALB enter the compute cluster cleanly through the AZ gap
    # (matching the house-style reference). Falls back to the VPC top band when
    # there are no AZ rows.
    if azs:
        mid_idx = len(azs) // 2
        mid_aid = azs[mid_idx]["id"]
        ingress_row_cy = vpc_region_y + az_y[mid_aid] + az_row_h_by_az[mid_aid] / 2
        # API Gateway aligns to the AZ above the middle (or the middle itself
        # when there is only one AZ).
        above_idx = max(0, mid_idx - 1)
        above_aid = azs[above_idx]["id"]
        apigw_row_cy = vpc_region_y + az_y[above_aid] + az_row_h_by_az[above_aid] / 2
    else:
        ingress_row_cy = vpc_region_y + VPC_PAD_TOP + ICON / 2
        apigw_row_cy = ingress_row_cy
    ingress_row_y = ingress_row_cy - ICON / 2          # top-left y of ingress icons
    apigw_row_y = apigw_row_cy - ICON / 2

    # ---- Shield/WAF outside the Region -----------------------------------
    # Their reserved cloud lane ends before the Region border, leaving a clear
    # gap before the IGW, which straddles the VPC border.
    if region_gutter_items:
        pair = [shield_item, waf_item]
        pair = [p for p in pair if p is not None]
        if not pair:
            pair = region_gutter_items  # fall back to spec order
        gutter_cy = ingress_row_y
        for slot_i, item in enumerate(pair):
            gx = cloud_region_x - (outside_region_w + REGION_PAD_X // 2) + slot_i * (ICON + ICON_GAP)
            cloud_y_rel = cloud_region_y + gutter_cy
            n = Node(item["id"], "resource", "cloud", gx, cloud_y_rel, ICON, ICON,
                     provider=item.get("provider", default_provider),
                     service=item["service"], label=item.get("label"))
            lo.add(n, cloud_x + gx, cloud_y + cloud_y_rel)

    # ---- VPC ENTRY GUTTER: ALB (AZ gap) + API Gateway (AZ1 centre) --------
    # Both icons are horizontally CENTRED in the VPC left-gutter column so they
    # sit visually "on" the VPC left edge rather than hugging its inner wall.
    # ALB aligns to the first AZ-gap corridor (the natural entry point for the
    # compute cluster). APIGW aligns to AZ1 centre (one row above ALB).
    if vpc_gutter_items:
        gutter_x = (vpc_gutter_w - ICON) / 2        # centre of gutter column
        if alb_item is not None:
            n = Node(alb_item["id"], "resource", "vpc", gutter_x,
                     ingress_row_y - vpc_region_y, ICON, ICON,
                     provider=alb_item.get("provider", default_provider),
                     service=alb_item["service"], label=alb_item.get("label"))
            lo.add(n, vpc_abs_x + gutter_x,
                   region_abs_y + ingress_row_y)
        if apigw_item is not None:
            n = Node(apigw_item["id"], "resource", "vpc", gutter_x,
                     apigw_row_y - vpc_region_y, ICON, ICON,
                     provider=apigw_item.get("provider", default_provider),
                     service=apigw_item["service"], label=apigw_item.get("label"))
            lo.add(n, vpc_abs_x + gutter_x,
                   region_abs_y + apigw_row_y)
        # Any other vpc-gutter items (rare) stack below ALB, centred in the gutter.
        placed = {i["id"] for i in (alb_item, apigw_item) if i}
        extra_y = ingress_row_y - vpc_region_y + ICON + ICON_GAP
        for item in vpc_gutter_items:
            if item["id"] in placed:
                continue
            n = Node(item["id"], "resource", "vpc", gutter_x, extra_y, ICON, ICON,
                     provider=item.get("provider", default_provider),
                     service=item["service"], label=item.get("label"))
            lo.add(n, vpc_abs_x + gutter_x, vpc_abs_y + extra_y)
            extra_y += ICON + ICON_GAP

    # ---- AZ rows + subnets -----------------------------------------------
    for az in azs:
        aid = az["id"]
        ay = az_y[aid]
        az_w = az_content_w
        az_row_h = az_row_h_by_az[aid]
        lo.add(Node(aid, "az", "vpc", vpc_content_x, ay, az_w, az_row_h,
                    label=az.get("label", aid)),
               vpc_abs_x + vpc_content_x, vpc_abs_y + ay)
        az_abs_x = vpc_abs_x + vpc_content_x
        az_abs_y = vpc_abs_y + ay
        tier_heights = {"public_subnet": pub_h_by_az[aid],
                        "app_subnet": app_h_by_az[aid],
                        "db_subnet": db_h_by_az[aid]}
        for tier, col_x, w in (("public_subnet", col_pub_x, pub_w),
                               ("app_subnet", col_app_x, app_w),
                               ("db_subnet", col_db_x, db_w)):
            subnet = az.get(tier)
            if subnet:
                th = tier_heights[tier]
                _emit_subnet(lo, subnet, tier, parent=aid,
                             rel_x=col_x, rel_y=AZ_INNER_PAD_TOP,
                             width=w, height=th,
                             abs_x=az_abs_x + col_x,
                             abs_y=az_abs_y + AZ_INNER_PAD_TOP,
                             default_provider=default_provider)

    # ---- VPC corridor x and region right corridor ------------------------
    lo.vpc_corridor_x = vpc_abs_x + VPC_LEFT_MARGIN / 2
    lo.region_right_x = region_abs_x + region_width + REGION_CORRIDOR_OFFSET

    # ---- AZ gap corridors + row bounds -----------------------------------
    az_mid_ys = []
    for i in range(len(azs) - 1):
        top_az = azs[i]["id"]
        bot_az = azs[i + 1]["id"]
        gap_top = vpc_abs_y + az_y[top_az] + az_row_h_by_az[top_az]
        gap_bot = vpc_abs_y + az_y[bot_az]
        lo.az_gaps.append((gap_top, gap_bot))
    for az in azs:
        row_top = vpc_abs_y + az_y[az["id"]]
        row_bot = row_top + az_row_h_by_az[az["id"]]
        lo.az_rows.append((row_top, row_bot))
        az_mid_ys.append((row_top + row_bot) / 2)

    # ---- Compute-group vertical lanes ------------------------------------
    if groups and azs:
        first_y = az_y[az_ids[0]] + AZ_INNER_PAD_TOP
        last_y  = az_y[az_ids[-1]] + AZ_INNER_PAD_TOP + app_h_by_az[az_ids[-1]]
        lane_top = first_y - LANE_OVERHANG
        az_last_bottom = az_y[az_ids[-1]] + az_row_h_by_az[az_ids[-1]] - AZ_INNER_PAD_BOTTOM
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

    # ---- IGW: straddle the VPC border in the horizontal ingress row ------
    if igw_item:
        igw_rel_x = -ICON / 2
        igw_rel_y = ingress_row_y - vpc_region_y
        n = Node(igw_item["id"], "resource", "vpc", igw_rel_x, igw_rel_y, ICON, ICON,
                 provider=igw_item.get("provider", default_provider),
                 service="internet_gateway", label=igw_item.get("label"))
        lo.add(n, vpc_abs_x + igw_rel_x, region_abs_y + ingress_row_y)

    # ---- External actors (left of cloud) ---------------------------------
    # Actors stack vertically at ACTOR_LEFT_X. They centre on the ingress entry
    # row they connect to: the outside-Region Shield/WAF lane when present, else the
    # leftover band. This keeps the users→shield/waf edge short and horizontal.
    if region_gutter_items:
        entry_cy = region_abs_y + ingress_row_cy
    else:
        entry_cy = cloud_y + cloud_ingress_y + ICON / 2
    if actor_items:
        n_act = len(actor_items)
        actors_total_h = n_act * ICON + (n_act - 1) * ACTOR_BETWEEN_GAP
        actor_y_start = entry_cy - actors_total_h / 2
        for i, res in enumerate(actor_items):
            ay = actor_y_start + i * (ICON + ACTOR_BETWEEN_GAP)
            n = Node(res["id"], "resource", "1", ACTOR_LEFT_X, ay, ICON, ICON,
                     provider=res.get("provider", default_provider),
                     service=res["service"], label=res.get("label"))
            lo.add(n, ACTOR_LEFT_X, ay)
    else:
        # Legacy: single "user" item
        user_item = next((r for r in edge_list if r.get("service") == "user"), None)
        if user_item:
            band_y = entry_cy - ICON / 2
            n = Node(user_item["id"], "resource", "1", ACTOR_LEFT_X, band_y, ICON, ICON,
                     provider=user_item.get("provider", default_provider),
                     service="user", label=user_item.get("label"))
            lo.add(n, ACTOR_LEFT_X, band_y)

    # ---- Overall extents + border ----------------------------------------
    content_right  = cloud_x + cloud_width
    content_bottom = cloud_y + cloud_height
    lo.width  = content_right
    lo.height = content_bottom
    lo.border_x = ACTOR_LEFT_X - BORDER_LEFT_MARGIN
    lo.border_y = 0 - BORDER_TOP_MARGIN
    lo.border_w = (content_right + BORDER_RIGHT_MARGIN) - lo.border_x
    lo.border_h = (content_bottom + BORDER_BOTTOM_MARGIN) - lo.border_y
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
    if kind == "db_subnet":
        default_cols = n
    else:
        default_cols = 2
    actual_cols = min(int(subnet.get("cols", default_cols)), n)
    rows = (n + actual_cols - 1) // actual_cols
    grid_w = actual_cols * ICON + (actual_cols - 1) * ICON_GAP
    grid_h = rows * ICON + (rows - 1) * ICON_GAP
    start_x = max(SUBNET_PAD_X, (width - grid_w) / 2)
    for idx, res in enumerate(resources):
        col_i = idx % actual_cols
        row_i = idx // actual_cols
        rx = start_x + col_i * (ICON + ICON_GAP)
        ry = SUBNET_PAD_TOP + row_i * (ICON + ICON_GAP)
        node = Node(res["id"], "resource", subnet["id"], rx, ry, ICON, ICON,
                    provider=res.get("provider", default_provider),
                    service=res["service"], label=res.get("label"))
        lo.add(node, abs_x + rx, abs_y + ry)


def all_ids(lo: Layout) -> set:
    return {n.node_id for n in lo.nodes}
