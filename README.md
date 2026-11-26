# Architecture Diagram Generator

A Kiro skill that turns cloud migration requirements into editable draw.io
(`.drawio.xml`) architecture and flow diagrams, matching the firm's house style
(AWS 2020 icon set, nested Cloud/Region/VPC/AZ/subnet grouping, standardised
title block). Azure and GCP starter icon sets are included.

Diagrams are authored directly by Kiro's reasoning — no code is run at
generation time. The agent reads the requirements, references, and template,
then writes valid Draw.io XML.

**Validation:** A Python validator (`.kiro/scripts/validate-drawio.py`) checks
generated diagrams for structural issues. The agent runs it automatically as the
last step of its workflow (step 8 in SKILL.md), and CI runs it on every push.
To run it manually:
```bash
python3 .kiro/scripts/validate-drawio.py outputs/<project>/<project>.drawio.xml
```

## Repository layout

```
outputs/                         # ← all client work lives here (git-ignored)
│   Each subfolder = one client / project.
│   Generated XMLs are NOT committed; work is shared out-of-band.
│
└── <project-slug>/
    └── <project>.drawio.xml     # produced by the agent

diagram examples/                # reference XMLs and PNGs used during design
flow diagram examples/           # reference flow-page examples

.kiro/
├── agents/
│   └── arch-diagram.json        # dedicated agent configuration
├── skills/arch-diagram/
│   ├── SKILL.md                 # procedure the agent follows
│   └── references/
│       ├── coords-cheatsheet.md # geometry constants — single source of truth for all coordinates
│       ├── house-style.md       # hierarchy, colours, title block, edges
│       ├── shapes-aws.md        # AWS service catalog
│       ├── shapes-azure.md      # Azure starter catalog
│       ├── shapes-gcp.md        # GCP starter catalog
│       ├── mcp-options.md       # optional MCP integrations
│       └── skeleton-3az.drawio.xml  # blank 3-AZ template; agent copies this to start every diagram
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

No generator and no intermediate spec. The only code is the structural validator
`.kiro/scripts/validate-drawio.py` (run by the agent after saving, and by CI) and its regression test
`.kiro/scripts/test-validator.py`:

```
python3 .kiro/scripts/validate-drawio.py outputs/<project-slug>/<project>.drawio.xml
python3 .kiro/scripts/test-validator.py
```

---

## Creating a new diagram

Open the `arch-diagram` agent and describe the system:

```
/arch-diagram three-tier web app — ECS Fargate, Aurora PostgreSQL, 3 AZs,
              one NAT Gateway per AZ, no CDN
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
| `coords-cheatsheet.md` | Geometry constants and formulas — the only authoritative source for all coordinate values |
| `skeleton-3az.drawio.xml` | Blank 3-AZ template; the agent copies this to start every diagram |
| `house-style.md` | Colour palette, boundary hierarchy, edge rules, title block |
| `shapes-aws.md` | AWS icon keys and stencil names |
| `shapes-azure.md` | Azure starter icon catalog |
| `shapes-gcp.md` | GCP starter icon catalog |
| `mcp-options.md` | How to use optional Draw.io or AWS MCPs |

To add a service to the catalog, add a row to the relevant `shapes-*.md` file.
The stencil naming convention is:
`mxgraph.aws4.<name>` · `mxgraph.azure.<name>` · `mxgraph.gcp2.<name>`

---

## Custom agent setup

To wire up a new agent that uses this skill, use `arch-diagram.json` as a
starting point — it already declares the correct tools, permissions, and
resources (SKILL.md, coords-cheatsheet.md, skeleton-3az.drawio.xml, and the
steering conventions). At minimum a custom agent needs those four resources;
omitting `coords-cheatsheet.md` or `skeleton-3az.drawio.xml` will leave the
agent without the geometry constants and the blank template it builds from.

---

## Design approach

The agent asks only about requirements that affect architecture, models only the
components and connections needed to explain the system, and writes Draw.io XML
directly. Layout decisions (positioning, routing, spacing) are handled by
Kiro's reasoning guided by the house-style rules — not by code.
