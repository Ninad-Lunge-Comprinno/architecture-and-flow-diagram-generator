# Architecture diagram conventions

For architecture requests, use `.kiro/skills/arch-diagram/SKILL.md`. Let Kiro
reason about the requirements, ask only topology-changing questions, and keep
the user-facing workflow prompt based. The normal deliverable is one editable
Draw.io file with one architecture page and one primary flow page; do not add
extra flows unless requested.

**Visual reference precedence (most authoritative first):**
1. `references/coords-cheatsheet.md` — **the only source for geometry numbers**.
   All x/y/w/h values, formulas, and derived positions live here. Do not read
   numbers from any other file.
2. `references/skeleton-3az.drawio.xml` — ready-made blank 3-AZ architecture.
   Copy it; fill in the topology. Never build containers from scratch.
3. `references/house-style.md` — style strings and layout rules (no numbers).
4. `diagram examples/Comprinno Architecture Template.drawio.xml` — visual
   style reference only. Do not copy its coordinates or topology.

Any recent validated output in `outputs/` can serve as a local reference
(gitignored, not in the repo).

Treat the template's example topology, AZ count, service inventory, metadata,
and connections as non-defaults. Use only its visual structure.

## Recurring rules that commonly fail — enforce these strictly

**Coordinate scale — constants (copy verbatim, never change):**
- Canvas border: `x=0 y=-40 w=3100 h=2600; strokeWidth=3; fillColor=none; strokeColor=#000000`
- Cloud: `x=260 y=250 w=2727 h=2115`
- Region: `x=247 y=285 w=2395 h=1745` (relative to cloud)
- VPC: `x=85 y=260 w=2225 h=1405` (relative to region)
- AZ rows (relative to VPC): `y=80 / 540 / 1000; h=340; spacing=460px`
- Subnets (relative to AZ): `public x=35 w=380 h=250` (default 2-icon; scale per content), `app x=pub_right+40 w=lane_w+55 h=250` when the lane is the only content;
  `app x=pub_right+40 w=(n×120+(n-1)×40+2×40) h=250` when icons are placed directly in the subnet.
  **Never use w=650 as a fixed default** — size the app subnet to its actual content.
  The 650 constant was derived for a wide multi-icon layout and is wrong for a single lane.
  `w=650` (default): use only when the app subnet holds 2+ direct-child icons., `db x=app_right+40 w=300 h=250` (1 icon default)
- IGW: `x=-60 y=650` (relative to VPC)
- Icon size: always 120×120. Icon y in 250-high subnet: always 65.

**Derived positions — always compute from formulas, never copy from another diagram:**
The specific values below (e.g. CloudFront y=1195, Users y=1445) are **N=3
examples**. For any other AZ count, recompute using the formulas in
`references/coords-cheatsheet.md` — do not reuse these numbers.
- **Users y**: `cloud_y + region_y + vpc_y + igw_vpc_y = 250+285+260+650 = 1445`
- **CloudFront y** (inline with IGW row): `region_y + vpc_y + igw_y = 285+260+650 = 1195` (cloud-relative)
- **Regional icons x**: `start_x = (2395 - n×120 - (n-1)×60) / 2`, then `x_i = start_x + i×180`
- **Global band icons x** (S3, IAM): `start_x = (2727 - n×120 - (n-1)×60) / 2`, then `x_i = start_x + i×180`
- **Icon x inside subnet**: `(subnet_width - n×120 - (n-1)×40) / 2`
- **Lane height**: `(last_AZ_y + AZ_height) - first_AZ_y`
- **Task icon y in lane**: `(AZ_y + AZ_height/2) - lane_vpc_y - 60`
- **Task icon x in lane**: `(lane_width - 120) / 2`
- **EKS/ECS→DB exitY**: `(db_abs_y_centre - lane_abs_top) / lane_height`

