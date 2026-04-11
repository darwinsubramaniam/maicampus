import threading
from datetime import date, datetime, timezone

from campus_calendar.event_model import EVENT_LABELS, event_type_from_str
from services import calendar_store as _store, get_memory_manager as _get_mgr
from tools import ToolDefinition, register


def _handle_update_task_status(args: dict) -> dict:
    event_id = args.get("event_id")
    if not event_id:
        return {"error": "event_id is required"}

    event = _store.get_event(event_id)
    if not event:
        return {"error": f"Event {event_id} not found"}

    update = {"status": args.get("status", "in_progress")}
    hours = args.get("hours_spent")
    if hours is not None:
        update["actual_hours_spent"] = float(hours)

    _store.update_event(event_id, update)
    return {"success": True, "event_id": event_id, "status": update["status"]}


def _handle_log_completion(args: dict) -> dict:
    event_id = args.get("event_id")
    if not event_id:
        return {"error": "event_id is required"}

    event = _store.get_event(event_id)
    if not event:
        return {"error": f"Event {event_id} not found"}

    actual_hours = float(args.get("actual_hours", 0))
    now = datetime.now(timezone.utc).isoformat()

    _store.update_event(event_id, {
        "status": "completed",
        "actual_hours_spent": actual_hours,
        "completed_at": now,
    })

    # Learn from completion — store competency data in Mem0
    mgr = _get_mgr()
    if mgr:
        subject = event.get("subject") or event.get("type", "task")
        title = event.get("title", "task")
        estimate = event.get("time_estimate_hours")

        if estimate and actual_hours:
            ratio = actual_hours / estimate
            if ratio > 1.5:
                insight = f"Student underestimated {subject} task '{title}': estimated {estimate}h, took {actual_hours}h"
            elif ratio < 0.6:
                insight = f"Student overestimated {subject} task '{title}': estimated {estimate}h, took {actual_hours}h"
            else:
                insight = f"Student completed {subject} task '{title}' on track: estimated {estimate}h, took {actual_hours}h"
        else:
            insight = f"Student completed {subject} task '{title}' in {actual_hours}h"

        def _store_insight():
            try:
                mgr.add_turn(
                    f"I finished {title}. It took me {actual_hours} hours.",
                    f"Great work! I've noted that. {insight}",
                )
            except Exception:
                pass

        threading.Thread(target=_store_insight, daemon=True).start()

    return {
        "success": True,
        "event_id": event_id,
        "title": event.get("title"),
        "actual_hours": actual_hours,
    }


def _handle_get_priority_tasks(args: dict) -> dict:
    days = int(args.get("days", 14))
    tasks = _store.get_actionable_tasks(days=days)

    mgr = _get_mgr()
    scored = []
    for d, event in tasks:
        days_until = max(0.1, (d - date.today()).days)
        deadline_urgency = 1.0 / days_until

        estimate = event.get("time_estimate_hours") or 2.0
        subject = event.get("subject") or event.get("type", "task")
        et = event_type_from_str(event.get("type", "custom"))

        # Check Mem0 for subject difficulty
        subject_difficulty = 1.0
        proc_risk = 1.0
        if mgr:
            try:
                memories = mgr.search_relevant(f"{subject} hours estimated actual difficulty")
                for m in memories:
                    if "underestimate" in m.lower():
                        subject_difficulty = max(subject_difficulty, 2.0)
                    if "late" in m.lower() or "overdue" in m.lower() or "procrastinat" in m.lower():
                        proc_risk = max(proc_risk, 1.5)
            except Exception:
                pass

        score = deadline_urgency * 3 + estimate * 2 + subject_difficulty * 1.5 + proc_risk
        status = event.get("status") or "unknown"

        scored.append({
            "event_id": event["id"],
            "title": event.get("title", ""),
            "type": EVENT_LABELS.get(et, "Task"),
            "subject": subject,
            "due_date": d.isoformat(),
            "days_until_due": int(days_until),
            "status": status,
            "estimated_hours": estimate,
            "priority_score": round(score, 1),
        })

    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"tasks": scored, "count": len(scored)}


def _handle_get_competency(args: dict) -> dict:
    subject = args.get("subject", "")
    mgr = _get_mgr()
    if not mgr:
        return {"memories": [], "subject": subject}

    try:
        memories = mgr.search_relevant(
            f"{subject} completion hours estimated actual performance competency",
            top_k=10,
        )
        return {"subject": subject, "memories": memories, "count": len(memories)}
    except Exception as e:
        return {"error": str(e), "subject": subject}


# Register tools
register(ToolDefinition(
    name="update_task_status",
    description="Update the status of a calendar task (assignment or exam). Use when a student reports progress on a task.",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event/task ID to update"},
            "status": {
                "type": "string",
                "description": "New status",
                "enum": ["pending", "in_progress", "completed", "overdue"],
            },
            "hours_spent": {"type": "number", "description": "Hours spent so far (optional)"},
        },
        "required": ["event_id", "status"],
    },
    handler=_handle_update_task_status,
))

register(ToolDefinition(
    name="log_task_completion",
    description="Log that a student has completed a task/assignment. Records actual time spent and learns from the data for future predictions.",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event/task ID that was completed"},
            "actual_hours": {"type": "number", "description": "Actual hours the student spent on this task"},
        },
        "required": ["event_id", "actual_hours"],
    },
    handler=_handle_log_completion,
))

register(ToolDefinition(
    name="get_priority_tasks",
    description="Get a prioritized list of upcoming assignments and exams with smart scoring based on deadlines, estimated effort, and student's historical performance patterns.",
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "Number of days to look ahead (default: 14)"},
        },
        "required": [],
    },
    handler=_handle_get_priority_tasks,
))

register(ToolDefinition(
    name="get_student_competency",
    description="Get the student's performance patterns and competency data for a specific subject or course. Shows historical completion times and behavioral insights.",
    parameters={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "The subject or course name to check (e.g. 'Math', 'Physics', 'Writing')"},
        },
        "required": ["subject"],
    },
    handler=_handle_get_competency,
))
