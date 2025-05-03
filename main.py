# bot.py
import logging
import re
import os # Import os
from datetime import datetime
from dotenv import load_dotenv # Import load_dotenv

from telegram import Update, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden

# --- Load Environment Variables ---
# Load variables from .env file into environment variables
# IMPORTANT: Call this BEFORE importing modules that rely on these variables (like config)
load_dotenv()

# --- Now import local modules ---
# config will now read from the environment variables loaded by load_dotenv
from config import TELEGRAM_BOT_TOKEN, EXERCISES # EXERCISES needed for goal check
import redis_client as rc
from chart_generator import generate_progress_chart, generate_all_progress_chart

# Enable logging (keep as before)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Command Handlers (start, help - Keep previous versions) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your friendly workout tracker bot. 💪"
        "\n\nUse /help to see available commands.",
        reply_markup=None,
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = "Here's how to use me:\n\n"
    help_text += "➡️ Log progress: `/alias reps` (e.g., `/psh 20`, `/plk 60`)\n"
    help_text += "   Available aliases:\n"
    details = rc.get_all_exercise_details()
    if not details:
        help_text += "     _(Could not load exercise details)_\n"
    else:
        # Use EXERCISES from config as the source of truth for display order/completeness
        # This ensures help matches the defined exercises, even if Redis sync is off
        for ex_id, detail_cfg in sorted(EXERCISES.items(), key=lambda item: item[1]['name']):
             alias = detail_cfg.get('alias', ex_id)
             name = detail_cfg.get('name', 'Unknown Exercise')
             goal = detail_cfg.get('goal', 'N/A')
             # Get current goal from redis if available, otherwise use config
             detail_redis = details.get(ex_id)
             if detail_redis and detail_redis.get('goal'):
                 goal = detail_redis['goal'] # Show goal currently stored in DB
             help_text += f"     • `/{alias}` for {name} (Goal: {goal})\n"

    help_text += "\n"
    help_text += "📊 View your progress: /my (sent privately)\n"
    help_text += "👥 View everyone's progress: /all (sent to this chat)\n"
    help_text += "ℹ️ Show this help message: /help"
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# --- record_progress_handler (Updated with Goal Alert) ---

EXERCISE_LOG_PATTERN = re.compile(r"^/(\w+)\s+(\d+)$")

