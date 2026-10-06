# Build prompt: simplify the architecture diagram workflow

You are maintaining this repository's Kiro architecture diagram generator. Fix
the user workflow so Kiro gathers requirements conversationally and produces
clear, editable draw.io diagrams that resemble the supplied examples. Keep the
implementation small and general: represent components, placement scopes, and
meaningful connections in the existing spec, then let the deterministic renderer
handle coordinates and routing. Do not add project-specific layout exceptions,
invent missing architecture details, or reproduce every service in a technology
inventory.

Use `diagram examples/` as the visual reference. Prefer the clean hierarchy and
title treatment in Sadhaka AI, the compute lanes and focused flow page in
MediaMint, and the larger multi-VPC organization in Borderless Access. Produce
readable landscape diagrams with correct cloud boundaries, restrained icon
counts, aligned groups, clear arrows, and one coherent title block.

Kiro should ask a short set of focused questions only for decisions that change
the architecture: provider, workload/purpose, entry path, compute, data stores,
availability/regions, and required integrations. Infer safe defaults only when
they are explicit in the request or standard for the named design; otherwise
ask. Summarize the proposed architecture and assumptions, then generate both a
spec and diagram. Ask for project name if absent; offer optional metadata without
blocking generation. Keep the spec as the source of truth.

Preserve existing useful schema and renderer behavior. Prefer removing
contradictions and dead complexity over adding abstractions. Validate inputs and
report unresolved visual or architecture issues plainly. Never claim the output
matches a reference unless the generated result has been inspected.
