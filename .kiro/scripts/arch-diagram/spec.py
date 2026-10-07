"""Spec parsing, validation, and connectivity analysis.

This module owns the input-spec lifecycle for the diagram generator:

* parsing the spec into a normalized list of pages (`_normalize_pages`),
* validating providers, services, unique ids, and edges,
* collecting the architecture element ids used by layout and routing
  (`_collect_arch_ids`), and
* producing non-fatal connectivity warnings for architecture pages
  (`_architecture_connectivity_warnings`).

The shared `SpecError` exception lives here because it is raised across the
spec, architecture-page, and flow-page modules. Edge-style assembly
(`_edge_style`) also lives here since it is driven by the validated spec and
the `EDGE_STYLE` base string imported from the diagram module.
"""

from __future__ import annotations

import logging
from typing import Optional

import shapes

from diagram import EDGE_STYLE

logger = logging.getLogger("arch_diagram")


# --------------------------------------------------------------------------
# Full spec handling: parsing + validation + architecture pages.
# --------------------------------------------------------------------------
class SpecError(Exception):
    """Raised when the input spec is invalid, with a human-readable message."""


def _collect_arch_ids(page: dict) -> list[tuple[str, dict]]:
    """Collect (id, node) for every element in an architecture page.

    Walks the grid-model sections: global[], entry[], region.services[],
    region.vpc.azs[].{public_subnet,db_subnet}.resources[], and
    region.vpc.compute_groups[] (expanding one node per spanned AZ), plus
    cicd[]. Validates required fields and compute-group kinds.
    """
    out: list[tuple[str, dict]] = []

    def add_resource(res: dict, where: str):
        if "id" not in res:
            raise SpecError(f"A resource in {where} is missing its 'id'.")
        if "service" not in res:
            raise SpecError(f"Resource {res.get('id')!r} in {where} is missing 'service'.")
        out.append((res["id"], res))

    for res in page.get("global", []) or []:
        add_resource(res, "global")
    for res in page.get("edge", []) or []:
        add_resource(res, "edge")

    region = page.get("region", {}) or {}
    for res in region.get("services", []) or []:
        add_resource(res, "region.services")

    vpc = region.get("vpc", {}) or {}
    az_ids = [az["id"] for az in vpc.get("azs", []) or [] if "id" in az]
    for az in vpc.get("azs", []) or []:
        if "id" not in az:
            raise SpecError("An availability zone is missing its 'id'.")
        out.append((az["id"], az))
        for tier in ("public_subnet", "app_subnet", "db_subnet"):
            subnet = az.get(tier)
            if subnet:
                if "id" not in subnet:
                    raise SpecError(f"A {tier} in {az['id']!r} is missing its 'id'.")
                out.append((subnet["id"], subnet))
                for res in subnet.get("resources", []) or []:
                    add_resource(res, f"{tier} {subnet['id']!r}")

    for g in vpc.get("compute_groups", []) or []:
        if "id" not in g:
            raise SpecError("A compute_group is missing its 'id'.")
        kind = g.get("kind", "ecs_cluster")
        if kind not in shapes.CLUSTER_KINDS:
            raise SpecError(
                f"Compute group {g['id']!r} has invalid kind {kind!r}; "
                f"expected one of {', '.join(shapes.CLUSTER_KINDS)}."
            )
        if "node_service" not in g:
            raise SpecError(f"Compute group {g['id']!r} is missing 'node_service'.")
        out.append((g["id"], g))
        for az_id in g.get("azs", az_ids):
            node = {"id": f"{g['id']}-{az_id}", "service": g["node_service"],
                    "provider": g.get("provider")}
            out.append((node["id"], node))

    return out


def _validate_provider(provider: str) -> str:
    provider = str(provider).lower()
    if provider not in shapes.PROVIDERS:
        raise SpecError(
            f"Unknown provider {provider!r}; expected one of {', '.join(shapes.PROVIDERS)}."
        )
    return provider


def _validate_services(elements: list[tuple[str, dict]], default_provider: str) -> None:
    for _id, node in elements:
        service = node.get("service")
        if service is None:
            continue  # containers have no service
        provider = _validate_provider(node.get("provider") or default_provider)
        try:
            shapes.get_shape(provider, service)
            # For AWS: get_shape_dynamic() is called automatically on unknown keys
            # and never raises, so any AWS service key is accepted.
        except shapes.UnknownServiceError as exc:
            # Only Azure/GCP catalog misses raise here; AWS uses dynamic fallback.
            raise SpecError(str(exc)) from exc


def _check_unique_ids(elements: list[tuple[str, dict]], page_name: str) -> set[str]:
    seen: set[str] = set()
    for eid, _node in elements:
        if eid in seen:
            raise SpecError(f"Duplicate id {eid!r} on page {page_name!r}.")
        seen.add(eid)
    return seen


