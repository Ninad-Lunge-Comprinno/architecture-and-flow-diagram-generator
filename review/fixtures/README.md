# Visual Regression Fixtures

This directory contains minimal fixtures for regression testing the diagram generator.

## Fixtures

### 1. 3tier-basic.spec.yaml
**Based on**: Sadhaka AI Architecture Diagram (cleanest reference)
**Tests**: Standard 3-tier house style

**Expected Invariants**:
- [ ] Title block visible in top-left with Project, Version, Date, Creator, Reviewer
- [ ] Container hierarchy: AWS Cloud → Region → VPC → AZ (×3) → Subnets
- [ ] Single NAT Gateway in AZ1 public subnet only
- [ ] Empty public subnets in AZ2, AZ3
- [ ] ECS cluster lane spans all 3 AZs vertically
- [ ] ECR positioned directly above ECS lane (dx < 50px)
- [ ] ECR→ECS edge drops straight down (no right corridor)
- [ ] RDS replication edges use right corridor for multi-AZ skip
- [ ] No icon or label overlaps
- [ ] ALB positioned in edge strip, aligned with AZ1-AZ2 gap

**Known Non-Defects**:
- IGW straddles VPC left border (intentional)
- Region services row uses 45px gap (tighter than 60px, intentional)

### 2. multi-lane.spec.yaml
**Based on**: MediaMint Architecture Diagram
**Tests**: Multiple compute-group lanes (ASG + ECS)

**Expected Invariants**:
- [ ] Two compute-group lanes: ASG (left), ECS (right)
- [ ] Both lanes span all 3 AZs
- [ ] ECR positioned above ECS lane (not ASG)
- [ ] ALB→ASG and ALB→ECS edges don't cross each other
- [ ] Cross-lane edges (asg-az1→rds1, ecs-az1→rds1) use appropriate routing
- [ ] Lanes don't overlap with each other

### 3. flow-branch-merge.spec.yaml
**Tests**: Flow diagram with branch and merge pattern

**Expected Invariants**:
- [ ] Nodes arranged in topological layers (sources at top)
- [ ] Branch point (ALB) has two outgoing edges that don't cross
- [ ] Merge point (f_db) has multiple incoming edges
- [ ] Cross-branch edge (f_ecs→f_s3) routed cleanly
- [ ] No overlapping edges at branching/merging nodes

## Running Tests

```bash
# Generate all fixtures
cd /path/to/architecture-diagram-generator
source .venv/bin/activate

for spec in review/fixtures/*.spec.yaml; do
    base=$(basename "$spec" .spec.yaml)
    python .kiro/scripts/arch-diagram/generate_diagram.py \
        --input "$spec" \
        --output "review/fixtures/${base}.drawio.xml"
done

# Run automated checks
pytest .kiro/scripts/arch-diagram/tests/ -v
```

## Manual Visual Review

After generating, open each `.drawio.xml` in draw.io and verify:

1. **Normal zoom (100%)**: Labels are readable, icons are recognizable
2. **Edges**: No crossings through unrelated icons, clean orthogonal routing
3. **Hierarchy**: Clear visual distinction between Cloud/Region/VPC/AZ/Subnet
4. **Spacing**: Consistent gaps, no cramped or overlapping elements
5. **Title block**: Properly formatted, not overlapping with diagram content

## Notes

- These fixtures use minimal specs to isolate specific patterns
- Source specs are included for reproducibility
- Original diagram examples (`diagram examples/`) are historical references, not generated outputs
- 2 examples have missing XMLs and cannot be regenerated
- 1 example has a stale PNG preview
