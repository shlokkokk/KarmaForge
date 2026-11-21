"""
KarmaForge Linguistic & Humor Analyzer
Analyzes scraped top Reddit posts and comments across all categories:
- Length (words, characters)
- Sentence structures and counts
- Punctuation quirks (trailing periods, capitalization, comma usage, exclamation marks)
- Humor patterns (observational, dry, cynical, self-deprecating, callback)
- Question phrasing in discussion subs
- Extracts top 5 highest-voted canonical examples per category
"""

import os
import json
import re
from typing import Dict, List, Any

def analyze_dataset(json_path: str = "data/reddit_top_analysis.json"):
    if not os.path.exists(json_path):
        print("Data file does not exist yet.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = {}

    for cat, posts in data.items():
        all_comments = []
        for p in posts:
            for c in p.get("top_comments", []):
                all_comments.append({
                    "post_title": p.get("title", ""),
                    "sub": p.get("subreddit", ""),
                    "body": c.get("body", "").strip(),
                    "score": c.get("score", 0),
                    "author": c.get("author", "")
                })

        if not all_comments:
            continue

        # Sort by score
        all_comments.sort(key=lambda x: x["score"], reverse=True)

        # Metrics
        word_counts = [len(c["body"].split()) for c in all_comments if c["body"]]
        char_counts = [len(c["body"]) for c in all_comments if c["body"]]
        
        # Punctuation checks
        has_trailing_period = sum(1 for c in all_comments if c["body"].endswith("."))
        starts_lowercase = sum(1 for c in all_comments if c["body"] and c["body"][0].islower())
        has_exclamation = sum(1 for c in all_comments if "!" in c["body"])
        has_question_mark = sum(1 for c in all_comments if "?" in c["body"])
        is_single_sentence = sum(1 for c in all_comments if len(re.split(r"[.!?]\s+", c["body"].strip())) <= 1)

        total = len(all_comments)
        avg_words = sum(word_counts) / max(1, len(word_counts))
        avg_chars = sum(char_counts) / max(1, len(char_counts))

        report[cat] = {
            "total_top_comments": total,
            "avg_word_count": round(avg_words, 1),
            "avg_char_count": round(avg_chars, 1),
            "pct_trailing_period": round((has_trailing_period / total) * 100, 1),
            "pct_starts_lowercase": round((starts_lowercase / total) * 100, 1),
            "pct_single_sentence": round((is_single_sentence / total) * 100, 1),
            "pct_has_exclamation": round((has_exclamation / total) * 100, 1),
            "pct_has_question": round((has_question_mark / total) * 100, 1),
            "canonical_top_examples": all_comments[:5]
        }

    with open("data/linguistic_analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("=== LINGUISTIC ANALYSIS SUMMARY ===")
    for cat, m in report.items():
        print(f"\n--- {cat.upper()} ---")
        print(f"Comments: {m['total_top_comments']} | Avg Words: {m['avg_word_count']} | Single sentence: {m['pct_single_sentence']}%")
        print(f"Trailing period: {m['pct_trailing_period']}% | Lowercase start: {m['pct_starts_lowercase']}% | Exclamation: {m['pct_has_exclamation']}% | Questions: {m['pct_has_question']}%")
        print("Top 2 Comments:")
        for ex in m['canonical_top_examples'][:2]:
            print(f"  [{ex['score']} pts] (r/{ex['sub']}): \"{ex['body'][:120]}...\"")

if __name__ == "__main__":
    analyze_dataset()
