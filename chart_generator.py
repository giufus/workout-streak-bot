# chart_generator.py
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend
import matplotlib.pyplot as plt
import io
import numpy as np

from config import CHART_DPI, CHART_BAR_COLOR, CHART_GOAL_COLOR, CHART_FONT_SIZE

plt.style.use('seaborn-v0_8-darkgrid')

# generate_progress_chart remains the same as before...
def generate_progress_chart(title: str, labels: list, values: list, goals: list = None) -> io.BytesIO:
    """Generates a bar chart image and returns it as BytesIO."""
    if not labels or not values:
        return io.BytesIO()

    fig, ax = plt.subplots(figsize=(8, max(4, len(labels) * 0.6)), dpi=CHART_DPI)

    bar_height = 0.6
    y_pos = np.arange(len(labels))

    bars = ax.barh(y_pos, values, height=bar_height, color=CHART_BAR_COLOR, label='Current Progress')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=CHART_FONT_SIZE)
    ax.invert_yaxis()
    ax.set_xlabel('Repetitions / Count / Seconds', fontsize=CHART_FONT_SIZE) # Generalized label
    ax.set_title(title, fontsize=CHART_FONT_SIZE + 2, pad=20)

    ax.bar_label(bars, padding=3, fmt='%d', fontsize=CHART_FONT_SIZE - 1)

    max_val = max(values) if values else 0
    if goals and len(goals) == len(labels):
        # Filter out None goals before calculating max_goal
        valid_goals = [g for g in goals if g is not None and g > 0]
        max_goal = max(valid_goals) if valid_goals else 0
        plot_limit = max(max_val, max_goal) * 1.15
        ax.set_xlim(right=max(10, plot_limit))

        for i, goal in enumerate(goals):
            if goal is not None and goal > 0:
                ax.axvline(x=goal, color=CHART_GOAL_COLOR, linestyle='--', linewidth=1)
                ax.text(goal, y_pos[i] + bar_height / 1.8, f' Goal: {goal}',
                        color=CHART_GOAL_COLOR, va='center', ha='left',
                        fontsize=CHART_FONT_SIZE - 1,
                        bbox=dict(facecolor='white', alpha=0.5, pad=1, boxstyle='round,pad=0.2'))
    else:
         plot_limit = max_val * 1.15
         ax.set_xlim(right=max(10, plot_limit))

    if goals and any(g is not None for g in goals):
        from matplotlib.lines import Line2D
        goal_line = Line2D([0], [0], color=CHART_GOAL_COLOR, linestyle='--', linewidth=1, label='Goal')
        handles, existing_labels = ax.get_legend_handles_labels()
        # Ensure 'bars' exists before adding to legend handles
        legend_handles = [h for h in [bars, goal_line] if h is not None]
        legend_labels = [l for l,h in zip(['Current Progress', 'Goal'], [bars, goal_line]) if h is not None]
        if legend_handles:
             ax.legend(handles=legend_handles, labels=legend_labels, loc='lower right', fontsize=CHART_FONT_SIZE-1)


    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf


# Updated function signature and logic
def generate_all_progress_chart(
    title: str,
    player_labels: list[str], # Now expects labels directly
    player_ids: list[int],    # Still need IDs to map data
    exercise_data: dict,      # {user_id: {exercise_id: score, ...}}
    exercise_details: dict    # {exercise_id: {"name": "Name", "goal": 100}, ...}
) -> io.BytesIO:
    """
    Generates a grouped bar chart for all players per exercise using provided labels.
    """
    if not exercise_data or not exercise_details or not player_labels or not player_ids:
        print("Warning: Missing data for generating all progress chart.")
        return io.BytesIO()

    # --- Data Preparation ---
    exercise_ids = list(exercise_details.keys())
    exercise_names = [details['name'] for details in exercise_details.values()]
    # Goals not directly plotted on grouped chart, but could be used for scaling Y axis
    goals = [details.get('goal', 0) for details in exercise_details.values()]

    num_players = len(player_ids)
    num_exercises = len(exercise_ids)

    if num_players == 0 or num_exercises == 0:
        print("Warning: Zero players or exercises for chart.")
        return io.BytesIO()

    # Matrix to hold scores: rows=exercises, cols=players
    scores = np.zeros((num_exercises, num_players))
    for i, ex_id in enumerate(exercise_ids):
        for j, user_id in enumerate(player_ids): # Iterate using the order of player_ids
            scores[i, j] = exercise_data.get(user_id, {}).get(ex_id, 0) # Default to 0

    # --- Plotting ---
    x = np.arange(num_exercises)
    total_bar_width = 0.8 # Total width allocated for all bars per exercise
    width = total_bar_width / num_players # Width of a single player's bar
    # Adjusted figsize: Wider based on exercises and players
    fig_width = max(10, num_exercises * num_players * 0.4)
    fig_height = max(6, num_exercises * 0.3) # Slightly taller if many exercises
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=CHART_DPI)

    # Use a colormap to get distinct colors for players
    colors = plt.cm.get_cmap('viridis', num_players) # 'viridis' or 'tab10' or 'tab20'

    max_score_overall = 0 # Track max score for Y-axis limit

    for j, player_label in enumerate(player_labels): # Use the provided labels
        offset = width * (j - (num_players - 1) / 2) # Centered offsets
        player_scores = scores[:, j]
        rects = ax.bar(x + offset, player_scores, width, label=player_label, color=colors(j / num_players))
        # Optional: Add bar labels (can get very cluttered)
        # ax.bar_label(rects, padding=3, fmt='%d', fontsize=CHART_FONT_SIZE - 3, rotation=90)
        max_score_overall = max(max_score_overall, player_scores.max())


    ax.set_ylabel('Repetitions / Count / Seconds', fontsize=CHART_FONT_SIZE)
    ax.set_title(title, fontsize=CHART_FONT_SIZE + 2, pad=15)
    ax.set_xticks(x, exercise_names, rotation=45, ha="right", fontsize=CHART_FONT_SIZE)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=CHART_FONT_SIZE-1) # Legend outside plot

    # Adjust Y axis limits
    max_goal_overall = max(goals) if goals else 0
    ax.set_ylim(bottom=0, top=max(10, max_score_overall, max_goal_overall) * 1.1)

    plt.tight_layout(rect=[0, 0, 0.85, 1]) # Adjust layout to make space for external legend

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf