---
name: arch-diagram
description: Generate a draw.io (.drawio.xml) cloud architecture and/or flow diagram from migration requirements, matching the firm's house style (AWS/Azure/GCP icons, nested Cloud/Region/VPC/AZ/subnet grouping, standardized title block). Use when the user asks to create, draft, or update an architecture or flow diagram.
---

# Architecture Diagram Generator

Generate draw.io architecture diagrams that are **aesthetically correct** and
**technically accurate** for cloud migration projects. You author a structured
spec; a Python engine computes layout and routing and emits validated XML.

---

## STEP 1 — Understand the request

Ask or infer (never guess):
- **Cloud provider**: aws (default), azure, gcp.
- **Architecture pattern** (see Pattern Library below).
- **Project metadata**: project name (required), version, date, creator, reviewer.
- **Scale**: how many AZs (default 3 for HA), how many tiers.

---

## STEP 2 — Read the references (load on demand)

| File | When to read |
|------|--------------|
| `references/spec-schema.md` | Before writing any spec |
| `references/shapes-aws.md` | To pick valid `service:` keys |
| `references/shapes-azure.md` / `shapes-gcp.md` | For non-AWS specs |
| `references/house-style.md` | For container hierarchy and colors |

---

## STEP 3 — Apply the Architecture Pattern Library

### 3-Tier Web Application (most common migration pattern)
```
global:    Route53, CloudFront, S3, IAM
edge:      Users (outside cloud), WAF, ALB, IGW
region.services: ACM, Secrets Manager, KMS, GuardDuty, CloudTrail,
                  CloudWatch, CodePipeline, CodeBuild, ECR
vpc:
  azs (×3): public_subnet → NAT (AZ1 only, others empty)
             app_subnet   → [ASG: EC2] [ECS Cluster: Fargate]
             db_subnet    → ElastiCache (left), RDS (right)
  compute_groups: asg (ec2), ecs (fargate)
edges:
  users→waf→alb→ecs (route)
  ecs-az1→cache1 (cache, direct right)
  ecs-az1→rds1   (SQL, bottom-exit, routes below icon row)
  rds1→rds2 (replication, dashed, straight vertical)
  rds1→rds3 (replication, dashed, right corridor for multi-AZ skip)
  ecr→ecs   (deploy, dashed, ECR bottom → ECS cluster top)
```

### Serverless / API-first
```
global:    Route53, CloudFront, S3, IAM
edge:      Users, WAF, API Gateway
region.services: Lambda, DynamoDB, SQS, SNS, CloudWatch, Secrets Manager
(no VPC required unless Lambda needs VPC access)
```

### Microservices / EKS
```
Same as 3-tier but:
  compute_groups: asg (ec2), eks (ec2), ecs (fargate)
  EKS cluster holds EC2 worker nodes
  Add ECR in region services for container registry
```

### Data Pipeline
```
global: S3, IAM
region.services: Glue, Step Functions, Lambda, Athena, QuickSight, CloudWatch
vpc (optional): EMR or Redshift cluster in db_subnet
```

---

## STEP 4 — Service Placement Rules (NEVER violate these)

### Global services (scope: global) — outside the Region box
- **Route 53** — always global (DNS is a global service)
- **CloudFront** — always global (edge network)
- **S3** — global when used for static assets / cross-region
- **IAM** — always global

### Edge services (scope: edge) — left strip inside the Cloud
Order top-to-bottom: `Users` (outside cloud) → `WAF` → `ALB` → `IGW`
- **Users**: outside the cloud boundary
- **WAF**: inside cloud, filters traffic before ALB
- **ALB**: inside cloud, at the **AZ1-AZ2 gap level** (aligned to gap1 mid-y)
  so its connecting line goes cleanly through the AZ gap corridor
- **IGW**: on the left VPC border at AZ1 mid-y

### Region-level services (scope: region.services) — inside Region, outside VPC
Include CI/CD here — CodePipeline, CodeBuild, CodeDeploy, ECR belong in the
region strip, **not** as a separate page or bottom strip.

### VPC subnets — per AZ
- `public_subnet` (green): NAT Gateway in AZ1 only; AZ2/AZ3 public subnets are empty
- `app_subnet` (blue): Usually empty — compute-group lanes overlay it
- `db_subnet` (blue): Place **ElastiCache first (left)**, then **RDS (right)**
  This ordering prevents the SQL connection from crossing the Cache icon

### Compute groups — vertical lanes spanning all 3 AZs
Declare once; engine places one node per AZ. Order matters (left→right):
1. `asg` (Auto Scaling Group) — holds EC2
2. `ecs` (ECS Cluster) — holds Fargate
3. `eks` (EKS Cluster) — holds EC2 worker nodes
Node ids auto-generated as `<group>-<az>` (e.g. `ecs-az1`, `ecs-az2`, `ecs-az3`)

---

## STEP 5 — Edge (connection) semantics rules

### Which connections to declare (and which to omit)
| Connection | Declare? | Pattern |
|---|---|---|
| Users → WAF | yes | `source: users, target: waf` |
| WAF → ALB | yes | `source: waf, target: alb` |
| ALB → ECS cluster | yes | `source: alb, target: ecs` (single edge to cluster boundary) |
| ECS task → RDS (SQL) | yes | `source: ecs-az1, target: rds1` — engine auto-routes below icon row |
| ECS task → Cache | yes | `source: ecs-az1, target: cache1` — direct right |
| RDS primary → RDS replica (same AZ below) | yes | dashed, straight vertical |
| RDS primary → RDS replica (2+ AZs away) | yes | dashed, right corridor |
| ECR → ECS cluster | yes | dashed, enters cluster from top |
| ECS task → S3 (assets) | **no** — S3 access is via NAT/VPC endpoint (structural), not a primary traffic arrow; show it on the Flow Diagram only |
| ALB → each individual Fargate task | **no** — connect to cluster boundary instead |
| Every service to CloudWatch | **no** — CloudWatch is implied; only show if it is a primary data flow |

