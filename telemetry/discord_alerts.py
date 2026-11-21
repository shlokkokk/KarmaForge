"""
KarmaForge Discord Alerts & Telemetry
Lightweight, zero-dependency Discord webhook dispatcher for real-time mission control.
"""

import os
import json
import urllib.request
from typing import Optional, Dict, Any

class DiscordAlerts:
    """Sends rich Discord embeds via native webhooks without external packages."""

    @staticmethod
    def _send_webhook(payload: Dict[str, Any]) -> bool:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "KarmaForge-Discord-Notifier/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"  [Discord Webhook] Failed to deliver alert: {e}")
            return False

    @classmethod
    def log_comment_posted(
        cls,
        username: str,
        subreddit: str,
        post_title: str,
        comment_text: str,
        post_url: str,
        persona: str
    ):
        """Sends rich embed when a comment is successfully posted."""
        embed = {
            "title": f"💬 New Comment Posted by /u/{username}",
            "color": 0xFF4500,  # Reddit OrangeRed
            "fields": [
                {"name": "Subreddit", "value": f"r/{subreddit}", "inline": True},
                {"name": "Persona", "value": persona, "inline": True},
                {"name": "Post Title", "value": post_title[:250], "inline": False},
                {"name": "Comment Text", "value": f"_{comment_text}_", "inline": False},
                {"name": "Direct Link", "value": f"[Open Discussion on Reddit]({post_url})", "inline": False}
            ],
            "footer": {"text": "KarmaForge Organic Engine • Wave-Riding"}
        }
        cls._send_webhook({"embeds": [embed]})

    @classmethod
    def log_downvote_shield_alert(
        cls,
        username: str,
        comment_id: str,
        score: int,
        deleted: bool,
        comment_text: str,
        post_url: str
    ):
        """Alerts when a comment experiences downvotes."""
        status = "🗑️ AUTO-DELETED to protect karma!" if deleted else "⚠️ Negative score warning!"
        embed = {
            "title": f"🛡️ Downvote Shield Triggered ({score} pts)",
            "description": f"**Account:** /u/{username}\n**Status:** {status}",
            "color": 0xED4245 if deleted else 0xFEE75C,  # Red / Yellow
            "fields": [
                {"name": "Comment Text", "value": f"_{comment_text[:200]}_", "inline": False},
                {"name": "Comment ID", "value": comment_id, "inline": True},
                {"name": "Post Link", "value": f"[View Post]({post_url})", "inline": True}
            ],
            "footer": {"text": "KarmaForge Downvote Shield"}
        }
        cls._send_webhook({"embeds": [embed]})

    @classmethod
    def log_milestone(
        cls,
        username: str,
        comment_text: str,
        score: int,
        post_url: str
    ):
        """Celebrates when a comment hits significant upvote milestones."""
        embed = {
            "title": f"🚀 Karma Milestone Crossed: +{score} Upvotes!",
            "description": f"/u/{username}'s wave-riding comment is blowing up!",
            "color": 0x57F287,  # Discord Green
            "fields": [
                {"name": "Comment", "value": f"_{comment_text[:250]}_", "inline": False},
                {"name": "Post Link", "value": f"[View on Reddit]({post_url})", "inline": False}
            ],
            "footer": {"text": "KarmaForge Milestone Radar"}
        }
        cls._send_webhook({"embeds": [embed]})
