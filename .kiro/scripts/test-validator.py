#!/usr/bin/env python3
"""Regression tests for validate-drawio.py and the skeleton (exit 0 = every case behaves).

Fixtures are built from the skeleton (lane block uncommented, an Aurora icon in a DB subnet, a lane->DB edge,
optional WAF / Lambda / NAT). Expected numbers come from the skeleton's own geometry or from the wrap rule
re-implemented here, so the tests stay valid if constants change.
Usage: python3 .kiro/scripts/test-validator.py
"""
import re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / ".kiro/scripts/validate-drawio.py"
SKEL = (ROOT / ".kiro/skills/arch-diagram/references/skeleton-3az.drawio.xml").read_text(encoding="utf-8")

ICON = ('        <mxCell id="{i}" parent="{p}" value="&lt;b&gt;{l}&lt;/b&gt;" style="sketch=0;outlineConnect=0;'
        'fillColor={f};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;'
        'html=1;whiteSpace=wrap;fontSize=18;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{r};" '
        'vertex="1"><mxGeometry x="{x}" y="{y}" width="120" height="120" as="geometry" /></mxCell>\n')
EDGE = ('        <mxCell id="{i}" edge="1" parent="1" source="{s}" target="{t}" '
        'style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeWidth=4;{extra}">'
        '<mxGeometry relative="1" as="geometry" /></mxCell>\n')
FLOW_MARK = "        <!-- ── FLOW EDGES"


def rhu(x):
    return int(x + 0.5)


def geom(cid, xml=SKEL):
    m = re.search(r'<mxCell id="%s".*?<mxGeometry x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)"' % cid, xml, re.S)
    return tuple(float(v) for v in m.groups())


def set_geom(xml, cid, **kw):
    def fix(m):
        blk = m.group(0)
        for k, v in kw.items():
            blk = re.sub(r'(<mxGeometry[^>]*?\b%s=")[-\d.]+(")' % k, r'\g<1>%s\2' % v, blk, 1)
        return blk
    return re.sub(r'<mxCell id="%s".*?</mxCell>' % cid, fix, xml, 1, flags=re.S)


def uncomment_lane(xml):
    lines = xml.split("\n")
    i = next(n for n, l in enumerate(lines) if 'id="ecslane"' in l)
    a = i - 1
    assert lines[a].strip() == "<!--", "lane block comment start not found"
    b = next(n for n in range(i, len(lines)) if lines[n].strip() == "-->")
    return "\n".join(lines[:a] + lines[a + 1:b] + lines[b + 1:])


LANE = uncomment_lane(SKEL)


def exit_y(az_n):
    _, lane_y, _, lane_h = geom("ecslane", LANE)
    return (geom(f"az{az_n}")[1] + geom(f"db{az_n}")[1] + 65 + 60 - lane_y) / lane_h


def fixture(db_n=1, y=None, extra=""):
    xml = LANE
    y = f"{exit_y(db_n):.3f}" if y is None else y
    add = ICON.format(i="aurora1", p=f"db{db_n}", l="Aurora Writer", f="#C925D1", r="aurora", x=90, y=65)
    add += EDGE.format(i="e-db", s="ecslane", t="aurora1", extra=f"exitX=1;exitY={y};entryX=0;entryY=0.5;")
    xml = xml.replace("</root>", add + extra + "    </root>", 1)
    return xml.replace(FLOW_MARK, ICON.format(i="f-task", p="1", l="Fargate Task", f="#ED7100", r="fargate", x=860, y=670) + FLOW_MARK, 1)


def add_icon(xml, **kw):
    return xml.replace("</root>", ICON.format(**kw) + "    </root>", 1)


def relayout(xml, pub_w=300, app_w=355, db_w=300):
    """Re-lay the skeleton for other subnet widths using the wrap rule (independent re-implementation)."""
    app_x = 35 + pub_w + 40
    db_x = app_x + app_w + 40
    az_w = db_x + db_w + 40
    vpc_w = 520 + az_w + 65
    reg_w = 85 + vpc_w + 85
    cld_w = 247 + reg_w + 85
    for n in (1, 2, 3):
        xml = set_geom(xml, f"pub{n}", width=pub_w)
        xml = set_geom(xml, f"app{n}", x=app_x, width=app_w)
        xml = set_geom(xml, f"db{n}", x=db_x, width=db_w)
        xml = set_geom(xml, f"az{n}", width=az_w)
    xml = set_geom(xml, "vpc", width=vpc_w)
    xml = set_geom(xml, "region", width=reg_w)
    xml = set_geom(xml, "cloud", width=cld_w)
    xml = set_geom(xml, "border", width=260 + cld_w + 113)
    start = rhu((reg_w - 480) / 2)
    for k, cid in enumerate(("cloudwatch", "cloudtrail", "kms")):
        xml = set_geom(xml, cid, x=start + 180 * k)
    return set_geom(xml, "iam", x=rhu((cld_w - 120) / 2))


