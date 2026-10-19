# Coordinate Cheatsheet

> **Single source of truth** for every geometry number. `house-style.md` holds style strings and rules
> only; steering and SKILL point here. Do not copy numbers into other files.
>
> - **Constants** — fixed dimensions that define the scale. Copy verbatim.
> - **Formulas / presets** — computed from the constants. Never copy another diagram's output; use a
>   preset below or recompute.
> - `validate-drawio.py` enforces the wrap rule, centred rows, subnet columns, lane gaps, straight edges and
>   scope boxes, so a wrong number fails the run instead of shipping.

## The six rules

1. **Wrap rule (containers always wrap their content — no threshold, no "trim later"):**
   `az_w = content_right + 40`, `vpc_w = 520 + az_w + 65`, `region_w = 85 + vpc_w + 85`,
   `cloud_w = 247 + region_w + 85`, `border_w = 260 + cloud_w + 113`. `content_right` is the right edge of the
   right-most subnet (AZ-relative). Insets 520 / 85 / 247 are fixed. Do **not** scale containers
   proportionally. No rounding of widths; the only rounding is `round_half_up` for centred rows.
2. **Rows stay centred:** `start_x = round_half_up((container_w − (n×120 + (n−1)×60)) / 2)`, pitch 180 —
   regional row inside the Region (y=65), global band inside the Cloud (y=70). Recompute after every add/delete.
3. **Subnet columns:** `public x=35 | 40 | app | 40 | db`, same in every AZ row. Width by icon count: 1 → 300,
   2 → 380, 3 → 520. **Lane exception:** `app_w = lane_w + 55` (35px left / 20px right gap), single or dual lanes.
4. **Hierarchy (nested, scope = parent chain):** `cloud → region → vpc → az → subnet → icon`. Regional services
   `parent=region`; global services `parent=cloud`; the VPC is a child of the Region. All edges `parent="1"`.
5. **Scope is checked by position, not only by parent:** VPC box inside Region box; VPC-bound icons inside the VPC;
   regional-only services inside the Region and outside the VPC; global services inside the Cloud and outside
   the Region.
6. **Flow page is flat** (all nodes `parent="1"`, absolute coordinates, decorative scope boxes) — see "Flow page".

## ⚡ Presets (3-AZ, copy directly; for other layouts apply rules 1–3)

| Preset | public / app / db w | content_right | AZ | VPC | Region | Cloud | Border |
|---|---|---|---|---|---|---|---|
| **D1 (shipped skeleton)** single lane, 1-icon public | 300 / 355 / 300 | 1070 | 1110 | 1695 | 1865 | 2197 | 2570 |
| D2 dual lanes, 1-icon public | 300 / 555 / 300 | 1270 | 1310 | 1895 | 2065 | 2397 | 2770 |
| D3 NAT+Bastion (2-icon public), single lane | 380 / 355 / 300 | 1150 | 1190 | 1775 | 1945 | 2277 | 2650 |

Row start_x (round half up) — regional row (inside Region, y=65): D1 n=3: 693, n=4: 603, n=5: 513, n=6: 423, n=7: 333; D2 n=3: 793, n=4: 703, n=5: 613, n=6: 523, n=7: 433; D3 n=3: 733, n=4: 643, n=5: 553, n=6: 463, n=7: 373.
Global band (inside Cloud, y=70): D1 n=1: 1039, n=2: 949, n=3: 859, n=4: 769; D2 n=1: 1139, n=2: 1049, n=3: 959, n=4: 869; D3 n=1: 1079, n=2: 989, n=3: 899, n=4: 809.

**Lane values (vpc-relative; `lane_x = az_x + app_x + 35`):**

| Element | D1 / D2 (app_x=375) | D3 (app_x=455) |
|---|---|---|
| single lane x / y / w / h | **930** / 170 / 300 / 1110 | **1010** / 170 / 300 / 1110 |
| single-lane badge (45×45) | x=938 y=178 | x=1018 y=178 |
| single-lane app_w / db_x (az-rel) | 355 / **770** | 355 / **850** |
| dual lanes (w=240) x1 / x2 | 930 / 1190 | 1010 / 1270 |
| dual app_w / db_x (az-rel) | 555 / **970** | 555 / **1050** |
| task_x (lane-relative) single / dual | 90 / 60 | 90 / 60 |
| task_y (lane-relative) AZ-1/2/3 | 25 / 485 / 945 (dual with a wrapping label: 85 / 545 / 1005) | same |
| lane→DB `exitY` AZ-1 / AZ-2 / AZ-3 | **0.077 / 0.491 / 0.905** (3 decimals — see "Straight edges") | same |
| no lane, 1 direct app icon: app_w / db_x | 300 / 715 (pub 300) or 795 (pub 380) | |

