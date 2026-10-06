# Diagram Examples Analysis Report

Generated: 2026-09-28

## Summary

| Diagram | XML | PNG | Status | Role |
|---------|-----|-----|--------|------|
| Borderless Access | ✓ | ✓ | Timestamps match | Reference (complex multi-VPC) |
| Sadhaka AI | ✓ | ✓ | Timestamps match | Reference (clean 3-tier) |
| MediaMint | ✓ | ✗ | PNG missing | Reference (with Flow page) |
| MediaMint-Architecture | ✗ | ✓ | XML missing | Cannot use as code reference |
| Humyn AI Flow | ✓ | ✓ | PNG STALE (6 days) | Reference (flow only) |
| Humyn AI Architecture | ✗ | ✓ | XML missing | Cannot use as code reference |

## Findings by Example

### 1. Borderless Access Architecture Diagram
- **Structure**: 2 AWS Clouds, 1 Region, 2 VPCs (Lumen VPC, Spectra VPC), 6 AZs
- **Elements**: 184 cells, 161 vertices, 21 edges, 103 AWS icons
- **House Style Violations**:
  - ⚠️ 10 NAT Gateways (house style recommends 1 per VPC)
  - This is a multi-VPC enterprise diagram, so multiple NATs may be intentional
- **Quality**: Title block present and well-formatted
- **Use as Reference**: Complex enterprise pattern, not typical 3-tier

### 2. Sadhaka AI Architecture Diagram
- **Structure**: 1 AWS Cloud, 1 Region, 1 VPC, 3 AZs
- **Elements**: 85 cells, 69 vertices, 14 edges, 63 AWS icons
- **House Style Compliance**:
  - ✓ 1 NAT Gateway
  - ✓ 3 Availability Zones
  - ✓ Standard title block
- **Quality**: Clean layout, reasonable edge complexity
- **Use as Reference**: ✅ BEST example for standard 3-tier architecture

### 3. MediaMint (XML only)
- **Pages**: 2 (Architecture Diagram + Flow Diagram)
- **Architecture Page**: 62 vertices, 17 edges, 3 AZs with compute-group lanes
- **Flow Page**: 42 vertices, 33 edges, 21 with complex routing (2+ waypoints)
- **Issue**: No PNG preview available
- **Use as Reference**: Good for testing multi-page and flow diagrams

### 4. Humyn AI Flow Diagram
- **Structure**: Flow diagram only (page named "Page-2")
- **Elements**: 32 vertices, 18 edges
- **Issue**: PNG is 6 days older than XML - STALE preview
- **Note**: XML suggests this was part of a larger document (Page-2)
- **Use as Reference**: Limited (flow only, stale preview)

### 5. Missing XML Files
These cannot be used for code reference:
- `Huymn AI Architecture Diagram.png` (no XML)
- `MediaMint-Architecture Diagram.drawio.png` (no XML)

## House Style Traits Extracted

### From Sadhaka AI (cleanest example):
1. Title block: Project name, Version, Date, Creator, Reviewer
2. Container hierarchy: AWS Cloud → Region → VPC → AZ → Subnet
3. 3 AZs with public/app/db subnets
4. Single NAT Gateway in AZ1 public subnet
5. Compute-group lanes span all AZs
6. Edge services (Users, WAF, ALB) on the left

### From MediaMint Architecture:
1. Auto Scaling Groups as vertical lanes
2. AZ rows are horizontal
3. Subnets organized by tier (public, app, db)

## Defects and Issues

### In the Examples (not code bugs):

1. **Borderless Access**: Multiple NAT Gateways - may be intentional for enterprise pattern
2. **MediaMint Flow**: 21/33 edges have complex routing - may cause visual clutter
3. **Missing XMLs**: 2 PNGs cannot be used for regression testing
4. **Stale PNG**: Humyn AI Flow preview doesn't match current XML

### Identified in Generator Code (from prior analysis):

1. **Fixed**: ECR→ECS routing incorrectly used right corridor when vertically aligned

## Recommended Regression Fixtures

Based on this analysis, create fixtures for:

1. **3-tier-basic.yaml**: Single VPC, 3 AZs, 1 NAT, ECS cluster (based on Sadhaka AI)
2. **multi-lane.yaml**: Multiple compute-group lanes (ASG + ECS) (based on MediaMint)
3. **flow-basic.yaml**: Simple flow diagram with branch/merge
4. **dense-services.yaml**: Many region services (stress test)

