# How the Skill Works — Technical Reference

This document describes the end-to-end pipeline that turns a user request into
a draw.io diagram. It covers the agent workflow, spec format, rendering engine,
layout algorithm, and edge routing in enough detail to understand, extend, or
debug the system.

---

## Overview

```
User request
    │
    ▼
Agent (Kiro) ──── reads SKILL.md ────► gathers requirements
    │
    ▼ writes
<project>.spec.yaml          ← structured YAML; the source of truth
    │
    ▼ python generate_diagram.py --input …
┌────────────────────────────────────────────┐
│              Rendering pipeline            │
│                                            │
│  1. validate_spec()                        │
│  2. _fix_regional_placement()              │
│  3. routing.plan_region_service_order()    │
│  4. layout.build()   → Layout object       │
│  5. emit nodes (icons + containers)        │
│  6. route_edges()    → waypoints + ports   │
│  7. find_conflicts() → validation report   │
│  8. render_xml()     → .drawio.xml         │
└────────────────────────────────────────────┘
    │
    ▼
<project>.drawio.xml    (git-ignored, regenerated on demand)
```

No coordinates are hand-authored. Every position, container size, and connector
waypoint is computed deterministically from the spec.

---

## 1. Agent workflow

The agent follows `.kiro/skills/arch-diagram/SKILL.md`:

1. **Gather** — read the request; ask one focused set of questions for choices
   that would change the architecture (provider, compute, AZ count, data tier,
   flows). Do not ask about information already supplied.
2. **Model** — choose components at their correct AWS scope (global, region,
   VPC, AZ, subnet). Only include what is needed to explain the system; avoid
   decorative or speculative services.
3. **Summarise** — present the proposed components and main traffic paths in a
   few bullets before generating. This gives the user a chance to correct scope
   or service choices before rendering.
4. **Write spec** — produce `outputs/<slug>/<project>.spec.yaml`.
5. **Run generator** — `python .kiro/scripts/arch-diagram/generate_diagram.py --input …`
6. **Report** — report the output paths, page types, key assumptions, and any
   remaining routing warnings.

---

## 2. Spec format

The spec is a YAML file consumed by `generate_diagram.py`. Two page types are
supported on the same document.

### Architecture page

```yaml
provider: aws
metadata:
  project: "Acme Orders"
  version: "1.0"
  date: "2026-10-01"
  creator: "Architecture Team"

pages:
  - name: "Architecture Diagram"
    type: architecture

    global:    # Account-level; rendered above the Region box
      - { id: cf, service: cloudfront, label: "CloudFront" }

    edge:      # Ingress strip; Users go outside the cloud, rest inside
      - { id: users, service: users,    label: "Customers" }
      - { id: waf,   service: waf,      label: "WAF" }
      - { id: alb,   service: application_load_balancer }
      - { id: igw,   service: internet_gateway }

    region:
      label: "us-east-1"
      services:            # Inside Region, outside any VPC
        - { id: ecr, service: ecr }

      vpc:
        label: "App VPC"
        azs:
          - id: az1
            public_subnet:  { id: pub1, resources: [ { id: nat1, service: nat_gateway } ] }
            app_subnet:     { id: app1, resources: [] }
            db_subnet:      { id: db1,  resources: [ { id: aurora1, service: aurora } ] }
        compute_groups:
          - { id: ecs, kind: ecs_cluster, node_service: fargate, label: "ECS Fargate" }

    edges:
      - { source: users, target: waf }
      - { source: waf,   target: igw }
      - { source: igw,   target: alb }
      - { source: alb,   target: ecs }
      - { source: ecs,   target: aurora1, label: "SQL" }
      - { source: ecr,   target: ecs, label: "deploy", dashed: true }
```

**Placement scopes** — where a resource renders:

