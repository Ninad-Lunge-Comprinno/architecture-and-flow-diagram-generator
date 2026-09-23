# Architecture Diagram Conventions

When the user asks to create, draft, or update a cloud **architecture** or
**flow** diagram (draw.io / .drawio.xml), use the `arch-diagram` skill — invoke
`/arch-diagram` or load `.kiro/skills/arch-diagram/SKILL.md`. Do not hand-write
draw.io XML; author a spec and run the generator.

House-style essentials (full detail in the skill's `references/`):

- **Nesting**: AWS Cloud -> Region -> VPC -> Availability Zone -> subnet
  (public / app / db) -> resource icons. Shared services (IAM, CloudWatch, S3,
  KMS) sit at the region level, outside the VPC.
- **Category colors**: compute #ED7100, database #C925D1, networking #8C4FFF,
  storage #7AA116, security #DD344C, management/analytics/integration #E7157B,
  ml #01A88D.
- **Title block** (page 1 only): project name, version, date, creator, reviewer.
- **Providers**: AWS (primary), Azure and GCP starter sets.
- **Deliverable**: a saved `<project>.drawio.xml`, often two pages
  (architecture + flow).

Only use service keys listed in the skill's `references/shapes-<provider>.md`.
