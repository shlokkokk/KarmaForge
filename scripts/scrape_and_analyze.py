"""
KarmaForge Deep Reddit Scraper & Pattern Analyzer
Fetches top posts of the month and their top comments across all 5 core categories.
Saves structured dataset for deep linguistic and humor analysis.
"""

import os
import json
import time
import subprocess
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv(".env")
USER_AGENT_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

SESSION_COOKIE = os.getenv("REDDIT_ACCOUNT_1_SESSION", "").strip()

CATEGORIES = {
    "massive_discussion": ["AskReddit", "NoStupidQuestions", "CasualConversation"],
    "viral_humor_relatable": ["me_irl", "mildlyinfuriating", "showerthoughts", "funny"],
    "curiosity_and_facts": ["todayilearned", "Damnthatsinteresting", "mildlyinteresting"],
    "gaming_and_entertainment": ["gaming", "pcmasterrace", "movies"],
    "tech_and_dev": ["technology", "ProgrammerHumor", "buildapc"]
}

def curl_fetch(url: str) -> str:
    cmd = ["curl.exe", "-s", "-A", USER_AGENT_BROWSER]
    if SESSION_COOKIE:
        cmd.extend(["-b", f"reddit_session={SESSION_COOKIE}"])
    cmd.append(url)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout if res.stdout else ""
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def scrape_category(category_name: str, subreddits: List[str]) -> List[Dict[str, Any]]:
    print(f"\n=== Scraping Category: {category_name} ===")
    results = []
    
    for sub in subreddits:
        print(f"Fetching r/{sub} top of month...")
        feed_url = f"https://old.reddit.com/r/{sub}/top.json?t=month&limit=6"
        feed_raw = curl_fetch(feed_url)
        if not feed_raw:
            print(f"Failed to fetch feed for r/{sub}")
            continue
            
        try:
            feed_data = json.loads(feed_raw)
            posts = feed_data.get("data", {}).get("children", [])
        except Exception as e:
            print(f"JSON decode error on r/{sub}: {e}")
            continue

        for p in posts:
            post_data = p.get("data", {})
            post_id = post_data.get("id")
            title = post_data.get("title", "")
            score = post_data.get("score", 0)
            num_comments = post_data.get("num_comments", 0)
            
            if not post_id:
                continue

            # Fetch top comments
            comm_url = f"https://old.reddit.com/r/{sub}/comments/{post_id}.json?sort=top&limit=8"
            comm_raw = curl_fetch(comm_url)
            comments_extracted = []
            
            if comm_raw:
                try:
                    comm_json = json.loads(comm_raw)
                    if isinstance(comm_json, list) and len(comm_json) > 1:
                        comment_children = comm_json[1].get("data", {}).get("children", [])
                        for c in comment_children:
                            c_data = c.get("data", {})
                            body = c_data.get("body", "")
                            c_score = c_data.get("score", 0)
                            c_author = c_data.get("author", "")
                            if body and c_author not in ["[deleted]", "AutoModerator"]:
                                comments_extracted.append({
                                    "body": body,
                                    "score": c_score,
                                    "author": c_author
                                })
                except Exception as e:
                    print(f"Error parsing comments for post {post_id}: {e}")

            results.append({
                "subreddit": sub,
                "category": category_name,
                "post_id": post_id,
                "title": title,
                "post_score": score,
                "num_comments": num_comments,
                "top_comments": comments_extracted[:5]
            })
            time.sleep(1.0) # Polite delay
            
    return results

def main():
    os.makedirs("data", exist_ok=True)
    all_data = {}
    
    for cat, subs in CATEGORIES.items():
        cat_results = scrape_category(cat, subs)
        all_data[cat] = cat_results
        
    with open("data/reddit_top_analysis.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nScraping complete. Total categories saved: {len(all_data)}")
    for cat, items in all_data.items():
        total_comms = sum(len(x.get("top_comments", [])) for x in items)
        print(f" - {cat}: {len(items)} posts, {total_comms} top comments collected")

if __name__ == "__main__":
    main()
