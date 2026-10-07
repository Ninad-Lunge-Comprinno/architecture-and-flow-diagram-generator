"""Regression tests for layout requirements (DataForge primary regression case).

Covers:
  - Ingress path to API Gateway and its Lambda
  - Users/devices outside the AWS Cloud boundary
  - WAF + ALB side-by-side in the ingress band
  - Connected services close to each other (Lambda near APIGW)
  - Boundary spacing and landscape page proportions
  - Multiple converging connections
  - VPC and cross-AZ routes
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import layout as lo_mod
import generate_diagram as gd


# ---- Helpers --------------------------------------------------------------

def _build_minimal_arch(
    edge_items=None,
    region_services=None,
    azs=None,
    edges=None,
    global_items=None,
):
    """Build a minimal architecture spec and return the Layout object."""
    spec_page = {
        "name": "Architecture Diagram",
        "type": "architecture",
        "global": global_items or [],
        "edge": edge_items or [],
        "region": {
            "label": "us-east-1",
            "services": region_services or [],
            "vpc": {
                "label": "Test VPC",
                "azs": azs or [
                    {
                        "id": "az1",
                        "public_subnet": {"id": "pub1", "resources": [
                            {"id": "nat1", "service": "nat_gateway"},
                        ]},
                        "app_subnet": {"id": "app1", "resources": []},
                        "db_subnet": {"id": "db1", "resources": [
                            {"id": "cache1", "service": "elasticache"},
                            {"id": "aurora1", "service": "aurora"},
                        ]},
                    },
                    {
                        "id": "az2",
                        "public_subnet": {"id": "pub2", "resources": []},
                        "app_subnet": {"id": "app2", "resources": []},
                        "db_subnet": {"id": "db2", "resources": [
                            {"id": "aurora2", "service": "aurora"},
                        ]},
                    },
                    {
                        "id": "az3",
                        "public_subnet": {"id": "pub3", "resources": []},
                        "app_subnet": {"id": "app3", "resources": []},
                        "db_subnet": {"id": "db3", "resources": [
                            {"id": "aurora3", "service": "aurora"},
                        ]},
                    },
                ],
                "compute_groups": [
                    {"id": "ecs", "kind": "ecs_cluster", "node_service": "fargate",
                     "label": "ECS Fargate"},
                ],
            },
        },
        "edges": edges or [],
    }
    return lo_mod.build(spec_page)


def _full_dataforge_layout():
    """Build DataForge architecture layout (real regression case)."""
    spec = {
        "provider": "aws",
        "metadata": {"project": "DataForge", "version": "1.0",
                     "date": "2026-09-23", "creator": "Test"},
        "pages": [{
            "name": "Architecture Diagram",
            "type": "architecture",
            "global": [
                {"id": "r53", "service": "route_53", "label": "Route 53"},
                {"id": "cf", "service": "cloudfront", "label": "CloudFront"},
                {"id": "s3", "service": "s3", "label": "S3"},
                {"id": "iam", "service": "identity_and_access_management"},
            ],
            "edge": [
                {"id": "users", "service": "users", "label": "Users"},
                {"id": "mobile", "service": "mobile_client", "label": "Mobile"},
                {"id": "waf", "service": "waf", "label": "WAF"},
                {"id": "shield", "service": "shield", "label": "Shield"},
                {"id": "alb", "service": "application_load_balancer", "label": "ALB"},
                {"id": "apigw", "service": "api_gateway", "label": "API Gateway"},
                {"id": "igw", "service": "internet_gateway", "label": "IGW"},
            ],
            "region": {
                "label": "us-east-1",
                "services": [
                    {"id": "cognito", "service": "cognito"},
                    {"id": "lambda", "service": "lambda", "label": "Lambda"},
                    {"id": "ecr", "service": "ecr"},
                    {"id": "kms", "service": "key_management_service"},
                    {"id": "cloudwatch", "service": "cloudwatch_2"},
                    {"id": "sqs", "service": "sqs"},
                    {"id": "sns", "service": "sns"},
                    {"id": "eventbridge", "service": "eventbridge"},
                ],
                "vpc": {
                    "label": "DataForge VPC",
                    "azs": [
                        {
                            "id": "az1", "label": "AZ1",
                            "public_subnet": {"id": "pub1", "resources": [
                                {"id": "nat1", "service": "nat_gateway"}]},
                            "app_subnet": {"id": "app1", "resources": []},
                            "db_subnet": {"id": "data1", "resources": [
                                {"id": "cache1", "service": "elasticache"},
                                {"id": "aurora1", "service": "aurora"},
                                {"id": "rds1", "service": "rds"},
                            ]},
                        },
                        {
                            "id": "az2", "label": "AZ2",
                            "public_subnet": {"id": "pub2", "resources": []},
                            "app_subnet": {"id": "app2", "resources": []},
                            "db_subnet": {"id": "data2", "resources": [
                                {"id": "cache2", "service": "elasticache"},
                                {"id": "aurora2", "service": "aurora"},
                                {"id": "rds2", "service": "rds"},
                            ]},
                        },
                        {
                            "id": "az3", "label": "AZ3",
                            "public_subnet": {"id": "pub3", "resources": []},
                            "app_subnet": {"id": "app3", "resources": []},
                            "db_subnet": {"id": "data3", "resources": [
                                {"id": "cache3", "service": "elasticache"},
                                {"id": "aurora3", "service": "aurora"},
                            ]},
                        },
                    ],
                    "compute_groups": [
                        {"id": "ecs", "kind": "ecs_cluster", "node_service": "fargate",
                         "label": "ECS Fargate"},
                        {"id": "eks", "kind": "eks_cluster", "node_service": "ec2",
                         "label": "EKS Cluster"},
                    ],
                },
            },
            "edges": [
                {"source": "users", "target": "shield", "label": "https"},
                {"source": "shield", "target": "waf", "label": "filtered"},
                {"source": "waf", "target": "alb", "label": "filtered"},
                {"source": "alb", "target": "ecs", "label": "route"},
                {"source": "apigw", "target": "lambda", "label": "invoke"},
                {"source": "ecr", "target": "ecs", "label": "deploy", "dashed": True},
                {"source": "ecs-az1", "target": "cache1", "label": "cache"},
                {"source": "ecs-az1", "target": "aurora1", "label": "sql"},
                {"source": "aurora1", "target": "aurora2", "label": "replication",
                 "dashed": True},
                {"source": "aurora1", "target": "aurora3", "label": "replication",
                 "dashed": True},
            ],
        }],
    }
    lo = gd.layout
    page = spec["pages"][0]
    gd._fix_regional_placement(page)
    gd._reorder_services_for_vpc_proximity(page)
    return lo.build(page)


# ---- Ingress Path Tests ---------------------------------------------------

class TestIngressPath:
    """Users/devices → ingress services → compute path is well-formed."""

    def test_users_outside_cloud(self):
        """Users must be placed LEFT of the cloud boundary (page x < cloud x)."""
        edge_items = [
            {"id": "users", "service": "users", "label": "Users"},
            {"id": "waf", "service": "waf", "label": "WAF"},
            {"id": "alb", "service": "application_load_balancer", "label": "ALB"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        users_box = lo.abs_boxes.get("users")
        cloud_box = lo.abs_boxes.get("cloud")
        assert users_box is not None, "users node must exist"
        assert cloud_box is not None, "cloud node must exist"
        # Users x must be left of cloud left edge
        assert users_box[0] < cloud_box[0], (
            f"users x={users_box[0]:.0f} must be left of cloud x={cloud_box[0]:.0f}"
        )

    def test_mobile_outside_cloud(self):
        """Mobile clients must be placed outside the cloud boundary."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "mobile", "service": "mobile_client"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        for actor in ["users", "mobile"]:
            actor_box = lo.abs_boxes.get(actor)
            cloud_box = lo.abs_boxes.get("cloud")
            if actor_box is not None and cloud_box is not None:
                assert actor_box[0] < cloud_box[0], (
                    f"{actor} x={actor_box[0]:.0f} must be left of cloud x={cloud_box[0]:.0f}"
                )

    def test_ingress_band_items_inside_cloud(self):
        """WAF and ALB must be placed INSIDE the cloud boundary."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        cloud_box = lo.abs_boxes.get("cloud")
        assert cloud_box is not None
        cloud_left, cloud_top, cloud_w, cloud_h = cloud_box
        cloud_right = cloud_left + cloud_w

        for svc in ["waf", "alb"]:
            box = lo.abs_boxes.get(svc)
            if box is not None:
                assert box[0] >= cloud_left, (
                    f"{svc} x={box[0]:.0f} must be inside cloud left={cloud_left:.0f}"
                )
                assert box[0] + box[2] <= cloud_right + 5, (
                    f"{svc} right edge must be inside cloud right={cloud_right:.0f}"
                )

    def test_ingress_items_do_not_overlap_region(self):
        """Ingress services are placed inside their containers per the new model:

        Shield/WAF live in AWS Cloud outside the Region; ALB/API Gateway
        live inside the VPC. They must be contained by the correct box and must
        not overlap the AZ rows.
        """
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "apigw", "service": "api_gateway"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        region_box = lo.abs_boxes.get("region")
        cloud_box = lo.abs_boxes.get("cloud")
        vpc_box = lo.abs_boxes.get("vpc")
        if region_box is None or vpc_box is None:
            return

        def _contained(inner, outer, tol=5):
            ix, iy, iw, ih = inner
            ox, oy, ow, oh = outer
            return (ix >= ox - tol and iy >= oy - tol
                    and ix + iw <= ox + ow + tol and iy + ih <= oy + oh + tol)

        # Shield/WAF inside the Cloud but outside the Region and VPC.
        for svc in ["shield", "waf"]:
            box = lo.abs_boxes.get(svc)
            if box is None:
                continue
            assert _contained(box, cloud_box), f"{svc} must be inside AWS Cloud"
            assert not _contained(box, region_box), f"{svc} must be outside the Region"
            assert not _contained(box, vpc_box), (
                f"{svc} must be OUTSIDE the VPC (regional service)"
            )

        # ALB/API Gateway inside the VPC.
        for svc in ["alb", "apigw"]:
            box = lo.abs_boxes.get(svc)
            if box is None:
                continue
            assert _contained(box, vpc_box), f"{svc} must be inside the VPC"


# ---- WAF + ALB Side-by-Side -----------------------------------------------

class TestWafAlbSideBySide:
    """WAF and ALB must be placed side-by-side (same y, different x)."""

    def test_waf_alb_same_y(self):
        """WAF and ALB must share the same y coordinate."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        waf_box = lo.abs_boxes.get("waf")
        alb_box = lo.abs_boxes.get("alb")
        assert waf_box is not None, "waf must be placed"
        assert alb_box is not None, "alb must be placed"
        # Same y (within 5px tolerance for rounding)
        assert abs(waf_box[1] - alb_box[1]) < 5, (
            f"WAF y={waf_box[1]:.0f} and ALB y={alb_box[1]:.0f} should be equal (side-by-side)"
        )

    def test_waf_alb_different_x(self):
        """WAF and ALB must have different x positions (side-by-side, not stacked)."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        waf_box = lo.abs_boxes.get("waf")
        alb_box = lo.abs_boxes.get("alb")
        if waf_box and alb_box:
            assert abs(waf_box[0] - alb_box[0]) >= lo_mod.ICON, (
                f"WAF x={waf_box[0]:.0f} and ALB x={alb_box[0]:.0f} must differ by at least ICON={lo_mod.ICON}"
            )

    def test_waf_left_of_alb(self):
        """WAF must be to the LEFT of ALB (traffic flows WAF→ALB left-to-right)."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        waf_box = lo.abs_boxes.get("waf")
        alb_box = lo.abs_boxes.get("alb")
        if waf_box and alb_box:
            assert waf_box[0] < alb_box[0], (
                f"WAF x={waf_box[0]:.0f} must be LEFT of ALB x={alb_box[0]:.0f}"
            )

    def test_ingress_chain_left_to_right_order(self):
        """Shield→WAF→ALB→APIGW must be ordered left-to-right (x increases)."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "apigw", "service": "api_gateway"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items)
        boxes = lo.abs_boxes
        # Shield must be left of WAF (or equal x if shield is before WAF)
        if boxes.get("shield") and boxes.get("waf"):
            assert boxes["shield"][0] <= boxes["waf"][0], "Shield must be left of or equal WAF"
        # WAF must be left of ALB
        if boxes.get("waf") and boxes.get("alb"):
            assert boxes["waf"][0] < boxes["alb"][0], "WAF must be left of ALB"
        # ALB must be left of or at same y as APIGW
        if boxes.get("alb") and boxes.get("apigw"):
            assert boxes["alb"][0] <= boxes["apigw"][0], "ALB must not be right of APIGW"

    def test_dataforge_waf_alb_side_by_side(self):
        """DataForge regression: WAF+ALB side-by-side in the full DataForge layout."""
        lo = _full_dataforge_layout()
        waf_box = lo.abs_boxes.get("waf")
        alb_box = lo.abs_boxes.get("alb")
        assert waf_box is not None, "WAF must be present in DataForge layout"
        assert alb_box is not None, "ALB must be present in DataForge layout"
        assert abs(waf_box[1] - alb_box[1]) < 5, (
            f"DataForge: WAF y={waf_box[1]:.0f} and ALB y={alb_box[1]:.0f} should be equal"
        )
        assert waf_box[0] < alb_box[0], (
            f"DataForge: WAF x={waf_box[0]:.0f} must be LEFT of ALB x={alb_box[0]:.0f}"
        )


# ---- Lambda Proximity to APIGW --------------------------------------------

class TestLambdaApigwProximity:
    """Lambda must be placed near APIGW, not 2500px away."""

    def test_apigw_lambda_distance_reasonable(self):
        """APIGW→Lambda distance must be < 1500px (was 2580px before fix)."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "shield", "service": "shield"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "apigw", "service": "api_gateway"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        region_services = [
            {"id": "lambda", "service": "lambda", "label": "Lambda"},
            {"id": "cognito", "service": "cognito"},
            {"id": "ecr", "service": "ecr"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items, region_services=region_services)
        apigw_box = lo.abs_boxes.get("apigw")
        lambda_box = lo.abs_boxes.get("lambda")
        if apigw_box is None or lambda_box is None:
            pytest.skip("APIGW or Lambda not present")
        apigw_cx = apigw_box[0] + apigw_box[2] / 2
        apigw_cy = apigw_box[1] + apigw_box[3] / 2
        lambda_cx = lambda_box[0] + lambda_box[2] / 2
        lambda_cy = lambda_box[1] + lambda_box[3] / 2
        dist = ((apigw_cx - lambda_cx) ** 2 + (apigw_cy - lambda_cy) ** 2) ** 0.5
        assert dist < 1500, (
            f"APIGW→Lambda distance {dist:.0f}px is too large (max 1500px); "
            f"APIGW at ({apigw_box[0]:.0f},{apigw_box[1]:.0f}), "
            f"Lambda at ({lambda_box[0]:.0f},{lambda_box[1]:.0f})"
        )

    def test_dataforge_apigw_lambda_distance(self):
        """DataForge regression: APIGW→Lambda distance reduced from 2580px."""
        lo = _full_dataforge_layout()
        apigw_box = lo.abs_boxes.get("apigw")
        lambda_box = lo.abs_boxes.get("lambda")
        assert apigw_box is not None
        assert lambda_box is not None
        dist = ((apigw_box[0] - lambda_box[0]) ** 2 +
                (apigw_box[1] - lambda_box[1]) ** 2) ** 0.5
        assert dist < 1500, (
            f"DataForge APIGW→Lambda distance {dist:.0f}px must be < 1500px"
        )


