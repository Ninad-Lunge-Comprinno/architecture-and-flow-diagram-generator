# AWS Shape Catalog

Service keys usable in a spec under `provider: aws`. This table mirrors
`.kiro/scripts/arch-diagram/shapes.py` (the source of truth); a consistency
test fails the build if they drift apart.

> Note: Any service key **not** listed here is also accepted — the engine
> derives a best-effort stencil automatically from the key name. Add to
> this table and to `_AWS` in `shapes.py` to make it permanent.

| key | category | fill | stencil | default label |
|-----|----------|------|---------|---------------|
| amplify | devtools | #C925D1 | mxgraph.aws4.amplify | AWS Amplify |
| api_gateway | networking | #8C4FFF | mxgraph.aws4.api_gateway | Amazon API Gateway |
| api_gateway_v2 | networking | #8C4FFF | mxgraph.aws4.api_gateway | Amazon API Gateway |
| app_runner | containers | #ED7100 | mxgraph.aws4.app_runner | AWS App Runner |
| appflow | integration | #E7157B | mxgraph.aws4.appflow | Amazon AppFlow |
| application_load_balancer | networking | #8C4FFF | mxgraph.aws4.application_load_balancer | Application Load Balancer |
| appsync | integration | #E7157B | mxgraph.aws4.appsync | AWS AppSync |
| athena | analytics | #E7157B | mxgraph.aws4.athena | Amazon Athena |
| aurora | database | #C925D1 | mxgraph.aws4.aurora | Amazon Aurora |
| auto_scaling2 | management | #E7157B | mxgraph.aws4.auto_scaling2 | AWS Auto Scaling |
| backup | storage | #7AA116 | mxgraph.aws4.backup | AWS Backup |
| batch | compute | #ED7100 | mxgraph.aws4.batch | AWS Batch |
| bedrock | ml | #01A88D | mxgraph.aws4.bedrock | Amazon Bedrock |
| certificate_manager_3 | security | #DD344C | mxgraph.aws4.certificate_manager_3 | AWS Certificate Manager |
| classic_load_balancer | networking | #8C4FFF | mxgraph.aws4.classic_load_balancer | Classic Load Balancer |
| clean_rooms | analytics | #E7157B | mxgraph.aws4.clean_rooms | AWS Clean Rooms |
| cloud9 | devtools | #C925D1 | mxgraph.aws4.cloud9 | AWS Cloud9 |
| cloudformation | management | #E7157B | mxgraph.aws4.cloudformation | AWS CloudFormation |
| cloudfront | networking | #8C4FFF | mxgraph.aws4.cloudfront | Amazon CloudFront |
| cloudtrail | management | #E7157B | mxgraph.aws4.cloudtrail | AWS CloudTrail |
| cloudwatch_2 | management | #E7157B | mxgraph.aws4.cloudwatch_2 | Amazon CloudWatch |
| codeartifact | devtools | #C925D1 | mxgraph.aws4.codeartifact | AWS CodeArtifact |
| codebuild | devtools | #C925D1 | mxgraph.aws4.codebuild | AWS CodeBuild |
| codecommit | devtools | #C925D1 | mxgraph.aws4.codecommit | AWS CodeCommit |
| codedeploy | devtools | #C925D1 | mxgraph.aws4.codedeploy | AWS CodeDeploy |
| codeguru | ml | #01A88D | mxgraph.aws4.codeguru | Amazon CodeGuru |
| codepipeline | devtools | #C925D1 | mxgraph.aws4.codepipeline | AWS CodePipeline |
| codestar | devtools | #C925D1 | mxgraph.aws4.codestar | AWS CodeStar |
| cognito | security | #DD344C | mxgraph.aws4.cognito | Amazon Cognito |
| comprehend | ml | #01A88D | mxgraph.aws4.comprehend | Amazon Comprehend |
| config | management | #E7157B | mxgraph.aws4.config | AWS Config |
| connect | integration | #E7157B | mxgraph.aws4.connect | Amazon Connect |
| control_tower | management | #E7157B | mxgraph.aws4.control_tower | AWS Control Tower |
| corporate_data_center | general | #232F3E | mxgraph.aws4.corporate_data_center | Corporate Data Center |
| data_pipeline | analytics | #E7157B | mxgraph.aws4.data_pipeline | AWS Data Pipeline |
| database_migration_service | database | #C925D1 | mxgraph.aws4.database_migration_service | AWS DMS |
| datasync | storage | #7AA116 | mxgraph.aws4.datasync | AWS DataSync |
| deepracer | ml | #01A88D | mxgraph.aws4.deepracer | AWS DeepRacer |
| detective | security | #DD344C | mxgraph.aws4.detective | Amazon Detective |
| direct_connect | networking | #8C4FFF | mxgraph.aws4.direct_connect | AWS Direct Connect |
| documentdb | database | #C925D1 | mxgraph.aws4.documentdb | Amazon DocumentDB |
| dynamodb | database | #C925D1 | mxgraph.aws4.dynamodb | Amazon DynamoDB |
| ebs | storage | #7AA116 | mxgraph.aws4.ebs | Amazon EBS |
| ec2 | compute | #ED7100 | mxgraph.aws4.ec2 | Amazon EC2 |
| ecr | containers | #ED7100 | mxgraph.aws4.ecr | Amazon ECR |
| ecs | containers | #ED7100 | mxgraph.aws4.ecs | Amazon ECS |
| efs | storage | #7AA116 | mxgraph.aws4.efs | Amazon EFS |
| eks | containers | #ED7100 | mxgraph.aws4.eks | Amazon EKS |
| elastic_beanstalk | compute | #ED7100 | mxgraph.aws4.elastic_beanstalk | AWS Elastic Beanstalk |
| elastic_load_balancing | networking | #8C4FFF | mxgraph.aws4.elastic_load_balancing | Elastic Load Balancing |
| elasticache | database | #C925D1 | mxgraph.aws4.elasticache | Amazon ElastiCache |
| elasticsearch_service | analytics | #E7157B | mxgraph.aws4.elasticsearch_service | Amazon OpenSearch |
| elemental_mediaconvert | management | #E7157B | mxgraph.aws4.elemental_mediaconvert | AWS Elemental MediaConvert |
| emr | analytics | #E7157B | mxgraph.aws4.emr | Amazon EMR |
| endpoints | networking | #8C4FFF | mxgraph.aws4.endpoints | VPC Endpoints |
| eventbridge | integration | #E7157B | mxgraph.aws4.eventbridge | Amazon EventBridge |
| fargate | containers | #ED7100 | mxgraph.aws4.fargate | AWS Fargate |
| firewall_manager | security | #DD344C | mxgraph.aws4.firewall_manager | AWS Firewall Manager |
| forecast | ml | #01A88D | mxgraph.aws4.forecast | Amazon Forecast |
| fsx | storage | #7AA116 | mxgraph.aws4.fsx | Amazon FSx |
| global_accelerator | networking | #8C4FFF | mxgraph.aws4.global_accelerator | AWS Global Accelerator |
| glue | analytics | #E7157B | mxgraph.aws4.glue | AWS Glue |
| guardduty | security | #DD344C | mxgraph.aws4.guardduty | Amazon GuardDuty |
| health | management | #E7157B | mxgraph.aws4.health | AWS Health |
| identity_and_access_management | security | #DD344C | mxgraph.aws4.identity_and_access_management | AWS IAM |
| inspector | security | #DD344C | mxgraph.aws4.inspector | Amazon Inspector |
| interactive_video_service | management | #E7157B | mxgraph.aws4.interactive_video_service | Amazon IVS |
| internet | general | #232F3E | mxgraph.aws4.internet | Internet |
| internet_gateway | networking | #8C4FFF | mxgraph.aws4.internet_gateway | Internet Gateway |
| iot_analytics | iot | #7AA116 | mxgraph.aws4.iot_analytics | AWS IoT Analytics |
| iot_core | iot | #7AA116 | mxgraph.aws4.iot_core | AWS IoT Core |
| iot_events | iot | #7AA116 | mxgraph.aws4.iot_events | AWS IoT Events |
| iot_greengrass | iot | #7AA116 | mxgraph.aws4.iot_greengrass | AWS IoT Greengrass |
| iot_sitewise | iot | #7AA116 | mxgraph.aws4.iot_sitewise | AWS IoT SiteWise |
| kendra | ml | #01A88D | mxgraph.aws4.kendra | Amazon Kendra |
| key_management_service | security | #DD344C | mxgraph.aws4.key_management_service | AWS KMS |
| keyspaces | database | #C925D1 | mxgraph.aws4.keyspaces | Amazon Keyspaces |
| kinesis | integration | #E7157B | mxgraph.aws4.kinesis | Amazon Kinesis |
| kinesis_data_analytics | integration | #E7157B | mxgraph.aws4.kinesis_data_analytics | Amazon Kinesis Data Analytics |
| kinesis_data_firehose | integration | #E7157B | mxgraph.aws4.kinesis_data_firehose | Amazon Kinesis Data Firehose |
| kinesis_data_streams | integration | #E7157B | mxgraph.aws4.kinesis_data_streams | Amazon Kinesis Data Streams |
| lake_formation | analytics | #E7157B | mxgraph.aws4.lake_formation | AWS Lake Formation |
| lambda | compute | #ED7100 | mxgraph.aws4.lambda | AWS Lambda |
| lex_v2 | ml | #01A88D | mxgraph.aws4.lex_v2 | Amazon Lex |
| lightsail | compute | #ED7100 | mxgraph.aws4.lightsail | Amazon Lightsail |
| macie | security | #DD344C | mxgraph.aws4.macie | Amazon Macie |
| managed_grafana | management | #E7157B | mxgraph.aws4.managed_grafana | Amazon Managed Grafana |
| managed_streaming_for_kafka | analytics | #E7157B | mxgraph.aws4.managed_streaming_for_kafka | Amazon MSK |
| memorydb | database | #C925D1 | mxgraph.aws4.memorydb | Amazon MemoryDB |
| mobile_client | general | #232F3E | mxgraph.aws4.mobile_client | Mobile Client |
| mq | integration | #E7157B | mxgraph.aws4.mq | Amazon MQ |
| nat_gateway | networking | #8C4FFF | mxgraph.aws4.nat_gateway | NAT Gateway |
| neptune | database | #C925D1 | mxgraph.aws4.neptune | Amazon Neptune |
| network_firewall | security | #DD344C | mxgraph.aws4.network_firewall | AWS Network Firewall |
| network_load_balancer | networking | #8C4FFF | mxgraph.aws4.network_load_balancer | Network Load Balancer |
| organizations | management | #E7157B | mxgraph.aws4.organizations | AWS Organizations |
| outposts | compute | #ED7100 | mxgraph.aws4.outposts | AWS Outposts |
| personal_health_dashboard | management | #E7157B | mxgraph.aws4.personal_health_dashboard | AWS Personal Health Dashboard |
| personalize | ml | #01A88D | mxgraph.aws4.personalize | Amazon Personalize |
| pinpoint | integration | #E7157B | mxgraph.aws4.pinpoint | Amazon Pinpoint |
| polly | ml | #01A88D | mxgraph.aws4.polly | Amazon Polly |
| quicksight | analytics | #E7157B | mxgraph.aws4.quicksight | Amazon QuickSight |
| rds | database | #C925D1 | mxgraph.aws4.rds | Amazon RDS |
| redshift | database | #C925D1 | mxgraph.aws4.redshift | Amazon Redshift |
| rekognition_2 | ml | #01A88D | mxgraph.aws4.rekognition_2 | Amazon Rekognition |
| route_53 | networking | #8C4FFF | mxgraph.aws4.route_53 | Amazon Route 53 |
| s3 | storage | #7AA116 | mxgraph.aws4.s3 | Amazon S3 |
| s3_glacier | storage | #7AA116 | mxgraph.aws4.s3_glacier | Amazon S3 Glacier |
| sagemaker | ml | #01A88D | mxgraph.aws4.sagemaker | Amazon SageMaker |
| secrets_manager | security | #DD344C | mxgraph.aws4.secrets_manager | AWS Secrets Manager |
| security_hub | security | #DD344C | mxgraph.aws4.security_hub | AWS Security Hub |
| service_catalog | management | #E7157B | mxgraph.aws4.service_catalog | AWS Service Catalog |
| ses | integration | #E7157B | mxgraph.aws4.ses | Amazon SES |
| shield | security | #DD344C | mxgraph.aws4.shield | AWS Shield |
| single_sign_on | security | #DD344C | mxgraph.aws4.single_sign_on | AWS IAM Identity Center |
| snow_family | storage | #7AA116 | mxgraph.aws4.snow_family | AWS Snow Family |
| sns | integration | #E7157B | mxgraph.aws4.sns | Amazon SNS |
| sqs | integration | #E7157B | mxgraph.aws4.sqs | Amazon SQS |
| step_functions | integration | #E7157B | mxgraph.aws4.step_functions | AWS Step Functions |
| storage_gateway | storage | #7AA116 | mxgraph.aws4.storage_gateway | AWS Storage Gateway |
| systems_manager | management | #E7157B | mxgraph.aws4.systems_manager | AWS Systems Manager |
| textract | ml | #01A88D | mxgraph.aws4.textract | Amazon Textract |
| timestream | database | #C925D1 | mxgraph.aws4.timestream | Amazon Timestream |
| traditional_server | general | #232F3E | mxgraph.aws4.traditional_server | Traditional Server |
| transcribe | ml | #01A88D | mxgraph.aws4.transcribe | Amazon Transcribe |
| transit_gateway | networking | #8C4FFF | mxgraph.aws4.transit_gateway | AWS Transit Gateway |
| translate | ml | #01A88D | mxgraph.aws4.translate | Amazon Translate |
| trusted_advisor | management | #E7157B | mxgraph.aws4.trusted_advisor | AWS Trusted Advisor |
| user | general | #232F3E | mxgraph.aws4.user | User |
| users | general | #232F3E | mxgraph.aws4.users | Users |
| verified_access | security | #DD344C | mxgraph.aws4.verified_access | AWS Verified Access |
| vpc | networking | #8C4FFF | mxgraph.aws4.vpc | Amazon VPC |
| vpc_privatelink | networking | #8C4FFF | mxgraph.aws4.vpc_privatelink | AWS PrivateLink |
| vpn | networking | #8C4FFF | mxgraph.aws4.vpn | AWS VPN |
| waf | security | #DD344C | mxgraph.aws4.waf | AWS WAF |
| wavelength | compute | #ED7100 | mxgraph.aws4.wavelength | AWS Wavelength |
| x_ray | management | #E7157B | mxgraph.aws4.x_ray | AWS X-Ray |

## Adding a new AWS service
1. Add the entry to `_AWS` in `shapes.py` (`key: (stencil_suffix, category, label)`).
2. Add a matching row to this table.
3. Run `pytest` to confirm no drift.
