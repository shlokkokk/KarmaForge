"""
KarmaForge Wave-Riding Hunter
Scans 'Rising' and 'Top (Past Hour)' feeds to find prime discussions
before they hit the front page.
"""

import time
from typing import List, Dict, Any, Tuple
from core.db import has_post_been_targeted

class Hunter:
    """Finds high-velocity candidate posts matching strict qualification rules."""

    def __init__(self, settings: Dict[str, Any]):
        self.qual_cfg = settings.get("qualification", {})
        self.min_age_m = self.qual_cfg.get("min_post_age_minutes", 15)
        self.max_age_m = self.qual_cfg.get("max_post_age_minutes", 55)
        self.max_comments = self.qual_cfg.get("max_existing_comments", 25)
        self.min_upvotes = self.qual_cfg.get("min_upvotes", 2)
        self.skip_serious = self.qual_cfg.get("skip_serious_tag", True)
        self.blacklist = [w.lower() for w in self.qual_cfg.get("blacklist_keywords", [])]

    def is_qualified(self, post: Dict[str, Any]) -> Tuple[bool, str]:
        """Runs the complete qualification filter chain against a candidate post dict."""
        post_id = post.get("id", "")
        if not post_id or has_post_been_targeted(post_id):
            return False, "Already targeted by KarmaForge."

        if post.get("locked", False):
            return False, "Thread is locked."
        if post.get("archived", False):
            return False, "Thread is archived."
        if post.get("over_18", False):
            return False, "NSFW post."

        now_ts = time.time()
        created_utc = post.get("created_utc", now_ts)
        age_minutes = (now_ts - created_utc) / 60.0

        if age_minutes < self.min_age_m:
            return False, f"Too young ({age_minutes:.1f}m < {self.min_age_m}m)."
        if age_minutes > self.max_age_m:
            return False, f"Too old ({age_minutes:.1f}m > {self.max_age_m}m)."

        num_comments = post.get("num_comments", 999)
        if num_comments > self.max_comments:
            return False, f"Too crowded ({num_comments} > {self.max_comments} comments)."

        score = post.get("score", 0)
        if score < self.min_upvotes:
            return False, f"Low score ({score} < {self.min_upvotes})."

        title = post.get("title", "").lower()
        if self.skip_serious and ("[serious]" in title or "serious replies only" in title):
            return False, "Tagged as [Serious]."

        for keyword in self.blacklist:
            if keyword in title:
                return False, f"Matches blacklist keyword: '{keyword}'."

        return True, "Qualified"

    def scan_subreddit(self, session: Any, subreddit_name: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Scans a subreddit's top-hour feed for top candidate opportunities."""
        candidates = []

        try:
            # 1. Scan Top Hour (reliable JSON feed containing all recent 1-hour rising posts)
            raw_posts = session.fetch_feed(subreddit_name, feed="top_hour", limit=limit)
            for post in raw_posts:
                ok, reason = self.is_qualified(post)
                if ok:
                    age_m = max(1.0, (time.time() - post["created_utc"]) / 60.0)
                    momentum = post["score"] / age_m
                    candidates.append({
                        "id": post["id"],
                        "title": post["title"],
                        "selftext": post.get("selftext", ""),
                        "subreddit": subreddit_name,
                        "score": post["score"],
                        "num_comments": post["num_comments"],
                        "age_minutes": round(age_m, 1),
                        "momentum": round(momentum, 3),
                        "url": f"https://reddit.com{post.get('permalink', '')}"
                    })

        except Exception as e:
            print(f"  [Hunter] Error scanning r/{subreddit_name}: {e}")

        # Sort descending by momentum
        candidates.sort(key=lambda x: x["momentum"], reverse=True)
        return candidates
