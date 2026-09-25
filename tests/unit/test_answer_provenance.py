"""The service half of the model pills: which model ANSWERED, and whether it searched.

The console shows two pills at the top right: the model that answered the last request, and
``Search`` when that answer used an online search tool. Both come from response headers the kit
emits (``install_answer_provenance`` in ``api/app.py``) for whatever the model adapters NOTED as
they called. Before a request is answered the pill shows ``generator_model`` from ``/healthz``,
so that value must be the model the bound adapter calls, never one a configuration flag names
while the adapter calls another.

Here the generator port is ``generation``, reached by ``POST /v1/tolerance`` when the proposal's
justification is narrated. Offline its stub notes ``deterministic-offline-stub``; the managed
adapter is a deploy-time placeholder that raises before any model answers, so it notes nothing.
No adapter here attaches a search tool, so ``Search`` is proved by standing a noting fake in for
the stub.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from hex_service_kit import provenance

from operational_resilience_mapping import config
from operational_resilience_mapping.adapters.local.generation import LocalGenerationAdapter
from operational_resilience_mapping.domain.models import GenerationRequest, GenerationResponse
from operational_resilience_mapping.domain.narrative import build_request

from tests import REPO_ROOT
from tests.fixtures import sample_cases

ANSWERED_BY = "x-answered-by"
SEARCH_USED = "x-search-used"


def _propose(api_client: TestClient) -> dict[str, str]:
    response = api_client.post(
        "/v1/tolerance",
        json={
            "scope": sample_cases.SCOPE,
            "service_id": sample_cases.SERVICE.id,
            "service_name": sample_cases.SERVICE.name,
            "regulator": "APRA_CPS230",
        },
        headers={"X-Dev-Persona": "auditor"},
    )
    assert response.status_code == 200, response.text
    return dict(response.headers)


def test_the_offline_stub_names_itself_as_the_model_that_answered(
    api_client: TestClient,
) -> None:
    """The narration stub answered, so the pill names it, and the name is what /healthz said."""
    headers = _propose(api_client)
    assert headers[ANSWERED_BY] == config.OFFLINE_STUB_MODEL
    assert SEARCH_USED not in headers, "the offline stub never goes online"
    configured = api_client.get("/healthz").json()["generator_model"]
    assert configured == headers[ANSWERED_BY], "the pill would change name on the first answer"


def test_a_request_that_reaches_no_model_names_none(api_client: TestClient) -> None:
    """Nothing noted, nothing sent: the pill never invents a model the request did not call."""
    headers = dict(api_client.get("/healthz").headers)
    assert ANSWERED_BY not in headers
    assert SEARCH_USED not in headers


def test_the_route_names_the_model_that_answered_and_that_it_searched(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = LocalGenerationAdapter.generate

    def _searching(self: LocalGenerationAdapter, request: GenerationRequest) -> GenerationResponse:
        # What a managed adapter that attached a search tool would note while it called.
        provenance.note_model("fake-answering-model")
        provenance.note_search()
        return original(self, request)

    monkeypatch.setattr(LocalGenerationAdapter, "generate", _searching)
    headers = _propose(api_client)
    assert headers[ANSWERED_BY] == "fake-answering-model, " + config.OFFLINE_STUB_MODEL
    assert headers[SEARCH_USED] == "true"
    # The next request is a fresh record: an answer never leaks into a later response.
    monkeypatch.setattr(LocalGenerationAdapter, "generate", original)
    headers = _propose(api_client)
    assert headers[ANSWERED_BY] == config.OFFLINE_STUB_MODEL
    assert SEARCH_USED not in headers


def test_the_narration_call_sends_no_temperature() -> None:
    """Narration is drafting, so its sampling is free, and free means the parameter is absent.

    The one call site of the generation port narrates a tolerance justification. Its request
    type carries no temperature at all, so no adapter can send one (some models reject it), and
    the managed adapter, a placeholder today, has none to pass on the day it is wired.
    """
    request = build_request("system", "prompt")
    assert "temperature" not in {f.name for f in dataclasses.fields(GenerationRequest)}
    assert not hasattr(request, "temperature")


def test_generator_model_is_the_setting_the_adapter_reads_and_no_flag_swaps_it() -> None:
    """The latent false banner: a flag that moved the pill but not the model that answered.

    A resolver once named ``models.hard_reasoning`` when ``models.use_hard_reasoning`` was set,
    while a managed adapter called ``request.model or models.reasoning`` and never read the
    flag. The pill then named a model that never answered. The flag is gone; a stray one in a
    settings object must change nothing.
    """
    models = SimpleNamespace(
        reasoning="the-model-the-adapter-calls",
        hard_reasoning="a-model-nobody-calls",
        use_hard_reasoning=True,
    )
    named = config._model_from_settings(SimpleNamespace(models=models), "models.reasoning")
    assert named == "the-model-the-adapter-calls"


def test_the_hard_reasoning_flag_does_not_exist() -> None:
    settings_file = (REPO_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert "use_hard_reasoning" not in settings_file
    for source in sorted((REPO_ROOT / "src").rglob("*.py")):
        assert "use_hard_reasoning" not in source.read_text(encoding="utf-8"), source