**Cluster lanes (ECS/EKS/ASG):**
- Lane y = az1_y = 80. Lane height = formula above. Single lane w=480; dual lanes w=240 each.
- Use `fontSize=14; spacingLeft=55; align=left; strokeWidth=3` on lane label.
- Badge: 45×45, parented to `vpc`, at `x=lane_x+8, y=88`.
- Two lanes of w=480 each overflow the app column — use w=240 each for dual lanes.

**Edge routing rules:**
- **Inbound path Users→CF→IGW→ALB**: all at same abs y-centre (1505). Use `exitX=1 exitY=0.5, entryX=0 entryY=0.5`, no waypoints.
- **EKS/ECS→DB edge**: exitY is NOT 0.5 — use formula: `exitY = (db_abs_y_centre - lane_abs_top) / lane_h`
- **Inbound path without CloudFront** (the default when CF is not requested):
  `Users → IGW → ALB` — all at the same abs y-centre, straight horizontal, no waypoints.
  The horizontal Users→IGW segment **must not pass through any global-band icon** (Route 53,
  S3, IAM). If a global-band icon would sit on that y-level between Users and IGW, it belongs
  in the global band row (cloud_rel_y=70), not inline. Move the icon up — do not reroute the edge.
- **Baseline edges** (ECR, Secrets): source the LANE border, not a task icon inside it. Source from a task icon with `exitY=0` creates a long vertical line.
- **EKS/ECS→DB**: use computed `exitY` fraction so edge exits at db's y-centre → straight horizontal line.
- **All edges**: `parent="1"` (root).

**Stencil names — always verify in `references/shapes-aws.md`:**
- Never guess. `elastic_container_service` → **ecs**, `elastic_kubernetes_service` → **eks**, `certificate_manager` → **certificate_manager_3**.

**Common wrong values to avoid:**
- AZ height 720 → **340**. AZ spacing 820 → **460**.
- Subnet height 580 → **250**. Lane width 230 → **480** (single) / **240** (dual).
- `strokeWidth=2` on border → **3**. `fillColor=default; strokeColor=#0066CC` on border → wrong.

**Other layout rules:**
- Default to a **3-AZ** three-tier layout unless the user specifies otherwise.
- Embed the real Comprinno logo as a fresh base64 blob from
  `Downloads/comprinno-logo.png`; never reuse a stale/truncated blob.
  Always add `strokeColor=none` to the logo image cell style to prevent a border/underline appearing.
- **Size each subnet to its content.** Keep dimensions identical across AZ rows.
  App subnet with a lane as only content: `w = lane_w + 55` (35px left + 20px right).
  App subnet with direct icons: `w = n×120 + (n-1)×40 + 80` (40px each side).
  Do NOT use a fixed w=650 if the lane is narrower than 595px.
- **Lambda is regional** — place it in the regional services row (`parent=region`), NOT
  floating inside the VPC.
- **S3 placement** — S3 as a CloudFront static-site origin goes in the **cloud band**.
  S3 as a primary object/document store accessed by EKS/ECS/Lambda goes in the
  **regional services row alongside the compute**. The baseline security row
  (Secrets Manager, CloudWatch, KMS, etc.) is for monitoring/security services only —
  do not bury a primary data store in it. If S3 is the main storage service,
  give it a position that reflects its importance in the architecture. Lambda does not belong in a subnet or as a vpc child unless
  it is a VPC-attached Lambda with a subnet ENI, which must be explicitly modelled.
- **ECR**: every compute cluster (ECS, EKS) in the diagram should have a dashed
  baseline edge to ECR for image pulls — not just one of them.
- **Baseline edges on the arch page**: keep only ECR (pull image) and optionally
  Secrets Manager. Do not draw arch-page arrows to Bedrock, Transcribe, MSK, S3
  from compute lanes — those belong on the flow page. Every baseline edge that
  exits a lane top MUST use horizontal waypoints above the VPC border.
