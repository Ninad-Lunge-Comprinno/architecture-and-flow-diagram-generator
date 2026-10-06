"""Tests for the overlap_check() validator."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

import generate_diagram as gd
import layout


def _build_lo():
    page = {
        "region": {"vpc": {"azs": [
            {"id": "az1",
             "public_subnet": {"id": "pub1", "resources": [{"id": "nat1", "service": "nat_gateway"}]},
             "app_subnet": {"id": "app1", "resources": []},
             "db_subnet": {"id": "db1", "resources": [{"id": "cache1", "service": "elasticache"},
                                                       {"id": "rds1", "service": "rds"}]}},
            {"id": "az2",
             "public_subnet": {"id": "pub2", "resources": []},
             "app_subnet": {"id": "app2", "resources": []},
             "db_subnet": {"id": "db2", "resources": [{"id": "rds2", "service": "rds"}]}},
            {"id": "az3",
             "public_subnet": {"id": "pub3", "resources": []},
             "app_subnet": {"id": "app3", "resources": []},
             "db_subnet": {"id": "db3", "resources": [{"id": "rds3", "service": "rds"}]}},
        ], "compute_groups": [
            {"id": "ecs", "kind": "ecs_cluster", "node_service": "fargate"},
        ]}},
    }
    return layout.build(page, "aws")


def test_no_overlaps_in_valid_layout():
    lo = _build_lo()
    warnings = gd.overlap_check(lo)
    # Intentional lane-over-AZ overlaps are excluded; no unexpected overlaps
    assert warnings == [], f"Unexpected overlaps: {warnings}"


def test_overlap_check_returns_empty_for_none():
    assert gd.overlap_check(None) == []


def test_overlap_check_detects_synthetic_overlap():
    """Inject a fake layout with two sibling icons at the same position."""
    import types
    lo = types.SimpleNamespace()
    lo.abs_boxes = {
        "icon_a": (100, 100, 120, 120),
        "icon_b": (150, 110, 120, 120),  # clearly overlapping icon_a
    }
    lo.nodes = [
        types.SimpleNamespace(node_id="icon_a", kind="resource", parent="subnet1"),
        types.SimpleNamespace(node_id="icon_b", kind="resource", parent="subnet1"),
    ]
    warnings = gd.overlap_check(lo)
    assert len(warnings) == 1
    assert "icon_a" in warnings[0] and "icon_b" in warnings[0]


def test_overlap_check_skips_different_parents():
    """Icons in different containers should not trigger an overlap warning."""
    import types
    lo = types.SimpleNamespace()
    lo.abs_boxes = {
        "icon_a": (100, 100, 120, 120),
        "icon_b": (150, 110, 120, 120),
    }
    lo.nodes = [
        types.SimpleNamespace(node_id="icon_a", kind="resource", parent="subnet1"),
        types.SimpleNamespace(node_id="icon_b", kind="resource", parent="subnet2"),  # different parent
    ]
    assert gd.overlap_check(lo) == []


def test_overlap_check_skips_lane_over_az():
    """Compute lanes intentionally overlap AZ rows — must not be flagged."""
    import types
    lo = types.SimpleNamespace()
    lo.abs_boxes = {
        "ecs_lane": (500, 800, 180, 1000),
        "az1":      (400, 810, 1200, 300),
    }
    lo.nodes = [
        types.SimpleNamespace(node_id="ecs_lane", kind="ecs_cluster", parent="vpc"),
        types.SimpleNamespace(node_id="az1",      kind="az",          parent="vpc"),
    ]
    assert gd.overlap_check(lo) == []
