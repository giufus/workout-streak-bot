# config.py
import os
import json

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Get from BotFather

# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 7379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None) # Set if your Redis requires auth

# --- Workout Definitions ---
# Structure: { internal_id: {"name": "Display Name", "alias": "cmd_alias", "goal": target_reps} }
EXERCISES_FILE_PATH = os.getenv("EXERCISES_FILE_PATH", "exercises.json")

def load_exercises_from_json(filepath):
    """Load exercises from a specified JSON file."""
    try:
        with open(filepath, 'r') as file:
            exercises = json.load(file)
        return exercises
    except FileNotFoundError:
        print(f"Error: Could not find the file at {filepath}")
    except json.JSONDecodeError:
        print("Error: JSON decoding error. Check the file's syntax.")
    except Exception as e:
        print(f"Unexpected error loading exercises: {e}")

    return {}

EXERCISES = load_exercises_from_json(EXERCISES_FILE_PATH)


# --- Charting ---
CHART_DPI = 100 # Resolution of the chart image
CHART_BAR_COLOR = '#4CAF50' # Greenish
CHART_GOAL_COLOR = '#FF5722' # Orangey-Red
CHART_FONT_SIZE = 10