"""
KarmaForge Downvote Shield & Karma Radar
Monitors active comments in batches, auto-deletes negative outliers,
and alerts on high-upvote milestones.
"""

import asyncio
from typing import Dict, Any, List, Optional
from core.db import get_active_comments, update_comment_score

class DownvoteShield:
    """Watchdog for negative score detection and milestone tracking."""

    def __init__(self, settings: Dict[str, Any], reddit_manager: Any, discord_bot: Any = None):
        self.cfg = settings.get("downvote_shield", {})
        self.auto_delete = self.cfg.get("auto_delete_enabled", True)
        self.delete_threshold = self.cfg.get("delete_threshold", -2)
        self.alert_threshold = self.cfg.get("alert_threshold", -1)
        self.window_hours = self.cfg.get("monitor_window_hours", 36)
        self.reddit_manager = reddit_manager
        self.discord_bot = discord_bot
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.milestone_tiers = [10, 25, 50, 100, 250, 500]

    def run_check_cycle(self) -> Dict[str, Any]:
        """Runs one full inspection cycle across all active comments."""
        active_comments = get_active_comments(window_hours=self.window_hours)
        if not active_comments:
            return {"checked": 0, "deleted": 0, "milestones": 0}

        by_account: Dict[str, List[Dict[str, Any]]] = {}
        for c in active_comments:
            user = c["account_username"]
            by_account.setdefault(user, []).append(c)

        stats = {"checked": len(active_comments), "deleted": 0, "milestones": 0}

        for username, comments_list in by_account.items():
            session = self.reddit_manager.get_account(username)
            if not session:
                continue

            comment_ids = [c["comment_id"] for c in comments_list]
            live_objs = session.batch_get_comments(comment_ids)
            live_map = {obj.get("id"): obj.get("score") for obj in live_objs if isinstance(obj, dict)}

            for row in comments_list:
                cid = row["comment_id"]
                score = live_map.get(cid)
                if score is None:
                    continue

                old_score = row["score"]

                # Milestone detection
                for milestone in self.milestone_tiers:
                    if old_score < milestone and score >= milestone:
                        stats["milestones"] += 1
                        if self.discord_bot and self.loop:
                            asyncio.run_coroutine_threadsafe(
                                self.discord_bot.log_milestone(
                                    username=username,
                                    comment_text=row["comment_text"],
                                    score=score,
                                    post_url=row["post_url"]
                                ),
                                self.loop
                            )
                        break

                # Negative score & downvote shield execution
                if score <= self.delete_threshold:
                    if self.auto_delete:
                        success, msg = session.delete_comment_by_id(cid)
                        if success:
                            stats["deleted"] += 1
                            update_comment_score(cid, score, deleted=True)
                            print(f"  [Shield] Comment {cid} (score {score}) by /u/{username} AUTO-DELETED.")
                            if self.discord_bot and self.loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.discord_bot.log_auto_deletion(
                                        username=username,
                                        comment_id=cid,
                                        score=score,
                                        comment_text=row["comment_text"],
                                        post_url=row["post_url"]
                                    ),
                                    self.loop
                                )
                            continue

                elif score <= self.alert_threshold and old_score > self.alert_threshold:
                    if self.discord_bot and self.loop:
                        asyncio.run_coroutine_threadsafe(
                            self.discord_bot.log_shield_warning(
                                username=username,
                                comment_id=cid,
                                score=score,
                                comment_text=row["comment_text"],
                                post_url=row["post_url"]
                            ),
                            self.loop
                        )

                update_comment_score(cid, score, deleted=False)

        return stats
