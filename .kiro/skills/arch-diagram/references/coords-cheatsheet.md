# Coordinate Cheatsheet

> **Single source of truth:** This is the single source of truth for all geometry
> numbers. `house-style.md` contains style strings and rules only. Do not duplicate
> numbers in other files.

> **Two types of values here:**
> - **Constants** — fixed dimensions that define the scale. Copy verbatim.
> - **Formulas** — compute these from the constants for your specific topology.
>   Never copy the example outputs from another diagram; recalculate each time.

## ⚡ Precomputed 3-AZ lookup (copy directly for N=3, skip all formulas)

> Use these values as-is for the standard 3-AZ layout. Only recompute if N≠3.

| Element | Value | Notes |
|---------|-------|-------|
| igw y (vpc-rel) | **650** | aligns with AZ midpoint |
| users y (abs) | **1445** | inline with IGW/ALB row |
| CF cloud-rel y | **1195** | inline with IGW row |
| lane_x (vpc-rel) | **1010** | app_vpc_x + 35 |
| lane_y (vpc-rel) | **170** | app_vpc_y_first + 40 |
| lane_w | **300** | app_w - 55 (for app_w=355) |
| lane_h | **1110** | fits inside app subnets |
| task_y AZ-1 | **25** | centred in AZ-1 app subnet (lane-rel) |
| task_y AZ-2 | **485** | centred in AZ-2 app subnet (lane-rel) |
| task_y AZ-3 | **945** | centred in AZ-3 app subnet (lane-rel) |
| task_x | **90** | (301−120)/2 |
| EKS→DB exitY | **0.08** | (1050−965)/1110 |
| ECS→AZ3 DB exitY | **0.95** | (1015+50+65+60−965)/1110 — for cluster connecting to AZ-3 db |
| regional row start_x (n=6) | **688** | (2395−1020)/2 |
| regional row start_x (n=7) | **598** | (2395−1200)/2 |
| global band start_x (n=2) | **1214** | (2727−300)/2 |
| global band start_x (n=4) | **1034** | (2727−660)/2 |
| **Dual lanes** x_lane1 (vpc-rel) | **1010** | az1_x+app_x+(app_w−total_w)/2 |
| **Dual lanes** x_lane2 (vpc-rel) | **1270** | lane1_x+240+20 |
| dual lane task_x | **60** | (240−120)/2 |
| dual lane task_y AZ-1 | **85** | 25+60 label clearance |
| dual lane task_y AZ-2 | **545** | 485+60 |
| dual lane task_y AZ-3 | **1005** | 945+60 |
| dual app_w (2 lanes 240+gap) | **555** | 2×240+20+55 |
| dual db_x (az-rel) | **1055** | app_x+app_w+40 = 455+555+40 |


---

## Canvas & frame (constants)

| Cell | x | y | w | h | Notes |
|------|---|---|---|---|-------|
| border | 0 | -40 | 3100 | 2600 | `strokeWidth=3; fillColor=none; strokeColor=#000000` |
| brand (logo) | 30 | 50 | 240.9 | 50 | image cell, embed fresh base64 |
| title block | 300.9 | 0 | 440 | 200 | text cell, parent=1 |

---

## Container hierarchy (constants — copy verbatim)

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| cloud | root(1) | 260 | 250 | 2727 | 2115 |
| region | cloud | 247 | 285 | 2395 | 1745 |
| vpc | region | 85 | 260 | 2225 | 1405 |
| az1 | vpc | 520 | 80 | 1640 | 340 |
| az2 | vpc | 520 | 540 | 1640 | 340 |
| az3 | vpc | 520 | 1000 | 1640 | 340 |

AZ height = **340**. AZ y-spacing = **460px**. All constants.

---

## Entry column (constants)

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| igw | vpc | -60 | 650 | 120 | 120 |
| alb | vpc | 160 | 650 | 120 | 120 |

> **y=650 is the N=3 value.** The IGW/ALB row centres vertically on the AZ stack,
> so for other AZ counts use `igw_y = 190 + 230*(N-1)` (see Users node section).