| Scope | Container | Examples |
|---|---|---|
| `global` | Above the Region box | CloudFront, Route 53, S3, IAM |
| `edge` | Left strip inside the Cloud | WAF, ALB, IGW (Users stay outside) |
| `region.services` | Inside Region, outside VPC | ECR, Cognito, Lambda, Secrets Manager |
| `public_subnet` | Web/DMZ tier in an AZ | NAT Gateway, Bastion |
| `app_subnet` | App tier band (usually empty; lanes overlay it) | — |
| `db_subnet` | Data tier in an AZ | Aurora, ElastiCache, RDS |
| `compute_groups` | Vertical lane spanning all AZ rows | Fargate tasks, EC2 workers |

### Flow page

```yaml
  - name: "Order Flow"
    type: flow
    nodes:
      - { id: customer, service: users,   label: "Customer" }
      - { id: api,      service: api_gateway }
      - { id: handler,  service: lambda,  label: "Order Handler" }
      - { id: db,       service: aurora }
    edges:
      - { source: customer, target: api,     label: "POST /order" }
      - { source: api,      target: handler, label: "invoke" }
      - { source: handler,  target: db,      label: "INSERT" }
```

Flow nodes are laid out left-to-right by topological rank. Independent branches
sit in separate rows. External actors (users, IoT devices) stay left; VPC
members sit in a right-hand lane.

---

## 3. Rendering pipeline — module by module

### `generate_diagram.py` — orchestrator

Entry point. `build_document(spec)` calls the sub-steps below and returns an
`ET.Element` (the mxfile). `main()` handles CLI argument parsing, reads the
YAML, calls `build_document`, and writes the XML.

**Architecture page pipeline** (`build_architecture_page`):

```
_fix_regional_placement(page)          # auto-migrate regional services out of VPC subnets
routing.plan_region_service_order(page) # sort region services: VPC-connected go last (nearest VPC)
_check_unique_ids / _validate_services  # spec validation — raises SpecError on bad input
layout.build(page)  →  Layout           # compute all node positions + container sizes
overlap_check(lo)                       # warn on sibling-icon collisions
emit nodes (add_icon / append Cell)     # write every positioned node to the Diagram
route_edges(all_edges, lo)              # compute exit/entry ports + waypoints per edge
find_conflicts(routes, icon_boxes)      # report icon-crossings and edge-edge overlaps
render_xml(mxfile)                      # ET.tostring → UTF-8 XML with declaration
```

**Flow page pipeline** (`build_flow_page`):

```
_flow_layout(nodes, edges, groups)     # topological rank assignment + row packing
emit nodes (add_icon)                  # place each icon at its computed (x, y)
_route_flow_edges(edges, boxes)        # multi-pass obstacle-aware routing
emit edges (add_edge)                  # write connectors with exit/entry fractions + waypoints
```

---

### `layout.py` — grid layout engine

Computes every node's position and every container's size from the spec without
any user-supplied coordinates. The output is a `Layout` object containing:

- `nodes` — flat list of `Node(id, kind, parent, x, y, w, h, service, label)`
- `abs_boxes` — `{id: (abs_x, abs_y, w, h)}` in page coordinates (used by routing)
- `az_gaps`, `az_rows` — AZ gap corridors for edge routing
- `vpc_corridor_x` — left spine x for fan-out routing
- `region_right_x` — right corridor for region→VPC edge detours

**Key decisions made by `layout.build()`:**

1. **Tier widths are uniform across AZs** — all public subnets share the same
   width; same for app and db. This keeps the grid aligned.
2. **AZ row heights are per-AZ** — a row is as tall as its tallest subnet, so
   AZs with more DB resources are taller than sparse ones.
3. **db_subnets use a single-row layout** — icons spread horizontally. Other
   subnet tiers use a 2-column grid.
4. **Ingress gutter** — Shield/WAF sit in a left gutter of the Region box;
   ALB/APIGW sit in a left gutter of the VPC box. Both gutters are sized to
   hold their icons centred and vertically aligned to the middle AZ gap.
5. **Compute-group lanes** — vertical boxes that span all AZ rows, overlaid on
   the app-subnet band. Lane width = `ICON + 2 × 30 px`; height is computed
   from first to last AZ, with a small overhang for the lane label.