### Connection routing is automatic
The engine detects:
- **Same AZ row, gap > 2.5×ICON (300px)**: exit top of source → route ABOVE the AZ row (inverted-U) → enter target top (avoids crossing sibling icons)
- **Same AZ row, gap ≤ 300px** (adjacent): direct right side-exit
- **Column-aligned, 1 AZ apart**: straight vertical bottom→top
- **Column-aligned, 2+ AZs apart**: right-side corridor
- **Outside-VPC → VPC container**: corridor spine at ALB's y level
- **Above tall container, offset**: exit bottom → enter container top (ECR→ECS)
- **Dashed edges**: async, deploy, replication flows

---

## STEP 6 — Common mistakes to avoid

1. **Don't put Route53/CloudFront inside the Region** — they are global services.
2. **Don't create one NAT per AZ** — one NAT in AZ1 public subnet; AZ2/AZ3 public subnets stay empty.
3. **Don't connect ALB to individual Fargate tasks** — connect to the ECS cluster boundary (`ecs`); the cluster represents all AZs.
4. **Don't put RDS left of ElastiCache** — Cache must be left, RDS right, or the SQL connection will cross the Cache icon.
5. **Don't add CI/CD as a separate page/tab** — CodePipeline/CodeBuild/ECR go in `region.services`; CI/CD tab is the Flow Diagram.
6. **Don't declare CloudFront in both `global` and `edge`** — pick one; `global` is preferred for CloudFront unless you need a WAF edge-strip ordering.
7. **Don't connect every service to every other service** — only primary traffic flows and key dependencies; monitoring (CloudWatch) and security (GuardDuty) are implied.
8. **Don't declare more than one IGW** — one IGW per VPC.
9. **Don't draw direct edges from compute nodes to global services (S3, CloudFront) on the architecture page** — these are structural access patterns (via NAT/VPC endpoint), not traffic-flow arrows. They belong on the Flow Diagram page only.
10. **Don't draw users → CloudFront on the architecture page.** Users connect to WAF. CloudFront sits in the `global` row for informational/CDN context only. The path User → CloudFront → WAF → ALB is implied; you only need `users → waf` on the diagram.

---

## STEP 7 — Write the spec (show to user for review)

Follow `references/spec-schema.md` exactly. Only use `service:` keys from
`references/shapes-<provider>.md`. Apply the patterns and rules above.

**Spec quality checklist before generating:**
- [ ] Route53 and CloudFront in `global` (not region)
- [ ] Users in `edge` with `service: user` (renders outside cloud)
- [ ] WAF in `edge` before ALB (ordering matters for visual alignment)
- [ ] Single NAT in AZ1 public subnet only
- [ ] ElastiCache declared BEFORE RDS in each db_subnet resources list
- [ ] `alb→ecs` (cluster) NOT `alb→ecs-az1/2/3` (individual tasks)
- [ ] `ecr→ecs` (cluster) NOT individual task targets
- [ ] CI/CD in `region.services`, not a separate section
- [ ] Replication edges are `dashed: true`
- [ ] No duplicate service ids across the whole page

---

## STEP 8 — Generate the diagram

```bash
# Activate venv if not already active
source .venv/bin/activate  # or: .venv/bin/python directly

python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input <project-slug>.spec.yaml \
  --output <project-slug>.drawio.xml
```

The generator will:
1. Validate the spec (reports `error:` and exits 2 on problems)
2. **Run an overlap check** — prints `⚠ OVERLAP:` warnings for any icons/containers
   that geometrically overlap (excluding intentional lane-over-AZ overlaps)
3. Emit validated draw.io XML
4. If `awsdac-mcp-server` is available, also call `generateDiagramToFile` for a
   PNG preview (see Track 3 in README)

### Handling overlap warnings
If the generator reports overlaps:
- Check if two resources in the same subnet are placed too close (increase ICON_GAP)
- Check if the subnet is sized too small for its resources (SUBNET_MIN_W)
- Or adjust the spec to move resources to different tiers/subnets

---

## STEP 9 — Report result

Tell the user:
- The path to `<project-slug>.drawio.xml` (open at https://app.diagrams.net)
- Any overlap warnings from the generator
- A one-line summary: `2 pages (Architecture + Flow), 3 AZs, ECS Fargate + RDS multi-AZ`

---

## Pattern Quick-Reference (for common migration scenarios)

| Customer says | Pattern to use | Key services |
|---|---|---|
| "3-tier web app" | 3-Tier Web | ALB, ECS/Fargate, RDS, ElastiCache |
| "lift-and-shift" | 3-Tier Web | ALB, ASG+EC2, RDS |
| "containerize" | 3-Tier + EKS/ECS | EKS or ECS, ECR, RDS |
| "go serverless" | Serverless | API Gateway, Lambda, DynamoDB |
| "data lake" | Data Pipeline | S3, Glue, Athena, QuickSight |
| "microservices" | Microservices | EKS, ECR, RDS (per service) |
| "multi-region DR" | 3-Tier × 2 regions | Route53 failover, Aurora Global |

---

## Extending the shape catalog

If a service the user needs isn't in the catalog:
1. Add to `_AWS` / `_AZURE` / `_GCP` in `shapes.py`
2. Add matching row to `references/shapes-<provider>.md`
3. Run `pytest` to confirm no drift
