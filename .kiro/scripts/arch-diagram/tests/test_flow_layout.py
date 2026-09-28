"""Tests for the flow page layered layout."""

import generate_diagram as gd


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


def test_linear_chain_is_top_down():
    pos = gd._flow_layout(**_flow_spec_linear())
    # Each node in the chain should be below the previous
    assert pos["a"][1] < pos["b"][1] < pos["c"][1] < pos["d"][1]


def test_linear_chain_same_column():
    pos = gd._flow_layout(**_flow_spec_linear())
    # Linear chain nodes share the same x (centred in a 1-wide layer)
    xs = {round(pos[nid][0]) for nid in ("a", "b", "c", "d")}
    assert len(xs) == 1


def test_fan_out_sibling_nodes_same_row():
    pos = gd._flow_layout(**_flow_spec_fan())
    # b and c are siblings (both children of a) so same y
    assert abs(pos["b"][1] - pos["c"][1]) < 5


def test_fan_out_siblings_different_x():
    pos = gd._flow_layout(**_flow_spec_fan())
    # Siblings are spread horizontally
    assert abs(pos["b"][0] - pos["c"][0]) > 100


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
