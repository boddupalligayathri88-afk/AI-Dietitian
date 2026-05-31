"""
routers/progress.py - Daily progress tracking routes
Handles logging meals, water, exercise, sleep, and mood.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from routers.auth import get_current_user
from routers.badges import check_and_award_badges
import os
import json
from datetime import date, timedelta

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


# -------------------------
# GET /tracker - Show daily tracker page
# -------------------------
@router.get("/tracker", response_class=HTMLResponse)
async def tracker_page(request: Request):
    """Render the daily progress tracker page"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    today = date.today().isoformat()

    db = get_db()
    try:
        # Get today's log if it exists
        today_log = db.execute(
            "SELECT * FROM progress_logs WHERE user_id = ? AND log_date = ?",
            (user_id, today)
        ).fetchone()

        # Get streak count (consecutive days logged)
        streak = calculate_streak(db, user_id)

        today_data = dict(today_log) if today_log else {}

    finally:
        db.close()

    return templates.TemplateResponse(request, "tracker.html", {
        "today": today,
        "today_log": today_data,
        "streak": streak,
        "username": request.session.get("username")
    })


# -------------------------
# POST /progress - Save daily progress log
# -------------------------
@router.post("/progress")
async def save_progress(
    request: Request,
    log_date: str = Form(...),
    water_ml: int = Form(0),
    exercise_min: int = Form(0),
    sleep_hours: float = Form(0.0),
    mood: int = Form(3),
    notes: str = Form(""),
    meals_json: str = Form("[]")
):
    """Save or update the daily progress log"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        db.execute("""
            INSERT INTO progress_logs 
                (user_id, log_date, meals_json, water_ml, exercise_min, sleep_hours, mood, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, log_date) DO UPDATE SET
                meals_json=excluded.meals_json, water_ml=excluded.water_ml,
                exercise_min=excluded.exercise_min, sleep_hours=excluded.sleep_hours,
                mood=excluded.mood, notes=excluded.notes
        """, (user_id, log_date, meals_json, water_ml, exercise_min, sleep_hours, mood, notes))
        db.commit()

        # Check for new badge awards after logging
        check_and_award_badges(db, user_id)
        db.commit()

    finally:
        db.close()

    return RedirectResponse(url="/tracker", status_code=302)


# -------------------------
# GET /progress - Show progress charts page
# -------------------------
@router.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request):
    """Render the progress visualization page"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "progress.html", {
        "username": request.session.get("username")
    })


# -------------------------
# GET /progress/charts - JSON data for Chart.js
# -------------------------
@router.get("/progress/charts")
async def progress_charts_data(request: Request):
    """
    Return 30 days of progress data as JSON for Chart.js visualizations.
    Includes water intake, exercise, sleep, and mood trends.
    """
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    try:
        # Get last 30 days of logs
        logs = db.execute("""
            SELECT log_date, water_ml, exercise_min, sleep_hours, mood
            FROM progress_logs
            WHERE user_id = ?
            AND log_date >= date('now', '-30 days')
            ORDER BY log_date ASC
        """, (user_id,)).fetchall()

        logs_list = [dict(l) for l in logs]

        # Weekly averages for summary cards
        weekly = db.execute("""
            SELECT 
                AVG(water_ml) as avg_water,
                AVG(exercise_min) as avg_exercise,
                AVG(sleep_hours) as avg_sleep,
                AVG(mood) as avg_mood,
                COUNT(*) as days_logged
            FROM progress_logs
            WHERE user_id = ?
            AND log_date >= date('now', '-7 days')
        """, (user_id,)).fetchone()

        # Total stats
        total = db.execute("""
            SELECT 
                COUNT(*) as total_days,
                SUM(exercise_min) as total_exercise,
                MAX(log_date) as last_log
            FROM progress_logs WHERE user_id = ?
        """, (user_id,)).fetchone()

        return JSONResponse({
            "logs": logs_list,
            "weekly_averages": dict(weekly) if weekly else {},
            "totals": dict(total) if total else {}
        })
    finally:
        db.close()


def calculate_streak(db, user_id: int) -> int:
    """
    Calculate the current consecutive days streak.
    Returns 0 if no logs, else counts back from today.
    """
    today = date.today()
    streak = 0
    check_date = today

    for _ in range(365):
        log = db.execute(
            "SELECT id FROM progress_logs WHERE user_id = ? AND log_date = ?",
            (user_id, check_date.isoformat())
        ).fetchone()

        if log:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak
