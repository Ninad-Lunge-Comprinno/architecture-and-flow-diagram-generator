"""Tests for dynamic service catalog: expanded catalog + dynamic fallback."""

import shapes


def test_catalog_exceeds_100_services():
    assert len(shapes.list_services("aws")) >= 100, \
        f"Expected 100+ AWS services, got {len(shapes.list_services('aws'))}"


def test_new_catalog_services_present():
    """Services added in the expanded catalog should be resolvable."""
    new_services = [
        "eventbridge", "athena", "glue", "emr", "quicksight",
        "kinesis", "sqs", "ses", "cognito", "codecommit",
        "amplify", "neptune", "redshift", "documentdb",
        "direct_connect", "transit_gateway", "network_load_balancer",
        "cloudformation", "ecs", "auto_scaling2",
        "iot_greengrass", "iot_sitewise", "comprehend",
        "textract", "kendra", "appsync",
    ]
    for svc in new_services:
        s = shapes.get_shape("aws", svc)
        assert s.stencil.startswith("mxgraph.aws4."), \
            f"{svc}: unexpected stencil {s.stencil}"


def test_dynamic_fallback_never_crashes():
    """Any unknown AWS service key should return a valid Shape, not raise."""
    unknown_services = [
        "some_new_service_2027",
        "quantum_computing",
        "holographic_database",
        "ai_agent_runtime",
    ]
    for svc in unknown_services:
        s = shapes.get_shape("aws", svc)
        assert isinstance(s, shapes.Shape)
        assert s.stencil == f"mxgraph.aws4.{svc}"
        assert s.fill in shapes.AWS_CATEGORY_COLORS.values()


def test_dynamic_fallback_infers_correct_category():
    """Category inference from keyword patterns should be accurate."""
    assert shapes.get_shape("aws", "my_custom_database").category == "database"
    assert shapes.get_shape("aws", "new_ml_service").category == "ml"
    assert shapes.get_shape("aws", "advanced_networking_tool").category == "networking"
    assert shapes.get_shape("aws", "iot_custom_device").category == "iot"
    assert shapes.get_shape("aws", "my_storage_vault").category == "storage"
    assert shapes.get_shape("aws", "custom_security_scanner").category == "security"


def test_dynamic_fallback_cached():
    """A dynamically-resolved service should be cached for subsequent lookups."""
    svc = "unique_service_for_cache_test_xyz"
    s1 = shapes.get_shape("aws", svc)
    s2 = shapes.get_shape("aws", svc)
    assert s1 is s2, "Second lookup should return the same cached object"


def test_dynamic_fallback_generates_valid_style():
    """Dynamically derived shapes should produce a valid draw.io style string."""
    s = shapes.get_shape("aws", "future_aws_service")
    style = s.style()
    assert "shape=mxgraph.aws4.resourceIcon" in style
    assert "resIcon=mxgraph.aws4.future_aws_service" in style
    assert "fillColor=" in style


def test_unknown_provider_still_raises():
    """Unknown providers should still raise — only AWS gets the dynamic fallback."""
    import pytest
    with pytest.raises(shapes.UnknownServiceError):
        shapes.get_shape("oracle", "database")


def test_unknown_azure_service_still_raises():
    """Unknown Azure/GCP services still raise (no dynamic fallback for them)."""
    import pytest
    with pytest.raises(shapes.UnknownServiceError):
        shapes.get_shape("azure", "nonexistent_azure_service_xyz")
