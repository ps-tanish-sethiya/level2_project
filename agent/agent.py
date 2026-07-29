"""
ReAct (Reason -> Act -> Observe) Agent Engine for DevSentinel.
Coordinates LLM provider, MCP client tools, and human-in-the-loop safeguards.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from agent.llm_provider import DualLLMProvider, LLMResponse
from agent.mcp_client import MCPClientWrapper
from agent.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger("devsentinel.agent.engine")


class AgentStepLog(BaseModel):
    step_number: int
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    provider_used: str = "gemini"


class AgentRunResult(BaseModel):
    query: str
    final_answer: str
    steps: List[AgentStepLog] = Field(default_factory=list)
    total_tool_calls: int = 0
    provider_used: str = "gemini"
    capped: bool = False
    pending_incident_write: Optional[Dict[str, Any]] = None


class DevSentinelAgent:
    """
    Goal-oriented ReAct Agent managing diagnosis trajectory and MCP tool invocations.
    """
    def __init__(self, max_iterations: int = 8):
        self.max_iterations = max_iterations
        self.llm = DualLLMProvider()
        self.mcp = MCPClientWrapper()

    def run(
        self,
        query: str,
        confirm_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> AgentRunResult:
        """
        Execute ReAct loop for a natural language diagnosis query.
        
        Args:
            query: User's diagnosis prompt.
            confirm_callback: Optional callable for human confirmation on state-changing actions.
            
        Returns:
            AgentRunResult containing synthesized diagnosis and step-by-step trace.
        """
        logger.info(f"=== Starting Agent Trajectory for Query: '{query}' ===")
        
        available_tools = self.mcp.list_tools()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]
        
        steps: List[AgentStepLog] = []
        providers_used_set = set()
        pending_write = None
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- ReAct Loop Iteration {iteration}/{self.max_iterations} ---")
            
            # Step 1: Call LLM provider layer
            llm_response: LLMResponse = self.llm.chat(messages=messages, tools=available_tools)
            
            if llm_response.provider_used != "none":
                providers_used_set.add(llm_response.provider_used)
                
            if llm_response.error:
                error_msg = f"Agent halted: {llm_response.error}"
                logger.error(error_msg)
                return AgentRunResult(
                    query=query,
                    final_answer=error_msg,
                    steps=steps,
                    total_tool_calls=len(steps),
                    provider_used="none",
                    capped=False
                )

            # Check if LLM produced final text answer without requesting further tool calls
            if not llm_response.tool_calls:
                final_text = llm_response.content or "Diagnosis completed (no specific recommendations produced)."
                logger.info(f"Agent produced final synthesized answer at iteration {iteration}.")
                
                primary_provider = list(providers_used_set)[0] if providers_used_set else "gemini"
                return AgentRunResult(
                    query=query,
                    final_answer=final_text,
                    steps=steps,
                    total_tool_calls=len(steps),
                    provider_used=primary_provider,
                    capped=False,
                    pending_incident_write=pending_write
                )

            # Step 2: Execute requested tool calls
            assistant_content = llm_response.content or ""
            tool_calls_log = []
            
            for tc in llm_response.tool_calls:
                tool_name = tc.name
                tool_args = tc.args
                tool_call_id = tc.id
                
                logger.info(f"Iteration {iteration}: LLM decided tool call -> {tool_name}({tool_args})")
                
                # Human-in-the-Loop Safeguard check for write operations
                if tool_name == "log_new_incident":
                    pending_write = tool_args
                    if confirm_callback is not None:
                        logger.info("Triggering Human-in-the-Loop approval prompt for log_new_incident...")
                        approved = confirm_callback(tool_args)
                        if not approved:
                            logger.warning("User REJECTED log_new_incident request.")
                            obs = {
                                "success": False,
                                "message": "User denied confirmation to execute log_new_incident. Action aborted.",
                                "error": "User rejected write action"
                            }
                            # Feed rejection back to LLM context
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "name": tool_name,
                                "content": json.dumps(obs)
                            })
                            steps.append(AgentStepLog(
                                step_number=iteration,
                                thought=assistant_content,
                                tool_name=tool_name,
                                tool_args=tool_args,
                                observation=obs,
                                provider_used=llm_response.provider_used
                            ))
                            continue

                # Execute tool via MCP client wrapper
                obs = self.mcp.call_tool(tool_name=tool_name, arguments=tool_args)
                
                steps.append(AgentStepLog(
                    step_number=iteration,
                    thought=assistant_content,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    observation=obs,
                    provider_used=llm_response.provider_used
                ))
                
                # Append tool observation back into LLM messages context
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": json.dumps(obs)
                })
                
        # If iteration limit hit
        logger.warning(f"ReAct loop reached maximum allowed iterations ({self.max_iterations}). Formulating best partial answer.")
        primary_provider = list(providers_used_set)[0] if providers_used_set else "gemini"
        return AgentRunResult(
            query=query,
            final_answer="Agent reached maximum tool call iterations. Please review the partial diagnostic step logs.",
            steps=steps,
            total_tool_calls=len(steps),
            provider_used=primary_provider,
            capped=True,
            pending_incident_write=pending_write
        )
