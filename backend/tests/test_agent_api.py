from fastapi.testclient import TestClient

from profitpulse.main import app
from profitpulse.agent.prompts import build_system_prompt


def test_agent_capabilities_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/agent/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["orchestration"] == "LangGraph tool-calling workflow"
    assert "get_financial_summary" in {tool["name"] for tool in payload["tools"]}
    assert "get_expense_breakdown" in {tool["name"] for tool in payload["tools"]}
    assert "get_monthly_expense_breakdown" in {tool["name"] for tool in payload["tools"]}


def test_agent_ask_requires_organization_header():
    with TestClient(app) as client:
        response = client.post("/api/v1/agent/ask", json={"question": "Why is profit declining?"})

    assert response.status_code == 422


def test_agent_ask_uses_tenant_header_and_returns_mocked_answer(monkeypatch):
    def fake_run_agent(question, organization_id, max_tool_rounds):
        assert question == "Why is EBITDA negative?"
        assert organization_id == "11111111-1111-4111-8111-111111111111"
        assert max_tool_rounds == 6
        return {
            "answer": "The ledger reports negative EBITDA for the requested period.",
            "provider": "gemini",
            "model": "test-model",
            "tools_used": ["get_financial_summary"],
            "tool_trace": [{"tool": "get_financial_summary", "arguments": {}}],
            "tool_result_count": 1,
            "disclaimer": "Decision-support only.",
        }

    monkeypatch.setattr("profitpulse.routers.api.run_agent", fake_run_agent)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/ask",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
            json={"question": "Why is EBITDA negative?"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("The ledger reports")
    assert payload["organization_id"] == "11111111-1111-4111-8111-111111111111"
    assert payload["tools_used"] == ["get_financial_summary"]


def test_agent_ask_rejects_too_short_question():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/ask",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
            json={"question": "hi"},
        )

    assert response.status_code == 422


def test_agent_ask_returns_503_when_provider_key_is_missing(monkeypatch):
    from profitpulse.agent.llm import LLMConfigurationError

    def fake_run_agent(question, organization_id, max_tool_rounds):
        raise LLMConfigurationError("Gemini key is missing")

    monkeypatch.setattr("profitpulse.routers.api.run_agent", fake_run_agent)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/ask",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
            json={"question": "Why is EBITDA negative?"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini key is missing"


def test_prompt_requires_tenant_currency_and_deterministic_monthly_changes():
    prompt = build_system_prompt()
    assert "Never assume USD, INR, or any currency" in prompt
    assert "Use month_over_month values returned by get_monthly_financial_trend" in prompt
    assert "first observed posting" in prompt


def test_prompt_does_not_treat_missing_calendar_month_as_month_over_month():
    prompt = build_system_prompt()
    assert "Do not calculate month-over-month percentages in narrative text" in prompt
