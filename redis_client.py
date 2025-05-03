# redis_client.py
import redis
import json
import time # Import the time module
from datetime import datetime # Import datetime for formatting

from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, EXERCISES

# --- Redis Key Prefixes (Keep as before) ---
PLAYER_PREFIX = "player:"
EXERCISE_ALIAS_KEY = "exercise:aliases"
EXERCISE_DETAILS_PREFIX = "exercise:details:"
PLAYERS_SET_KEY = "players:ids"
USER_INFO_PREFIX = "user:info:"

# --- Initialize Redis Connection (Keep as before) ---
try:
    redis_conn = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    redis_conn.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    redis_conn = None
    exit()

# --- setup_initial_data, get_exercise_id_from_alias, get_exercise_details, get_all_exercise_details (Keep as before) ---
# ... (paste previous versions here) ...
def setup_initial_data():
    """Sets up exercise aliases and details in Redis if not present."""
    if not redis_conn: return
    print("Setting up initial exercise data in Redis...")
    aliases = {}
    example_ex_id = next(iter(EXERCISES)) # Get the first key from EXERCISES dict
    needs_setup = not redis_conn.exists(f"{EXERCISE_DETAILS_PREFIX}{example_ex_id}")

    if needs_setup:
         pipe = redis_conn.pipeline()
         pipe.delete(EXERCISE_ALIAS_KEY)
         for ex_id, details in EXERCISES.items():
             aliases[details['alias']] = ex_id
             details_key = f"{EXERCISE_DETAILS_PREFIX}{ex_id}"
             pipe.hset(details_key, mapping={
                 "name": details['name'],
                 "goal": str(details['goal'])
             })
         if aliases:
             pipe.hset(EXERCISE_ALIAS_KEY, mapping=aliases)
         pipe.execute()
         print("Initial exercise data stored/updated in Redis.")
    else:
        print("Exercise data likely already exists in Redis.")


def get_exercise_id_from_alias(alias: str) -> str | None:
    """Finds the internal exercise ID based on its alias."""
    if not redis_conn: return None
    return redis_conn.hget(EXERCISE_ALIAS_KEY, alias.lower())

def get_exercise_details(exercise_id: str) -> dict | None:
    """Gets the name and goal for an exercise."""
    if not redis_conn: return None
    details = redis_conn.hgetall(f"{EXERCISE_DETAILS_PREFIX}{exercise_id}")
    if details and 'goal' in details:
        try:
            details['goal'] = int(details['goal'])
        except (ValueError, TypeError):
            print(f"Warning: Invalid non-integer goal '{details['goal']}' found for exercise {exercise_id}")
            details['goal'] = 0
    return details if details else None

def get_all_exercise_details() -> dict:
    """Gets details for all defined exercises."""
    if not redis_conn: return {}
    all_details = {}
    aliases = redis_conn.hgetall(EXERCISE_ALIAS_KEY)
    if not aliases:
        print("Warning: No exercise aliases found in Redis. Was setup run?")
        return {}
    for alias, ex_id in aliases.items():
         details = get_exercise_details(ex_id)
         if details:
             all_details[ex_id] = details
             all_details[ex_id]['alias'] = alias
    return all_details
# --- Updated Functions ---

def store_user_info(user_id: int, first_name: str, username: str | None, update_time: int | None = None):
    """Stores or updates user's first name, username, and optionally last update time."""
    if not redis_conn: return
    user_info_key = f"{USER_INFO_PREFIX}{user_id}"
    info_to_store = {"first_name": first_name}
    if username:
        info_to_store["username"] = username
    else:
         # Explicitly remove username field if it's None now but might have existed before
         redis_conn.hdel(user_info_key, "username")

    if update_time is not None:
         info_to_store["last_update"] = str(update_time) # Store timestamp as string

    # Use hset which updates fields or creates the hash
    if info_to_store: # Only call hset if there's something to store/update
        redis_conn.hset(user_info_key, mapping=info_to_store)

