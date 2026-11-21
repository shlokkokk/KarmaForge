"""
KarmaForge Downvote Shield & Karma Radar
Multi-signal defensive engine protecting account karma against downvotes,
vote fuzzing, and sudden thread controversies while safeguarding high-karma winners.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from core.db import get_active_comments, update_comment_score, get_latest_karma

class DownvoteShield:
    """Watchdog for negative score detection, milestone tracking, and discussion preservation."""

    def __init__(self, settings: Dict[str, Any], reddit_manager: Any, discord_bot: Any = None):
        self.cfg = settings.get("downvote_shield", {})
        self.auto_delete = self.cfg.get("auto_delete_enabled", True)
        self.hard_delete_threshold = self.cfg.get("hard_delete_threshold", -3)
        self.soft_delete_threshold = self.cfg.get("soft_delete_threshold", -1)
        self.grace_period_minutes = self.cfg.get("grace_period_minutes", 15)
        self.discussion_buffer_replies = self.cfg.get("discussion_buffer_replies", 1)
        self.vault_minimum_score = self.cfg.get("vault_minimum_score", 3)
        self.high_water_mark_immunity = self.cfg.get("high_water_mark_immunity", 10)
        self.window_hours = self.cfg.get("monitor_window_hours", 36)
        
        self.reddit_manager = reddit_manager
        self.discord_bot = discord_bot
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.milestone_tiers = [10, 25, 50, 100, 250, 500]

    def _sync_dispatch(self, coro):
        loop = getattr(self.discord_bot, "loop", None) or self.loop
        if self.discord_bot and loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            try:
                coro.close()
            except Exception:
                pass

    def evaluate_comment_state(
        self,
        score: int,
        peak_score: int,
        age_minutes: float,
        replies_count: int,
        delta_s: int,
        is_fragile: bool
    ) -> tuple[str, str]:
        """
        Evaluates the comment against all 8 operational safety cases.
        Returns (state_name, reason).
        """
        # Case 1: Karma Vault (High-score lock)
        if score >= self.high_water_mark_immunity:
            return "VAULTED", f"Score +{score} locked in vault. Total immunity."

        # Case 2: Healthy positive
        if score >= self.vault_minimum_score:
            return "HEALTHY", f"Score +{score} is net positive and healthy."

        # Case 3: Dip Watch (Previously peaked high, experiencing noise/fuzzing)
        if score >= 1 and peak_score >= self.high_water_mark_immunity:
            return "DIP_WATCH", f"Score +{score} (peaked +{peak_score}). Positive profit maintained."

        # Case 4: Catastrophic Reversal of a previously vaulted winner
        if score <= self.soft_delete_threshold and peak_score >= self.high_water_mark_immunity:
            return "ANOMALY_COLLAPSE", f"Thread anomaly: collapsed from peak +{peak_score} to {score}. Held for manual review."

        # Case 5: Infant Grace Period (Reddit vote fuzzing & initial bot noise)
        if age_minutes < self.grace_period_minutes and score > self.hard_delete_threshold:
            return "GRACE", f"Age {age_minutes:.1f}m < {self.grace_period_minutes}m. Shielded against fuzzing."

        # Case 6: Discussion Rebound Immunity (Active replies or positive velocity)
        if score in [-1, -2] and (replies_count >= self.discussion_buffer_replies or delta_s > 0):
            reason = f"Replies: {replies_count}, Velocity Delta: +{delta_s}. High rebound probability."
            return "REBOUND_IMMUNITY", reason

        # Case 7: Avalanche Hard Purge (Severe dogpile or fragile account risk)
        if score <= self.hard_delete_threshold or (is_fragile and score <= -2 and replies_count == 0):
            reason = f"Score {score} hit hard floor (Fragile: {is_fragile}). Dogpile purge triggered."
            return "HARD_PURGE", reason

        # Case 8: Stagnant Soft Purge (Matured flop with 0 replies and flat/negative trajectory)
        if score <= self.soft_delete_threshold and age_minutes >= self.grace_period_minutes and replies_count == 0 and delta_s <= 0:
            reason = f"Score {score} after {age_minutes:.1f}m with 0 replies and delta {delta_s}. Dead weight purge."
            return "SOFT_PURGE", reason

        return "WATCHLIST", f"Score {score}, age {age_minutes:.1f}m. Retained on watchlist."

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

            # Fetch account karma fragility
            acc_karma = get_latest_karma(username)
            acc_comment_karma = acc_karma.get("comment_karma", 1) if acc_karma else 1
            is_fragile = acc_comment_karma <= 5

            comment_ids = [c["comment_id"] for c in comments_list]
            live_objs = session.batch_get_comments(comment_ids)
            live_map = {obj.get("id"): obj for obj in live_objs if isinstance(obj, dict)}

            for row in comments_list:
                cid = row["comment_id"]
                live_info = live_map.get(cid)
                if not live_info:
                    continue

                score = live_info.get("score")
                if score is None:
                    continue

                old_score = row.get("score", 1)
                old_peak = row.get("peak_score") or old_score
                new_peak = max(old_peak, score)

                # Parse age in minutes
                age_minutes = 30.0
                if row.get("posted_at"):
                    try:
                        posted_dt = datetime.strptime(row["posted_at"], "%Y-%m-%d %H:%M:%S")
                        age_minutes = max(0.0, (datetime.now() - posted_dt).total_seconds() / 60.0)
                    except Exception:
                        pass

                # Parse score history & compute trajectory delta
                raw_history = row.get("score_history") or "[]"
                try:
                    history = json.loads(raw_history) if isinstance(raw_history, str) else []
                except Exception:
                    history = []
                
                delta_s = (score - history[-1]) if history else 0
                history.append(score)
                if len(history) > 6:
                    history = history[-6:]
                updated_history_str = json.dumps(history)

                # Fetch replies count if comment is at risk (score <= 0)
                replies_count = row.get("replies_count") or 0
                permalink = live_info.get("permalink") or row.get("post_url", "")
                if score <= 0 and hasattr(session, "get_comment_replies_count"):
                    fetched_replies = session.get_comment_replies_count(permalink)
                    replies_count = max(replies_count, fetched_replies)

                # Milestone tracking
                for milestone in self.milestone_tiers:
                    if old_score < milestone and score >= milestone:
                        stats["milestones"] += 1
                        self._sync_dispatch(
                            self.discord_bot.log_milestone(
                                username=username,
                                comment_text=row["comment_text"],
                                score=score,
                                post_url=row["post_url"]
                            )
                        )
                        break

                # State Machine Evaluation
                state, reason = self.evaluate_comment_state(
                    score=score,
                    peak_score=new_peak,
                    age_minutes=age_minutes,
                    replies_count=replies_count,
                    delta_s=delta_s,
                    is_fragile=is_fragile
                )

                # Execute Deletion if state demands purge
                if state in ["HARD_PURGE", "SOFT_PURGE"]:
                    if self.auto_delete:
                        success, msg = session.delete_comment_by_id(cid)
                        if success:
                            stats["deleted"] += 1
                            update_comment_score(
                                comment_id=cid,
                                score=score,
                                deleted=True,
                                peak_score=new_peak,
                                score_history=updated_history_str,
                                replies_count=replies_count,
                                status=state
                            )
                            print(f"  [Shield: {state}] Comment {cid} (score {score}) by /u/{username} AUTO-DELETED. Reason: {reason}")
                            self._sync_dispatch(
                                self.discord_bot.log_auto_deletion(
                                    username=username,
                                    comment_id=cid,
                                    score=score,
                                    comment_text=row["comment_text"],
                                    post_url=row["post_url"]
                                )
                            )
                            continue

                elif state in ["ANOMALY_COLLAPSE", "WATCHLIST"] and score <= self.soft_delete_threshold:
                    if old_score > self.soft_delete_threshold:
                        self._sync_dispatch(
                            self.discord_bot.log_shield_warning(
                                username=username,
                                comment_id=cid,
                                score=score,
                                comment_text=row["comment_text"],
                                post_url=row["post_url"]
                            )
                        )

                # Persist updated metrics and state
                update_comment_score(
                    comment_id=cid,
                    score=score,
                    deleted=False,
                    peak_score=new_peak,
                    score_history=updated_history_str,
                    replies_count=replies_count,
                    status=state
                )

        return stats

