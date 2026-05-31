"""
routers/diet.py - AI Diet Plan generation routes
Uses Groq Cloud API to generate personalized Indian diet plans.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from routers.auth import get_current_user
from routers.badges import award_badge
import os
import json
import re

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def build_diet_prompt(profile: dict, special_request: str = "") -> str:
    """
    Build a detailed prompt for the Groq AI to generate a personalized Indian diet plan.
    The prompt includes all relevant health information.
    """
    diseases = profile.get("diseases", "") or "None"
    goals = profile.get("fitness_goals", "maintenance")
    budget = profile.get("budget", "medium")
    food_pref = profile.get("food_preferences", "veg")
    allergies = profile.get("allergies", "") or "None"
    region = profile.get("region", "north")
    age = profile.get("age", 25)
    gender = profile.get("gender", "male")
    activity = profile.get("activity_level", "moderate")

    goal_map = {
        "weight_loss": "lose weight",
        "muscle_gain": "build muscle",
        "maintenance": "maintain current weight",
        "improve_health": "improve overall health"
    }
    region_map = {
        "north": "North Indian",
        "south": "South Indian",
        "east": "East Indian",
        "west": "West Indian",
        "central": "Central Indian"
    }

    prompt = f"""You are an expert Indian dietitian. Create a detailed, personalized one-day diet plan for:

Patient Details:
- Age: {age}, Gender: {gender}
- Goal: {goal_map.get(goals, goals)}
- Diseases/Conditions: {diseases}
- Food Preference: {food_pref}
- Allergies: {allergies}
- Budget: {budget} (low=<500 INR/day, medium=500-1000 INR/day, high=>1000 INR/day)
- Cuisine: {region_map.get(region, region)} cuisine preferred
- Activity Level: {activity}
{f'- Special Request: {special_request}' if special_request else ''}

Respond ONLY with a valid JSON object (no markdown, no extra text) in this exact format:
{{
  "breakfast": [
    {{"name": "Food item name", "quantity": "Amount", "calories": 200, "notes": "optional note"}}
  ],
  "lunch": [
    {{"name": "Food item name", "quantity": "Amount", "calories": 300, "notes": ""}}
  ],
  "snacks": [
    {{"name": "Food item name", "quantity": "Amount", "calories": 150, "notes": ""}}
  ],
  "dinner": [
    {{"name": "Food item name", "quantity": "Amount", "calories": 350, "notes": ""}}
  ],
  "water_recommendation": "Drink 2.5-3 litres of water daily",
  "total_calories": 1800,
  "notes": "General health tip specific to the patient's condition"
}}

