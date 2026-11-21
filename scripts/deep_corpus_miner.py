"""
Deep Corpus Miner & Linguistic Learning Pipeline
Collects real top comments from the past 1-3 months across all 31 configured subreddits.
Analyzes syntax, sentence length, capitalization, punctuation, emotional tone, and opening hooks.
Produces structured playbook JSONs and calibration data for KarmaForge's PersonaEngine.
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

PROXY_BASE = os.getenv("REDDIT_PROXY_URL", "https://karmaforge.44idgaf44.workers.dev")
SESSION_COOKIE = os.getenv("REDDIT_ACCOUNT_1_SESSION") or os.getenv("REDDIT_ACCOUNT_2_SESSION", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Cookie": f"reddit_session={SESSION_COOKIE}"
}

ALL_SUBREDDITS = [
    # Massive Discussion
    "AskReddit", "NoStupidQuestions", "CasualConversation", "explainlikeimfive", "tooafraidtoask", "Advice",
    # Viral Humor & Relatable
    "me_irl", "mildlyinfuriating", "Showerthoughts", "funny", "memes", "facepalm", "clevercomebacks", "wholesomememes",
    # Curiosity & Facts
    "todayilearned", "Damnthatsinteresting", "mildlyinteresting", "interestingasfuck", "LifeProTips",
    # Gaming & Entertainment
    "gaming", "pcmasterrace", "pcgaming", "movies", "television", "Steam",
    # Tech & Dev
    "technology", "gadgets", "ProgrammerHumor", "programming", "webdev", "buildapc"
]

def make_request(url: str, retries: int = 3, delay: float = 1.5) -> Optional[Any]:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
            else:
                time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return None

def clean_comment_text(text: str) -> str:
    # Unescape common html entities
    text = text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    return text.strip()

def analyze_comment_syntax(body: str) -> Dict[str, Any]:
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    cleaned = " ".join(lines)
    
    # Word count
    words = cleaned.split()
    word_count = len(words)
    
    # Sentence count
    sentences = [s for s in re.split(r'[.!?]+', cleaned) if s.strip()]
    sentence_count = max(1, len(sentences))
    
    # Capitalization: starts with lowercase?
    first_char = cleaned[0] if cleaned else ""
    starts_lowercase = first_char.islower()
    
    # Punctuation: ends without period?
    ends_without_period = not cleaned.endswith((".", "!", "?"))
    
    # Dialogue style?
    has_dialogue = bool(re.search(r'["\'].*["\']', cleaned)) or (":" in cleaned and "\n" in body)
    
    # Quote reply?
    has_quote = body.startswith(">") or "\n>" in body
    
    # Common opening hook words
    first_two_words = " ".join(words[:2]).lower() if len(words) >= 2 else cleaned.lower()
    
    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "starts_lowercase": starts_lowercase,
        "ends_without_period": ends_without_period,
        "has_dialogue": has_dialogue,
        "has_quote": has_quote,
        "first_two_words": first_two_words
    }

def mine_subreddit(subreddit: str, target_posts: int = 8) -> Dict[str, Any]:
    print(f"\n[Mining] Starting r/{subreddit} (Past 1-3 Months Top Posts)...")
    
    # Fetch top posts for the month
    url = f"{PROXY_BASE}/r/{subreddit}/top.json?t=month&limit={target_posts}"
    data = make_request(url)
    
    if not data or "data" not in data or "children" not in data["data"]:
        # Fallback to t=year if month is sparse
        url = f"{PROXY_BASE}/r/{subreddit}/top.json?t=year&limit={target_posts}"
        data = make_request(url)
        
    if not data or "data" not in data or "children" not in data["data"]:
        print(f"  [Warning] Failed to fetch top posts for r/{subreddit}")
        return {}

    posts = data["data"]["children"]
    collected_comments = []
    
    for p_idx, post_obj in enumerate(posts, 1):
        p_data = post_obj.get("data", {})
        post_id = p_data.get("id")
        post_title = p_data.get("title", "")
        post_score = p_data.get("score", 0)
        
        if not post_id:
            continue
            
        time.sleep(0.8) # polite delay
        
        # Fetch comments for this top post
        c_url = f"{PROXY_BASE}/r/{subreddit}/comments/{post_id}.json?limit=15&depth=1"
        c_data = make_request(c_url)
        
        if not c_data or not isinstance(c_data, list) or len(c_data) < 2:
            continue
            
        c_children = c_data[1].get("data", {}).get("children", [])
        
        for c_obj in c_children:
            d = c_obj.get("data", {})
            body = d.get("body", "")
            author = d.get("author", "")
            score = d.get("score", 0)
            
            # Filter auto-moderators, bot notices, deleted, or low-score comments
            if (not body or 
                author.lower() in ("automoderator", "deleted", "[deleted]") or 
                body in ("[deleted]", "[removed]") or 
                score < 100 or 
                "I am a bot" in body or 
                "Please review the rules" in body):
                continue
                
            cleaned = clean_comment_text(body)
            syntax = analyze_comment_syntax(cleaned)
            
            collected_comments.append({
                "id": d.get("id"),
                "post_id": post_id,
                "post_title": post_title,
                "post_score": post_score,
                "author": author,
                "score": score,
                "body": cleaned,
                **syntax
            })
            
        print(f"  Processed post {p_idx}/{len(posts)}: [{post_id}] - {len(collected_comments)} qualifying comments total")

    if not collected_comments:
        print(f"  [Warning] No qualifying comments mined for r/{subreddit}")
        return {}

    # Sort comments by score descending
    collected_comments.sort(key=lambda x: x["score"], reverse=True)
    
    # Statistical analysis
    total = len(collected_comments)
    median_words = sorted([c["word_count"] for c in collected_comments])[total // 2]
    median_sentences = sorted([c["sentence_count"] for c in collected_comments])[total // 2]
    lowercase_ratio = round(sum(1 for c in collected_comments if c["starts_lowercase"]) / total, 3)
    no_period_ratio = round(sum(1 for c in collected_comments if c["ends_without_period"]) / total, 3)
    dialogue_ratio = round(sum(1 for c in collected_comments if c["has_dialogue"]) / total, 3)
    quote_ratio = round(sum(1 for c in collected_comments if c["has_quote"]) / total, 3)
    
    # Top 5 exemplar comments
    exemplars = []
    for c in collected_comments[:5]:
        exemplars.append({
            "score": c["score"],
            "post_title": c["post_title"],
            "body": c["body"],
            "words": c["word_count"],
            "sentences": c["sentence_count"]
        })
        
    summary = {
        "subreddit": subreddit,
        "sample_size": total,
        "median_words": median_words,
        "median_sentences": median_sentences,
        "lowercase_ratio": lowercase_ratio,
        "no_period_ratio": no_period_ratio,
        "dialogue_ratio": dialogue_ratio,
        "quote_ratio": quote_ratio,
        "top_exemplars": exemplars,
        "raw_comments": collected_comments[:25] # keep top 25
    }
    
    # Save individual subreddit dataset
    os.makedirs("data/corpus", exist_ok=True)
    with open(f"data/corpus/{subreddit}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    print(f"  [Complete] r/{subreddit}: {total} top comments mined. Median words: {median_words}, Lowercase: {lowercase_ratio*100}%, No period: {no_period_ratio*100}%")
    return summary

def main():
    print("=" * 70)
    print("KarmaForge Deep Linguistic Mining Engine - All 31 Subreddits")
    print("=" * 70)
    
    all_summaries = {}
    
    for idx, sub in enumerate(ALL_SUBREDDITS, 1):
        print(f"\nProgress: Subreddit {idx}/{len(ALL_SUBREDDITS)} ({sub})")
        res = mine_subreddit(sub, target_posts=6)
        if res:
            all_summaries[sub] = res
        time.sleep(1.0)
        
    # Save unified summary
    with open("data/corpus_unified_summary.json", "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2, ensure_ascii=False)
        
    print("\n" + "=" * 70)
    print(f"Mining Finished! Successfully processed {len(all_summaries)}/{len(ALL_SUBREDDITS)} subreddits.")
    print("=" * 70)

if __name__ == "__main__":
    main()
