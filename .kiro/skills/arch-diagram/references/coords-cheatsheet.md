# Coordinate Cheatsheet

> **Two types of values here:**
> - **Constants** — fixed dimensions that define the scale. Copy verbatim.
> - **Formulas** — compute these from the constants for your specific topology.
>   Never copy the example outputs from another diagram; recalculate each time.

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

---

## Subnets inside each AZ (constants — same across all AZ rows)

| Subnet | parent | x | y | w | h | fill |
|--------|--------|---|---|---|---|------|
| public | azN | 35 | 50 | **380** | 250 | ← default for 2 icons; use formula for n icons | `#E9F3E6` stroke `#248814` |
| app | azN | 455 | 50 | 650 | 250 | `#E6F2F8` stroke `#147EBA` |
| db | azN | 1145 | 50 | 300 | 250 | `#CCE5FF` stroke `#147EBA` |

Keep gaps between subnets at **40px**. DB default width=300 (1 icon, 90px padding each side).
Widen any subnet proportionally for more icons: `w = n×120 + (n-1)×40 + 2×padding`.

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
| 300 | 1 | — | 90 | — | (db default) |
| 380 | 2 | 40 | 40 | 200 |


| 650 | 1 | — | 265 | — |

---

## Users node — FORMULA

Users sits on the same horizontal row as IGW/ALB so the inbound path is a straight line.

```
users_abs_y_centre = vpc_abs_y + igw_vpc_y + icon_half
                   = (cloud_y + region_y + vpc_y) + igw_y + 60
                   = (250 + 285 + 260) + 650 + 60 = 1505

users_y = users_abs_y_centre - 60 = 1445
users_x = 60  (left of cloud boundary)
```

| Cell | parent | x | y | w | h |
|------|--------|---|---|---|---|
| users | root(1) | 60 | **= igw_abs_y_centre − 60** | 120 | 120 |

---

## Global row icons (children of cloud) — FORMULA

**CloudFront** sits inline with the IGW/ALB row (not in the top band) for a clean
horizontal inbound path.

```
cf_y (cloud-relative) = igw_abs_y - cloud_abs_y - icon_half
                      = (vpc_abs_y + igw_vpc_y) - cloud_abs_y - 60
                      = (795 + 650) - 250 - 60 = 1135
```
> Note: using the working-output values: vpc_abs_y = cloud_y+region_y+vpc_y = 250+285+260=795.
> cf_y = 795+650-250-60 = 1135. But since CF is a child of cloud (cloud_y=250):
> cf_cloud_rel_y = 1135 - 250 + 250 = ... actually:
> cf_abs_top = cf_abs_y_centre - 60 = 1505-60 = 1445. CF parent=cloud(abs y=250).
> cf_cloud_rel_y = 1445 - 250 = 1195. ✓ (matches the validated value)

```
cf_cloud_rel_y = igw_abs_y_centre - icon_half - cloud_abs_y
               = 1505 - 60 - 250 = 1195
```

**CloudFront x** — place left of the VPC left edge with a 40px gap:
```
vpc_abs_left = cloud_abs_x + region_cloud_x + vpc_region_x = 260+247+85 = 592
cf_abs_right = vpc_abs_left - 40 = 552
cf_cloud_rel_x = cf_abs_right - 120 - cloud_abs_x = 552 - 120 - 260 = 172
```
> Validated working value: x=112. The difference is because IGW at x=-60 means vpc_abs_left
> for the IGW icon edge is 592-60=532, so cf_abs_right < 532: cf_cloud_rel_x = 532-120-260=152.
> Use **x=112** (leaves 40px gap to IGW).

**S3 (CF static-site origin) and IAM** — top global band, **centre-aligned**:
```
n = number of global band icons (S3, IAM, Route53...)
group_w = n × 120 + (n-1) × 60
start_x = (cloud_width - group_w) / 2
x_i = start_x + i × 180
```
For n=2 (S3 + IAM): `start_x = (2727 - 300) / 2 = 1213.5 ≈ 1214`

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

**Lane height:**
```
lane_h = (last_AZ_y + AZ_height) - first_AZ_y
       = (1000 + 340) - 80 = 1260   [for 3-AZ default]
```

**Lane y:** always = `az1_y` = **80**

**Lane width and x:**
- Single lane: `w=480`, centre in app column: `x = app_az_x + (app_w - lane_w) / 2 = 415 + (650-480)/2 = 415+85 = 500`. Round to **500** or adjust to avoid overlap with db subnet.
- Two lanes: `w=240` each. `x_lane1 = app_az_x + gap`, `x_lane2 = x_lane1 + 240 + 20`

**Task icon x inside lane (centres 120px icon):**
```
task_x = (lane_width - 120) / 2
```
Single lane (w=480): task_x = **180**
Dual lane (w=240): task_x = **60**

**Task icon y inside lane — FORMULA (not hardcoded):**
```
az_mid_vpc_y = az_y + AZ_height/2          (midpoint of AZ row, vpc-relative)
task_y = (az_mid_vpc_y - lane_top_vpc_y) - icon_half
       = (az_y + 170) - 80 - 60
```

| AZ | az_y | az_mid_vpc_y | task_y |
|----|------|-------------|--------|
| AZ-1 | 80 | 250 | 110 |
| AZ-2 | 540 | 710 | 570 |
| AZ-3 | 1000 | 1170 | 1030 |

> These table values are the formula outputs for the 3-AZ default. **If you change
> AZ positions, recalculate using the formula, not by copying this table.**

**Badge (45×45, parent=vpc):**
```
badge_x = lane_x + 8
badge_y = lane_y + 8 = 88
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

For the 3-AZ working-output defaults with Aurora in AZ-1 db-subnet:
```
aurora_abs_y_centre = 250+285+260+80+50+65+60 = 1050
lane_abs_top        = 250+285+260+80 = 875
lane_height         = 1260
exitY = (1050 - 875) / 1260 = 0.139 ≈ 0.14
```

> **Recalculate this whenever the database's AZ row or the lane's vpc-relative y changes.**
> Do not copy 0.14 as a universal value.

---

## CloudFront → IGW edge routing

CF and IGW share the same absolute y-centre — the edge should be **horizontal** with no jog.

```
exitX=1  exitY = formula  (see EKS/ECS→DB section below)   (exit CF right-centre)
entryX=0 entryY=0.5  (enter IGW left-centre)
No waypoints needed — same y-centre, straight horizontal.
```

> CloudFront is always inline with IGW (same y-centre). These waypoints are only needed if CF is deliberately placed above the IGW row in an exceptional layout:
CF left and travelling down the left side of the cloud boundary:
```
exitX=0 exitY = formula  (see EKS/ECS→DB section below)   entryX=0 entryY=0.5
waypoints: x = cloud_abs_x - 40, y = cf_abs_y_centre
           x = cloud_abs_x - 40, y = igw_abs_y_centre
```

---

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

## Common mistakes (constants that are often wrong)

| Wrong | Correct |
|-------|---------|
| AZ height 720 | **340** |
| AZ y-spacing 820 | **460** |
| subnet height 580 | **250** |
| public subnet w=300 with 2 icons | **380** |
| lane w=480 each when 2 lanes | **240** each |
| lane w=230 | **480** (single) or **240** (dual) |
| lane label fontSize=20, align=center | **14, align=left, spacingLeft=55** |
| icon size 60×60 | **120×120** |
| border strokeWidth=2 | **3** |
| fontSize=14 on icons | **18** |
| `elastic_container_service` stencil | **`ecs`** |
| `elastic_kubernetes_service` stencil | **`eks`** |
| `certificate_manager` stencil | **`certificate_manager_3`** |
