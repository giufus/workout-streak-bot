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
MESSAGES_USER_PREFIX = "messages:user:"


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
# Add specific exception for authentication failure
except redis.exceptions.AuthenticationError:
    print(f"Error connecting to Redis: Authentication failed. Check REDIS_PASSWORD environment variable.")
    redis_conn = None
    # exit() # Exit might not be desired if running in a managed environment like OpenShift
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis ({REDIS_HOST}:{REDIS_PORT}): {e}")
    redis_conn = None
    # exit()
except Exception as e: # Catch other potential errors
     print(f"An unexpected error occurred during Redis connection: {e}")
     redis_conn = None
     # exit()


# --- setup_initial_data, get_exercise_id_from_alias, get_exercise_details, get_all_exercise_details (Keep as before) ---
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
    if not redis_conn: return None
    return redis_conn.hget(EXERCISE_ALIAS_KEY, alias.lower())

def get_exercise_details(exercise_id: str) -> dict | None:
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

# --- store_user_info, get_user_display_name_and_time (Keep as before) ---
def store_user_info(user_id: int, first_name: str, username: str | None, update_time: int | None = None):
    """Stores or updates user's first name, username, and optionally last update time."""
    if not redis_conn: return
    user_info_key = f"{USER_INFO_PREFIX}{user_id}"
    info_to_store = {"first_name": first_name}
    if username:
        info_to_store["username"] = username
    else:
         redis_conn.hdel(user_info_key, "username") # Remove if None

    if update_time is not None:
         info_to_store["last_update"] = str(update_time)

    if info_to_store:
        redis_conn.hset(user_info_key, mapping=info_to_store)

def get_user_display_name_and_time(user_id: int) -> tuple[str, int | None]:
    """Gets display name and last update timestamp."""
    if not redis_conn: return f"User {user_id}", None
    user_info_key = f"{USER_INFO_PREFIX}{user_id}"
    user_info = redis_conn.hgetall(user_info_key)
    display_name = f"User {user_id}"
    if user_info.get("username"): display_name = f"@{user_info['username']}"
    elif user_info.get("first_name"): display_name = user_info['first_name']
    last_update_timestamp = None
    if user_info.get("last_update"):
        try: last_update_timestamp = int(user_info["last_update"])
        except (ValueError, TypeError): last_update_timestamp = None
    return display_name, last_update_timestamp

# --- record_player_progress (Keep as before) ---
def record_player_progress(user_id: int, user_first_name: str, user_username: str | None, exercise_id: str, value: int) -> int:
    """Adds value to a player's score and updates user info including last update time. Returns new total."""
    if not redis_conn: return 0
    player_key = f"{PLAYER_PREFIX}{user_id}"
    current_timestamp = int(time.time())
    # Update user info first (includes timestamp)
    store_user_info(user_id, user_first_name, user_username, current_timestamp)
    # Add player to set
    redis_conn.sadd(PLAYERS_SET_KEY, str(user_id))
    # Increment score
    new_total = redis_conn.hincrby(player_key, exercise_id, value)
    return new_total

# --- NEW FUNCTION ---
def reset_player_exercise(user_id: int, user_first_name: str, user_username: str | None, exercise_id: str) -> bool:
    """Resets a player's score for a specific exercise to 0 and updates timestamp."""
    if not redis_conn: return False
    player_key = f"{PLAYER_PREFIX}{user_id}"
    current_timestamp = int(time.time())
    try:
        # Update user info timestamp first
        store_user_info(user_id, user_first_name, user_username, current_timestamp)
        # Set the specific exercise score to 0 in the player's hash
        # HSET returns 1 if field created, 0 if updated. We just care it succeeded.
        redis_conn.hset(player_key, exercise_id, 0)
        # Add player to set if they somehow weren't there but resetting
        redis_conn.sadd(PLAYERS_SET_KEY, str(user_id))
        print(f"Reset score for user {user_id} on exercise {exercise_id} to 0.")
        return True
    except redis.RedisError as e:
        print(f"Redis error resetting score for user {user_id} on {exercise_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error resetting score for user {user.id} on {exercise_id}: {e}")
        return False


# --- get_player_progress, get_all_players_progress (Keep as before) ---
def get_player_progress(user_id: int) -> dict:
    if not redis_conn: return {}
    player_key = f"{PLAYER_PREFIX}{user_id}"
    progress = redis_conn.hgetall(player_key)
    return {ex_id: int(score) for ex_id, score in progress.items()}

def get_all_players_progress() -> dict:
    if not redis_conn: return {}
    all_progress = {}
    player_ids = redis_conn.smembers(PLAYERS_SET_KEY)
    if not player_ids: return {}
    pipe = redis_conn.pipeline(transaction=False)
    keys_to_fetch = [f"{PLAYER_PREFIX}{user_id}" for user_id in player_ids]
    for key in keys_to_fetch: pipe.hgetall(key)
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


def get_messages_key_for_user(user_id: int) -> str:
    """Constructs the Redis Sorted Set key for a user's messages."""
    return f"{MESSAGES_USER_PREFIX}{user_id}"


def store_user_message(user_id: int, message_text: str, message_time: datetime) -> bool:
    """Stores a user's message in their sorted set using timestamp as score."""
    if not redis_conn:
        print("Redis connection not available for store_user_message.")
        return False

    messages_key = get_messages_key_for_user(user_id)
    timestamp_score = message_time.timestamp() # Use Unix float timestamp for score

    try:
        # ZADD key score member [score member ...]
        # If message_text (member) already exists, its score (timestamp) is updated.
        # This naturally handles storing the same message text multiple times if sent at different times.
        redis_conn.zadd(messages_key, {message_text: timestamp_score})
        # logger.debug(f"Stored message for user {user_id} in key {messages_key}") # Maybe too verbose
        return True
    except Exception as e:
        print(f"Error ZADD message to Redis key {messages_key} for user {user_id}: {e}", exc_info=True)
        return False


# Run setup when this module is imported
setup_initial_data()