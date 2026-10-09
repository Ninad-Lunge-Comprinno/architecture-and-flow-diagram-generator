# House Style

Conventions derived from working outputs (ignosis, docustack-ai) and the
Comprinno Architecture Template. Follow these rules exactly — do not scale
coordinates or change values unless the rule explicitly permits it.

> **AZ count: ask if not specified, default to 3 AZs. All constants in this
> document assume 3 AZs.**
>
> **For geometry numbers, use `references/coords-cheatsheet.md`. This file
> contains style strings and layout rules only.**

---

## 1. Canvas and page settings

Every diagram page uses these `mxGraphModel` attributes:

```xml
<mxGraphModel grid="1" gridSize="10" guides="1" tooltips="1" connect="1"
              arrows="1" fold="1" page="1" pageScale="1"
              pageWidth="850" pageHeight="1100" math="0" shadow="0">
```

`pageWidth` / `pageHeight` are only the print-page hint — the actual canvas is
much larger. All geometry coordinates are absolute in a coordinate space that
starts at (0,0). Working diagrams span roughly **x: 0–3100, y: 0–2500** for
architecture pages and **x: 0–2300, y: 0–1100** for flow pages.

---

## 2. Page frame, logo, and title block

Paste these three cells verbatim on every page. Replace only the text values.

**Logo source**: Use the base64 blob embedded in the skeleton file at
`references/skeleton-3az.drawio.xml`. Do not re-encode from a local path. Do NOT reuse
an old/truncated blob — a broken blob renders as a blank or missing image. Copy the
`image=` attribute verbatim from the skeleton's `brand` cell.

Set the brand cell style to
`shape=image;aspect=fixed;imageAspect=0;strokeColor=none;image=data:image/png,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;`
Recommended logo geometry on an architecture page: `x=30 y=50 width=240.9 height=50`.
The actual PNG is 1200×250 (~4.8:1); keep that aspect ratio when resizing.

```xml
<!-- outer border — strokeWidth=3, fillColor=none, plain black -->
<mxCell id="border" parent="1"
  style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#000000;strokeWidth=3;"
  vertex="1">
  <mxGeometry x="0" y="-40" width="3100" height="2600" as="geometry"/>
</mxCell>

<!-- Comprinno logo — real PNG, base64 copied from references/skeleton-3az.drawio.xml -->
<mxCell id="brand" parent="1"
  style="shape=image;aspect=fixed;imageAspect=0;strokeColor=none;image=data:image/png,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;"
  vertex="1">
  <mxGeometry x="30" y="50" width="240.9" height="50" as="geometry"/>
</mxCell>

<!-- title block — replace PROJECT_NAME and metadata values -->
<mxCell id="title" parent="1"
  value="&lt;h1 style='text-align:left'&gt;&lt;b style='font-size:32px'&gt;PROJECT_NAME&lt;/b&gt;&lt;/h1&gt;&lt;div style='text-align:left;font-size:20px'&gt;Version: 1.0&lt;/div&gt;&lt;div style='text-align:left;font-size:20px'&gt;Date: To be filled&lt;/div&gt;&lt;div style='text-align:left;font-size:20px'&gt;Creator: To be filled&lt;/div&gt;&lt;div style='text-align:left;font-size:20px'&gt;Reviewer: To be filled&lt;/div&gt;"
  style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;"
  vertex="1">
  <mxGeometry x="290.9" y="0" width="440" height="200" as="geometry"/>
</mxCell>
```

**Key points:**
- Border: plain black `rounded=0`, `strokeWidth=3`, `fillColor=none`. NOT a `fillColor=default; strokeColor=#0066CC` box.
- Logo: embed the real Comprinno PNG by copying the base64 blob from `references/skeleton-3az.drawio.xml`. Do not re-encode from a local path. A stale or truncated blob will not render.
- Title block: use a bold project name (36px), a subtitle (22px), and a metadata line (18px). Place it to the right of the logo.

---

## 3. Container hierarchy and coordinates