def _check_edges(edges: list[dict], ids: set[str], page_name: str) -> None:
    for edge in edges:
        for endpoint in ("source", "target"):
            if endpoint not in edge:
                raise SpecError(f"An edge on page {page_name!r} is missing '{endpoint}'.")
            if edge[endpoint] not in ids:
                raise SpecError(
                    f"Edge {endpoint} {edge[endpoint]!r} on page {page_name!r} "
                    "references an id that does not exist on the page."
                )


def _architecture_connectivity_warnings(page: dict) -> list[str]:
    """Flag common missing paths and AZ-specific targets on shared ingress."""
    elements = _collect_arch_ids(page)
    pairs = {(edge.get("source"), edge.get("target"))
             for edge in (page.get("edges", []) or [])}
    warnings: list[str] = []

    def ids_for(service: str) -> list[str]:
        return [node_id for node_id, node in elements if node.get("service") == service]

    actors = [node_id for node_id, node in elements
              if node.get("service") in {"user", "users", "mobile_client", "iot_device"}]
    cdns = ids_for("cloudfront")
    wafs = ids_for("waf")
    shields = ids_for("shield")
    igws = ids_for("internet_gateway")
    albs = [node_id for node_id, node in elements
            if node.get("service") in {"application_load_balancer", "network_load_balancer"}]

    adjacency: dict[str, set[str]] = {}
    for source, target in pairs:
        adjacency.setdefault(source, set()).add(target)

    def has_path(source: str, target: str) -> bool:
        pending, visited = [source], set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, set()) - visited)
        return False

    public_entry_services = {
        "cloudfront", "route_53", "api_gateway", "shield", "waf",
        "application_load_balancer", "network_load_balancer",
    }
    public_entries = [node_id for node_id, node in elements
                      if node.get("service") in public_entry_services]
    if actors and public_entries:
        for actor in actors:
            if not any(has_path(actor, entry) for entry in public_entries):
                warnings.append(
                    f"External actor {actor!r} has no path to a public entry service."
                )
    elif actors and (wafs or shields or albs):
        for actor in actors:
            if not any(has_path(actor, target) for target in (shields or wafs or albs)):
                warnings.append(
                    f"External actor {actor!r} has no edge to the ingress path."
                )

    origins = [node_id for node_id, node in elements
               if "origin" in f"{node_id} {node.get('label', '')}".lower()]
    for cdn in cdns:
        if origins and not any((cdn, origin) in pairs for origin in origins):
            warnings.append(
                f"CloudFront {cdn!r} has no edge to a named origin."
            )

    if wafs and igws and albs:
        if (wafs[0], igws[0]) not in pairs:
            warnings.append("Ingress path is missing the WAF → Internet Gateway connection.")
        if (igws[0], albs[0]) not in pairs:
            warnings.append("Ingress path is missing the Internet Gateway → load balancer connection.")

    vpc = (page.get("region", {}) or {}).get("vpc", {}) or {}
    groups = vpc.get("compute_groups", []) or []
    for group in groups:
        group_id = group.get("id")
        if not group_id or group.get("kind") not in {"ecs_cluster", "eks_cluster"}:
            continue
        az_children = {f"{group_id}-{az.get('id')}"
                       for az in (vpc.get("azs", []) or []) if az.get("id")}
        for alb in albs:
            for target in az_children:
                if (alb, target) in pairs:
                    explicit_az_route = any(
                        edge.get("source") == alb and edge.get("target") == target
                        and edge.get("az_specific") is True
                        for edge in (page.get("edges", []) or [])
                    )
                    if explicit_az_route:
                        continue
                    warnings.append(
                        f"Load balancer {alb!r} targets AZ task {target!r}; "
                        f"use shared cluster {group_id!r} unless the route is AZ-specific."
                    )
    return warnings


def _edge_style(edge: dict) -> str:
    style = EDGE_STYLE
    if edge.get("dashed"):
        style += "dashed=1;"
    if edge.get("style"):
        style += str(edge["style"])
        if not style.endswith(";"):
            style += ";"
    return style


def _normalize_pages(spec: dict) -> list[dict]:
    """Return a list of page dicts, supporting the single-page shorthand."""
    if "pages" in spec:
        pages = spec["pages"]
        if not pages:
            raise SpecError("Spec 'pages' is empty.")
        return pages
    # single-page shorthand: cloud/edges or nodes/edges at top level
    if "region" in spec:
        return [{"name": spec.get("metadata", {}).get("project", "Architecture Diagram"),
                 "type": "architecture",
                 "global": spec.get("global", []),
                 "edge": spec.get("edge", []),
                 "region": spec["region"],
                 "edges": spec.get("edges", [])}]
    if "nodes" in spec:
        return [{"name": "Flow Diagram", "type": "flow",
                 "nodes": spec["nodes"], "edges": spec.get("edges", [])}]
    raise SpecError("Spec must contain 'pages', or a top-level 'region'/'nodes'.")