Rules:
- Use authentic Indian food items
- Consider diseases: for diabetes use low-GI foods, for hypertension use low-sodium foods, for thyroid use iodine-rich foods
- Keep within the budget range
- Include at least 2-3 items per meal
- All food names should be recognizable Indian dishes
"""
    return prompt


async def call_groq_api(prompt: str) -> dict:
    """
    Call Groq API to generate the diet plan.
    Returns parsed JSON or a fallback plan if API key is not set.
    """
    if not GROQ_API_KEY:
        # Return a sample plan when no API key is configured
        return get_sample_plan()

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )

        response_text = completion.choices[0].message.content.strip()

        # Extract JSON from response (in case there's any extra text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response_text)

    except Exception as e:
        print(f"Groq API error: {e}")
        return get_sample_plan()


def get_sample_plan() -> dict:
    """
    Return a sample Indian diet plan as fallback when Groq API key is not set.
    This demonstrates the app's functionality without requiring an API key.
    """
    return {
        "breakfast": [
            {"name": "Oats Upma", "quantity": "1 bowl (150g)", "calories": 180, "notes": "Rich in fibre"},
            {"name": "Boiled Eggs", "quantity": "2 eggs", "calories": 140, "notes": "High protein"},
            {"name": "Green Tea", "quantity": "1 cup", "calories": 5, "notes": "Antioxidant rich"}
        ],
        "lunch": [
            {"name": "Brown Rice", "quantity": "1 cup cooked", "calories": 215, "notes": "Complex carbs"},
            {"name": "Dal Tadka", "quantity": "1 bowl", "calories": 180, "notes": "Protein source"},
            {"name": "Mixed Sabzi", "quantity": "1 bowl", "calories": 120, "notes": "Seasonal vegetables"},
            {"name": "Cucumber Raita", "quantity": "1 small bowl", "calories": 60, "notes": "Probiotic"}
        ],
        "snacks": [
            {"name": "Roasted Chana", "quantity": "30g", "calories": 100, "notes": "High fibre snack"},
            {"name": "Buttermilk", "quantity": "1 glass", "calories": 40, "notes": "Digestive aid"}
        ],
        "dinner": [
            {"name": "Roti (Whole Wheat)", "quantity": "2 medium", "calories": 160, "notes": "Whole grain"},
            {"name": "Palak Paneer", "quantity": "1 bowl", "calories": 220, "notes": "Iron and calcium rich"},
            {"name": "Salad", "quantity": "1 plate", "calories": 50, "notes": "Fresh vegetables"}
        ],
        "water_recommendation": "Drink 8-10 glasses (2.5-3 litres) of water throughout the day",
        "total_calories": 1470,
        "notes": "This is a sample balanced Indian diet plan. Add your Groq API key to get a fully personalized plan based on your health conditions and preferences."
    }


# -------------------------
# GET /diet-plan - Show diet plan page
# -------------------------
@router.get("/diet-plan", response_class=HTMLResponse)
async def diet_plan_page(request: Request):
    """Render the diet plan page with the latest plan"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        # Get latest diet plan
        latest_plan = db.execute(
            "SELECT * FROM diet_plans WHERE user_id = ? ORDER BY generated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        # Get plan history count
        plan_count = db.execute(
            "SELECT COUNT(*) as cnt FROM diet_plans WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

        plan_data = None
        generated_at = None
        if latest_plan:
            plan_data = json.loads(latest_plan["plan_json"])
            generated_at = latest_plan["generated_at"]

        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

    finally:
        db.close()

    return templates.TemplateResponse(request, "diet_plan.html", {
        "plan": plan_data,
        "generated_at": generated_at,
        "plan_count": plan_count,
        "has_profile": profile is not None,
        "has_api_key": bool(GROQ_API_KEY),
        "username": request.session.get("username")
    })


# -------------------------
# POST /diet-plan - Generate a new diet plan
# -------------------------
@router.post("/diet-plan")
async def generate_diet_plan(
    request: Request,
    special_request: str = Form("")
):
    """Generate a new AI-powered diet plan using Groq API"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not profile:
            return RedirectResponse(url="/onboarding", status_code=302)

        profile_dict = dict(profile)

        # Build prompt and call Groq API
        prompt = build_diet_prompt(profile_dict, special_request)
        plan_data = await call_groq_api(prompt)

        # Save the plan to database
        db.execute(
            "INSERT INTO diet_plans (user_id, plan_json) VALUES (?, ?)",
            (user_id, json.dumps(plan_data))
        )
        db.commit()

        # Award 'First Plan' badge if this is the first plan
        plan_count = db.execute(
            "SELECT COUNT(*) as cnt FROM diet_plans WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

        if plan_count == 1:
            award_badge(db, user_id, "first_plan", "First Plan Generated", "🌟")

        db.commit()

    finally:
        db.close()

    return RedirectResponse(url="/diet-plan", status_code=302)


# -------------------------
# GET /diet-plan/history - Past diet plans (JSON API)
# -------------------------
@router.get("/diet-plan/history")
async def diet_plan_history(request: Request):
    """Return list of past diet plans as JSON"""
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    try:
        plans = db.execute(
            "SELECT id, generated_at FROM diet_plans WHERE user_id = ? ORDER BY generated_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()
        return JSONResponse([dict(p) for p in plans])
    finally:
        db.close()