N-AZ values: `igw_y = 190 + 230×(N−1)`, `users_y = 795 + igw_y`, `cf_cloud_y = 545 + igw_y`, `lane_h = 190 + 460×(N−1)`
(N=3: 650 / 1445 / 1195 / 1110). Region, VPC and Cloud heights each grow by 460 per extra AZ.

---

## Canvas & frame (constants)

| Cell | x | y | w | h | Notes |
|------|---|---|---|---|-------|
| border | 0 | -40 | `cloud_x + cloud_w + 113` (2570 for D1) | 2600 | `strokeWidth=3; fillColor=none; strokeColor=#000000` |
| brand (logo) | 30 | 50 | 240.9 | 50 | copy the cell from the skeleton (embedded blob, `strokeColor=none`) |
| title block | 300.9 | 0 | 440 | 200 | text cell, parent=1: name, subtitle, Version / Date / Creator / Reviewer |

## Container hierarchy (x/y/h constants; widths from the wrap rule)

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| cloud | root(1) | 260 | 250 | wrap (D1 2197) | 2115 |
| region | cloud | 247 | 285 | wrap (D1 1865) | 1745 |
| vpc | region | 85 | 260 | wrap (D1 1695) | 1405 |
| az1 | vpc | 520 | 80 | wrap (D1 1110) | 340 |
| az2 | vpc | 520 | 540 | same | 340 |
| az3 | vpc | 520 | 1000 | same | 340 |

AZ height = **340**, AZ y-spacing = **460**. Absolute origins (3-AZ): vpc_abs = (592, 795); region_abs = (507, 535).

## Entry column (constants, N=3)

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| igw | vpc | -60 | 650 | 120 | 120 |
| alb | vpc | 160 | 650 | 120 | 120 |

For other AZ counts use `igw_y = 190 + 230×(N−1)`.

## Subnets inside each AZ

| Subnet | parent | x | y | w | h | style |
|--------|--------|---|---|---|---|-------|
| public | azN | 35 | 50 | 300 (1 icon) / 380 (2) | 250 | fill `#E9F3E6` stroke `#248814` |
| app | azN | pub_x + pub_w + 40 | 50 | 300 (1 icon) / lane_w+55 (lane) | 250 | fill `#E6F2F8` stroke `#147EBA` |
| db | azN | app_x + app_w + 40 | 50 | 300 (1) / 380 (2) | 250 | fill `#CCE5FF` stroke `#147EBA` |

**Consistency:** if public, app and db each hold one icon, all three are w=300. Never widen app "because it's
compute" (the old w=650 default is wrong). Gaps between subnet columns are 40.

Icons inside subnets: 120×120, **y=65**, `x = (subnet_w − n×120 − (n−1)×40) / 2` (w=300, n=1 → 90; w=380, n=2 → 40 / 200).

## Users, CloudFront and the global band

```
users_abs_y_centre = vpc_abs_y + igw_y + 60 = 795 + 650 + 60 = 1505   [N=3]
users_y = 1445   users_x = 60  (any x ≤ cloud_abs_x − 160 = 100 passes)
```

| Cell | parent | x | y |
|---|---|---|---|
| users | root(1) | 60 | igw_abs_y_centre − 60 |
| CloudFront (only if requested) | cloud | 72 | 1195 [N=3] — inline with IGW, `Users → CF → IGW → ALB` straight, `exitX=1 exitY=0.5 entryX=0 entryY=0.5`, no waypoints |
| Route 53, IAM, S3 (CloudFront origin) | cloud | global-band formula (left→right: Route 53, IAM, S3) | 70 |

- **Route 53 is DNS, not a network hop:** always the global band, never inline, **no Route 53 edges on the Architecture page**.
- **WAF follows what it protects** (AWS WAF is regional except when attached to CloudFront): fronting CloudFront →
  global band (`parent=cloud`, y=70); fronting an ALB → regional row (`parent=region`, y=65). Never root, never in
  the VPC. **No WAF edge on the Architecture page** (the association is a Flow-page edge).
- Inbound path without CloudFront: `Users → IGW → ALB`, one straight horizontal line; no global-band icon may sit on it.

## Regional services row (children of region, y=65)

Baseline (always): CloudWatch, CloudTrail, KMS. IAM is in the global band. Optional: Secrets Manager, ECR, ACM, WAF
(ALB-fronting), Lambda, primary S3 data store. Start x from rule 2 with `container_w = region_w`.

---

## Cluster lanes (children of vpc)

One tall, transparent lane (orange outline) shows one logical ECS/EKS service replicated across AZs. It overlays
the app subnets and crosses the inter-AZ gaps on purpose; do not split it per AZ or convert a subnet into a
service container. The lane renders **inside the app-subnet column**.

