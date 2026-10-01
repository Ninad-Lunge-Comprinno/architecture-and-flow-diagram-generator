"""Tests for the XML emission core (generate_diagram.py)."""

import xml.etree.ElementTree as ET

import pytest

import generate_diagram as gd


def _spec():
    return {
        "provider": "aws",
        "metadata": {
            "project": "Test Architecture",
            "version": "1.0",
            "date": "2026-09-22",
            "creator": "Tester",
            "reviewer": "Reviewer",
        },
        "resources": [
            {"id": "r53", "service": "route_53", "x": 40, "y": 40},
            {"id": "cf", "service": "cloudfront", "x": 240, "y": 40},
            {"id": "s3", "service": "s3", "x": 440, "y": 40},
        ],
        "edges": [
            {"source": "r53", "target": "cf", "label": "DNS"},
            {"source": "cf", "target": "s3", "label": "Origin"},
        ],
    }


def test_build_and_validate_flat_diagram():
    mxfile = gd.build_flat_diagram(_spec())
    # validate() runs inside build; reaching here means it passed
    assert mxfile.tag == "mxfile"


def test_output_is_well_formed_xml():
    mxfile = gd.build_flat_diagram(_spec())
    xml = gd.render_xml(mxfile)
    # Re-parse to confirm well-formedness
    parsed = ET.fromstring(xml.split("?>", 1)[1])
    assert parsed.tag == "mxfile"


def test_structural_cells_present():
    mxfile = gd.build_flat_diagram(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    ids = [c.get("id") for c in root.findall("mxCell")]
    assert "0" in ids and "1" in ids


def test_ids_are_unique():
    mxfile = gd.build_flat_diagram(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    ids = [c.get("id") for c in root.findall("mxCell")]
    assert len(ids) == len(set(ids))


def test_edges_reference_existing_vertices():
    mxfile = gd.build_flat_diagram(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    cells = root.findall("mxCell")
    id_set = {c.get("id") for c in cells}
    for c in cells:
        if c.get("edge") == "1":
            assert c.get("source") in id_set
            assert c.get("target") in id_set


def test_title_block_contains_metadata():
    mxfile = gd.build_flat_diagram(_spec())
    xml = gd.render_xml(mxfile)
    assert "Test Architecture" in xml
    assert "Version: 1.0" in xml
    assert "Date: 2026-09-22" in xml
    assert "Creator: Tester" in xml
    assert "Reviewer: Reviewer" in xml


def test_missing_metadata_fields_use_fill_in_placeholders_on_both_page_types():
    spec = {
        "provider": "aws",
        "metadata": {},
        "pages": [
            {"name": "Architecture", "type": "architecture",
             "region": {"vpc": {"azs": []}}, "edges": []},
            {"name": "Flow", "type": "flow",
             "nodes": [{"id": "s3", "service": "s3"}], "edges": []},
        ],
    }
    xml = gd.render_xml(gd.build_document(spec))
    assert xml.count("To be filled") == 10
    for label in ("Version", "Date", "Creator", "Reviewer"):
        assert xml.count(f"{label}: To be filled") == 2


def test_vertex_and_edge_flags_mutually_exclusive():
    mxfile = gd.build_flat_diagram(_spec())
    root = mxfile.find("diagram/mxGraphModel/root")
    for c in root.findall("mxCell"):
        assert not (c.get("vertex") == "1" and c.get("edge") == "1")


def test_html_label_is_escaped_in_value():
    d = gd.Diagram("P", "page-1")
    d.add_icon("aws", "ec2", label="A & B <test>")
    xml = gd.render_xml(gd.build_mxfile([d]))
    # raw special chars must not appear unescaped inside the value
    assert "A &amp; B &lt;test&gt;" in xml


def test_architecture_connectivity_warnings_catch_missing_entry_and_origin_paths():
    page = {
        "global": [
            {"id": "cdn", "service": "cloudfront"},
            {"id": "video_origin", "service": "s3", "label": "Video Origin"},
        ],
        "edge": [{"id": "viewers", "service": "users"}],
        "region": {"services": [], "vpc": {"azs": [], "compute_groups": []}},
        "edges": [],
    }
    warnings = gd._architecture_connectivity_warnings(page)
    assert any("no path to a public entry service" in warning for warning in warnings)
    assert any("no edge to a named origin" in warning for warning in warnings)


def test_architecture_connectivity_warning_prefers_shared_cluster_target():
    page = {
        "edge": [{"id": "alb", "service": "application_load_balancer"}],
        "region": {
            "services": [],
            "vpc": {
                "azs": [{"id": "az1"}],
                "compute_groups": [
                    {"id": "eks", "kind": "eks_cluster", "node_service": "ec2"},
                ],
            },
        },
        "edges": [{"source": "alb", "target": "eks-az1"}],
    }
    warnings = gd._architecture_connectivity_warnings(page)
    assert any("use shared cluster 'eks'" in warning for warning in warnings)


def test_strict_connectivity_blocks_incomplete_architecture():
    spec = {
        "provider": "aws",
        "metadata": {"project": "Incomplete"},
        "pages": [{
            "name": "Architecture",
            "type": "architecture",
            "global": [
                {"id": "cdn", "service": "cloudfront"},
                {"id": "origin", "service": "s3", "label": "Video Origin"},
            ],
            "edge": [{"id": "viewers", "service": "users"}],
            "region": {"services": [], "vpc": {"azs": [], "compute_groups": []}},
            "edges": [],
        }],
    }
    with pytest.raises(gd.SpecError, match="connectivity checks failed"):
        gd.build_document(spec, strict_connectivity=True)


def test_uncompressed_no_compressed_attr():
    mxfile = gd.build_flat_diagram(_spec())
    xml = gd.render_xml(mxfile)
    assert "compressed" not in xml


def test_validation_catches_dangling_edge():
    d = gd.Diagram("P", "page-1")
    d.add_icon("aws", "ec2", cell_id="a")
    # edge to a non-existent target
    d.add_edge(source="a", target="ghost")
    with pytest.raises(gd.ValidationError):
        gd.validate(gd.build_mxfile([d]))
