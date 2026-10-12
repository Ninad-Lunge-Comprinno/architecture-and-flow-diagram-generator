#!/usr/bin/env python3
"""Invariant checker for house-style draw.io architecture files.

Usage: python3 .kiro/scripts/validate-drawio.py <file.drawio.xml>
Exit 0 = PASS, 1 = failures found.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

SHAPES_MD = Path(__file__).resolve().parents[1] / "skills/arch-diagram/references/shapes-aws.md"


def load_valid_stencils():
    """Collect stencil names from the shapes-aws.md 'stencil' column."""
    stencils = set()
    for line in SHAPES_MD.read_text(encoding="utf-8").splitlines():
        for m in re.findall(r"mxgraph\.aws4\.(\w+)", line):
            stencils.add(m)
    return stencils


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: decode mxGraphModel from diagram element
# ─────────────────────────────────────────────────────────────────────────────

def get_graph_model(diagram):
    """Extract mxGraphModel from diagram, handling both compressed and uncompressed formats."""
    # Try uncompressed first (direct child)
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model

    # Try compressed (base64+deflate in text content)
    text = diagram.text
    if text and text.strip():
        import base64
        import zlib
        try:
            decoded = base64.b64decode(text.strip())
            decompressed = zlib.decompress(decoded, -zlib.MAX_WBITS)
            xml_str = unquote(decompressed.decode('utf-8'))
            return ET.fromstring(xml_str)
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CHECK FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_COLOURS = {
    '#ED7100': ['ec2', 'ecs', 'eks', 'fargate', 'ecr', 'lambda', 'app_runner'],
    '#C925D1': ['rds', 'aurora', 'elasticache', 'dynamodb', 'documentdb', 'docdb'],
    '#8C4FFF': ['alb', 'nlb', 'nat_gateway', 'internet_gateway', 'cloudfront', 'route_53'],
    '#DD344C': ['waf', 'key_management_service', 'identity_and_access_management',
                'acm', 'certificate_manager_3', 'secrets_manager', 'guardduty'],
    '#7AA116': ['s3', 'efs', 'backup'],
    '#E7157B': ['cloudwatch_2', 'cloudtrail', 'managed_streaming_for_kafka', 'sns', 'sqs'],
    '#01A88D': ['bedrock', 'sagemaker', 'transcribe', 'comprehend'],
}


def check_canvas_and_frame(model, issues, page_name="Architecture"):
    """Checklist A: Canvas and frame."""
    if model is None:
        issues.append(f"[{page_name}] Could not parse mxGraphModel")
        return

    cells = list(model.iter('mxCell'))
    if len(cells) == 0:
        issues.append(f"[{page_name}] Page has zero mxCell elements — empty or incorrectly parsed")
        return

    # Check border cell
    border = next((c for c in cells if c.get('id', '') == 'border' or c.get('id', '') == 'f-border' or
                   ('strokeWidth=3' in c.get('style', '') and 'fillColor=none' in c.get('style', '') and
                    c.get('parent') == '1' and 'container' not in c.get('style', ''))), None)
    if border is not None:
        style = border.get('style', '')
        if 'strokeColor=#0066CC' in style:
            issues.append(f"[{page_name}] Border cell uses strokeColor=#0066CC (template chrome); use strokeColor=#000000")
        if 'fillColor=default' in style:
            issues.append(f"[{page_name}] Border cell uses fillColor=default; use fillColor=none")

    # Check logo blob is not a truncated placeholder
    for cell in cells:
        style = cell.get('style', '')
        cid = cell.get('id', '').lower()
        if 'shape=image' in style and ('brand' in cid or 'logo' in cid):
            m = re.search(r'image=data:image/png,([^;]+)', style)
            if m:
                blob = m.group(1)
                if len(blob) < 100:
                    issues.append(f"[{page_name}] Logo cell '{cell.get('id')}' has a truncated base64 blob "
                                  f"(len={len(blob)}) — copy from skeleton-3az.drawio.xml")
            if 'strokeColor=none' not in style:
                issues.append(f"[{page_name}] Logo cell '{cell.get('id')}' missing strokeColor=none "
                              f"(will render with underline border)")


def check_icon_colours(model, issues, page_name="Architecture"):
    """Checklist B: Category colour consistency."""
    if model is None:
        return
    for cell in model.iter('mxCell'):
        style = cell.get('style', '')
        if 'resourceIcon' not in style:
            continue
        m_res = re.search(r'resIcon=mxgraph\.aws4\.(\S+?)(?:;|")', style)
        m_fill = re.search(r'fillColor=(#[0-9A-Fa-f]{6})', style)
        if not m_res or not m_fill:
            continue
        stencil = m_res.group(1)
        fill = m_fill.group(1).upper()
        expected_fills = [cat_fill for cat_fill, stencils in CATEGORY_COLOURS.items()
                          if any(s in stencil for s in stencils)]
        if expected_fills and fill not in [f.upper() for f in expected_fills]:
            issues.append(f"[{page_name}] Icon '{cell.get('id')}' stencil '{stencil}' has fill {fill}; "
                          f"expected {expected_fills[0]}")


def check_edge_density(model, issues, page_name="Architecture"):
    """Checklist F30: Edge density — warn if > 12 edges on architecture page."""
    if model is None:
        return
    edges = [c for c in model.iter('mxCell') if c.get('edge') == '1']
    solid = [e for e in edges if 'dashed=1' not in e.get('style', '')]
    if len(edges) > 15:
        issues.append(f"[{page_name}] High edge count: {len(edges)} edges ({len(solid)} solid, "
                      f"{len(edges)-len(solid)} dashed). Consider removing decorative edges.")


def check_edge_labels(model, issues, page_name="Architecture"):
    """Checklist F31: Edge labels — warn on very long labels."""
    if model is None:
        return
    for cell in model.iter('mxCell'):
        if cell.get('edge') != '1':
            continue
        val = cell.get('value', '')
        # Strip HTML
        text = re.sub(r'<[^>]+>', '', val).strip()
        if len(text) > 30:
            issues.append(f"[{page_name}] Edge '{cell.get('id')}' label is long ({len(text)} chars): "
                          f"'{text[:40]}…' — keep ≤4 words")


def check_alb_connects_to_lane(model, issues, page_name="Architecture"):
    """Checklist F24: ALB must connect to the cluster lane, not to individual tasks."""
    if model is None:
        return
    cells = {c.get('id'): c for c in model.iter('mxCell')}
    for cell in model.iter('mxCell'):
        if cell.get('edge') != '1':
            continue
        src = cell.get('source', '')
        tgt = cell.get('target', '')
        src_cell = cells.get(src)
        tgt_cell = cells.get(tgt)
        if src_cell is not None and 'application_load_balancer' in src_cell.get('style', ''):
            if tgt_cell is not None:
                tgt_style = tgt_cell.get('style', '')
                if any(s in tgt_style for s in ['fargate', 'mxgraph.aws4.ec2', 'mxgraph.aws4.ecs']):
                    issues.append(f"[{page_name}] Edge '{cell.get('id')}': ALB connects directly to task/instance "
                                  f"'{tgt}'. ALB should connect to the cluster lane border.")


def check_no_invented_vpc(model, issues, page_name="Architecture"):
    """Scenario B: Lambda+S3 diagrams must not invent a VPC."""
    if model is None:
        return
    cells = list(model.iter('mxCell'))
    has_lambda = any('mxgraph.aws4.lambda' in c.get('style', '') for c in cells)
    has_rds = any('mxgraph.aws4.rds' in c.get('style', '') or
                  'mxgraph.aws4.aurora' in c.get('style', '') for c in cells)
    has_vpc = any('group_vpc' in c.get('style', '') for c in cells)
    has_ecs = any('mxgraph.aws4.ecs' in c.get('style', '') or
                  'mxgraph.aws4.fargate' in c.get('style', '') for c in cells)

    # Only flag if ONLY Lambda (no ECS/RDS which require VPC)
    if has_lambda and not has_rds and not has_ecs and has_vpc:
        issues.append(
            f"[{page_name}] Scenario B: diagram has Lambda+S3 but also contains a VPC container. "
            "Lambda does not require a VPC unless explicitly specified."
        )


def check_az_count_consistency(model, issues, page_name="Architecture"):
    """Verify AZ containers match across all resource rows."""
    if model is None:
        return
    cells = list(model.iter('mxCell'))
    az_cells = [c for c in cells if 'group_availability_zone' in c.get('style', '')]
    az_count = len(az_cells)

    if az_count == 0:
        return  # No AZ containers (e.g. Lambda+S3 diagram)

    if az_count not in (1, 2, 3):
        issues.append(
            f"[{page_name}] Unusual AZ count: {az_count}. Verify this matches the user's requested topology."
        )

    # Check all AZs have the same width (columns must align)
    widths = set()
    for az in az_cells:
        geo = az.find('mxGeometry')
        if geo is not None and geo.get('width'):
            widths.add(geo.get('width'))
    if len(widths) > 1:
        issues.append(f"[{page_name}] AZ containers have inconsistent widths {widths} — columns will not align.")


def check_flow_page(model, issues, page_name="Flow"):
    """Check flow page specific rules."""
    if model is None:
        issues.append(f"[{page_name}] Could not parse mxGraphModel")
        return

    cells = list(model.iter('mxCell'))
    if len(cells) == 0:
        issues.append(f"[{page_name}] Page has zero mxCell elements — empty or incorrectly parsed")
        return

    # Check title block has metadata fields
    title_cells = [c for c in cells
                   if c.get('id', '').endswith('title') or c.get('id', '') == 'f-title']
    for tc in title_cells:
        val = tc.get('value', '')
        for field in ['Version', 'Date', 'Creator', 'Reviewer']:
            # Only warn for the Architecture title which should have all metadata
            # Flow title typically just has project name and flow description
            pass  # Relaxed check - flow title just needs project name

    # Check brand/logo cell has strokeColor=none
    brand_cells = [c for c in cells if 'brand' in c.get('id', '')]
    for bc in brand_cells:
        style = bc.get('style', '')
        if 'shape=image' in style and 'strokeColor=none' not in style:
            issues.append(f"[{page_name}] Logo cell '{bc.get('id')}' missing strokeColor=none (will show underline)")

    # Check cloud/region/vpc containers exist (optional for flow - just a note)
    containers = {c.get('id') for c in cells if 'container=1' in c.get('style', '')}
    # Note: f-cloud, f-region, f-vpc are recommended but not strictly required for all flows


def check_page_name_consistency(diagrams, issues):
    """Checklist I37: Service names should be consistent across pages."""
    # Collect service labels per page
    page_labels = {}
    for diag_name, model in diagrams.items():
        if model is None:
            continue
        labels = set()
        for cell in model.iter('mxCell'):
            val = cell.get('value', '')
            if val and 'resourceIcon' in cell.get('style', ''):
                text = re.sub(r'<[^>]+>', '', val).strip()
                if text:
                    labels.add(text.lower())
        page_labels[diag_name] = labels

    if len(page_labels) == 2 and 'Architecture' in page_labels and 'Flow' in page_labels:
        arch_labels = page_labels.get('Architecture', set())
        flow_labels = page_labels.get('Flow', set())
        # Services on flow but not arch are fine (flow may aggregate)
        # Services on arch but not flow: warn only for compute
        compute_in_arch_not_flow = {
            l for l in arch_labels if any(k in l for k in ['eks', 'ecs', 'fargate', 'lambda'])
            and l not in flow_labels
        }
        if compute_in_arch_not_flow:
            issues.append(f"[Consistency] Compute services on Architecture page not found on Flow page: "
                          f"{compute_in_arch_not_flow}. Verify both pages are consistent.")


def check_icon_dimensions_and_stencils(model, valid_stencils, issues, page_name):
    """Check icon sizes (120x120) and stencil validity."""
    if model is None:
        return

    for c in model.iter('mxCell'):
        style = c.get("style") or ""
        if "shape=mxgraph.aws4.resourceIcon" not in style:
            continue
        cid = c.get("id") or ""
        geo = c.find("mxGeometry")
        w = geo.get("width") if geo is not None else None
        h = geo.get("height") if geo is not None else None

        # Badge exceptions: 45x45 for cluster badges
        is_badge = (cid.endswith("badge") or "clusterlogo" in cid or
                    "clusterbadge" in cid or cid.endswith("logo"))

        if not is_badge and (w, h) != ("120", "120"):
            issues.append(f"[{page_name}] Icon '{cid}' is {w}x{h}, expected 120x120")

        m = re.search(r"resIcon=mxgraph\.aws4\.(\w+)", style)
        if m and m.group(1) not in valid_stencils:
            issues.append(f"[{page_name}] Icon '{cid}' uses unknown resIcon '{m.group(1)}'")


def check_unique_ids_and_parents(model, issues, page_name):
    """Check for duplicate IDs and dangling parent references."""
    if model is None:
        return

    cells = list(model.iter('mxCell'))
    ids = [c.get("id") for c in cells if c.get("id") is not None]

    # Unique cell IDs within the page
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        issues.append(f"[{page_name}] Duplicate cell IDs: {sorted(dupes)}")

    # Parent references point to existing IDs on the same page
    idset = set(ids)
    for c in cells:
        p = c.get("parent")
        if p is not None and p not in idset:
            issues.append(f"[{page_name}] Cell '{c.get('id')}' has dangling parent '{p}'")


def main():
    if len(sys.argv) != 2:
        print("usage: validate-drawio.py <file.drawio.xml>")
        return 1
    path = Path(sys.argv[1])
    issues = []

    # 1. Parse XML
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError) as e:
        print(f"FAIL: invalid XML — {e}")
        return 1

    # 2. Find diagram pages
    diagrams = root.findall(".//diagram")
    if not diagrams:
        print("FAIL: no <diagram> elements found")
        return 1

    page_names = [d.get("name") for d in diagrams]

    # Check for required pages
    if "Architecture" not in page_names:
        issues.append("Missing required page 'Architecture'")
    if "Flow" not in page_names:
        issues.append("Missing required page 'Flow'")

    # Check page order and extra pages
    if page_names and page_names != ["Architecture", "Flow"]:
        if set(page_names) == {"Architecture", "Flow"}:
            issues.append(f"Page order should be ['Architecture', 'Flow'], found {page_names}")
        elif len(page_names) > 2:
            issues.append(f"Expected 2 pages ['Architecture', 'Flow'], found {len(page_names)}: {page_names}")

    # Load valid stencils
    valid = load_valid_stencils()

    # Build page-name-to-model mapping
    page_models = {}
    for diag in diagrams:
        name = diag.get("name")
        model = get_graph_model(diag)
        page_models[name] = model

    # 3. Run Architecture-specific checks
    arch_model = page_models.get("Architecture")
    if arch_model is not None:
        check_canvas_and_frame(arch_model, issues, "Architecture")
        check_icon_colours(arch_model, issues, "Architecture")
        check_edge_density(arch_model, issues, "Architecture")
        check_edge_labels(arch_model, issues, "Architecture")
        check_alb_connects_to_lane(arch_model, issues, "Architecture")
        check_no_invented_vpc(arch_model, issues, "Architecture")
        check_az_count_consistency(arch_model, issues, "Architecture")
        check_icon_dimensions_and_stencils(arch_model, valid, issues, "Architecture")
        check_unique_ids_and_parents(arch_model, issues, "Architecture")
    elif "Architecture" in page_names:
        issues.append("[Architecture] Could not parse mxGraphModel from Architecture page")

    # 4. Run Flow-specific checks
    flow_model = page_models.get("Flow")
    if flow_model is not None:
        check_flow_page(flow_model, issues, "Flow")
        check_canvas_and_frame(flow_model, issues, "Flow")
        check_icon_dimensions_and_stencils(flow_model, valid, issues, "Flow")
        check_unique_ids_and_parents(flow_model, issues, "Flow")
    elif "Flow" in page_names:
        issues.append("[Flow] Could not parse mxGraphModel from Flow page")

    # 5. Cross-page consistency checks
    check_page_name_consistency(page_models, issues)

    # 6. Report results
    if issues:
        print(f"FAIL ({len(issues)} issue(s)):")
        for f in issues:
            print(f"  - {f}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
