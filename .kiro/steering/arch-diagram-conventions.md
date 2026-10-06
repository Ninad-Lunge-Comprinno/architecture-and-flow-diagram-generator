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

For shared ECS/EKS workloads, connect ingress to the cluster boundary unless an
AZ-specific route is required. When architecture and flow views are both
requested, cross-check their primary request and data paths and resolve missing
connections before generating the diagram.

For flow views, verify producer-to-consumer direction and show the shortest
clear sequence. Model a person and their client as one external endpoint when
they represent the same traffic source/destination; keep them separate only
when their relationship matters, stack them outside AWS, and route network
traffic through the client. Keep a shared endpoint on the left even when it
receives responses. Stack independent branches into compact rows, minimize
empty columns, and use only bends required by branches or boundaries. Ask about
missing topology only when it changes the flow. Split independent journeys into
focused pages when combining them creates long crossovers or a crowded canvas.

The local provider shape catalogs define supported service keys. Do not invent
stencil names. If a needed service is unsupported, explain that and extend the
catalog only when that work is part of the request.
