# Architecture Diagram Conventions

When the user asks to create, draft, or update a cloud **architecture** or
**flow** diagram (draw.io / .drawio.xml), use the `arch-diagram` skill — invoke
`/arch-diagram` or load `.kiro/skills/arch-diagram/SKILL.md`. Do not hand-write
draw.io XML; author a spec and run the generator.

## Stencil Name Validation (CRITICAL)

Before generating any diagram, validate AWS service stencil names against the
authoritative source. **Do not guess stencil names** — incorrect names render as
colored squares instead of icons.

**Authoritative source for AWS stencil names:**
https://github.com/vidanov/aws-architecture-diagram-skill/tree/main/references

Fetch the relevant reference file before using any service:
- `aws-icons-compute.md` - EC2, Lambda, ECS, EKS, Fargate, Batch
- `aws-icons-database.md` - RDS, Aurora, DynamoDB, ElastiCache, Neptune
- `aws-icons-storage.md` - S3, EFS, EBS, FSx, Glacier
- `aws-icons-networking.md` - VPC, ALB, NLB, CloudFront, Route 53, VPN
- `aws-icons-security.md` - IAM, Cognito, KMS, WAF, Shield
- `aws-icons-integration.md` - SQS, SNS, EventBridge, Step Functions, SES
- `aws-icons-analytics-ml.md` - Athena, Glue, SageMaker, Bedrock, Lex
- `aws-icons-iot-migration-devtools.md` - IoT Core, Greengrass, X-Ray, CodePipeline

**Common stencil name corrections** (names differ from service keys):
- EFS: `elastic_file_system` (not `efs`)
- EBS: `elastic_block_store` (not `ebs`)
- DocumentDB: `documentdb_with_mongodb_compatibility`
- MemoryDB: `memorydb_for_redis`
- S3 Glacier: `glacier` (not `s3_glacier`)
- VPN: `vpn_gateway` (not `vpn`)
- X-Ray: `xray` (not `x_ray`)
- SES: `simple_email_service` (not `ses`)
- Lex: `lex` (not `lex_v2`)
- Managed Grafana: `managed_service_for_grafana`

When adding a new service to a diagram, always verify its stencil name from the
authoritative source first.

## Think about the architecture before placing icons

Treat the spec as an architecture model, not a list of every service mentioned
in the request. Before writing it, identify the workload's important actors,
entry points, compute, data stores, integrations, and operational dependencies.
Include a service only when it is part of the requested solution or needed to
explain a key boundary or flow. Do not turn a broad technology inventory, the
DataForge example, or a long list of possible services into one crowded diagram.

For every included component, decide and validate its scope before layout:

- global/account, edge, regional, VPC-level, or AZ/subnet-level;
- whether it is actually deployed in the VPC or only accessed by VPC workloads;
- the appropriate subnet and availability placement when it is VPC-bound;
- whether it belongs with a related group, a separate region/VPC, or a separate
  page to keep the architecture readable.

Never move a component to a different scope just to make the layout work. If the
requested placement is technically invalid or ambiguous, explain the issue and
use the correct placement when it is clear; ask a focused question when the
choice would change the architecture. Do not silently rewrite or discard the
user's spec.

Add an edge only when it communicates a primary traffic path, data movement,
deployment, replication, or an important dependency. Check that each edge's
source and destination match the stated flow and that it does not imply a false
network path. Avoid decorative connections, inferred integrations, and
all-to-all monitoring/security lines. Prefer a small number of clearly labeled
paths over a dense web of arrows.

Before generation, review the proposed component groups, scopes, and key edges
as a coherent design. For dense systems, reduce detail to the requested level or
separate the views into focused pages; do not solve density by shrinking icons,
packing unrelated services together, or routing long lines through the diagram.
After generation, inspect the rendered diagram at normal viewing size. XML
validity and non-overlapping icon boxes are necessary but do not prove that the
architecture or the visual result is clear.

House-style essentials (full detail in the skill's `references/`):

- **Nesting**: AWS Cloud -> Region -> VPC -> Availability Zone -> subnet
  (public / app / db) -> resource icons. Shared services (IAM, CloudWatch, S3,
  KMS) sit at the correct shared scope, outside the VPC when they are not
  deployed in it. Do not treat every service in this list as mandatory for every
  design.
- **Category colors**: compute #ED7100, database #C925D1, networking #8C4FFF,
  storage #7AA116, security #DD344C, management/analytics/integration #E7157B,
  ml #01A88D.
- **Title block** (page 1 only): project name, version, date, creator, reviewer.
- **Providers**: AWS (primary), Azure and GCP starter sets.
- **Deliverable**: a saved `<project>.drawio.xml`, often two pages
  (architecture + flow).

Only use service keys listed in the skill's `references/shapes-<provider>.md`.
