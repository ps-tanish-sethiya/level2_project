"""
LLM Provider Layer with Gemini 2.5 Flash as Primary and Groq Llama-3.3-70b as Fallback.
Provides transparent failover on 429, timeout, 5xx, or network errors with response normalization.
"""
import os
import time
import logging
import warnings
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Suppress google.generativeai deprecation warning
warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("devsentinel.agent.llm_provider")


class LLMToolCall(BaseModel):
    id: str = Field(..., description="Call identifier")
    name: str = Field(..., description="Name of tool to call")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool call")


class LLMResponse(BaseModel):
    content: Optional[str] = Field(None, description="Natural language response text")
    tool_calls: List[LLMToolCall] = Field(default_factory=list, description="Requested tool calls")
    provider_used: str = Field(..., description="Provider that processed the request ('gemini' or 'groq')")
    error: Optional[str] = Field(None, description="Error message if all providers failed")
    raw_gemini_content: Optional[Any] = Field(None, description="Original Gemini Content object for thought_signature retention")
    prompt_tokens: int = Field(0, description="Number of prompt/input tokens used")
    completion_tokens: int = Field(0, description="Number of completion/output tokens used")
    total_tokens: int = Field(0, description="Total tokens used in this request")
    cost_usd: float = Field(0.0, description="Estimated monetary cost of request in USD")


def _fix_schema_types_for_gemini(schema: Any) -> Any:
    """Convert JSON schema type strings to uppercase (OBJECT, STRING, etc.) required by Gemini protobuf parser."""
    if isinstance(schema, dict):
        new_dict = {}
        for k, v in schema.items():
            if k == "type" and isinstance(v, str):
                new_dict[k] = v.upper()
            else:
                new_dict[k] = _fix_schema_types_for_gemini(v)
        return new_dict
    elif isinstance(schema, list):
        return [_fix_schema_types_for_gemini(item) for item in schema]
    return schema


