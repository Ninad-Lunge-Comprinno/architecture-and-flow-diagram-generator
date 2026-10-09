# How the Skill Works — Technical Reference

This document describes the end-to-end approach that turns a user request into a
draw.io diagram. The project has no code: diagrams are authored directly by
Kiro's reasoning, guided by Markdown steering files and visual references. This
document covers the agent workflow, the house-style rules the agent applies, the
emitted draw.io XML structure, and how the agent self-checks its output.

---

## Overview

```
User request
    │
    ▼
Agent (Kiro) ── reads SKILL.md + references + template ──► gathers requirements
    │
    ▼ reasons about scope, components, placement, flow
    │
    ▼ writes draw.io XML directly (no code, no intermediate spec)
<project>.drawio.xml      ← one Architecture page + one Flow page
    │
    ▼ (optional) rendered preview inspected and corrected
delivered to outputs/<slug>/
```

There is no rendering engine, no layout algorithm, and no routing module. Every
coordinate, container size, and connector waypoint is reasoned out by the agent
from the house-style constants documented in the reference files and applied
directly in the XML it writes.

---

## 1. Agent workflow

The agent follows `.kiro/skills/arch-diagram/SKILL.md`:

1. **Gather** — read the request; ask one focused set of questions only for
   choices that would change the architecture (provider, compute, AZ count, data
   tier, flows). Do not ask about information already supplied.
2. **Model** — choose components at their correct AWS scope (global, region,
   VPC, AZ, subnet). Only include what is needed to explain the system; avoid
   decorative or speculative services.
3. **Summarise** — present the proposed components and main traffic paths in a
   few bullets before generating. This gives the user a chance to correct scope
   or service choices before the diagram is written.
4. **Author XML** — write `outputs/<slug>/<project>.drawio.xml` directly, using
   the geometry constants and placement rules from the references.
5. **Self-check and report** — verify boundary containment, alignment, and edge
   routing against the house-style rules; inspect a rendered preview when one is
   available; then report the output path, page types, and key assumptions.

A supplied `.spec.yaml` is treated as an optional topology **source** describing
what to draw — it is not a required intermediate format and is not consumed by
any generator.

---

## 2. Inputs the agent reads

Rather than running code, the agent grounds its output in these authoritative
sources (most authoritative first):

| Source | Role |
|---|---|
| `diagram examples/Comprinno Architecture Template.drawio.xml` | House-style template — geometry, styles, title block, logo |
| `outputs/ignosis/ignosis.drawio.xml` | Validated working output using the nested-container coordinate system |
| `.kiro/skills/arch-diagram/references/house-style.md` | Hierarchy, container styles, colours, edge rules, scaling guidance |
| `.kiro/skills/arch-diagram/references/coords-cheatsheet.md` | Formulas and constants for every position |
| `.kiro/skills/arch-diagram/references/skeleton-3az.drawio.xml` | Starting skeleton for the default 3-AZ three-tier layout |
| `.kiro/skills/arch-diagram/references/shapes-*.md` | AWS / Azure / GCP stencil catalogs |
| `.kiro/steering/arch-diagram-conventions.md` | Always-on rules and common failure corrections |

Treat the template's example topology, AZ count, service inventory, and
connections as non-defaults — only its visual structure is reused.

---

## 3. Placement scopes

Where each service renders is decided by its AWS scope. The agent places icons
into the correct container parent:

| Scope | Container | Examples |
|---|---|---|
| Global | Cloud band above the Region box | CloudFront, Route 53, WAF, S3, IAM |
| Ingress band | Inline IGW/ALB row inside the Cloud | IGW, ALB (Users stay outside the cloud) |
| Region services | Inside Region, outside any VPC | ECR, Cognito, Lambda, Secrets Manager |
| Public subnet | Web/DMZ tier in an AZ | NAT Gateway, Bastion |
| App subnet | App tier band (lanes overlay it) | — |
| DB subnet | Data tier in an AZ | Aurora, ElastiCache, RDS |
| Compute lanes | Vertical lane spanning all AZ rows | Fargate tasks, EC2 workers, EKS/ECS |

Key placement rules the agent enforces (from the conventions file):

- **Lambda is regional** — placed in the regional services row, not inside a VPC
  subnet (unless a VPC-attached Lambda with a subnet ENI is explicitly modelled).
- **WAF and Route 53 are global** — placed in the cloud band above the region.
- **CloudFront** sits inline with the IGW/ALB row so the inbound path
  `Users → CloudFront → IGW → ALB` is a straight horizontal line.
- Every compute cluster (ECS, EKS) gets a dashed baseline edge to **ECR** for
  image pulls.