---

## Subnets inside each AZ (constants — same across all AZ rows)

**Subnet width by icon count (MUST be consistent across subnet types):**

| Icons | Width | Formula | Use case |
|-------|-------|---------|----------|
| 1 | **300** | 120 + 180 padding | NAT, single compute, single DB |
| 2 | **380** | 120+40+120 + 100 padding | NAT+Bastion, Writer+Replica |
| 3 | **520** | 120+40+120+40+120 + 80 | Three services |

**Critical rule:** If public has 1 icon (w=300), app has 1 icon (w=300), and db has 1 icon (w=300),
ALL THREE must be w=300. Never make app wider "just because it's compute".

**Lane exception:** When app contains a cluster lane (vertical bar spanning AZs):
- `app_w = lane_w + 55` (lane + 35px left + 20px right)
- This is the ONLY case where app width differs from the icon-count formula

| Subnet | parent | x | y | w | h | notes |
|--------|--------|---|---|---|---|-------|
| public | azN | 35 | 50 | **300** (1 icon) or **380** (2 icons) | 250 | fill `#E9F3E6` stroke `#248814` |
| app | azN | pub_x + pub_w + 40 | 50 | **300** (1 icon) or **lane_w+55** (with lane) | 250 | fill `#E6F2F8` stroke `#147EBA` |
| db | azN | app_x + app_w + 40 | 50 | **300** (1 icon) or **380** (2 icons) | 250 | fill `#CCE5FF` stroke `#147EBA` |

**Example layouts:**

| Layout | public_w | app_w | db_w | Notes |
|--------|----------|-------|------|-------|
| All single icons | 300 | 300 | 300 | Consistent, balanced |
| NAT+Bastion, single compute, Writer+Standby | 380 | 300 | 380 | Width matches content |
| Single NAT, EKS lane (w=300), single DB | 300 | 355 | 300 | Lane adds 55px |

Keep gaps between subnets at **40px**.

---

## Icons inside subnets — FORMULA, not hardcoded

**Icon size:** always 120×120. **Icon y in 250-high subnet:** always **65** (50px top label gap + centred).

**Icon x — centre formula:**
```
x = (subnet_width - n_icons × 120 - (n_icons - 1) × gap) / 2
gap = 40px recommended
```

| Subnet w | n icons | gap | x (first) | x (second) |
|----------|---------|-----|-----------|------------|
| 300 | 1 | — | 90 | — |
| 380 | 2 | 40 | 40 | 200 |


| 650 | 1 | — | 265 | — |

---

## Users node — FORMULA

Users sits on the same horizontal row as IGW/ALB so the inbound path is a straight line.

> **N-AZ generalisation** — the IGW/ALB/CF row and the lane height depend on the
> number of AZs (N). The values below (650 / 1445 / 1195 / 1260) are the N=3 case.
> Recompute with these formulas for any other N:
> ```
> igw_y       = 190 + 230*(N-1)                     # 650 for N=3
> users_y     = cloud_y + region_y + vpc_y + igw_y  # = 795 + igw_y  (1445 for N=3)
> cf_cloud_y  = 545 + igw_y                          # 1195 for N=3
> lane_h      = 340 + 460*(N-1)                      # 1260 for N=3
> ```

```
users_abs_y_centre = vpc_abs_y + igw_vpc_y + icon_half
                   = (cloud_y + region_y + vpc_y) + igw_y + 60
                   = (250 + 285 + 260) + 650 + 60 = 1505   [N=3]

users_y = users_abs_y_centre - 60 = 1445   [N=3]
users_x = 60  (left of cloud boundary)
```

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| users | root(1) | 60 | **= igw_abs_y_centre − 60** | 120 | 120 |

---

## Global row icons (children of cloud) — FORMULA

> **Only applies if CloudFront was explicitly requested by the user.**
> If CloudFront is not in the request, skip this section entirely —
> do not add the icon or reserve its position.

### Geometry constraint — CRITICAL

