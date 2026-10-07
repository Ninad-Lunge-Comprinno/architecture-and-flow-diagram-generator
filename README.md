# Architecture Diagram Generator

A Kiro skill that turns cloud migration requirements into editable draw.io
(`.drawio.xml`) architecture and flow diagrams, matching the firm's house style
(AWS 2020 icon set, nested Cloud/Region/VPC/AZ/subnet grouping, standardised
title block). Azure and GCP starter icon sets are included.

No LLM API calls are made at generation time: the agent (guided by the skill and
reference catalogs) authors a structured spec, and a deterministic Python helper
computes the layout and emits valid XML.

## Repository layout

```
outputs/                         # ← all client work lives here
│   Each subfolder = one client / project.
│   The spec (.spec.yaml) is committed; the XML is generated and git-ignored.
│
├── acme-orders/
│   └── acme-orders.spec.yaml
├── dataforge/
│   └── dataforge.spec.yaml
├── healthbridge/
│   └── healthbridge.spec.yaml
├── jiohotstar/
│   └── jiohotstar-architecture.spec.yaml
└── ...                          # one folder per client

diagram examples/                # reference PNGs and XMLs used during design
flow diagram examples/           # reference flow-page examples

.kiro/
├── agents/
│   └── arch-diagram.json        # dedicated agent configuration
├── skills/arch-diagram/
│   ├── SKILL.md                 # procedure the agent follows (/arch-diagram)
│   └── references/
│       ├── spec-schema.md       # intermediate spec format
│       ├── shapes-aws.md        # AWS service catalog (mirrors shapes.py)
│       ├── shapes-azure.md      # Azure starter catalog
│       ├── shapes-gcp.md        # GCP starter catalog
│       └── house-style.md       # hierarchy, colours, title block, edges
├── steering/
│   └── arch-diagram-conventions.md   # always-on rules + pointer to skill
└── scripts/arch-diagram/
    ├── generate_diagram.py      # spec → .drawio.xml (CLI)
    ├── layout.py                # grid-based layout engine with AZ routing
    ├── routing.py               # edge routing and conflict checker
    ├── shapes.py                # shape/colour catalog (SOURCE OF TRUTH)
    └── tests/                   # pytest suite
```

> **Rule:** committed files are specs only. Generated XMLs are git-ignored and
> reproduced on demand by running the generator.

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # installs the package + the `arch-diagram` command + pytest
pytest
```

For a reproducible, hash-verified install of the exact dependency closure
(used by CI), install from the lockfile instead:

```bash
pip install --require-hashes -r requirements.lock   # pinned deps, verified by sha256
pip install -e . --no-deps                          # the package itself
```

Or use the Makefile:

```bash
make venv     # create .venv and install the package + dev deps
make test     # run the suite
make run SPEC=outputs/acme-orders/acme-orders.spec.yaml
make regen    # regenerate every outputs/**/*.spec.yaml
```

### CLI output contract

The generator prints **only the resolved output path to stdout** (so it can be
piped/scripted); all operational messaging (architecture checks, routing
conflicts, success) is logged to **stderr** with severity levels. Pass `-v` for
DEBUG diagnostics. On error it logs the cause and exits with code `2` instead of
raising a traceback.

### PNG preview (optional — for visual inspection)

The generator can rasterise each page to a PNG so you (or an agent) can eyeball
layout, grouping, and edge routing without opening draw.io. It uses a built-in
structural renderer (Pillow only — no browser, fully headless and deterministic)
that reads the generated XML and draws the container hierarchy, resource tiles
(coloured by service category), and every edge through its real waypoints.

```bash
pip install -e ".[png]"      # installs Pillow

# Generate XML and PNG previews in one step
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input outputs/acme-orders/acme-orders.spec.yaml --png

# Or render an existing XML on its own
python .kiro/scripts/arch-diagram/render_png.py \
  --input outputs/acme-orders/acme-orders.drawio.xml
```

Multi-page specs produce `<stem>.p1.png`, `<stem>.p2.png`, …; single-page specs
produce `<stem>.png`. The renderer prints each PNG path to stdout. The preview is
a *structural* view (it does not draw the AWS stencil glyphs), which is exactly
what is needed to catch overlapping arrows, bad grouping, or disconnected nodes.
Generated PNGs are git-ignored like the XML.

---

## Creating a new diagram

### 1. Via the Kiro agent (recommended)

Open the `arch-diagram` agent and describe the system:

```
/arch-diagram three-tier web app for Acme Orders — ECS Fargate, Aurora, 3 AZs,
              one NAT Gateway, CloudFront in front of S3 static site
