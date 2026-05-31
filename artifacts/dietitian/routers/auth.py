"""
routers/auth.py - Authentication routes: register, login, logout
Handles user account creation and session management.
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from database import get_db
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Password hashing context using bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def truncate_password(password: str) -> str:
    """Truncate password to bcrypt's 72-byte limit"""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt"""
    return pwd_context.hash(truncate_password(password))


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its hash"""
    return pwd_context.verify(truncate_password(plain), hashed)


def get_current_user(request: Request):
    """
    Get the currently logged-in user from the session.
    Returns the user_id if logged in, else None.
    """
    return request.session.get("user_id")


# -------------------------
# GET /login - Show login/register page
# -------------------------
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login and registration page"""
    # If already logged in, redirect to dashboard
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {"error": None})


# -------------------------
# GET / - Redirect root to login or dashboard
# -------------------------
@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to dashboard if logged in, else to login page"""
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


# -------------------------
# POST /register - Handle new user registration
# -------------------------
@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """
    Register a new user account.
    Validates inputs, hashes password, stores in database.
    """
    # Truncate passwords to bcrypt limit (72 bytes) before validation
    password = truncate_password(password)
    confirm_password = truncate_password(confirm_password)

    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(request, "landing.html", {
            "error": "Passwords do not match",
            "tab": "register"
        })

    # Validate password length
    if len(password) < 6:
        return templates.TemplateResponse(request, "landing.html", {
            "error": "Password must be at least 6 characters",
            "tab": "register"
        })

    db = get_db()
    try:
        # Check if username or email already exists
        existing = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()

        if existing:
            return templates.TemplateResponse(request, "landing.html", {
                "error": "Username or email already registered",
                "tab": "register"
            })

        # Hash password and insert user
        hashed = hash_password(password)
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        db.commit()

        # Log the user in immediately after registration
        request.session["user_id"] = cursor.lastrowid
        request.session["username"] = username

        return RedirectResponse(url="/onboarding", status_code=302)

    except Exception as e:
        return templates.TemplateResponse(request, "landing.html", {
            "error": f"Registration failed: {str(e)}",
            "tab": "register"
        })
    finally:
        db.close()


# -------------------------
# POST /login - Handle login form submission
# -------------------------
@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Authenticate a user and start a session.
    """
    db = get_db()
    try:
        # Find the user by username
        user = db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse(request, "landing.html", {
                "error": "Invalid username or password",
                "tab": "login"
            })

        # Store user info in session
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]

        # Check if profile exists, redirect to onboarding if not
        profile = db.execute(
            "SELECT id FROM health_profiles WHERE user_id = ?",
            (user["id"],)
        ).fetchone()

        if not profile:
            return RedirectResponse(url="/onboarding", status_code=302)

        return RedirectResponse(url="/dashboard", status_code=302)

    finally:
        db.close()


# -------------------------
# GET /logout - End user session
# -------------------------
@router.get("/logout")
async def logout(request: Request):
    """Clear the user session and redirect to login"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
