# main.py (or bot.py)
import logging
import re
import os
from datetime import datetime
from dotenv import load_dotenv

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
load_dotenv()

# --- Now import local modules ---
from config import TELEGRAM_BOT_TOKEN, EXERCISES
import redis_client as rc
from chart_generator import generate_progress_chart, generate_all_progress_chart

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your workout tracker. Use /help for commands.",
        reply_markup=None,
    )

# --- Updated help_command ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message listing commands."""
    help_text = "Here's how to use me:\n\n"
    help_text += "➡️ **Log progress:** `/alias reps`\n"
    help_text += "   _(e.g., `/psh 20`, `/plk 60`)_\n"
    help_text += "🗑️ **RESET progress:** `/alias reset`\n" # Added Reset info
    help_text += "   _(e.g., `/psh reset` to set Push-Ups to 0)_\n\n"
    help_text += "   **Available aliases:**\n"

    details = rc.get_all_exercise_details()
    if not details:
        help_text += "     _(Could not load exercise details)_\n"
    else:
        for ex_id, detail_cfg in sorted(EXERCISES.items(), key=lambda item: item[1]['name']):
             alias = detail_cfg.get('alias', ex_id)
             name = detail_cfg.get('name', 'Unknown Exercise')
             goal = detail_cfg.get('goal', 'N/A')
             detail_redis = details.get(ex_id)
             if detail_redis and detail_redis.get('goal'):
                 goal = detail_redis['goal']
             help_text += f"     • `/{alias}` for {name} (Goal: {goal})\n"

    help_text += "\n"
    help_text += "📊 **View your progress:** /my (sent privately)\n"
    help_text += "👥 **View group progress:** /all (sent to this chat)\n"
    help_text += "ℹ️ **Show this help:** /help"

    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# --- Regex Patterns ---
EXERCISE_LOG_PATTERN = re.compile(r"^/(\w+)\s+(\d+)$")
# --- NEW Regex for Reset ---
EXERCISE_RESET_PATTERN = re.compile(r"^/(\w+)\s+reset$", re.IGNORECASE) # Match 'reset', case-insensitive

# --- record_progress_handler (keep as before) ---
async def record_progress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages matching the /alias reps pattern and checks for goal completion."""
    message_text = update.message.text
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat: return

    match = EXERCISE_LOG_PATTERN.match(message_text)
    if not match: return # Should only match log pattern now

    alias = match.group(1).lower()
    try: reps = int(match.group(2))
    except ValueError:
        await update.message.reply_text("Invalid number. Please use a whole number.")
        return
    if reps <= 0:
        await update.message.reply_text("Progress value must be positive.")
        return

    logger.info(f"User {user.id} attempting to log {reps} for alias '{alias}'")
    exercise_id = rc.get_exercise_id_from_alias(alias)
    if not exercise_id:
        # No need for reply here, maybe handled by unrecognized command handler later if added
        logger.debug(f"Unknown alias '{alias}' used for logging by user {user.id}")
        return

    exercise_details = rc.get_exercise_details(exercise_id)
    if not exercise_details:
         logger.error(f"Internal error finding details for exercise ID: {exercise_id}")
         await update.message.reply_text("An internal error occurred finding exercise details.")
         return

    exercise_name = exercise_details.get('name', exercise_id)
    goal = exercise_details.get('goal')

    current_progress_map = rc.get_player_progress(user.id)
    old_total = current_progress_map.get(exercise_id, 0)

    try:
        new_total = rc.record_player_progress(
            user_id=user.id, user_first_name=user.first_name, user_username=user.username,
            exercise_id=exercise_id, value=reps
        )
        logger.info(f"User {user.id} logged {reps} for {exercise_id}. Old: {old_total}, New: {new_total}.")

        goal_text = f" (Goal: {goal})" if goal and goal > 0 else ""
        await update.message.reply_text(
            f"✅ Logged {reps} for {exercise_name}. Your total: {new_total}{goal_text}.", quote=True
        )

        if goal and isinstance(goal, int) and goal > 0:
            if old_total < goal <= new_total:
                logger.info(f"User {user.id} reached goal {goal} for {exercise_id}")
                user_display_name, _ = rc.get_user_display_name_and_time(user.id)
                alert_message = (
                    f"🎉🏆 **Goal Achieved!** 🏆🎉\n\n"
                    f"Congrats {user_display_name}! You've reached the goal of **{goal}** for **{exercise_name}**!\n\n"
                    f"Your new total is **{new_total}**! Keep pushing! 💪"
                )
                await context.bot.send_message(chat_id=chat.id, text=alert_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error recording progress for user {user.id} on {exercise_id}: {e}", exc_info=True)
        await update.message.reply_text("😥 Sorry, there was an error saving your progress.")

# --- NEW reset_progress_handler ---
async def reset_progress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages matching the /alias reset pattern."""
    message_text = update.message.text
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat: return

    match = EXERCISE_RESET_PATTERN.match(message_text)
    if not match: return # Should only match reset pattern

    alias = match.group(1).lower()
    logger.info(f"User {user.id} attempting to reset progress for alias '{alias}' in chat {chat.id}")

    exercise_id = rc.get_exercise_id_from_alias(alias)
    if not exercise_id:
        await update.message.reply_text(f"Sorry, I don't recognize `/{alias}`. Use /help.", parse_mode=ParseMode.MARKDOWN, quote=True)
        return

    exercise_details = rc.get_exercise_details(exercise_id)
    if not exercise_details:
         logger.error(f"Internal error finding details for exercise ID: {exercise_id} during reset")
         await update.message.reply_text("An internal error occurred finding exercise details.", quote=True)
         return
    exercise_name = exercise_details.get('name', exercise_id)

    try:
        success = rc.reset_player_exercise(
            user_id=user.id,
            user_first_name=user.first_name, # Pass info to update timestamp
            user_username=user.username,
            exercise_id=exercise_id
        )
        if success:
            logger.info(f"Successfully reset score for user {user.id} on {exercise_id}")
            await update.message.reply_text(
                f"🗑️ Reset your progress for **{exercise_name}** back to 0.",
                parse_mode=ParseMode.MARKDOWN, quote=True
            )
        else:
             # This else might be redundant if reset_player_exercise raises exceptions handled below
             logger.warning(f"reset_player_exercise returned False for user {user.id}, exercise {exercise_id}")
             await update.message.reply_text("😥 Sorry, couldn't reset the progress due to an unexpected issue.", quote=True)

    except Exception as e:
        logger.error(f"Error resetting progress for user {user.id} on {exercise_id}: {e}", exc_info=True)
        await update.message.reply_text("😥 Sorry, there was an error resetting your progress.", quote=True)


