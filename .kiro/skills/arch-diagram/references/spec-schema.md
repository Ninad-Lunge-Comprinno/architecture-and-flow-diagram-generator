# Intermediate Spec Schema (grid layout)

The generator (`generate_diagram.py`) consumes a YAML/JSON spec and emits a
`.drawio.xml` file. This schema describes the firm's house-style layout, which
is a **grid with overlapping compute-group lanes** (see `house-style.md`).

The agent authors this spec from the user's requirements, the user reviews it,
then the generator renders it deterministically.

## Top-level structure

```yaml
provider: aws                 # aws | azure | gcp (default provider for services)
metadata:
  project: "Acme Migration"   # required (title block)
  version: "1.0"
  date: "2026-09-22"
  creator: "Your Name"
  reviewer: "Reviewer Name"

pages:
  - name: "Architecture Diagram"
    type: architecture
    global:   [ ... ]         # account-level services (OUTSIDE the region)
    edge:     [ ... ]         # left strip: Users (outside cloud), WAF, CloudFront, ALB, IGW
    region:
      label: "ap-south-1"
      services: [ ... ]       # region-shared services incl. CI/CD (CodePipeline, CodeBuild, ECR)
      vpc:
        label: "Lumen VPC"
        azs:       [ ... ]    # one block per AZ: public_subnet, app_subnet, db_subnet
        compute_groups: [ ... ]  # vertical lanes spanning ALL AZ rows (overlay app-subnets)
    edges:    [ ... ]         # traffic / flow arrows (declared SEPARATELY from placement)

  - name: "Flow Diagram"
    type: flow
    nodes: [ ... ]
    edges: [ ... ]
```

Single architecture page shorthand: put `global`/`edge`/`region`/`edges` at the
top level and omit `pages`.

## Placement scopes

Every resource lives in exactly one scope:

| scope | where it renders | examples |
|-------|------------------|----------|
| `global` | account level, above/outside the Region box | CloudFront, Route 53, S3, IAM |
| `edge` | left strip INSIDE the AWS Cloud, left of the Region (Users stay outside) | Users, WAF, ALB, CloudFront |
| region `services` | inside Region, outside any VPC (incl. CI/CD icons) | ACM, Secrets Manager, GuardDuty, CloudTrail, Lambda, CodePipeline, CodeBuild, ECR |
| AZ `public_subnet` resources | inside a subnet in one AZ | NAT Gateway (typically AZ1 only) |
| AZ `app_subnet` resources | inside the app-subnet band; compute-group lanes overlay it | (usually left to the lanes) |
| AZ `db_subnet` resources | inside a subnet in one AZ | RDS, ElastiCache |
| `compute_groups` node | intersection of a group lane and an AZ row | EC2 (ASG), Fargate (ECS), EC2 worker (EKS) |