```
lane_x = az_x + app_x + 35                 (35px left gap; D1: 930, D3: 1010)
lane_y = az1_y + 50 + 40 = 170             (40px for the subnet label)
lane_w = app_w − 55                        (single 300; dual lanes 240 each, 20px apart)
lane_h = (az3_y + 50 + 250 − 20) − lane_y = 1110   [N=3]
```

- **Width:** `lane_w = 120 + 2×pad`, pad ≥ 60. Short label → 300 (single); label > 20 characters → 480 (then
  `app_w = 535`); dual lanes 240 each (`app_w = 2×240 + 20 + 55 = 555`).
- **Tasks are children of the lane** (`parent=<lane id>`): `task_x = (lane_w − 120)/2` (single 90, dual 60),
  `task_y = az_y + 175 − 60 − lane_y` → 25 / 485 / 945. Keep the AWS Fargate stencil; do not draw arrows between replicas.
- **Dual-lane label clearance:** add +60 to `task_y` (85 / 545 / 1005) **only when the lane label wraps** (label
  > ~20 characters at fontSize 14 in a 240-wide lane). Short labels ("Amazon EKS") keep 25 / 485 / 945.
- **Badge** 45×45, `parent=vpc`, at `x = lane_x + 8`, `y = lane_y + 8 = 178`.
- The main request path connects to the **lane border** at the middle AZ row, not to each task.

## Lane label style (constant)

Always use these to prevent label overlapping the badge icon:
```
fontSize=14; spacingLeft=55; align=left; strokeWidth=3
```

---

### Straight edges (lane → database, validator-enforced, |dy| ≤ 2px)

```
exitY = (db_abs_y_centre − lane_abs_top) / lane_h          # use 3 DECIMALS: 0.077, 0.491, 0.905
db_abs_y_centre = 795 + az_y + 50 + 65 + 60 ; lane_abs_top = 795 + lane_y
```

`0.08` is a ~4px jog and `0.91` for AZ-3 a ~5px jog — always three decimals. Recompute whenever the DB's AZ row or
the lane y changes. Two edges into the same db subnet must leave at different `exitY` (or the second enters from the
top with waypoints); never route two edges from one exit point to adjacent icons.

### Architecture page edges — allowed set

1. Inbound path: Users → (CloudFront →) IGW → ALB → cluster lane (solid).
2. ECR: lane → ECR (dashed, "pull image") for **every** ECS/EKS lane.
3. Database: lane → primary DB (solid), primary → replica (dashed replication).

Everything else (SQS, SNS, MSK, Bedrock, Transcribe, S3 data access, Secrets Manager, CloudWatch, KMS, Lambda
invocations, Route 53, WAF) is a **Flow-page** edge. All edges `parent="1"`.

### ECR / baseline edge waypoints

Source the **lane border** (`exitX=0.5 exitY=0`), never a task icon. Route the horizontal run through the gap between
the regional-row labels (they extend to y≈766) and the VPC top (795), 12px clear of the border:

```
vpc_abs_top = cloud_y + region_y + vpc_y = 250 + 285 + 260 = 795
waypoint_y  = vpc_abs_top − 12 = 783
lane_abs_xc = vpc_abs_x + lane_x + lane_w/2        (vpc_abs_x = 260 + 247 + 85 = 592)
ecr_abs_xc  = region_abs_x + ecr_x + 60            (region_abs_x = 507)
waypoints: (lane_abs_xc, 783), (ecr_abs_xc, 783)
```

Keep baseline edges unlabelled or use a short label ("pull").

## Icon style (copy verbatim — change only resIcon and fillColor)

```
sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];outlineConnect=0;fontColor=#232F3E;fillColor=FILL;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;whiteSpace=wrap;labelWidth=160;spacingTop=2;fontSize=18;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=STENCIL;
```

Label HTML: `<font style="font-size:18px"><b>Service Name</b></font>`

---

---

## ⚠️ Stencil names — always verify in shapes-aws.md

Never guess. Look the key up in `references/shapes-aws.md` before writing `resIcon=`.

| Wrong (blank box) | Correct |
|-------------------|---------|
| `elastic_container_service` | `ecs` |
| `elastic_kubernetes_service` | `eks` |
| `certificate_manager` | `certificate_manager_3` |
| `cloudwatch` | `cloudwatch_2` |

---

## Category fill colours (constants)

| Category | fillColor | Examples |
|----------|-----------|---------|
| compute/containers | `#ED7100` | EC2, ECS, EKS, Fargate, ECR |
| database | `#C925D1` | RDS, Aurora, ElastiCache, DynamoDB |
| networking | `#8C4FFF` | ALB, NLB, NAT GW, IGW, CloudFront, Route53 |
| storage | `#7AA116` | S3, EFS |
| security | `#DD344C` | WAF, KMS, IAM, ACM, Secrets Manager |
| management | `#E7157B` | CloudWatch, CloudTrail, SNS |
| ml | `#01A88D` | Bedrock, SageMaker |
| users/external | `#232F3E` | Users icon |

