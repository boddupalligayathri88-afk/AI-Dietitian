"""
database.py - SQLite3 database setup and helper functions
This module handles all database connections and table creation for the AI Dietitian app.
"""

import sqlite3
import os

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "dietitian.db")


def get_db():
    """
    Create and return a SQLite3 database connection.
    row_factory=sqlite3.Row allows accessing columns by name (like a dict).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent performance
    return conn


def init_db():
    """
    Initialize all database tables if they don't already exist.
    Called once on application startup.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # -------------------------
    # Table 1: users
    # Stores login credentials and account info
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------
    # Table 2: health_profiles
    # Stores each user's health details collected during onboarding
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            age INTEGER,
            gender TEXT,
            height_cm REAL,
            weight_kg REAL,
            diseases TEXT,          -- comma-separated: diabetes,hypertension,etc.
            food_preferences TEXT,  -- veg, non-veg, vegan
            allergies TEXT,
            budget TEXT,            -- low, medium, high
            fitness_goals TEXT,     -- weight_loss, muscle_gain, maintenance
            activity_level TEXT,    -- sedentary, light, moderate, active, very_active
            sleep_hours REAL,
            water_habit TEXT,       -- less_than_2L, 2_to_3L, more_than_3L
            region TEXT,            -- north, south, east, west, central
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -------------------------
    # Table 3: diet_plans
    # Stores AI-generated diet plans for each user
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diet_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_json TEXT NOT NULL,  -- Full JSON plan: breakfast, lunch, snacks, dinner
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -------------------------
    # Table 4: progress_logs
    # Stores daily tracking data (meals, water, exercise, sleep, mood)
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date DATE NOT NULL,
            meals_json TEXT,        -- JSON array of meals consumed
            water_ml INTEGER DEFAULT 0,
            exercise_min INTEGER DEFAULT 0,
            sleep_hours REAL DEFAULT 0,
            mood INTEGER DEFAULT 3, -- 1 (bad) to 5 (excellent)
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, log_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -------------------------
    # Table 5: badges
    # Stores gamification badges earned by users
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_type TEXT NOT NULL,  -- e.g., 'first_plan', 'hydration_hero'
            badge_name TEXT NOT NULL,
            badge_emoji TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, badge_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -------------------------
    # Table 6: chatbot_history
    # Stores conversation history with the AI diet chatbot
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,     -- 'user' or 'assistant'
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully")