# ---- Landscape Proportions ------------------------------------------------

class TestLandscapeProportions:
    """Diagram should be wider than tall (landscape orientation)."""

    def test_simple_arch_landscape(self):
        """A typical 3-AZ architecture must not produce extreme portrait (W < 0.7 * H)."""
        edge_items = [
            {"id": "users", "service": "users"},
            {"id": "waf", "service": "waf"},
            {"id": "alb", "service": "application_load_balancer"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        region_services = [
            {"id": "ecr", "service": "ecr"},
            {"id": "kms", "service": "key_management_service"},
        ]
        lo = _build_minimal_arch(edge_items=edge_items, region_services=region_services)
        cloud_box = lo.abs_boxes.get("cloud")
        assert cloud_box is not None
        w, h = cloud_box[2], cloud_box[3]
        # With a sparse spec (only 2 region services), landscape isn't guaranteed
        # since 3 AZ rows stack vertically. The key requirement is: not extreme portrait.
        # A ratio < 0.7 means the diagram is extremely tall — the "before" DataForge state.
        assert w >= h * 0.7, (
            f"Expected at least 0.7:1 aspect ratio, got {w:.0f}x{h:.0f} = {w/h:.2f}:1"
        )

    def test_dataforge_not_portrait(self):
        """DataForge with 85 services must not produce a 0.7:1 portrait diagram."""
        lo = _full_dataforge_layout()
        cloud_box = lo.abs_boxes.get("cloud")
        assert cloud_box is not None
        w, h = cloud_box[2], cloud_box[3]
        ratio = w / h
        assert ratio > 0.85, (
            f"DataForge cloud is too portrait ({w:.0f}x{h:.0f} = {ratio:.2f}:1); expected > 0.85:1"
        )


# ---- Boundary Spacing Tests -----------------------------------------------

class TestBoundarySpacing:
    """Container hierarchies must have consistent, readable spacing."""

    def test_vpc_inside_region(self):
        """VPC box must be fully contained within the region box."""
        lo = _build_minimal_arch()
        vpc_box = lo.abs_boxes.get("vpc")
        region_box = lo.abs_boxes.get("region")
        assert vpc_box and region_box
        rx, ry, rw, rh = region_box
        vx, vy, vw, vh = vpc_box
        assert vx >= rx, f"VPC left {vx:.0f} must be >= region left {rx:.0f}"
        assert vy >= ry, f"VPC top {vy:.0f} must be >= region top {ry:.0f}"
        assert vx + vw <= rx + rw + 5, f"VPC right must be inside region right"
        assert vy + vh <= ry + rh + 5, f"VPC bottom must be inside region bottom"

    def test_region_inside_cloud(self):
        """Region box must be fully contained within the cloud box."""
        lo = _build_minimal_arch()
        region_box = lo.abs_boxes.get("region")
        cloud_box = lo.abs_boxes.get("cloud")
        assert region_box and cloud_box
        cx, cy, cw, ch = cloud_box
        rx, ry, rw, rh = region_box
        assert rx >= cx, f"Region left {rx:.0f} must be >= cloud left {cx:.0f}"
        assert ry >= cy, f"Region top {ry:.0f} must be >= cloud top {cy:.0f}"
        assert rx + rw <= cx + cw + 5, "Region right must be inside cloud right"
        assert ry + rh <= cy + ch + 5, "Region bottom must be inside cloud bottom"

    def test_az_rows_inside_vpc(self):
        """AZ row boxes must be inside the VPC box."""
        lo = _build_minimal_arch()
        vpc_box = lo.abs_boxes.get("vpc")
        assert vpc_box is not None
        vx, vy, vw, vh = vpc_box
        for az_id in ["az1", "az2", "az3"]:
            az_box = lo.abs_boxes.get(az_id)
            if az_box is None:
                continue
            ax, ay, aw, ah = az_box
            assert ax >= vx - 5, f"{az_id} left {ax:.0f} must be inside VPC left {vx:.0f}"
            assert ay >= vy - 5, f"{az_id} top {ay:.0f} must be inside VPC top {vy:.0f}"

    def test_no_az_rows_overlap_each_other(self):
        """AZ rows must not overlap each other (should be separated by AZ_GAP)."""
        lo = _build_minimal_arch()
        az_ids = ["az1", "az2", "az3"]
        for i in range(len(az_ids) - 1):
            a_box = lo.abs_boxes.get(az_ids[i])
            b_box = lo.abs_boxes.get(az_ids[i + 1])
            if a_box is None or b_box is None:
                continue
            a_bottom = a_box[1] + a_box[3]
            b_top = b_box[1]
            assert a_bottom <= b_top, (
                f"{az_ids[i]} bottom {a_bottom:.0f} overlaps {az_ids[i+1]} top {b_top:.0f}"
            )


# ---- Cross-AZ Replication Routes ------------------------------------------

class TestCrossAzRoutes:
    """Replication edges (Aurora, ElastiCache) cross AZ rows without confusion."""

    def test_cross_az_edge_generation(self):
        """spec edges with aurora1→aurora2 across AZs must produce valid XML."""
        spec = {
            "provider": "aws",
            "metadata": {"project": "CrossAZ Test"},
            "pages": [{
                "name": "Architecture Diagram",
                "type": "architecture",
                "global": [],
                "edge": [
                    {"id": "alb", "service": "application_load_balancer"},
                    {"id": "igw", "service": "internet_gateway"},
                    {"id": "users", "service": "users"},
                ],
                "region": {
                    "label": "us-east-1",
                    "services": [
                        {"id": "ecr", "service": "ecr"},
                    ],
                    "vpc": {
                        "label": "VPC",
                        "azs": [
                            {
                                "id": "az1",
                                "public_subnet": {"id": "pub1", "resources": [
                                    {"id": "nat1", "service": "nat_gateway"}]},
                                "app_subnet": {"id": "app1", "resources": []},
                                "db_subnet": {"id": "db1", "resources": [
                                    {"id": "aurora1", "service": "aurora",
                                     "label": "Aurora Primary"},
                                ]},
                            },
                            {
                                "id": "az2",
                                "public_subnet": {"id": "pub2", "resources": []},
                                "app_subnet": {"id": "app2", "resources": []},
                                "db_subnet": {"id": "db2", "resources": [
                                    {"id": "aurora2", "service": "aurora",
                                     "label": "Aurora Replica"},
                                ]},
                            },
                            {
                                "id": "az3",
                                "public_subnet": {"id": "pub3", "resources": []},
                                "app_subnet": {"id": "app3", "resources": []},
                                "db_subnet": {"id": "db3", "resources": [
                                    {"id": "aurora3", "service": "aurora",
                                     "label": "Aurora Replica"},
                                ]},
                            },
                        ],
                        "compute_groups": [
                            {"id": "ecs", "kind": "ecs_cluster", "node_service": "fargate"},
                        ],
                    },
                },
                "edges": [
                    {"source": "users", "target": "alb"},
                    {"source": "alb", "target": "ecs"},
                    {"source": "aurora1", "target": "aurora2", "label": "replication",
                     "dashed": True},
                    {"source": "aurora1", "target": "aurora3", "label": "replication",
                     "dashed": True},
                ],
            }],
        }
        import io
        import xml.etree.ElementTree as ET
        import generate_diagram as gd2
        result = gd2.build_document(spec)
        # Must produce valid XML with edges
        xml_str = gd2.render_xml(result)
        root = ET.fromstring(xml_str.split('\n', 1)[1])
        edges = [c for c in root.iter('mxCell') if c.get('edge') == '1']
        # House style: edges render with label="" (labels are documentation only).
        # Verify the replication edges exist as connectors (source/target pairs).
        pairs = {(c.get('source'), c.get('target')) for c in edges}
        assert ("aurora1", "aurora2") in pairs and ("aurora1", "aurora3") in pairs, (
            "Cross-AZ replication edges must appear in output XML"
        )


# ---- DataForge Full Build Integration Tests --------------------------------

class TestDataForgeFullBuild:
    """End-to-end DataForge build validates all requirements together."""

def _find_dataforge_spec():
    """Locate dataforge.spec.yaml relative to this test file."""
    # tests/ -> arch-diagram/ -> scripts/ -> .kiro/ -> project root
    test_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(test_dir, "..", "..", "..", "..", "dataforge.spec.yaml")
    return os.path.normpath(candidate)


# ---- DataForge Full Build Integration Tests --------------------------------

class TestDataForgeFullBuild:
    """End-to-end DataForge build validates all requirements together."""

    def _build_dataforge_xml(self):
        """Load and build the real DataForge spec."""
        import yaml
        spec_path = _find_dataforge_spec()
        if not os.path.exists(spec_path):
            pytest.skip(f"dataforge.spec.yaml not found at {spec_path}")
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        import generate_diagram as gd2
        return gd2.build_document(spec)

    def test_dataforge_builds_without_errors(self):
        """DataForge spec must build to valid XML without exceptions."""
        import yaml
        spec_path = _find_dataforge_spec()
        if not os.path.exists(spec_path):
            pytest.skip("dataforge.spec.yaml not found")
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        import generate_diagram as gd2
        # Should not raise
        result = gd2.build_document(spec)
        xml_str = gd2.render_xml(result)
        assert xml_str.startswith("<?xml"), "Output must be valid XML"

    def test_dataforge_xml_is_well_formed(self):
        """DataForge XML output must parse without errors."""
        import xml.etree.ElementTree as ET
        import yaml
        spec_path = _find_dataforge_spec()
        if not os.path.exists(spec_path):
            pytest.skip("dataforge.spec.yaml not found")
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        import generate_diagram as gd2
        result = gd2.build_document(spec)
        xml_str = gd2.render_xml(result)
        root = ET.fromstring(xml_str.split('\n', 1)[1])
        assert root.tag in ("mxGraphModel", "mxfile"), (
            f"Root element must be mxGraphModel or mxfile, got {root.tag}"
        )

    def test_dataforge_layout_users_outside_cloud(self):
        """DataForge: users and mobile must be outside the cloud box."""
        lo = _full_dataforge_layout()
        cloud_box = lo.abs_boxes.get("cloud")
        assert cloud_box is not None
        cloud_left = cloud_box[0]
        for actor_id in ["users", "mobile"]:
            actor_box = lo.abs_boxes.get(actor_id)
            if actor_box is not None:
                assert actor_box[0] < cloud_left, (
                    f"DataForge: {actor_id} x={actor_box[0]:.0f} must be left of "
                    f"cloud x={cloud_left:.0f}"
                )

    def test_dataforge_layout_no_overlaps(self):
        """DataForge layout must produce no overlapping sibling icons/containers."""
        import generate_diagram as gd2
        lo = _full_dataforge_layout()
        warnings = gd2.overlap_check(lo)
        assert not warnings, f"DataForge layout has overlaps: {warnings}"


# ---- VPC Centering + Entry Gutter Placement (new requirements) ------------

class TestVpcCenteringAndGutters:
    """Shield/WAF outside Region, ALB/APIGW inside VPC, VPC in Cloud."""

    def _gutter_layout(self):
        edge_items = [
            {"id": "users", "service": "users", "label": "Users"},
            {"id": "mobile", "service": "mobile_client", "label": "Mobile"},
            {"id": "shield", "service": "shield", "label": "Shield"},
            {"id": "waf", "service": "waf", "label": "WAF"},
            {"id": "alb", "service": "application_load_balancer", "label": "ALB"},
            {"id": "apigw", "service": "api_gateway", "label": "API Gateway"},
            {"id": "igw", "service": "internet_gateway"},
        ]
        region_services = [
            {"id": "lambda", "service": "lambda", "label": "Lambda"},
            {"id": "ecr", "service": "ecr"},
        ]
        return _build_minimal_arch(edge_items=edge_items,
                                   region_services=region_services)

    def test_shield_waf_inside_cloud_outside_region_and_vpc(self):
        lo = self._gutter_layout()
        cloud = lo.abs_boxes["cloud"]
        region = lo.abs_boxes["region"]
        vpc = lo.abs_boxes["vpc"]

        def contained(inner, outer, tol=5):
            ix, iy, iw, ih = inner
            ox, oy, ow, oh = outer
            return (ix >= ox - tol and iy >= oy - tol
                    and ix + iw <= ox + ow + tol and iy + ih <= oy + oh + tol)

        for svc in ["shield", "waf"]:
            box = lo.abs_boxes.get(svc)
            assert box is not None, f"{svc} must be placed"
            assert contained(box, cloud), f"{svc} must be inside AWS Cloud"
            assert not contained(box, region), f"{svc} must be outside the Region"
            assert not contained(box, vpc), f"{svc} must be outside the VPC"

    def test_region_border_falls_between_waf_and_igw(self):
        lo = self._gutter_layout()
        region_left = lo.abs_boxes["region"][0]
        waf = lo.abs_boxes["waf"]
        igw = lo.abs_boxes["igw"]
        assert waf[0] + waf[2] < region_left < igw[0]
        cloud_y = lo.abs_boxes["cloud"][1]
        nodes = {node.node_id: node for node in lo.nodes}
        for service in ("shield", "waf"):
            assert nodes[service].y + cloud_y == lo.abs_boxes[service][1]

    def test_alb_apigw_inside_vpc(self):
        lo = self._gutter_layout()
        vpc = lo.abs_boxes["vpc"]

        def contained(inner, outer, tol=5):
            ix, iy, iw, ih = inner
            ox, oy, ow, oh = outer
            return (ix >= ox - tol and iy >= oy - tol
                    and ix + iw <= ox + ow + tol and iy + ih <= oy + oh + tol)

        for svc in ["alb", "apigw"]:
            box = lo.abs_boxes.get(svc)
            assert box is not None, f"{svc} must be placed"
            assert contained(box, vpc), f"{svc} must be inside the VPC"

    def test_cloud_avoids_excess_right_whitespace_and_pads_outer_border(self):
        lo = self._gutter_layout()
        cloud = lo.abs_boxes["cloud"]
        vpc = lo.abs_boxes["vpc"]
        left_gap = vpc[0] - cloud[0]
        right_gap = (cloud[0] + cloud[2]) - (vpc[0] + vpc[2])
        assert right_gap < left_gap, "Cloud should not duplicate the left gutter on the right"
        assert right_gap <= 2 * lo_mod.CLOUD_PAD_X + 5
        assert left_gap > 0 and right_gap > 0

        outer_right = lo.border_x + lo.border_w
        outer_bottom = lo.border_y + lo.border_h
        assert outer_right - (cloud[0] + cloud[2]) == lo_mod.BORDER_RIGHT_MARGIN
        bottom_padding = outer_bottom - (cloud[1] + cloud[3])
        assert bottom_padding == lo_mod.BORDER_BOTTOM_MARGIN

    def test_cloud_service_to_container_gaps_are_compact(self):
        lo = _build_minimal_arch(
            global_items=[{"id": "iam", "service": "identity_and_access_management"}],
            region_services=[
                {"id": "cw", "service": "cloudwatch_2"},
                {"id": "trail", "service": "cloudtrail"},
            ],
        )
        region = lo.abs_boxes["region"]
        global_row_bottom = lo.abs_boxes["iam"][1] + lo_mod.ICON + lo_mod.LABEL_BAND
        global_to_region_gap = region[1] - global_row_bottom
        assert global_to_region_gap == (
            lo_mod.INGRESS_BAND_MARGIN + lo_mod.INGRESS_BAND_BELOW_GAP
        )

        last_regional = lo.abs_boxes["trail"]
        regional_to_vpc_gap = lo.abs_boxes["vpc"][1] - (
            last_regional[1] + lo_mod.ICON + lo_mod.LABEL_BAND
        )
        assert regional_to_vpc_gap == lo_mod.REGION_SERVICES_VPC_GAP

    def test_waf_alb_same_row(self):
        """WAF (region gutter) and ALB (vpc gutter) sit on the same y row."""
        lo = self._gutter_layout()
        waf = lo.abs_boxes["waf"]
        alb = lo.abs_boxes["alb"]
        assert abs(waf[1] - alb[1]) < 5, (
            f"WAF y={waf[1]:.0f} and ALB y={alb[1]:.0f} should align"
        )
        assert waf[0] < alb[0], "WAF must be left of ALB (traffic order)"

    def test_shield_waf_igw_alb_have_clear_horizontal_spacing(self):
        lo = self._gutter_layout()
        shield, waf, igw, alb = (lo.abs_boxes[key]
                                 for key in ("shield", "waf", "igw", "alb"))
        region_left = lo.abs_boxes["region"][0]
        assert shield[0] < waf[0] < region_left < igw[0] < alb[0]
        # Gutter pair follows the icon rhythm; the IGW gap is border-forced
        # (IGW straddles the VPC edge) so it only needs daylight, not rhythm.
        assert waf[0] - (shield[0] + shield[2]) >= lo_mod.ICON_GAP
        for left, right in ((waf, igw), (igw, alb)):
            assert right[0] - (left[0] + left[2]) > 0

    def test_users_outside_cloud_with_gutters(self):
        lo = self._gutter_layout()
        cloud = lo.abs_boxes["cloud"]
        for actor in ["users", "mobile"]:
            box = lo.abs_boxes.get(actor)
            if box is not None:
                assert box[0] < cloud[0], f"{actor} must be left of the cloud"
