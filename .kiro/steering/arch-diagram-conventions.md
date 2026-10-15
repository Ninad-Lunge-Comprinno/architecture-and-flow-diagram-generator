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
- Subnets (relative to AZ): all `h=250`, width by icon count:
  - **1 icon**: `w=300` (public, app, or db — all same for consistency)
  - **2 icons**: `w=380`
  - **With lane**: `app_w = lane_w + 55` (lane exception only)
  - `x` positions: public=35, app=pub_x+pub_w+40, db=app_x+app_w+40
  **Consistency rule:** If all subnets have 1 icon each, they MUST all be w=300.
  Never make app subnet wider "just because it's compute". The old w=650 default
  was wrong — it was for 4+ icons and should never be used for single icons.
- IGW: `x=-60 y=650` (relative to VPC)
- Icon size: always 120×120. Icon y in 250-high subnet: always 65.

**Derived positions — always compute from formulas, never copy from another diagram:**
The specific values below (e.g. CloudFront y=1195, Users y=1445) are **N=3
examples**. For any other AZ count, recompute using the formulas in
`references/coords-cheatsheet.md` — do not reuse these numbers.
- **Users y**: `cloud_y + vpc_cloud_y + igw_vpc_y = 250+545+650 = 1445`
  (With region=container=0, vpc is cloud-relative at y=545, not region-relative.
  Old formula `cloud_y+region_y+vpc_y+igw_y = 250+285+260+650` gives the same result
  for the untrimmed layout only — use the vpc_cloud_y form for trimmed diagrams.)
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
- Use `fontSize=14; spacingLeft=55; align=left; strokeWidth=2` on lane label.
- Badge: 45×45, parented to `vpc`, at `x=lane_x+8, y=88`.
- Two lanes of w=480 each overflow the app column — use w=240 each for dual lanes.
- **Dual-lane task_y — label-clearance offset is conditional:** The precomputed dual
  values (AZ-1=85, AZ-2=545, AZ-3=1005) include a +60 px top offset to prevent the
  lane label from overlapping the first task icon. Apply this offset **only when the
  lane label wraps to two lines** (i.e. label text > ~20 characters at fontSize=14).
  For short labels (≤20 chars, single line), use the standard single-lane values
  (AZ-1=25, AZ-2=485, AZ-3=945) even inside dual lanes. Check: if `lane_w=240` and
  label is "Amazon EKS" (9 chars) — use 25/485/945. If label is "ECS Fargate (App Tier)"
  — use 85/545/1005.

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
- **Baseline services always included** — every diagram gets CloudWatch, CloudTrail,
  KMS (regional row) and IAM (global band) even if user doesn't ask. These are
  essential operational hygiene. Other security services (WAF, Secrets Manager,
  GuardDuty) are optional — only if user requests or architecture requires.
- **Container widths — always check and trim to content:**
  Cloud, Region, VPC, and AZ containers start from the skeleton defaults (AZ w=1640,
  VPC w=2225, Region w=2395, Cloud w=2727). **Always run the right-margin check before
  finalising — do not skip it even when the gap looks acceptable:**
  1. Compute `content_right = rightmost_subnet_x + rightmost_subnet_w` (AZ-relative).
     For a layout with public x=35 w=300, app x=375 w=555, db x=970 w=300: content_right = 1270.
  2. If `AZ_w - content_right > 0.2 × AZ_w` (i.e. dead space > 20%), reduce containers:
     `new_AZ_w = content_right + 40` (40 px right margin), then scale VPC/Region/Cloud
     widths proportionally: multiply each by `new_AZ_w / 1640`. Round to nearest 10.
  3. Example: content_right=1270, new_AZ_w=1310, scale=0.799.
     **Use the validated values below — do NOT recompute with a raw ×0.8 multiplier:**
     AZ: 1310. VPC: 1965. Region: 2310. Cloud: 2620.
     (A raw ×0.8 gives VPC=1780 which is wrong; use the table in coords-cheatsheet.md.)
  The 20% threshold means BizAmica-style layouts (dual lanes, db right-edge at 1270)
  will always be trimmed. The old 40% threshold was too permissive and produced
  visible dead space even when the gap was technically below the limit.
