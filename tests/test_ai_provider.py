from job_hunt_agent.ai_provider import DeterministicProvider, GeminiProvider, OllamaProvider, select_provider


def test_deterministic_provider_blocks_access_controls():
    result = DeterministicProvider().classify("Please sign in to view this job")
    assert result.source_kind == "blocked"
    assert result.needs_review is True


def test_deterministic_provider_extracts_public_evidence():
    result = DeterministicProvider().extract("# Automation Engineer\nApply: https://example.com/jobs/1")
    assert result.title == "Automation Engineer"
    assert result.links == ("https://example.com/jobs/1",)


def test_provider_selection_falls_back_without_ollama():
    provider = select_provider(base_url="http://127.0.0.1:1")
    assert isinstance(provider, DeterministicProvider)


def test_ollama_prompt_provider_has_expected_defaults():
    provider = OllamaProvider()
    assert provider.model == "llama3.2"
    assert provider.base_url.endswith(":11434")


def test_gemini_provider_does_not_claim_health_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GeminiProvider().health() is False


def test_provider_selection_can_use_configured_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    provider = select_provider(prefer_ollama=False, prefer_gemini=True)
    assert isinstance(provider, GeminiProvider)
