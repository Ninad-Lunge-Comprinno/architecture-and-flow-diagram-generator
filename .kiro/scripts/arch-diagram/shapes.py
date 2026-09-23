"""Shape and color catalog for the Architecture Diagram Generator.

This module is the SINGLE SOURCE OF TRUTH for:
  - cloud service -> draw.io stencil name + fill color + category
  - container definitions (AWS Cloud, Region, VPC, Availability Zone, subnets)

The human-readable reference markdown files under
``.kiro/skills/arch-diagram/references/shapes-*.md`` mirror this catalog.
A consistency test guards against drift between the two.

Stencil naming (confirmed from the official draw.io style reference and the
example diagrams in ``diagram examples/``):

  AWS resource icon:  shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.<name>
  AWS container:      shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_<type>
  Azure resource:     shape=mxgraph.azure.<name>
  GCP resource:       shape=mxgraph.gcp2.<name>
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Category -> fill color (AWS 2020 palette, taken from the example diagrams)
# --------------------------------------------------------------------------
AWS_CATEGORY_COLORS = {
    "compute": "#ED7100",
    "containers": "#ED7100",
    "database": "#C925D1",
    "networking": "#8C4FFF",
    "storage": "#7AA116",
    "security": "#DD344C",
    "management": "#E7157B",
    "analytics": "#E7157B",
    "ml": "#01A88D",
    "integration": "#E7157B",
    "devtools": "#C925D1",
    "iot": "#7AA116",
    "general": "#232F3E",
}

FONT_COLOR = "#232F3E"
WHITE = "#ffffff"


@dataclass(frozen=True)
class Shape:
    """A resolved cloud-service shape."""

    provider: str
    key: str
    stencil: str      # e.g. "mxgraph.aws4.ec2"
    fill: str         # hex color
    category: str
    label: str        # default human label

    def style(self, font_size: int = 18, label_width: int = 160) -> str:
        """Return the draw.io style string for this shape.

        Labels wrap within ``label_width`` (wider than the 120px icon) so long
        service names break onto a second line instead of overflowing.
        """
        if self.provider == "aws":
            return (
                "sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],"
                "[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],"
                "[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];outlineConnect=0;"
                f"fontColor={FONT_COLOR};fillColor={self.fill};strokeColor={WHITE};"
                "dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;"
                f"html=1;whiteSpace=wrap;labelWidth={label_width};spacingTop=2;"
                f"fontSize={font_size};fontStyle=0;aspect=fixed;"
                f"shape=mxgraph.aws4.resourceIcon;resIcon={self.stencil};"
            )
        # Azure / GCP stencils are self-contained shape references.
        return (
            "sketch=0;outlineConnect=0;"
            f"fontColor={FONT_COLOR};fillColor={self.fill};strokeColor={WHITE};"
            "dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;"
            f"html=1;whiteSpace=wrap;labelWidth={label_width};spacingTop=2;"
            f"fontSize={font_size};fontStyle=0;aspect=fixed;shape={self.stencil};"
        )


# --------------------------------------------------------------------------
# AWS catalog: key -> (stencil-suffix, category, default label)
# The stencil name becomes "mxgraph.aws4.<suffix>".
# Covers all major AWS service families. When a service is NOT listed here,
# get_shape_dynamic() derives a best-effort shape — see below.
# --------------------------------------------------------------------------
_AWS = {
    # ---- Compute ---------------------------------------------------------
    "ec2": ("ec2", "compute", "Amazon EC2"),
    "lambda": ("lambda", "compute", "AWS Lambda"),
    "elastic_beanstalk": ("elastic_beanstalk", "compute", "AWS Elastic Beanstalk"),
    "batch": ("batch", "compute", "AWS Batch"),
    "lightsail": ("lightsail", "compute", "Amazon Lightsail"),
    "outposts": ("outposts", "compute", "AWS Outposts"),
    "wavelength": ("wavelength", "compute", "AWS Wavelength"),
    # ---- Containers ------------------------------------------------------
    "ecs": ("ecs", "containers", "Amazon ECS"),
    "eks": ("eks", "containers", "Amazon EKS"),
    "fargate": ("fargate", "containers", "AWS Fargate"),
    "ecr": ("ecr", "containers", "Amazon ECR"),
    "app_runner": ("app_runner", "containers", "AWS App Runner"),
    # ---- Networking & CDN ------------------------------------------------
    "vpc": ("vpc", "networking", "Amazon VPC"),
    "application_load_balancer": ("application_load_balancer", "networking", "Application Load Balancer"),
    "network_load_balancer": ("network_load_balancer", "networking", "Network Load Balancer"),
    "classic_load_balancer": ("classic_load_balancer", "networking", "Classic Load Balancer"),
    "nat_gateway": ("nat_gateway", "networking", "NAT Gateway"),
    "internet_gateway": ("internet_gateway", "networking", "Internet Gateway"),
    "cloudfront": ("cloudfront", "networking", "Amazon CloudFront"),
    "route_53": ("route_53", "networking", "Amazon Route 53"),
    "api_gateway": ("api_gateway", "networking", "Amazon API Gateway"),
    "endpoints": ("endpoints", "networking", "VPC Endpoints"),
    "vpc_privatelink": ("vpc_privatelink", "networking", "AWS PrivateLink"),
    "direct_connect": ("direct_connect", "networking", "AWS Direct Connect"),
    "transit_gateway": ("transit_gateway", "networking", "AWS Transit Gateway"),
    "vpn": ("vpn", "networking", "AWS VPN"),
    "global_accelerator": ("global_accelerator", "networking", "AWS Global Accelerator"),
    "elastic_load_balancing": ("elastic_load_balancing", "networking", "Elastic Load Balancing"),
    # ---- Database --------------------------------------------------------
    "rds": ("rds", "database", "Amazon RDS"),
    "aurora": ("aurora", "database", "Amazon Aurora"),
    "elasticache": ("elasticache", "database", "Amazon ElastiCache"),
    "dynamodb": ("dynamodb", "database", "Amazon DynamoDB"),
    "redshift": ("redshift", "database", "Amazon Redshift"),
    "documentdb": ("documentdb", "database", "Amazon DocumentDB"),
    "keyspaces": ("keyspaces", "database", "Amazon Keyspaces"),
    "neptune": ("neptune", "database", "Amazon Neptune"),
    "timestream": ("timestream", "database", "Amazon Timestream"),
    "memorydb": ("memorydb", "database", "Amazon MemoryDB"),
    "database_migration_service": ("database_migration_service", "database", "AWS DMS"),
    # ---- Storage ---------------------------------------------------------
    "s3": ("s3", "storage", "Amazon S3"),
    "efs": ("efs", "storage", "Amazon EFS"),
    "fsx": ("fsx", "storage", "Amazon FSx"),
    "s3_glacier": ("s3_glacier", "storage", "Amazon S3 Glacier"),
    "storage_gateway": ("storage_gateway", "storage", "AWS Storage Gateway"),
    "backup": ("backup", "storage", "AWS Backup"),
    "ebs": ("ebs", "storage", "Amazon EBS"),
    "snow_family": ("snow_family", "storage", "AWS Snow Family"),
    "datasync": ("datasync", "storage", "AWS DataSync"),
    # ---- Security & Compliance -------------------------------------------
    "waf": ("waf", "security", "AWS WAF"),
    "key_management_service": ("key_management_service", "security", "AWS KMS"),
    "identity_and_access_management": ("identity_and_access_management", "security", "AWS IAM"),
    "guardduty": ("guardduty", "security", "Amazon GuardDuty"),
    "security_hub": ("security_hub", "security", "AWS Security Hub"),
    "certificate_manager_3": ("certificate_manager_3", "security", "AWS Certificate Manager"),
    "secrets_manager": ("secrets_manager", "security", "AWS Secrets Manager"),
    "single_sign_on": ("single_sign_on", "security", "AWS IAM Identity Center"),
    "inspector": ("inspector", "security", "Amazon Inspector"),
    "macie": ("macie", "security", "Amazon Macie"),
    "shield": ("shield", "security", "AWS Shield"),
    "firewall_manager": ("firewall_manager", "security", "AWS Firewall Manager"),
    "network_firewall": ("network_firewall", "security", "AWS Network Firewall"),
    "cognito": ("cognito", "security", "Amazon Cognito"),
    "verified_access": ("verified_access", "security", "AWS Verified Access"),
    "detective": ("detective", "security", "Amazon Detective"),
    # ---- Management & Governance -----------------------------------------
    "cloudwatch_2": ("cloudwatch_2", "management", "Amazon CloudWatch"),
    "cloudtrail": ("cloudtrail", "management", "AWS CloudTrail"),
    "config": ("config", "management", "AWS Config"),
    "systems_manager": ("systems_manager", "management", "AWS Systems Manager"),
    "organizations": ("organizations", "management", "AWS Organizations"),
    "cloudformation": ("cloudformation", "management", "AWS CloudFormation"),
    "service_catalog": ("service_catalog", "management", "AWS Service Catalog"),
    "control_tower": ("control_tower", "management", "AWS Control Tower"),
    "auto_scaling2": ("auto_scaling2", "management", "AWS Auto Scaling"),
    "trusted_advisor": ("trusted_advisor", "management", "AWS Trusted Advisor"),
    "health": ("health", "management", "AWS Health"),
    "managed_grafana": ("managed_grafana", "management", "Amazon Managed Grafana"),
    "x_ray": ("x_ray", "management", "AWS X-Ray"),
    "personal_health_dashboard": ("personal_health_dashboard", "management", "AWS Personal Health Dashboard"),
    # ---- Integration & Messaging -----------------------------------------
    "sns": ("sns", "integration", "Amazon SNS"),
    "sqs": ("sqs", "integration", "Amazon SQS"),
    "eventbridge": ("eventbridge", "integration", "Amazon EventBridge"),
    "step_functions": ("step_functions", "integration", "AWS Step Functions"),
    "mq": ("mq", "integration", "Amazon MQ"),
    "appflow": ("appflow", "integration", "Amazon AppFlow"),
    "kinesis": ("kinesis", "integration", "Amazon Kinesis"),
    "kinesis_data_streams": ("kinesis_data_streams", "integration", "Amazon Kinesis Data Streams"),
    "kinesis_data_firehose": ("kinesis_data_firehose", "integration", "Amazon Kinesis Data Firehose"),
    "kinesis_data_analytics": ("kinesis_data_analytics", "integration", "Amazon Kinesis Data Analytics"),
    "ses": ("ses", "integration", "Amazon SES"),
    "pinpoint": ("pinpoint", "integration", "Amazon Pinpoint"),
    "connect": ("connect", "integration", "Amazon Connect"),
    # ---- Analytics -------------------------------------------------------
    "elasticsearch_service": ("elasticsearch_service", "analytics", "Amazon OpenSearch"),
    "athena": ("athena", "analytics", "Amazon Athena"),
    "glue": ("glue", "analytics", "AWS Glue"),
    "emr": ("emr", "analytics", "Amazon EMR"),
    "quicksight": ("quicksight", "analytics", "Amazon QuickSight"),
    "lake_formation": ("lake_formation", "analytics", "AWS Lake Formation"),
    "data_pipeline": ("data_pipeline", "analytics", "AWS Data Pipeline"),
    "managed_streaming_for_kafka": ("managed_streaming_for_kafka", "analytics", "Amazon MSK"),
    "clean_rooms": ("clean_rooms", "analytics", "AWS Clean Rooms"),
    # ---- ML & AI ---------------------------------------------------------
    "bedrock": ("bedrock", "ml", "Amazon Bedrock"),
    "sagemaker": ("sagemaker", "ml", "Amazon SageMaker"),
    "transcribe": ("transcribe", "ml", "Amazon Transcribe"),
    "rekognition_2": ("rekognition_2", "ml", "Amazon Rekognition"),
    "polly": ("polly", "ml", "Amazon Polly"),
    "comprehend": ("comprehend", "ml", "Amazon Comprehend"),
    "translate": ("translate", "ml", "Amazon Translate"),
    "textract": ("textract", "ml", "Amazon Textract"),
    "forecast": ("forecast", "ml", "Amazon Forecast"),
    "personalize": ("personalize", "ml", "Amazon Personalize"),
    "kendra": ("kendra", "ml", "Amazon Kendra"),
    "lex_v2": ("lex_v2", "ml", "Amazon Lex"),
    "codeguru": ("codeguru", "ml", "Amazon CodeGuru"),
    "deepracer": ("deepracer", "ml", "AWS DeepRacer"),
    # ---- Developer Tools -------------------------------------------------
    "codepipeline": ("codepipeline", "devtools", "AWS CodePipeline"),
    "codebuild": ("codebuild", "devtools", "AWS CodeBuild"),
    "codedeploy": ("codedeploy", "devtools", "AWS CodeDeploy"),
    "codecommit": ("codecommit", "devtools", "AWS CodeCommit"),
    "cloud9": ("cloud9", "devtools", "AWS Cloud9"),
    "codeartifact": ("codeartifact", "devtools", "AWS CodeArtifact"),
    "codestar": ("codestar", "devtools", "AWS CodeStar"),
    "amplify": ("amplify", "devtools", "AWS Amplify"),
    # ---- IoT -------------------------------------------------------------
    "iot_core": ("iot_core", "iot", "AWS IoT Core"),
    "iot_greengrass": ("iot_greengrass", "iot", "AWS IoT Greengrass"),
    "iot_sitewise": ("iot_sitewise", "iot", "AWS IoT SiteWise"),
    "iot_events": ("iot_events", "iot", "AWS IoT Events"),
    "iot_analytics": ("iot_analytics", "iot", "AWS IoT Analytics"),
    # ---- General / Diagramming ------------------------------------------
    "user": ("user", "general", "User"),
    "users": ("users", "general", "Users"),
    "mobile_client": ("mobile_client", "general", "Mobile Client"),
    "traditional_server": ("traditional_server", "general", "Traditional Server"),
    "corporate_data_center": ("corporate_data_center", "general", "Corporate Data Center"),
    "internet": ("internet", "general", "Internet"),
    # ---- Application Integration -----------------------------------------
    "appsync": ("appsync", "integration", "AWS AppSync"),
    "api_gateway_v2": ("api_gateway", "networking", "Amazon API Gateway"),
    # ---- Media -----------------------------------------------------------
    "elemental_mediaconvert": ("elemental_mediaconvert", "management", "AWS Elemental MediaConvert"),
    "interactive_video_service": ("interactive_video_service", "management", "Amazon IVS"),
}

# --------------------------------------------------------------------------
# Azure starter catalog: key -> (stencil, fill, category, label)
# --------------------------------------------------------------------------
_AZURE = {
    "virtual_machine": ("mxgraph.azure.virtual_machine", "#0079D6", "compute", "Virtual Machine"),
    "app_service": ("mxgraph.azure.app_services", "#0079D6", "compute", "App Service"),
    "function_app": ("mxgraph.azure.function_apps", "#0079D6", "compute", "Function App"),
    "sql_database": ("mxgraph.azure.sql_database", "#0079D6", "database", "Azure SQL Database"),
    "cosmos_db": ("mxgraph.azure.azure_cosmos_db", "#0079D6", "database", "Cosmos DB"),
    "blob_storage": ("mxgraph.azure.blob_storage", "#0079D6", "storage", "Blob Storage"),
    "virtual_network": ("mxgraph.azure.virtual_networks", "#0079D6", "networking", "Virtual Network"),
    "load_balancer": ("mxgraph.azure.load_balancer", "#0079D6", "networking", "Load Balancer"),
    "application_gateway": ("mxgraph.azure.application_gateway", "#0079D6", "networking", "Application Gateway"),
    "key_vault": ("mxgraph.azure.key_vault", "#0079D6", "security", "Key Vault"),
    "aks": ("mxgraph.azure.azure_kubernetes_service", "#0079D6", "containers", "AKS"),
}

# --------------------------------------------------------------------------
# GCP starter catalog: key -> (stencil, fill, category, label)
# --------------------------------------------------------------------------
_GCP = {
    "compute_engine": ("mxgraph.gcp2.compute_engine", "#4285F4", "compute", "Compute Engine"),
    "cloud_functions": ("mxgraph.gcp2.cloud_functions", "#4285F4", "compute", "Cloud Functions"),
    "cloud_run": ("mxgraph.gcp2.cloud_run", "#4285F4", "compute", "Cloud Run"),
    "gke": ("mxgraph.gcp2.google_kubernetes_engine", "#4285F4", "containers", "GKE"),
    "cloud_sql": ("mxgraph.gcp2.cloud_sql", "#4285F4", "database", "Cloud SQL"),
    "firestore": ("mxgraph.gcp2.cloud_firestore", "#4285F4", "database", "Firestore"),
    "cloud_storage": ("mxgraph.gcp2.cloud_storage", "#4285F4", "storage", "Cloud Storage"),
    "vpc_network": ("mxgraph.gcp2.virtual_private_cloud", "#4285F4", "networking", "VPC Network"),
    "cloud_load_balancing": ("mxgraph.gcp2.cloud_load_balancing", "#4285F4", "networking", "Cloud Load Balancing"),
    "cloud_cdn": ("mxgraph.gcp2.cloud_cdn", "#4285F4", "networking", "Cloud CDN"),
    "cloud_iam": ("mxgraph.gcp2.cloud_iam", "#4285F4", "security", "Cloud IAM"),
}


class UnknownServiceError(KeyError):
    """Raised when a (provider, service) pair is not in the catalog."""


def _build_catalog() -> dict[str, dict[str, Shape]]:
    catalog: dict[str, dict[str, Shape]] = {"aws": {}, "azure": {}, "gcp": {}}
    for key, (suffix, category, label) in _AWS.items():
        catalog["aws"][key] = Shape(
            provider="aws",
            key=key,
            stencil=f"mxgraph.aws4.{suffix}",
            fill=AWS_CATEGORY_COLORS[category],
            category=category,
            label=label,
        )
    for key, (stencil, fill, category, label) in _AZURE.items():
        catalog["azure"][key] = Shape("azure", key, stencil, fill, category, label)
    for key, (stencil, fill, category, label) in _GCP.items():
        catalog["gcp"][key] = Shape("gcp", key, stencil, fill, category, label)
    return catalog


CATALOG = _build_catalog()

PROVIDERS = tuple(CATALOG.keys())


def get_shape(provider: str, service: str) -> Shape:
    """Look up a shape by provider and service key.

    For AWS, if the key is not in the static catalog, falls back to
    ``get_shape_dynamic()`` which derives a best-effort shape from the key
    name — so this function never raises for AWS services.

    Raises ``UnknownServiceError`` only for unknown providers or for
    Azure/GCP services not in the starter catalog.
    """
    provider = provider.lower()
    if provider not in CATALOG:
        raise UnknownServiceError(
            f"Unknown provider {provider!r}. Known providers: {', '.join(PROVIDERS)}."
        )
    services = CATALOG[provider]
    if service in services:
        return services[service]
    if provider == "aws":
        return get_shape_dynamic(service)
    raise UnknownServiceError(
        f"Unknown {provider} service {service!r}. "
        f"See references/shapes-{provider}.md for valid keys."
    )


# --- Keyword maps for dynamic category inference --------------------------
_KEYWORD_CATEGORY = [
    ({"lambda", "ec2", "batch", "lightsail", "beanstalk", "compute",
      "fargate", "app_runner"}, "compute"),
    ({"ecs", "eks", "ecr", "container", "kubernetes", "docker"}, "containers"),
    ({"rds", "aurora", "dynamodb", "elasticache", "redshift", "documentdb",
      "neptune", "timestream", "keyspaces", "database", "db", "sql",
      "memorydb", "dax"}, "database"),
    ({"s3", "efs", "fsx", "ebs", "glacier", "storage", "backup",
      "datasync", "snow"}, "storage"),
    ({"waf", "kms", "iam", "guardduty", "security_hub", "certificate",
      "secrets", "shield", "macie", "inspector", "cognito", "firewall",
      "detective", "verified_access", "security", "identity"}, "security"),
    ({"cloudwatch", "cloudtrail", "config", "systems_manager", "ssm",
      "cloudformation", "control_tower", "service_catalog", "auto_scaling",
      "trusted_advisor", "health", "monitoring", "grafana", "xray",
      "management", "governance", "cost"}, "management"),
    ({"eventbridge", "sns", "sqs", "step_functions", "mq", "ses",
      "kinesis", "appflow", "connect", "pinpoint", "appsync",
      "integration", "messaging", "queue", "event", "notification",
      "workflow"}, "integration"),
    ({"athena", "glue", "emr", "quicksight", "lake_formation", "kafka",
      "msk", "opensearch", "elasticsearch", "analytics", "redshift",
      "clean_rooms", "data"}, "analytics"),
    ({"bedrock", "sagemaker", "transcribe", "rekognition", "polly",
      "comprehend", "translate", "textract", "forecast", "personalize",
      "kendra", "lex", "codeguru", "ml", "ai", "machine_learning",
      "deep_learning", "inference"}, "ml"),
    ({"codepipeline", "codebuild", "codedeploy", "codecommit", "cloud9",
      "codeartifact", "codestar", "amplify", "cicd", "devops",
      "developer"}, "devtools"),
    ({"iot", "greengrass", "sitewise", "thing", "sensor"}, "iot"),
    ({"cloudfront", "route53", "vpc", "alb", "nlb", "nat", "igw",
      "gateway", "load_balancer", "direct_connect", "transit_gateway",
      "vpn", "accelerator", "cdn", "network", "dns", "endpoint",
      "privatelink"}, "networking"),
]


def _infer_category(key: str) -> str:
    """Infer the AWS service category from its key name."""
    key_lower = key.lower()
    key_parts = set(key_lower.split("_") + [key_lower])
    for keywords, category in _KEYWORD_CATEGORY:
        if key_parts & keywords:
            return category
        # substring match
        for kw in keywords:
            if kw in key_lower:
                return category
    return "general"


def get_shape_dynamic(service: str) -> Shape:
    """Derive a best-effort draw.io shape for any AWS service key.

    The AWS draw.io stencil library (`mxgraph.aws4.*`) covers hundreds of
    services using the exact service key as the stencil suffix. If the
    stencil doesn't exist in draw.io, the orthogonal router will still place
    a generic icon that the user can manually swap.

    This function:
    1. Infers the service category from keyword patterns in the key name.
    2. Assigns the corresponding category color.
    3. Uses the key directly as the stencil suffix (mxgraph.aws4.<key>).
    4. Adds the derived shape to the live catalog so future lookups are free.
    """
    category = _infer_category(service)
    fill = AWS_CATEGORY_COLORS.get(category, AWS_CATEGORY_COLORS["general"])
    stencil = f"mxgraph.aws4.{service}"
    # Convert key to a human-readable label
    label = "AWS " + service.replace("_", " ").title()
    shape = Shape(
        provider="aws",
        key=service,
        stencil=stencil,
        fill=fill,
        category=category,
        label=label,
    )
    # Cache so repeated calls are O(1) and downstream code can enumerate it.
    CATALOG["aws"][service] = shape
    return shape


def list_services(provider: str) -> list[str]:
    """Return the sorted service keys available for a provider."""
    provider = provider.lower()
    if provider not in CATALOG:
        raise UnknownServiceError(f"Unknown provider {provider!r}.")
    return sorted(CATALOG[provider])


# --------------------------------------------------------------------------
# Container definitions: kind -> style builder
# Mirrors the AWS group stencils and colors from the example diagrams.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Container:
    kind: str
    stencil: str          # grIcon value, or "" for a plain rectangle group
    stroke: str
    fill: str             # "none" for transparent
    font_color: str
    dashed: bool
    label: str

    def style(self, font_size: int = 18) -> str:
        dash = "1" if self.dashed else "0"
        if self.stencil:
            return (
                "sketch=0;outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;"
                f"fontSize={font_size};fontStyle=0;container=1;pointerEvents=0;"
                "collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
                f"grIcon={self.stencil};strokeColor={self.stroke};fillColor={self.fill};"
                f"verticalAlign=top;align=left;spacingLeft=30;fontColor={self.font_color};"
                f"dashed={dash};strokeWidth=2;"
            )
        # Plain rectangle container (e.g. logical cluster/lane boxes).
        # Label is placed at the BOTTOM (verticalAlign=bottom) so it does not
        # overlap the app-subnet label, which renders at the TOP of the subnet
        # box that the lane overhangs into.
        return (
            "rounded=0;whiteSpace=wrap;html=1;container=1;collapsible=0;"
            f"strokeColor={self.stroke};fillColor={self.fill};verticalAlign=bottom;"
            f"fontColor={self.font_color};dashed={dash};strokeWidth=2;"
            f"fontSize={font_size};spacingBottom=5;"
        )


_CONTAINERS = {
    "cloud": Container(
        "cloud", "mxgraph.aws4.group_aws_cloud_alt", "#232F3E", "none", "#232F3E", False, "AWS Cloud"
    ),
    "region": Container(
        "region", "mxgraph.aws4.group_region", "#147EBA", "none", "#147EBA", True, "Region"
    ),
    "vpc": Container(
        "vpc", "mxgraph.aws4.group_vpc", "#248814", "none", "#232F3E", False, "VPC"
    ),
    "az": Container(
        "az", "mxgraph.aws4.group_availability_zone", "#545B64", "none", "#545B64", True, "Availability Zone"
    ),
    "public_subnet": Container(
        "public_subnet", "mxgraph.aws4.group_security_group", "#248814", "#E9F3E6", "#248814", False, "Public Subnet"
    ),
    "app_subnet": Container(
        "app_subnet", "mxgraph.aws4.group_security_group", "#147EBA", "#E6F2F8", "#147EBA", False, "App Subnet"
    ),
    "db_subnet": Container(
        "db_subnet", "mxgraph.aws4.group_security_group", "#147EBA", "#CCE5FF", "#147EBA", False, "DB Subnet"
    ),
    "account": Container(
        "account", "mxgraph.aws4.group_account", "#E7157B", "none", "#E7157B", False, "AWS Account"
    ),
    # Generic logical box (used for ECS/EKS clusters, auto scaling groups, etc.)
    "cluster": Container(
        "cluster", "", "#FF8000", "none", "#5A6C86", False, "Cluster"
    ),
    # Compute-grouping boxes placed inside a subnet.
    "ecs_cluster": Container(
        "ecs_cluster", "", "#FF8000", "none", "#5A6C86", False, "ECS Cluster"
    ),
    "eks_cluster": Container(
        "eks_cluster", "", "#FF8000", "none", "#5A6C86", False, "EKS Cluster"
    ),
    "asg": Container(
        "asg", "mxgraph.aws4.group_auto_scaling_group", "#D86613", "none", "#D86613", True, "Auto Scaling Group"
    ),
}

# subnet kinds recognised for convenience
SUBNET_KINDS = ("public_subnet", "app_subnet", "db_subnet")

# cluster kinds that can live inside a subnet and hold compute resources
CLUSTER_KINDS = ("cluster", "ecs_cluster", "eks_cluster", "asg")


class UnknownContainerError(KeyError):
    """Raised when a container kind is not defined."""


def get_container(kind: str) -> Container:
    """Look up a container definition by kind."""
    if kind not in _CONTAINERS:
        raise UnknownContainerError(
            f"Unknown container kind {kind!r}. Known kinds: {', '.join(sorted(_CONTAINERS))}."
        )
    return _CONTAINERS[kind]


def list_containers() -> list[str]:
    return sorted(_CONTAINERS)
