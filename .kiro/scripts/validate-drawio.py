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
    """Scenario B: Lambda+S3 diagrams must not invent a VPC.

    This is a heuristic: Lambda alone does not require a VPC. But a VPC IS
    legitimately in scope when the diagram contains VPC-bound resources
    (NAT Gateway, IGW, VPC endpoints) or a VPC-attached Lambda (a Lambda icon
    whose parent chain is an AZ/subnet). Those cases are NOT invented VPCs, so
    the check must not flag them — otherwise it produces a false positive for
    serverless-in-VPC architectures (e.g. a NAT Gateway + VPC-attached Lambda
    pipeline from a cost estimate).
    """
    if model is None:
        return
    cells = list(model.iter('mxCell'))
    has_lambda = any('mxgraph.aws4.lambda' in c.get('style', '') for c in cells)
    has_rds = any('mxgraph.aws4.rds' in c.get('style', '') or
                  'mxgraph.aws4.aurora' in c.get('style', '') for c in cells)
    has_vpc = any('group_vpc' in c.get('style', '') for c in cells)
    has_ecs = any('mxgraph.aws4.ecs' in c.get('style', '') or
                  'mxgraph.aws4.fargate' in c.get('style', '') for c in cells)

    # VPC-bound resources that PROVE the VPC is required (not invented).
    vpc_bound_stencils = (
        'mxgraph.aws4.nat_gateway',
        'mxgraph.aws4.internet_gateway',
        'mxgraph.aws4.endpoints',
        'mxgraph.aws4.vpc_privatelink',
        'mxgraph.aws4.application_load_balancer',
        'mxgraph.aws4.network_load_balancer',
    )
    has_vpc_bound = any(
        any(s in c.get('style', '') for s in vpc_bound_stencils) for c in cells
    )

    # VPC-attached Lambda: a Lambda icon parented into an AZ/subnet container.
    subnet_ids = {
        c.get('id') for c in cells
        if 'group_security_group' in c.get('style', '')
        or 'group_availability_zone' in c.get('style', '')
    }
    lambda_in_subnet = any(
        'mxgraph.aws4.lambda' in c.get('style', '') and c.get('parent') in subnet_ids
        for c in cells
    )

    # Only flag if ONLY Lambda (no ECS/RDS which require VPC) AND there is no
    # evidence the VPC is genuinely in scope.
    if (has_lambda and not has_rds and not has_ecs and has_vpc
            and not has_vpc_bound and not lambda_in_subnet):
        issues.append(
            f"[{page_name}] Scenario B (scenario-b): diagram has Lambda+S3 but also contains a VPC container "
            "with no VPC-bound resources (no NAT/IGW/endpoints, Lambda not in a subnet). "
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

    # Title block must carry the metadata fields (same as the Architecture page)
    title_cells = [c for c in cells
                   if c.get('id', '').endswith('title') or c.get('id', '') == 'f-title']
    for tc in title_cells:
        val = tc.get('value', '')
        for field in ['Version', 'Date', 'Creator', 'Reviewer']:
            if field not in val:
                issues.append(f"[{page_name}] title block '{tc.get('id')}' missing '{field}' metadata")

    # Check brand/logo cell has strokeColor=none
    brand_cells = [c for c in cells if 'brand' in c.get('id', '')]
    for bc in brand_cells:
        style = bc.get('style', '')
        if 'shape=image' in style and 'strokeColor=none' not in style:
            issues.append(f"[{page_name}] Logo cell '{bc.get('id')}' missing strokeColor=none (will show underline)")

    # FLAT layout: f-cloud / f-region / f-vpc are REQUIRED decorative scope boxes (container=0), absolute
    # coordinates, parent '1'; every node is parent '1' too. Nodes are checked against the boxes by position
    # (see check_scope_boxes), so editing in draw.io can never re-parent or drift them.
    by_id = {c.get('id'): c for c in cells}

    def _g(c):
        g = c.find('mxGeometry')
        return None if g is None else {k: float(g.get(k) or 0) for k in ('x', 'y', 'width', 'height')}

    boxes = {}
    for cid in ('f-cloud', 'f-region', 'f-vpc'):
        c = by_id.get(cid)
        if c is None:
            issues.append(f"[{page_name}] missing scope box '{cid}'")
            continue
        if 'container=1' in (c.get('style') or ''):
            issues.append(f"[{page_name}] scope box '{cid}' must be decorative (container=0), not a parent")
        if c.get('parent') != '1':
            issues.append(f"[{page_name}] scope box '{cid}' must have parent '1' (flat layout)")
        boxes[cid] = _g(c)

    def _inside(i, o):
        return i and o and i['x'] >= o['x'] and i['y'] >= o['y'] \
            and i['x'] + i['width'] <= o['x'] + o['width'] and i['y'] + i['height'] <= o['y'] + o['height']
    if all(boxes.get(k) for k in boxes) and len(boxes) == 3:
        if not _inside(boxes['f-region'], boxes['f-cloud']):
            issues.append(f"[{page_name}] 'f-region' is not inside 'f-cloud'")
        if not _inside(boxes['f-vpc'], boxes['f-region']):
            issues.append(f"[{page_name}] 'f-vpc' is not inside 'f-region'")
    t = _g(by_id['f-title']) if 'f-title' in by_id else None
    if t and boxes.get('f-cloud') and t['y'] + t['height'] > boxes['f-cloud']['y']:
        issues.append(f"[{page_name}] title block overlaps 'f-cloud'")
    for c in cells:
        if c.get('vertex') == '1' and c.get('parent') not in ('1', None) and c.get('id') != 'f-border':
            issues.append(f"[{page_name}] '{c.get('id')}' has parent '{c.get('parent')}': the Flow page is flat, "
                          f"every node must be parent '1' with absolute coordinates")


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

    # NOTE: Consistency check disabled for now.
    # Rule #15 says task icons should be "Fargate Task"/"EC2 Node" (task type).
    # Rule #37 says service labels should be identical on both pages.
    # These rules conflict: Architecture has task icons inside lanes with task-type labels,
    # but Flow page has the cluster as a single icon (e.g., "EKS" or "ECS Fargate").
    # Until this is clarified, we skip the consistency check to avoid false positives.
    #
    # if len(page_labels) == 2 and 'Architecture' in page_labels and 'Flow' in page_labels:
    #     arch_labels = page_labels.get('Architecture', set())
    #     flow_labels = page_labels.get('Flow', set())
    #     compute_in_arch_not_flow = {
    #         l for l in arch_labels if any(k in l for k in ['eks', 'ecs', 'fargate', 'lambda'])
    #         and l not in flow_labels
    #     }
    #     if compute_in_arch_not_flow:
    #         issues.append(f"[Consistency] Compute services on Architecture page not found on Flow page: "
    #                       f"{compute_in_arch_not_flow}. Verify both pages are consistent.")


def check_icon_overlaps(model, issues, page_name="Architecture"):
    """Check for overlapping icons based on absolute coordinates."""
    if model is None:
        return

    # Build parent hierarchy to compute absolute coords
    cells = {c.get('id'): c for c in model.iter('mxCell')}

    def get_abs_coords(cell_id, visited=None):
        """Recursively compute absolute x,y from parent chain."""
        if visited is None:
            visited = set()
        if cell_id in visited:
            return (0, 0)
        visited.add(cell_id)

        cell = cells.get(cell_id)
        if cell is None:
            return (0, 0)

        geo = cell.find('mxGeometry')
        x = float(geo.get('x', 0)) if geo is not None else 0
        y = float(geo.get('y', 0)) if geo is not None else 0

        parent_id = cell.get('parent')
        if parent_id and parent_id != '1' and parent_id != '0':
            px, py = get_abs_coords(parent_id, visited)
            x += px
            y += py

        return (x, y)

    # Collect icons with their absolute bounding boxes
    # EXCLUDE badges (45x45) — they intentionally overlap lane borders
    icons = []
    for cell in model.iter('mxCell'):
        style = cell.get('style', '')
        if 'resourceIcon' not in style:
            continue

        cell_id = cell.get('id', '')
        geo = cell.find('mxGeometry')
        if geo is None:
            continue

        w = float(geo.get('width', 120))
        h = float(geo.get('height', 120))

        # Skip badges (45x45 icons that sit on lane borders)
        is_badge = (w <= 50 and h <= 50) or 'badge' in cell_id.lower()
        if is_badge:
            continue

        abs_x, abs_y = get_abs_coords(cell_id)

        icons.append({
            'id': cell_id,
            'x': abs_x,
            'y': abs_y,
            'w': w,
            'h': h,
            'right': abs_x + w,
            'bottom': abs_y + h
        })

    # Check for overlaps (any two icons)
    min_gap = 20  # Minimum gap between icons
    for i, icon1 in enumerate(icons):
        for icon2 in icons[i+1:]:
            # Check if bounding boxes overlap (with minimum gap)
            x_overlap = not (icon1['right'] + min_gap <= icon2['x'] or
                            icon2['right'] + min_gap <= icon1['x'])
            y_overlap = not (icon1['bottom'] + min_gap <= icon2['y'] or
                            icon2['bottom'] + min_gap <= icon1['y'])

            if x_overlap and y_overlap:
                issues.append(
                    f"[{page_name}] Icon overlap: '{icon1['id']}' (x={icon1['x']:.0f}) and "
                    f"'{icon2['id']}' (x={icon2['x']:.0f}) are too close or overlapping"
                )


def check_multiaz_db_placement(model, issues, page_name="Architecture"):
    """Check that Multi-AZ databases are placed across different AZs."""
    if model is None:
        return

    cells = {c.get('id'): c for c in model.iter('mxCell')}

    # Find all RDS/Aurora icons
    db_icons = []
    for cell in model.iter('mxCell'):
        style = cell.get('style', '')
        cell_id = cell.get('id', '')
        value = cell.get('value', '').lower()

        if any(s in style for s in ['mxgraph.aws4.rds', 'mxgraph.aws4.aurora']):
            parent = cell.get('parent', '')
            db_icons.append({
                'id': cell_id,
                'parent': parent,
                'value': value,
                'is_multiaz': 'multi-az' in value or 'multiaz' in value,
                'is_writer': 'writer' in value or 'primary' in value,
                'is_standby': 'standby' in value,
                'is_replica': 'replica' in value or 'reader' in value
            })

    if len(db_icons) < 2:
        return  # Single DB or no DBs, skip check

    # Check if any are marked as Multi-AZ
    has_multiaz = any(db['is_multiaz'] or db['is_standby'] for db in db_icons)
    if not has_multiaz:
        return  # Not a Multi-AZ setup, skip

    # Get parents of all DB icons
    parents = set(db['parent'] for db in db_icons)

    # For Multi-AZ, we expect DBs in different parent containers (different AZs)
    if len(parents) == 1:
        parent_id = list(parents)[0]
        parent_cell = cells.get(parent_id)
        parent_value = parent_cell.get('value', '') if parent_cell is not None else ''

        # Check if parent is an AZ-specific container (db1, db2, db3, etc.)
        if 'db' in parent_id.lower() or 'subnet' in parent_id.lower():
            issues.append(
                f"[{page_name}] Multi-AZ database placement issue: all DB icons ({[d['id'] for d in db_icons]}) "
                f"are in the same container '{parent_id}'. For Multi-AZ, Writer and Standby should be in "
                f"different AZ db-subnets (e.g., db1 and db2)."
            )


def check_waf_placement(model, issues, page_name="Architecture"):
    """WAF follows what it protects: CloudFront web ACL -> global band (parent cloud); ALB web ACL ->
    regional row (parent region). Never root / inside the VPC. No WAF edges on the Architecture page."""
    if model is None:
        return
    cells = {c.get('id'): c for c in model.iter('mxCell')}
    for w in [c for c in cells.values() if 'mxgraph.aws4.waf' in (c.get('style') or '').lower()]:
        if w.get('parent') not in ('cloud', 'region'):
            issues.append(f"[{page_name}] WAF '{w.get('id')}' has parent '{w.get('parent')}'. Use parent='cloud' "
                          f"(global band, fronting CloudFront) or parent='region' (regional row, fronting an ALB); "
                          f"never root or inside the VPC.")
        for e in cells.values():
            if e.get('edge') == '1' and w.get('id') in (e.get('source'), e.get('target')):
                issues.append(f"[{page_name}] edge '{e.get('id')}' touches WAF '{w.get('id')}': WAF associations "
                              f"are drawn on the Flow page only")


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


def _abs_xy(cells, c):
    x = y = 0.0
    while c is not None and c.get("id") not in ("0", "1"):
        g = c.find("mxGeometry")
        if g is not None:
            x += float(g.get("x") or 0); y += float(g.get("y") or 0)
        c = cells.get(c.get("parent"))
    return x, y


def _geo(c):
    g = c.find("mxGeometry")
    return None if g is None else {k: float(g.get(k) or 0) for k in ("x", "y", "width", "height")}


def check_container_wrap(model, issues, page_name="Architecture"):
    """WRAP RULE: containers always wrap their content with fixed insets, and rows stay centred.
    az_w = content_right + 40; vpc_w = az_x + az_w + 65; region_w = vpc_x + vpc_w + 85;
    cloud_w = region_x + region_w + 85; border_w = cloud_x + cloud_w + 113 (insets 520/85/247 fixed)."""
    cells = {c.get("id"): c for c in model.iter("mxCell")}
    need = ("cloud", "region", "vpc", "az1")
    if any(n not in cells for n in need):
        return
    g = {n: _geo(cells[n]) for n in need}
    azs = [c for c in cells.values() if (c.get("id") or "").startswith("az") and _geo(c)
           and "group_availability_zone" in (c.get("style") or "")]
    right = 0.0
    for c in cells.values():
        par = cells.get(c.get("parent"))
        if par is not None and par in azs and _geo(c) and (c.get("id") or "").startswith(("pub", "app", "db")):
            right = max(right, _geo(c)["x"] + _geo(c)["width"])
    if right == 0:
        return

    def expect(label, got, want):
        if abs(got - want) > 1:
            issues.append(f"[{page_name}] {label} is {got:.0f}, wrap rule says {want:.0f}")
    for fixed, cid, val in (("AZ x-inset", "az1", 520), ("VPC x-inset", "vpc", 85), ("Region x-inset", "region", 247)):
        expect(fixed, g[cid]["x"], val)
    for az in azs:
        expect(f"{az.get('id')} width (content_right {right:.0f} + 40)", _geo(az)["width"], right + 40)
    expect("vpc width (az_x + az_w + 65)", g["vpc"]["width"], g["az1"]["x"] + g["az1"]["width"] + 65)
    expect("region width (vpc_x + vpc_w + 85)", g["region"]["width"], g["vpc"]["x"] + g["vpc"]["width"] + 85)
    expect("cloud width (region_x + region_w + 85)", g["cloud"]["width"], g["region"]["x"] + g["region"]["width"] + 85)
    if "border" in cells and _geo(cells["border"]):
        b = _geo(cells["border"])
        expect("border width (cloud_x + cloud_w + 113)", b["width"], g["cloud"]["x"] + g["cloud"]["width"] + 113)

    def row(parent, y):
        return [_geo(c) for c in cells.values() if c.get("parent") == parent and _geo(c)
                and abs(_geo(c)["y"] - y) < 0.5 and _geo(c)["width"] == 120 and c.get("vertex") == "1"]
    for parent, y, cw, label in (("region", 65, g["region"]["width"], "regional services row"),
                                 ("cloud", 70, g["cloud"]["width"], "global band")):
        icons = row(parent, y)
        if icons:
            mid = (min(i["x"] for i in icons) + max(i["x"] + 120 for i in icons)) / 2
            if abs(mid - cw / 2) > 1.5:
                issues.append(f"[{page_name}] {label} is not centred: group centre {mid:.1f} vs container centre "
                              f"{cw / 2:.1f}; start_x must be round_half_up((width - (n*120 + (n-1)*60))/2)")


def check_lane_geometry(model, issues, page_name="Architecture"):
    """Cluster lanes sit INSIDE the app-subnet column with a 35px left / 20px right gap
    (app_w = lane_w + 55; dual lanes: 2*240 + 20 + 55) and own their Fargate/EKS task icons."""
    cells = {c.get("id"): c for c in model.iter("mxCell")}
    lanes = [c for c in cells.values()
             if (c.get("id") or "").endswith("lane") and "ED7100" in (c.get("style") or "")]
    if not lanes:
        return
    apps = []
    for c in cells.values():
        par = cells.get(c.get("parent"))
        if (c.get("id") or "").startswith("app") and par is not None and "group_availability_zone" in (par.get("style") or ""):
            x, y = _abs_xy(cells, c); g = _geo(c)
            apps.append((x, x + g["width"], y, y + g["height"]))
    if apps:
        left, right = min(a[0] for a in apps), max(a[1] for a in apps)
        top, bottom = min(a[2] for a in apps), max(a[3] for a in apps)
        lx = [(_abs_xy(cells, l)[0], _geo(l)["width"]) for l in lanes]
        ly = [(_abs_xy(cells, l)[1], _geo(l)["height"]) for l in lanes]
        if min(x for x, _ in lx) < left or max(x + w for x, w in lx) > right \
                or min(y for y, _ in ly) < top or max(y + h for y, h in ly) > bottom:
            issues.append(f"[{page_name}] lane is not inside the app-subnet column "
                          f"(x {left:.0f}-{right:.0f}, y {top:.0f}-{bottom:.0f})")
        else:
            gl = min(x for x, _ in lx) - left
            gr = right - max(x + w for x, w in lx)
            if abs(gl - 35) > 1 or abs(gr - 20) > 1:
                issues.append(f"[{page_name}] lane gaps inside the app subnet are {gl:.0f}px left / {gr:.0f}px right; "
                              f"rule is 35 / 20 (app_w = lane_w + 55; dual lanes: 2*240 + 20 + 55)")
    lane_ids = {l.get("id") for l in lanes}
    for c in cells.values():
        if "mxgraph.aws4.fargate" in (c.get("style") or "") and c.get("parent") not in lane_ids:
            issues.append(f"[{page_name}] task icon '{c.get('id')}' has parent '{c.get('parent')}'; "
                          f"tasks must be children of the lane ({sorted(lane_ids)})")


def check_subnet_columns(model, issues, page_name="Architecture"):
    """pub | 40 | app | 40 | db columns, identical in every AZ row."""
    cells = {c.get("id"): c for c in model.iter("mxCell")}
    rows = {}
    for c in cells.values():
        par = cells.get(c.get("parent"))
        if par is None or "group_availability_zone" not in (par.get("style") or ""):
            continue
        kind = next((k for k in ("pub", "app", "db") if (c.get("id") or "").startswith(k)), None)
        if kind and _geo(c):
            rows.setdefault(par.get("id"), {})[kind] = (_geo(c)["x"], _geo(c)["width"])
    first = None
    for az, r in sorted(rows.items()):
        if {"pub", "app", "db"} <= set(r):
            if abs(r["app"][0] - (r["pub"][0] + r["pub"][1] + 40)) > 1:
                issues.append(f"[{page_name}] {az}: app subnet x must be pub_right+40")
            if abs(r["db"][0] - (r["app"][0] + r["app"][1] + 40)) > 1:
                issues.append(f"[{page_name}] {az}: db subnet x must be app_right+40 "
                              f"(found {r['db'][0]:.0f}, expected {r['app'][0] + r['app'][1] + 40:.0f})")
            if first is None:
                first = r
            elif r != first:
                issues.append(f"[{page_name}] {az}: subnet columns differ from the first AZ row")


def check_straight_edges(model, issues, page_name="Architecture"):
    """A right->left edge without waypoints must be horizontal (|dy| <= 2px): exitY/entryY need 3 decimals."""
    cells = {c.get("id"): c for c in model.iter("mxCell")}
    for e in cells.values():
        if e.get("edge") != "1" or e.find(".//Array") is not None:
            continue
        st = e.get("style") or ""

        def v(name):
            m = re.search(name + r"=([0-9.]+)", st)
            return float(m.group(1)) if m else None
        src, tgt = cells.get(e.get("source")), cells.get(e.get("target"))
        ex, ey, nx, ny = v("exitX"), v("exitY"), v("entryX"), v("entryY")
        if src is None or tgt is None or ex != 1 or nx != 0 or not _geo(src) or not _geo(tgt):
            continue
        sx, sy = _abs_xy(cells, src); tx, ty = _abs_xy(cells, tgt)
        sh, th = _geo(src)["height"], _geo(tgt)["height"]
        y1 = sy + (0.5 if ey is None else ey) * sh
        y2 = ty + (0.5 if ny is None else ny) * th
        if abs(y1 - y2) > 2:
            issues.append(f"[{page_name}] edge '{e.get('id')}' is not straight: exit y {y1:.1f} vs entry y {y2:.1f} "
                          f"(dy {y1 - y2:+.1f}px). Use exitY={(y2 - sy) / sh:.3f} (3 decimals).")


VPC_BOUND_SCOPE = ("nat_gateway", "application_load_balancer", "network_load_balancer", "ecs", "fargate", "eks",
                   "rds", "aurora", "documentdb", "elasticache", "msk", "endpoints")   # IGW straddles the border: exempt
REGION_ONLY_SCOPE = ("cloudwatch_2", "cloudtrail", "key_management_service", "secrets_manager",
                     "elastic_container_registry", "certificate_manager_3")
FLOW_REGION_EXTRA = ("s3", "bedrock", "transcribe", "sqs", "sns", "dynamodb")
GLOBAL_SCOPE = ("identity_and_access_management", "route_53", "cloudfront")


def check_scope_boxes(model, issues, page_name="Architecture", ids=("region", "vpc"), cloud_id=None, flow=False):
    """Hierarchy-agnostic scope check on ABSOLUTE positions: VPC box inside Region box; VPC-bound icons inside
    the VPC; Region-only services inside the Region but outside the VPC; global services outside the Region
    (and, when a cloud box is given, inside it)."""
    cells = {c.get("id"): c for c in model.iter("mxCell")}
    rid, vid = ids
    if rid not in cells or vid not in cells:
        return

    def box(c):
        x, y = _abs_xy(cells, c); g = _geo(c)
        return x, y, x + g["width"], y + g["height"]

    def inside(b, o, tol=1):
        return b[0] >= o[0] - tol and b[1] >= o[1] - tol and b[2] <= o[2] + tol and b[3] <= o[3] + tol

    def centre_in(b, o):
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return o[0] <= cx <= o[2] and o[1] <= cy <= o[3]
    R, V = box(cells[rid]), box(cells[vid])
    C = box(cells[cloud_id]) if cloud_id in cells else None
    if not inside(V, R):
        issues.append(f"[{page_name}] '{vid}' is not visually inside '{rid}' (vpc x {V[0]:.0f}-{V[2]:.0f}, "
                      f"y {V[1]:.0f}-{V[3]:.0f} vs region x {R[0]:.0f}-{R[2]:.0f}, y {R[1]:.0f}-{R[3]:.0f}) "
                      f"- check parent and coordinate frame")
    region_only = REGION_ONLY_SCOPE + (FLOW_REGION_EXTRA if flow else ())
    for c in cells.values():
        m = re.search(r"resIcon=mxgraph\.aws4\.(\w+)", c.get("style") or "")
        if not m or _geo(c) is None:
            continue
        res, b = m.group(1), box(c)
        if res in VPC_BOUND_SCOPE and not centre_in(b, V):
            issues.append(f"[{page_name}] '{c.get('id')}' ({res}) is VPC-bound but sits outside the VPC box")
        if res in region_only and (not centre_in(b, R) or centre_in(b, V)):
            issues.append(f"[{page_name}] '{c.get('id')}' ({res}) is a regional service: it must be inside the "
                          f"Region box and outside the VPC box")
        if res in GLOBAL_SCOPE and (centre_in(b, R) or (C is not None and not centre_in(b, C))):
            issues.append(f"[{page_name}] '{c.get('id')}' ({res}) is a global service: it must sit inside the "
                          f"cloud and outside the Region box")


def main():
    args = sys.argv[1:]
    allow = []
    while "--allow" in args:                      # --allow <substring>: report matching issues as WARN, do not fail
        i = args.index("--allow")
        if i + 1 >= len(args):
            print("usage: validate-drawio.py <file.drawio.xml> [--allow <issue-substring> ...]")
            return 1
        allow.append(args[i + 1].lower()); del args[i:i + 2]
    if len(args) != 1:
        print("usage: validate-drawio.py <file.drawio.xml> [--allow <issue-substring> ...]")
        return 1
    path = Path(args[0])
    issues = []

    # Detect if this is a reference/template file (not a final output)
    is_reference = any(x in str(path).lower() for x in [
        'template', 'skeleton', 'diagram examples', 'flow diagram examples'
    ])

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

    # Check for required pages (skip for reference/template files)
    if not is_reference:
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
        check_icon_overlaps(arch_model, issues, "Architecture")
        check_multiaz_db_placement(arch_model, issues, "Architecture")
        check_waf_placement(arch_model, issues, "Architecture")
        check_container_wrap(arch_model, issues, "Architecture")
        check_lane_geometry(arch_model, issues, "Architecture")
        check_subnet_columns(arch_model, issues, "Architecture")
        check_straight_edges(arch_model, issues, "Architecture")
        check_scope_boxes(arch_model, issues, "Architecture")
    elif "Architecture" in page_names:
        issues.append("[Architecture] Could not parse mxGraphModel from Architecture page")

    # 4. Run Flow-specific checks
    flow_model = page_models.get("Flow")
    if flow_model is not None:
        check_flow_page(flow_model, issues, "Flow")
        check_canvas_and_frame(flow_model, issues, "Flow")
        check_icon_dimensions_and_stencils(flow_model, valid, issues, "Flow")
        check_unique_ids_and_parents(flow_model, issues, "Flow")
        check_scope_boxes(flow_model, issues, "Flow", ids=("f-region", "f-vpc"), cloud_id="f-cloud", flow=True)
    elif "Flow" in page_names:
        issues.append("[Flow] Could not parse mxGraphModel from Flow page")

    # 5. Cross-page consistency checks
    check_page_name_consistency(page_models, issues)

    # 6. Report results
    warned = [f for f in issues if any(a in f.lower() for a in allow)]
    issues = [f for f in issues if f not in warned]
    if issues:
        print(f"FAIL ({len(issues)} issue(s)):")
        for f in issues:
            print(f"  - {f}")
        for f in warned:
            print(f"  ~ WARN (allowed): {f}")
        return 1

    print("PASS" if not warned else f"PASS ({len(warned)} allowed warning(s))")
    for f in warned:
        print(f"  ~ WARN (allowed): {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
