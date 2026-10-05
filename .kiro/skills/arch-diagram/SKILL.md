---
name: arch-diagram
description: Create or update a clear, editable draw.io cloud architecture or flow diagram from a user's requirements.
---

# Architecture diagram workflow

Turn the user's intent into a small, accurate architecture model and generate
an editable `.drawio.xml` using the repository's deterministic renderer. The
spec is the source of truth; do not hand-author diagram XML or hardcode project
specific coordinates.

## 1. Gather requirements

Read the request and existing project files first. Ask one compact set of
focused questions for missing choices that would change the architecture:

- cloud/provider and workload purpose;
- workload purpose and users/entry path;
- compute and data stores;
- regions, availability zones, and resilience needs;
- integrations or important data/deployment flows.

Do not ask for information already supplied. Use sensible defaults only when
the user has stated them or they follow directly from the requested design.
Otherwise ask; do not silently invent components, availability guarantees, or
network paths. Client name, version, date, creator, and reviewer are optional
metadata fields; leave missing values as `To be filled` instead of blocking
diagram generation to collect them.

**Always generate both an architecture page and a flow page** unless the user
explicitly says they only need one. The architecture page shows deployment
boundaries and placement; the flow page shows the primary request or data path
through the system. For most systems the primary flow is the user-facing request
path (e.g. customer → CDN → ALB → compute → database). If the request describes
a data pipeline or background process, use that as the flow instead.

Before generating, summarize the proposed architecture, key connections, and
any assumptions in a few bullets. Keep that review focused; do not make the
user approve routine formatting decisions.

## 2. Model the diagram

Read `references/spec-schema.md` before writing a spec. Read the provider's
shape catalog for valid service keys, and `references/house-style.md` when
choosing hierarchy or visual grouping. Use the supplied examples as visual
references:

- Sadhaka AI for a clean, standard multi-AZ architecture;
- MediaMint for compute lanes and a separate flow page;
- Borderless Access for multi-VPC or enterprise scope.
- `flow diagram examples/Fintech Cloud Flow Diagram.drawio.png` and
  `Docustack Flow Diagram.drawio.png` for process paths and service groupings;
- `flow diagram examples/_Atomberg Data Lake Flow Diagram.drawio.png` for a
  numbered, branching data pipeline.

Select only components needed to explain the requested system. Group them at
their actual scope: global/account, region, VPC, availability zone, subnet, or
compute group. Keep unrelated services out of a crowded inventory. Add an edge
only for an important request/response path, data movement, deployment,
replication, or dependency; avoid decorative and inferred all-to-all links.

Use architecture pages for deployment boundaries and placement. Use flow pages
for ordered processing, branching, and data movement. Split views when one page
would become dense. Follow the provider's actual placement semantics; if a
service's scope or network path is uncertain, check the local catalog/docs or
ask rather than moving it merely to fit the layout. Do not guess icon stencil
names: use the local catalog, and update the catalog only when the user asks
for an unsupported service.

For a flow page, first identify the actor or system that starts each process,
the ordered request/data steps, branches or merges, and the destination. Ask
only for missing details that change the topology or deployment scope. Check
that every arrow points from the real producer/requester to its consumer; an
authorization service validates access and is not a proxy in the application
request path.

Represent a person and their web/mobile/TV client as one external endpoint when
they are the same source and destination of the depicted traffic (for example,
`Viewer / Mobile and TV Player`). Keep separate human and client nodes only
when their interaction matters to the story; stack them together outside AWS,
connect them with a short `uses` relationship, and attach network traffic to
the client. Do not duplicate an endpoint to make response arrows run left to
right. A shared endpoint may send requests/events and receive responses; keep
it at the left edge and show its independent paths on separate rows.

Keep the main path left-to-right, stack independent processes into compact
rows, put branches beside their parent step, and place merges after all inputs.
Use concise labels for payloads or conditions. Place Cognito, S3, and other
services outside the VPC unless the design says they are VPC resources. Keep
external actors outside AWS. Use confirmed flow `groups` for Cloud, Region,
VPC, or cluster boundaries. VPC members share their flow rows in a right-hand
lane so a long lower band does not force avoidable vertical connectors. If
independent journeys would create a crowded page or long crossovers, split them
into focused flow pages and repeat only the shared components needed to explain
each journey. Prefer aligned steps and the shortest clear connector; avoid
extra columns, decorative links, and bends that do not express a branch or
boundary crossing. Flow connectors are solid arrows. The shared orthogonal
router avoids icon and label boxes, spreads edges into separate channels, and
checks the finished routes for conflicts.

Keep architectural paths semantically clean: show CloudFront's origin as a
separate connection when relevant, represent WAF as its own component when it
is part of the request path, and keep the Internet Gateway on the VPC boundary.
For customer ingress diagrams, align Customers → WAF → Internet Gateway → ALB
on one horizontal row when those components are present. Every AWS architecture
page automatically includes IAM, S3, Secrets Manager, CloudWatch, CloudTrail,
and KMS unless the service is already represented in the spec. For shared ECS/EKS services, connect
the cluster boundary to shared data stores; connect individual AZ task nodes
only when the AZ-specific path itself matters.

Before writing the spec, make a short connection inventory from the user's
request. If both architecture and flow pages are requested, cross-check the
primary request and data paths across both views; the architecture page must
show how external users reach the deployed system and how named origins feed
CloudFront. Ask about missing or ambiguous paths rather than silently omitting
them. Connect ALB/API Gateway to the shared ECS/EKS cluster boundary by default;
target an AZ-specific task only when the user describes an AZ-specific route.
After generation, resolve any architecture-connectivity warnings as well as
schema errors before delivery.

For AWS multi-AZ VPC examples, use the existing AZ/subnet/compute-group schema.
One NAT in a shared design is not a universal rule: model the user's stated
resilience and egress requirements. Do not assume every architecture needs a
VPC, three AZs, a CDN, or a WAF. A single flow page is always included (see
section 1); if independent journeys would create a crowded page, focus the flow
on the primary request path.

## 3. Generate

Write `<project-slug>.spec.yaml`, then run:

```bash
.venv/bin/python .kiro/scripts/arch-diagram/generate_diagram.py \
  --strict-connectivity --input <project-slug>.spec.yaml \
  --output <project-slug>.drawio.xml
```

Resolve connectivity errors before delivery; ask the user about any path the
requirements do not establish. Review warnings and the resulting
diagram at normal viewing size when a renderer/preview is available. XML
validity alone does not establish visual quality. If a preview is unavailable,
say so and report the checks actually completed. Keep the output landscape and
readable, with a clear hierarchy, aligned groups, restrained crossings, legible
labels, and a title block populated from available metadata.

## 4. Deliver

Report the spec and draw.io file paths, page types, major scope/availability
choices, and any unresolved assumptions or warnings. Keep the summary concise.
