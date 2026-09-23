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
    ├── generate_diagram.py      # spec -> .drawio.xml (CLI)
    ├── layout.py                # deterministic lane-based layout engine
    ├── shapes.py                # shape/color catalog (SOURCE OF TRUTH)
    └── tests/                   # pytest suite
```

## Usage

### Via the skill (recommended)
Ask the agent to create a diagram (e.g. "draft an architecture diagram for our
3-tier app migrating to AWS"). The agent invokes the `arch-diagram` skill,
drafts a spec, shows it to you for review, then generates the file.

### Directly via the CLI
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input my-project.spec.yaml \
  --output my-project.drawio.xml
```
Open the result at https://app.diagrams.net or in the draw.io desktop app.

See `.kiro/skills/arch-diagram/references/spec-schema.md` for the spec format and
`tests/fixtures/demo_grid.yaml` for a worked grid-layout example.

## Skill discoverability

The default Kiro agent discovers skills via the `skill://.kiro/skills/*/SKILL.md`
resource, so `arch-diagram` is available out of the box. For a **custom** agent,
add these to its `resources` so it can find the skill and conventions:
```json
{
  "resources": [
    "skill://.kiro/skills/*/SKILL.md",
    "file://.kiro/steering/**/*.md"
  ]
}
```

## Development

```bash
pip install -r requirements.txt
pytest            # runs the full suite (paths configured in pyproject.toml)
```

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
