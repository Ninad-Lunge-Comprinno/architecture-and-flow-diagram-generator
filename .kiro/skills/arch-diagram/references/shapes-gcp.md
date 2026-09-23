# GCP Shape Catalog (starter set)

Service keys usable in a spec under `provider: gcp`. Mirrors `shapes.py`.
GCP uses the `mxgraph.gcp2.*` stencil family. This is a starter set; extend it
following the workflow at the bottom.

| key | category | fill | stencil | default label |
|-----|----------|------|---------|---------------|
| cloud_cdn | networking | #4285F4 | mxgraph.gcp2.cloud_cdn | Cloud CDN |
| cloud_functions | compute | #4285F4 | mxgraph.gcp2.cloud_functions | Cloud Functions |
| cloud_iam | security | #4285F4 | mxgraph.gcp2.cloud_iam | Cloud IAM |
| cloud_load_balancing | networking | #4285F4 | mxgraph.gcp2.cloud_load_balancing | Cloud Load Balancing |
| cloud_run | compute | #4285F4 | mxgraph.gcp2.cloud_run | Cloud Run |
| cloud_sql | database | #4285F4 | mxgraph.gcp2.cloud_sql | Cloud SQL |
| cloud_storage | storage | #4285F4 | mxgraph.gcp2.cloud_storage | Cloud Storage |
| compute_engine | compute | #4285F4 | mxgraph.gcp2.compute_engine | Compute Engine |
| firestore | database | #4285F4 | mxgraph.gcp2.cloud_firestore | Firestore |
| gke | containers | #4285F4 | mxgraph.gcp2.google_kubernetes_engine | GKE |
| vpc_network | networking | #4285F4 | mxgraph.gcp2.virtual_private_cloud | VPC Network |

## Adding a new GCP service
1. Add the entry to `_GCP` in `shapes.py` (`key: (stencil, fill, category, label)`).
2. Add a matching row here.
3. Run `pytest` to confirm no drift.
