# Architecture Diagram Generator

A Kiro skill that turns cloud migration requirements into editable draw.io
(`.drawio.xml`) architecture and flow diagrams, matching the firm's house style
(AWS 2020 icon set, nested Cloud/Region/VPC/AZ/subnet grouping, standardized
title block). Azure and GCP starter icon sets are included.

No LLM API calls are made at generation time: the agent (guided by the skill and
reference catalogs) authors a structured spec, and a deterministic Python helper
computes the layout and emits valid XML.

## Layout

```
.kiro/
├── agents/
│   └── arch-diagram.json        # dedicated agent with awsdac MCP wired in
├── skills/arch-diagram/
│   ├── SKILL.md                 # the procedure the agent follows (/arch-diagram)
│   └── references/
│       ├── spec-schema.md       # the intermediate spec format
│       ├── shapes-aws.md        # AWS service catalog (mirrors shapes.py)
│       ├── shapes-azure.md      # Azure starter catalog
│       ├── shapes-gcp.md        # GCP starter catalog
│       └── house-style.md       # hierarchy, colors, title block, edges
├── steering/
│   └── arch-diagram-conventions.md   # lean always-on rules + pointer to skill
└── scripts/arch-diagram/
    ├── generate_diagram.py      # spec -> .drawio.xml (CLI) + overlap checker
    ├── layout.py                # grid-based layout engine with AZ routing
    ├── shapes.py                # shape/color catalog (SOURCE OF TRUTH)
    ├── assets/
    │   └── comprinno-logo.png   # embedded in generated diagram headers
    └── tests/                   # pytest suite
```

AWS architecture pages automatically include IAM and S3 in the global
services row, plus Secrets Manager, CloudWatch, CloudTrail, and KMS in the
regional services area. A service already present in the spec is not added a
second time. These defaults apply to architecture pages, not flow diagrams.

The renderer balances regional services across rows and keeps the AWS Cloud
sized close to its contents. Flow diagrams use compact left-to-right steps
and stack independent branches. Their arrows use the shared orthogonal router,
which avoids icons, spreads shared paths into separate channels, and checks for
conflicts. When the same viewer/client sends requests and receives responses,
model it as one external endpoint on the left. Dense systems can use focused
flow pages for separate journeys. Customer
ingress can be laid out on a single row through WAF, Internet Gateway, and ALB
when those components and connections are part of the design.
ECS and EKS cluster headers show the service logo beside the cluster name. The
Comprinno logo is embedded in the diagram header.

## Usage

### Via the skill (recommended)
Use the dedicated `arch-diagram` agent, or invoke the skill from any agent:

```
/arch-diagram our e-commerce app is migrating to AWS — 3-tier, 3 AZs, ECS Fargate + RDS
```

The agent will ask for architecture choices that are missing, summarize the
proposed components and important flows, then create a focused spec and diagram.
It does not assume a fixed pattern, AZ count, NAT design, or workload-specific
service inventory. AWS architecture pages do include the shared foundation
services listed above. If an awsdac preview tool is available, it may also
render a PNG.

### Via the CLI
```bash
source .venv/bin/activate
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --strict-connectivity \
  --input my-project.spec.yaml \
  --output my-project.drawio.xml
```

`--strict-connectivity` blocks output when common architecture paths are
missing or an ALB targets an AZ-specific ECS/EKS task without an explicit
`az_specific: true` edge declaration. This lets the skill resolve or ask about
ambiguous paths before delivering a diagram.

See `.kiro/scripts/arch-diagram/tests/fixtures/demo_grid.yaml` for a worked example.
Open output at https://app.diagrams.net or in the draw.io desktop app.

## Setup

### Python dependencies
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

### awsdac MCP server (optional — enables PNG preview)

Install on macOS:
```bash
brew install awsdac
# Verify both binaries are available:
which awsdac && which awsdac-mcp-server
```

The agent config at `.kiro/agents/arch-diagram.json` already references
`awsdac-mcp-server`. Once installed, switching to the `arch-diagram` agent
will automatically start the MCP server and make `generateDiagramToFile`
available. The skill will call it after generating the draw.io XML to produce
a `<project>.png` preview.

If awsdac is not installed, the skill falls back gracefully — it still
generates the draw.io XML, it just won't produce the PNG preview.

## Skill discoverability

The default Kiro agent discovers skills via `skill://.kiro/skills/*/SKILL.md`.
The dedicated `arch-diagram` agent (`.kiro/agents/arch-diagram.json`) is the
recommended entry point — it has awsdac wired in and write permissions pre-approved
for spec and diagram files.

For a **custom agent** that needs access to this skill, add:
```json
{
  "resources": [
    "skill://.kiro/skills/*/SKILL.md",
    "file://.kiro/steering/**/*.md"
  ],
  "mcpServers": {
    "awsdac-mcp-server": {
      "command": "awsdac-mcp-server",
      "args": []
    }
  }
}
```

## Design approach

Kiro asks about requirements that affect the architecture, models only the
components and important connections needed to explain the system, and writes a
spec before rendering. The renderer handles coordinates and emits editable
draw.io XML. The examples in `diagram examples/` provide visual guidance; they
are not templates that every request must follow.

## Extending the shape catalog

`shapes.py` is the single source of truth; the `references/shapes-*.md` files
mirror it and a drift test enforces the match.

1. Add the service to the relevant dict in `shapes.py`:
   - AWS: `_AWS[key] = (stencil_suffix, category, label)`
   - Azure/GCP: `_AZURE[key]` / `_GCP[key] = (stencil, fill, category, label)`
2. Add a matching row to the corresponding `references/shapes-<provider>.md`.
3. Run `pytest` — `test_references.py` fails if the two drift apart.

Stencil names follow draw.io conventions: AWS `mxgraph.aws4.<name>`, Azure
`mxgraph.azure.<name>`, GCP `mxgraph.gcp2.<name>`.
