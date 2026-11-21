"""
KarmaForge Hugging Face Space Entrypoint
Launches the autonomous engine + Discord bot in a background daemon thread
and provides a clean Gradio Mission Control dashboard.
"""

import os
import sys
import threading
import time
from typing import List, Dict, Any

try:
    import gradio as gr
except ImportError:
    gr = None

from main import run_unified
from core.reddit_client import RedditClientManager
from core.db import get_recent_comments, get_daily_comment_count

def get_status_markdown() -> str:
    try:
        manager = RedditClientManager()
        accounts = manager.get_all_accounts()
        if not accounts:
            return "No accounts configured yet. Set your environment secrets in Space Settings."

        lines = ["### KarmaForge Operational Telemetry\n"]
        for acc in accounts:
            ok, msg, karma = acc.verify_auth()
            daily = get_daily_comment_count(acc.username)
            status_str = "ACTIVE" if ok else f"ERROR: {msg}"
            ckarma = karma.get("comment_karma", 0)
            pkarma = karma.get("link_karma", 0)
            lines.append(
                f"- **/u/{acc.username}**: Status: `{status_str}` | "
                f"Comment Karma: **{ckarma}** | Post Karma: **{pkarma}** | "
                f"Daily Quota: `{daily}/6`"
            )

        recent = get_recent_comments(limit=5)
        lines.append("\n### Recent Wave-Riding Comments")
        if recent:
            for r in recent:
                lines.append(
                    f"- **r/{r.get('subreddit')}** | Score: `{r.get('score')}` | "
                    f"Author: `/u/{r.get('account_username')}`\n"
                    f"  > \"{r.get('comment_text')}\""
                )
        else:
            lines.append("- *No comments posted yet in this cycle.*")

        return "\n".join(lines)
    except Exception as e:
        return f"Error loading status: {e}"

# Start KarmaForge autonomous engine in background thread
engine_thread = threading.Thread(target=run_unified, daemon=True)
engine_thread.start()

# Launch Gradio interface
if gr:
    with gr.Blocks(title="KarmaForge Mission Control") as demo:
        gr.Markdown("# KarmaForge Mission Control")
        gr.Markdown("Autonomous organic Reddit engagement engine with real-time Discord telemetry.")
        
        status_display = gr.Markdown(value=get_status_markdown)
        refresh_btn = gr.Button("Refresh Telemetry")
        refresh_btn.click(fn=get_status_markdown, outputs=status_display)

    if __name__ == "__main__":
        demo.launch(server_name="0.0.0.0", server_port=7860)
else:
    if __name__ == "__main__":
        while True:
            time.sleep(3600)
