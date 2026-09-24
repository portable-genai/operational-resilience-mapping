"""Review routing has a switch, default on, and every caller says what happened to a hand-off.

The fleet's runtime-control contract (2026-09-24). Review routing is the one cheap runtime control
this service has: ``RESILIENCE_REVIEW_ROUTING`` is read in three states; off binds a disabled router
and says so at startup; on under the managed profile refuses to boot without a console; and the
tolerance route, the agent tool and the CLI report ``review_routing`` rather than failing an
already-audited result when the console is unreachable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from operational_resilience_mapping.adapters.controls import (
    DisabledReviewRouter,
    RecordingReviewRouter,
    ReviewRouting,
)
from operational_resilience_mapping.agent import tools
from operational_resilience_mapping.api import app as api_module
from operational_resilience_mapping.api.app import app
from operational_resilience_mapping.cli.main import main as cli_main
from operational_resilience_mapping.config import (
    REVIEW_ROUTING_ENV,
    Container,
    ControlSwitches,
    ProfileChoice,
    Settings,
    build_container,
    warn_switched_off,
)
from operational_resilience_mapping.domain.kernel import Decision, Severity
from operational_resilience_mapping.domain.models import ResilienceReview
from operational_resilience_mapping.envread import ConfiguredEmptyError

from tests.fixtures import sample_cases

_LOOPBACK = ("127.0.0.1", 50000)
_TOLERANCE: dict[str, object] = {
    "scope": sample_cases.SCOPE,
    "service_id": sample_cases.SERVICE.id,
    "service_name": sample_cases.SERVICE.name,
    "regulator": "APRA_CPS230",
}
_AUDITOR = {"X-Dev-Persona": "auditor"}
_LOCAL_ROUTE = "operational_resilience_mapping.adapters.local.review_router.LocalReviewRouter.route"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(REVIEW_ROUTING_ENV, raising=False)
    monkeypatch.delenv("HUMAN_REVIEW_URL", raising=False)
    # The API caches its container for the process; each test here states its own posture.
    api_module._container.cache_clear()
    yield
    api_module._container.cache_clear()


def _result(escalating: bool = True) -> ResilienceReview:
    return ResilienceReview(
        subject=sample_cases.SERVICE.name,
        severity=Severity.HIGH if escalating else Severity.LOW,
        decision=Decision.ESCALATED if escalating else Decision.ALLOWED,
        summary="scenario computed a disruption against the tolerance",
        requires_human_review=escalating,
        citations=(),
    )


def _gcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "operational_resilience_mapping.config.resolve_profile",
        lambda environ=None: ProfileChoice("gcp", True),
    )


# --------------------------------------------------------------------------- #
# Three states
# --------------------------------------------------------------------------- #
def test_routing_is_on_when_nothing_is_said() -> None:
    assert Settings.load().controls == ControlSwitches(review_routing=True)


def test_routing_switched_off_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "off")
    assert Settings.load().controls.switched_off() == (REVIEW_ROUTING_ENV,)


def test_an_emptied_switch_refuses_at_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "")
    with pytest.raises(ConfiguredEmptyError, match=REVIEW_ROUTING_ENV):
        Settings.load()


def test_an_unrecognised_switch_refuses_at_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "sometimes")
    with pytest.raises(ValueError, match=REVIEW_ROUTING_ENV):
        Settings.load()


# --------------------------------------------------------------------------- #
# Off binds the disabled router, and says so once
# --------------------------------------------------------------------------- #
def test_off_binds_the_disabled_router() -> None:
    settings = Settings(profile="local", controls=ControlSwitches(review_routing=False))
    assert isinstance(Container(settings).review_router, DisabledReviewRouter)


def test_on_binds_the_profile_router() -> None:
    settings = Settings(profile="local")
    assert not isinstance(Container(settings).review_router, DisabledReviewRouter)


def test_the_off_posture_is_logged_once_however_many_containers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    warn_switched_off.cache_clear()
    settings = Settings(profile="local", controls=ControlSwitches(review_routing=False))
    with caplog.at_level(logging.WARNING, logger="operational_resilience_mapping.config"):
        for _ in range(3):
            build_container(settings)
    assert caplog.text.count(REVIEW_ROUTING_ENV) == 1


# --------------------------------------------------------------------------- #
# On has to work: checked at boot under the managed profile
# --------------------------------------------------------------------------- #
def test_routing_on_under_gcp_without_a_console_refuses_at_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _gcp(monkeypatch)
    with pytest.raises(ConfiguredEmptyError, match="HUMAN_REVIEW_URL"):
        Settings.load()


def test_routing_stated_off_under_gcp_needs_no_console(monkeypatch: pytest.MonkeyPatch) -> None:
    _gcp(monkeypatch)
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "false")
    assert Settings.load().controls.review_routing is False


def test_routing_on_under_gcp_with_a_console_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    _gcp(monkeypatch)
    monkeypatch.setenv("HUMAN_REVIEW_URL", "https://review.example.test")
    assert Settings.load().review_url == "https://review.example.test"


# --------------------------------------------------------------------------- #
# The four routing outcomes
# --------------------------------------------------------------------------- #
class _Accepting:
    def route(self, result: ResilienceReview, *, maker: str, tenant: str = "") -> str:
        return "review-1"


class _Refusing:
    def route(self, result: ResilienceReview, *, maker: str, tenant: str = "") -> str:
        raise ConnectionError("console unreachable")


def test_routing_outcomes_take_each_of_their_four_values() -> None:
    result = _result()
    assert result.requires_human_review

    not_required = RecordingReviewRouter(_Accepting())
    assert not_required.route(_result(escalating=False), maker="m") == ""
    assert not_required.outcome is ReviewRouting.NOT_REQUIRED

    routed = RecordingReviewRouter(_Accepting())
    assert routed.route(result, maker="m") == "review-1"
    assert routed.outcome is ReviewRouting.ROUTED

    off = RecordingReviewRouter(DisabledReviewRouter(Settings()))
    assert off.route(result, maker="m") == ""
    assert off.outcome is ReviewRouting.OFF


def test_a_failed_hand_off_is_reported_and_logged_never_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = RecordingReviewRouter(_Refusing())
    with caplog.at_level(
        logging.WARNING, logger="operational_resilience_mapping.adapters.controls"
    ):
        assert failed.route(_result(), maker="m") == ""
    assert failed.outcome is ReviewRouting.FAILED
    assert "ConnectionError" in caplog.text


# --------------------------------------------------------------------------- #
# Every caller reports it
# --------------------------------------------------------------------------- #
def _post(path: str, body: dict[str, object]) -> dict[str, object]:
    response = TestClient(app, client=_LOOPBACK).post(path, json=body, headers=_AUDITOR)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_tolerance_route_reports_a_routed_hand_off() -> None:
    reply = _post("/v1/tolerance", _TOLERANCE)
    assert reply["review_routing"] == "routed"
    assert reply["review_ref"]


def test_the_tolerance_route_reports_routing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "off")
    reply = _post("/v1/tolerance", _TOLERANCE)
    assert reply["review_routing"] == "off"
    assert reply["review_ref"] == ""


def test_the_tolerance_route_reports_a_failed_hand_off_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_LOCAL_ROUTE, _Refusing.route)
    reply = _post("/v1/tolerance", _TOLERANCE)
    assert reply["review_routing"] == "failed"
    assert reply["review_ref"] == ""


def test_the_agent_tool_reports_the_hand_off(monkeypatch: pytest.MonkeyPatch) -> None:
    args = (sample_cases.SERVICE.id, sample_cases.SERVICE.name)
    assert tools.assess_resilience(*args, scope=sample_cases.SCOPE)["review_routing"] == "routed"
    monkeypatch.setattr(_LOCAL_ROUTE, _Refusing.route)
    failed = tools.assess_resilience(*args, scope=sample_cases.SCOPE)
    assert failed["review_routing"] == "failed"
    assert failed["review_ref"] == ""


def test_the_cli_reports_the_hand_off(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "off")
    argv = ["tolerance", sample_cases.SERVICE.id, sample_cases.SERVICE.name]
    assert cli_main([*argv, "--scope", sample_cases.SCOPE]) == 0
    assert "human review hand-off : off" in capsys.readouterr().out