def with_regional_waf(xml, edge=False):
    """Add a regional WAF as the 4th regional-row icon and re-centre the row (start_x from the wrap rule)."""
    reg_w = geom("region", xml)[2]
    start = rhu((reg_w - (4 * 120 + 3 * 60)) / 2)
    for k, cid in enumerate(("cloudwatch", "cloudtrail", "kms")):
        xml = set_geom(xml, cid, x=start + 180 * k)
    xml = add_icon(xml, i="waf", p="region", l="AWS WAF", f="#DD344C", r="waf", x=start + 540, y=65)
    if edge:
        xml = xml.replace("</root>", EDGE.format(i="e-waf", s="waf", t="alb", extra="") + "    </root>", 1)
    return xml


def no_entry(xml):
    return re.sub(r'<mxCell id="(igw|alb)".*?</mxCell>\n', "", xml, flags=re.S)


FLOW_SLOTS = [  # (id, label, stencil, fill, x, y) — the positions documented in the cheatsheet "Flow page" table
    ("fn-users", "Users", "users", "#232F3E", 220, 670),
    ("fn-cf", "CloudFront", "cloudfront", "#8C4FFF", 540, 670),
    ("fn-alb", "ALB", "application_load_balancer", "#8C4FFF", 860, 670),
    ("fn-ecs", "ECS Fargate", "ecs", "#ED7100", 1180, 670),
    ("fn-rds", "Aurora", "aurora", "#C925D1", 1500, 670),
    ("fn-s3", "S3", "s3", "#7AA116", 1820, 670),
    ("fn-r53", "Route 53", "route_53", "#8C4FFF", 470, 910),
    ("fn-waf", "AWS WAF", "waf", "#DD344C", 540, 250),
]


def with_flow_slots(xml, move=None):
    nodes = "".join(ICON.format(i=i, p="1", l=l, f=f, r=r, x=(move or {}).get(i, (x, y))[0], y=(move or {}).get(i, (x, y))[1])
                    for i, l, r, f, x, y in FLOW_SLOTS)
    return xml.replace(FLOW_MARK, nodes + FLOW_MARK, 1)


def run(xml, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".drawio.xml", delete=False, encoding="utf-8") as f:
        f.write(xml)
    r = subprocess.run([sys.executable, str(VALIDATOR), f.name, *args], capture_output=True, text=True)
    return r.returncode, r.stdout


