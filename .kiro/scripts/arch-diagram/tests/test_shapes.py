"""Tests for shapes.py lookups and style generation."""

import pytest

import shapes


def test_aws_ec2_lookup():
    s = shapes.get_shape("aws", "ec2")
    assert s.stencil == "mxgraph.aws4.ec2"
    assert s.fill == "#ED7100"
    assert s.category == "compute"


def test_aws_rds_lookup():
    s = shapes.get_shape("aws", "rds")
    assert s.stencil == "mxgraph.aws4.rds"
    assert s.fill == "#C925D1"
    assert s.category == "database"


def test_aws_networking_color():
    assert shapes.get_shape("aws", "cloudfront").fill == "#8C4FFF"
    assert shapes.get_shape("aws", "route_53").fill == "#8C4FFF"


def test_aws_security_color():
    assert shapes.get_shape("aws", "waf").fill == "#DD344C"


def test_aws_storage_color():
    assert shapes.get_shape("aws", "s3").fill == "#7AA116"


def test_provider_case_insensitive():
    assert shapes.get_shape("AWS", "ec2").key == "ec2"


def test_azure_lookup():
    s = shapes.get_shape("azure", "virtual_machine")
    assert s.stencil.startswith("mxgraph.azure.")
    assert s.provider == "azure"


def test_gcp_lookup():
    s = shapes.get_shape("gcp", "compute_engine")
    assert s.stencil.startswith("mxgraph.gcp2.")
    assert s.provider == "gcp"


def test_unknown_service_raises():
    with pytest.raises(shapes.UnknownServiceError) as exc:
        shapes.get_shape("aws", "does_not_exist")
    assert "does_not_exist" in str(exc.value)


def test_unknown_provider_raises():
    with pytest.raises(shapes.UnknownServiceError):
        shapes.get_shape("oracle", "ec2")


def test_aws_style_string_contains_resicon():
    style = shapes.get_shape("aws", "ec2").style()
    assert "shape=mxgraph.aws4.resourceIcon" in style
    assert "resIcon=mxgraph.aws4.ec2" in style
    assert "fillColor=#ED7100" in style


def test_azure_style_string():
    style = shapes.get_shape("azure", "sql_database").style()
    assert "shape=mxgraph.azure.sql_database" in style


def test_required_services_present():
    required = [
        "vpc", "ec2", "ecs", "eks", "fargate", "application_load_balancer",
        "nat_gateway", "internet_gateway", "rds", "aurora", "elasticache", "s3",
        "cloudfront", "route_53", "lambda", "api_gateway", "cloudwatch_2", "waf",
        "key_management_service", "identity_and_access_management", "bedrock",
        "sagemaker", "secrets_manager", "cloudtrail", "guardduty", "security_hub",
        "config", "systems_manager", "single_sign_on", "organizations",
        "certificate_manager_3", "ecr", "codepipeline", "codebuild", "codedeploy",
        "dynamodb", "backup", "elasticsearch_service", "transcribe",
        "rekognition_2", "polly", "iot_core", "sns", "endpoints",
        "vpc_privatelink", "user",
    ]
    have = set(shapes.list_services("aws"))
    missing = [k for k in required if k not in have]
    assert not missing, f"missing AWS services: {missing}"


def test_container_lookup():
    c = shapes.get_container("vpc")
    assert c.stencil == "mxgraph.aws4.group_vpc"
    assert "shape=mxgraph.aws4.group" in c.style()
    assert "grIcon=mxgraph.aws4.group_vpc" in c.style()


def test_container_dashed_region():
    assert "dashed=1" in shapes.get_container("region").style()


def test_unknown_container_raises():
    with pytest.raises(shapes.UnknownContainerError):
        shapes.get_container("nonsense")
