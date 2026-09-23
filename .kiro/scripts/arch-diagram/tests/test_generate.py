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
    assert "Creator: Tester" in xml


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
