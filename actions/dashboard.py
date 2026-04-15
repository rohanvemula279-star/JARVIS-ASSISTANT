import json
import threading
from datetime import datetime
from typing import Optional, Any
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()


def get_dashboard_summary() -> str:
    """Generate a unified dashboard summary."""
    from memory.memory_manager import load_memory, format_memory_for_prompt
    from memory.task_manager import get_task_manager
    from memory.knowledge_base import get_knowledge_base

    lines = []
    lines.append("=" * 50)
    lines.append("📊 PERSONAL DASHBOARD")
    lines.append("=" * 50)

    memory = load_memory()
    name = memory.get("identity", {}).get("name", {}).get("value")
    if name:
        lines.append(f"\n👤 Welcome back, {name}!")

    now = datetime.now()
    lines.append(f"\n📅 {now.strftime('%A, %B %d, %Y')}")
    lines.append(f"🕐 {now.strftime('%I:%M %p')}")

    tm = get_task_manager()
    stats = tm.get_stats()
    lines.append(f"\n📋 TASKS:")
    lines.append(
        f"   Total: {stats['total']} | Pending: {stats['pending']} | Completed: {stats['completed']} | Overdue: {stats['overdue']}"
    )

    if stats["by_category"]:
        lines.append(
            f"   By category: {', '.join(f'{k}({v})' for k, v in stats['by_category'].items())}"
        )

    today_tasks = tm.get_today_tasks()
    if today_tasks:
        lines.append(f"\n📌 TODAY'S TASKS ({len(today_tasks)}):")
        for t in today_tasks[:5]:
            priority_marker = {
                "urgent": "🔴",
                "high": "🟠",
                "normal": "🟡",
                "low": "⚪",
            }.get(t.priority, "⚪")
            lines.append(f"   {priority_marker} {t.title} [{t.category}]")

    overdue = tm.get_overdue_tasks()
    if overdue:
        lines.append(f"\n⚠️ OVERDUE ({len(overdue)}):")
        for t in overdue[:3]:
            lines.append(f"   🔴 {t.title} (due {t.deadline})")

    kb = get_knowledge_base()
    all_notes = kb.get_all_notes()
    if all_notes:
        lines.append(f"\n📝 NOTES: {len(all_notes)} total")
        folders = kb.get_folders()
        if folders:
            lines.append(f"   Folders: {', '.join(folders[:5])}")

    user_mem = format_memory_for_prompt(memory)
    if user_mem:
        mem_lines = [l for l in user_mem.split("\n") if l.strip()]
        if mem_lines:
            lines.append(f"\n🧠 MEMORY HIGHLIGHTS:")
            for l in mem_lines[1:6]:
                lines.append(f"   {l}")

    lines.append("\n" + "=" * 50)

    return "\n".join(lines)


def show_dashboard(player=None) -> str:
    """Show the dashboard in GUI or return as text."""
    summary = get_dashboard_summary()
    try:
        print(summary)
    except UnicodeEncodeError:
        print(summary.encode("ascii", "replace").decode("ascii"))

    if player and hasattr(player, "write_log"):
        player.write_log(summary)

    return summary