---

---

## Edge styles (constants — copy verbatim)

**Solid (primary path):**
```
edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=4;fontStyle=0;fontSize=14;fontColor=#232F3E;labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;
```

**Dashed (baseline/async):**
```
edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;dashed=1;strokeColor=#999999;fontStyle=0;fontSize=14;fontColor=#232F3E;labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;
```

**Replication:**
```
edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;dashed=1;strokeColor=#C925D1;fontStyle=0;fontSize=14;fontColor=#232F3E;labelBackgroundColor=#FFFFFF;spacing=5;whiteSpace=wrap;
```

All edges: `parent="1"` (root).

---

---

## Flow page (flat layout — constants)

The Flow page is **flat**: every icon and edge is `parent="1"` with absolute coordinates. The Cloud / Region / VPC
boxes are **decorative scope boxes** (`container=0`, parent `1`); they are never parents, so editing in draw.io
cannot re-parent or drift a node. `validate-drawio.py` checks each node against the boxes by position.

| Cell | x | y | w | h |
|------|---|---|---|---|
| border | 0 | 0 | 2500 | 1200 |
| brand | 40 | 30 | 240.9 | 50 |
| title | 300.9 | 0 | 440 | 200 (name, subtitle, Version/Date/Creator/Reviewer) |
| f-cloud (box) | 380 | 220 | 2040 | 920 |
| f-region (box) | 680 | 390 | 1700 | 680 |
| f-vpc (box) | 740 | 450 | 1000 | 560 |

**Spine:** nodes 120×120, node top `y = 670` (centre 730) for every spine node, pitch **320** centre-to-centre,
`x = 220 + 320k`:

| k | scope | x | rule |
|---|---|---|---|
| 0 | Users (outside the cloud box) | 220 | `users_x = cloud_x − 40 − 120` |
| 1 | cloud, left of the region box | 540 | CloudFront |
| 2–4 | VPC box | 860 / 1180 / 1500 | IGW, ALB, compute, DB… (all VPC-bound) |
| 5–6 | region box, right of the VPC | 1820 / 2140 | S3, Bedrock, Transcribe, SQS… |

Scope map: **VPC box** — IGW, ALB/NLB, ECS/EKS/Fargate/EC2, RDS, Aurora, DocumentDB, MSK, ElastiCache, NAT, endpoints
(they live in VPC subnets — same scope as the Architecture page). **Region box, outside the VPC** — S3, Bedrock,
Transcribe, SQS, SNS, DynamoDB, Lambda (unless VPC-attached), CloudWatch, KMS, Secrets Manager, ECR, a WAF fronting an
ALB. **Cloud box, outside the Region** — CloudFront, Route 53, IAM, a WAF fronting CloudFront.

**Branch nodes** (240px off the spine: `y = 430` above, `y = 910` below) are **region-scope** services anchored to
k=5/6 only. Never branch off a VPC node: 240px above/below leaves the 560px-high VPC box. Cloud scope (outside the region): WAF
fronting CloudFront at `(540, 250)`, Route 53 at `(470, 910)`.

**Edges:** Users → Route 53 (dashed "DNS query") → the public endpoint it resolves to (CloudFront, otherwise the
ALB — **never the IGW**); WAF → its target (dashed "inspect"). Keep every edge off other icons; add waypoints if needed.
The y-centre of nodes joined by a straight edge must be identical, or the router adds a bend.

---

## Common mistakes

| Wrong | Correct |
|-------|---------|
| containers left at the old 1640/2225/2395/2727 widths | wrap rule (rule 1); D1 = 1110/1695/1865/2197 |
| rows not re-centred after a width change | rule 2 |
| AZ height 720 / spacing 820 | **340** / **460** |
| subnet height 580 | **250** |
| public w=300 holding 2 icons | **380** |
| app w=650 with a single lane | **lane_w + 55** (355 for lane_w=300) |
| lane x copied from another layout | `az_x + app_x + 35` (D1 930, D3 1010) |
| tasks parented to the subnet | children of the lane |
| `exitY` rounded to 2 decimals | 3 decimals (0.077 / 0.491 / 0.905) |
| lane label fontSize=20, align=center | **14, align=left, spacingLeft=55** |
| icon size 60×60 | **120×120** |
| border strokeWidth=2 | **3** |
| fontSize=14 on icons | **18** |
| WAF with parent=1, or a WAF edge on the Architecture page | scope rule above; Flow-page edge only |
| Route 53 inline / Route 53 → IGW | global band; DNS → CloudFront or ALB |
| Flow nodes parented to the scope boxes | parent `1`, absolute coordinates |
| `elastic_container_service` / `elastic_kubernetes_service` / `certificate_manager` stencils | `ecs` / `eks` / `certificate_manager_3` |