Every container is a **parent cell** (`container=1;pointerEvents=0;collapsible=0;
recursiveResize=0`). Children use **coordinates relative to their parent**.

```
parent=1 (root)
├── border          (absolute coords, large canvas)
├── brand           (absolute)
├── title           (absolute)
├── users           (absolute, outside AWS Cloud)
│
├── cloud           (absolute, e.g. x=260 y=250 w=2727 h=2115)
│   ├── s3          (relative to cloud, global row)
│   ├── iam         (relative to cloud, global row)
│   │
│   └── region      (relative to cloud, e.g. x=247 y=285 w=2395 h=1745)
│       ├── secrets_manager  (relative to region, services row)
│       ├── cloudwatch       (relative to region, services row)
│       ├── cloudtrail       (relative to region, services row)
│       ├── kms              (relative to region, services row)
│       ├── acm              (relative to region, services row)
│       ├── ecr              (relative to region, services row)
│       │
│       └── vpc   (relative to region, e.g. x=85 y=260 w=2225 h=1405)
│           ├── igw           (relative to vpc)
│           ├── alb           (relative to vpc)
│           │
│           ├── az1           (relative to vpc, e.g. x=520 y=80  w=1640 h=340)
│           │   ├── pub1      (relative to az1, e.g. x=35 y=50 w=380 h=250)
│           │   │   └── nat1  (relative to pub1)
│           │   ├── app1      (relative to az1, e.g. x=455 y=50 w=650 h=250)
│           │   └── data1     (relative to az1, e.g. x=1145 y=50 w=300 h=250)
│           │       ├── rds1  (relative to data1)
│           │       └── ...
│           │
│           ├── az2           (relative to vpc, e.g. x=520 y=540 w=1640 h=340)
│           │   └── ...same subnet structure...
│           │
│           └── ecs_cluster   (relative to vpc, vertical lane spanning all AZs)
│               ├── fargate-az1
│               └── fargate-az2
│
└── edges           (all edges: parent=1, use absolute coordinates for waypoints)
```

**Critical rules:**
- `cloud`, `region`, `vpc`, `az`, subnets, and compute-group lanes are ALL
  container cells with `parent` set to their enclosing container.
- Compute icons inside subnets have `parent` set to the subnet cell.
- Compute icons inside cluster lanes have `parent` set to the lane cell.
- **Edges always have `parent="1"` (root)**, even if they connect nested nodes.
  Use absolute-coordinate waypoints in `<Array as="points">`.

---

## 4. Canonical coordinate values

> **All geometry numbers live in `references/coords-cheatsheet.md`.**
> Do not read numbers from this file. This section is intentionally empty
> to prevent the model from using stale values.
>
> The cheatsheet contains: container x/y/w/h, subnet dimensions, icon
> positions, lane geometry, CloudFront/WAF/Route53 positions, edge formulas,
> N-AZ generalisation formulas, and a common-mistakes table.


## 5. Icon style (copy verbatim, change only resIcon and fill colour)

```xml
style="sketch=0;
  points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],
          [0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],
          [0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];
  outlineConnect=0;
  fontColor=#232F3E;
  fillColor=CATEGORY_COLOR;
  strokeColor=#ffffff;
  dashed=0;
  verticalLabelPosition=bottom;
  verticalAlign=top;
  align=center;
  html=1;
  whiteSpace=wrap;
  labelWidth=160;
  spacingTop=2;
  fontSize=18;
  fontStyle=0;
  aspect=fixed;
  shape=mxgraph.aws4.resourceIcon;
  resIcon=SERVICE_STENCIL;"
```

- Icon size: **120×120** always.
- Font: `fontSize=18; fontStyle=0` (not bold — the bold is in the label HTML).
- Label HTML: `<font style="font-size:18px"><b>Service Name</b></font>`.
- `labelWidth=160` ensures the label wraps cleanly below the icon.
- Do NOT use `fontSize=14; fontStyle=1` — that produces small, clipped labels.

---

## 6. Container styles (copy verbatim)