async def record_progress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages matching the /alias reps pattern and checks for goal completion."""
    message_text = update.message.text
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat: return

    match = EXERCISE_LOG_PATTERN.match(message_text)
    if not match: return

    alias = match.group(1).lower()
    try:
        reps = int(match.group(2))
    except ValueError:
        await update.message.reply_text("Invalid number. Please use a whole number.")
        return
    if reps <= 0:
        await update.message.reply_text("Progress value must be positive.")
        return

    logger.info(f"User {user.id} ({user.username or user.first_name}) in chat {chat.id} logging {reps} for alias '{alias}'")
    exercise_id = rc.get_exercise_id_from_alias(alias)
    if not exercise_id:
        await update.message.reply_text(f"Sorry, I don't recognize `/{alias}`. Use /help.", parse_mode=ParseMode.MARKDOWN)
        return

    # Fetch exercise details (including the goal) from Redis
    exercise_details = rc.get_exercise_details(exercise_id)
    if not exercise_details:
         logger.error(f"Internal error finding details for exercise ID: {exercise_id}")
         await update.message.reply_text("An internal error occurred finding exercise details.")
         return

    exercise_name = exercise_details.get('name', exercise_id)
    goal = exercise_details.get('goal') # Could be None or 0 if not set properly

    # Get current score *before* updating to check if goal is crossed
    # Note: This introduces a slight race condition possibility if the user sends
    # two commands very quickly, but it's generally acceptable for this use case.
    # A more robust way would involve Lua scripting in Redis, but is more complex.
    current_progress_map = rc.get_player_progress(user.id)
    old_total = current_progress_map.get(exercise_id, 0)

    try:
        # Record progress (this updates the score in Redis)
        new_total = rc.record_player_progress(
            user_id=user.id,
            user_first_name=user.first_name,
            user_username=user.username,
            exercise_id=exercise_id,
            value=reps
        )
        logger.info(f"User {user.id} logged {reps} for {exercise_id}. Old total: {old_total}, New total: {new_total}. Timestamp updated.")

        # Send confirmation message first
        goal_text = f" (Goal: {goal})" if goal and goal > 0 else ""
        await update.message.reply_text(
            f"✅ Logged {reps} for {exercise_name}. Your total: {new_total}{goal_text}.",
            quote=True
        )

        # --- Goal Check ---
        # Check if a valid goal exists and if the threshold was crossed *by this update*
        if goal and isinstance(goal, int) and goal > 0:
            if old_total < goal <= new_total:
                logger.info(f"User {user.id} reached goal {goal} for {exercise_id} (New total: {new_total})")
                user_display_name, _ = rc.get_user_display_name_and_time(user.id) # Get name for alert
                alert_message = (
                    f"🎉🏆 **Goal Achieved!** 🏆🎉\n\n"
                    f"Congrats {user_display_name}! You've reached the goal of **{goal}** for **{exercise_name}**!\n\n"
                    f"Your new total is **{new_total}**! Keep pushing! 💪"
                )
                # Send alert to the group chat
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=alert_message,
                    parse_mode=ParseMode.MARKDOWN
                    # Consider disabling notification for less interruption: disable_notification=True
                )

    except Exception as e:
        logger.error(f"Error recording progress or sending alert for user {user.id} on {exercise_id}: {e}", exc_info=True)
        # Send error only about saving, not the alert failure specifically
        await update.message.reply_text("😥 Sorry, there was an error saving your progress.")

# --- my_progress, all_progress (Keep previous versions) ---
async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    logger.info(f"User {user.id} ({user.username or user.first_name}) requested /my progress.")

    user_progress = rc.get_player_progress(user.id)
    all_exercise_details = rc.get_all_exercise_details()

    if not user_progress:
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="You haven't logged any exercises yet! Use `/alias reps` in the group chat.",
                parse_mode=ParseMode.MARKDOWN
            )
            if update.message.chat.type != 'private':
                 await update.message.reply_text(f"📊 Sent your (empty) summary privately, {user.first_name}!", quote=True)
            return
        except Forbidden:
            logger.warning(f"Failed send private msg to user {user.id} (Forbidden).")
            await update.message.reply_text(f"{user.first_name}, I couldn't send privately. Please start a chat with me: @{context.bot.username}", quote=True)
        except Exception as e:
             logger.error(f"Failed send private msg to user {user.id}: {e}")
             await update.message.reply_text("Could not send privately. Have you started a chat with me?", quote=True)
        return

    labels = []
    values = []
    goals = []
    user_display_name, _ = rc.get_user_display_name_and_time(user.id)
    for ex_id, details in sorted(all_exercise_details.items(), key=lambda item: item[1]['name']):
        labels.append(details['name'])
        values.append(user_progress.get(ex_id, 0))
        goals.append(details.get('goal'))

    chart_title = f"{user_display_name}'s Workout Progress"
    chart_buffer = generate_progress_chart(chart_title, labels, values, goals)

    if chart_buffer.getbuffer().nbytes == 0:
         logger.warning(f"Empty /my chart buffer for user {user.id}")
         try: await context.bot.send_message(chat_id=user.id, text="Could not generate your chart.")
         except Exception: pass
         return

    try:
        await context.bot.send_photo(
            chat_id=user.id, photo=chart_buffer, caption="Here's your progress! 🔥"
        )
        logger.info(f"Sent /my chart to user {user.id}")
        if update.message.chat.type != 'private':
             await update.message.reply_text(f"📊 Sent your summary privately, {user.first_name}!", quote=True)
    except Forbidden:
        logger.warning(f"Failed send private photo to user {user.id} (Forbidden).")
        await update.message.reply_text(f"{user.first_name}, couldn't send chart privately. Start chat with me: @{context.bot.username}", quote=True)
    except Exception as e:
        logger.error(f"Failed send private photo to user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("Error sending private chart.", quote=True)


async def all_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caller_user = update.effective_user
    chat = update.effective_chat
    if not caller_user or not chat: return

    logger.info(f"User {caller_user.id} requested /all progress in chat {chat.id}.")
    all_player_data = rc.get_all_players_progress()
    all_exercise_details = rc.get_all_exercise_details()

    if not all_player_data:
        await update.message.reply_text("No progress logged yet!")
        return

    player_ids = list(all_player_data.keys())
    player_labels = []

    for user_id in player_ids:
        display_name, last_update_ts = rc.get_user_display_name_and_time(user_id)
        if last_update_ts:
            try:
                dt_object = datetime.fromtimestamp(last_update_ts)
                time_str = dt_object.strftime('%Y-%m-%d %H:%M') # Or '%b %d %H:%M'
                formatted_label = f"{display_name} (Upd: {time_str})"
            except Exception as e:
                 logger.warning(f"Timestamp format error for user {user_id}: {e}")
                 formatted_label = display_name
        else:
            formatted_label = display_name
        player_labels.append(formatted_label)

    sorted_exercise_details = dict(sorted(all_exercise_details.items(), key=lambda item: item[1]['name']))
    chat_title = chat.title or "Group"
    chart_title = f"{chat_title} Workout Progress"

    chart_buffer = generate_all_progress_chart(
        title=chart_title,
        player_labels=player_labels,
        player_ids=player_ids,
        exercise_data=all_player_data,
        exercise_details=sorted_exercise_details
    )

    if chart_buffer.getbuffer().nbytes == 0:
         await update.message.reply_text("Could not generate the group progress chart.")
         logger.warning(f"Empty /all chart buffer for request by {caller_user.id} in chat {chat.id}")
         return

    try:
        await context.bot.send_photo(
            chat_id=chat.id,
            photo=chart_buffer,
            caption=f"📊 Group progress overview requested by {caller_user.first_name}!"
        )
        logger.info(f"Sent /all progress chart with timestamps to chat {chat.id}")
    except Exception as e:
        logger.error(f"Failed send public /all photo to chat {chat.id}: {e}", exc_info=True)
        await update.message.reply_text("😥 Sorry, I couldn't send the progress chart image here.")


# --- Main Bot Execution (Updated Token Check) ---

def main() -> None:
    """Start the bot."""
    # TELEGRAM_BOT_TOKEN is now loaded from .env into os.environ by load_dotenv()
    # Check if the token was actually loaded
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN not found in environment variables or .env file!")
        print("\nError: TELEGRAM_BOT_TOKEN is missing.")
        print("Please ensure it is set in your .env file or environment variables.\n")
        return

    # Check Redis connection (uses config values read from environment)
    if not rc.redis_conn:
        logger.error("FATAL: Could not connect to Redis. Aborting bot startup.")
        print("\nError: Failed to connect to Redis.")
        print(f"Check Redis server status and connection details (Host: {rc.REDIS_HOST}, Port: {rc.REDIS_PORT}, DB: {rc.REDIS_DB}).\n")
        return

    application = Application.builder().token(token).build() # Use the loaded token

    # Register Handlers (keep as before)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("my", my_progress))
    application.add_handler(CommandHandler("all", all_progress))
    application.add_handler(MessageHandler(filters.COMMAND & filters.Regex(EXERCISE_LOG_PATTERN) & (~filters.UpdateType.EDITED_MESSAGE), record_progress_handler))

    logger.info("Starting bot polling...")
    print("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    print("Bot stopped.")


if __name__ == "__main__":
    main()