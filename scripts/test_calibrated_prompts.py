import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env")
from core.ai_gateway import AIGateway
from core.persona_engine import PersonaEngine

gw = AIGateway()
test_cases = [
    ("AskReddit", "What is an unspoken social rule that too many people ignore?"),
    ("mildlyinfuriating", "Someone parked their truck across 3 parking spots at Costco"),
    ("todayilearned", "TIL astronauts on the ISS have to exercise 2.5 hours a day to prevent bone density loss"),
    ("gaming", "Rockstar delays next update to focus on fixing microtransactions"),
    ("technology", "CEO says AI will completely replace software engineers within 6 months")
]

for sub, title in test_cases:
    cat, prompt = PersonaEngine.get_persona_for_subreddit(sub)
    comment = gw.generate_comment(PersonaEngine.build_comment_prompt(title, "", sub), prompt)
    print(f"[{sub} | {cat}]")
    print(f"  Comment: \"{comment}\"\n")