**AWS Cloud**
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_aws_cloud_alt;
  strokeColor=#232F3E;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#232F3E;dashed=0;strokeWidth=2;"
```

**Region** (dashed blue)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_region;
  strokeColor=#147EBA;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#147EBA;dashed=1;strokeWidth=2;"
```

**VPC** (solid green)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc;
  strokeColor=#248814;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#232F3E;dashed=0;strokeWidth=2;"
```

**Availability Zone** (dashed grey)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_availability_zone;
  strokeColor=#545B64;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#545B64;dashed=1;strokeWidth=2;"
```

**Public subnet** (green fill)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;
  strokeColor=#248814;fillColor=#E9F3E6;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#248814;dashed=0;strokeWidth=2;"
```

**App subnet** (light blue fill)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;
  strokeColor=#147EBA;fillColor=#E6F2F8;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#147EBA;dashed=0;strokeWidth=2;"
```

**DB subnet** (blue fill)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;
  strokeColor=#147EBA;fillColor=#CCE5FF;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#147EBA;dashed=0;strokeWidth=2;"
```

**Auto Scaling Group lane** (dashed orange)
```
style="sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;
  fontSize=18;fontStyle=0;container=1;pointerEvents=0;collapsible=0;
  recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_auto_scaling_group;
  strokeColor=#D86613;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;
  fontColor=#D86613;dashed=1;strokeWidth=2;"
```

**ECS / EKS cluster lane** (solid orange rectangle, no grIcon)
```
style="fillColor=none;strokeColor=#ED7100;verticalAlign=top;fontStyle=1;
  fontColor=#ED7100;whiteSpace=wrap;html=1;strokeWidth=2;align=center;spacingTop=8;"
```

---

## 7. Label convention

| Scope | Use | Avoid |
|-------|-----|-------|
| Architecture page | `Amazon EC2` | `EC2 (m6a.2xlarge)` |
| Architecture page | `Amazon S3` | `S3 (Documents)` |
| Architecture page | `Availability Zone` | `Availability Zone 1` |
| Architecture page | `VPC` | `Docustack VPC` |
| Flow page | `App Tier (EC2 m6a.2xlarge)` | (detail OK on flow pages) |

Label HTML for icons: `<font style="font-size:18px"><b>Service Name</b></font>`

---

## 8. Edge style

All edges have `parent="1"` (root). Standard style:

```
style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;
  html=1;strokeWidth=4;fontStyle=0;fontSize=14;fontColor=#232F3E;
  labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;
  exitX=1.0;exitY=0.5;exitDx=0;exitDy=0;
  entryX=0.0;entryY=0.5;entryDx=0;entryDy=0;"
