# Architecture diagram conventions

For architecture requests, use `.kiro/skills/arch-diagram/SKILL.md`. Let Kiro reason about the requirements, ask
only topology-changing questions, and keep the user-facing workflow prompt based. The normal deliverable is one
editable Draw.io file with one architecture page and one primary flow page; do not add extra flows unless requested.

**Source precedence (most authoritative first):**
1. `references/coords-cheatsheet.md` — **the only source for geometry numbers** (constants, formulas, presets).
   This file deliberately contains no coordinates: if a number here ever disagrees with the cheatsheet, the
   cheatsheet wins and this file has a bug.
2. `references/skeleton-3az.drawio.xml` — ready-made blank 3-AZ architecture (preset D1). Copy it; fill in the
   topology. Never build containers from scratch.
3. `references/house-style.md` — style strings and layout rules.
4. `diagram examples/Comprinno Architecture Template.drawio.xml` — visual style reference only. Do not copy its
   coordinates, topology, AZ count, service inventory or metadata.

Any recent validated output in `outputs/` can serve as a local reference (untracked, not in the repo).

## Quality gate

After saving a diagram run `python3 .kiro/scripts/validate-drawio.py outputs/<project>/<file>.drawio.xml`, fix
every issue and re-run until it prints `PASS`, and paste the **raw output** in the delivery summary. The validator
enforces the wrap rule, centred rows, subnet columns, lane gaps, straight edges, scope boxes, stencil names and the
flat Flow layout. Use `--allow scenario-b` only for a known false positive (Scenario B-VPC with Public IPv4 /
Data Transfer lines the validator cannot see) and name the reason in the summary. Never edit the validator to
make a diagram pass.

## Layout rules that commonly fail

- **Numbers come from formulas and presets, never from memory or another diagram.** Containers always wrap their
  content (wrap rule), rows are re-centred after every add/delete, subnet columns are `public | app | db` with 40px
  gaps, and a cluster lane sits inside the app-subnet column (35px left / 20px right, `app_w = lane_w + 55`). All
  of it is in the cheatsheet; the skeleton already satisfies it for its layout.
- **Hierarchy is nested; scope is the parent chain:** `cloud → region → vpc → az → subnet → icon`. Regional
  services are `parent=region`, global services `parent=cloud`, VPC-bound resources live in subnets. Do not
  flatten it. Every edge is `parent="1"`.
- **Stencil names — always verify in `references/shapes-aws.md`.** Never guess. Known blank-box traps:
  `elastic_container_service` → `ecs`, `elastic_kubernetes_service` → `eks`, `certificate_manager` →
  `certificate_manager_3`, `cloudwatch` → `cloudwatch_2`.
- **Common wrong values** are listed in the cheatsheet ("Common mistakes"); consult it instead of memory.
- Default to a **3-AZ** three-tier layout unless the user specifies otherwise (other N: cheatsheet N-AZ formulas).
- **Baseline services are always included:** CloudWatch, CloudTrail, KMS (regional row) and IAM (global band), even
  if the user doesn't ask. Other security services (WAF, Secrets Manager, GuardDuty) are optional — only if
  requested or required by the architecture.
- **Size each subnet to its content** and keep dimensions identical across AZ rows. Lane as only content:
  `w = lane_w + 55`. Direct icons: by icon count. Never use the old fixed w=650.
- **Logo:** copy the `brand` cell from the skeleton verbatim. Never re-encode a logo from a local path or reuse a
  stale/truncated blob; keep `strokeColor=none` on the logo cell.
- **Cluster lanes:** lane label style, badge and task rules are in the cheatsheet. Tasks are children of the lane.
  Dual-lane `task_y` gets the +60 label-clearance offset only when the lane label wraps (cheatsheet).
- **Lambda is regional:** place it in the regional services row (`parent=region`). Only a VPC-attached Lambda
  (explicitly modelled, with its subnet ENI) belongs in a subnet.
- **No orphan compute icons:** every EC2/ECS/EKS icon sits inside a subnet or lane, never floating as a VPC child.
- **S3 placement:** S3 as a CloudFront static-site origin goes in the global band. S3 as the primary
  object/document store used by EKS/ECS/Lambda goes in the regional row beside the compute, positioned to reflect
  its importance. The baseline row is for monitoring/security services only.
