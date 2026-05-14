"""
Agent Specialization Profiles
Routes tasks to specialized system prompts with curated tool subsets.
"""

from typing import Dict, List, Optional
from backend.agents import Intent


AGENT_PROFILES: Dict[str, Dict] = {
    "RESEARCHER": {
        "system_prompt_addon": """
You are in RESEARCHER mode. Your primary job is to find, synthesize, and summarize information.
- Always cite your sources when possible
- Verify claims across multiple results
- Prefer primary sources over secondary
- Flag any conflicting information you find
- Provide clear, structured summaries
""",
        "tool_categories": ["browser", "search"],
        "max_iterations": 12,
    },

    "EXECUTOR": {
        "system_prompt_addon": """
You are in EXECUTOR mode. Your job is to carry out system and desktop tasks.
- Always confirm what you did after executing
- Report exactly what succeeded and what failed
- If a tool fails, try an alternative approach before giving up
- Never execute destructive operations without explaining first
""",
        "tool_categories": ["system", "file"],
        "max_iterations": 5,
    },

    "ANALYST": {
        "system_prompt_addon": """
You are in ANALYST mode. Your job is to analyze data, code, and documents.
- Read files thoroughly before drawing conclusions
- Provide structured analysis with clear sections
- Include concrete recommendations, not just observations
- Use numbers and specifics, not vague statements
""",
        "tool_categories": ["file", "system"],
        "max_iterations": 8,
    },

    "PLANNER": {
        "system_prompt_addon": """
You are in PLANNER mode. Your job is to break complex goals into actionable plans.
- Output structured plans with: goal, sub-tasks, dependencies, estimated effort
- Identify risks and blockers
- Suggest which approach should handle each sub-task
- Be specific and actionable — avoid vague recommendations
""",
        "tool_categories": [],  # Planner reasons, doesn't act
        "max_iterations": 3,
    },

    "CODER": {
        "system_prompt_addon": """
You are in CODER mode. Your job is to write, analyze, and debug code.
- Write clean, well-structured code following language conventions
- Test your code mentally before presenting it
- Explain your reasoning for design decisions
- If debugging, identify the root cause before suggesting fixes
""",
        "tool_categories": ["file", "system"],
        "max_iterations": 10,
    },

    "DEFAULT": {
        "system_prompt_addon": "",
        "tool_categories": [],  # All tools available
        "max_iterations": 6,
    },
}

# Intent → profile mapping
INTENT_PROFILE_MAP: Dict[Intent, Optional[str]] = {
    Intent.WEB_SEARCH: "RESEARCHER",
    Intent.BROWSER_AUTOMATION: "RESEARCHER",
    Intent.LAUNCH_APP: "EXECUTOR",
    Intent.FILE_OPERATION: "EXECUTOR",
    Intent.SYSTEM_QUERY: "EXECUTOR",
    Intent.CODE_EXECUTION: "ANALYST",
    Intent.MULTI_STEP: "PLANNER",
    Intent.CONVERSATION: None,  # Default mode
    Intent.MEMORY_RECALL: None,
    Intent.SCHEDULE_TASK: None,
}


def get_profile_for_intent(intent: Intent, confidence: float = 0.0) -> Optional[Dict]:
    """Select a specialist profile based on classified intent.

    Returns None if default mode should be used.
    Only activates specialist profiles if confidence > 0.7.
    """
    if confidence < 0.7:
        return None

    profile_name = INTENT_PROFILE_MAP.get(intent)
    if profile_name:
        return AGENT_PROFILES.get(profile_name)

    return None