```

The agent asks for any missing choices, summarises the proposed design, writes a
spec, and runs the generator. The output lands in `outputs/<project-slug>/`.

### 2. Via the CLI — quick generation

```bash
source .venv/bin/activate

# Auto-place in outputs/<project-slug>/ derived from metadata.project
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input outputs/acme-orders/acme-orders.spec.yaml

# Custom output directory
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input outputs/acme-orders/acme-orders.spec.yaml \
  --output-dir /path/to/deliverables

# Explicit output path (original behaviour)
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input outputs/acme-orders/acme-orders.spec.yaml \
  --output /tmp/acme-orders.drawio.xml

# Strict mode — fails if ingress paths or connectivity are incomplete
python .kiro/scripts/arch-diagram/generate_diagram.py \
  --input outputs/acme-orders/acme-orders.spec.yaml \
  --strict-connectivity
```

#### `--output-dir` behaviour

| Scenario | What happens |
|---|---|
| `--output-dir outputs` (default) | Creates `outputs/<slug>/` from `metadata.project` and writes `<stem>.drawio.xml` there |
| `--output-dir /path/to/dir` | Same, under that directory |
| `--output path/to/file.drawio.xml` | Writes directly to the given path (no folder created) |
| Neither flag given | Defaults to `--output-dir outputs` |

> **Note:** The folder slug is derived from `metadata.project` (e.g. `"Acme Orders"` → `acme-orders/`). If you run the generator on a spec that already has a folder under a different name (e.g. `outputs/acme-orders/`) the generator may create a second folder with the slug name. Keep the spec's `metadata.project` consistent with the folder name to avoid duplicates.

Open the generated XML at <https://app.diagrams.net> or in the draw.io desktop app.

### 3. Regenerate all outputs

```bash
source .venv/bin/activate
for spec in outputs/**/*.spec.yaml; do
  python .kiro/scripts/arch-diagram/generate_diagram.py --input "$spec"
done
```

---

## Adding a new client project

1. Create the folder and spec:

   ```bash
   mkdir -p outputs/my-client
   # Write outputs/my-client/my-client.spec.yaml
   ```

2. Populate the spec (see `references/spec-schema.md` for the full schema):

   ```yaml
   provider: aws
   metadata:
     project: "My Client"
     version: "1.0"
     date: "2026-10-01"
     creator: "Your Name"
   pages:
     - name: "Architecture Diagram"
       type: architecture
       global: [ ... ]
       edge:   [ ... ]
       region:
         label: "us-east-1"
         services: [ ... ]
         vpc:
           label: "My VPC"
           azs: [ ... ]
           compute_groups: [ ... ]
       edges: [ ... ]
   ```

3. Generate the diagram:

   ```bash
   source .venv/bin/activate
   python .kiro/scripts/arch-diagram/generate_diagram.py \
     --input outputs/my-client/my-client.spec.yaml
   # → outputs/my-client/my-client.drawio.xml
   ```

4. Commit the spec only — the XML is git-ignored:

   ```bash
   git add outputs/my-client/my-client.spec.yaml
   git commit -m "Add My Client architecture spec"
   ```

---

## Running tests

```bash
source .venv/bin/activate
pytest                           # run the full suite
pytest -k "dataforge"            # run tests matching a keyword
pytest --tb=short -q             # compact output
```

---

## Extending the shape catalog

`shapes.py` is the single source of truth; the `references/shapes-*.md` files
mirror it and a drift test fails the build if they diverge.

1. Add the service to the relevant dict in `shapes.py`:
   - AWS: `_AWS[key] = (stencil_suffix, category, label)`
   - Azure/GCP: `_AZURE[key]` / `_GCP[key] = (stencil, fill, category, label)`
2. Add a matching row to the corresponding `references/shapes-<provider>.md`.
3. Run `pytest` — `test_references.py` fails if the two drift apart.

Stencil names follow draw.io conventions:
`mxgraph.aws4.<name>` · `mxgraph.azure.<name>` · `mxgraph.gcp2.<name>`

---

## Design approach

The agent asks for requirements that affect the architecture, models only the
components and connections needed to explain the system, and writes a spec before
rendering. The renderer handles coordinates and emits editable XML. Examples in
`diagram examples/` and `flow diagram examples/` provide visual guidance — they
are references, not templates.

For a **custom agent** that needs access to this skill, add to its config:

```json
{
  "resources": [
    "skill://.kiro/skills/*/SKILL.md",
    "file://.kiro/steering/**/*.md"
  ]
}
```
