# Architecture diagram conventions

For architecture or flow diagram requests, use `.kiro/skills/arch-diagram/SKILL.md`.
Gather missing architecture decisions conversationally, then write a YAML spec
and use `.kiro/scripts/arch-diagram/generate_diagram.py`. Do not hand-write XML,
guess missing requirements, or expand a request into an unrelated service list.

Model components at their real scope and connect only important traffic, data,
deployment, replication, or dependency paths. Use the examples in
`diagram examples/` as visual references, with a focus on readable grouping,
hierarchy, concise labels, and limited edge crossings. Apply availability and
network choices from the user's requirements; there is no universal AZ, NAT, or
VPC template.

The local provider shape catalogs define supported service keys. Do not invent
stencil names. If a needed service is unsupported, explain that and extend the
catalog only when that work is part of the request.
