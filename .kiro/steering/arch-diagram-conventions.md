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

Use existing specs, shape catalogs, and renderer when they fit. Do not add
project-specific generator code or introduce a new renderer for a single
diagram. Use MCP tools only if already available and useful for AWS fact checks
or native Draw.io editing; never assume an MCP is configured.

Keep paths semantically correct and visually clear: few essential arrows,
short routes, readable labels, no overlaps, and no arrows running along
container borders. Inspect a rendered preview when available and correct visual
issues before delivery.