- **Region container — use `container=0` (decorative box) on architecture pages:**
  Three-level nesting (`cloud→region→vpc`) with all containers set to `container=1`
  causes coordinate drift: children of region are relative to region, children of vpc
  are relative to region-relative-vpc, and regional services must be placed with
  compound offsets that are easy to miscalculate. The stable pattern is:
  - `region`: set **`container=0`** — draws the dashed blue Region boundary as a
    non-parent reference box. All children that visually appear inside it are parented
    directly to **`cloud`** instead.
  - `vpc`: parented directly to **`cloud`** (not to region), with absolute cloud-relative
    coordinates. Compute `vpc_cloud_x = region_cloud_x + vpc_region_x` and
    `vpc_cloud_y = region_cloud_y + vpc_region_y`.
  - Regional service icons (CloudWatch, KMS, ECR, etc.): parented to **`cloud`**, placed
    at the visual position inside the region box using cloud-relative coordinates.
  - VPC children (IGW, ALB, subnets, lanes): still parented to **`vpc`** as normal.
  This flattens the hierarchy from three levels to two and eliminates region-relative
  coordinate math entirely. The region box remains visible as a drawn boundary.
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
- **Architecture page edges — minimal set only:**
  - Inbound path: Users → (CloudFront →) IGW → ALB → cluster lane
  - ECR: dashed edge from lane to ECR
  - Database: lane → primary DB, plus dashed replication edges
  - **Nothing else.** SQS, SNS, MSK, S3, Bedrock, Transcribe, Secrets Manager,
    CloudWatch, KMS — all service connections go on the **Flow page only**.
  The Architecture page shows *where services are deployed*, not *how they communicate*.
- Connect the load balancer to the **cluster lane border** (not each task).
  Connect the cluster to the **primary database only** (replicas get dashed edges).
- **Inbound LB-to-tier wiring — state as assumption, never infer as fact:** A cost
  estimate or service inventory lists what LBs exist but does NOT specify which tier
  each fronts. If the source is ambiguous (e.g. both ALB and NLB present but no routing
  description), explicitly state an assumption ("Assumed ALB → app tier, NLB → data tier")
  and ask the user to confirm before drawing the edges. Never pick a wiring silently and
  present it as a fact.
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

- **WAF is a global service** — place it in the **cloud band** (`parent=cloud`) in the
  global icon row at `y=70`, alongside Route53 and IAM. Do NOT place WAF directly above
  ALB with a vertical drop edge on the Architecture page — that edge crosses the region
  row, skims adjacent icons, and creates visual clutter. WAF's association with ALB/CF
  is shown on the **Flow page only** (dashed "inspect" edge from WAF to ALB or CF).
  On the Architecture page, WAF is an icon showing "WAF is provisioned"; no edge needed.
- **Route53** — DNS resolution, NOT a network hop. **Always in the global band** at
  `cloud_rel x=72, y=70`, alongside IAM. Route53 edges belong on the **Flow page only** —
  do NOT draw Users→R53 on the Architecture page.
- **CloudFront** — only if explicitly requested. Inline at `cloud_rel x=72, y=1195`.
  CloudFront IS a network hop (edge cache), so it appears on the Architecture inbound path:
  Users → CloudFront → IGW → ALB.
- **Inbound path on Architecture** — shows network path, not DNS:
  - With CloudFront: Users → CF → IGW → ALB → cluster
  - Without CloudFront: Users → IGW → ALB → cluster
  Route53 is NEVER on the Architecture page inbound path.
- **Internal ALB** — when architecture has both external and internal ALBs:
  - External ALB: vpc-rel `x=160, y=650` (inline with IGW)
  - Internal ALB: place in **AZ-1 or AZ-2 public subnet** (NOT AZ-3)
  - Internal ALB connects from cluster to backend services, not from IGW

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
- **Flow page container guidance — flat layout for complex flows:** When the flow
  involves 6 or more distinct service icons, use a **flat absolute layout**: all nodes
  `parent="1"` with absolute coordinates; containers (`container=0`) drawn as non-parent
  reference boxes only. Three-level nested containers (`f-cloud → f-region → f-vpc`)
  with container-relative child coordinates become brittle at this scale — coordinate
  drift causes nodes to fall outside their intended containers when edited. Reserve
  nested containers (`container=1`) only for simple flows with 4 or fewer icons.
- **Flow page Route53 edge:** When Route53 is shown on the flow page, always draw a
  dashed edge from Route53 **to CloudFront** (or to IGW if no CF) to complete the DNS
  resolution story. The edge `Users → R53` shows the DNS query; the edge `R53 → CF`
  shows the resolved target. Stopping at R53 without connecting it forward leaves the
  flow incomplete. Label the R53→CF edge "resolves to" or leave it unlabelled.
