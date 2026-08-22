"""Minimal stdlib CLI: build a resilience map or propose impact tolerances (argparse only)."""

from __future__ import annotations

import argparse
import sys

from hex_service_kit.logging import configure_logging

from ..config import build_container
from ..domain.models import ImportantBusinessService, Regulator
from ..factory import build_studio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operational_resilience_mapping")
    sub = parser.add_subparsers(dest="command", required=True)

    map_cmd = sub.add_parser("map", help="Build the resilience map for a business service.")
    map_cmd.add_argument("service_id")
    map_cmd.add_argument("service_name")
    map_cmd.add_argument("--scope", default="projects/fictional")
    map_cmd.add_argument("--actor", default="cli-user@bank.example")
    map_cmd.add_argument("--tenant", default="")

    tol_cmd = sub.add_parser("tolerance", help="Propose impact tolerances (routes to Hrz7).")
    tol_cmd.add_argument("service_id")
    tol_cmd.add_argument("service_name")
    tol_cmd.add_argument("--regulator", default="APRA_CPS230", choices=[r.value for r in Regulator])
    tol_cmd.add_argument("--scope", default="projects/fictional")
    tol_cmd.add_argument("--actor", default="cli-user@bank.example")
    tol_cmd.add_argument("--tenant", default="")

    args = parser.parse_args(argv)
    container = build_container()
    # Idempotent: a process that is both an API app and a CLI configures once.
    configure_logging(container.settings.profile, service="operational-resilience-mapping")
    studio = build_studio(container)
    service = ImportantBusinessService(id=args.service_id, name=args.service_name)

    if args.command == "map":
        resilience_map, reconciliation, gaps = studio.build_map(
            service, args.scope, actor=args.actor, tenant=args.tenant
        )
        print(f"{service.name}: {resilience_map.n_nodes} nodes, {resilience_map.n_edges} edges")
        print(f"  accepted edges: {len(reconciliation.accepted)}")
        print(f"  reconciliation gaps: {len(reconciliation.gaps)}; integrity gaps: {len(gaps)}")
        return 0

    if args.command == "tolerance":
        resilience_map, _reconciliation, _gaps = studio.build_map(
            service, args.scope, actor=args.actor, tenant=args.tenant
        )
        proposal, review_ref = studio.propose_tolerances(
            service, resilience_map, Regulator(args.regulator), actor=args.actor, tenant=args.tenant
        )
        print(f"{service.name}: proposed {len(proposal.tolerances)} tolerances")
        for tolerance in proposal.tolerances:
            print(f"  {tolerance.metric.value.upper()}: {tolerance.value} {tolerance.unit}")
        print(f"  requires_human_review: {proposal.requires_human_review}")
        print(f"  routed to human review: {review_ref}")
        return 0

    return 2  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
