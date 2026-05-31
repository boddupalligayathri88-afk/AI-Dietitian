"""
main.py - AI Dietitian Web Application
Entry point for the FastAPI application.

Tech Stack:
- Backend: Python 3 + FastAPI
- Database: SQLite3
- Templates: Jinja2 (HTML + Tailwind CSS)
- AI: Groq Cloud API

Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Import all route modules
from database import init_db
from routers import auth, profile, diet, progress, badges, chatbot

# -------------------------
# App Configuration
# -------------------------

# Create the FastAPI application instance
app = FastAPI(
    title="AI Dietitian",
    description="Personalized AI-powered diet planning and health tracking",
    version="1.0.0"
)

# Session middleware for login state management
# Uses the SESSION_SECRET environment variable for signing
SESSION_SECRET = os.environ.get("SESSION_SECRET", "ai-dietitian-secret-key-change-in-production")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="dietitian_session",
    max_age=86400 * 7,  # 7 days
    https_only=False    # Set True in production with HTTPS
)

# -------------------------
# Static Files & Templates
# -------------------------

BASE_DIR = os.path.dirname(__file__)

# Serve CSS, JS, and image files from /static
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# -------------------------
# Register all route modules
# -------------------------
app.include_router(auth.router)       # /login, /register, /logout
app.include_router(profile.router)   # /onboarding, /profile, /bmi
app.include_router(diet.router)      # /diet-plan
app.include_router(progress.router)  # /tracker, /progress
app.include_router(badges.router)    # /badges
app.include_router(chatbot.router)   # /chatbot, /health-report

# -------------------------
# Dashboard Route
# -------------------------

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/dashboard")
async def dashboard(request: Request):
    """
    Main dashboard page — shows BMI, health score, badges, charts, and AI plan.
    Requires login.
    """
    from fastapi.responses import RedirectResponse, HTMLResponse
    from database import get_db
    from routers.auth import get_current_user
    from routers.profile import calculate_bmi, calculate_bmr, calculate_daily_calories, get_health_score
    import json

    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        # Load health profile
        profile_row = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        profile = dict(profile_row) if profile_row else {}

        # Calculate health metrics
        bmi_data = {}
        if profile:
            bmi_info = calculate_bmi(profile.get("weight_kg", 0), profile.get("height_cm", 0))
            bmr = calculate_bmr(
                profile.get("weight_kg", 0), profile.get("height_cm", 0),
                profile.get("age", 0), profile.get("gender", "male")
            )
            daily_cal = calculate_daily_calories(bmr, profile.get("activity_level", "moderate"))
            health_score = get_health_score(
                bmi_info["category"], profile.get("sleep_hours", 7),
                profile.get("water_habit", "2_to_3L"), profile.get("activity_level", "moderate")
            )
            bmi_data = {
                **bmi_info,
                "bmr": bmr,
                "daily_calories": daily_cal,
                "health_score": health_score
            }

        # Load latest diet plan
        latest_plan_row = db.execute(
            "SELECT plan_json FROM diet_plans WHERE user_id = ? ORDER BY generated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        latest_plan = json.loads(latest_plan_row["plan_json"]) if latest_plan_row else None

        # Load today's progress
        from datetime import date
        today = date.today().isoformat()
        today_log = db.execute(
            "SELECT * FROM progress_logs WHERE user_id = ? AND log_date = ?",
            (user_id, today)
        ).fetchone()
        today_data = dict(today_log) if today_log else {}

        # Load user's badges
        earned_badges = db.execute(
            "SELECT * FROM badges WHERE user_id = ? ORDER BY earned_at DESC",
            (user_id,)
        ).fetchall()

        # Get stats summary
        total_plans = db.execute(
            "SELECT COUNT(*) as cnt FROM diet_plans WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

        total_logs = db.execute(
            "SELECT COUNT(*) as cnt FROM progress_logs WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

        # Get last 7 days chart data
        week_logs = db.execute("""
            SELECT log_date, water_ml, exercise_min, sleep_hours, mood
            FROM progress_logs
            WHERE user_id = ? AND log_date >= date('now', '-7 days')
            ORDER BY log_date ASC~
        """, (user_id,)).fetchall()

    finally:
        db.close()

    return templates.TemplateResponse(request, "dashboard.html", {
        "profile": profile,
        "bmi_data": bmi_data,
        "latest_plan": latest_plan,
        "today_log": today_data,
        "badges": [dict(b) for b in earned_badges],
        "total_plans": total_plans,
        "total_logs": total_logs,
        "week_logs": [dict(l) for l in week_logs],
        "username": request.session.get("username"),
        "has_profile": bool(profile),
        "groq_enabled": bool(os.environ.get("GROQ_API_KEY"))
    })


# -------------------------
# Application Startup Event
# -------------------------

@app.on_event("startup")
async def startup_event():
    """
    Initialize the database and create tables on application startup.
    This runs once when the server starts.
    """
    init_db()
    print("AI Dietitian app started successfully!")
    print(f"   Groq AI: {'Enabled' if os.environ.get('GROQ_API_KEY') else 'Not configured (add GROQ_API_KEY secret)'}")


# -------------------------
# Run directly for development
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
