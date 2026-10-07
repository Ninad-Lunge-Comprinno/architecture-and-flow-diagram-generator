"""Tests for the CLI entry point (main) and its pure path helpers.

Covers slug derivation, output-path resolution (including the ``.spec`` stem
stripping that the README flags as a duplicate-folder hazard), the happy-path
file write, stdout/stderr separation, and the guarded error-exit codes.
"""

import os
import textwrap

import pytest

import generate_diagram as gd


# --------------------------------------------------------------------------
# Pure path helpers (no filesystem writes)
# --------------------------------------------------------------------------
class TestSlugAndStem:
    def test_slug_from_project_name_is_kebab_lowercased(self):
        assert gd._derive_slug("Acme Orders", "x.yaml") == "acme-orders"

    def test_slug_collapses_non_alphanumerics_and_strips_edges(self):
        assert gd._derive_slug("  My_Client (v2)!! ", "x.yaml") == "my-client-v2"

    def test_slug_falls_back_to_input_stem_when_no_project(self):
        assert gd._derive_slug("", "/tmp/healthbridge.spec.yaml") == "healthbridge.spec"

    def test_spec_stem_strips_trailing_dot_spec(self):
        assert gd._spec_stem("/a/b/acme-orders.spec.yaml") == "acme-orders"

    def test_spec_stem_leaves_plain_stem_untouched(self):
        assert gd._spec_stem("/a/b/dataforge.yaml") == "dataforge"


class TestResolveOutputPath:
    _spec = {"metadata": {"project": "Acme Orders"}}

    def test_explicit_output_wins_verbatim(self):
        got = gd.resolve_output_path(
            self._spec, "acme.spec.yaml", output="/tmp/custom.drawio.xml",
            output_dir="ignored",
        )
        assert got == "/tmp/custom.drawio.xml"

    def test_output_dir_builds_slug_and_stem_path(self):
        got = gd.resolve_output_path(
            self._spec, "acme-orders.spec.yaml", output=None, output_dir="outputs",
        )
        assert got == os.path.join("outputs", "acme-orders", "acme-orders.drawio.xml")

    def test_output_dir_defaults_to_outputs_when_none(self):
        got = gd.resolve_output_path(
            self._spec, "acme-orders.spec.yaml", output=None, output_dir=None,
        )
        assert got.startswith(os.path.join("outputs", "acme-orders"))


# --------------------------------------------------------------------------
# Fixtures: minimal valid / invalid spec files on disk
# --------------------------------------------------------------------------
_VALID_SPEC = textwrap.dedent(
    """\
    provider: aws
    metadata:
      project: "CLI Test"
      version: "1.0"
    pages:
      - name: "Flow"
        type: flow
        nodes:
          - {id: s3, service: s3}
        edges: []
    """
)


@pytest.fixture
def valid_spec(tmp_path):
    p = tmp_path / "cli-test.spec.yaml"
    p.write_text(_VALID_SPEC, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# main() — happy paths
# --------------------------------------------------------------------------
class TestMainHappyPath:
    def test_explicit_output_writes_file_and_prints_path(self, valid_spec, tmp_path, capsys, caplog):
        import logging as _logging
        out = tmp_path / "diagram.drawio.xml"
        with caplog.at_level(_logging.INFO, logger="arch_diagram"):
            rc = gd.main(["--input", str(valid_spec), "--output", str(out)])
        assert rc == 0
        assert out.is_file()
        assert out.read_text(encoding="utf-8").startswith("<?xml")
        # The resolved path is the sole stdout line (for scripting).
        assert capsys.readouterr().out.strip() == str(out)
        # Operational "wrote" messaging is logged (routed to stderr at runtime).
        assert any("wrote" in r.message.lower() for r in caplog.records)

    def test_output_dir_creates_slug_folder(self, valid_spec, tmp_path, capsys):
        rc = gd.main(["--input", str(valid_spec), "--output-dir", str(tmp_path)])
        assert rc == 0
        expected = tmp_path / "cli-test" / "cli-test.drawio.xml"
        assert expected.is_file()
        assert capsys.readouterr().out.strip() == str(expected)


# --------------------------------------------------------------------------
# main() — guarded error-exit paths (return code 2, no traceback)
# --------------------------------------------------------------------------
class TestMainErrorExits:
    def test_missing_input_file_returns_2(self, tmp_path, caplog):
        import logging as _logging
        with caplog.at_level(_logging.ERROR, logger="arch_diagram"):
            rc = gd.main(["--input", str(tmp_path / "does-not-exist.yaml"),
                          "--output", str(tmp_path / "o.xml")])
        assert rc == 2
        assert any("cannot read input" in r.message.lower() for r in caplog.records)

    def test_malformed_yaml_returns_2(self, tmp_path, caplog):
        import logging as _logging
        bad = tmp_path / "bad.spec.yaml"
        bad.write_text("provider: aws\n  : : not valid yaml\n", encoding="utf-8")
        with caplog.at_level(_logging.ERROR, logger="arch_diagram"):
            rc = gd.main(["--input", str(bad), "--output", str(tmp_path / "o.xml")])
        assert rc == 2
        assert any("invalid yaml" in r.message.lower() for r in caplog.records)

    def test_non_mapping_spec_returns_2(self, tmp_path, caplog):
        import logging as _logging
        notmap = tmp_path / "list.spec.yaml"
        notmap.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with caplog.at_level(_logging.ERROR, logger="arch_diagram"):
            rc = gd.main(["--input", str(notmap), "--output", str(tmp_path / "o.xml")])
        assert rc == 2
        assert any("mapping" in r.message.lower() for r in caplog.records)

    def test_invalid_spec_contents_returns_2(self, tmp_path, caplog):
        import logging as _logging
        # Valid YAML, but not a usable spec (no pages/region/nodes).
        spec = tmp_path / "empty.spec.yaml"
        spec.write_text("provider: aws\nmetadata: {}\n", encoding="utf-8")
        with caplog.at_level(_logging.ERROR, logger="arch_diagram"):
            rc = gd.main(["--input", str(spec), "--output", str(tmp_path / "o.xml")])
        assert rc == 2
        # SpecError message is surfaced via the logger at ERROR level.
        assert any(r.levelname == "ERROR" for r in caplog.records)


# --------------------------------------------------------------------------
# Graceful degradation when the brand logo asset is unavailable (C2)
# --------------------------------------------------------------------------
def test_missing_logo_degrades_gracefully(monkeypatch, caplog):
    import logging as _logging

    d = gd.Diagram("P", "page-1")

    # Point the asset lookup at a path that does not exist by monkeypatching
    # Path.read_bytes to raise, then confirm we get "" and a warning, not a crash.
    import pathlib

    def _boom(self):
        raise FileNotFoundError(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", _boom)
    with caplog.at_level(_logging.WARNING, logger="arch_diagram"):
        cid = d.add_comprinno_mark(x=0, y=0)
    assert cid == ""
    assert any("logo unavailable" in r.message for r in caplog.records)