# --- my_progress, all_progress (Keep as before) ---
async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    logger.info(f"User {user.id} ({user.username or user.first_name}) requested /my progress.")

    user_progress = rc.get_player_progress(user.id)
    all_exercise_details = rc.get_all_exercise_details()

    if not user_progress:
        try:
            await context.bot.send_message(chat_id=user.id, text="You haven't logged any exercises yet! Use `/alias reps` in the group chat.", parse_mode=ParseMode.MARKDOWN)
            if update.message.chat.type != 'private': await update.message.reply_text(f"📊 Sent your (empty) summary privately, {user.first_name}!", quote=True)
        except Forbidden: await update.message.reply_text(f"{user.first_name}, I couldn't send privately. Please start a chat with me: @{context.bot.username}", quote=True)
        except Exception as e: logger.error(f"Failed send private msg to user {user.id}: {e}"); await update.message.reply_text("Could not send privately.", quote=True)
        return

    labels, values, goals = [], [], []
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
        await context.bot.send_photo(chat_id=user.id, photo=chart_buffer, caption="Here's your progress! 🔥")
        logger.info(f"Sent /my chart to user {user.id}")
        if update.message.chat.type != 'private': await update.message.reply_text(f"📊 Sent your summary privately, {user.first_name}!", quote=True)
    except Forbidden: await update.message.reply_text(f"{user.first_name}, couldn't send chart privately. Start chat with me: @{context.bot.username}", quote=True)
    except Exception as e: logger.error(f"Failed send private photo to user {user.id}: {e}", exc_info=True); await update.message.reply_text("Error sending private chart.", quote=True)

