# Telegram Group Workout Tracker Bot 💪

A Python-based Telegram bot designed to track workout exercise progress for participants within a group chat. It uses Redis for persistent data storage, Matplotlib for generating progress charts, and Docker/Docker Compose for easy deployment.

## Features

*   **Exercise Tracking:** Log progress for various predefined workout exercises (Plank, Push-ups, Abs, etc.).
*   **Simple Logging:** Users log reps/time using simple chat commands (e.g., `/psh 20`, `/plk 60`).
*   **Personal Summary:** Get a private summary of your own progress with the `/my` command, including a chart showing progress towards goals.
*   **Group Summary:** View a collective summary chart of all participants' progress using the `/all` command, posted publicly in the chat. This chart includes usernames (or IDs) and the time of their last update.
*   **Visual Charts:** Uses Matplotlib to generate informative and visually enhanced bar charts.
*   **Goal Alerts:** Automatically notifies the group chat when a user's logged progress reaches the predefined goal for an exercise.
*   **Redis Persistence:** Stores user progress, exercise definitions, and user info reliably in Redis.
*   **Dockerized:** Includes a `Dockerfile` and `docker-compose.yml` for straightforward setup and deployment with Redis included.
*   **Configurable:** Easily configure exercises, goals, and bot settings via `config.py` and environment variables (`.env`).

## Technology Stack

*   **Language:** Python 3.12+
*   **Telegram Library:** `python-telegram-bot`
*   **Database:** Redis (via `redis-py`)
*   **Charting:** `matplotlib`
*   **Configuration:** `python-dotenv`
*   **Containerization:** Docker & Docker Compose

## Prerequisites

*   Docker ([Install Guide](https://docs.docker.com/engine/install/))
*   Docker Compose (v1.27+ or V2 - usually included with Docker Desktop)
*   Git (for cloning the repository)
*   A Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather) on Telegram.

## Setup and Installation

1.  **Clone the Repository:**


2.  **Configure Environment Variables:**
    Create a `.env` file in the project root directory by copying `.env-sample` or creating it manually. Add the following variables:

    ```dotenv
    # .env
    TELEGRAM_BOT_TOKEN="YOUR_ACTUAL_TELEGRAM_BOT_TOKEN"

    # Redis Configuration for Docker Compose
    REDIS_HOST="redis" # Use the service name from docker-compose.yml
    REDIS_PORT="6379"
    REDIS_DB="0"
    # REDIS_PASSWORD="your_strong_redis_password" # Uncomment and set if you configured a password in docker-compose.yml
    ```
    *   **Replace `"YOUR_ACTUAL_TELEGRAM_BOT_TOKEN"`** with the token you got from BotFather.
    *   Ensure `REDIS_HOST` is set to `redis` when using the provided `compose.yml`.

## Running the Bot (using Docker Compose)

This is the recommended method as it manages both the bot and the Redis database container.

1.  **Build the Docker Image:**
    *(This step builds the image based on the `Dockerfile`)*
    ```bash
    docker compose build
    ```

2.  **Start the Services:**
    *(This starts the bot and Redis containers in the background)*
    ```bash
    docker compose up -d
    ```

3.  **Check Logs (Optional):**
    *(View the bot's output/logs)*
    ```bash
    docker compose logs -f bot
    ```
    *(View Redis logs)*
    ```bash
    docker compose logs -f redis
    ```

4.  **Stop the Services:**
    ```bash
    docker compose down
    ```
    *(To stop and remove containers, networks. Use `docker compose down -v` to also remove the Redis data volume)*

## Bot Usage

Add the bot to your Telegram group chat. Participants can interact with the following commands:

*   `/start`: Displays a welcome message.
*   `/help`: Shows available commands and the list of trackable exercises with their aliases and goals.
*   `/alias reps`: Logs progress for an exercise. Replace `alias` with the exercise alias (e.g., `psh`, `plk`, `abs`) and `reps` with the number of repetitions, seconds, or minutes completed.
    *   Example: `/psh 25` (Logs 25 Push-Ups)
    *   Example: `/plk 90` (Logs 90 seconds of Plank)
*   `/my`: Receive a private message from the bot containing a chart summarizing your personal progress across all exercises against their goals.
*   `/all`: The bot posts a chart publicly in the group chat summarizing the progress of all participants for all exercises. The legend includes participant names/usernames and the timestamp of their last logged update.

**Goal Alerts:** When a `/alias reps` command causes a user's total for that exercise to meet or exceed its goal, the bot will automatically post a congratulatory message in the group chat.

## Docker Hub Image (Optional)

If a pre-built image is available on Docker Hub (e.g., at `giufus/workout-bot:latest`), you can potentially pull and run it.

1.  **Pull the image:**
    ```bash
    docker pull giufus/workout-bot:latest
    ```
2.  **Run (Example - Requires separate Redis):** You would typically still use Docker Compose to manage Redis and networking easily. Running standalone requires manually setting up Redis and linking:
    ```bash
    # Ensure a Redis container named 'my-redis' is running
    docker run -d --name my-redis redis:8.0-rc1

    # Run the bot, linking to Redis and passing environment variables
    docker run -d --name workout-bot --link my-redis:redis \
      -e TELEGRAM_BOT_TOKEN="YOUR_TOKEN" \
      -e REDIS_HOST="redis" \
      -e REDIS_PORT="6379" \
      -e REDIS_DB="0" \
      giufus/workout-bot:latest
    ```
    *(Using the provided `compose.yml` after pulling the image is generally simpler if you modify it to use `image:` instead of `build: .` for the `bot` service)*

## Customization

*   **Exercises & Goals:** Modify the `EXERCISES` dictionary within the `config.py` file to add, remove, or change exercises, their aliases, and goal values. Rebuild the Docker image (`docker compose build`) after changes.
*   **Chart Appearance:** Adjust colors, fonts, and styles in the `CHART_` variables in `config.py` and the plotting logic within `chart_generator.py`. Rebuild the Docker image after changes.

## Contributing

Contributions, issues, and feature requests are welcome. Please open an issue to discuss any significant changes beforehand.

## License

[MIT](LICENSE) 