Available space between cloud-left (abs x=260) and IGW (abs x=532) is **272px**.
- One icon inline: 120px → ✓ fits with 40px gaps on each side
- Two icons inline: 280px (120+40+120) → ✗ **does not fit** — will overlap IGW

**Therefore: Never place R53 and CF side-by-side inline.**

### Inbound path positioning — four cases

**Case 1: Neither R53 nor CF** (`Users → IGW → ALB`):
```
# No icons in the inline gutter. Users connects directly to IGW.
# Users at abs_x=100, IGW at abs_x=532. Clear path.
```

**Case 2: Route 53 only** (`Users → R53 → IGW → ALB`):
```
r53_cloud_rel_x = 72   # centred in the 272px space: (272-120)/2 ≈ 76, use 72
r53_cloud_rel_y = 1195
# R53 abs: x=332, right=452. Gap to IGW(532): 80px ✓
```

**Case 3: CloudFront only** (`Users → CF → IGW → ALB`):
```
cf_cloud_rel_x = 72   # same position as R53-only case
cf_cloud_rel_y = 1195
```

**Case 4: Route 53 + CloudFront** (`Users → R53 → CF → IGW → ALB`):
```
# ⚠️ Cannot fit both inline — use vertical stacking:
# R53 goes to GLOBAL BAND (top), CF takes the inline position

r53_cloud_rel_x = 72
r53_cloud_rel_y = 70   # global band, NOT inline

cf_cloud_rel_x = 72
cf_cloud_rel_y = 1195  # inline position

# Edge path: Users→R53(top, vertical)→CF(inline)→IGW→ALB
# The Users→R53 segment is vertical; R53→CF is vertical; CF→IGW→ALB is horizontal.
```

**Summary table — icon positions (cloud-relative):**

| Present | R53 x | R53 y | CF x | CF y | Notes |
|---------|-------|-------|------|------|-------|
| Neither | — | — | — | — | Users→IGW direct |
| R53 only | 72 | 1195 | — | — | R53 inline |
| CF only | — | — | 72 | 1195 | CF inline |
| R53 + CF | 72 | **70** | 72 | 1195 | R53 in global band, CF inline |

**S3 (CF static-site origin) and IAM** — top global band, **centre-aligned**:
```
n = number of global band icons (S3, IAM)
group_w = n × 120 + (n-1) × 60
start_x = (cloud_width - group_w) / 2
x_i = start_x + i × 180
```
For n=2 (S3 + IAM): `start_x = (2727 - 300) / 2 = 1213.5 ≈ 1214`

**Route 53** is `parent=cloud` at cloud-relative x=63 when placed inline (Case A — see
Route 53 placement section). Route53 abs left = `cloud_abs_x + 63` = 323 for default scale.
`users_x` must satisfy BOTH constraints:
  1. `users_abs_right + 40 ≤ cloud_abs_x`  → `users_x ≤ cloud_abs_x - 160 = 100`
  2. `users_abs_right + 40 ≤ Route53_abs_left` → `users_x ≤ Route53_abs_left - 160`
Constraint 1 is usually tighter. Default: **users_x = 100** (abs_right=220, 40px to cloud left=260).

| Icon | formula | example (n=2) |
|------|---------|---------------|
| first | `start_x` | 1214 |
| second | `start_x + 180` | 1394 |
| third | `start_x + 360` | 1574 |

---

## Regional services row (children of region) — FORMULA

All icons sit at **y=65** (constant). x positions are **centre-aligned** across the region width.

```
n = number of service icons
group_w = n × 120 + (n-1) × 60
start_x = (region_width - group_w) / 2   (region_width = 2395)
x_i = start_x + i × 180
```

| n | group_w | start_x | x positions |
|---|---------|---------|-------------|
| 4 | 660 | 868 | 868, 1048, 1228, 1408 |
| 5 | 840 | 778 | 778, 958, 1138, 1318, 1498 |
| 6 | 1020 | 688 | 688, 868, 1048, 1228, 1408, 1588 |
| 7 | 1200 | 598 | 598, 778, 958, 1138, 1318, 1498, 1678 |

> Each row is independently centred within its own container; the global band (few
> icons) and the regional row (many icons) are **NOT expected to align column-for-column**
> — this is correct, not a bug.

---

## Cluster lanes (children of vpc) — FORMULA

### One ECS/Fargate service replicated across AZs

Use one tall, transparent service lane to show a single logical ECS service
deployed across multiple AZs. The lane is a separate child of the VPC. Its
orange outline spans from the first app-subnet row through the last app-subnet
row and remains visible across the inter-AZ gaps. **Crossing those gaps is
intentional:** it shows that one ECS service is deployed in several AZs. Do not
shorten the outline at each subnet, split it into one box per AZ, or treat the
gap-crossing outline as a subnet-boundary error. Put the ECS service badge and
name just inside the lane's upper-left corner.

The orange service lane is an overlay/grouping boundary, not a replacement for
the blue app-subnet containers. Keep every app subnet as its own subnet with
its existing label, fill, border, AZ parent, and geometry. Do not convert an
app subnet into an ECS cluster or service container.

Place one Fargate task icon inside each app subnet/AZ where the service runs.
Center each task horizontally on the lane and vertically in its AZ's app
subnet. Keep each task cell parented to its actual app subnet so the subnet
placement remains accurate. Preserve its AWS Fargate icon style and stencil
when positioning it; do not recreate it as a generic shape or reparent it to
the overlay lane. The task icons share the same x coordinate, forming a
straight column. The lane outline groups these replicas; the repeated task
icons show their distribution. Do not add arrows between replicas to imply
replication.

For the main request path, connect to the logical service at the middle AZ row
(or to the lane edge on that row), rather than drawing separate incoming and
outgoing paths to every task. Keep the connection horizontal through that row
and clear of the task label. Only connect directly to an individual task when
the user specifically asks to show a task-level interaction. Apply the same
layout pattern to EKS workloads when one service is replicated across AZs.

**Lane must render INSIDE the app subnet column** — the lane's orange border must
not extend beyond the blue app subnet borders. The lane spans from inside the
first app subnet through inside the last app subnet, crossing the inter-AZ gaps.

**Lane geometry — fit inside app subnets:**
```
# App subnet vpc-relative position
app_vpc_x = az_x + app_az_x = 520 + 455 = 975
app_vpc_y_first = az1_y + app_az_y = 80 + 50 = 130
app_vpc_y_last_bottom = az3_y + app_az_y + app_h = 1000 + 50 + 250 = 1300

# Lane position (vpc-relative) — inside the app subnet column
lane_left_padding = 35                 # horizontal padding inside subnet (left)
lane_right_padding = 20                # horizontal padding inside subnet (right)
lane_top_padding = 40                  # vertical padding for subnet label
lane_bottom_padding = 20

lane_x = app_vpc_x + lane_left_padding = 975 + 35 = 1010
lane_y = app_vpc_y_first + lane_top_padding = 130 + 40 = 170
lane_w = app_w - lane_left_padding - lane_right_padding   # e.g. 355 - 55 = 300 for app_w=355
lane_h = (app_vpc_y_last_bottom - lane_bottom_padding) - lane_y
       = (1300 - 20) - 170 = 1110     [for 3-AZ, app_h=250]
```

**3-AZ default values (copy directly):**
- `lane_x = 1010` (vpc-relative)
- `lane_y = 170` (vpc-relative)
- `lane_w = 300` (for app_w=355, lane fits inside subnet)
- `lane_h = 1110`

**Lane width — size to content:**
Lane width = `120 + 2×pad` where pad≥60. Single icon, short label: `lane_w=300`.
Long label (>20 chars): `lane_w=480`. Dual lanes: `w=240` each.

**App subnet width follows the lane:** `app_w = lane_w + 55`
(35px left gap + 20px right gap). Do NOT use w=650 as a fixed default.
Example: lane_w=300 → app_w=355. lane_w=480 → app_w=535.

**Task icon x inside lane (centres 120px icon):**
```
task_x = (lane_width - 120) / 2
```
Single lane (w=301): task_x = **90**
Dual lane (w=240): task_x = **60**