def task_action(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Task management action."""
    action = parameters.get("action", "list")

    from memory.task_manager import get_task_manager

    tm = get_task_manager()

    if action == "list":
        tasks = tm.get_pending_tasks()
        if not tasks:
            return "No pending tasks."

        lines = ["📋 Pending Tasks:"]
        for t in tasks[:10]:
            lines.append(f"  • {t.title} [{t.category}] {t.priority}")
        return "\n".join(lines)

    elif action == "create":
        title = parameters.get("title")
        if not title:
            return "Please provide a title."

        category = parameters.get("category", "general")
        priority = parameters.get("priority", "normal")
        deadline = parameters.get("deadline")

        task = tm.create_task(
            title=title,
            description=parameters.get("description", ""),
            category=category,
            priority=priority,
            deadline=deadline,
            tags=parameters.get("tags", []),
        )
        return f"✅ Task created: {task.title} (ID: {task.id})"

    elif action == "complete":
        task_id = parameters.get("task_id")
        if not task_id:
            return "Please provide task_id."

        tm.complete_task(task_id)
        return f"✅ Task completed: {task_id}"

    elif action == "today":
        tasks = tm.get_today_tasks()
        if not tasks:
            return "No tasks due today."

        lines = ["📌 Today's Tasks:"]
        for t in tasks:
            lines.append(f"  • {t.title} [{t.priority}]")
        return "\n".join(lines)

    elif action == "stats":
        stats = tm.get_stats()
        return f"Tasks: {stats['total']} total, {stats['pending']} pending, {stats['completed']} completed, {stats['overdue']} overdue"

    return f"Unknown action: {action}"


def note_action(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Note/knowledge base action."""
    action = parameters.get("action", "list")

    from memory.knowledge_base import get_knowledge_base

    kb = get_knowledge_base()

    if action == "create":
        title = parameters.get("title")
        content = parameters.get("content", "")
        if not title:
            return "Please provide a title."

        note = kb.create_note(
            title=title,
            content=content,
            tags=parameters.get("tags", []),
            folder=parameters.get("folder", "general"),
        )
        return f"✅ Note created: {note.title} (ID: {note.id})"

    elif action == "search":
        query = parameters.get("query")
        if not query:
            return "Please provide a search query."

        results = kb.search(query, top_k=5)
        if not results:
            return "No matching notes found."

        lines = ["📝 Search Results:"]
        for r in results:
            lines.append(f"  • {r['title']} (score: {r['score']:.2f})")
            if r.get("tags"):
                lines.append(f"    Tags: {', '.join(r['tags'])}")
        return "\n".join(lines)

    elif action == "list":
        notes = kb.get_all_notes()
        if not notes:
            return "No notes yet."

        lines = ["📝 All Notes:"]
        for n in notes[:10]:
            lines.append(f"  • {n.title} [{n.folder}]")
        return "\n".join(lines)

    elif action == "folders":
        folders = kb.get_folders()
        return f"Folders: {', '.join(folders) if folders else 'None'}"

    return f"Unknown action: {action}"


def memory_action(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Memory system action."""
    action = parameters.get("action", "show")

    from memory.memory_manager import load_memory, format_memory_for_prompt
    from memory.vector_memory import get_vector_store

    if action == "show":
        memory = load_memory()
        formatted = format_memory_for_prompt(memory)
        if not formatted:
            return "No memory stored yet."
        return formatted

    elif action == "search":
        query = parameters.get("query")
        if not query:
            return "Please provide a search query."

        vs = get_vector_store()
        results = vs.search(query, top_k=5)
        if not results:
            return "No matching memories found."

        lines = ["🧠 Semantic Search Results:"]
        for r in results:
            lines.append(f"  • {r['content'][:80]}... (score: {r['score']:.2f})")
        return "\n".join(lines)

    elif action == "add":
        content = parameters.get("content")
        if not content:
            return "Please provide content to remember."

        vs = get_vector_store()
        mem_id = vs.add_memory(
            content=content,
            memory_type=parameters.get("type", "general"),
            metadata=parameters.get("metadata"),
        )
        return f"✅ Memory added: {mem_id}"

    return f"Unknown action: {action}"


def calendar_action(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Calendar action."""
    from integrations.calendar_client import get_calendar_client

    cal = get_calendar_client()

    if not cal.is_configured():
        return "⚠️ Google Calendar not configured. Add credentials to config/calendar_credentials.json"

    action = parameters.get("action", "today")

    if action == "today":
        events = cal.get_today_events()
        if not events:
            return "No events scheduled for today."

        lines = ["📅 Today's Events:"]
        for e in events:
            start = (
                e.start_time.split("T")[1][:5] if "T" in e.start_time else e.start_time
            )
            lines.append(f"  • {start} - {e.title}")
        return "\n".join(lines)

    elif action == "upcoming":
        events = cal.get_upcoming_events(days=parameters.get("days", 7))
        if not events:
            return "No upcoming events."

        lines = ["📅 Upcoming Events:"]
        for e in events[:10]:
            date = e.start_time.split("T")[0] if "T" in e.start_time else e.start_time
            lines.append(f"  • {date} - {e.title}")
        return "\n".join(lines)

    elif action == "create":
        title = parameters.get("title")
        start = parameters.get("start_time")
        end = parameters.get("end_time")

        if not title or not start or not end:
            return "Please provide title, start_time, and end_time."

        event = cal.create_event(
            title=title,
            start_time=start,
            end_time=end,
            description=parameters.get("description", ""),
            location=parameters.get("location", ""),
        )
        if event:
            return f"✅ Event created: {event.title}"
        return "Failed to create event."

    elif action == "free":
        slots = cal.find_free_slots(
            duration_minutes=parameters.get("duration", 60),
            days_ahead=parameters.get("days", 7),
        )
        if not slots:
            return "No free slots found."

        lines = ["📅 Free Slots:"]
        for s in slots[:10]:
            lines.append(f"  • {s['date']} {s['start']}-{s['end']}")
        return "\n".join(lines)

    return f"Unknown action: {action}"


def email_action(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Email action."""
    from integrations.gmail_client import get_gmail_client

    gmail = get_gmail_client()

    if not gmail.is_configured():
        return (
            "⚠️ Gmail not configured. Add credentials to config/gmail_credentials.json"
        )

    action = parameters.get("action", "unread")

    if action == "unread":
        emails = gmail.get_unread_emails(max_results=5)
        if not emails:
            return "No unread emails."

        lines = ["📧 Unread Emails:"]
        for e in emails:
            lines.append(f"  • {e.sender}: {e.subject}")
            lines.append(f"    {e.snippet[:60]}...")
        return "\n".join(lines)

    elif action == "recent":
        emails = gmail.get_recent_emails(max_results=5)
        if not emails:
            return "No recent emails."

        lines = ["📧 Recent Emails:"]
        for e in emails:
            lines.append(f"  • {e.sender}: {e.subject}")
        return "\n".join(lines)

    elif action == "summarize":
        email_id = parameters.get("email_id")
        if not email_id:
            return "Please provide email_id."

        emails = gmail.get_messages(max_results=1, query=f"id:{email_id}")
        if emails:
            summary = gmail.summarize_email(emails[0])
            return f"📧 Summary: {summary}"
        return "Email not found."

    elif action == "draft":
        to = parameters.get("to")
        subject = parameters.get("subject")
        body = parameters.get("body")

        if not to or not subject or not body:
            return "Please provide to, subject, and body."

        from integrations.gmail_client import EmailDraft

        draft = EmailDraft(to=to, subject=subject, body=body)
        if gmail.create_draft(draft):
            return f"✅ Draft created for {to}"
        return "Failed to create draft."

    return f"Unknown action: {action}"


def dashboard(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """Main dashboard action."""
    view = parameters.get("view", "summary")

    if view == "summary":
        return show_dashboard(player)

    elif view == "tasks":
        return task_action({"action": "list"}, response, player, session_memory)

    elif view == "notes":
        return note_action({"action": "list"}, response, player, session_memory)

    elif view == "calendar":
        return calendar_action({"action": "today"}, response, player, session_memory)

    elif view == "email":
        return email_action({"action": "unread"}, response, player, session_memory)

    elif view == "memory":
        return memory_action({"action": "show"}, response, player, session_memory)

    return f"Unknown view: {view}"
