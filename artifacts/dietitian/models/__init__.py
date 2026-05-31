"""
models/__init__.py - Pydantic models for request/response validation
These models define the data structures used across the application.
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date


# -------------------------
# Authentication Models
# -------------------------

class RegisterRequest(BaseModel):
    """Data required to register a new user"""
    username: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    """Data required to log in"""
    username: str
    password: str


# -------------------------
# Health Profile Models
# -------------------------

class HealthProfileRequest(BaseModel):
    """Complete health profile submitted during onboarding"""
    name: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    diseases: Optional[str] = ""       # comma-separated
    food_preferences: str = "veg"
    allergies: Optional[str] = ""
    budget: str = "medium"             # low / medium / high
    fitness_goals: str = "maintenance"
    activity_level: str = "moderate"
    sleep_hours: float = 7.0
    water_habit: str = "2_to_3L"
    region: str = "north"


class BMIResponse(BaseModel):
    """Calculated health metrics"""
    bmi: float
    bmi_category: str
    bmr: float
    daily_calories: float
    weight_kg: float
    height_cm: float


# -------------------------
# Diet Plan Models
# -------------------------

class DietPlanRequest(BaseModel):
    """Optional overrides when generating a diet plan"""
    special_request: Optional[str] = ""


class MealItem(BaseModel):
    name: str
    quantity: str
    calories: Optional[int] = None
    notes: Optional[str] = ""


class DietPlanResponse(BaseModel):
    breakfast: List[MealItem]
    lunch: List[MealItem]
    snacks: List[MealItem]
    dinner: List[MealItem]
    water_recommendation: str
    total_calories: Optional[int] = None
    notes: Optional[str] = ""


# -------------------------
# Progress Tracking Models
# -------------------------

class ProgressLogRequest(BaseModel):
    """Daily progress log entry"""
    log_date: str          # YYYY-MM-DD
    meals_json: Optional[str] = "[]"
    water_ml: int = 0
    exercise_min: int = 0
    sleep_hours: float = 0.0
    mood: int = 3          # 1-5
    notes: Optional[str] = ""


# -------------------------
# Chatbot Models
# -------------------------

class ChatMessage(BaseModel):
    """A single chat message from the user"""
    message: str