---

## 4. Geometry — reasoned, not computed by code

The agent applies fixed house-style constants and derives positions with the
formulas in `coords-cheatsheet.md` and the conventions file. These are applied
by hand in the XML, not produced by a layout engine. The core constants:

- **Canvas border**: `x=0 y=-40 w=3100 h=2600; strokeWidth=3`
- **Cloud**: `x=260 y=250 w=2727 h=2115`
- **Region** (rel. to cloud): `x=247 y=285 w=2395 h=1745`
- **VPC** (rel. to region): `x=85 y=260 w=2225 h=1405`
- **AZ rows** (rel. to VPC): `y=80 / 540 / 1000; h=340; spacing=460`
- **Subnets** (rel. to AZ): public `x=35 w=380 h=250`; app `w=650`; db `w=300`
- **Icon size**: always 120×120; icon y in a 250-high subnet is always 65

Derived positions (users y, CloudFront y, regional icon x spread, lane heights,
cluster→DB exit fractions) are computed from the documented formulas each time
rather than copied from another diagram. Default layout is a 3-AZ three-tier,
single prod environment unless the user specifies otherwise.

---

## 5. draw.io XML structure

The agent emits draw.io's uncompressed format directly:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel grid="1" ...>
  <root>
    <mxCell id="0" />                    <!-- required root -->
    <mxCell id="1" parent="0" />         <!-- required default layer -->

    <!-- containers (Cloud, Region, VPC, AZ, subnet, lane) -->
    <mxCell id="cloud" parent="1" value="AWS Cloud" style="points=...;..." vertex="1">
      <mxGeometry x="260" y="250" width="2727" height="2115" as="geometry" />
    </mxCell>

    <!-- resource icons -->
    <mxCell id="ecs" parent="vpc" value="ECS Fargate" style="shape=mxgraph.aws4.ecs;..." vertex="1">
      <mxGeometry x="765" y="80" width="120" height="120" as="geometry" />
    </mxCell>

    <!-- edges with explicit connection points -->
    <mxCell edge="1" source="alb" target="ecs"
            style="edgeStyle=orthogonalEdgeStyle;exitX=1;exitY=0.5;entryX=0;entryY=0.5;...">
      <mxGeometry relative="1" as="geometry">
        <Array as="points"><mxPoint x="1190" y="1505" /></Array>
      </mxGeometry>
    </mxCell>
  </root>
</mxGraphModel>
```

**Key XML properties:**

| Property | Purpose |
|---|---|
| `parent` | Container hierarchy — icons are children of their subnet/lane/region |
| `exitX/exitY` | Connection point fraction on source icon border (enforces 90° exit) |
| `entryX/entryY` | Connection point fraction on target icon border (enforces 90° entry) |
| `Array as="points"` | Intermediate waypoints for multi-bend paths |
| `style="..."` | Full draw.io style string including stencil, colour, and label position |

Edge routing rules the agent applies (from the conventions file):

- **Inbound path** `Users → CF → IGW → ALB`: all share the same absolute
  y-centre; `exitX=1 exitY=0.5, entryX=0 entryY=0.5`, no waypoints.
- **Cluster → DB**: `exitY` is a computed fraction so the edge exits at the DB's
  y-centre and runs straight horizontally.
- **Baseline edges** (ECR, Secrets): source the lane border, not a task icon.
- **All edges** use `parent="1"` (root).

---

## 6. Stencils

Stencil names follow the draw.io `mxgraph.aws4.<name>` convention
(`mxgraph.azure.<name>`, `mxgraph.gcp2.<name>` for the other providers). The
agent never guesses a stencil name — it verifies each one against
`references/shapes-*.md` before use. Common corrections to watch for:
`elastic_container_service` → `ecs`, `elastic_kubernetes_service` → `eks`,
`certificate_manager` → `certificate_manager_3`.

To add a service, add a row to the relevant `shapes-*.md` catalog.

---

## 7. Self-checks before delivery

There is no automated test suite. The agent validates its own output against the
house-style rules before delivering:

| Check | What it confirms |
|---|---|
| Boundary containment | Every icon sits fully inside its declared container |
| Column alignment | Subnet widths are identical across AZ rows so columns line up |
| Scope correctness | Lambda regional, WAF/Route 53 global, CloudFront inline with IGW/ALB |
| Edge geometry | Inbound path is a straight horizontal line; no arrows run along borders |
| Stencil validity | Every `shape=` key exists in the shape catalog |
| Visual review | A rendered preview is inspected and corrected when one is available |

Deliverables are one editable `.drawio.xml` with one Architecture page and one
primary Flow page; extra flow pages are added only when requested.
