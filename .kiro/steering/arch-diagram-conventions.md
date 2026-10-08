# Architecture diagram conventions

For architecture requests, use `.kiro/skills/arch-diagram/SKILL.md`. Let Kiro
reason about the requirements, ask only topology-changing questions, and keep
the user-facing workflow prompt based. The normal deliverable is one editable
Draw.io file with one architecture page and one primary flow page; do not add
extra flows unless requested.

Treat `diagram examples/Comprinno Architecture Template.drawio.xml` as the
current visual reference only. Its example components, metadata, AZ count,
resource counts, and connections are not defaults. Keep architecture scope
accurate: global services above the Region, regional resources such as S3
buckets in the Region and outside the VPC, and external users outside AWS.

For the prompt-based workflow, use Kiro's reasoning to create editable Draw.io
XML directly from the requirements and references. Do not run or modify the
Python generator or create project-specific code. A supplied YAML spec is a
topology source, not a required intermediate format. Use MCP tools only when
already configured and useful for AWS fact checks or native Draw.io editing;
never assume an MCP is available.

Keep paths semantically correct and visually clear: few essential arrows,
short routes, readable labels, no overlaps, and no arrows running along
container borders. Inspect a rendered preview when available and correct visual
issues before delivery.