Notes matching the house style:
- **One NAT Gateway** for the VPC (put it in AZ1's `public_subnet`); other public
  subnets render as empty uniform boxes.
- **Users** render OUTSIDE the AWS Cloud; **WAF / ALB / CloudFront** render in the
  `edge` strip inside the cloud. **ALB sits outside the subnets but within the VPC
  region** conceptually and fans out to all AZs (declare edges alb -> each AZ node).
- **IGW** is drawn on the left VPC border automatically when an `internet_gateway`
  resource is in the `edge` list.
- **CI/CD** icons (CodePipeline, CodeBuild, ECR) go in `region.services` — there is
  no separate bottom strip.

## Resource entry (used in global / entry / services / subnet resources)

```yaml
- { id: r53, service: route_53, label: "Route 53" }
```
| field | required | description |
|-------|----------|-------------|
| `id` | yes | unique across the page (edges reference it) |
| `service` | yes | key from `references/shapes-<provider>.md` |
| `label` | no | override default label |
| `provider` | no | override page provider |

## Availability Zones + subnets

Each AZ repeats the same subnet pattern. The engine sizes all subnets of the
same tier **uniformly** (a subnet only widens when it holds more resources).
Resources inside a subnet are laid **left-to-right**.

```yaml
azs:
  - id: az1
    label: "Availability Zone 1"
    public_subnet:
      id: pub1
      label: "public-subnet-1"
      resources: [ { id: nat1, service: nat_gateway } ]   # single NAT for the VPC
    app_subnet:
      id: app1
      label: "app-subnet-1"
      resources: [ ]        # usually empty; the compute-group lanes overlay this band
    db_subnet:
      id: data1
      label: "db-subnet-1"
      resources:
        - { id: rds1, service: rds, label: "RDS PostgreSQL" }
        - { id: cache1, service: elasticache, label: "ElastiCache" }
  - id: az2
    ...
  - id: az3
    ...
```

The **app-subnet** is a real blue container per AZ. The `compute_groups` lanes
(below) are drawn **over** the app-subnets, extending slightly above/below —
this is the intentional dual-boundary overlay (see `house-style.md`).

## Compute groups (vertical lanes spanning all AZ rows)

Declared **once**. The engine draws each as a vertical box crossing every AZ
row (logical grouping for HA) and places **one node per AZ** at the intersection
(physical placement). Node ids are `"<group_id>-<az_id>"` for use in edges.

```yaml
compute_groups:
  - { id: asg, kind: asg,         node_service: ec2,      label: "Auto Scaling Group" }
  - { id: ecs, kind: ecs_cluster, node_service: fargate,  label: "ECS Cluster" }
  - { id: eks, kind: eks_cluster, node_service: ec2,      label: "EKS Cluster" }
```
| field | required | description |
|-------|----------|-------------|
| `id` | yes | group id (node ids become `<id>-<az_id>`) |
| `kind` | yes | `asg` \| `ecs_cluster` \| `eks_cluster` \| `cluster` |
| `node_service` | yes | service placed once per AZ (e.g. `ec2`, `fargate`) |
| `label` | no | group label |
| `azs` | no | subset of AZ ids to span (default: all AZs) |

Column order in the app tier follows the `compute_groups` list order.

## Edge strip (left, inside the Cloud)

```yaml
edge:
  - { id: users, service: user, label: "Users" }       # rendered OUTSIDE the cloud
  - { id: waf, service: waf }                           # inside cloud, left strip
  - { id: cf_edge, service: cloudfront, label: "CloudFront" }
  - { id: alb, service: application_load_balancer, label: "ALB" }
  - { id: igw, service: internet_gateway, label: "IGW" } # drawn on the left VPC border
```
`edge` renders as a vertical strip on the left. A `user` service renders just
outside the cloud; the rest render inside the cloud to the left of the Region.
An `internet_gateway` here is placed on the left VPC border.

CI/CD icons are NOT a separate section — put CodePipeline / CodeBuild / ECR in
`region.services`.

## Edges (traffic / flow — declared separately from placement)

```yaml
edges:
  - { source: alb, target: ecs-az1, label: "route" }        # entry -> compute intersection
  - { source: ecs-az1, target: eks-az2, label: "internal" } # cross-AZ
  - { source: rds1, target: rds2, label: "replication", dashed: true }
  - { source: ecr, target: ecs-az1, label: "deploy", dashed: true }  # CI/CD deploy-up
```
| field | required | description |
|-------|----------|-------------|
| `source` / `target` | yes | ids of existing elements (incl. `<group>-<az>` nodes) |
| `label` | no | edge label |
| `dashed` | no | `true` for async/deploy/replication flows |
| `style` | no | raw draw.io style override (disables auto-routing) |

Edges are kept separate from the containment structure on purpose: mixing
placement and traffic-flow confuses layout. The engine routes them with
connection points + waypoints so they attach to borders and avoid icons.

## Validation (SpecError raised for)
- missing `metadata.project`; invalid `provider`.
- unknown `service` for its provider; unknown compute-group `kind`.
- resource/node missing `id` or `service`.
- duplicate id on a page; edge endpoint referencing a missing id.
- invalid page `type` (must be `architecture` or `flow`).
