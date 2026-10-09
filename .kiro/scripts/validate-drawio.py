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
