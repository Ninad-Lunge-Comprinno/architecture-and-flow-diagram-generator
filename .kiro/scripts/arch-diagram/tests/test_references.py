"""Consistency test: reference markdown catalogs must not drift from shapes.py."""

import re
from pathlib import Path

import pytest

import shapes

REFERENCES = Path(__file__).resolve().parents[3] / "skills" / "arch-diagram" / "references"


def _keys_from_markdown(path: Path) -> set[str]:
    """Extract the first-column key from a markdown table.

    Rows look like: ``| key | category | fill | stencil | label |``.
    We skip the header row and the ``|---|`` separator, and only accept rows
    whose first cell is a bare service key (word chars) — not a header word.
    """
    keys: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0]
        # skip header / separator rows
        if first in {"key", ""} or set(first) <= set("-: "):
            continue
        if re.fullmatch(r"[a-z0-9_]+", first):
            keys.add(first)
    return keys


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_reference_md_matches_catalog(provider):
    md = REFERENCES / f"shapes-{provider}.md"
    assert md.exists(), f"missing reference file {md}"
    md_keys = _keys_from_markdown(md)
    # Re-build the catalog from the source module to get only the static keys,
    # not any runtime-dynamic keys cached by other tests.
    from importlib import import_module
    import importlib
    shapes_mod = import_module("shapes")
    # The static keys are those defined in _AWS / _AZURE / _GCP — rebuild a
    # fresh catalog snapshot by calling _build_catalog directly.
    static_catalog = shapes_mod._build_catalog()
    catalog_keys = set(static_catalog.get(provider, {}).keys())
    # Every static catalog key must be documented in the markdown.
    missing_in_md = catalog_keys - md_keys
    assert not missing_in_md, \
        f"{provider}: in shapes.py static catalog but not in md: {sorted(missing_in_md)}"


def test_skill_md_has_frontmatter():
    skill = REFERENCES.parent / "SKILL.md"
    text = skill.read_text()
    assert text.startswith("---"), "SKILL.md must start with YAML frontmatter"
    assert "name: arch-diagram" in text
    assert "description:" in text


def test_house_style_lists_container_kinds():
    house = (REFERENCES / "house-style.md").read_text()
    for kind in ("cloud", "region", "vpc", "public_subnet", "db_subnet",
                 "asg", "ecs_cluster"):
        assert kind in house, f"house-style.md should mention {kind}"