6. **Region services** use `REGION_ROW_ICONS = 21` icons per row. Services
   connected to the VPC are pushed to the last row (closest to the VPC) by
   `routing.plan_region_service_order`.

**Spacing tokens** (defined at module top):

```python
ICON = 120           # icon box size
ICON_GAP = 60        # gap between sibling icons
TIER_GAP = 80        # gap between subnet columns inside an AZ
AZ_GAP = 120         # gap between AZ rows
LANE_GAP = 50        # gap between compute-group lane columns
VPC_PAD_X = 65       # VPC left/right internal padding
REGION_PAD_X = 85    # Region left/right internal padding
CLOUD_PAD_X = 85     # Cloud right internal padding
```

All container sizes derive from these tokens, so changing one constant
consistently affects the whole layout.

---

### `routing.py` — edge routing and placement planning

Two responsibilities:

#### 3a. `plan_region_service_order(page)`

Reorders `region.services` in-place before layout runs. Services are scored:

| Score | Meaning | Position |
|---|---|---|
| 0 | No connections | Front (rendered in early rows, far from VPC) |
| 1 | Connected to another region service | Middle |
| 2 | Connected to an APIGW/ALB gutter item (e.g. Lambda) | End (last row, near VPC) |
| 3 | Connected to a VPC element (e.g. ECR→ECS) | Very end |

This ensures Lambda lands in the last row adjacent to the APIGW gutter, and ECR
lands adjacent to the ECS lane — keeping their edges short.

#### 3b. Architecture edge routing

Architecture page edges are routed by the inline case-based router in
`generate_diagram.py` (with `routing.find_conflicts()` for validation):

| Case | Condition | Route strategy |
|---|---|---|
| 1 | Source in ingress band → VPC/tall container | Exit bottom → horizontal waypoint above VPC → enter top |
| 2 | Region service → tall cluster (ECR deploy) | Exit bottom → horizontal at midpoint → enter top |
| 3 | Lane → icon (Sadhaka geometry) | Exit right at bus_y (AZ-gap centre) → horizontal → enter top |
| 4 | Same-row left→right | Straight; or upper/lower band jog if blocked (obstacle-checked) |
| 5 | Fallback | `_route_edge()` with AZ-gap corridors and VPC spine |

The `_seg_hits_resource()` function checks whether a candidate polyline crosses
any resource icon before committing to a path. If it does, the router tries the
next candidate (upper-band jog → lower-band jog → fallback).

#### 3c. Flow edge routing — `_route_flow_edges()`

Multi-pass obstacle-aware router for flow pages:

1. **Topological spanning** — longer edges are routed first (they need more
   space); short backbone runs are treated as pinned.
2. **Shape classification** — each edge is classified "h" (side-to-side) or
   "v" (top-to-bottom) based on whether horizontal distance exceeds vertical
   distance. Edges where dy > dx get "v" to avoid diagonal exits.
3. **Port allocation** — `_plan_flow_ports()` assigns each edge's exit and
   entry to one of five declared anchor fractions (0, 0.25, 0.5, 0.75, 1.0)
   on the icon's border. Ports are snapped to these anchors so arrows attach
   at the icon's declared connection points, not arbitrary positions.
4. **Channel selection** — `_flow_options()` generates candidates (straight →
   upper-band jog → lower-band jog → column-based detour). Each is checked
   against icon obstacles; the lowest-penalty candidate wins.
5. **Rework loop** (up to 3 passes) — edges still crossing icons have their
   shape flipped (h↔v) and are re-routed.
6. **Conflict report** — `routing.find_conflicts()` tallies residual icon
   crossings and edge-edge overlaps and prints them as warnings.

**Key fix (anchor snapping):** Port fractions and path endpoint coordinates are
both snapped to the same icon anchor grid, eliminating the sub-pixel y-mismatch
that previously caused diagonal attachment at icon borders.

---

### `shapes.py` — shape catalog

Single source of truth for every service stencil, colour, and category.
Three dicts: `_AWS`, `_AZURE`, `_GCP`. Lookup function: `get_shape(provider, key)`.

