"""Tests for the flow page layered layout."""

import layout

import generate_diagram as gd
import routing


def _flow_spec_linear():
    """A→B→C→D linear chain."""
    return {
        "nodes": [{"id": "a", "service": "user"}, {"id": "b", "service": "waf"},
                  {"id": "c", "service": "application_load_balancer"}, {"id": "d", "service": "ecs"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"},
                  {"source": "c", "target": "d"}],
    }


def _flow_spec_fan():
    """A→{B, C} fan-out."""
    return {
        "nodes": [{"id": "a", "service": "ecs"}, {"id": "b", "service": "rds"},
                  {"id": "c", "service": "elasticache"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "a", "target": "c"}],
    }


def test_linear_chain_is_left_to_right():
    pos = gd._flow_layout(**_flow_spec_linear())
    assert pos["a"][0] < pos["b"][0] < pos["c"][0] < pos["d"][0]


def test_linear_chain_same_row():
    pos = gd._flow_layout(**_flow_spec_linear())
    ys = {round(pos[nid][1]) for nid in ("a", "b", "c", "d")}
    assert len(ys) == 1


def test_chain_stays_aligned_beside_a_branch():
    spec = {
        "nodes": [{"id": "viewer", "service": "users"},
                  {"id": "cdn", "service": "cloudfront"},
                  {"id": "gateway", "service": "api_gateway"},
                  {"id": "identity", "service": "cognito"}],
        "edges": [{"source": "viewer", "target": "cdn"},
                  {"source": "viewer", "target": "gateway"},
                  {"source": "gateway", "target": "identity"}],
    }
    pos = gd._flow_layout(**spec)
    assert pos["gateway"][1] == pos["identity"][1]


def test_fan_out_sibling_nodes_same_column():
    pos = gd._flow_layout(**_flow_spec_fan())
    assert abs(pos["b"][0] - pos["c"][0]) < 5


def test_fan_out_siblings_different_y():
    pos = gd._flow_layout(**_flow_spec_fan())
    assert abs(pos["b"][1] - pos["c"][1]) > 100


def test_merge_waits_for_latest_predecessor():
    spec = {
        "nodes": [{"id": n, "service": "s3"} for n in ("a", "b", "c", "d")],
        "edges": [{"source": "a", "target": "b"},
                  {"source": "a", "target": "c"},
                  {"source": "b", "target": "d"},
                  {"source": "c", "target": "d"}],
    }
    pos = gd._flow_layout(**spec)
    assert pos["a"][0] < pos["b"][0] == pos["c"][0] < pos["d"][0]


def test_layout_is_deterministic_for_same_graph():
    spec = _flow_spec_fan()
    assert gd._flow_layout(**spec) == gd._flow_layout(**spec)


def test_all_positions_unique():
    pos = gd._flow_layout(**_flow_spec_fan())
    coords = [(round(x), round(y)) for x, y in pos.values()]
    assert len(coords) == len(set(coords))


def test_explicit_xy_overrides_layout():
    """Spec nodes with x/y should override the computed position."""
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Override"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [
                {"id": "a", "service": "user", "x": 999, "y": 888},
                {"id": "b", "service": "waf"},
            ],
            "edges": [{"source": "a", "target": "b"}],
        }],
    }
    mxfile = gd.build_document(spec)
    root = mxfile.find("diagram/mxGraphModel/root")
    node_a = next(c for c in root.findall("mxCell") if c.get("id") == "a")
    geo = node_a.find("mxGeometry")
    assert int(geo.get("x")) == 999
    assert int(geo.get("y")) == 888


def test_flow_page_has_outer_border():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Border"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "a", "service": "user"}, {"id": "b", "service": "waf"}],
            "edges": [{"source": "a", "target": "b"}],
        }],
    }
    mxfile = gd.build_document(spec)
    root = mxfile.find("diagram/mxGraphModel/root")
    borders = [c for c in root.findall("mxCell") if c.get("id", "").endswith("-border")]
    assert len(borders) == 1


