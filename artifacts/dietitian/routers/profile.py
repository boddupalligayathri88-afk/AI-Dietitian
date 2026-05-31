"""
routers/profile.py - Health profile routes
Handles onboarding form submission and profile editing.
Also computes BMI, BMR, and daily calorie needs.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from routers.auth import get_current_user
import os
import math

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


# -------------------------
# BMI & Health Calculation Functions
# -------------------------

def calculate_bmi(weight_kg: float, height_cm: float) -> dict:
    """
    Calculate BMI and determine the category.
    BMI = weight(kg) / height(m)^2
    """
    if height_cm <= 0 or weight_kg <= 0:
        return {"bmi": 0, "category": "Unknown"}

    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m ** 2), 1)

    if bmi < 18.5:
        category = "Underweight"
        color = "blue"
    elif bmi < 25:
        category = "Normal"
        color = "green"
    elif bmi < 30:
        category = "Overweight"
        color = "yellow"
    else:
        category = "Obese"
        color = "red"

    return {"bmi": bmi, "category": category, "color": color}


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.
    This is the number of calories burned at complete rest.

    Male:   BMR = 10*weight + 6.25*height - 5*age + 5
    Female: BMR = 10*weight + 6.25*height - 5*age - 161
    """
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender.lower() == "male":
        bmr += 5
    else:
        bmr -= 161
    return round(bmr, 0)


def calculate_daily_calories(bmr: float, activity_level: str) -> float:
    """
    Calculate Total Daily Energy Expenditure (TDEE).
    Multiplies BMR by an activity factor.
    """
    activity_multipliers = {
        "sedentary": 1.2,       # Little or no exercise
        "light": 1.375,          # Light exercise 1-3 days/week
        "moderate": 1.55,        # Moderate exercise 3-5 days/week
        "active": 1.725,         # Hard exercise 6-7 days/week
        "very_active": 1.9       # Very hard exercise, physical job
    }
    multiplier = activity_multipliers.get(activity_level, 1.55)
    return round(bmr * multiplier, 0)


def get_health_score(bmi_category: str, sleep_hours: float, water_habit: str, activity_level: str) -> int:
    """
    Calculate a composite health score out of 100.
    Based on BMI, sleep, hydration, and activity level.
    """
    score = 0

    # BMI score (0-40 points)
    bmi_scores = {"Normal": 40, "Underweight": 25, "Overweight": 20, "Obese": 10}
    score += bmi_scores.get(bmi_category, 20)

    # Sleep score (0-25 points)
    if 7 <= sleep_hours <= 9:
        score += 25
    elif 6 <= sleep_hours < 7 or 9 < sleep_hours <= 10:
        score += 15
    else:
        score += 5

    # Water intake score (0-20 points)
    water_scores = {"more_than_3L": 20, "2_to_3L": 15, "less_than_2L": 5}
    score += water_scores.get(water_habit, 10)

    # Activity score (0-15 points)
    activity_scores = {"very_active": 15, "active": 12, "moderate": 10, "light": 6, "sedentary": 3}
    score += activity_scores.get(activity_level, 8)

    return min(score, 100)


# -------------------------
# GET /onboarding - Show health profile form
# -------------------------
@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    """Render the health profile onboarding form"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        # Pre-fill form if profile already exists
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        profile_data = dict(profile) if profile else {}
    finally:
        db.close()

    return templates.TemplateResponse(request, "onboarding.html", {
        "profile": profile_data,
        "username": request.session.get("username")
    })


# -------------------------
# POST /profile - Save health profile
# -------------------------
@router.post("/profile")
async def save_profile(
    request: Request,
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    diseases: str = Form(""),
    food_preferences: str = Form("veg"),
    allergies: str = Form(""),
    budget: str = Form("medium"),
    fitness_goals: str = Form("maintenance"),
    activity_level: str = Form("moderate"),
    sleep_hours: float = Form(7.0),
    water_habit: str = Form("2_to_3L"),
    region: str = Form("north")
):
    """Save or update the user's health profile"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        # Upsert: insert or replace if exists
        db.execute("""
            INSERT INTO health_profiles 
                (user_id, name, age, gender, height_cm, weight_kg, diseases, food_preferences,
                 allergies, budget, fitness_goals, activity_level, sleep_hours, water_habit, region, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name, age=excluded.age, gender=excluded.gender,
                height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,
                diseases=excluded.diseases, food_preferences=excluded.food_preferences,
                allergies=excluded.allergies, budget=excluded.budget,
                fitness_goals=excluded.fitness_goals, activity_level=excluded.activity_level,
                sleep_hours=excluded.sleep_hours, water_habit=excluded.water_habit,
                region=excluded.region, updated_at=CURRENT_TIMESTAMP
        """, (user_id, name, age, gender, height_cm, weight_kg, diseases, food_preferences,
              allergies, budget, fitness_goals, activity_level, sleep_hours, water_habit, region))
        db.commit()
    finally:
        db.close()

    return RedirectResponse(url="/dashboard", status_code=302)


# -------------------------
# GET /bmi - JSON API for BMI/BMR data
# -------------------------
@router.get("/bmi")
async def get_bmi(request: Request):
    """Return calculated health metrics as JSON"""
    user_id = get_current_user(request)
    if not user_id:
        return {"error": "Not authenticated"}

    db = get_db()
    try:
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not profile:
            return {"error": "Profile not found"}

        profile = dict(profile)
        bmi_data = calculate_bmi(profile["weight_kg"], profile["height_cm"])
        bmr = calculate_bmr(profile["weight_kg"], profile["height_cm"], profile["age"], profile["gender"])
        daily_cal = calculate_daily_calories(bmr, profile["activity_level"])
        health_score = get_health_score(
            bmi_data["category"], profile["sleep_hours"],
            profile["water_habit"], profile["activity_level"]
        )

        return {
            "bmi": bmi_data["bmi"],
            "bmi_category": bmi_data["category"],
            "bmi_color": bmi_data["color"],
            "bmr": bmr,
            "daily_calories": daily_cal,
            "health_score": health_score
        }
    finally:
        db.close()


# -------------------------
# GET /profile - Profile edit page
# -------------------------
@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Render the profile editing page"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    try:
        profile = db.execute(
            "SELECT * FROM health_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

        user = db.execute(
            "SELECT username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        profile_data = dict(profile) if profile else {}
        bmi_data = {}
        if profile_data:
            bmi_info = calculate_bmi(profile_data.get("weight_kg", 0), profile_data.get("height_cm", 0))
            bmr = calculate_bmr(profile_data.get("weight_kg", 0), profile_data.get("height_cm", 0),
                               profile_data.get("age", 0), profile_data.get("gender", "male"))
            daily_cal = calculate_daily_calories(bmr, profile_data.get("activity_level", "moderate"))
            bmi_data = {**bmi_info, "bmr": bmr, "daily_calories": daily_cal}

    finally:
        db.close()

    return templates.TemplateResponse(request, "profile.html", {
        "profile": profile_data,
        "bmi_data": bmi_data,
        "user": dict(user) if user else {},
        "username": request.session.get("username")
    })
