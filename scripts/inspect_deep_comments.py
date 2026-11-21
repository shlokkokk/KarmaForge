import json

with open("data/linguistic_analysis_report.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for cat, rep in data.items():
    print(f"\n==========================================")
    print(f"=== {cat.upper()} TOP REAL COMMENTS ===")
    print(f"==========================================")
    for i, ex in enumerate(rep["canonical_top_examples"][:4], 1):
        print(f"\n{i}. [{ex['score']} pts] (r/{ex['sub']}):")
        print(f"   Post Title: \"{ex['post_title']}\"")
        print(f"   Top Comment: \"{ex['body']}\"")