async def all_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caller_user = update.effective_user
    chat = update.effective_chat
    if not caller_user or not chat: return

    logger.info(f"User {caller_user.id} requested /all progress in chat {chat.id}.")
    all_player_data = rc.get_all_players_progress()
    all_exercise_details = rc.get_all_exercise_details()

    if not all_player_data: await update.message.reply_text("No progress logged yet!"); return

    player_ids = list(all_player_data.keys())
    player_labels = []
    for user_id in player_ids:
        display_name, last_update_ts = rc.get_user_display_name_and_time(user_id)
        if last_update_ts:
            try: time_str = datetime.fromtimestamp(last_update_ts).strftime('%Y-%m-%d %H:%M'); formatted_label = f"{display_name} (Upd: {time_str})"
            except Exception as e: logger.warning(f"Timestamp format error for user {user_id}: {e}"); formatted_label = display_name
        else: formatted_label = display_name
        player_labels.append(formatted_label)

    sorted_exercise_details = dict(sorted(all_exercise_details.items(), key=lambda item: item[1]['name']))
    chat_title = chat.title or "Group"; chart_title = f"{chat_title} Workout Progress"
    chart_buffer = generate_all_progress_chart(title=chart_title, player_labels=player_labels, player_ids=player_ids, exercise_data=all_player_data, exercise_details=sorted_exercise_details)

    if chart_buffer.getbuffer().nbytes == 0: await update.message.reply_text("Could not generate the group progress chart."); logger.warning(f"Empty /all chart buffer requested by {caller_user.id}"); return

    try:
        await context.bot.send_photo(chat_id=chat.id, photo=chart_buffer, caption=f"📊 Group progress overview requested by {caller_user.first_name}!")
        logger.info(f"Sent /all progress chart to chat {chat.id}")
    except Exception as e: logger.error(f"Failed send public /all photo to chat {chat.id}: {e}", exc_info=True); await update.message.reply_text("😥 Sorry, I couldn't send the chart image.")


async def message_store_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles regular text messages to backup them using user_id as key."""
    user = update.effective_user
    message = update.effective_message
    chat = update.effective_chat

    # Basic checks: Must have user, message, text, and not be a command
    if not user or not message or not message.text or message.text.startswith('/'):
        return

    # Only store messages from groups or supergroups
    if message.chat.type not in ['group', 'supergroup']:
        return

    # Use user.id for the key, text for the value, and message.date for the score
    user_id = user.id
    message_text = message.text
    # Use message.date (timezone-aware UTC datetime from Telegram)
    message_time = message.date
    # message.date is a datetime object, convert to UNIX timestamp (float)
    message_timestamp = message.date.timestamp()
    chat_id = chat.id if chat else None
    telegram_message_id = message.message_id

    # logger.debug(f"Attempting to store message from user {user_id} in chat {message.chat.id}")

    # Update user info first (includes timestamp)
    rc.store_user_info(user_id=user.id, first_name=user.first_name, username=user.username)

    success_sset = rc.store_user_message_sortedset(
        user_id=user_id,
        message_text=message_text,
        message_time=message_time
    )

    success_stream = rc.store_user_message_stream(
        user_id=user_id,
        message_text=message_text,
        message_timestamp=message_timestamp,
        chat_id=chat_id,
        telegram_message_id=telegram_message_id
    )

    if not success_sset:
        logger.warning(f"Failed to store message to the sorted set for user {user_id} from chat {message.chat.id}")

    if not success_stream:
        logger.warning(f"Failed to store message to the stream for user {user_id} from chat {message.chat.id}")


async def hard_reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    is_admin = await is_user_admin(update, context)
    if not is_admin:
        await update.message.reply_text("⛔ You are not authorized to use this command.", quote=True)
        return

    logger.info(f"User {user.id} initiated a hard reset.")
    rc.setup_initial_data(hard_reset=True)
    await update.message.reply_text("✅ Hard reset performed successfully.", quote=True)



# --- Main Bot Execution ---
def main() -> None:
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN missing!")
        print("\nError: TELEGRAM_BOT_TOKEN is missing.\n")
        return

    if not rc.redis_conn:
        # Error already printed in redis_client.py during connection attempt
        logger.error("FATAL: Could not connect to Redis. Aborting.")
        print("\nError: Failed to connect to Redis. Check logs and connection details.\n")
        return

    application = Application.builder().token(token).build()

    # --- Register Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("my", my_progress))
    application.add_handler(CommandHandler("all", all_progress))
    application.add_handler(CommandHandler("hardreset", hard_reset_handler))

    # Handler for LOGGING progress (/alias <number>)
    application.add_handler(MessageHandler(
        filters.COMMAND & filters.Regex(EXERCISE_LOG_PATTERN) & (~filters.UpdateType.EDITED_MESSAGE),
        record_progress_handler
    ))
    # --- NEW Handler for RESETTING progress (/alias reset) ---
    application.add_handler(MessageHandler(
        filters.COMMAND & filters.Regex(EXERCISE_RESET_PATTERN) & (~filters.UpdateType.EDITED_MESSAGE),
        reset_progress_handler
    ))

    application.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND) & (filters.ChatType.GROUPS),
        message_store_handler
    ))


    logger.info("Starting bot polling...")
    print("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    print("Bot stopped.")

async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user initiating a command is an admin."""
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False
    
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status for user {user.id}: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    main()