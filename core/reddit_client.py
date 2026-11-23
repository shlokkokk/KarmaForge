"""
KarmaForge Reddit Client
Uses curl-backed engine to cleanly bypass Reddit's Fastly TLS 403 firewall.
Authenticates via Browser Session Cookie (reddit_session).
"""

from __future__ import annotations

import os
import re
import json
import time
import subprocess
from typing import Dict, Optional, List, Tuple, Any

USER_AGENT_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

def get_reddit_base_url() -> str:
    return os.environ.get("REDDIT_PROXY_URL", "").strip().rstrip("/") or "https://old.reddit.com"

def curl_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, str]] = None,
    session_cookie: Optional[str] = None,
    modhash: Optional[str] = None,
    proxy_url: Optional[str] = None
) -> Tuple[int, str]:
    """Executes an HTTP request via system curl to preserve modern TLS/HTTP2 fingerprints."""
    curl_bin = "curl.exe" if os.name == "nt" else "curl"
    base_url = (proxy_url or get_reddit_base_url()).strip().rstrip("/")
    cmd = [
        curl_bin, "-s", "-L", "--compressed",
        "-A", USER_AGENT_BROWSER,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Sec-Fetch-Dest: document",
        "-H", "Sec-Fetch-Mode: navigate",
        "-H", "Sec-Fetch-Site: none",
        "-H", "Upgrade-Insecure-Requests: 1"
    ]

    if session_cookie:
        clean_cookie = session_cookie.replace("\r", "").replace("\n", "").strip('"').strip("'").strip()
        cmd.extend(["-b", f"reddit_session={clean_cookie}"])

    if method == "POST":
        cmd.extend(["-X", "POST"])
        if modhash:
            cmd.extend(["-H", f"X-Modhash: {modhash}"])
        cmd.extend(["-H", f"Origin: {base_url}"])
        cmd.extend(["-H", f"Referer: {base_url}/"])
        if data:
            for k, v in data.items():
                cmd.extend(["-d", f"{k}={v}"])

    cmd.append(url)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (200 if res.stdout else 500), res.stdout
    except Exception as e:
        return 500, str(e)