**Task icon y inside lane — centred in app subnet region:**
```
# Task should be centred vertically in the portion of lane overlapping each AZ's app subnet
app_center_vpc_y = az_y + app_az_y + (app_h / 2) = az_y + 50 + 125 = az_y + 175
task_y = app_center_vpc_y - 60 - lane_y   # (lane-relative)
```

| AZ | az_y | app_center_vpc_y | task_y (lane-rel) |
|----|------|------------------|-------------------|
| AZ-1 | 80 | 255 | 25 |
| AZ-2 | 540 | 715 | 485 |
| AZ-3 | 1000 | 1175 | 945 |

> These table values are for the 3-AZ default with lane_y=170. **If you change
> AZ positions or lane geometry, recalculate using the formula.**

**Dual-lane label clearance:** With narrow lanes (w=240) and long labels like
"EKS Cluster (API)", the label text wraps and overlaps task icons. Add +60px
to each task_y for dual lanes: **AZ-1=85, AZ-2=545, AZ-3=1005**.

**Badge (45×45, parent=vpc):**
```
badge_x = lane_x + 8 = 1010
badge_y = lane_y + 8 = 178
```

---

## EKS/ECS → database edge — FORMULA

When connecting a lane to a database in AZ-1, the edge should be a **straight horizontal line**.
The exit point on the lane must match the database's absolute y-centre.

```
exitY = (db_abs_y_centre - lane_abs_top) / lane_height

db_abs_y_centre = cloud_y + region_y + vpc_y + az1_y + db_az_y + db_icon_y + icon_half
lane_abs_top    = cloud_y + region_y + vpc_y + lane_vpc_y
```

For the 3-AZ defaults with Aurora in AZ-1 db-subnet (lane_y=170, lane_h=1110):
```
aurora_abs_y_centre = 250+285+260+80+50+65+60 = 1050
lane_abs_top        = 250+285+260+170 = 965
lane_height         = 1110
exitY = (1050 - 965) / 1110 = 0.077 ≈ 0.08
```

> **Recalculate this whenever the database's AZ row or the lane's vpc-relative y changes.**
> Do not copy 0.14 as a universal value.

**Multiple DB icons in the same subnet (e.g. RDS + DocumentDB):**
When EKS/ECS connects to two icons in the same db subnet:
- Primary (e.g. RDS Writer): use the computed `exitY` fraction → enters db icon left side.
- Secondary (e.g. DocumentDB): enter from the **top** (`entryX=0.5 entryY=0`) using a
  separate edge with `exitY=0` from the lane top + horizontal waypoints to avoid piercing
  the VPC border. Or: exit the lane right at a different `exitY` so the two edges leave
  at visually distinct y-positions.
Never route two edges from the identical exit point to adjacent icons — the router bends one through the other.

---

## CloudFront → IGW edge routing

CF and IGW share the same absolute y-centre — the edge should be **horizontal** with no jog.

```
exitX=1;exitY=0.5; entryX=0;entryY=0.5; no waypoints needed.
```

> CloudFront is always inline with IGW (same y-centre). These waypoints are only needed if CF is deliberately placed above the IGW row in an exceptional layout:
CF left and travelling down the left side of the cloud boundary:
```
exitX=0 exitY=1  entryX=0 entryY=0.5
waypoints: x = cloud_abs_x - 40, y = cf_abs_y_centre
           x = cloud_abs_x - 40, y = igw_abs_y_centre
```

---


**Inbound path without CloudFront** (the default when CF is not requested):
`Users → IGW → ALB` — all at the same abs y-centre, straight horizontal, no waypoints.
The horizontal Users→IGW segment **must not pass through any global-band icon** (Route 53,
S3, IAM). If a global-band icon would sit on that y-level between Users and IGW, it belongs
in the global band row (`cloud_rel_y=70`), not inline. Move the icon up — do not reroute the edge.


## Baseline edges (ECR, Secrets) — routing rule