For AWS, any unknown key falls back to `get_shape_dynamic()`, which infers a
stencil name and colour from the key string — so new services work without a
catalog entry. For Azure and GCP, unknown keys raise `UnknownServiceError`.

A test (`test_references.py`) fails the build if `shapes.py` and the
`references/shapes-*.md` markdown catalogs drift apart.

---

## 4. draw.io XML structure

The emitted XML follows draw.io's uncompressed format:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel grid="1" ...>
  <root>
    <mxCell id="0" />                    <!-- required root -->
    <mxCell id="1" parent="0" />         <!-- required default layer -->

    <!-- containers (Cloud, Region, VPC, AZ, subnet, lane) -->
    <mxCell id="cloud" parent="1" value="AWS Cloud" style="points=...;..." vertex="1">
      <mxGeometry x="260" y="250" width="3570" height="3080" as="geometry" />
    </mxCell>

    <!-- resource icons -->
    <mxCell id="ecs" parent="vpc" value="ECS Fargate" style="shape=mxgraph.aws4.ecs;..." vertex="1">
      <mxGeometry x="765" y="80" width="180" height="1215" as="geometry" />
    </mxCell>

    <!-- edges with explicit connection points -->
    <mxCell edge="1" source="alb" target="ecs"
            style="edgeStyle=orthogonalEdgeStyle;exitX=1.0;exitY=0.5;entryX=0.0;entryY=0.5;...">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="1190" y="1610" />
        </Array>
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

Labels are wrapped in HTML (`<font style="font-size:18px;"><b>...</b></font>`) so
draw.io renders them with the house-style font. Edge labels use `label=""` —
spec labels are documentation only and are not rendered on connector lines.

---

## 5. Validation

Three layers of validation run before and after rendering:

| Layer | When | What it checks |
|---|---|---|
| `_check_unique_ids` | Before layout | No duplicate IDs on a page |
| `_validate_services` | Before layout | Every service key is known (or dynamic fallback) |
| `_check_edges` | Before layout | Every edge source/target ID exists |
| `overlap_check(lo)` | After layout | Sibling icons in the same container don't physically overlap |
| `_architecture_connectivity_warnings` | After layout | Ingress path completeness (WAF→IGW, IGW→ALB, actors have entry points) |
| `find_conflicts(routes)` | After routing | Edge-over-icon and edge-over-edge crossings |

Warnings are printed to stdout but do not block output unless `--strict-connectivity`
is passed.

---

## 6. Adding a new service

1. Open `shapes.py` and add an entry to the appropriate dict:
   ```python
   # AWS
   _AWS["my_service"] = ("my_service", "compute", "My Service")
   #                       stencil suffix  category   default label
   ```
2. Add the same row to `references/shapes-aws.md`.
3. Run `pytest` — `test_references.py` will fail if the two are out of sync.

Stencil names follow the draw.io `mxgraph.aws4.<suffix>` convention. Browse
existing entries in `shapes.py` for the pattern.

---

## 7. Testing

```bash
source .venv/bin/activate
pytest                        # 187 tests
pytest -k "layout"            # run a subset
pytest --tb=short -q          # compact output
```

Key test files:

| File | What it covers |
|---|---|
| `test_grid.py` | Architecture page layout: container hierarchy, lane placement, subnet sizing |
| `test_polish.py` | Icon styles, edge stroke widths, label wrapping, routing heuristics |
| `test_overlap.py` | Overlap checker: detects collisions, skips intentional lane-over-AZ overlaps |
| `test_layout_requirements.py` | Regression tests: WAF+ALB side-by-side, external actors outside cloud, Lambda row, boundary containment |
| `test_routing.py` | `plan_region_service_order`: Lambda ends up in last row, ECR at end |
| `test_regional_fix.py` | Auto-migration of regional services out of VPC subnets |
| `test_references.py` | `shapes.py` ↔ `shapes-aws.md` drift; SKILL.md front-matter; house-style container list |
| `test_generate.py` | XML validity, unique IDs, edge references, title block |
| `test_shapes.py` | Shape lookup, style strings, dynamic fallback, unknown service handling |
