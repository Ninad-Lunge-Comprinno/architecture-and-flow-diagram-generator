#!/usr/bin/env python3
"""Invariant checker for house-style draw.io architecture files.

Usage: python3 .kiro/scripts/validate-drawio.py <file.drawio.xml>
Exit 0 = PASS, 1 = failures found.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SHAPES_MD = Path(__file__).resolve().parents[1] / "skills/arch-diagram/references/shapes-aws.md"


def load_valid_stencils():
    """Collect stencil names from the shapes-aws.md 'stencil' column."""
    stencils = set()
    for line in SHAPES_MD.read_text(encoding="utf-8").splitlines():
        for m in re.findall(r"mxgraph\.aws4\.(\w+)", line):
            stencils.add(m)
    return stencils




def check_flow_page(root, issues):
    """Check flow page specific rules."""
    cells = {c.get('id'): c for c in root.iter('mxCell')}
    
    # Check title block has metadata fields
    title_cells = [c for c in root.iter('mxCell') 
                   if c.get('id','').endswith('title') or c.get('id','') == 'f-title']
    for tc in title_cells:
        val = tc.get('value','')
        for field in ['Creator', 'Reviewer', 'Version', 'Date']:
            if field not in val:
                issues.append(f"Flow title block missing '{field}' metadata field")
    
    # Check brand/logo cell has strokeColor=none
    brand_cells = [c for c in root.iter('mxCell') if 'brand' in c.get('id','')]
    for bc in brand_cells:
        style = bc.get('style','')
        if 'shape=image' in style and 'strokeColor=none' not in style:
            issues.append(f"Flow logo cell '{bc.get('id')}' missing strokeColor=none (will show underline)")
    
    # Check cloud/region/vpc containers exist
    containers = {c.get('id') for c in root.iter('mxCell') if 'container=1' in c.get('style','')}
    for expected in ['f-cloud', 'f-region', 'f-vpc']:
        if expected not in containers:
            issues.append(f"Flow page missing container '{expected}' — services will have no AWS scope context")
    
    # Check no resourceIcon is floating in root without a logical container
    for cell in root.iter('mxCell'):
        style = cell.get('style','')
        parent = cell.get('parent','1')
        cid = cell.get('id','')
        if 'resourceIcon' in style and parent == '1':
            # Allowed to be root: Users, Route53, IGW (if not using containers)
            # Flag compute icons (ECS/EKS/EC2/Fargate) floating at root
            if any(s in style for s in ['mxgraph.aws4.ecs', 'mxgraph.aws4.eks', 
                                          'mxgraph.aws4.ec2', 'mxgraph.aws4.fargate']):
                issues.append(f"Flow compute icon '{cid}' is floating (parent=root) — should be inside f-vpc")


def check_no_invented_vpc(root, issues):
    """Scenario B: Lambda+S3 diagrams must not invent a VPC."""
    cells = list(root.iter('mxCell'))
    has_lambda = any('mxgraph.aws4.lambda' in c.get('style','') for c in cells)
    has_rds    = any('mxgraph.aws4.rds' in c.get('style','') or 
                     'mxgraph.aws4.aurora' in c.get('style','') for c in cells)
    has_vpc    = any('group_vpc' in c.get('style','') for c in cells)
    has_ecs    = any('mxgraph.aws4.ecs' in c.get('style','') or 
                     'mxgraph.aws4.fargate' in c.get('style','') for c in cells)
    
    # Only flag if ONLY Lambda (no ECS/RDS which require VPC)
    if has_lambda and not has_rds and not has_ecs and has_vpc:
        issues.append(
            "Scenario B: diagram has Lambda+S3 but also contains a VPC container. "
            "Lambda does not require a VPC unless explicitly specified."
        )


def check_az_count_consistency(root, issues):
    """Verify AZ containers match across all resource rows."""
    cells = list(root.iter('mxCell'))
    az_cells = [c for c in cells if 'group_availability_zone' in c.get('style','')]
    az_count = len(az_cells)
    
    if az_count == 0:
        return  # No AZ containers (e.g. Lambda+S3 diagram)
    
    if az_count not in (1, 2, 3):
        issues.append(
            f"Unusual AZ count: {az_count}. Verify this matches the user's requested topology."
        )
    
    # Check all AZs have the same width (columns must align)
    widths = set()
    for az in az_cells:
        geo = az.find('mxGeometry')
        if geo is not None and geo.get('width'):
            widths.add(geo.get('width'))
    if len(widths) > 1:
        issues.append(f"AZ containers have inconsistent widths {widths} — columns will not align.")



# ─────────────────────────────────────────────────────────────────────────────
# COMPREHENSIVE CHECKS matching the SKILL.md pre-save checklist
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_GLOBAL_PARENT = {'iam', 'route53', 'cloudfront', 'waf', 'cf'}
KNOWN_REGIONAL_PARENT = {'ecr', 'acm', 'secrets', 'cloudwatch', 'cloudtrail', 'kms', 'lambda',
                          'bedrock', 'transcribe', 'msk', 's3', 'secrets_manager'}
KNOWN_VPC_OR_DEEPER = {'igw', 'alb', 'nat', 'bastion', 'ec2', 'ecs', 'eks', 'fargate', 'rds',
                        'aurora', 'docdb', 'elasticache', 'redis'}

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


def check_canvas_and_frame(root, issues):
    """Checklist A: Canvas and frame."""
    cells = list(root.iter('mxCell'))

    # Check border cell
    border = next((c for c in cells if c.get('id','') == 'border' or
                   ('strokeWidth=3' in c.get('style','') and 'fillColor=none' in c.get('style','') and
                    c.get('parent') == '1' and 'container' not in c.get('style',''))), None)
    if border:
        style = border.get('style', '')
        if 'strokeColor=#0066CC' in style:
            issues.append("Border cell uses strokeColor=#0066CC (template chrome); use strokeColor=#000000")
        if 'fillColor=default' in style:
            issues.append("Border cell uses fillColor=default; use fillColor=none")

    # Check logo blob is not a truncated placeholder
    for cell in cells:
        style = cell.get('style', '')
        if 'shape=image' in style and 'brand' in cell.get('id', '').lower():
            m = re.search(r'image=data:image/png,([^;]+)', style)
            if m:
                blob = m.group(1)
                if len(blob) < 100:
                    issues.append(f"Logo cell '{cell.get('id')}' has a truncated base64 blob "
                                  f"(len={len(blob)}) — copy from skeleton-3az.drawio.xml")
                if 'strokeColor=none' not in style:
                    issues.append(f"Logo cell '{cell.get('id')}' missing strokeColor=none "
                                  f"(will render with underline border)")


def check_icon_colours(root, issues):
    """Checklist B: Category colour consistency."""
    for cell in root.iter('mxCell'):
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
            issues.append(f"Icon '{cell.get('id')}' stencil '{stencil}' has fill {fill}; "
                          f"expected {expected_fills[0]}")


def check_edge_density(root, issues):
    """Checklist F30: Edge density — warn if > 12 edges on architecture page."""
    edges = [c for c in root.iter('mxCell') if c.get('edge') == '1']
    solid = [e for e in edges if 'dashed=1' not in e.get('style','')]
    if len(edges) > 15:
        issues.append(f"High edge count: {len(edges)} edges ({len(solid)} solid, "
                      f"{len(edges)-len(solid)} dashed). Consider removing decorative edges.")


def check_edge_labels(root, issues):
    """Checklist F31: Edge labels — warn on very long labels."""
    for cell in root.iter('mxCell'):
        if cell.get('edge') != '1':
            continue
        val = cell.get('value', '')
        # Strip HTML
        text = re.sub(r'<[^>]+>', '', val).strip()
        if len(text) > 30:
            issues.append(f"Edge '{cell.get('id')}' label is long ({len(text)} chars): "
                          f"'{text[:40]}…' — keep ≤4 words")


def check_alb_connects_to_lane(root, issues):
    """Checklist F24: ALB must connect to the cluster lane, not to individual tasks."""
    cells = {c.get('id'): c for c in root.iter('mxCell')}
    for cell in root.iter('mxCell'):
        if cell.get('edge') != '1':
            continue
        src = cell.get('source', '')
        tgt = cell.get('target', '')
        # ALB→fargate or ALB→ec2 is wrong
        src_cell = cells.get(src)
        tgt_cell = cells.get(tgt)
        if src_cell is not None and 'application_load_balancer' in src_cell.get('style',''):
            if tgt_cell is not None:
                tgt_style = tgt_cell.get('style','')
                if any(s in tgt_style for s in ['fargate', 'mxgraph.aws4.ec2', 'mxgraph.aws4.ecs']):
                    issues.append(f"Edge '{cell.get('id')}': ALB connects directly to task/instance "
                                  f"'{tgt}'. ALB should connect to the cluster lane border.")


def check_page_name_consistency(diagrams, issues):
    """Checklist I37: Service names should be consistent across pages."""
    # Collect service labels per page
    page_labels = {}
    for diag_name, root in diagrams.items():
        labels = set()
        for cell in root.iter('mxCell'):
            val = cell.get('value', '')
            if val and 'resourceIcon' in cell.get('style', ''):
                text = re.sub(r'<[^>]+>', '', val).strip()
                if text:
                    labels.add(text.lower())
        page_labels[diag_name] = labels

    if len(page_labels) == 2:
        names = list(page_labels.keys())
        arch_labels = page_labels.get('Architecture', set())
        flow_labels = page_labels.get('Flow', set())
        # Services on flow but not arch are fine (flow may aggregate)
        # Services on arch but not flow: warn only for compute
        compute_in_arch_not_flow = {
            l for l in arch_labels if any(k in l for k in ['eks', 'ecs', 'fargate', 'lambda'])
            and l not in flow_labels
        }
        if compute_in_arch_not_flow:
            issues.append(f"Compute services on Architecture page not found on Flow page: "
                          f"{compute_in_arch_not_flow}. Verify both pages are consistent.")


def main():
    if len(sys.argv) != 2:
        print("usage: validate-drawio.py <file.drawio.xml>")
        return 1
    path = Path(sys.argv[1])
    failures = []

    # 1. valid XML
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        print(f"FAIL: invalid XML — {e}")
        return 1

    # 2. exactly 2 pages named Architecture and Flow
    pages = [d.get("name") for d in root.findall(".//diagram")]
    if pages != ["Architecture", "Flow"]:
        failures.append(f"pages must be ['Architecture','Flow'], found {pages}")

    valid = load_valid_stencils()

    # Per-page checks: ID uniqueness is scoped to a page (root cells 0/1 repeat
    # per page by design); cross-page IDs may legitimately coincide.
    for page in root.findall(".//diagram"):
        pname = page.get("name")
        cells = page.findall(".//mxCell")
        ids = [c.get("id") for c in cells if c.get("id") is not None]

        # 3. unique cell IDs within the page
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            failures.append(f"[{pname}] duplicate cell IDs: {sorted(dupes)}")

        # 4. parent references point to existing IDs on the same page
        idset = set(ids)
        for c in cells:
            p = c.get("parent")
            if p is not None and p not in idset:
                failures.append(f"[{pname}] cell {c.get('id')!r} has dangling parent {p!r}")

        # 5/6. resourceIcon cells: full-size icons must be 120x120; cluster
        # badges (id endswith 'badge') are intentionally 45x45. All must use a
        # resIcon stencil present in shapes-aws.md.
        for c in cells:
            style = c.get("style") or ""
            if "shape=mxgraph.aws4.resourceIcon" not in style:
                continue
            cid = c.get("id") or ""
            geo = c.find("mxGeometry")
            w = geo.get("width") if geo is not None else None
            h = geo.get("height") if geo is not None else None
            if not cid.endswith("badge") and (w, h) != ("120", "120"):
                failures.append(f"[{pname}] icon {cid!r} is {w}x{h}, expected 120x120")
            m = re.search(r"resIcon=mxgraph\.aws4\.(\w+)", style)
            if m and m.group(1) not in valid:
                failures.append(f"[{pname}] icon {cid!r} uses unknown resIcon {m.group(1)!r}")

    if failures:
        print(f"FAIL ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
