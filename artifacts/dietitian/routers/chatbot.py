"""
routers/chatbot.py - AI Diet Chatbot routes
Handles conversational AI using Groq API with user profile context.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from routers.auth import get_current_user
from routers.badges import award_badge
import os
import json

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# System prompt for the diet chatbot
SYSTEM_PROMPT = """You are NutriBot, an expert AI dietitian specializing in Indian cuisine and nutrition.
You help users with:
- Diet and nutrition advice
- Indian food alternatives for health conditions
- Calorie and nutrient information
- Healthy eating habits
- Exercise and lifestyle tips

Keep your responses concise, friendly, and practical. 
Use Indian food examples when possible.
If the user asks about medical conditions, remind them to consult a doctor.
Respond in 2-4 short paragraphs maximum."""


async def get_ai_response(messages: list, user_profile: dict = None) -> str:
    """
    Get a response from Groq AI for the chatbot.
    Includes user's health profile as context.
    """
    if not GROQ_API_KEY:
        return ("I'm NutriBot, your AI diet assistant! 🥗\n\n"
                "To activate me, please add your **Groq API key** as the `GROQ_API_KEY` "
                "environment secret. You can get a free key at console.groq.com.\n\n"
                "Once configured, I can answer all your diet and nutrition questions!")

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        # Build context-aware system prompt if profile exists
        system = SYSTEM_PROMPT
        if user_profile:
            system += f"""

Current user profile context:
- Age: {user_profile.get('age')}, Gender: {user_profile.get('gender')}
- Health conditions: {user_profile.get('diseases') or 'None'}
- Food preference: {user_profile.get('food_preferences')}
- Fitness goal: {user_profile.get('fitness_goals')}
- Region: {user_profile.get('region')} Indian cuisine"""

        api_messages = [{"role": "system", "content": system}] + messages

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=api_messages,
            temperature=0.7,
            max_tokens=500
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}. Please try again."


# -------------------------
# GET /chatbot - Show chatbot page
# -------------------------
@router.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page(request: Request):
    """Render the AI chatbot page with conversation history"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        # Get last 20 messages for display
        history = db.execute("""
            SELECT role, message, created_at FROM chatbot_history
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 20
        """, (user_id,)).fetchall()

        history_list = list(reversed([dict(h) for h in history]))

    finally:
        db.close()

    return templates.TemplateResponse(request, "chatbot.html", {
        "history": history_list,
        "has_api_key": bool(GROQ_API_KEY),
        "username": request.session.get("username")
    })


# -------------------------
# POST /chatbot - Send a message to the AI
# -------------------------
@router.post("/chatbot")
async def chat(request: Request):
    """
    Handle a chat message from the user.
    Returns AI response as JSON for AJAX updates.
    """
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    body = await request.json()
    user_message = body.get("message", "").strip()

    if not user_message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    db = get_db()
    try:
        # Get user's health profile for context
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        profile_dict = dict(profile) if profile else {}

        # Get recent conversation history for context (last 10 messages)
        history = db.execute("""
            SELECT role, message FROM chatbot_history
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 10
        """, (user_id,)).fetchall()

        # Build messages array for Groq API (oldest first)
        messages = [{"role": h["role"], "content": h["message"]} for h in reversed(history)]
        messages.append({"role": "user", "content": user_message})

        # Get AI response
        ai_response = await get_ai_response(messages, profile_dict)

        # Save both messages to history
        db.execute(
            "INSERT INTO chatbot_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, "user", user_message)
        )
        db.execute(
            "INSERT INTO chatbot_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, "assistant", ai_response)
        )

        # Award chat explorer badge on first message
        msg_count = db.execute(
            "SELECT COUNT(*) as cnt FROM chatbot_history WHERE user_id = ? AND role = 'user'",
            (user_id,)
        ).fetchone()["cnt"]

        if msg_count == 1:
            award_badge(db, user_id, "chat_explorer", "Chat Explorer", "🤖")

        db.commit()

        return JSONResponse({
            "response": ai_response,
            "timestamp": "Just now"
        })

    finally:
        db.close()


# -------------------------
# GET /health-report - AI-generated health summary
# -------------------------
@router.get("/health-report")
async def health_report(request: Request):
    """Generate an AI health report based on user's progress data"""
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    try:
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not profile:
            return JSONResponse({"report": "Please complete your health profile first."})

        profile_dict = dict(profile)

        # Get last 7 days of progress
        logs = db.execute("""
            SELECT * FROM progress_logs
            WHERE user_id = ?
            AND log_date >= date('now', '-7 days')
            ORDER BY log_date DESC
        """, (user_id,)).fetchall()

        logs_list = [dict(l) for l in logs]

        if not GROQ_API_KEY:
            report = ("Health report requires the Groq API key. "
                     "Add GROQ_API_KEY to your environment secrets to enable this feature.")
            return JSONResponse({"report": report})

        # Build report prompt
        avg_water = sum(l["water_ml"] for l in logs_list) / max(len(logs_list), 1)
        avg_exercise = sum(l["exercise_min"] for l in logs_list) / max(len(logs_list), 1)
        avg_sleep = sum(l["sleep_hours"] for l in logs_list) / max(len(logs_list), 1)
        avg_mood = sum(l["mood"] for l in logs_list) / max(len(logs_list), 1)

        prompt = f"""As a dietitian, write a brief, encouraging weekly health summary for:
- Age: {profile_dict.get('age')}, Gender: {profile_dict.get('gender')}
- Health conditions: {profile_dict.get('diseases') or 'None'}
- Goal: {profile_dict.get('fitness_goals')}
- Last 7 days average: Water {avg_water:.0f}ml/day, Exercise {avg_exercise:.0f}min/day, 
  Sleep {avg_sleep:.1f}hrs, Mood {avg_mood:.1f}/5
- Days logged: {len(logs_list)} out of 7

Write 3 short paragraphs: (1) What's going well, (2) Area to improve, (3) This week's tip.
Keep it warm, positive, and actionable."""

        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=400
        )
        report = completion.choices[0].message.content

    except Exception as e:
        report = f"Could not generate report: {str(e)}"
    finally:
        db.close()

    return JSONResponse({"report": report})