- Connect the load balancer to the **cluster lane border** (not each task).
  Connect the cluster to the **primary database only** (replicas get dashed edges).
- **CloudFront** must be explicitly requested by the user. Never infer CloudFront
  from the presence of S3 or a load balancer. If CloudFront is not in the user's
  spec, do not add it. The phrase "include CF when relevant" has been removed.
  Place **CloudFront** inline with the IGW/ALB row so the inbound path
  `Users → CloudFront → IGW → ALB` is a straight horizontal line.
  S3 (static-site origin) and IAM stay in the top global band (y=70), centre-aligned.

**Environment scope:** Default to a **single environment** (prod only) unless the user
explicitly asks for multi-environment. Do not add Dev/QA/Staging VPCs unless requested.

For the prompt-based workflow, use Kiro's reasoning to create editable Draw.io
XML directly from the requirements and references. Do not run or modify the
Python generator or create project-specific code. A supplied YAML spec is a
topology source, not a required intermediate format. Use MCP tools only when
already configured and useful for AWS fact checks or native Draw.io editing;
never assume an MCP is available.

- **WAF is a global service** — place it in the **cloud band above the region**
  (`parent=cloud`), not in the regional services row and not inside the VPC.
  Same x-column as ALB: `waf_cloud_rel_x = alb_abs_x - cloud_abs_x`.
  WAF cloud-relative y must be < region_cloud_y (285): place at y≈85 (80px above region top).
  Connected vertically to ALB: WAF bottom → ALB top (`exitY=1`, `entryY=0`).
  The WAF→ALB edge crossing the region/VPC is intentional — it shows a global rule applying.
- **Route53** — global service, `parent=cloud`. Placement depends on the inbound path:
  - **When Route 53 is the explicit first hop** (`Users → Route 53 → IGW → ALB`): place it
    inline with the IGW/ALB row, equidistant between the cloud left border and the region left
    border. Formula: `cloud_rel_x = (region_cloud_x - 120) / 2` (≈63 for default scale).
    Route53 abs left=323, gaps to cloud(63px) and region(64px) are equal.
    y = same inline row as IGW/ALB. Do NOT set parent=1 — overlap risk.
    Users must also clear the cloud left border: `users_abs_right + 40 ≤ cloud_abs_x`
    → `users_x ≤ cloud_abs_x - 40 - 120 = 260-40-120 = 100`. Default: Users x=100 ✓
    (users abs_right=220, 40px gap to cloud left=260, 103px gap to Route53 abs_left=323)
  - **When Route 53 is NOT on the drawn inbound path** (`Users → IGW → ALB`): place Route 53
    in the **top global band** (`cloud_rel_y=70`) alongside IAM, S3, etc., using the
    global-band centre formula. An inline Route 53 would sit on the Users→IGW horizontal
    segment and overlap it — this is the source of the Route 53 misplacement bug.
  - **Boundary invariant (both cases):** Route 53 abs-left ≥ cloud_abs_x. Never shift
    Route 53 left to make room for another service; remove the conflicting service instead.

- **No orphan compute icons** — every EC2/ECS/EKS icon must be inside a subnet or lane,
  not floating directly as a VPC child with no container parent.
- **Bastion / jump-box placement** — place management EC2 instances in **AZ1 or AZ3**
  public subnets, never in the middle AZ (AZ2). The middle AZ public subnet sits at the
  same y-level as the ALB→cluster horizontal edge, causing icon/edge crossings.
  AZ1 is preferred (top row, visually clear).

Keep paths semantically correct and visually clear: few essential arrows,
short routes, readable labels, no overlaps, and no arrows running along
container borders. Inspect a rendered preview when available and correct visual
issues before delivery.

- **Flow page service placement**: Use correct AWS container parents.
  Compute a single `spine_abs_yc` from the VPC icon y-centre and derive all
  node y-positions from it — mismatched y-centres create edge bends.
  Regional services (S3, RDS etc.) must be placed right of the VPC right border.
