# House Style

Conventions the generator follows so diagrams match the firm's decks
(Borderless Access, MediaMint, Sadhaka AI). The architecture layout is a
**grid with overlapping compute-group lanes**.

## The big picture

```
Outer border
├─ AWS Cloud
│  ├─ [global row]   CloudFront · Route 53 · S3 · IAM      (account level, OUTSIDE region)
│  └─ Region (dashed blue)
│     ├─ [region services row]  ACM · Secrets · GuardDuty · CloudTrail · ECR · Lambda ...
│     └─ VPC (green)
│        ├─ AZ rows (horizontal dashed):  az1 / az2 / az3   ← physical placement
│        │    public-subnet (green)  → NAT Gateway
│        │    app tier band           ← the compute lanes cross here
│        │    db-subnet   (blue)      → RDS · ElastiCache · ... (side by side)
│        └─ compute-group lanes (vertical, span ALL AZ rows):  ← logical grouping
│             [ Auto Scaling Group | ECS Cluster | EKS Cluster ]
│             one compute icon per AZ at each lane×row intersection
├─ entry column (left, outside VPC):  Users → WAF → CloudFront → ALB → IGW
└─ CI/CD strip (bottom):  CodePipeline → CodeBuild → ECR → (deploy ↑ into app tier)
```

## The two overlapping boundary systems (app tier)

This is the defining feature of the house style:

- **Horizontal dashed boxes = Availability Zones** (physical). One row per AZ.
- **Vertical boxes = logical compute groups** (ASG dashed-orange, ECS/EKS solid
  orange). Each spans **all** AZ rows.
- **A compute icon sits at every intersection** = that group's instance in that
  AZ. So an ECS Cluster across 3 AZs = 3 Fargate tasks; an ASG = 3 EC2; an EKS
  cluster = 3 EC2 worker nodes.

The vertical lanes are intentionally drawn **over** the AZ rows — this is the one
place the layout overlaps on purpose, because it represents two coordinate
systems (logical grouping × physical zone), not containment.

## Placement scopes

| scope | renders | examples |
|-------|---------|----------|
| global | account level, above the Region | CloudFront, Route 53, S3, IAM |
| edge | left strip INSIDE the cloud (Users stay outside) | Users, WAF, CloudFront, ALB |
| region services | inside Region, outside VPC (incl. CI/CD) | ACM, Secrets, GuardDuty, CloudTrail, CodePipeline, CodeBuild, ECR |
| public_subnet | web/public tier (one NAT for the VPC, in AZ1) | NAT Gateway |
| app_subnet | blue band behind the compute-group lanes | (usually empty) |
| db_subnet | data tier | RDS, ElastiCache |
| compute-group node | lane × AZ intersection | EC2 / Fargate |

Route 53 and CloudFront are **global**. Users render **outside** the cloud; WAF /
CloudFront / ALB render in the **edge** strip inside the cloud. **IGW** sits on the
left VPC border. There is **one NAT Gateway** for the VPC (in AZ1); other public
subnets are empty uniform boxes. **CI/CD** icons live in `region.services`.

## Sizing / aesthetics

- Resource icons are 120×120; labels are bold 18px below the icon.
- **Subnets of the same tier share one width** (uniform). A subnet only widens
  when it holds more resources; resources inside a subnet are laid **left→right**.
- All AZ rows share one height and their subnet columns line up in a grid.
- One ALB / one CloudFront in the entry column — not one per AZ.

## Category colors (AWS 2020 palette)

| category | fill | examples |
|----------|------|----------|
| compute / containers | #ED7100 | EC2, ECS, EKS, Fargate, Lambda, ECR |
| database | #C925D1 | RDS, Aurora, ElastiCache, DynamoDB |
| networking | #8C4FFF | VPC, ALB, NAT, IGW, CloudFront, Route 53 |
| storage | #7AA116 | S3, Backup |
| security | #DD344C | WAF, KMS, IAM, GuardDuty, Security Hub, ACM, Secrets Manager |
| management / analytics / integration | #E7157B | CloudWatch, CloudTrail, Config, SNS, OpenSearch |
| ml | #01A88D | Bedrock, SageMaker, Transcribe, Rekognition, Polly |
| devtools | #C925D1 | CodePipeline, CodeBuild, CodeDeploy |

## Containers

| kind | stencil / style | use |
|------|-----------------|-----|
| cloud | group_aws_cloud_alt, #232F3E | AWS Cloud |
| region | group_region, dashed #147EBA | Region |
| vpc | group_vpc, #248814 | VPC |
| az | group_availability_zone, dashed #545B64 | one per AZ row |
| public_subnet | group_security_group, #248814 / #E9F3E6 | web/public tier |
| db_subnet | group_security_group, #147EBA / #CCE5FF | data tier |
| asg | group_auto_scaling_group, dashed #D86613 | Auto Scaling Group lane |
| ecs_cluster / eks_cluster | orange rectangle | compute-group lane |

## Edges (traffic / flow)

Declared **separately** from placement. Default connector
`edgeStyle=orthogonalEdgeStyle;strokeWidth=3;` with computed connection points
(`exitX/entryX`) + waypoints so arrows attach to borders and route around icons.
Use `dashed: true` for async / deploy / replication flows. Cross-boundary arrows
(ALB fan-out to each AZ, cross-AZ, CI/CD deploy-up) are ordinary edges.

## Title block & pages

- Title block (page 1 only): project, version, date, creator, reviewer.
- Two tabs: **Architecture Diagram** and **Flow Diagram** (CI/CD belongs on the
  flow tab or the architecture CI/CD strip — not a third page).
