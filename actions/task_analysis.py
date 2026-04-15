import os
from datetime import datetime
import subprocess

from agent.task_queue import get_queue  # type: ignore

def create_notepad_report(content: str) -> str:
    path = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "Desktop", "Jarvis_Task_Analysis.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.Popen(["notepad.exe", path])
        return path
    except Exception as e:
        print(f"[TaskAnalysis] Failed to write report: {e}")
        return ""

def task_analysis(parameters: dict, player) -> str:
    # 1. Gather Task queue info
    queue = get_queue()
    statuses = queue.get_all_statuses()
    
    completed = [s for s in statuses if s['status'] == 'completed']
    failed = [s for s in statuses if s['status'] == 'failed']
    pending = [s for s in statuses if s['status'] == 'pending']
    running = [s for s in statuses if s['status'] == 'running']
    
    # 2. Generate full report text
    report = f"JARVIS FULL TASK ANALYSIS ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
    report += "=" * 50 + "\n\n"
    report += "CAPABILITIES (What I can execute):\n"
    report += "I have direct access to the following action tools:\n"
    report += "- open_app: Opens applications, programs, and websites\n"
    report += "- web_search: Searches the web for direct answers and comparison\n"
    report += "- weather_report: Gets real-time and forecast weather updates near you\n"
    report += "- send_message: Sends text messages via WhatsApp, Telegram, etc.\n"
    report += "- reminder: Sets timed reminders locally\n"
    report += "- youtube_video: Plays and summarizes YouTube videos\n"
    report += "- screen_process: Analyzes the screen or webcam via computer vision\n"
    report += "- computer_settings: Adjusts volume, brightness, toggles dark mode, window focus etc.\n"
    report += "- browser_control: Fully controls Google Chrome (clicks, types, navigates, books flights etc)\n"
    report += "- file_controller: Manages files and folders deeply in the OS\n"
    report += "- cmd_control: Runs CMD/powershell commands from natural language\n"
    report += "- desktop_control: Organizes desktop, changes wallpapers\n"
    report += "- code_helper: Writes, explains, tests and builds python/node files\n"
    report += "- dev_agent: Scaffolds complete multi-file projects from scratch\n"
    report += "- flight_finder: Books specific flights off Google Flights\n"
    report += "- study_mode: Blocks screen and creates study environment\n"
    report += "- computer_control: Directly moves mouse, presses hotkeys, auto-types data\n"
    report += "- agent_task: Executes complex multi-step reasoning tasks in runtime agent.\n"
    
    report += "\n" + "=" * 50 + "\n\n"
    report += "EXECUTION HISTORY (TASKS ANALYSIS):\n"
    report += f"Total Agent Tasks Executed/Tracked: {len(statuses)}\n"
    report += f"Tasks Done Correctly (SUCCESS): {len(completed)}\n"
    report += f"Tasks Failed / Can't Be Done: {len(failed)}\n"
    report += f"Tasks Currently Pending/Running: {len(pending) + len(running)}\n\n"
    
    if completed:
        report += "Examples of tasks done correctly:\n"
        for t in completed[-15:]:
            report += f"  - [SUCCESS] {t.get('goal')}\n"
            
    if failed:
        report += "\nExamples of tasks that failed or couldn't be done:\n"
        for t in failed[-15:]:
            report += f"  - [FAILED] {t.get('goal')}\n"
            
    report += "\n" + "=" * 50 + "\n"
    report += "ANALYSIS:\n"
    report += "The majority of success comes from well-defined direct action commands.\n"
    report += "Complex tasks requiring extensive autonomous multi-step reasoning may fail if the tools encounter \n"
    report += "dynamic CAPTCHAs, unhandled element locators on websites, or incomplete user instructions. \n"
    
    # 3. Write to Notepad
    path = create_notepad_report(report)
    
    if player:
        player.write_log("Generated full task analysis.")
    
    # 4. Summarized spoken response
    spoken = (f"I have successfully compiled a full overview of my capabilities and task history. "
              f"I have opened a detailed analysis report on your Desktop in Notepad. "
              f"Currently logged {len(completed)} successful multi-step tasks and {len(failed)} failed ones.")
              
    return spoken
