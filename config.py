# config.py
import os

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Get from BotFather

# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 7379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None) # Set if your Redis requires auth

# --- Workout Definitions ---
# Structure: { internal_id: {"name": "Display Name", "alias": "cmd_alias", "goal": target_reps} }
EXERCISES = {
    "plank":    {"name": "Plank (Seconds)", "alias": "plk", "goal": 300},  # e.g., 5 minutes total
    "rope":     {"name": "Rope Skipping (Mins)", "alias": "rop", "goal": 60},
    "pushup":   {"name": "Push-Ups",        "alias": "psh", "goal": 500},
    "squat":    {"name": "Squats",          "alias": "sqt", "goal": 1000},
    "abs":      {"name": "Abs Circuit (Reps)","alias": "abs", "goal": 1000},
    "jab":      {"name": "Jabs",            "alias": "jab", "goal": 2000},
    "uppercut": {"name": "Uppercuts",       "alias": "upc", "goal": 1000},
    "straight": {"name": "Straights",       "alias": "str", "goal": 2000},
    # Add more exercises here if needed
}

# --- Charting ---
CHART_DPI = 100 # Resolution of the chart image
CHART_BAR_COLOR = '#4CAF50' # Greenish
CHART_GOAL_COLOR = '#FF5722' # Orangey-Red
CHART_FONT_SIZE = 10