class RedditSessionCookieClient:
    """Authenticates directly via browser session cookie (reddit_session)."""

    def __init__(self, username: str, session_cookie: str, proxy_url: Optional[str] = None):
        self.username = username
        self.session_cookie = session_cookie.strip()
        self.proxy_url = (proxy_url or get_reddit_base_url()).strip().rstrip("/")
        self.modhash: Optional[str] = None
        self.cooldown_until: float = 0.0
        self.comment_karma: int = 0
        self.link_karma: int = 0

    def is_on_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def get_remaining_cooldown(self) -> int:
        return max(0, int(self.cooldown_until - time.time()))

    def verify_auth(self) -> Tuple[bool, str, Dict[str, int]]:
        """Validates the session cookie against /api/me.json and grabs modhash + karma."""
        url = f"{self.proxy_url}/api/me.json"
        try:
            status, stdout = curl_request(url, method="GET", session_cookie=self.session_cookie, proxy_url=self.proxy_url)
            if not stdout:
                return False, "Empty response from Reddit.", {}

            try:
                data = json.loads(stdout).get("data", {})
            except Exception as je:
                preview = stdout[:250].replace("\n", " ").replace("\r", "")
                return False, f"JSON parse error ({je}): Status {status}, Body: {preview}", {}

            real_username = data.get("name")
            if not real_username:
                preview = stdout[:250].replace("\n", " ").replace("\r", "")
                return False, f"Invalid or expired session cookie. Body: {preview}", {}

            self.modhash = data.get("modhash", "")
            self.comment_karma = data.get("comment_karma", 0)
            self.link_karma = data.get("link_karma", 0)

            return True, f"Authenticated as /u/{real_username}", {
                "comment_karma": self.comment_karma,
                "link_karma": self.link_karma
            }
        except Exception as e:
            return False, f"Session verification failed: {e}", {}

    def fetch_feed(self, subreddit: str, feed: str = "rising", limit: int = 25) -> List[Dict[str, Any]]:
        """Pulls posts directly from Reddit JSON feed."""
        base_url = self.proxy_url
        if feed == "top_hour":
            url = f"{base_url}/r/{subreddit}/top.json?t=hour&limit={limit}"
        else:
            url = f"{base_url}/r/{subreddit}/rising.json?limit={limit}"

        try:
            status, stdout = curl_request(url, method="GET", session_cookie=self.session_cookie, proxy_url=self.proxy_url)
            if not stdout:
                return []

            data = json.loads(stdout)
            children = data.get("data", {}).get("children", [])
            posts = []
            for child in children:
                cdata = child.get("data", {})
                posts.append({
                    "id": cdata.get("id"),
                    "title": cdata.get("title", ""),
                    "selftext": cdata.get("selftext", ""),
                    "subreddit": subreddit,
                    "score": cdata.get("score", 0),
                    "num_comments": cdata.get("num_comments", 0),
                    "created_utc": cdata.get("created_utc", time.time()),
                    "locked": cdata.get("locked", False),
                    "archived": cdata.get("archived", False),
                    "over_18": cdata.get("over_18", False),
                    "permalink": cdata.get("permalink", "")
                })
            return posts
        except Exception as e:
            print(f"  [Session Client] Failed to fetch r/{subreddit} {feed}: {e}")
            return []

    def reply_to_submission(self, post_id: str, comment_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Submits a comment to a post via Reddit's web API."""
        if self.is_on_cooldown():
            return None, f"Account {self.username} is on cooldown for {self.get_remaining_cooldown()}s."

        if not self.modhash:
            self.verify_auth()

        url = f"{self.proxy_url}/api/comment"
        thing_id = f"t3_{post_id}" if not post_id.startswith("t3_") else post_id
        
        payload = {
            "api_type": "json",
            "thing_id": thing_id,
            "text": comment_text,
            "uh": self.modhash or ""
        }

        try:
            status, stdout = curl_request(
                url,
                method="POST",
                data=payload,
                session_cookie=self.session_cookie,
                modhash=self.modhash,
                proxy_url=self.proxy_url
            )
            res = json.loads(stdout)
            errors = res.get("json", {}).get("errors", [])
            if errors:
                err_code = errors[0][0] if errors[0] else "UNKNOWN"
                err_msg = errors[0][1] if len(errors[0]) > 1 else ""
                if "RATELIMIT" in err_code:
                    wait_seconds = 600
                    match = re.search(r"(\d+)\s*(second|minute)", err_msg, re.IGNORECASE)
                    if match:
                        val = int(match.group(1))
                        unit = match.group(2).lower()
                        wait_seconds = val if "second" in unit else val * 60

                    # Auto-retry once if cooldown is reasonable (up to 5 minutes / 300s)
                    if wait_seconds <= 300:
                        retry_wait = wait_seconds + 30
                        print(f"  [{self.username}] Rate-limited for {wait_seconds}s. Auto-waiting {retry_wait}s (+30s buffer) to retry...")
                        time.sleep(retry_wait)
                        status_retry, stdout_retry = curl_request(
                            url,
                            method="POST",
                            data=payload,
                            session_cookie=self.session_cookie,
                            modhash=self.modhash,
                            proxy_url=self.proxy_url
                        )
                        try:
                            res_retry = json.loads(stdout_retry)
                            errors_retry = res_retry.get("json", {}).get("errors", [])
                            if not errors_retry:
                                things_retry = res_retry.get("json", {}).get("data", {}).get("things", [])
                                if things_retry:
                                    new_cid = things_retry[0].get("data", {}).get("id", "")
                                    return new_cid.replace("t1_", ""), None
                                return "posted_ok", None
                            else:
                                err_msg = errors_retry[0][1] if len(errors_retry[0]) > 1 else err_msg
                                match2 = re.search(r"(\d+)\s*(second|minute)", err_msg, re.IGNORECASE)
                                if match2:
                                    val2 = int(match2.group(1))
                                    unit2 = match2.group(2).lower()
                                    wait_seconds = val2 if "second" in unit2 else val2 * 60
                        except Exception:
                            pass

                    self.cooldown_until = time.time() + wait_seconds + 30
                    return None, f"Rate-limited: {err_msg}"
                return None, f"Reddit error: {err_code} - {err_msg}"

            things = res.get("json", {}).get("data", {}).get("things", [])
            if things:
                new_comment_id = things[0].get("data", {}).get("id", "")
                return new_comment_id.replace("t1_", ""), None
            return "posted_ok", None

        except Exception as e:
            return None, f"Failed to post comment: {e}"

    def upvote(self, thing_id: str) -> bool:
        """Upvotes a submission or comment."""
        if not self.modhash:
            self.verify_auth()

        url = f"{self.proxy_url}/api/vote"
        full_id = f"t3_{thing_id}" if not thing_id.startswith("t") else thing_id
        payload = {"id": full_id, "dir": "1", "uh": self.modhash or ""}

        try:
            status, stdout = curl_request(
                url,
                method="POST",
                data=payload,
                session_cookie=self.session_cookie,
                modhash=self.modhash,
                proxy_url=self.proxy_url
            )
            return True
        except Exception:
            return False

    def delete_comment_by_id(self, comment_id: str) -> Tuple[bool, str]:
        """Deletes a comment."""
        if not self.modhash:
            self.verify_auth()

        url = f"{self.proxy_url}/api/del"
        full_id = f"t1_{comment_id}" if not comment_id.startswith("t1_") else comment_id
        payload = {"id": full_id, "uh": self.modhash or ""}

        try:
            status, stdout = curl_request(
                url,
                method="POST",
                data=payload,
                session_cookie=self.session_cookie,
                modhash=self.modhash,
                proxy_url=self.proxy_url
            )
            return True, "Comment deleted."
        except Exception as e:
            return False, f"Delete failed: {e}"

    def batch_get_comments(self, comment_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetches comment score inspection via user comments listing."""
        if not comment_ids:
            return []
        url = f"{self.proxy_url}/user/{self.username}/comments.json?limit=50"
        try:
            status, stdout = curl_request(url, method="GET", session_cookie=self.session_cookie, proxy_url=self.proxy_url)
            if not stdout:
                return []
            data = json.loads(stdout)
            results = []
            id_set = set(comment_ids)
            for child in data.get("data", {}).get("children", []):
                cdata = child.get("data", {})
                cid = cdata.get("id")
                clean_cid = cid.replace("t1_", "") if cid else ""
                if cid in id_set or clean_cid in id_set or f"t1_{clean_cid}" in id_set:
                    results.append({
                        "id": clean_cid or cid,
                        "score": cdata.get("score", 1),
                        "author": cdata.get("author"),
                        "created_utc": cdata.get("created_utc"),
                        "permalink": cdata.get("permalink", ""),
                        "subreddit": cdata.get("subreddit", "")
                    })
            return results
        except Exception as e:
            print(f"  [Session Client] Batch inspect error: {e}")
            return []

    def get_comment_replies_count(self, permalink: str) -> int:
        """Fetches thread slice to count direct child replies for an at-risk comment."""
        if not permalink:
            return 0
        clean_link = permalink.rstrip("/")
        url = f"{self.proxy_url}{clean_link}.json?limit=10"
        try:
            status, stdout = curl_request(url, method="GET", session_cookie=self.session_cookie, proxy_url=self.proxy_url)
            if not stdout:
                return 0
            data = json.loads(stdout)
            if isinstance(data, list) and len(data) > 1:
                comments_listing = data[1].get("data", {}).get("children", [])
                if comments_listing:
                    top_comment = comments_listing[0].get("data", {})
                    replies_data = top_comment.get("replies")
                    if isinstance(replies_data, dict):
                        children = replies_data.get("data", {}).get("children", [])
                        valid_replies = [c for c in children if c.get("kind") == "t1"]
                        return len(valid_replies)
            return 0
        except Exception as e:
            print(f"  [Session Client] Reply count fetch error: {e}")
            return 0


class RedditClientManager:
    """Unified session manager supporting Session Cookies."""

    def __init__(self):
        self.accounts: Dict[str, Any] = {}
        self._load_accounts()

    def _load_accounts(self):
        for idx in range(1, 10):
            enabled = os.environ.get(f"REDDIT_ACCOUNT_{idx}_ENABLED", "false").lower() == "true"
            if not enabled:
                continue

            username = os.environ.get(f"REDDIT_ACCOUNT_{idx}_USERNAME", "").strip()
            session_cookie = os.environ.get(f"REDDIT_ACCOUNT_{idx}_SESSION", "").strip()

            if username and session_cookie:
                proxy_url = os.environ.get(f"REDDIT_ACCOUNT_{idx}_PROXY_URL", "").strip() or None
                client = RedditSessionCookieClient(username, session_cookie, proxy_url=proxy_url)
                self.accounts[username] = client

    def get_account(self, username: str) -> Optional[Any]:
        return self.accounts.get(username)

    def get_all_accounts(self) -> List[Any]:
        return list(self.accounts.values())

    def get_active_account_names(self) -> List[str]:
        return list(self.accounts.keys())
