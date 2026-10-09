# Intermediate Spec Schema (reference only)

> **This schema is not part of the active workflow.**
> The agent generates Draw.io XML directly from user requirements using
> `SKILL.md` and the reference files. No Python generator is used.
> This document is kept as a reference for the house-style layout structure
> and may be useful when describing a topology before generating XML.
> Do not instruct the agent to produce a YAML spec as an intermediate step.

## Layout structure reference

## Top-level structure

```yaml
provider: aws                 # aws | azure | gcp (default provider for services)
metadata:
  client_name: "Example Corp"   # optional; shown as Client Name
  project: "Cloud Migration"   # optional fallback for Client Name
  version: "1.0"              # all fields optional; missing values display as "To be filled"
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

## Flow pages

Flow pages use directed steps, independent of architecture placement. The
renderer lays them out left-to-right with compact, label-safe spacing: branches
occupy separate rows and merges appear after all incoming steps. AWS flow pages
receive an AWS Cloud boundary, with external actors outside it. A shared client
endpoint that both sends and receives traffic stays on the left; a terminal
external destination is placed beyond the cloud. VPC members use a separate
right-hand placement lane, aligned to the connected flow rows so unrelated
Cloud services remain outside the VPC frame without pushing VPC work below the
diagram. Every page gets the branded title header and outer border.

```yaml
- name: "Order Processing"
  type: flow
  nodes:
    - { id: checkout, service: user, label: "Customer checkout" }
    - { id: validate, service: lambda, label: "Validate order" }
    - { id: charge, service: lambda, label: "Charge payment" }
    - { id: reject, service: sns, label: "Notify customer" }
    - { id: fulfill, service: sqs, label: "Start fulfillment" }
  edges:
    - { source: checkout, target: validate }
    - { source: validate, target: charge, label: "valid" }
    - { source: validate, target: reject, label: "invalid" }
    - { source: charge, target: fulfill, label: "payment accepted" }
```

Nodes require unique `id` and `service`; `label`, `provider`, and explicit
`x`/`y` positions are optional. Use `scope: external` for non-AWS endpoints;
`scope: cloud` and `scope: vpc` can clarify placement. Model the same client as
one endpoint when it sends requests/events and receives responses. Edges define
the real producer-to-consumer direction and may include a meaningful `label`.
Flow arrows are rendered solid and use the shared orthogonal router, which
avoids icon and label boxes, spreads shared paths into separate channels, and
checks for conflicts. Prefer describing branch conditions and merge behavior
in the spec over setting coordinates.

Optional `groups` draw named deployment boundaries around flow nodes. Their
frames size themselves to the listed members and render behind the icons.
VPC groups also establish the VPC placement lane to the right of non-VPC AWS
services.

```yaml
groups:
  - id: app_vpc
    kind: vpc
    label: "Application VPC"
    members: [service, database]
```

`kind` uses a known container from the provider's container catalog (for AWS,
`cloud`, `region`, `vpc`, and `cluster` are common choices).

## Placement scopes

Every resource lives in exactly one scope:

| scope | where it renders | examples |
|-------|------------------|----------|
| `global` | account level, above/outside the Region box | CloudFront, Route 53, IAM |
| `edge` | left strip INSIDE the AWS Cloud, left of the Region (Users stay outside) | Users, WAF, ALB, CloudFront |
| region `services` | inside Region, outside any VPC (incl. CI/CD icons and S3 buckets) | S3, ACM, Secrets Manager, GuardDuty, CloudTrail, Lambda, CodePipeline, CodeBuild, ECR |
| AZ `public_subnet` resources | inside a subnet in one AZ | NAT Gateway (typically AZ1 only) |
| AZ `app_subnet` resources | inside the app-subnet band; compute-group lanes overlay it | (usually left to the lanes) |
| AZ `db_subnet` resources | inside a subnet in one AZ | RDS, ElastiCache |
| `compute_groups` node | intersection of a group lane and an AZ row | EC2 (ASG), Fargate (ECS), EC2 worker (EKS) |

Notes matching the house style:
- Model NAT Gateways and public subnet contents according to the requested
  egress, availability, and cost requirements; do not assume one NAT per VPC.
- **Users** render OUTSIDE the AWS Cloud; ingress services render in the
  `edge` scope. Place services at the scope described by the requested design.
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
  - { source: users, target: waf, label: "HTTPS" }
  - { source: waf, target: igw }
  - { source: igw, target: alb }
  - { source: alb, target: ecs, label: "route" }            # shared cluster boundary
  - { source: ecs, target: cache1, label: "cache" }
  - { source: ecs, target: rds1, label: "queries" }
  - { source: ecr, target: ecs, label: "deploy", dashed: true }
```
| field | required | description |
|-------|----------|-------------|
| `source` / `target` | yes | ids of existing elements; `<group>-<az>` targets are for AZ-specific paths |
| `label` | no | edge label |
| `dashed` | no | `true` for async or deploy flows |
| `az_specific` | no | `true` when an edge intentionally targets one ECS/EKS AZ task |
| `style` | no | raw draw.io style override (disables auto-routing) |

Edges are kept separate from the containment structure on purpose: mixing
placement and traffic-flow confuses layout. The engine routes them with
connection points + waypoints so they attach to borders and avoid icons.

## Validation (SpecError raised for)
- invalid `provider`.
- unknown `service` for its provider; unknown compute-group `kind`.
- resource/node missing `id` or `service`.
- duplicate id on a page; edge endpoint referencing a missing id.
- invalid page `type` (must be `architecture` or `flow`).