def main():
    ok = fixture()
    cases = [  # (name, xml, expected substring | None for PASS, extra args)
        ("skeleton passes", SKEL, None, ()),
        ("lane + AZ1/AZ2/AZ3 db edges pass", fixture(2), None, ()),
        ("AZ3 edge passes", fixture(3), None, ()),
        ("D2 dual-lane columns via the wrap rule pass (no lane)", relayout(SKEL, app_w=555), None, ()),
        ("D3 2-icon public subnet via the wrap rule passes", relayout(SKEL, pub_w=380), None, ()),
        ("D3 with the lane block re-based to app_x=455 passes", set_geom(relayout(LANE, pub_w=380), "ecslane", x=1010), None, ()),
        ("2-icon public subnet but containers not re-wrapped", set_geom(SKEL, "pub1", width=380), "app subnet x must be pub_right+40", ()),
        ("exitY off by 0.005 (>2px jog)", fixture(3, y=f"{exit_y(3) + 0.005:.3f}"), "not straight", ()),
        ("exitY rounded to 2 decimals jogs", fixture(3, y=f"{exit_y(3) + 0.01:.3f}"), "not straight", ()),
        ("lane gaps 27/27 instead of 35/20", set_geom(ok, "ecslane", x=geom("ecslane", ok)[0] - 8, width=geom("ecslane", ok)[2] + 1), "lane gaps", ()),
        ("lane outside app column", set_geom(ok, "ecslane", x=500), "not inside the app-subnet column", ()),
        ("tasks parented to subnet", re.sub(r'(id="ecs[123]" parent=")ecslane"', r'\1app1"', ok), "must be children of the lane", ()),
        ("db subnet not app_right+40", set_geom(ok, "db1", x=geom("db1", ok)[0] + 100), "db subnet x must be app_right+40", ()),
        ("AZ wider than content (old 1640 default)", set_geom(set_geom(set_geom(ok, "az1", width=1640), "az2", width=1640), "az3", width=1640), "wrap rule", ()),
        ("VPC width off", set_geom(ok, "vpc", width=geom("vpc", ok)[2] + 30), "vpc width", ()),
        ("border still 3100", set_geom(ok, "border", width=3100), "border width", ()),
        ("regional row not re-centred", set_geom(ok, "kms", x=geom("kms", ok)[0] + 120), "regional services row is not centred", ()),
        ("global band not re-centred", set_geom(ok, "iam", x=geom("iam", ok)[0] + 200), "global band is not centred", ()),
        ("flow VPC box missing", re.sub(r'<mxCell id="f-vpc".*?</mxCell>\n', "", ok, flags=re.S), "missing scope box 'f-vpc'", ()),
        ("flow scope box is a container", re.sub(r'(<mxCell id="f-region".*?style="[^"]*)container=0', r'\1container=1', ok, 1, flags=re.S), "must be decorative", ()),
        ("flow node parented to a box", ok.replace('id="f-task" parent="1"', 'id="f-task" parent="f-vpc"'), "Flow page is flat", ()),
        ("flow title metadata missing", ok.replace("Creator: To be filled", ""), "missing 'Creator'", ()),
        ("flow VPC node outside the VPC box", set_geom(ok, "f-task", x=1900), "VPC-bound but sits outside", ()),
        ("Flow nodes at the documented slots pass", with_flow_slots(ok), None, ()),
        ("Flow: S3 dropped inside the VPC box", with_flow_slots(ok, {"fn-s3": (1180, 500)}), "regional service", ()),
        ("Flow: Route 53 inside the Region box", with_flow_slots(ok, {"fn-r53": (900, 910)}), "global service", ()),
        ("Flow: ALB outside the VPC box", with_flow_slots(ok, {"fn-alb": (1820, 430)}), "VPC-bound but sits outside", ()),
        ("blank-box ACM stencil", add_icon(ok, i="acm", p="region", l="ACM", f="#DD344C", r="certificate_manager", x=1500, y=65), "unknown resIcon", ()),
        ("WAF fronting an ALB, regional row, passes", with_regional_waf(ok), None, ()),
        ("WAF with parent=1 fails", add_icon(ok, i="waf", p="1", l="AWS WAF", f="#DD344C", r="waf", x=1300, y=65), "WAF 'waf' has parent '1'", ()),
        ("WAF edge on the Architecture page", with_regional_waf(ok, edge=True), "Flow page only", ()),
        ("VPC re-parented without shifting (drift)", re.sub(r'(<mxCell id="vpc" parent=")region"', r'\1cloud"', ok, 1), "not visually inside", ()),
        ("KMS in the global band", re.sub(r'(<mxCell id="kms" parent=")region"', r'\1cloud"', ok, 1), "regional service", ()),
        ("ALB outside the VPC", re.sub(r'(<mxCell id="alb" parent=")vpc"', r'\1cloud"', ok, 1), "VPC-bound but sits outside", ()),
        ("IAM inside the Region box", re.sub(r'(<mxCell id="iam" parent=")cloud"', r'\1region"', ok, 1), "global service", ()),
    ]
    nv = no_entry(SKEL)          # VPC container kept, no IGW/ALB, no ECS tasks
    cases += [
        ("Lambda in region + VPC, nothing VPC-bound (Scenario B)", add_icon(nv, i="fn", p="region", l="Lambda", f="#ED7100", r="lambda", x=100, y=400), "Scenario B", ()),
        ("Scenario B acknowledged with --allow", add_icon(nv, i="fn", p="region", l="Lambda", f="#ED7100", r="lambda", x=100, y=400), None, ("--allow", "scenario-b")),
        ("VPC-attached Lambda in a subnet passes", add_icon(nv, i="fn", p="app1", l="Lambda", f="#ED7100", r="lambda", x=90, y=65), None, ()),
        ("NAT Gateway proves the VPC", add_icon(add_icon(nv, i="fn", p="region", l="Lambda", f="#ED7100", r="lambda", x=100, y=400), i="nat1", p="pub1", l="NAT Gateway", f="#8C4FFF", r="nat_gateway", x=90, y=65), None, ()),
    ]
    bad = 0
    for name, xml, expect, extra in cases:
        code, out = run(xml, *extra)
        good = (code == 0 and out.startswith("PASS")) if expect is None else (code != 0 and expect in out)
        print(("ok   " if good else "FAIL ") + name)
        if not good:
            bad += 1
            print("     validator said:", out.strip()[:500])
    print(f"{len(cases) - bad}/{len(cases)} cases behave")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
