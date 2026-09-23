# AWS Shape Catalog

Service keys usable in a spec under `provider: aws`. This table mirrors
`.kiro/scripts/arch-diagram/shapes.py` (the source of truth); a consistency
test fails the build if they drift apart.

Use the **key** column as the `service:` value in a spec.

| key | category | fill | stencil | default label |
|-----|----------|------|---------|---------------|
| api_gateway | networking | #8C4FFF | mxgraph.aws4.api_gateway | Amazon API Gateway |
| application_load_balancer | networking | #8C4FFF | mxgraph.aws4.application_load_balancer | Application Load Balancer |
| aurora | database | #C925D1 | mxgraph.aws4.aurora | Amazon Aurora |
| backup | storage | #7AA116 | mxgraph.aws4.backup | AWS Backup |
| bedrock | ml | #01A88D | mxgraph.aws4.bedrock | Amazon Bedrock |
| certificate_manager_3 | security | #DD344C | mxgraph.aws4.certificate_manager_3 | AWS Certificate Manager |
| cloudfront | networking | #8C4FFF | mxgraph.aws4.cloudfront | Amazon CloudFront |
| cloudtrail | management | #E7157B | mxgraph.aws4.cloudtrail | AWS CloudTrail |
| cloudwatch_2 | management | #E7157B | mxgraph.aws4.cloudwatch_2 | Amazon CloudWatch |
| codebuild | devtools | #C925D1 | mxgraph.aws4.codebuild | AWS CodeBuild |
| codedeploy | devtools | #C925D1 | mxgraph.aws4.codedeploy | AWS CodeDeploy |
| codepipeline | devtools | #C925D1 | mxgraph.aws4.codepipeline | AWS CodePipeline |
| config | management | #E7157B | mxgraph.aws4.config | AWS Config |
| dynamodb | database | #C925D1 | mxgraph.aws4.dynamodb | Amazon DynamoDB |
| ec2 | compute | #ED7100 | mxgraph.aws4.ec2 | Amazon EC2 |
| ecr | containers | #ED7100 | mxgraph.aws4.ecr | Amazon ECR |
| ecs | containers | #ED7100 | mxgraph.aws4.ecs | Amazon ECS |
| eks | containers | #ED7100 | mxgraph.aws4.eks | Amazon EKS |
| elasticache | database | #C925D1 | mxgraph.aws4.elasticache | Amazon ElastiCache |
| elasticsearch_service | analytics | #E7157B | mxgraph.aws4.elasticsearch_service | Amazon OpenSearch |
| endpoints | networking | #8C4FFF | mxgraph.aws4.endpoints | VPC Endpoints |
| fargate | containers | #ED7100 | mxgraph.aws4.fargate | AWS Fargate |
| guardduty | security | #DD344C | mxgraph.aws4.guardduty | Amazon GuardDuty |
| identity_and_access_management | security | #DD344C | mxgraph.aws4.identity_and_access_management | AWS IAM |
| internet_gateway | networking | #8C4FFF | mxgraph.aws4.internet_gateway | Internet Gateway |
| iot_core | iot | #7AA116 | mxgraph.aws4.iot_core | AWS IoT Core |
| key_management_service | security | #DD344C | mxgraph.aws4.key_management_service | AWS KMS |
| lambda | compute | #ED7100 | mxgraph.aws4.lambda | AWS Lambda |
| nat_gateway | networking | #8C4FFF | mxgraph.aws4.nat_gateway | NAT Gateway |
| organizations | management | #E7157B | mxgraph.aws4.organizations | AWS Organizations |
| polly | ml | #01A88D | mxgraph.aws4.polly | Amazon Polly |
| rds | database | #C925D1 | mxgraph.aws4.rds | Amazon RDS |
| rekognition_2 | ml | #01A88D | mxgraph.aws4.rekognition_2 | Amazon Rekognition |
| route_53 | networking | #8C4FFF | mxgraph.aws4.route_53 | Amazon Route 53 |
| s3 | storage | #7AA116 | mxgraph.aws4.s3 | Amazon S3 |
| sagemaker | ml | #01A88D | mxgraph.aws4.sagemaker | Amazon SageMaker |
| secrets_manager | security | #DD344C | mxgraph.aws4.secrets_manager | AWS Secrets Manager |
| security_hub | security | #DD344C | mxgraph.aws4.security_hub | AWS Security Hub |
| single_sign_on | security | #DD344C | mxgraph.aws4.single_sign_on | AWS IAM Identity Center |
| sns | integration | #E7157B | mxgraph.aws4.sns | Amazon SNS |
| step_functions | integration | #E7157B | mxgraph.aws4.step_functions | AWS Step Functions |
| systems_manager | management | #E7157B | mxgraph.aws4.systems_manager | AWS Systems Manager |
| transcribe | ml | #01A88D | mxgraph.aws4.transcribe | Amazon Transcribe |
| user | general | #232F3E | mxgraph.aws4.user | User |
| vpc | networking | #8C4FFF | mxgraph.aws4.vpc | Amazon VPC |
| vpc_privatelink | networking | #8C4FFF | mxgraph.aws4.vpc_privatelink | AWS PrivateLink |
| waf | security | #DD344C | mxgraph.aws4.waf | AWS WAF |

## Adding a new AWS service
1. Add the entry to `_AWS` in `shapes.py` (`key: (stencil_suffix, category, label)`).
2. Add a matching row to this table.
3. Run `pytest` — the consistency test confirms the two stay in sync.
