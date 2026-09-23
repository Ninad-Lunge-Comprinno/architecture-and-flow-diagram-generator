"""Tests for rendering polish: label band, centering, strokes, routing."""

import generate_diagram as gd
import layout
import shapes


# ---- label wrapping / band ------------------------------------------------
def test_icon_style_wraps_labels():
    style = shapes.get_shape("aws", "s3").style()
    assert "whiteSpace=wrap" in style
    assert "labelWidth=" in style


def test_label_band_is_routing_clearance_only():
    # LABEL_BAND is used for edge-routing clearance, NOT to inflate subnet height.
    # Subnets stay compact: SUBNET_H = ICON + PAD_TOP + PAD_BOTTOM.
    assert layout.LABEL_BAND == 50
    assert layout.SUBNET_H == layout.ICON + layout.SUBNET_PAD_TOP + layout.SUBNET_PAD_BOTTOM


# ---- centering ------------------------------------------------------------
def test_single_icon_centered_in_subnet():
    page = {
        "region": {"vpc": {"azs": [
            {"id": "az1",
             "public_subnet": {"id": "p1", "resources": [{"id": "nat", "service": "nat_gateway"}]},
             "db_subnet": {"id": "d1", "resources": [{"id": "rds", "service": "rds"}]}},
        ]}},
    }
    lo = layout.build(page, "aws")
    b = lo.abs_boxes
    px, py, pw, ph = b["p1"]
    nx, ny, nw, nh = b["nat"]
    # icon center aligns with subnet center (within a pixel)
    assert abs((nx + nw / 2) - (px + pw / 2)) <= 1.0


def test_two_icons_centered_group_in_subnet():
    page = {
        "region": {"vpc": {"azs": [
            {"id": "az1",
             "public_subnet": {"id": "p1", "resources": []},
             "db_subnet": {"id": "d1", "resources": [
                 {"id": "rds", "service": "rds"}, {"id": "cache", "service": "elasticache"}]}},
        ]}},
    }
    lo = layout.build(page, "aws")
    b = lo.abs_boxes
    dx, dy, dw, dh = b["d1"]
    rds = b["rds"]; cache = b["cache"]
    group_center = (rds[0] + (cache[0] + cache[2])) / 2
    assert abs(group_center - (dx + dw / 2)) <= 1.5


# ---- stroke widths --------------------------------------------------------
def test_container_dashed_border_2px():
    assert "strokeWidth=2" in shapes.get_container("region").style()
    assert "strokeWidth=2" in shapes.get_container("vpc").style()


def test_edge_stroke_4px():
    assert "strokeWidth=4" in gd.EDGE_STYLE


def test_outer_border_2px():
    d = gd.Diagram("P", "page-1")
    d.add_outer_border(0, 0, 100, 100, margin=0)
    cell = d.cells[-1]
    assert "strokeWidth=2" in cell.style


# ---- routing --------------------------------------------------------------
def test_route_prefers_side_when_horizontally_separated():
    src = (0, 0, 120, 120)
    tgt = (400, 10, 120, 120)   # clearly to the right
    exit_xy, entry_xy, wps = gd._route_edge(src, tgt, label_band=50)
    assert exit_xy == (1.0, 0.5)   # right side
    assert entry_xy == (0.0, 0.5)  # left side


def test_route_bottom_clears_label_band():
    src = (0, 0, 120, 120)
    tgt = (0, 400, 120, 120)   # directly below (column-aligned)
    exit_xy, entry_xy, wps = gd._route_edge(src, tgt, label_band=50)
    assert exit_xy == (0.5, 1.0)   # bottom exit
    # same-column: no waypoints needed (draw.io routes straight)
    assert wps == []


def test_route_top_clears_target_band():
    src = (0, 400, 120, 120)
    tgt = (0, 0, 120, 120)     # directly above (column-aligned)
    exit_xy, entry_xy, wps = gd._route_edge(src, tgt, label_band=50)
    assert exit_xy == (0.5, 0.0)   # top exit
    # column-aligned: no waypoints (draw.io routes straight)
    assert wps == []


