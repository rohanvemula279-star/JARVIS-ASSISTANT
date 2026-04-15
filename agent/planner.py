import json
import re
import sys
from pathlib import Path

from memory.config_manager import get_gemini_key  # type: ignore


PLANNER_PROMPT = """You are the planning module of MARK XXV, a personal AI assistant.  
Your job: break any user goal into a sequence of steps using ONLY the tools listed below.  

ABSOLUTE RULES:
- NEVER use generated_code or write Python scripts. It does not exist.
- NEVER reference previous step results in parameters. Every step is independent.  
- Use web_search for ANY information retrieval, research, or current data.
- Use file_controller to save content to disk.
- Use cmd_control to open files or run system commands.
- Max 4 steps. Use the minimum steps needed.

AVAILABLE TOOLS AND THEIR PARAMETERS:

open_app
  app_name: string (required)

web_search
  query: string (required) — write a clear, focused search query

browser_task
  request: string (required)
  user_data: dict (optional)

file_controller
  action: "write" | "create_file" | "read" | "list" | "delete" | "find" (required)
  path: string
  name: string
  content: string

cmd_control
  task: string (required)

computer_settings
  action: string
  description: string

computer_control
  action: "type" | "click" | "hotkey" | "press" | "scroll" | "screenshot"
  text: string

screen_process
  text: string (required)

send_message
  receiver: string
  message_text: string
  platform: string

reminder
  date: string
  time: string
  message: string

desktop_control
  action: "wallpaper" | "organize" | "clean"

youtube_video
  action: "play" | "summarize"

weather_report
  city: string

flight_finder
  origin: string
  destination: string
  date: string

code_helper
  action: "write" | "edit" | "run"
  description: string

dev_agent
  description: string

study_mode
  action: "activate" | "deactivate"

dashboard
  view: "summary" | "tasks" | "calendar"

OUTPUT — return ONLY valid JSON:
{"goal":"...","steps":[{"step":1,"tool":"tool_name","description":"...","parameters":{}}]}
"""


def create_plan(goal: str, context: str = "") -> dict:
    import google.generativeai as genai  # type: ignore

    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config={"temperature": 0.2, "max_output_tokens": 512},
    )

    user_input = f"Goal: {goal}"

    try:
        response = model.generate_content(user_input)
        text = response.text.strip()
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

        plan = json.loads(text)

        if "steps" not in plan or not isinstance(plan["steps"], list):
            raise ValueError("Invalid plan structure")

        for step in plan["steps"]:
            if step.get("tool") in ("generated_code",):
                print(
                    f"[Planner] ⚠️ generated_code detected in step {
                        step.get('step')
                    } — replacing with web_search"
                )
                desc = step.get("description", goal)
                step["tool"] = "web_search"
                step["parameters"] = {"query": desc[:200]}

        print(f"[Planner] ✅ Plan: {len(plan['steps'])} steps")
        for s in plan["steps"]:
            print(f"  Step {s['step']}: [{s['tool']}] {s['description']}")

        return plan

    except json.JSONDecodeError as e:
        print(f"[Planner] ⚠️ JSON parse failed: {e}")
        return _fallback_plan(goal)
    except Exception as e:
        print(f"[Planner] ⚠️ Planning failed: {e}")
        return _fallback_plan(goal)


def _fallback_plan(goal: str) -> dict:
    print("[Planner] 🔄 Fallback plan")
    return {
        "goal": goal,
        "steps": [
            {
                "step": 1,
                "tool": "web_search",
                "description": f"Search for: {goal}",
                "parameters": {"query": goal},
                "critical": True,
            }
        ],
    }


def replan(goal: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    import google.generativeai as genai  # type: ignore

    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config={"temperature": 0.2, "max_output_tokens": 512},
    )

    prompt = f"Goal: {goal}\nFailed: {failed_step.get('description')}\nFix and retry."

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        plan = json.loads(text)

        # generated_code kontrolü
        for step in plan.get("steps", []):
            if step.get("tool") == "generated_code":
                step["tool"] = "web_search"
                step["parameters"] = {"query": step.get("description", goal)[:200]}

        print(f"[Planner] 🔄 Revised plan: {len(plan['steps'])} steps")
        return plan
    except Exception as e:
        print(f"[Planner] ⚠️ Replan failed: {e}")
        return _fallback_plan(goal)
