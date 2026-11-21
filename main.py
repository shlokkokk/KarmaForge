"""
KarmaForge CLI & Unified Runner
Autonomous Organic Reddit Engagement Engine with Discord Mission Control.
"""

import os
import sys
import json
import asyncio
import threading
import argparse
from pathlib import Path

def load_env_file():
    env_paths = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent / "config" / ".env"
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
            return True
    return False

load_env_file()

from core.reddit_client import RedditClientManager
from core.hunter import Hunter
from core.persona_engine import PersonaEngine
from core.ai_gateway import AIGateway
from core.downvote_shield import DownvoteShield
from core.operator import AutonomousOperator
from core.db import (
    get_daily_comment_count,
    get_recent_comments,
    get_active_comments
)

SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "settings.json"

def load_settings():
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"settings.json not found at {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def show_status():
    settings = load_settings()
    manager = RedditClientManager()
    accounts = manager.get_all_accounts()

    print("\n" + "=" * 65)
    print("KarmaForge Account & Telemetry Status")
    print("=" * 65)

    if not accounts:
        print("No Reddit accounts configured in .env.")
        return

    for session in accounts:
        ok, msg, karma = session.verify_auth()
        daily = get_daily_comment_count(session.username)
        limit = settings.get("pacing", {}).get("daily_comment_limit_per_account", 6)
        status_text = "Active" if ok else f"Offline ({msg})"
        print(f"\nAccount: /u/{session.username}")
        print(f"   Status: {status_text}")
        if ok:
            print(f"   Karma: Comment: {karma.get('comment_karma', 0)} | Post: {karma.get('link_karma', 0)}")
            print(f"   Today's Quota: {daily}/{limit} comments")

    active_shield = get_active_comments()
    print(f"\nActive Downvote Shield Watchlist: {len(active_shield)} comments monitored")
    
    recent = get_recent_comments(limit=5)
    if recent:
        print("\nLast 5 Comments Posted:")
        for r in recent:
            print(f"   [{r['posted_at']}] /u/{r['account_username']} in r/{r['subreddit']} (Score: {r['score']}):")
            print(f"      \"{r['comment_text'][:90]}...\"")
    print("=" * 65 + "\n")

def run_dry_run():
    settings = load_settings()
    manager = RedditClientManager()
    hunter = Hunter(settings)
    ai = AIGateway()

    accounts = manager.get_all_accounts()
    if not accounts:
        print("No accounts configured in .env.")
        return
    session = accounts[0]
    
    print("\n" + "=" * 65)
    print("KarmaForge Wave-Riding Simulation (Dry Run Mode)")
    print("   Scanning live feeds & generating proposed comments...")
    print("   (No comments will be posted to Reddit)")
    print("=" * 65)

    subreddits = ["programming", "headphones", "AskReddit", "me_irl"]
    for sub_name in subreddits:
        print(f"\nScanning r/{sub_name} (Rising & Top Hour)...")
        candidates = hunter.scan_subreddit(session, sub_name, limit=15)
        if not candidates:
            print(f"   No posts passed age/momentum filters in r/{sub_name}.")
            continue

        best = candidates[0]
        cat, sys_prompt = PersonaEngine.get_persona_for_subreddit(sub_name)
        user_prompt = PersonaEngine.build_comment_prompt(best["title"], best["selftext"], sub_name)

        print(f"   Post Qualified: \"{best['title'][:70]}\"")
        print(f"      Metrics: {best['score']} pts, {best['num_comments']} comments, {best['age_minutes']}m old | Velocity: {best['momentum']}")
        
        comment = ai.generate_comment(user_prompt, sys_prompt)
        if comment:
            print(f"      Proposed Comment ({cat}):")
            print(f"         \"{comment}\"")
        else:
            print("      AI generation skipped (check API keys).")

    print("\n" + "=" * 65)
    print("Dry run completed.")

def start_health_server(port: int = 7860):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"KarmaForge Autonomous Engine: ACTIVE\n")
        def log_message(self, format, *args):
            return
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[Health Server] Could not bind to port {port}: {e}")

def run_unified():
    """Runs Discord Bot and Autonomous Operator simultaneously."""
    settings = load_settings()
    manager = RedditClientManager()
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()

    from discord_bot.bot import KarmaForgeBot
    from core.downvote_shield import DownvoteShield

    shield = DownvoteShield(settings, manager)
    bot = KarmaForgeBot(reddit_manager=manager, shield=shield)
    operator = AutonomousOperator(settings, manager, discord_bot=bot)
    bot.operator = operator

    def start_operator_thread(loop):
        operator.loop = loop
        operator.run_forever()

    # Start lightweight health server only if requested (Gradio handles 7860 on Spaces)
    if os.environ.get("ENABLE_HEALTH_SERVER", "0") == "1":
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()

    if token:
        print("[Launcher] Starting Discord Bot & Autonomous Operator...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start background operator thread
        op_thread = threading.Thread(target=start_operator_thread, args=(loop,), daemon=True)
        op_thread.start()

        # Run Discord Bot in main asyncio loop
        try:
            bot.run(token)
        except KeyboardInterrupt:
            operator.running = False
    else:
        print("[Launcher] No Discord Bot Token found. Running CLI-only operator...")
        operator.run_forever()

def main():
    parser = argparse.ArgumentParser(description="KarmaForge Reddit Autonomous Engagement Engine")
    parser.add_argument("--dry-run", action="store_true", help="Simulate hunting and comment generation without posting")
    parser.add_argument("--status", action="store_true", help="Display account karma and live system status")
    parser.add_argument("--check-shield", action="store_true", help="Run immediate Downvote Shield check")
    parser.add_argument("--run", action="store_true", help="Start continuous autonomous engine + Discord bot")
    parser.add_argument("--bot", action="store_true", help="Start Discord bot only")
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run()
    elif args.status:
        show_status()
    elif args.check_shield:
        settings = load_settings()
        manager = RedditClientManager()
        shield = DownvoteShield(settings, manager)
        stats = shield.run_check_cycle()
        print(f"Shield Results: Checked: {stats['checked']} | Deleted: {stats['deleted']} | Milestones: {stats['milestones']}")
    elif args.bot:
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        from discord_bot.bot import run_discord_bot
        run_discord_bot(token)
    elif args.run:
        run_unified()
    else:
        show_status()
        print("Commands:")
        print("   python main.py --status       # View karma and account health")
        print("   python main.py --dry-run      # Test hunting & comment generation safely")
        print("   python main.py --run          # Launch full autonomous operator + Discord bot")
        print("   python main.py --bot          # Launch Discord bot standalone\n")

if __name__ == "__main__":
    main()
