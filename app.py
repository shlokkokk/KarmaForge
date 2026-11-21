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

import gradio as gr
import spaces

@spaces.GPU
def init_gpu():
    return "ZeroGPU initialized"

try:
    init_gpu()
except Exception as e:
    print(f"ZeroGPU init note: {e}")

from main import run_unified
from core.reddit_client import RedditClientManager
from core.db import get_recent_comments, get_daily_comment_count

def run_reddit_diagnostic() -> str:
    import subprocess
    c1 = os.environ.get("REDDIT_ACCOUNT_1_SESSION", "").replace("\r", "").replace("\n", "").strip('"').strip("'").strip()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    
    results = ["### Network & Reddit Deep Diagnostics\n"]
    
    # 1. Check Space Outbound IP
    try:
        ip_res = subprocess.run(["curl", "-s", "https://ifconfig.me"], capture_output=True, text=True, timeout=5)
        results.append(f"- **Container IP**: `{ip_res.stdout.strip()}`")
    except Exception as e:
        results.append(f"- **Container IP**: Error `{e}`")

    results.append(f"- **Cookie length**: `{len(c1)}` chars")

    # 2. Test old.reddit.com with response headers (-i) without redirect following
    try:
        cmd1 = ["curl", "-s", "-i", "-A", ua, "-H", f"Cookie: reddit_session={c1}", "https://old.reddit.com/api/me.json"]
        r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=10)
        lines = r1.stdout.splitlines()
        status_line = lines[0] if lines else "None"
        headers_preview = [l for l in lines[:15] if any(l.lower().startswith(x) for x in ["location:", "set-cookie:", "server:", "x-", "content-type:"])]
        results.append(f"\n**Test 1: old.reddit.com with Cookie Header (No -L)**\n- Status: `{status_line}`\n- Headers: ```{headers_preview}```")
    except Exception as e:
        results.append(f"\n**Test 1 Error**: `{e}`")

    # 3. Test www.reddit.com with response headers (-i)
    try:
        cmd2 = ["curl", "-s", "-i", "-A", ua, "-H", f"Cookie: reddit_session={c1}", "https://www.reddit.com/api/me.json"]
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        lines2 = r2.stdout.splitlines()
        status_line2 = lines2[0] if lines2 else "None"
        headers_preview2 = [l for l in lines2[:15] if any(l.lower().startswith(x) for x in ["location:", "set-cookie:", "server:", "x-", "content-type:"])]
        results.append(f"\n**Test 2: www.reddit.com with Cookie Header (No -L)**\n- Status: `{status_line2}`\n- Headers: ```{headers_preview2}```")
    except Exception as e:
        results.append(f"\n**Test 2 Error**: `{e}`")

    # 4. Test Python requests directly
    try:
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": ua})
        s.cookies.set("reddit_session", c1, domain=".reddit.com")
        resp = s.get("https://old.reddit.com/api/me.json", allow_redirects=False, timeout=10)
        results.append(f"\n**Test 3: Python requests (old.reddit.com)**\n- Status: `{resp.status_code}`\n- Location: `{resp.headers.get('location')}`\n- Body preview: `{resp.text[:120]}`")
    except Exception as e:
        results.append(f"\n**Test 3 Error**: `{e}`")

    return "\n".join(results)

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

        # Append deep diagnostics
        lines.append("\n---\n" + run_reddit_diagnostic())

        return "\n".join(lines)
    except Exception as e:
        return f"Error loading status: {e}"

# Start KarmaForge autonomous engine in background thread
print(run_reddit_diagnostic())
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

        # ZeroGPU registration anchor
        gpu_btn = gr.Button("ZeroGPU Healthcheck", visible=False)
        gpu_btn.click(fn=init_gpu, outputs=[])

    if __name__ == "__main__":
        demo.launch(server_name="0.0.0.0", server_port=7860)
else:
    if __name__ == "__main__":
        while True:
            time.sleep(3600)
