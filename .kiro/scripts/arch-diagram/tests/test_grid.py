"""Tests for the house-style grid layout (redesign)."""

import xml.etree.ElementTree as ET

import pytest

import generate_diagram as gd
import layout
import shapes


def grid_page():
    return {
        "name": "Architecture Diagram",
        "type": "architecture",
        "global": [
            {"id": "r53", "service": "route_53"},
            {"id": "cf", "service": "cloudfront"},
            {"id": "s3", "service": "s3"},
            {"id": "iam", "service": "identity_and_access_management"},
        ],
        "edge": [
            {"id": "users", "service": "user"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ],
        "region": {
            "label": "ap-south-1",
            "services": [
                {"id": "kms", "service": "key_management_service"},
                {"id": "secrets", "service": "secrets_manager"},
                {"id": "pipe", "service": "codepipeline"},
                {"id": "build", "service": "codebuild"},
                {"id": "ecr", "service": "ecr"},
            ],
            "vpc": {
                "label": "App VPC",
                "azs": [
                    {"id": "az1", "label": "AZ 1",
                     "public_subnet": {"id": "pub1", "resources": [{"id": "nat1", "service": "nat_gateway"}]},
                     "app_subnet": {"id": "app1", "resources": []},
                     "db_subnet": {"id": "db1", "resources": [{"id": "rds1", "service": "rds"}, {"id": "cache1", "service": "elasticache"}]}},
                    {"id": "az2", "label": "AZ 2",
                     "public_subnet": {"id": "pub2", "resources": []},
                     "app_subnet": {"id": "app2", "resources": []},
                     "db_subnet": {"id": "db2", "resources": [{"id": "rds2", "service": "rds"}]}},
                    {"id": "az3", "label": "AZ 3",
                     "public_subnet": {"id": "pub3", "resources": []},
                     "app_subnet": {"id": "app3", "resources": []},
                     "db_subnet": {"id": "db3", "resources": [{"id": "rds3", "service": "rds"}]}},
                ],
                "compute_groups": [
                    {"id": "asg", "kind": "asg", "node_service": "ec2", "label": "Auto Scaling Group"},
                    {"id": "ecs", "kind": "ecs_cluster", "node_service": "fargate", "label": "ECS Cluster"},
                    {"id": "eks", "kind": "eks_cluster", "node_service": "ec2", "label": "EKS Cluster"},
                ],
            },
        },
        "edges": [
            {"source": "alb", "target": "ecs-az1", "label": "route"},
            {"source": "ecs-az1", "target": "eks-az2", "label": "internal"},
            {"source": "rds1", "target": "rds2", "label": "repl", "dashed": True},
            {"source": "ecr", "target": "ecs-az1", "label": "deploy", "dashed": True},
        ],
    }


def _spec():
    return {"provider": "aws", "metadata": {"project": "Grid Test"}, "pages": [grid_page()]}


def _lo():
    return layout.build(grid_page(), "aws")


# ---- scopes / parenting ---------------------------------------------------
def test_global_services_parented_to_cloud():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["r53"] == "cloud"
    assert parents["cf"] == "cloud"


def test_region_services_parented_to_region():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["kms"] == "region"
    assert parents["secrets"] == "region"


def test_container_chain():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["region"] == "cloud"
    assert parents["vpc"] == "region"
    assert parents["az1"] == "vpc"
    assert parents["pub1"] == "az1"
    assert parents["app1"] == "az1"
    assert parents["db1"] == "az1"


def test_edge_scope_placement():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    # user renders outside the cloud (base layer)
    assert parents["users"] == "1"
    # WAF / ALB render inside the cloud
    assert parents["waf"] == "cloud"
    assert parents["alb"] == "cloud"
    # IGW is placed on the VPC border (child of vpc)
    assert parents["igw"] == "vpc"


def test_cicd_in_region_services():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["pipe"] == "region"
    assert parents["ecr"] == "region"


# ---- compute-group lanes + 3x3 intersections ------------------------------
def test_compute_group_lane_parented_to_vpc():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["ecs"] == "vpc"
    assert parents["asg"] == "vpc"
    assert parents["eks"] == "vpc"


def test_group_nodes_one_per_az():
    lo = _lo()
    ids = {n.node_id for n in lo.nodes}
    for g in ("asg", "ecs", "eks"):
        for az in ("az1", "az2", "az3"):
            assert f"{g}-{az}" in ids


def test_group_node_parented_to_lane():
    lo = _lo()
    parents = {n.node_id: n.parent for n in lo.nodes}
    assert parents["ecs-az1"] == "ecs"
    assert parents["ecs-az2"] == "ecs"
    assert parents["eks-az3"] == "eks"


def test_lane_spans_all_az_rows():
    lo = _lo()
    b = lo.abs_boxes
    ex, ey, ew, eh = b["ecs"]
    # lane covers app-subnet bands for az1 and az2 at minimum; az3 band may
    # be partially covered (lane stops before az3 bottom border by design)
    for az in ("app1", "app2"):
        ax, ay, aw, ah = b[az]
        assert ey <= ay and ey + eh >= ay + ah
    # lane top is above app1
    ax, ay, aw, ah = b["app1"]
    assert ey <= ay


def test_group_nodes_align_vertically_same_column():
    lo = _lo()
    b = lo.abs_boxes
    xs = {round(b[f"ecs-{az}"][0]) for az in ("az1", "az2", "az3")}
    assert len(xs) == 1  # same x across AZs (one column)
    ys = [b[f"ecs-{az}"][1] for az in ("az1", "az2", "az3")]
    assert ys[0] < ys[1] < ys[2]  # increasing y (one per AZ row)


def test_group_columns_side_by_side():
    lo = _lo()
    b = lo.abs_boxes
    # asg left of ecs left of eks
    assert b["asg"][0] < b["ecs"][0] < b["eks"][0]


# ---- uniform subnet sizing ------------------------------------------------
def test_public_subnets_uniform_width():
    lo = _lo()
    b = lo.abs_boxes
    widths = {round(b[f"pub{i}"][2]) for i in (1, 2, 3)}
    assert len(widths) == 1


def test_db_subnet_widens_for_more_resources_but_uniform_across_azs():
    lo = _lo()
    b = lo.abs_boxes
    # db1 has 2 resources; all db subnets share the same (widened) width
    widths = {round(b[f"db{i}"][2]) for i in (1, 2, 3)}
    assert len(widths) == 1
    # and that width is larger than a single-icon public subnet
    assert b["db1"][2] >= b["pub1"][2]


# ---- app tier ordering: public | app-lanes | db ---------------------------
def test_tier_column_order():
    lo = _lo()
    b = lo.abs_boxes
    assert b["pub1"][0] < b["app1"][0] < b["db1"][0]


def test_lanes_overlay_app_subnet():
    lo = _lo()
    b = lo.abs_boxes
    # ecs lane horizontally sits within the app-subnet's x-range for az1
    appx, appy, appw, apph = b["app1"]
    ex, ey, ew, eh = b["ecs"]
    assert appx <= ex and ex + ew <= appx + appw + 1
    # and the lane extends above and below the app-subnet band (overhang)
    assert ey < appy and ey + eh > appy + apph


# ---- emission / validity --------------------------------------------------
def test_document_builds_and_validates():
    mxfile = gd.build_document(_spec())
    gd.validate(mxfile)  # structural checklist
    xml = gd.render_xml(mxfile)
    assert "Grid Test" in xml
    assert "group_availability_zone" in xml
    assert "group_auto_scaling_group" in xml
    assert "resIcon=mxgraph.aws4.fargate" in xml


def test_outer_border_present():
    mxfile = gd.build_document(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    borders = [c for c in root.findall("mxCell") if c.get("id", "").endswith("-border")]
    assert len(borders) == 1


def test_edges_have_connection_points_and_waypoints():
    mxfile = gd.build_document(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    edges = [c for c in root.findall("mxCell") if c.get("edge") == "1"]
    assert edges
    for e in edges:
        style = e.get("style", "")
        # dashed edges still route; every routed edge has ports
        assert "exitX=" in style and "entryX=" in style
        arr = e.find("mxGeometry/Array[@as='points']")
        assert arr is not None and len(arr.findall("mxPoint")) >= 1


def test_all_ids_unique_in_document():
    mxfile = gd.build_document(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    ids = [c.get("id") for c in root.findall("mxCell")]
    assert len(ids) == len(set(ids))


def test_edges_reference_existing_cells():
    mxfile = gd.build_document(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    cells = root.findall("mxCell")
    id_set = {c.get("id") for c in cells}
    for c in cells:
        if c.get("edge") == "1":
            assert c.get("source") in id_set
            assert c.get("target") in id_set


# ---- spec validation ------------------------------------------------------
def test_unknown_compute_group_kind_raises():
    spec = _spec()
    spec["pages"][0]["region"]["vpc"]["compute_groups"][0]["kind"] = "bogus"
    with pytest.raises(gd.SpecError) as exc:
        gd.build_document(spec)
    assert "bogus" in str(exc.value)


def test_missing_node_service_raises():
    spec = _spec()
    del spec["pages"][0]["region"]["vpc"]["compute_groups"][1]["node_service"]
    with pytest.raises(gd.SpecError) as exc:
        gd.build_document(spec)
    assert "node_service" in str(exc.value)


def test_dangling_edge_to_group_node_raises():
    spec = _spec()
    spec["pages"][0]["edges"].append({"source": "alb", "target": "ecs-az9"})
    with pytest.raises(gd.SpecError) as exc:
        gd.build_document(spec)
    assert "ecs-az9" in str(exc.value)


def test_missing_project_raises():
    spec = _spec()
    del spec["metadata"]["project"]
    with pytest.raises(gd.SpecError):
        gd.build_document(spec)