def test_flow_page_edges_get_connection_points():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Polish"},
        "pages": [{
            "name": "Flow Diagram",
            "type": "flow",
            "nodes": [
                {"id": "u", "service": "user", "label": "Users"},
                {"id": "cf", "service": "cloudfront"},
                {"id": "alb", "service": "application_load_balancer"},
            ],
            "edges": [
                {"source": "u", "target": "cf", "label": "request"},
                {"source": "cf", "target": "alb", "label": "forward"},
            ],
        }],
    }
    mxfile = gd.build_document(spec)
    root = mxfile.find("diagram/mxGraphModel/root")
    edges = [c for c in root.findall("mxCell") if c.get("edge") == "1"]
    assert edges
    for e in edges:
        style = e.get("style", "")
        # Edges have connection points and 4px stroke
        assert "exitX=" in style and "entryX=" in style
        assert "strokeWidth=4" in style


def test_flow_page_nodes_wrap_labels():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Wrap"},
        "pages": [{
            "name": "Flow Diagram",
            "type": "flow",
            "nodes": [{"id": "rds", "service": "rds", "label": "RDS PostgreSQL Read-Replica"}],
            "edges": [],
        }],
    }
    mxfile = gd.build_document(spec)
    root = mxfile.find("diagram/mxGraphModel/root")
    icon = next(c for c in root.findall("mxCell") if c.get("id") == "rds")
    assert "whiteSpace=wrap" in icon.get("style", "")
    assert "labelWidth=" in icon.get("style", "")


# ---- fixes: label-aware sizing, content-based region width, routing --------
def test_subnet_width_accounts_for_label_width():
    # A single-resource subnet must be at least LABEL_WIDTH wide (label footprint
    # can be wider than the 120px icon).
    assert layout._subnet_width(1) >= layout.LABEL_WIDTH
    # Two resources with 2-line labels: 2*LABEL_WIDTH + one ICON_GAP is the
    # minimum content; the subnet must be at least that wide.
    two = layout._subnet_width(2)
    assert two >= 2 * layout.LABEL_WIDTH + layout.ICON_GAP


def test_region_width_covers_services_row():
    # A page with a long services row (more icons than the VPC is wide) must
    # produce a region box at least as wide as the services row + padding.
    services = [{"id": f"svc{i}", "service": "cloudwatch_2"} for i in range(9)]
    page = {
        "global": [],
        "edge": [{"id": "igw", "service": "internet_gateway"}],
        "region": {
            "label": "r",
            "services": services,
            "vpc": {
                "label": "v",
                "azs": [{
                    "id": "az1",
                    "public_subnet": {"id": "p1", "resources": []},
                    "app_subnet": {"id": "a1", "resources": []},
                    "db_subnet": {"id": "d1", "resources": []},
                }],
                "compute_groups": [],
            },
        },
    }
    lo = layout.build(page, "aws")
    region = lo.abs_boxes["region"]  # (x, y, w, h)
    n = len(services)
    services_row_w = n * layout.ICON + (n - 1) * layout.REGION_RES_GAP
    assert region[2] >= services_row_w + 2 * layout.REGION_PAD_X
    # And no service icon overflows the region right edge.
    region_right = region[0] + region[2]
    last = lo.abs_boxes["svc8"]
    assert (last[0] + last[2]) <= region_right


def test_lane_container_label_at_bottom():
    # Lane (plain-rectangle) containers place their label at the bottom so it
    # does not collide with the app-subnet label at the top.
    style = shapes.get_container("ecs_cluster").style()
    assert "verticalAlign=bottom" in style
    assert "verticalAlign=top" not in style


def test_same_az_row_routing_goes_above():
    # ecs-az1 -> rds1 style: same AZ row, gap > 300px. Should exit TOP and route
    # ABOVE the AZ row (inverted-U), with the waypoint y ABOVE the AZ row top.
    src = (1380, 910, 120, 120)   # ecs-az1
    tgt = (1870, 910, 120, 120)   # rds1
    az_rows = [(810, 1110)]       # AZ1 row bounds
    exit_xy, entry_xy, wps = gd._route_edge(
        src, tgt, label_band=50, az_rows=az_rows
    )
    assert exit_xy == (0.5, 0.0)   # top exit
    assert entry_xy == (0.5, 0.0)  # top entry
    assert wps, "expected inverted-U waypoints"
    az_top = az_rows[0][0]
    assert all(y < az_top for _x, y in wps), "waypoints must be ABOVE the AZ row"