class DualLLMProvider:
    """
    Dual-provider LLM manager handling transparent failover between Gemini and Groq.
    """
    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    @property
    def gemini_key(self) -> str:
        load_dotenv(override=True)
        return os.getenv("GOOGLE_API_KEY", "").strip("'\" \t\r\n")

    @property
    def groq_key(self) -> str:
        load_dotenv(override=True)
        return os.getenv("GROQ_API_KEY", "").strip("'\" \t\r\n")

    def _convert_tools_to_gemini(self, mcp_tools: List[Dict[str, Any]]) -> List[Any]:
        """
        Convert standard MCP tool dicts to Gemini declaration format with UPPERCASE types.

        IMPORTANT: google.generativeai expects `tools` to be a list of Tool objects,
        where each Tool wraps its function declarations under a `function_declarations`
        key. Passing a flat list of raw declaration dicts (the previous bug) causes the
        protobuf parser to raise on GenerativeModel(...) construction for every model
        name in the fallback list, which looks like "Gemini always fails" even with a
        perfectly valid API key.
        """
        declarations = []
        for t in mcp_tools:
            raw_params = t.get("parameters") or t.get("inputSchema") or {"type": "object", "properties": {}}
            declarations.append({
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": _fix_schema_types_for_gemini(raw_params)
            })
        # Wrap in a single Tool dict with function_declarations, as required by the SDK.
        return [{"function_declarations": declarations}]

    def _convert_tools_to_groq(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert standard MCP tool dicts to clean OpenAI/Groq function format."""
        groq_tools = []
        for t in mcp_tools:
            params = t.get("parameters") or t.get("inputSchema") or {}
            props = params.get("properties", {})
            req = params.get("required", [])
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": req
                    }
                }
            })
        return groq_tools

    def _call_gemini(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        import google.generativeai as genai

        key = self.gemini_key
        if not key or key.startswith("your_"):
            raise ValueError("GOOGLE_API_KEY is missing from .env file")

        genai.configure(api_key=key)
        gemini_tools = self._convert_tools_to_gemini(tools) if tools else None

        system_instruction = None
        history = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role in ("user", "human"):
                history.append({"role": "user", "parts": [content]})
            elif role in ("assistant", "model"):
                raw_content = msg.get("raw_gemini_content")
                if raw_content is not None:
                    history.append(raw_content)
                else:
                    parts = []
                    if content and content.strip():
                        parts.append(genai.protos.Part(text=content))
                    if msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            fn_name = str(tc["name"]).replace("default_api:", "").strip()
                            parts.append(genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=fn_name,
                                    args=tc.get("args", {})
                                )
                            ))
                    if not parts:
                        parts.append(genai.protos.Part(text="Executing tools..."))
                    history.append(genai.protos.Content(role="model", parts=parts))
            elif role == "tool":
                tool_name = str(msg.get("name", "tool")).replace("default_api:", "").strip()
                result_content = str(msg.get("content", ""))
                try:
                    resp_dict = json.loads(result_content)
                except Exception:
                    resp_dict = {"result": result_content}
                part = genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response=resp_dict if isinstance(resp_dict, dict) else {"result": str(resp_dict)}
                    )
                )
                history.append(genai.protos.Content(role="user", parts=[part]))

        model_names = ["models/gemini-3.5-flash-lite"]
        response = None
        last_model_err = None

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

        for m_name in model_names:
            # Try up to 2 attempts with brief 1.0s backoff for rate limits
            for attempt in range(1, 3):
                try:
                    model = genai.GenerativeModel(
                        model_name=m_name,
                        system_instruction=system_instruction,
                        tools=gemini_tools
                    )
                    start_time = time.time()

                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(model.generate_content, history)
                        response = future.result(timeout=self.timeout_seconds)

                    elapsed = time.time() - start_time
                    logger.info(f"Gemini succeeded using model '{m_name}' in {elapsed:.2f}s")
                    break
                except FutureTimeoutError:
                    last_model_err = TimeoutError(f"Gemini API call exceeded timeout threshold of {self.timeout_seconds}s")
                    logger.warning(f"Gemini model '{m_name}' timed out after {self.timeout_seconds}s.")
                    break
                except Exception as e:
                    last_model_err = e
                    err_str = str(e)
                    if "429" in err_str or "ResourceExhausted" in err_str:
                        if attempt < 2:
                            logger.warning(f"Gemini 429 rate-limited on '{m_name}'. Retrying with brief 1.0s backoff...")
                            time.sleep(1.0)
                        else:
                            logger.warning(f"Gemini 429 rate-limit limit reached on '{m_name}'. Initiating fast failover...")
                            break
                    else:
                        logger.warning(f"Gemini model '{m_name}' failed with error: {e}. Attempting fallback...")
                        break
            if response is not None:
                break

        if response is None:
            raise last_model_err or Exception("All Gemini models failed")

        tool_calls = []
        text_content = ""

        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                text_content += part.text
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                args_dict = dict(fc.args) if fc.args else {}
                raw_name = str(fc.name)
                clean_name = raw_name.split(":")[-1].strip()
                tool_calls.append(LLMToolCall(
                    id=f"call_gemini_{clean_name}_{int(time.time()*1000)}",
                    name=clean_name,
                    args=args_dict
                ))

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
            completion_tokens = getattr(um, "candidates_token_count", 0) or 0
            total_tokens = getattr(um, "total_token_count", 0) or (prompt_tokens + completion_tokens)
        else:
            prompt_tokens = len(json.dumps(messages)) // 4
            completion_tokens = len(text_content or "") // 4
            total_tokens = prompt_tokens + completion_tokens

        prompt_cost = (prompt_tokens / 1_000_000.0) * 0.075
        completion_cost = (completion_tokens / 1_000_000.0) * 0.30
        cost_usd = round(prompt_cost + completion_cost, 7)

        return LLMResponse(
            content=text_content if text_content else None,
            tool_calls=tool_calls,
            provider_used="gemini",
            error=None,
            raw_gemini_content=candidate.content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd
        )

    def _call_groq(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        from groq import Groq
        import json

        key = self.groq_key
        if not key or key.startswith("your_"):
            raise ValueError("GROQ_API_KEY is not configured in .env file")

        client = Groq(api_key=key, timeout=self.timeout_seconds)
        groq_tools = self._convert_tools_to_groq(tools) if tools else None

        formatted_messages = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                formatted_messages.append({"role": "system", "content": content or ""})
            elif role in ("user", "human"):
                formatted_messages.append({"role": "user", "content": content or ""})
            elif role in ("assistant", "model"):
                msg_dict: Dict[str, Any] = {"role": "assistant", "content": content or ""}
                if m.get("tool_calls"):
                    tcs = []
                    for tc in m["tool_calls"]:
                        tcs.append({
                            "id": tc.get("id", "call_1"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("args", {}))
                            }
                        })
                    msg_dict["tool_calls"] = tcs
                formatted_messages.append(msg_dict)
            elif role == "tool":
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", "call_1"),
                    "content": str(m.get("content", ""))
                })
        kwargs: Dict[str, Any] = {
            "model": "llama-3.3-70b-versatile",
            "messages": formatted_messages,
        }
        if groq_tools:
            kwargs["tools"] = groq_tools
            kwargs["tool_choice"] = "auto"

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as groq_err:
            err_str = str(groq_err)
            import re
            match = re.search(r"<function=([a-zA-Z0-9_]+)\s*(\{.*?\})", err_str)
            if match:
                fn_name = match.group(1).strip()
                raw_args = match.group(2).strip()
                try:
                    args_dict = json.loads(raw_args)
                except Exception:
                    args_dict = {}
                logger.info(f"Parsed raw Groq string tool call -> {fn_name}({args_dict})")
                return LLMResponse(
                    content=None,
                    tool_calls=[LLMToolCall(id=f"call_groq_parsed_{fn_name}", name=fn_name, args=args_dict)],
                    provider_used="groq",
                    error=None
                )
            raise groq_err

        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                raw_name = str(fn.name)
                clean_name = raw_name.split("=")[0].split("(")[0].strip()
                try:
                    args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                except Exception:
                    args = {}
                tool_calls.append(LLMToolCall(
                    id=tc.id or f"call_groq_{clean_name}",
                    name=clean_name,
                    args=args or {}
                ))

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if hasattr(response, "usage") and response.usage:
            u = response.usage
            prompt_tokens = getattr(u, "prompt_tokens", 0) or 0
            completion_tokens = getattr(u, "completion_tokens", 0) or 0
            total_tokens = getattr(u, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        else:
            prompt_tokens = len(json.dumps(messages)) // 4
            completion_tokens = len(msg.content or "") // 4
            total_tokens = prompt_tokens + completion_tokens

        prompt_cost = (prompt_tokens / 1_000_000.0) * 0.59
        completion_cost = (completion_tokens / 1_000_000.0) * 0.79
        cost_usd = round(prompt_cost + completion_cost, 7)

        return LLMResponse(
            content=msg.content if msg.content else None,
            tool_calls=tool_calls,
            provider_used="groq",
            error=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd
        )

    def _call_ollama(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        import json
        import urllib.request

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

        openai_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                openai_messages.append({"role": "system", "content": content})
            elif role in ("user", "human"):
                openai_messages.append({"role": "user", "content": content})
            elif role in ("assistant", "model"):
                m_dict = {"role": "assistant", "content": content or ""}
                if msg.get("tool_calls"):
                    m_dict["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{tc['name']}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("args", {}))
                            }
                        }
                        for tc in msg["tool_calls"]
                    ]
                openai_messages.append(m_dict)
            elif role == "tool":
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", "call_tool"),
                    "content": str(msg.get("content", ""))
                })

        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {})
                }
            })

        payload = {
            "model": ollama_model,
            "messages": openai_messages,
            "stream": False
        }
        if openai_tools:
            payload["tools"] = openai_tools

        req = urllib.request.Request(
            ollama_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        choice = data["choices"][0]
        msg = choice["message"]

        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                raw_name = str(fn.get("name", ""))
                clean_name = raw_name.split(":")[-1].strip()
                args_raw = fn.get("arguments", {})
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except Exception:
                    args = {}
                tool_calls.append(LLMToolCall(
                    id=tc.get("id") or f"call_ollama_{clean_name}",
                    name=clean_name,
                    args=args or {}
                ))

        usage = data.get("usage", {})
        p_tok = usage.get("prompt_tokens") or (len(json.dumps(messages)) // 4)
        c_tok = usage.get("completion_tokens") or (len(msg.get("content") or "") // 4)
        t_tok = usage.get("total_tokens") or (p_tok + c_tok)

        return LLMResponse(
            content=msg.get("content") or None,
            tool_calls=tool_calls,
            provider_used="ollama",
            error=None,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=t_tok,
            cost_usd=0.0
        )

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """
        Execute chat query with Gemini primary, Ollama local, and Groq cloud failovers.
        """
        errors = []

        # Step 1: Attempt Gemini primary
        try:
            logger.info("Attempting primary LLM provider: Google Gemini (gemini-3.5-flash-lite)...")
            res = self._call_gemini(messages=messages, tools=tools)
            logger.info("Call processed successfully by primary provider: Google Gemini")
            return res
        except Exception as gemini_err:
            errors.append(f"Gemini: {gemini_err}")
            logger.warning(f"Primary provider (Gemini) failed: {gemini_err}. Initiating fallback to Ollama...", exc_info=True)

        # Step 2: Attempt Ollama local (llama3.2:3b)
        try:
            logger.info("Attempting local LLM provider: Ollama (llama3.2:3b)...")
            res = self._call_ollama(messages=messages, tools=tools)
            logger.info("Call processed successfully by local provider: Ollama (llama3.2:3b)")
            return res
        except Exception as ollama_err:
            errors.append(f"Ollama: {ollama_err}")
            logger.warning(f"Local provider (Ollama) failed: {ollama_err}. Initiating fallback to Groq...", exc_info=True)

        # Step 3: Attempt Groq fallback
        try:
            logger.info("Attempting fallback LLM provider: Groq (llama-3.3-70b-versatile)...")
            res = self._call_groq(messages=messages, tools=tools)
            logger.info("Call processed successfully by fallback provider: Groq (llama-3.3-70b-versatile)")
            return res
        except Exception as groq_err:
            errors.append(f"Groq: {groq_err}")
            logger.error(f"Fallback provider (Groq) also failed: {groq_err}", exc_info=True)
            return LLMResponse(
                content=None,
                tool_calls=[],
                provider_used="none",
                error=f"All LLM providers failed. " + " | ".join(errors)
            )