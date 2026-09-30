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

- cloud/provider and project name;
- workload purpose and users/entry path;
- compute and data stores;
- regions, availability zones, and resilience needs;
- integrations or important data/deployment flows;
- whether the user needs an architecture view, a flow view, or both.

Do not ask for information already supplied. Use sensible defaults only when
the user has stated them or they follow directly from the requested design.
Otherwise ask; do not silently invent components, availability guarantees, or
network paths. Version, date, creator, and reviewer are optional metadata.

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

Keep architectural paths semantically clean: show CloudFront's origin as a
separate connection when relevant, represent WAF as its own component when it
is part of the request path, and keep the Internet Gateway on the VPC boundary.
For customer ingress diagrams, align Customers → WAF → Internet Gateway → ALB
on one horizontal row when those components are present. Every AWS architecture
page automatically includes IAM, S3, Secrets Manager, CloudWatch, CloudTrail,
and KMS unless the service is already represented in the spec. For shared ECS/EKS services, connect
the cluster boundary to shared data stores; connect individual AZ task nodes
only when the AZ-specific path itself matters.

For AWS multi-AZ VPC examples, use the existing AZ/subnet/compute-group schema.
One NAT in a shared design is not a universal rule: model the user's stated
resilience and egress requirements. Do not assume every architecture needs a
VPC, three AZs, a CDN, a WAF, CI/CD, or a flow page.

## 3. Generate

Write `<project-slug>.spec.yaml`, then run:

```bash
.venv/bin/python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input <project-slug>.spec.yaml \
  --output <project-slug>.drawio.xml
```

Resolve validation errors before delivery. Review warnings and the resulting
diagram at normal viewing size when a renderer/preview is available. XML
validity alone does not establish visual quality. If a preview is unavailable,
say so and report the checks actually completed. Keep the output landscape and
readable, with a clear hierarchy, aligned groups, restrained crossings, legible
labels, and a title block populated from available metadata.

## 4. Deliver

Report the spec and draw.io file paths, page types, major scope/availability
choices, and any unresolved assumptions or warnings. Keep the summary concise.
