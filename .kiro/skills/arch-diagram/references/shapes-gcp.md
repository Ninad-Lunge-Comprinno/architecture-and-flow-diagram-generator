# GCP Shape Catalog (starter set)

Service keys usable in architecture diagrams under `provider: gcp`.
Core GCP services use the `mxgraph.gcp2.*` stencil family. This is a
starter set; extend it following the workflow at the bottom.

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
| bigquery | analytics | #4285F4 | mxgraph.gcp2.bigquery | BigQuery |
| cloud_pubsub | integration | #4285F4 | mxgraph.gcp2.cloud_pubsub | Cloud Pub/Sub |
| cloud_dataflow | analytics | #4285F4 | mxgraph.gcp2.cloud_dataflow | Cloud Dataflow |
| cloud_dataproc | analytics | #4285F4 | mxgraph.gcp2.cloud_dataproc | Cloud Dataproc |
| cloud_scheduler | integration | #4285F4 | mxgraph.gcp2.cloud_scheduler | Cloud Scheduler |
| cloud_workflows | integration | #4285F4 | mxgraph.gcp2.cloud_workflows | Cloud Workflows |
| artifact_registry | devtools | #4285F4 | mxgraph.gcp2.artifact_registry | Artifact Registry |
| cloud_monitoring | management | #4285F4 | mxgraph.gcp2.cloud_monitoring | Cloud Monitoring |
| cloud_logging | management | #4285F4 | mxgraph.gcp2.cloud_logging | Cloud Logging |
| cloud_build | devtools | #4285F4 | mxgraph.gcp2.cloud_build | Cloud Build |
| user | general | #4285F4 | mxgraph.gcp2.user | User |

## Adding a new GCP service

1. Add a row to the table above with: key, category, fill color, stencil, and default label
2. The stencil must be a valid `mxgraph.gcp2.*` shape
3. Test by placing the icon in a diagram to verify it renders correctly
