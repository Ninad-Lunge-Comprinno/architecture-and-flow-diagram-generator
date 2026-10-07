"""CLI entry point for the architecture diagram generator.

Reads a structured YAML spec, builds the draw.io XML through the modular
pipeline (diagram → spec → arch_page / flow_page), and writes the result.

The public symbols from the submodules are re-exported here so that existing
call sites (``import generate_diagram as gd; gd.Diagram(...)``) continue to
work unchanged.

Usage:
    python generate_diagram.py --input spec.yaml [--output out.drawio.xml] [--png]
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

import layout  # noqa: F401 — re-exported for tests (gd.layout)
import shapes  # noqa: F401

# ---- Re-exports from submodules ------------------------------------------
# Tests and callers do ``import generate_diagram as gd`` then reference
# gd.Diagram, gd.SpecError, gd._route_edge, etc.  The imports below keep
# that contract intact.

from diagram import (  # noqa: F401
    Cell,
    Diagram,
    EDGE_STYLE,
    ICON_SIZE,
    PAGE_ATTRS,
    ValidationError,
    _edge_label_html,
    _label_html,
    _num,
    build_flat_diagram,
    build_mxfile,
    overlap_check,
    render_xml,
    title_block_value,
    validate,
)

from spec import (  # noqa: F401
    SpecError,
    _architecture_connectivity_warnings,
    _check_edges,
    _check_unique_ids,
    _collect_arch_ids,
    _edge_style,
    _normalize_pages,
    _validate_provider,
    _validate_services,
)

from arch_page import (  # noqa: F401
    build_architecture_page,
    _emit_arch_edges,
    _emit_arch_frame,
    _emit_arch_nodes,
    _ensure_aws_foundation_services,
    _fix_regional_placement,
    _prepare_arch_page,
    _reorder_services_for_vpc_proximity,
    _route_edge,
    _seg_hits_resource,
)

from flow_page import (  # noqa: F401
    build_flow_page,
    _count_crossings,
    _flow_label_size,
    _flow_layout,
    _flow_obstacle,
    _flow_path_length,
    _flow_point_at,
    _flow_rects_overlap,
    _minimise_flow_crossings,
    _pack_flow_rows,
    _plan_flow_ports,
    _route_flow_edge,
    _route_flow_edges,
    FLOW_PORT_ANCHORS,
    FLOW_ROW_GUTTER,
)

logger = logging.getLogger("arch_diagram")


# --------------------------------------------------------------------------
# Document builder (orchestrates page builders)
# --------------------------------------------------------------------------
def build_document(spec: dict, strict_connectivity: bool = False) -> ET.Element:
    """Validate a full spec and build the complete (possibly multi-page) mxfile."""
    if not isinstance(spec, dict):
        raise SpecError("Spec must be a mapping/object.")
    meta = spec.get("metadata") or {}
    default_provider = _validate_provider(spec.get("provider", "aws"))

    pages = _normalize_pages(spec)
    diagrams: list[Diagram] = []
    seen_page_ids: set[str] = set()
    for idx, page in enumerate(pages, start=1):
        ptype = page.get("type", "architecture")
        page_id = page.get("id", f"page-{idx}")
        if page_id in seen_page_ids:
            raise SpecError(f"Duplicate page id {page_id!r}.")
        seen_page_ids.add(page_id)
        page_meta = dict(meta)
        if ptype == "architecture":
            diagrams.append(build_architecture_page(
                page, default_provider, page_id, page_meta,
                strict_connectivity=strict_connectivity,
            ))
        elif ptype == "flow":
            diagrams.append(build_flow_page(page, default_provider, page_id, page_meta))
        else:
            raise SpecError(
                f"Page {page.get('name', page_id)!r} has invalid type {ptype!r}; "
                "expected 'architecture' or 'flow'."
            )

    mxfile = build_mxfile(diagrams)
    validate(mxfile)
    return mxfile


# --------------------------------------------------------------------------
# Output-path resolution (pure logic, testable without filesystem)
# --------------------------------------------------------------------------
def _derive_slug(project_name: str, input_path: str) -> str:
    """Derive a filesystem-safe folder slug from the project name."""
    if project_name:
        return re.sub(r"[^a-zA-Z0-9]+", "-", project_name).strip("-").lower()
    return os.path.splitext(os.path.basename(input_path))[0]


def _spec_stem(input_path: str) -> str:
    """Return the spec filename stem, stripping a trailing ``.spec`` suffix."""
    stem = os.path.splitext(os.path.basename(input_path))[0]
    if stem.endswith(".spec"):
        stem = stem[:-len(".spec")]
    return stem


def resolve_output_path(spec: dict, input_path: str,
                        output: Optional[str], output_dir: Optional[str]) -> str:
    """Resolve the final .drawio.xml path from the CLI flags and the spec."""
    if output:
        return output
    project_name = (spec.get("metadata") or {}).get("project", "")
    slug = _derive_slug(project_name, input_path)
    stem = _spec_stem(input_path)
    return os.path.join(output_dir or "outputs", slug, f"{stem}.drawio.xml")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a draw.io diagram from a spec.")
    parser.add_argument("--input", required=True, help="Path to spec YAML/JSON.")
    parser.add_argument(
        "--output",
        help="Path to write .drawio.xml. Required unless --output-dir is given.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help=(
            "Root output directory. The diagram is written to "
            "DIR/<project-slug>/<spec-stem>.drawio.xml, creating the folder "
            "automatically. Ignored when --output is also supplied. "
            "Default: outputs/ (relative to the current working directory)."
        ),
    )
    parser.add_argument(
        "--strict-connectivity", action="store_true",
        help="Do not emit diagrams with unresolved architecture connectivity warnings.",
    )
    parser.add_argument(
        "--png", action="store_true",
        help="Also render a PNG preview of each page next to the XML (needs Pillow).",
    )
    parser.add_argument(
        "--png-scale", type=float, default=0.5,
        help="Scale factor for the PNG preview (default 0.5).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Emit DEBUG-level diagnostics on stderr.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.output and not args.output_dir:
        args.output_dir = "outputs"

    import yaml  # local import — module loads without PyYAML for unit tests

    # --- Read + parse the spec (guarded) ---------------------------------
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
    except OSError as exc:
        logger.error("cannot read input spec %r: %s", args.input, exc)
        return 2
    except yaml.YAMLError as exc:
        logger.error("invalid YAML in %r: %s", args.input, exc)
        return 2

    if not isinstance(spec, dict):
        logger.error("spec %r did not parse to a mapping/object.", args.input)
        return 2

    output_path = resolve_output_path(spec, args.input, args.output, args.output_dir)

    # --- Build the document (guarded) ------------------------------------
    try:
        mxfile = build_document(spec, strict_connectivity=args.strict_connectivity)
    except (SpecError, ValidationError) as exc:
        logger.error("%s", exc)
        return 2

    xml = render_xml(mxfile)

    # --- Write the output (guarded) --------------------------------------
    try:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(xml)
    except OSError as exc:
        logger.error("cannot write output %r: %s", output_path, exc)
        return 2

    logger.info("wrote %s", output_path)

    # Optional PNG preview for visual inspection.
    if args.png:
        try:
            import render_png
            png_paths = render_png.render_file(output_path, scale=args.png_scale)
            for p in png_paths:
                logger.info("rendered %s", p)
        except ImportError:
            logger.warning(
                "--png requested but Pillow is not installed; skipping preview. "
                "Install with: pip install Pillow"
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("PNG preview failed (%s); XML was still written.", exc)

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
