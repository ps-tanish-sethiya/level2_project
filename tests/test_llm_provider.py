"""
Unit tests for the LLM Provider layer, validating the Gemini -> Ollama -> Groq failover logic.
"""

import pytest
from unittest.mock import patch, MagicMock

from agent.llm_provider import DualLLMProvider, LLMResponse, LLMToolCall


def test_gemini_primary_success():
    provider = DualLLMProvider()
    
    mock_gemini_resp = LLMResponse(
        content="Diagnosis: Everything looks normal.",
        tool_calls=[],
        provider_used="gemini",
        error=None
    )
    
    with patch.object(provider, "_call_gemini", return_value=mock_gemini_resp) as mock_gemini:
        res = provider.chat(
            messages=[{"role": "user", "content": "Check status"}],
            tools=[]
        )
        assert res.provider_used == "gemini"
        assert res.content == "Diagnosis: Everything looks normal."
        mock_gemini.assert_called_once()


def test_gemini_rate_limit_failover_to_ollama():
    """
    Test explicit failover: Mock a Gemini 429 rate limit exception and assert the call
    transparently succeeds via local Ollama.
    """
    provider = DualLLMProvider()
    
    mock_ollama_resp = LLMResponse(
        content="Ollama local fallback response: Recommend merging PR.",
        tool_calls=[],
        provider_used="ollama",
        error=None
    )
    
    with patch.object(provider, "_call_gemini", side_effect=Exception("HTTP 429 Rate Limit Exceeded")) as mock_gemini:
        with patch.object(provider, "_call_ollama", return_value=mock_ollama_resp) as mock_ollama:
            res = provider.chat(
                messages=[{"role": "user", "content": "Is this PR safe?"}],
                tools=[]
            )
            assert res.provider_used == "ollama"
            assert "Ollama local fallback" in res.content
            mock_gemini.assert_called_once()
            mock_ollama.assert_called_once()


def test_gemini_and_ollama_failover_to_groq():
    """
    Test 3-stage failover: Mock Gemini and Ollama failures and assert the call falls back to Groq.
    """
    provider = DualLLMProvider()
    
    mock_groq_resp = LLMResponse(
        content="Groq fallback response after Gemini and Ollama fail.",
        tool_calls=[],
        provider_used="groq",
        error=None
    )
    
    with patch.object(provider, "_call_gemini", side_effect=TimeoutError("Gemini call timed out")):
        with patch.object(provider, "_call_ollama", side_effect=Exception("Ollama Connection Refused")):
            with patch.object(provider, "_call_groq", return_value=mock_groq_resp) as mock_groq:
                res = provider.chat(
                    messages=[{"role": "user", "content": "Check logs"}],
                    tools=[]
                )
                assert res.provider_used == "groq"
                assert "Groq fallback" in res.content
                mock_groq.assert_called_once()


def test_all_providers_fail():
    """
    Test graceful structured error return when all three providers fail.
    """
    provider = DualLLMProvider()
    
    with patch.object(provider, "_call_gemini", side_effect=Exception("Gemini Down")):
        with patch.object(provider, "_call_ollama", side_effect=Exception("Ollama Down")):
            with patch.object(provider, "_call_groq", side_effect=Exception("Groq Down")):
                res = provider.chat(
                    messages=[{"role": "user", "content": "Check status"}],
                    tools=[]
                )
                assert res.provider_used == "none"
                assert res.error is not None
                assert "All LLM providers failed" in res.error