```

Use `strokeWidth=4` (not 3). Add `dashed=1` for async/deploy flows.
Use `<Array as="points">` with absolute coordinates to route around icons.

---

## 9. Placement scopes

| Scope | Container parent | Examples |
|-------|-----------------|----------|
| Global / edge (above Region) | `cloud` | CloudFront, Route 53, IAM, S3 (CloudFront static-site origin), **WAF** |
| Above ALB (not inline) | root(`1`) | WAF — connected vertically to ALB top; not in the horizontal inbound path |
| Regional services row | `region` | S3 (app data bucket), ACM, Secrets Manager, KMS, CloudWatch, CloudTrail, ECR, Lambda |
| VPC entry column | `vpc` | IGW, ALB |
| Public subnet | inside AZ public-subnet container | NAT Gateway |
| App subnet | inside AZ app-subnet container | (compute lives in the cluster/ASG lane over this column) |
| DB subnet | inside AZ db-subnet container | RDS, Aurora, ElastiCache |
| Compute lane × AZ | inside lane container | EC2, Fargate |
| Outside AWS | root (parent=1) | Users |

**Placement rules:**
- Users render **outside** the AWS Cloud container — parent=1, to the left.
- **CloudFront is the entry point for web traffic**: place it in the `cloud`
  band inline with the IGW/ALB row (same y-centre), left of the VPC entry
  column. This keeps the inbound path a straight horizontal line
  (Users → CloudFront → IGW → ALB). WAF, when
  present, attaches to CloudFront there.
- When there is NO CloudFront, the ALB (and WAF) is the entry point inside `vpc`.
- IGW sits at the **left VPC border**: negative x (e.g. x=-60) relative to the
  vpc container so it straddles the VPC left edge.
- **S3 as a CloudFront static-site origin** sits in the global/edge band next to
  CloudFront (per house decision — treat the static origin as edge for layout).
- **S3 as an application data bucket** (not a CloudFront origin) sits in the
  `region`, outside the VPC.
- ACM is regional for ALB certificates; place in `region`.
- IAM, Route 53, and CloudFront are global; place in the `cloud` band.

---

## 10. Category colours (AWS 2020 palette)

| Category | Fill | Examples |
|----------|------|----------|
| compute / containers | `#ED7100` | EC2, ECS, EKS, Fargate, Lambda, ECR |
| database | `#C925D1` | RDS, Aurora, ElastiCache, DynamoDB |
| networking | `#8C4FFF` | ALB, NLB, NAT Gateway, IGW, CloudFront, Route 53 |
| storage | `#7AA116` | S3, EFS, Backup |
| security | `#DD344C` | WAF, KMS, IAM, ACM, Secrets Manager, GuardDuty |
| management | `#E7157B` | CloudWatch, CloudTrail, Config, SNS |
| ml | `#01A88D` | Bedrock, SageMaker, Transcribe, Rekognition |

---

## 11. Flow page layout

Flow pages use a simpler coordinate space (typically ~2500×1200):

- Border: `x=0 y=0 w=2500 h=1200; rounded=0; strokeColor=#000000; strokeWidth=3`
- Logo and title block: same style as the architecture page (real base64 logo).
- Nodes: left-to-right, 280px spacing between icon centres (icon=120×120).
- All nodes are children of `parent="1"` (root), NOT nested inside containers,
  unless a container boundary is meaningful for the flow.
- Branch nodes (e.g. S3 static assets, Secrets Manager) sit on a row ~220px
  above the main left-to-right spine and connect with a short dashed arrow.
- Edges: `parent="1"`, `strokeWidth=4`, use waypoints to avoid crossings.
- Return/response edges use `dashed=1` and a lighter/category `strokeColor`.
- Labels on edges: short verb phrases; number the main-path steps ①②③④.

---

## 12. What the architecture page must NOT do

- Do not use a tiny canvas with 60×60 icons — everything will be microscopic. Icons are always 120×120.
- Do not set `container=0` on subnets or AZ cells.
- Do not use `fillColor=default` on the outer border; use `fillColor=none` + black stroke, `strokeWidth=3`.
- Do not reuse a stale/truncated logo blob — copy a fresh base64 blob from `references/skeleton-3az.drawio.xml`.
- Do not place icons as siblings of their enclosing container — they must be children.
- Do not put `parent="1"` on icons that belong inside a subnet or lane.
- Do not use `fontSize=14; fontStyle=1` on icons (use 18/20; 0 + bold HTML).
- Do not create arrows that run along container borders or take long diagonal routes.
- Do not connect the ALB to each task — connect it to the cluster lane border.
- Do not connect the cluster to replica databases — connect to the primary only.
- Do not leave a subnet long and empty — size each subnet to its content and centre the icons.
- Do not omit `labelWidth=160` from icon styles — labels will overflow.
- Do not default to fewer than 3 AZs unless the user asks for a different count.

---

## 13. Scaling the canvas for different diagram sizes

> **See `references/coords-cheatsheet.md`** for the N-AZ scaling formulas.
> Key: AZ height=340, spacing=460px constant. Use `igw_y = 190 + 230*(N-1)`.


## 14. ECS / EKS / cluster lane — correct pattern

> **See `references/coords-cheatsheet.md`** — "Cluster lanes" section — for
> all lane geometry numbers and task icon positions.

