"""
DevSentinel Interactive CLI Entrypoint.
Provides a REPL interface for developer build/PR diagnosis with human-in-the-loop safeguards.
"""

import sys
import os
import argparse
from typing import Dict, Any

from agent.agent import DevSentinelAgent, AgentRunResult


def human_confirmation_prompt(incident_data: Dict[str, Any]) -> bool:
    """
    CLI Confirmation prompt presented to human operator before executing state-changing write tool.
    """
    print("\n" + "=" * 60)
    print(" ⚠️  HUMAN-IN-THE-LOOP APPROVAL REQUIRED TO LOG NEW INCIDENT")
    print("=" * 60)
    print(f" Component  : {incident_data.get('component', 'N/A')}")
    print(f" Summary    : {incident_data.get('summary', 'N/A')}")
    print(f" Root Cause : {incident_data.get('root_cause', 'N/A')}")
    print(f" Resolution : {incident_data.get('resolution', 'N/A')}")
    print("=" * 60)
    
    try:
        choice = input("Do you approve writing this incident record to SQLite? [y/N]: ").strip().lower()
        return choice in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print("\nConfirmation prompt cancelled.")
        return False


def run_cli_session(query: str = None):
    print("\n" + "─" * 60)
    print(" 🛡️  DevSentinel — Agentic AI Build & PR Diagnosis System")
    print("─" * 60)

    agent = DevSentinelAgent(max_iterations=8)

    if query:
        _execute_query(agent, query)
        return

    # Interactive REPL Loop
    while True:
        try:
            user_input = input("\nDevSentinel> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting DevSentinel CLI session. Goodbye!")
                break
                
            _execute_query(agent, user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI session.")
            break


def _execute_query(agent: DevSentinelAgent, query: str):
    print(f"\n[QUERY]: {query}")
    print("Analyzing and executing diagnostic trajectory...\n")

    result: AgentRunResult = agent.run(
        query=query,
        confirm_callback=human_confirmation_prompt
    )

    print("\n" + "─" * 60)
    print(" 🔍 REACTION & TOOL TRAJECTORY LOGS")
    print("─" * 60)
    for step in result.steps:
        print(f"Step #{step.step_number} [{step.provider_used.upper()}]:")
        if step.thought:
            print(f"  Thought: {step.thought.strip()}")
        if step.tool_name:
            print(f"  Action: {step.tool_name}({step.tool_args})")
        if step.observation:
            obs_str = str(step.observation)
            if len(obs_str) > 200:
                obs_str = obs_str[:200] + "..."
            print(f"  Observation: {obs_str}\n")

    print("=" * 60)
    print(" 📋 SYNTHESIZED DIAGNOSIS & RECOMMENDATION")
    print("=" * 60)
    print(result.final_answer)
    print("=" * 60)
    print(f"Total Tool Calls: {result.total_tool_calls} | Provider: {result.provider_used.upper()}\n")


def main():
    parser = argparse.ArgumentParser(description="DevSentinel Agentic AI CLI")
    parser.add_argument("query", nargs="?", help="Optional natural language diagnosis query")
    args = parser.parse_args()

    run_cli_session(query=args.query)


if __name__ == "__main__":
    main()