def test_flow_header_and_logo_are_inside_border():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Header"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "a", "service": "user"}, {"id": "b", "service": "waf"}],
            "edges": [{"source": "a", "target": "b"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    cells = root.findall("mxCell")
    border = next(c for c in cells if c.get("id", "").endswith("-border"))
    border_geo = border.find("mxGeometry")
    bx, by = float(border_geo.get("x")), float(border_geo.get("y"))
    bw, bh = float(border_geo.get("width")), float(border_geo.get("height"))
    logo = next(c for c in cells if "shape=image" in c.get("style", ""))
    logo_geo = logo.find("mxGeometry")
    assert float(logo_geo.get("x")) >= bx
    assert float(logo_geo.get("y")) >= by
    assert float(logo_geo.get("y")) + float(logo_geo.get("height")) <= by + bh
    assert float(logo_geo.get("x")) + float(logo_geo.get("width")) <= bx + bw


def test_flow_title_starts_after_logo_without_client_name_prefix():
    spec = {
        "provider": "aws",
        "metadata": {"client_name": "Acme Orders", "version": "1.0"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "client", "service": "users"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    cells = root.findall("mxCell")
    logo = next(c for c in cells if "shape=image" in c.get("style", ""))
    title = next(c for c in cells if "<h1" in c.get("value", ""))
    logo_geo, title_geo = logo.find("mxGeometry"), title.find("mxGeometry")
    assert float(title_geo.get("x")) == float(logo_geo.get("x")) + float(logo_geo.get("width")) + 20
    assert "Acme Orders" in title.get("value", "")
    assert "Client Name:" not in title.get("value", "")


def test_aws_flow_has_cloud_boundary_and_keeps_source_actor_outside():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Boundaries"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "user", "service": "users"},
                      {"id": "api", "service": "api_gateway"}],
            "edges": [{"source": "user", "target": "api"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    cells = {c.get("id"): c for c in root.findall("mxCell")}
    cloud_geo = cells["page-1-cloud"].find("mxGeometry")
    user_geo = cells["user"].find("mxGeometry")
    assert float(user_geo.get("x")) + float(user_geo.get("width")) < float(cloud_geo.get("x"))


def test_external_flow_destination_sits_beyond_aws_cloud():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Endpoint"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "requester", "service": "users"},
                      {"id": "api", "service": "api_gateway"},
                      {"id": "player", "service": "users", "scope": "external"}],
            "edges": [{"source": "requester", "target": "api"},
                      {"source": "api", "target": "player"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    cells = {c.get("id"): c for c in root.findall("mxCell")}
    cloud = cells["page-1-cloud"].find("mxGeometry")
    player = cells["player"].find("mxGeometry")
    assert float(player.get("x")) > float(cloud.get("x")) + float(cloud.get("width"))


def test_external_actor_with_return_flow_centers_between_all_neighbors():
    nodes = [{"id": "cdn", "service": "cloudfront"},
             {"id": "service", "service": "eks", "scope": "vpc"},
             {"id": "telemetry", "service": "kinesis_data_streams"},
             {"id": "player", "service": "users", "scope": "external"}]
    edges = [{"source": "cdn", "target": "player"},
             {"source": "service", "target": "player"},
             {"source": "player", "target": "telemetry"}]
    positions = gd._flow_layout(nodes, edges)
    expected_y = sum(positions[node][1] for node in ("cdn", "service", "telemetry")) / 3
    assert positions["player"][1] == expected_y
    assert positions["player"][0] < positions["cdn"][0]


def test_shared_external_actor_feedback_does_not_collapse_flow_ranks():
    nodes = [{"id": "client", "service": "users", "scope": "external"},
             {"id": "cdn", "service": "cloudfront"},
             {"id": "origin", "service": "s3"},
             {"id": "telemetry", "service": "kinesis_data_streams"}]
    edges = [{"source": "client", "target": "cdn"},
             {"source": "cdn", "target": "client"},
             {"source": "cdn", "target": "origin"},
             {"source": "client", "target": "telemetry"}]

    positions = gd._flow_layout(nodes, edges)

    assert positions["client"][0] < positions["cdn"][0] < positions["origin"][0]
    assert positions["client"][0] < positions["telemetry"][0]


def test_flow_groups_render_around_their_member_nodes():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Flow Groups"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "groups": [{"id": "vpc", "kind": "vpc", "label": "App VPC",
                        "members": ["api", "db"]}],
            "nodes": [{"id": "user", "service": "users"},
                      {"id": "api", "service": "lambda"},
                      {"id": "db", "service": "rds"},
                      {"id": "cognito", "service": "cognito"},
                      {"id": "s3", "service": "s3"}],
            "edges": [{"source": "user", "target": "api"},
                      {"source": "api", "target": "db"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    cells = {c.get("id"): c for c in root.findall("mxCell")}
    frame = cells["page-1-vpc"].find("mxGeometry")
    cloud = cells["page-1-cloud"].find("mxGeometry")
    border = next(c for c in cells.values() if c.get("id", "").endswith("-border"))
    border_geo = border.find("mxGeometry")
    api = cells["api"].find("mxGeometry")
    db = cells["db"].find("mxGeometry")
    fx, fy = float(frame.get("x")), float(frame.get("y"))
    fr, fb = fx + float(frame.get("width")), fy + float(frame.get("height"))
    cx, cy = float(cloud.get("x")), float(cloud.get("y"))
    cr, cb = cx + float(cloud.get("width")), cy + float(cloud.get("height"))
    bx, by = float(border_geo.get("x")), float(border_geo.get("y"))
    br = bx + float(border_geo.get("width"))
    bb = by + float(border_geo.get("height"))
    assert cx < fx < fr < cr and cy < fy < fb < cb
    assert bx <= cx and by <= cy and br >= cr and bb >= cb
    for geo in (api, db):
        x, y = float(geo.get("x")), float(geo.get("y"))
        assert fx < x < fr and fy < y < fb
    for key in ("cognito", "s3"):
        geo = cells[key].find("mxGeometry")
        x, y = float(geo.get("x")), float(geo.get("y"))
        right = x + float(geo.get("width"))
        bottom = y + float(geo.get("height"))
        assert right <= fx or x >= fr or bottom < fy or y > fb


def test_scoped_flow_layout_keeps_vpc_lane_compact():
    nodes = [
        {"id": "player", "service": "users", "scope": "external"},
        {"id": "cdn", "service": "cloudfront"},
        {"id": "gateway", "service": "api_gateway"},
        {"id": "identity", "service": "cognito"},
        {"id": "playback", "service": "eks"},
        {"id": "catalog", "service": "rds"},
        {"id": "manifests", "service": "s3"},
        {"id": "telemetry", "service": "kinesis_data_streams"},
        {"id": "fanout", "service": "sns"},
        {"id": "recommendations", "service": "sagemaker"},
        {"id": "analytics", "service": "elasticsearch_service"},
    ]
    edges = [
        {"source": "player", "target": "cdn"},
        {"source": "player", "target": "gateway"},
        {"source": "gateway", "target": "identity"},
        {"source": "gateway", "target": "playback"},
        {"source": "playback", "target": "catalog"},
        {"source": "playback", "target": "manifests"},
        {"source": "cdn", "target": "player"},
        {"source": "playback", "target": "player"},
        {"source": "player", "target": "telemetry"},
        {"source": "telemetry", "target": "fanout"},
        {"source": "fanout", "target": "recommendations"},
        {"source": "fanout", "target": "analytics"},
    ]
    positions = gd._flow_layout(
        nodes, edges,
        groups=[{"id": "vpc", "kind": "vpc", "members": ["playback", "catalog"]}],
    )

    assert max(y for _, y in positions.values()) < 1000
    assert positions["playback"][0] > positions["identity"][0]
    assert positions["player"][0] < positions["cdn"][0]


def test_vpc_path_keeps_connected_service_on_the_same_row():
    nodes = [{"id": "client", "service": "users", "scope": "external"},
             {"id": "gateway", "service": "api_gateway"},
             {"id": "service", "service": "eks", "scope": "vpc"},
             {"id": "database", "service": "rds", "scope": "vpc"},
             {"id": "bucket", "service": "s3"}]
    edges = [{"source": "client", "target": "gateway"},
             {"source": "gateway", "target": "service"},
             {"source": "service", "target": "database"},
             {"source": "service", "target": "bucket"}]

    positions = gd._flow_layout(
        nodes, edges,
        groups=[{"id": "vpc", "kind": "vpc", "members": ["service", "database"]}],
    )

    assert positions["gateway"][1] == positions["service"][1]
    assert positions["client"][0] < positions["gateway"][0] < positions["service"][0]
    assert positions["bucket"][1] != positions["service"][1]
    boxes = {nid: (*xy, gd.ICON_SIZE, gd.ICON_SIZE)
             for nid, xy in positions.items()}
    routes = gd._route_flow_edges(edges, boxes)
    assert routes[1] is not None


def test_single_vpc_output_stays_aligned_with_its_cloud_consumer():
    nodes = [{"id": "playback", "service": "eks", "scope": "vpc"},
             {"id": "telemetry", "service": "kinesis_data_streams"}]
    positions = gd._flow_layout(
        nodes, [{"source": "playback", "target": "telemetry"}],
    )

    assert positions["playback"][1] == positions["telemetry"][1]


def test_flow_edges_are_solid_even_when_marked_async():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Solid Flow"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "source", "service": "users"},
                      {"id": "queue", "service": "sqs"}],
            "edges": [{"source": "source", "target": "queue", "dashed": True}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    edge = next(c for c in root.findall("mxCell") if c.get("edge") == "1")
    assert "dashed=1" not in edge.get("style", "")


def test_flow_edges_remove_dashed_custom_style():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Solid Custom Flow"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "source", "service": "users"},
                      {"id": "queue", "service": "sqs"}],
            "edges": [{"source": "source", "target": "queue",
                       "style": "dashed=1;strokeColor=#111111;"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    edge = next(c for c in root.findall("mxCell") if c.get("edge") == "1")
    assert "dashed=" not in edge.get("style", "")
    assert "strokeColor=#111111" in edge.get("style", "")


def test_aligned_flow_chain_uses_orthogonal_connectors():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Straight Path"},
        "pages": [{
            "name": "Flow", "type": "flow",
            "nodes": [{"id": "user", "service": "users"},
                      {"id": "gateway", "service": "api_gateway"},
                      {"id": "service", "service": "lambda"}],
            "edges": [{"source": "user", "target": "gateway"},
                      {"source": "gateway", "target": "service"}],
        }],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    edges = [c for c in root.findall("mxCell") if c.get("edge") == "1"]
    assert all("edgeStyle=orthogonalEdgeStyle" in edge.get("style", "")
               for edge in edges)


def test_offset_flow_connection_uses_consistent_horizontal_anchors():
    exit_xy, entry_xy, points = gd._route_flow_edge(
        (0, 0, 120, 120), (300, 250, 120, 120)
    )
    assert exit_xy == (1.0, 0.85)
    assert entry_xy == (0.0, 0.15)
    assert points == []


def _route_points(boxes, edge, route):
    exit_xy, entry_xy, waypoints = route[0], route[1], route[2]
    source, target = boxes[edge["source"]], boxes[edge["target"]]
    start = (source[0] + exit_xy[0] * source[2],
             source[1] + exit_xy[1] * source[3])
    end = (target[0] + entry_xy[0] * target[2],
           target[1] + entry_xy[1] * target[3])
    return [start, *waypoints, end]


def test_flow_router_avoids_icons_and_spreads_shared_edges():
    import routing

    boxes = {
        "source": (0, 300, 120, 120),
        "upper": (600, 80, 120, 120),
        "lower": (600, 520, 120, 120),
        "blocker": (300, 300, 120, 120),
    }
    edges = [{"source": "source", "target": "upper"},
             {"source": "source", "target": "lower"}]
    routes = gd._route_flow_edges(edges, boxes)
    conflicts = routing.find_conflicts(
        {(edge["source"], edge["target"]): _route_points(boxes, edge, route)
         for edge, route in zip(edges, routes)}, boxes,
    )
    assert all(route is not None for route in routes)
    assert not conflicts


def test_fanout_edges_use_spread_anchors():
    source = (0, 400, 120, 120)
    targets = [(300, y, 120, 120) for y in (0, 300, 700)]
    source_fractions = [gd._route_flow_edge(source, target)[0][1]
                        for target in targets]
    assert source_fractions[0] < source_fractions[1] < source_fractions[2]


def test_generated_flow_edges_keep_drawio_orthogonal_style():
    spec = {
        "provider": "aws",
        "pages": [{"name": "Flow", "type": "flow",
                   "nodes": [{"id": "a", "service": "users"},
                             {"id": "b", "service": "api_gateway"}],
                   "edges": [{"source": "a", "target": "b"}]}],
    }
    root = gd.build_document(spec).find("diagram/mxGraphModel/root")
    edge = next(cell for cell in root.findall("mxCell") if cell.get("edge") == "1")
    assert "edgeStyle=orthogonalEdgeStyle" in edge.get("style", "")


# ---------------------------------------------------------------------------
# Routing regressions: unnecessary bends and overlapping arrows.
# ---------------------------------------------------------------------------
def _flow_paths(edges, boxes):
    """(edge, absolute polyline) for every routed edge."""
    routes = gd._route_flow_edges(edges, boxes)
    return [(edge, _route_points(boxes, edge, route))
            for edge, route in zip(edges, routes) if route]


def _flow_spec():
    """Branch/merge flow: a chain that fans out to two producers, which in
    turn both write to shared data stores."""
    return (
        [{"id": "f_user", "service": "users"},
         {"id": "f_waf", "service": "waf"},
         {"id": "f_alb", "service": "application_load_balancer"},
         {"id": "f_ecs", "service": "ecs"},
         {"id": "f_lambda", "service": "lambda"},
         {"id": "f_cache", "service": "elasticache"},
         {"id": "f_db", "service": "aurora"},
         {"id": "f_s3", "service": "s3"}],
        [{"source": "f_user", "target": "f_waf"},
         {"source": "f_waf", "target": "f_alb"},
         {"source": "f_alb", "target": "f_ecs"},
         {"source": "f_alb", "target": "f_lambda"},
         {"source": "f_ecs", "target": "f_cache"},
         {"source": "f_ecs", "target": "f_db"},
         {"source": "f_lambda", "target": "f_db"},
         {"source": "f_lambda", "target": "f_s3"},
         {"source": "f_ecs", "target": "f_s3"}],
    )


def _branch_merge_boxes():
    nodes, edges = _flow_spec()
    pos = gd._flow_layout(nodes, edges)
    boxes = {node["id"]: (pos[node["id"]][0], pos[node["id"]][1] + 280,
                          gd.ICON_SIZE, gd.ICON_SIZE)
             for node in nodes}
    return edges, boxes


def test_flow_routing_never_draws_a_tiny_stub_jog():
    """A waypoint that only shifts the line a few pixels is a visible kink with
    no purpose; every segment must be long enough to read as part of the route."""
    edges, boxes = _branch_merge_boxes()
    for _, path in _flow_paths(edges, boxes):
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) >= 25


def test_flow_routing_never_overlaps_two_arrows():
    """Parallel arrows must run in separate channels, not on top of each other."""
    edges, boxes = _branch_merge_boxes()
    paths = [path for _, path in _flow_paths(edges, boxes)]
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            for a, b in zip(paths[i], paths[i][1:]):
                for c, d in zip(paths[j], paths[j][1:]):
                    assert not routing._segments_overlap(a, b, c, d)


def test_flow_routing_never_draws_an_arrow_through_an_icon():
    edges, boxes = _branch_merge_boxes()
    rects = {node_id: gd._flow_obstacle(box) for node_id, box in boxes.items()}
    for edge, path in _flow_paths(edges, boxes):
        for node_id, rect in rects.items():
            if node_id in (edge["source"], edge["target"]):
                continue
            assert not routing._polyline_hits_rect(path, rect)


def test_flow_routing_is_deterministic():
    edges, boxes = _branch_merge_boxes()
    assert gd._route_flow_edges(edges, boxes) == gd._route_flow_edges(edges, boxes)


def test_flow_layout_leaves_a_free_band_between_stacked_rows():
    """Rows must clear each other's routing obstacles, otherwise a vertical run
    has no gap to cross and is forced through a neighbour."""
    nodes, edges = _flow_spec()
    pos = gd._flow_layout(nodes, edges)
    rects = {node["id"]: gd._flow_obstacle(
        (pos[node["id"]][0], pos[node["id"]][1], gd.ICON_SIZE, gd.ICON_SIZE))
        for node in nodes}
    ids = sorted(rects)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = rects[ids[i]], rects[ids[j]]
            overlap_x = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            overlap_y = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            # Icons may share a row or a column, but must never overlap outright.
            assert overlap_x <= 0 or overlap_y <= 0


def test_stacked_flow_rows_are_a_whole_step_apart():
    """A node placed half a step from its neighbour has no crossing room."""
    nodes = [{"id": "a", "service": "ecs"}, {"id": "b", "service": "lambda"}]
    edges = [{"source": "a", "target": "b"}]
    pos = gd._flow_layout(nodes, edges)
    step = gd.ICON_SIZE + layout.LABEL_BAND + gd.FLOW_ROW_GUTTER
    assert abs(pos["b"][1] - pos["a"][1]) % step < 0.01 or \
        pos["a"][1] == pos["b"][1]


def _midpoint(path):
    """The point draw.io puts an edge label on: the arc-length midpoint."""
    return gd._flow_point_at(path, gd._flow_path_length(path) / 2)


def _labelled_branch_merge():
    """Branch/merge flow where every arrow carries a label, so label boxes can
    collide the way they do on a real flow page."""
    edges, boxes = _branch_merge_boxes()
    labels = ["Auth", "Serve", "Render", "Fan out", "Cache", "Write",
              "Aggregate", "Archive", "Copy"]
    return ([dict(edge, label=label) for edge, label in zip(edges, labels)],
            boxes)


def test_flow_ports_land_on_declared_icon_connection_points():
    """Arrows must attach to the icon's own connection points.

    The AWS resourceIcon stencil declares ``points=`` anchors at 0, 0.25, 0.5,
    0.75 and 1. Any other fraction makes draw.io pull the exit off the shape's
    outline, which is what produced arrows glued to icon corners.
    """
    edges, boxes = _branch_merge_boxes()
    for route in gd._route_flow_edges(edges, boxes):
        if not route:
            continue
        for fractions in (route[0], route[1]):
            for value in fractions:
                assert any(abs(value - anchor) < 1e-9
                           for anchor in gd.FLOW_PORT_ANCHORS)


def test_flow_port_allocation_keeps_arrows_on_distinct_anchors():
    """Two arrows sharing one side must not be snapped onto the same point,
    or they leave the icon as a single indistinguishable bundle."""
    edges, boxes = _branch_merge_boxes()
    seen: dict = {}
    for index, route in enumerate(gd._route_flow_edges(edges, boxes)):
        if not route:
            continue
        for which, fractions in (("source", route[0]), ("target", route[1])):
            side = ("right" if fractions[0] == 1.0 else
                    "left" if fractions[0] == 0.0 else
                    "bottom" if fractions[1] == 1.0 else "top")
            node = edges[index]["source" if which == "source" else "target"]
            key = (node, side)
            offset = fractions[1] if side in ("left", "right") else fractions[0]
            assert offset not in seen.get(key, set()), \
                f"two arrows share connection point {offset} on {key}"
            seen.setdefault(key, set()).add(offset)


def test_flow_labels_do_not_overlap_each_other():
    """draw.io draws an edge label at the path midpoint, so two arrows sharing a
    midpoint print their text on top of each other. Offsets must break that."""
    edges, boxes = _labelled_branch_merge()
    routes = gd._route_flow_edges(edges, boxes)
    placed: list = []
    for index, route in enumerate(routes):
        if not route:
            continue
        path = _route_points(boxes, edges[index], route)
        offset = route[3] or (0.0, 0.0)
        centre = _midpoint(path)
        centre = (centre[0] + offset[0], centre[1] + offset[1])
        width, height = gd._flow_label_size(edges[index]["label"])
        box = (centre[0] - width / 2, centre[1] - height / 2, width, height)
        for other in placed:
            assert not gd._flow_rects_overlap(box, other), \
                f"labels of edge {index} and an earlier edge overlap"
        placed.append(box)


def test_flow_labels_do_not_cover_an_icon():
    """A label box sitting on top of an icon hides the thing it describes."""
    edges, boxes = _labelled_branch_merge()
    routes = gd._route_flow_edges(edges, boxes)
    for index, route in enumerate(routes):
        if not route:
            continue
        path = _route_points(boxes, edges[index], route)
        offset = route[3] or (0.0, 0.0)
        centre = _midpoint(path)
        centre = (centre[0] + offset[0], centre[1] + offset[1])
        width, height = gd._flow_label_size(edges[index]["label"])
        box = (centre[0] - width / 2, centre[1] - height / 2, width, height)
        for node_id, icon in boxes.items():
            if node_id in (edges[index]["source"], edges[index]["target"]):
                continue
            assert not gd._flow_rects_overlap(box, icon), \
                f"label of edge {index} covers icon {node_id}"


def test_flow_label_offset_is_dropped_for_hand_placed_geometry():
    """An edge with explicit waypoints no longer follows the routed path, so a
    label offset measured against the route would land it in the wrong spot."""
    diagram = gd.build_flow_page({
        "name": "Flow",
        "nodes": [{"id": "a", "service": "user"},
                  {"id": "b", "service": "waf"}],
        "edges": [{"source": "a", "target": "b", "label": "Auth",
                   "waypoints": [[300, 200]]}],
    }, "aws", "page")
    assert not any(cell.label_offset for cell in diagram.cells if cell.edge)
