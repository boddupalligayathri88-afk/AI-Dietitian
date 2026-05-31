"""
routers/badges.py - Badge / Gamification system
Awards achievement badges to users based on their activity.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from routers.auth import get_current_user
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# All available badges with their descriptions
BADGE_CATALOG = {
    "first_plan": {
        "name": "First Plan Generated",
        "emoji": "🌟",
        "description": "Generated your very first AI diet plan",
        "color": "yellow"
    },
    "hydration_hero": {
        "name": "Hydration Hero",
        "emoji": "💧",
        "description": "Logged 2L+ water intake for 7 days",
        "color": "blue"
    },
    "consistency_7": {
        "name": "7 Days Consistency",
        "emoji": "🏅",
        "description": "Logged progress for 7 consecutive days",
        "color": "gold"
    },
    "healthy_streak": {
        "name": "Healthy Streak",
        "emoji": "💚",
        "description": "Maintained a healthy BMI category",
        "color": "green"
    },
    "chat_explorer": {
        "name": "Chat Explorer",
        "emoji": "🤖",
        "description": "Asked your first question to the AI chatbot",
        "color": "purple"
    },
    "exercise_warrior": {
        "name": "Exercise Warrior",
        "emoji": "🏋️",
        "description": "Logged exercise for 5 days in a week",
        "color": "orange"
    },
    "sleep_champion": {
        "name": "Sleep Champion",
        "emoji": "😴",
        "description": "Logged 7+ hours of sleep for 5 days",
        "color": "indigo"
    }
}


def award_badge(db, user_id: int, badge_type: str, badge_name: str, badge_emoji: str) -> bool:
    """
    Award a badge to a user if they don't already have it.
    Returns True if the badge was newly awarded, False if already earned.
    """
    try:
        db.execute(
            "INSERT OR IGNORE INTO badges (user_id, badge_type, badge_name, badge_emoji) VALUES (?, ?, ?, ?)",
            (user_id, badge_type, badge_name, badge_emoji)
        )
        return db.execute(
            "SELECT changes() as c"
        ).fetchone()["c"] > 0
    except Exception as e:
        print(f"Badge award error: {e}")
        return False


def check_and_award_badges(db, user_id: int):
    """
    Check various conditions and automatically award earned badges.
    Called after logging progress to check for new achievements.
    """
    # Check hydration hero: 7 days with 2000+ ml water
    hydration_days = db.execute("""
        SELECT COUNT(*) as cnt FROM progress_logs
        WHERE user_id = ? AND water_ml >= 2000
        ORDER BY log_date DESC LIMIT 7
    """, (user_id,)).fetchone()["cnt"]

    if hydration_days >= 7:
        award_badge(db, user_id, "hydration_hero", "Hydration Hero", "💧")

    # Check 7-day consistency streak
    streak = db.execute("""
        SELECT COUNT(DISTINCT log_date) as cnt FROM progress_logs
        WHERE user_id = ?
        AND log_date >= date('now', '-7 days')
    """, (user_id,)).fetchone()["cnt"]

    if streak >= 7:
        award_badge(db, user_id, "consistency_7", "7 Days Consistency", "🏅")

    # Check exercise warrior: 5 days with exercise in last 7 days
    exercise_days = db.execute("""
        SELECT COUNT(*) as cnt FROM progress_logs
        WHERE user_id = ? AND exercise_min > 0
        AND log_date >= date('now', '-7 days')
    """, (user_id,)).fetchone()["cnt"]

    if exercise_days >= 5:
        award_badge(db, user_id, "exercise_warrior", "Exercise Warrior", "🏋️")

    # Check sleep champion: 5 days with 7+ hours sleep
    sleep_days = db.execute("""
        SELECT COUNT(*) as cnt FROM progress_logs
        WHERE user_id = ? AND sleep_hours >= 7
        AND log_date >= date('now', '-7 days')
    """, (user_id,)).fetchone()["cnt"]

    if sleep_days >= 5:
        award_badge(db, user_id, "sleep_champion", "Sleep Champion", "😴")


# -------------------------
# GET /badges - Show badges page
# -------------------------
@router.get("/badges")
async def get_badges(request: Request):
    """Return user badges as JSON"""
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    try:
        earned = db.execute(
            "SELECT badge_type, badge_name, badge_emoji, earned_at FROM badges WHERE user_id = ?",
            (user_id,)
        ).fetchall()

        earned_types = {b["badge_type"] for b in earned}

        result = {
            "earned": [dict(b) for b in earned],
            "all_badges": [
                {
                    "type": k,
                    "name": v["name"],
                    "emoji": v["emoji"],
                    "description": v["description"],
                    "color": v["color"],
                    "earned": k in earned_types
                }
                for k, v in BADGE_CATALOG.items()
            ]
        }
        return JSONResponse(result)
    finally:
        db.close()
