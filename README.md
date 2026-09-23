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
    └── tests/                   # pytest suite
```

## Usage

### Via the skill (recommended)
Use the dedicated `arch-diagram` agent, or invoke the skill from any agent:

```
/arch-diagram our e-commerce app is migrating to AWS — 3-tier, 3 AZs, ECS Fargate + RDS
```

The agent will:
1. Ask clarifying questions if needed
2. Draft a spec following the Pattern Library in SKILL.md
3. Show you the spec for review
4. Generate `<project>.drawio.xml` with overlap warnings
5. (If awsdac is installed) also generate a PNG preview

### Via the CLI
```bash
source .venv/bin/activate
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input my-project.spec.yaml \
  --output my-project.drawio.xml
```

See `tests/fixtures/demo_grid.yaml` for a worked example.
Open output at https://app.diagrams.net or in the draw.io desktop app.

## Setup

### Python dependencies
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest            # 67 tests should pass
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

## What makes the diagrams intelligent

The skill's SKILL.md encodes:
- **Architecture Pattern Library**: 3-tier, serverless, microservices, data pipeline
- **Service placement rules**: what belongs in global vs edge vs region vs VPC
- **Connection semantics**: when to exit bottom vs top, when to use direct vs routed edges
- **Common mistakes to avoid**: single NAT, Cache-left/RDS-right ordering, ALB→cluster not tasks
- **Routing is fully computed**: the engine detects adjacent-vs-non-adjacent, multi-AZ replication skips, ECR-above-cluster — no hardcoded coordinates
- **Overlap detection**: after generating, the engine checks if any icons or containers geometrically overlap and warns before writing

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