**Lane style (solid orange rectangle, no grIcon — copy verbatim):**
```
style="fillColor=none;strokeColor=#ED7100;verticalAlign=top;fontStyle=1;
  fontColor=#ED7100;whiteSpace=wrap;html=1;strokeWidth=3;align=left;
  spacingTop=8;spacingLeft=55;fontSize=14;"
```

**Cluster badge style (45×45, parent=vpc):**
```
style="sketch=0;...shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.ecs;"
```
Use `resIcon=mxgraph.aws4.ecs` for ECS, `resIcon=mxgraph.aws4.eks` for EKS.
Never use `ecs` or `eks` — those produce blank boxes.

**Checklist before saving:**
- [ ] Lane parent is `vpc` (not `az` or `subnet`)
- [ ] Badge resIcon is `ecs` or `eks` (NOT `ecs`)
- [ ] Task icon parent is the lane cell
- [ ] Lane label: `fontSize=14; spacingLeft=55; align=left; strokeWidth=3`
- [ ] Two lanes side by side: w=240 each (not 480 each — overflows app column)


## 15. Edge (connection) quality checks

All edges must pass these checks before the file is saved:

**Routing:**
- [ ] No arrow runs along or inside a container border
- [ ] All waypoints use absolute coordinates (matching the large canvas scale)
- [ ] Cross-boundary arrows use explicit `exitX/exitY` and `entryX/entryY`
- [ ] Arrow bends only to avoid an icon, cross a boundary, or express a branch
- [ ] Return arrows (responses) use `dashed=1` and a lighter `strokeColor`
- [ ] **Baseline edges (ECR pull-image, Secrets Manager) source the LANE border,
      not a task icon inside the lane.** Sourcing a nested icon with `exitY=0`
      creates a tall vertical line cutting through everything above. Use
      `source="ecslane"` / `source="ekslane"` and add explicit horizontal
      waypoints to route below the regional services row.
      **Remove or keep very short any label** on baseline dashed edges —
      verbose labels on diagonal/vertical segments overlap icons and borders.
- [ ] **CloudFront→IGW: straight horizontal. CF is inline with the IGW/ALB row
      (same y-centre), so exit CF right (`exitX=1 exitY=0.5`) and enter IGW left
      (`entryX=0 entryY=0.5`) with NO waypoints.** Do not exit CF bottom (exitY=1)
      or detour around the cloud boundary — the inbound path is a clean horizontal line.

**Label placement:**
- [ ] Edge labels are short (≤4 words) and placed on a straight segment
- [ ] No label overlaps a node icon or container border
- [ ] Labels use `labelBackgroundColor=#FFFFFF` so they are readable over lines

**Scope — reduce the number of connections:**
- [ ] All edges have `parent="1"` (root) — never parent an edge to a container
- [ ] Do NOT draw all-to-all arrows (e.g. every Fargate task → every DB node)
- [ ] **Connect the load balancer to the CLUSTER LANE BORDER, not to each task.**
      One ALB→cluster edge replaces N ALB→task edges.
- [ ] **Connect the cluster to the PRIMARY database only, not to the replicas.**
      Show replica relationships as dashed `replication` edges from primary→replica.
- [ ] Keep baseline service connections (Fargate → Secrets Manager, ECR) as dashed
- [ ] Inbound path reads cleanly: Users → CloudFront → IGW → ALB → cluster.
      CloudFront is inline with the IGW/ALB row — inbound path is a straight horizontal line.

**Standard edge style (copy verbatim):**
```
style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;
  html=1;strokeWidth=4;fontStyle=0;fontSize=14;fontColor=#232F3E;
  labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;
  exitX=1.0;exitY=0.5;exitDx=0;exitDy=0;
  entryX=0.0;entryY=0.5;entryDx=0;entryDy=0;"
```

For dashed (async / baseline):
```
style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;
  html=1;strokeWidth=3;dashed=1;strokeColor=#999999;fontStyle=0;fontSize=14;
  fontColor=#232F3E;labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;"
```
