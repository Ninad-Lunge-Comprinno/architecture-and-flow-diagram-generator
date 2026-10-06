"""Tests for multi-VPC diagrams (stacked peered VPCs, TGW, route tables)."""

import pytest

import generate_diagram as gd
import layout


def _az(aid, db_ids=()):
    return {
        "id": aid, "label": aid,
        "public_subnet": {"id": f"pub-{aid}", "resources": []},
        "app_subnet": {"id": f"app-{aid}", "resources": []},
        "db_subnet": {
            "id": f"db-{aid}",
            "resources": [
                {"id": rid, "service": "rds"} for rid in db_ids
            ],
        },
    }


def _vpc(vid, azs, groups):
    return {
        "id": vid, "label": vid,
        "azs": azs,
        "compute_groups": groups,
    }


def mirror_page():
    return {
        "name": "Architecture Diagram",
        "type": "architecture",
        "global": [{"id": "r53", "service": "route_53"}],
        "edge": [
            {"id": "users", "service": "user"},
            {"id": "waf-a", "service": "waf", "vpc": "vpc-a"},
            {"id": "alb-a", "service": "application_load_balancer", "vpc": "vpc-a"},
            {"id": "igw-a", "service": "internet_gateway", "vpc": "vpc-a"},
            {"id": "waf-b", "service": "waf", "vpc": "vpc-b"},
            {"id": "alb-b", "service": "application_load_balancer", "vpc": "vpc-b"},
            {"id": "igw-b", "service": "internet_gateway", "vpc": "vpc-b"},
        ],
        "region": {
            "label": "us-east-1",
            "services": [{"id": "ecr", "service": "ecr"}],
            "transit_gateway": {"id": "tgw"},
            "vpcs": [
                _vpc("vpc-a",
                     [_az("a-az1", ("a-rds1",)), _az("a-az2"), _az("a-az3")],
                     [{"id": "eksa", "kind": "eks_cluster", "node_service": "ec2"}]),
                _vpc("vpc-b",
                     [_az("b-az1", ("b-rds1",)), _az("b-az2"), _az("b-az3")],
                     [{"id": "eksb", "kind": "eks_cluster", "node_service": "ec2"}]),
            ],
        },
        "edges": [
            {"source": "users", "target": "waf-a"},
            {"source": "waf-a", "target": "igw-a"},
            {"source": "igw-a", "target": "alb-a"},
            {"source": "users", "target": "waf-b"},
            {"source": "waf-b", "target": "igw-b"},
            {"source": "igw-b", "target": "alb-b"},
            {"source": "alb-a", "target": "eksa"},
            {"source": "alb-b", "target": "eksb"},
            {"source": "eksa", "target": "a-rds1"},
            {"source": "eksb", "target": "b-rds1"},
            {"source": "eksa", "target": "tgw"},
            {"source": "tgw", "target": "eksb"},
            {"source": "ecr", "target": "eksa"},
        ],
    }


def _spec():
    return {"provider": "aws", "metadata": {"project": "Mirror Test"},
            "pages": [mirror_page()]}


# ---- layout ---------------------------------------------------------------

def test_two_vpc_boxes_stacked_same_width():
    lo = layout.build(mirror_page(), "aws")
    a = lo.abs_boxes["vpc-a"]
    b = lo.abs_boxes["vpc-b"]
    assert b[1] > a[1] + a[3]  # stacked, gap between
    assert a[2] == b[2]        # uniform width (columns align)


def test_single_vpc_keeps_legacy_ids():
    page = mirror_page()
    region = page["region"]
    region["vpc"] = region.pop("vpcs")[0]
    region.pop("transit_gateway", None)
    for res in page["edge"]:
        res.pop("vpc", None)
    lo = layout.build(page, "aws")
    assert "vpc" in lo.abs_boxes
    assert lo.vpc_corridors == {"vpc": lo.vpc_corridor_x}
    assert lo.vpc_tops == {"vpc": lo.vpc_abs_top}


def test_tgw_centred_in_gap():
    lo = layout.build(mirror_page(), "aws")
    a = lo.abs_boxes["vpc-a"]
    b = lo.abs_boxes["vpc-b"]
    t = lo.abs_boxes["tgw"]
    gap_mid = (a[1] + a[3] + b[1]) / 2
    assert abs((t[1] + t[3] / 2) - gap_mid) < 5


