"""End-to-end golden (snapshot) tests for the full spec -> XML pipeline.

Each fixture spec under ``review/fixtures/`` is rendered through the real
``build_document`` + ``render_xml`` path and compared byte-for-byte against a
committed ``*.golden.xml`` snapshot. This is a regression safety net: any change
that alters emitted geometry, routing, styles, or structure will fail here.

Because output is deterministic, the goldens double as documentation of the
current rendering behaviour.

To (re)generate the goldens after an *intentional* behaviour change:

    UPDATE_GOLDEN=1 pytest .kiro/scripts/arch-diagram/tests/test_golden_e2e.py

Review the resulting diff carefully before committing — an unreviewed golden
update defeats the purpose of the snapshot.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import generate_diagram as gd

yaml = pytest.importorskip("yaml")

# review/fixtures lives at the repo root: tests/ -> arch-diagram -> scripts ->
# .kiro -> <repo root>.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE_DIR = _REPO_ROOT / "review" / "fixtures"
_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# Representative fixtures: a standard 3-tier arch page, a multi-lane arch page,
# and a branch/merge flow page. Together they exercise containers, compute-group
# lanes, architecture edge routing, and flow layout + routing.
_FIXTURES = ["3tier-basic", "multi-lane", "flow-branch-merge"]

_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


def _render(spec_name: str) -> str:
    spec_path = _FIXTURE_DIR / f"{spec_name}.spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    mxfile = gd.build_document(spec)  # validate() runs inside build_document
    return gd.render_xml(mxfile)


@pytest.mark.parametrize("spec_name", _FIXTURES)
def test_golden_snapshot(spec_name):
    """Rendered XML matches the committed golden byte-for-byte."""
    rendered = _render(spec_name)
    golden_path = _GOLDEN_DIR / f"{spec_name}.golden.xml"

    if _UPDATE:
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(rendered, encoding="utf-8")
        pytest.skip(f"updated golden: {golden_path.name}")

    assert golden_path.is_file(), (
        f"missing golden {golden_path}; regenerate with "
        f"UPDATE_GOLDEN=1 pytest {Path(__file__).name}"
    )
    expected = golden_path.read_text(encoding="utf-8")
    assert rendered == expected, (
        f"rendered XML for {spec_name!r} drifted from its golden. If this change "
        f"is intentional, regenerate with UPDATE_GOLDEN=1 and review the diff."
    )


@pytest.mark.parametrize("spec_name", _FIXTURES)
def test_rendered_output_is_well_formed_and_valid(spec_name):
    """The pipeline output parses as XML and passes the draw.io checklist.

    This holds independently of the goldens, so a stale golden can never mask a
    structurally broken document.
    """
    rendered = _render(spec_name)

    # Well-formed: strip the XML declaration, then parse.
    body = rendered.split("?>", 1)[1]
    root = ET.fromstring(body)
    assert root.tag == "mxfile"

    # Structural validity (unique ids, valid parents, edge endpoints, etc.).
    gd.validate(root)

    # Round-trip: re-serialising the parsed tree stays well-formed.
    ET.fromstring(ET.tostring(root, encoding="unicode"))