- **ECR:** every ECS/EKS lane has a dashed `pull image` edge to ECR.
- **Bastion / jump boxes:** AZ1 (preferred) or AZ3 public subnets, never AZ2 (its public subnet shares the y-level of
  the ALB→cluster edge).
- **Internal ALB:** the external ALB stays inline with the IGW row; an internal ALB goes in the AZ1 or AZ2 public
  subnet (not AZ3) and connects from the cluster to backend services, not from the IGW.
- **CloudFront** only if the user explicitly asks; never infer it from S3 or a load balancer. It is a network hop:
  inline with the IGW/ALB row so `Users → CloudFront → IGW → ALB` is one straight horizontal line.
- **Route 53** is DNS, not a hop: always the global band, never inline, never an edge on the Architecture page.
- **WAF follows what it protects** (AWS WAF is regional except when attached to CloudFront): fronting CloudFront →
  global band; fronting an ALB → regional row. No WAF edge on the Architecture page; the association is a
  dashed "inspect" edge on the Flow page.
- **Environment scope:** a single environment (prod only) unless the user explicitly asks for more.

## Edges

- **Architecture page — minimal set only:** inbound path (Users → [CloudFront →] IGW → ALB → lane), ECR (dashed,
  lane → ECR), database (lane → primary DB, dashed replication). **Nothing else:** SQS, SNS, MSK, S3, Bedrock,
  Transcribe, Secrets Manager, CloudWatch, KMS and all service-to-service calls go on the Flow page. The
  Architecture page shows where services are deployed, not how they communicate.
- Connect the load balancer to the **lane border**, not to each task, and the cluster to the **primary database only**.
- **Straight edges:** nodes joined by a horizontal edge share the identical y-centre; lane → DB `exitY` uses three
  decimals (the validator fails any jog over 2px).
- **Inbound path without CloudFront:** `Users → IGW → ALB`, straight, no waypoints. No global-band icon may sit on
  that line; keep global icons in the band.
- Baseline edges (ECR, Secrets) source the **lane border**, never a task icon; waypoints per the cheatsheet.
- Few essential arrows, short routes, no overlaps, no arrows along container borders. Inspect a rendered preview
  when one is available (CI uploads a skeleton render); otherwise state that no rendering was performed.

## Flow page

- **Flat layout:** every node and edge is `parent="1"` with absolute coordinates; the Cloud / Region / VPC boxes
  are decorative (`container=0`). Each node must sit in the box that matches its AWS scope (cheatsheet scope map).
  VPC-bound services (RDS, Aurora, DocumentDB, MSK, ElastiCache, compute, ALB) are in the VPC box on both pages.
- One spine y for all main-path nodes (identical y-centres, otherwise the router adds a bend); pitch and slots are in
  the cheatsheet. Regional services sit right of the VPC border.
- **Route 53 on the Flow page:** `Users → Route 53` (DNS query), then Route 53 → the **public endpoint it resolves
  to** — CloudFront, otherwise the ALB. Never the IGW (an IGW is not a DNS target). Leave the edge unlabelled or
  use "resolves to".

## Sources: cost estimates and migration sheets

- A cost estimate or service inventory is **not a wiring diagram**. State the inferred data/request path as an
  assumption; if load balancers are ambiguous (e.g. ALB and NLB, no routing description) write the assumption
  ("Assumed ALB → app tier, NLB → data tier") and ask the user to confirm before drawing the edges.
- **Read every group before building.** One workload can be split across several top-level groups; AI/ML,
  monitoring and networking lines often live only in a secondary group. Enumerate the union of services, then diff
  the final icon set against it: every service is drawn or skipped with a stated reason (EBS via its host; Public
  IPv4 / Data Transfer as billing-only lines). Omission produces no validator error — this diff is the only guard.
- Model the **AWS target** service (the `Service Name` field), not the Azure/external name in a description; map a
  non-AWS line (e.g. "OpenAI/GPT") to its AWS-native stand-in (Amazon Bedrock) and note the substitution.

## Workflow

For the prompt-based workflow, use Kiro's reasoning to create editable Draw.io XML directly from the requirements
and references. There is no generator: the only script is `validate-drawio.py` (plus its regression test). A
supplied YAML spec is a topology source, not a required intermediate format. Use MCP tools only when already
configured and useful for AWS fact checks or native Draw.io editing; never assume an MCP is available.
