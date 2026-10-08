# Architecture Diagram Generator

A Kiro skill that turns cloud migration requirements into editable draw.io
(`.drawio.xml`) architecture and flow diagrams, matching the firm's house style
(AWS 2020 icon set, nested Cloud/Region/VPC/AZ/subnet grouping, standardised
title block). Azure and GCP starter icon sets are included.

Diagrams are authored directly by Kiro's reasoning — no code is run at
generation time. The agent reads the requirements, references, and template,
then writes valid Draw.io XML.

## Repository layout

```
outputs/                         # ← all client work lives here
│   Each subfolder = one client / project.
│   Only the .drawio.xml is committed; PNGs are git-ignored.
│
├── ignosis/
│   └── ignosis.drawio.xml
├── docustack-ai/
│   └── docustack-ai.drawio.xml
└── ...                          # one folder per client

diagram examples/                # reference XMLs and PNGs used during design
flow diagram examples/           # reference flow-page examples

.kiro/
├── agents/
│   └── arch-diagram.json        # dedicated agent configuration
├── skills/arch-diagram/
│   ├── SKILL.md                 # procedure the agent follows
│   └── references/
│       ├── house-style.md       # hierarchy, colours, title block, edges
│       ├── shapes-aws.md        # AWS service catalog
│       ├── shapes-azure.md      # Azure starter catalog
│       ├── shapes-gcp.md        # GCP starter catalog
│       ├── spec-schema.md       # YAML spec format (reference only)
│       └── mcp-options.md       # optional MCP integrations
└── steering/
    └── arch-diagram-conventions.md   # always-on rules + pointer to skill
```

---

## How it works

The agent is steered entirely through Markdown files. When you open the
`arch-diagram` agent and describe a system:

1. Kiro reads the SKILL.md procedure and the reference catalogs.
2. It asks only for missing choices that would change the topology.
3. It reasons about the architecture and builds Draw.io XML directly.
4. The result is saved to `outputs/<project-slug>/<project>.drawio.xml`.

No Python, no intermediate spec, no CLI commands.

---

## Creating a new diagram

Open the `arch-diagram` agent and describe the system:

```
/arch-diagram three-tier web app for Acme Orders — ECS Fargate, Aurora, 3 AZs,
              one NAT Gateway, CloudFront in front of S3 static site
```

Kiro will:
- ask about any topology-changing choices that are missing
- summarise the proposed components and flow
- generate an editable `.drawio.xml` in `outputs/<project-slug>/`

Open the result at <https://app.diagrams.net> or in the draw.io desktop app.

---

## What Kiro produces

Each diagram has exactly two pages:

| Page | Purpose |
|---|---|
| **Architecture** | Deployment scope, network boundaries, AZs, and where services run |
| **Flow** | The primary request, event, or data journey through those services |

Extra pages are only added if explicitly requested.

---

## Visual reference files

`diagram examples/` and `flow diagram examples/` contain real client diagrams
that Kiro uses as visual references:

- `diagram examples/Comprinno Architecture Template.drawio.xml` — the current
  house-style template (page frame, logo, title block, icon style, colours)
- Other XMLs and PNGs — layout references for specific patterns

These are references, not templates. Kiro does not copy their service inventory,
AZ count, or connections.

---

## Reference catalogs

All steering is in `.kiro/skills/arch-diagram/references/`:

| File | Purpose |
|---|---|
| `house-style.md` | Colour palette, boundary hierarchy, edge rules, title block |
| `shapes-aws.md` | AWS icon keys and stencil names |
| `shapes-azure.md` | Azure starter icon catalog |
| `shapes-gcp.md` | GCP starter icon catalog |
| `spec-schema.md` | YAML spec format — used when a spec is supplied as input |
| `mcp-options.md` | How to use optional Draw.io or AWS MCPs |

To add a service to the catalog, add a row to the relevant `shapes-*.md` file.
The stencil naming convention is:
`mxgraph.aws4.<name>` · `mxgraph.azure.<name>` · `mxgraph.gcp2.<name>`

---

## Custom agent setup

For a custom agent that needs access to this skill, add to its config:

```json
{
  "resources": [
    "skill://.kiro/skills/*/SKILL.md",
    "file://.kiro/steering/**/*.md"
  ]
}
```

---

## Design approach

The agent asks only about requirements that affect architecture, models only the
components and connections needed to explain the system, and writes Draw.io XML
directly. Layout decisions (positioning, routing, spacing) are handled by
Kiro's reasoning guided by the house-style rules — not by code.
