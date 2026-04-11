"""Background smart planner — scans calendar periodically and generates alerts."""

import threading
from datetime import date, datetime

from campus_calendar.event_model import EVENT_LABELS, event_type_from_str
from campus_calendar.event_store import CalendarEventStore

SCAN_INTERVAL_SECONDS = 5 * 60 * 60  # 5 hours


class SmartPlannerTask:
    def __init__(
        self,
        store: CalendarEventStore,
        get_memory_manager: callable,
        notification_center,  # NotificationCenter
        page,  # ft.Page for run_task
        open_chat_fn: callable = None,  # callback(prompt: str)
    ):
        self._store = store
        self._get_mgr = get_memory_manager
        self._notif = notification_center
        self._page = page
        self._open_chat_fn = open_chat_fn
        self._timer: threading.Timer | None = None
        self._running = False

    def start(self):
        """Start the planner — runs immediately, then every 5 hours."""
        self._running = True
        # Run first scan in a background thread
        threading.Thread(target=self._scan, daemon=True).start()
        self._schedule_next()

    def stop(self):
        """Stop the periodic planner."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self):
        if not self._running:
            return
        self._timer = threading.Timer(SCAN_INTERVAL_SECONDS, self._scan_and_reschedule)
        self._timer.daemon = True
        self._timer.start()

    def _scan_and_reschedule(self):
        self._scan()
        self._schedule_next()

    def _scan(self):
        """Scan upcoming tasks and generate notifications."""
        try:
            tasks = self._store.get_actionable_tasks(days=14)
            today = date.today()
            alerts = []

            for d, event in tasks:
                days_until = (d - today).days
                title = event.get("title", "Task")
                status = event.get("status")
                et = event_type_from_str(event.get("type", "custom"))
                label = EVENT_LABELS.get(et, "Task")
                event_id = event["id"]

                # Overdue — past due and not completed
                if days_until < 0 and status != "completed":
                    self._store.update_event(event_id, {"status": "overdue"})
                    alerts.append({
                        "message": f"OVERDUE: {title} ({label}) was due {abs(days_until)} day(s) ago!",
                        "icon": "WARNING_AMBER",
                        "color": "ERROR",
                        "prompt": f"I noticed your {title} ({label}) is overdue by {abs(days_until)} day(s). I'd like to help you catch up — have you started working on it, or do you need a plan?",
                        "title": title,
                        "event_id": event_id,
                        "due_date": d.isoformat(),
                    })

                elif days_until <= 3 and status in (None, "pending"):
                    alerts.append({
                        "message": f"{title} ({label}) is due in {days_until} day(s)! How's it going?",
                        "icon": "SCHEDULE",
                        "color": "ORANGE",
                        "prompt": f"Hey! Just checking in on your {title} ({label}) — it's due in {days_until} day(s). How are you doing with it? Have you started, still working on it, or already done?",
                        "title": title,
                        "event_id": event_id,
                        "due_date": d.isoformat(),
                    })

                elif days_until <= 7 and status is None:
                    alerts.append({
                        "message": f"Upcoming: {title} ({label}) due in {days_until} days",
                        "icon": "CALENDAR_MONTH",
                        "color": "TEAL",
                        "prompt": f"Heads up! Your {title} ({label}) is coming up in {days_until} days. Have you thought about when you'll work on it? I can help you plan your time.",
                        "title": title,
                        "event_id": event_id,
                        "due_date": d.isoformat(),
                    })

            # Deliver notifications via page.run_task for thread safety
            if alerts:
                import flet as ft

                async def _deliver():
                    for alert in alerts:
                        icon = getattr(ft.Icons, alert["icon"], ft.Icons.INFO)
                        color = getattr(ft.Colors, alert["color"], ft.Colors.TEAL)

                        click_fn = None
                        if self._open_chat_fn:
                            a = alert  # capture for closure
                            click_fn = lambda e, _a=a: self._open_chat_fn(
                                _a["prompt"], _a.get("title", "Task"), _a.get("event_id"), _a.get("due_date")
                            )

                        self._notif.add(
                            alert["message"],
                            icon=icon,
                            color=color,
                            on_click=click_fn,
                        )

                self._page.run_task(_deliver)

            # Store scan summary in Mem0
            mgr = self._get_mgr()
            if mgr and tasks:
                def _store_summary():
                    try:
                        overdue = sum(1 for _, e in tasks if e.get("status") == "overdue")
                        pending = sum(1 for _, e in tasks if e.get("status") in (None, "pending"))
                        mgr.add_turn(
                            "Smart planner background scan",
                            f"Scanned {len(tasks)} upcoming tasks. {overdue} overdue, {pending} pending/unknown status.",
                        )
                    except Exception:
                        pass

                threading.Thread(target=_store_summary, daemon=True).start()

        except Exception as e:
            print(f"[Planner] Scan error: {e}", flush=True)