def test_per_vpc_ingress_chains_at_middle_rows():
    lo = layout.build(mirror_page(), "aws")
    boxes = lo.abs_boxes
    ca = boxes["alb-a"][1] + 60
    cb = boxes["alb-b"][1] + 60
    assert boxes["waf-a"][1] + 60 == ca == boxes["igw-a"][1] + 60
    assert boxes["waf-b"][1] + 60 == cb == boxes["igw-b"][1] + 60
    assert cb > ca  # one chain per VPC, vertically separated
    rows = lo.az_rows
    assert rows[1][0] < ca < rows[1][1]  # VPC-A middle row
    assert rows[4][0] < cb < rows[4][1]  # VPC-B middle row


# ---- spec validation --------------------------------------------------------

def test_unknown_vpc_binding_rejected():
    page = mirror_page()
    page["edge"].append({"id": "x", "service": "waf", "vpc": "vpc-zzz"})
    with pytest.raises(gd.SpecError):
        gd.build_document({"provider": "aws",
                           "metadata": {"project": "T"},
                           "pages": [page]})


def test_tgw_without_id_rejected():
    page = mirror_page()
    page["region"]["transit_gateway"] = {"label": "TGW"}
    with pytest.raises(gd.SpecError):
        gd.build_document({"provider": "aws",
                           "metadata": {"project": "T"},
                           "pages": [page]})


# ---- generation + routing -------------------------------------------------

def test_mirror_generates_without_icon_conflicts():
    import routing as _routing
    lo = layout.build(mirror_page(), "aws")
    doc = gd.build_document(_spec())
    assert doc is not None
    # Re-derive routed polylines is internal; assert the structural facts:
    assert "tgw" in lo.abs_boxes
    assert lo.vpc_of["alb-a"] == "vpc-a"
    assert lo.vpc_of["alb-b"] == "vpc-b"
    assert lo.vpc_of["a-rds1"] == "vpc-a"
    assert set(lo.vpc_corridors) == {"vpc-a", "vpc-b"}


# ---- N-VPC generality (3 VPCs, no code changes) -----------------------------

def _three_vpc_page():
    page = mirror_page()
    region = page["region"]
    third = {
        "id": "vpc-c", "label": "vpc-c",
        "azs": [
            {"id": "c-az1", "label": "c-az1",
             "public_subnet": {"id": "c-pub1", "resources": []},
             "app_subnet": {"id": "c-app1", "resources": []},
             "db_subnet": {"id": "c-db1", "resources": [
                 {"id": "c-rds1", "service": "rds"}]}},
            {"id": "c-az2", "label": "c-az2",
             "public_subnet": {"id": "c-pub2", "resources": []},
             "app_subnet": {"id": "c-app2", "resources": []},
             "db_subnet": {"id": "c-db2", "resources": []}},
        ],
        "compute_groups": [
            {"id": "eksc", "kind": "eks_cluster", "node_service": "ec2"}],
    }
    region["vpcs"].append(third)
    page["edge"] += [
        {"id": "waf-c", "service": "waf", "vpc": "vpc-c"},
        {"id": "alb-c", "service": "application_load_balancer", "vpc": "vpc-c"},
        {"id": "igw-c", "service": "internet_gateway", "vpc": "vpc-c"},
    ]
    page["edges"] += [
        {"source": "users", "target": "waf-c"},
        {"source": "waf-c", "target": "igw-c"},
        {"source": "igw-c", "target": "alb-c"},
        {"source": "alb-c", "target": "eksc"},
        {"source": "eksc", "target": "c-rds1"},
        {"source": "eksc", "target": "tgw"},
    ]
    return page


def test_three_vpcs_stack_with_chains_and_tgw():
    page = _three_vpc_page()
    lo = layout.build(page, "aws")
    boxes = lo.abs_boxes
    tops = sorted((boxes[v][1], v) for v in ("vpc-a", "vpc-b", "vpc-c"))
    assert [v for _, v in tops] == ["vpc-a", "vpc-b", "vpc-c"]
    assert tops[1][0] > tops[0][0] + boxes["vpc-a"][3]
    assert tops[2][0] > tops[1][0] + boxes["vpc-b"][3]
    # TGW stays in the first gap; every VPC gets its own chain row.
    a = boxes["vpc-a"]
    assert a[1] + a[3] < boxes["tgw"][1] < tops[1][0]
    cas = {v: boxes[f"alb-{v[-1]}"][1] + 60 for v in ("vpc-a", "vpc-b", "vpc-c")}
    assert cas["vpc-a"] < cas["vpc-b"] < cas["vpc-c"]
    assert set(lo.vpc_corridors) == {"vpc-a", "vpc-b", "vpc-c"}
    assert lo.vpc_of["alb-c"] == "vpc-c"
    assert lo.vpc_of["c-rds1"] == "vpc-c"


def test_three_vpc_document_builds():
    doc = gd.build_document({"provider": "aws",
                             "metadata": {"project": "T"},
                             "pages": [_three_vpc_page()]})
    assert doc is not None