**Never** source a baseline edge from a task icon inside a lane (`exitY=0` from a nested icon
goes straight up through the lane and region, creating a vertical line).
Source from the **lane border** itself:
```
source = "ecslane" or "ekslane"   (not the individual task icon)
exitX=0.5  exitY=0                (exit lane top centre)
```
Then route horizontal waypoints **above** the vpc top before turning toward the target:
```
waypoint_y = midpoint between region_svc_abs_bottom and vpc_abs_top
           = (region_abs_y + 65 + 120 + vpc_abs_y) / 2
           ≈ 757  for the default scale (compute per topology)
```
Route: lane_top → up to waypoint_y → left to target_abs_x → up to target.

---

## Lane label style (constant)

Always use these to prevent label overlapping the badge icon:
```
fontSize=14; spacingLeft=55; align=left; strokeWidth=3
```

---

## Icon style (copy verbatim — change only resIcon and fillColor)

```
sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];outlineConnect=0;fontColor=#232F3E;fillColor=FILL;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;whiteSpace=wrap;labelWidth=160;spacingTop=2;fontSize=18;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=STENCIL;
```

Label HTML: `<font style="font-size:18px"><b>Service Name</b></font>`

---

## ⚠️ Stencil names — always verify in shapes-aws.md

Never guess a stencil name. Look it up in `references/shapes-aws.md` before writing `resIcon=`.

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

## Flow page (constants)

| Cell | x | y | w | h |
|------|---|---|---|---|
| border | 0 | 0 | 2500 | 1200 |
| brand | 40 | 30 | 240.9 | 50 |
| title | 300.9 | 0 | 440 | 120 |

Flow nodes: 120×120, spine at y≈500, spacing = **320px** centre-to-centre (constant).
Branch nodes (e.g. S3): same x as anchor, y = spine_y − 240.

---


## Architecture page edges — allowed set

**Only these edges belong on the Architecture page:**
1. **Inbound path**: Users → (CloudFront →) IGW → ALB → cluster lane (solid)
2. **ECR**: lane → ECR (dashed, "pull image")
3. **Database**: lane → primary DB (solid), primary → replica (dashed replication)

**Everything else goes on Flow page only:**
- SQS, SNS, MSK, Kinesis (messaging/streaming)
- Bedrock, Transcribe, Comprehend (AI/ML)
- S3 (when used as data store)
- Secrets Manager, CloudWatch, KMS (operational)
- Lambda invocations, API calls, event triggers

The Architecture page shows **where services are deployed** (containers, subnets, AZs).
The Flow page shows **how requests flow through services** (numbered steps, branches).

## ECR edge waypoints — formula

Both EKS and ECS clusters must have a dashed `pull image` edge to ECR.
Source: the lane container border (`exitY=0`). Use horizontal waypoints:

```
waypoint_y = pvpc_abs_top - 30
           = cloud_y + region_cloud_y + pvpc_region_y - 30

For each lane:
  lane_abs_xc = pvpc_abs_x + lane_vpc_x + lane_w/2
  ecr_abs_xc  = region_abs_x + ecr_region_x + 60

Waypoints: (lane_abs_xc, waypoint_y), (ecr_abs_xc, waypoint_y)
```

Keep ECR edge unlabelled or use a short label like "pull" — verbose labels overlap container borders.


## Flow page layout — containers and alignment

Flow pages should show **AWS Cloud → Region → VPC** containers as context.
All service icons have `parent` matching their actual AWS scope.

### Container parents in flow diagrams

| Service | Parent | Reason |
|---------|--------|--------|
| Users | root(1) | External, outside cloud |
| Route 53, WAF, CloudFront | `f-cloud` | Global services |
| S3, Bedrock, Transcribe, MSK, RDS, DocumentDB, Lambda | `f-region` | Regional, outside VPC |
| IGW, ALB, ECS/EKS compute | `f-vpc` | VPC-bound |

### Spine alignment (critical — prevents edge bends)

All nodes on the main horizontal path MUST share the same abs y-centre.
Compute a single `spine_abs_yc` and derive every y from it:

```
spine_abs_yc = vay + vpc_icon_y + 60
  vpc_icon_y = vcy + (vch - 120) // 2   (centres 120px icon in VPC height)

For nodes in VPC (parent=f-vpc):
  node_y = vpc_icon_y

For nodes in Region (parent=f-region):
  node_y = spine_abs_yc - 60 - ray   (ray = cloud_y + region_cloud_y)

For nodes parent=1:
  node_y = spine_abs_yc - 60
```

If source and target y-centres differ by even 1px, orthogonal router adds a bend.

### Flow page spine spacing

Spine nodes are spaced **320px centre-to-centre** on the main horizontal path.
Branch nodes (S3, WAF, RDS) sit 240px above or below the spine.

```
node_x_i = first_node_x + i * 280
branch_y  = spine_abs_yc - 240 - 60   (above spine)
```

### WAF x-alignment in flow (must match ALB exactly)

```
alb_abs_xc  = vpc_abs_x + alb_vpc_rel_x + 60
waf_cloud_x = alb_abs_xc - 60 - cloud_abs_x
waf_cloud_y = region_cloud_y - 120 - 20   (20px gap above region top)
```

### Route 53 in flow page

Route 53 is `parent=f-cloud`. Cloud-relative x equidistant between cloud and region:
```
r53_cloud_x = (region_cloud_x - 120) // 2
r53_cloud_y = spine_abs_yc - 60 - cloud_abs_y
```

### S3 and regional services: must be RIGHT of VPC right border

```
min_region_rel_x = vpc_abs_right - region_abs_x + gap(40)
                 = (vpc_region_rel_x + vpc_width) + gap
```
S3/Bedrock/Transcribe etc. must have `region_rel_x ≥ min_region_rel_x` or they
visually appear inside the VPC.

### Users x in flow

```
users_x = cloud_abs_x - gap(40) - 120
```
Default: cloud_x=380 → users_x=100, right=340, gap to cloud=40px.


## Route 53 placement (conditional)

Route 53 is always `parent=cloud`. Its **x-position depends on the inbound path**:

**Case A — Route 53 IS the first hop** (request path is `Users → Route 53 → IGW → ALB`):
Place Route 53 inline with the IGW/ALB row so the inbound path is a straight horizontal line.
```
cloud_rel_x = (region_cloud_x - 120) / 2 = (247-120)/2 = 63   ← equidistant cloud↔region
cloud_rel_y = spine_abs_yc - 60 - cloud_abs_y  (= 1135 for 3-AZ default)
```

**Case B — Route 53 is NOT on the drawn inbound path** (path is `Users → IGW → ALB`):
Place Route 53 in the **top global band** alongside IAM, S3, etc. using the global-band
centre formula. Do NOT place it inline — an inline Route 53 would sit directly on the
Users→IGW horizontal segment and overlap it visually.
```
cloud_rel_y = 70   (global band top row)
cloud_rel_x = global-band centre formula: start_x + i × 180
```

**Boundary invariant (both cases):** Route 53 abs-left (`cloud_abs_x + cloud_rel_x`) must be
≥ `cloud_abs_x`. Never shift Route 53 left to make room for another service; if the
inbound row is crowded, remove the conflicting service instead.

## Common mistakes (constants that are often wrong)

| Wrong | Correct |
|-------|---------|
| AZ height 720 | **340** |
| AZ y-spacing 820 | **460** |
| subnet height 580 | **250** |
| public subnet w=300 with 2 icons | **380** |
| lane w=480 each when 2 lanes | **240** each |
| lane w=230 | **300–480** depending on content |
| app w=650 with single lane | **lane_w + 55** (e.g. 355 for lane_w=300) |
| lane label fontSize=20, align=center | **14, align=left, spacingLeft=55** |
| icon size 60×60 | **120×120** |
| border strokeWidth=2 | **3** |
| fontSize=14 on icons | **18** |
| `elastic_container_service` stencil | **`ecs`** |
| `elastic_kubernetes_service` stencil | **`eks`** |
| `certificate_manager` stencil | **`certificate_manager_3`** |