# Modified to return timestamp as well
def get_user_display_name_and_time(user_id: int) -> tuple[str, int | None]:
    """
    Gets the best display name and the last update timestamp for a user.
    Returns: (display_name, last_update_timestamp | None)
    """
    if not redis_conn: return f"User {user_id}", None

    user_info_key = f"{USER_INFO_PREFIX}{user_id}"
    user_info = redis_conn.hgetall(user_info_key)

    display_name = f"User {user_id}" # Default fallback
    if user_info.get("username"):
        display_name = f"@{user_info['username']}"
    elif user_info.get("first_name"):
        display_name = user_info['first_name']

    last_update_timestamp = None
    if user_info.get("last_update"):
        try:
            last_update_timestamp = int(user_info["last_update"])
        except (ValueError, TypeError):
            print(f"Warning: Could not parse last_update '{user_info['last_update']}' for user {user_id}")
            last_update_timestamp = None # Treat invalid data as None

    return display_name, last_update_timestamp


# Modified to store timestamp
def record_player_progress(user_id: int, user_first_name: str, user_username: str | None, exercise_id: str, value: int) -> int:
    """Adds value to a player's score and updates user info including last update time. Returns new total."""
    if not redis_conn: return 0
    player_key = f"{PLAYER_PREFIX}{user_id}"
    current_timestamp = int(time.time()) # Get current Unix timestamp

    # Use a pipeline for atomicity (or near-atomicity) of updates
    pipe = redis_conn.pipeline()

    # 1. Update User Info (including timestamp)
    user_info_key = f"{USER_INFO_PREFIX}{user_id}"
    info_to_store = {"first_name": user_first_name, "last_update": str(current_timestamp)}
    if user_username:
        info_to_store["username"] = user_username
    # Queue HSET for user info
    pipe.hset(user_info_key, mapping=info_to_store)
    # If username is None, ensure it's removed if it exists
    if not user_username:
         pipe.hdel(user_info_key, "username")

    # 2. Add player to the set of active players
    pipe.sadd(PLAYERS_SET_KEY, str(user_id))

    # 3. Atomically increment the score for the exercise
    # HINCRBY needs to be executed separately to get the return value easily,
    # or handle its result index from the pipeline execution if needed elsewhere.
    # For simplicity here, we execute HINCRBY after the pipeline that updates info.
    # This is usually acceptable unless strict atomicity between info and score is critical.
    pipe.execute() # Execute info update and set add

    # Now increment the score
    new_total = redis_conn.hincrby(player_key, exercise_id, value)

    return new_total

# --- get_player_progress, get_all_players_progress (Keep as before) ---
def get_player_progress(user_id: int) -> dict:
    """Gets all progress for a specific player."""
    if not redis_conn: return {}
    player_key = f"{PLAYER_PREFIX}{user_id}"
    progress = redis_conn.hgetall(player_key)
    return {ex_id: int(score) for ex_id, score in progress.items()}

def get_all_players_progress() -> dict:
    """Gets progress for all players who have recorded data."""
    if not redis_conn: return {}
    all_progress = {}
    player_ids = redis_conn.smembers(PLAYERS_SET_KEY)
    if not player_ids:
        return {}

    pipe = redis_conn.pipeline(transaction=False)
    keys_to_fetch = [f"{PLAYER_PREFIX}{user_id}" for user_id in player_ids]
    for key in keys_to_fetch:
        pipe.hgetall(key)

    results = pipe.execute()

    for i, user_id_str in enumerate(player_ids):
        user_id = int(user_id_str)
        raw_progress = results[i]
        if isinstance(raw_progress, dict):
             all_progress[user_id] = {ex_id: int(score) for ex_id, score in raw_progress.items()}
        else:
            print(f"Warning: No progress data found or unexpected result for user {user_id}")
            all_progress[user_id] = {}

    return all_progress


# Run setup when this module is imported
setup_initial_data()