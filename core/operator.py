"""
KarmaForge Autonomous Operator
Main orchestrator handling multi-account rotation, circadian rest,
humanized pacing jitter, and category-level Discord telemetry.
"""

from __future__ import annotations

import os
import time
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable

from core.db import (
    get_daily_comment_count,
    record_comment,
    record_karma,
    get_recent_comments
)
from core.hunter import Hunter
from core.persona_engine import PersonaEngine
from core.ai_gateway import AIGateway
from core.downvote_shield import DownvoteShield

class AutonomousOperator:
    """Orchestrates stealth operations across all enabled Reddit accounts."""

    def __init__(self, settings: Dict[str, Any], reddit_manager: Any, discord_bot: Any = None):
        self.settings = settings
        self.reddit_manager = reddit_manager
        self.discord_bot = discord_bot
        self.hunter = Hunter(settings)
        self.ai = AIGateway()
        self.shield = DownvoteShield(settings, reddit_manager, discord_bot=discord_bot)
        
        self.pacing = settings.get("pacing", {})
        self.min_delay = self.pacing.get("min_delay_minutes", 45) * 60
        self.max_delay = self.pacing.get("max_delay_minutes", 115) * 60
        self.daily_limit = self.pacing.get("daily_comment_limit_per_account", 6)
        
        self.sleep_cfg = self.pacing.get("circadian_sleep", {})
        self.subreddits_cfg = settings.get("subreddits", {})
        self.running = False
        self.paused = False
        self._cooldown_alerted: Dict[str, float] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.next_cycle_at: float = time.time() + random.uniform(self.min_delay, self.max_delay)

    def _sync_dispatch(self, coro):
        loop = getattr(self.discord_bot, "loop", None) or self.loop
        if self.discord_bot and loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            try:
                coro.close()
            except Exception:
                pass

    def is_in_circadian_rest(self) -> bool:
        if not self.sleep_cfg.get("enabled", True):
            return False

        # Apply local timezone offset (defaulting to +5.5 for IST)
        tz_offset = timedelta(hours=self.sleep_cfg.get("timezone_offset_hours", 5.5))
        now = datetime.utcnow() + tz_offset
        start_m = self.sleep_cfg.get("start_hour", 0) * 60 + self.sleep_cfg.get("start_minute", 30)
        end_m = self.sleep_cfg.get("end_hour", 8) * 60 + self.sleep_cfg.get("end_minute", 30)
        current_m = now.hour * 60 + now.minute

        if start_m > end_m:
            return current_m >= start_m or current_m < end_m
        return start_m <= current_m < end_m

    def execute_account_turn(self, session: Any) -> Tuple[bool, str]:
        if self.paused:
            print(f"  [{session.username}] Engine is currently PAUSED via Control Panel.")
            return False, "Engine is paused via Control Panel."

        username = session.username

        # Health check
        ok, msg, karma = session.verify_auth()
        if not ok:
            print(f"  ❌ [{username}] Session error: {msg}")
            self._sync_dispatch(
                self.discord_bot.log_session_alert(
                    username=username,
                    status="EXPIRED",
                    details=f"The browser session cookie for /u/{username} is invalid or expired ({msg}). Update .env and run status check."
                )
            )
            return False, f"Session error: {msg}"

        daily_count = get_daily_comment_count(username)
        if daily_count >= self.daily_limit:
            print(f"  [{username}] Daily quota reached ({daily_count}/{self.daily_limit}). Resting.")
            return False, f"Daily quota reached ({daily_count}/{self.daily_limit})."

        # Check if account posted recently in the database to prevent reboot spam
        recent = get_recent_comments(username, limit=1)
        if recent and recent[0].get("posted_at"):
            try:
                posted_dt = datetime.strptime(recent[0]["posted_at"], "%Y-%m-%d %H:%M:%S")
                elapsed_seconds = (datetime.now() - posted_dt).total_seconds()
                min_spacing = 900  # 15 minutes minimum spacing between comments for an account
                if elapsed_seconds < min_spacing:
                    rem = int(min_spacing - elapsed_seconds)
                    print(f"  [{username}] Posted recently ({int(elapsed_seconds/60)}m ago). Waiting {rem}s before next turn.")
                    session.cooldown_until = max(session.cooldown_until, time.time() + rem)
                    return False, f"Recent post cooldown ({rem}s remaining)."
            except Exception:
                pass

        if session.is_on_cooldown():
            rem = session.get_remaining_cooldown()
            print(f"  [{username}] On cooldown ({rem}s remaining). Skipping turn.")
            last_alert = self._cooldown_alerted.get(username, 0)
            if time.time() - last_alert > 600:
                self._cooldown_alerted[username] = time.time()
                self._sync_dispatch(self.discord_bot.log_ratelimit(username, rem))
            return False, f"On Reddit cooldown ({rem}s remaining)."
        else:
            self._cooldown_alerted.pop(username, None)

        all_subs = []
        for cat_subs in self.subreddits_cfg.values():
            all_subs.extend(cat_subs)

        # Protect fragile accounts (comment karma <= 5) from high-friction subreddits
        if getattr(session, "comment_karma", 1) <= 5:
            all_subs = [s for s in all_subs if s.lower() not in ["advice"]]

        random.shuffle(all_subs)

        candidates = []
        for sub_name in all_subs[:6]:
            found = self.hunter.scan_subreddit(session, sub_name, limit=20)
            if found:
                for c in found:
                    self._sync_dispatch(
                        self.discord_bot.log_radar(
                            subreddit=sub_name,
                            candidate_title=c["title"],
                            age_m=c["age_minutes"],
                            comments_count=c["num_comments"],
                            momentum=c["momentum"],
                            qualified=True,
                            reason="Passed all momentum filters"
                        )
                    )
                candidates.extend(found)
                if len(candidates) >= 3:
                    break
            time.sleep(random.uniform(1.5, 2.5))

        if not candidates:
            print(f"  [{username}] No qualifying rising threads found right now. Will scan on next cycle.")
            return False, "No qualifying rising threads found right now."

        target = candidates[0]
        sub_name = target["subreddit"]
        cat_name, system_prompt = PersonaEngine.get_persona_for_subreddit(sub_name)

        print(f"\n  Target Selected in r/{sub_name}: \"{target['title'][:70]}...\"")
        print(f"     Metrics: {target['score']} upvotes, {target['num_comments']} comments, {target['age_minutes']}m old, {target['momentum']} velocity")

        user_prompt = PersonaEngine.build_comment_prompt(
            title=target["title"],
            selftext=target["selftext"],
            subreddit=sub_name
        )

        loop = getattr(self.discord_bot, "loop", None) or self.loop
        telemetry_cb = None
        if self.discord_bot and loop and loop.is_running() and hasattr(self.discord_bot, "create_ai_telemetry_session"):
            t_session = self.discord_bot.create_ai_telemetry_session(sub_name, target["title"])
            if t_session:
                def on_step(status: str, detail: str, is_final: bool = False, success: bool = True, output_preview: str = ""):
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            t_session.update(status, detail, is_final, success, output_preview),
                            loop
                        )
                telemetry_cb = on_step

        comment_text = self.ai.generate_comment(
            prompt=user_prompt,
            system_prompt=system_prompt,
            enforce_lowercase=self.settings.get("engagement", {}).get("natural_lowercase_start", True),
            max_sentences=self.settings.get("engagement", {}).get("max_sentences", 2),
            telemetry_cb=telemetry_cb
        )

        if not comment_text:
            print(f"  [{username}] AI failed to generate comment. Skipping turn.")
            return False, "AI failed to generate a comment."

        print(f"  Crafted Comment ({cat_name}): \"{comment_text}\"")

        comment_id, err = session.reply_to_submission(target["id"], comment_text)
        if err or not comment_id:
            print(f"  Failed to post: {err}")
            if "Rate-limited" in str(err):
                rem = session.get_remaining_cooldown() or 60
                self._sync_dispatch(self.discord_bot.log_ratelimit(username, rem))
            else:
                self._sync_dispatch(self.discord_bot.log_error(f"Post Failure /u/{username}", str(err)))
            return False, f"Failed to post to Reddit: {err}"

        if self.settings.get("engagement", {}).get("auto_upvote_parent_post", True):
            session.upvote(target["id"])
            self._sync_dispatch(self.discord_bot.log_upvote(username, target["title"], target["url"]))

        record_comment(
            comment_id=comment_id,
            post_id=target["id"],
            account_username=username,
            subreddit=sub_name,
            post_title=target["title"],
            post_url=target["url"],
            comment_text=comment_text,
            persona_used=cat_name
        )

        comment_direct_url = f"https://reddit.com/comments/{target['id']}/-/{comment_id}"
        self._sync_dispatch(
            self.discord_bot.log_activity(
                username=username,
                subreddit=sub_name,
                post_title=target["title"],
                comment_text=comment_text,
                post_url=comment_direct_url,
                persona=cat_name,
                comment_id=comment_id
            )
        )

        print(f"  Comment successfully posted by /u/{username}! [https://reddit.com/comments/{target['id']}/-/{comment_id}]")
        return True, f"Comment posted to r/{sub_name} by /u/{username}!"

    def run_forever(self):
        self.running = True
        self.shield.loop = self.loop
        print("\n" + "=" * 65)
        print("KarmaForge Autonomous Engine Started")
        print(f"   Target limit: {self.daily_limit} comments/day per account")
        print(f"   Jitter delay: {self.min_delay // 60}m - {self.max_delay // 60}m")
        print("=" * 65 + "\n")

        accounts = self.reddit_manager.get_all_accounts()
        if not accounts:
            print("No enabled Reddit accounts found! Please check your .env configuration.")
            return

        while self.running:
            try:
                shield_stats = self.shield.run_check_cycle()
                if shield_stats["checked"] > 0:
                    print(f"  [Shield] Checked {shield_stats['checked']} active comments. Deletions: {shield_stats['deleted']}, Milestones: {shield_stats['milestones']}")

                if self.is_in_circadian_rest():
                    print("  [Circadian Rest] Local night hours active. Sleeping 25 minutes...")
                    time.sleep(1500)
                    continue

                for session in accounts:
                    if not self.running:
                        break
                    self.execute_account_turn(session)

                    if len(accounts) > 1:
                        inter_account_delay = random.uniform(300, 600)
                        print(f"  [Operator] Waiting {inter_account_delay / 60:.1f} minutes before next account turn...")
                        time.sleep(inter_account_delay)

                # Schedule the next full cycle with jitter delay (45 - 115 minutes)
                self.next_cycle_at = time.time() + random.uniform(self.min_delay, self.max_delay)
                next_time = datetime.fromtimestamp(self.next_cycle_at).strftime("%H:%M:%S")
                rem_mins = int(max(0, self.next_cycle_at - time.time()) // 60)
                print(f"\n  Cycle complete. Next run scheduled at {next_time} (~{rem_mins} minutes)...")

                while time.time() < self.next_cycle_at and self.running:
                    # Run DownvoteShield watchdog every 2 minutes
                    try:
                        shield_stats = self.shield.run_check_cycle()
                        if shield_stats.get("deleted", 0) > 0:
                            print(f"  [Shield Watchdog] Automatically deleted {shield_stats['deleted']} negative comments.")
                    except Exception as se:
                        print(f"  [Shield Watchdog Error] {se}")
                    
                    time.sleep(min(120, max(1, int(self.next_cycle_at - time.time()))))

            except KeyboardInterrupt:
                print("\nShutdown initiated.")
                self.running = False
                break
            except Exception as e:
                print(f"  [Operator Error] {e}")
                self._sync_dispatch(self.discord_bot.log_error("Operator Loop Error", str(e)))
                time.sleep(60)
