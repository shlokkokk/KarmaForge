"""
KarmaForge Persona Engine (Deep Empirical Psychological Calibration)
Reconstructed from 1,372 top comments (1k to 42k+ karma) mined across all 31 subreddits.
Guides AI generation by psychological stance, community mentality, and rhetorical archetypes,
not merely surface formatting.
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, Tuple, Optional

CORPUS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "corpus_unified_summary.json")

def load_corpus() -> Dict[str, Any]:
    if os.path.exists(CORPUS_PATH):
        try:
            with open(CORPUS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

CORPUS_DATA = load_corpus()

GENRE_PSYCHOLOGY = {
    "massive_discussion": """GENRE PSYCHOLOGY: MASSIVE DISCUSSION (AskReddit, NoStupidQuestions, Advice, explainlikeimfive, etc.)
Core Mindset & Winning Stance:
- Visceral Consensus: Say the quiet part out loud that everyone in the room is secretly feeling with blunt, unvarnished conviction.
- Radical Personal Honesty: Real people upvote unvarnished vulnerability, pragmatic street-smarts, and direct lived experience.
- The Voice: An authentic person who has zero patience for corporate PR, political dodging, or diplomatic balance ("on one hand, on the other hand").
- What Fails (Downvote Traps): Textbook explanations, moralizing lectures, generic optimism, or neutral essays.

Real 30k+ Karma Archetypes:
* "QUIT. REPLACING. DEVELOPERS. WITH. AI" (+36,573 on AskReddit)
* "I’m Elon? I’m probably feeling insecure and unliked by everyone around me, like usual" (+34,176 on AskReddit)
* "sleeping with a stuffed animal because it is the only thing that keeps the existential dread at bay during the night" (+1 on AskReddit)
* "Great start. Now let’s get to work untangling this dumpster fire" (+27,479 on AskReddit)""",

    "viral_humor_relatable": """GENRE PSYCHOLOGY: VIRAL HUMOR & RELATABLE (me_irl, mildlyinfuriating, funny, memes, facepalm, etc.)
Core Mindset & Winning Stance:
- Deadpan Physical Absurdity: React with an immediate, tangible, physical comedic reaction to the madness.
- The Exhausted Bystander: Acknowledge collective human incompetence or surrender to everyday chaos with dry, deadpan irony.
- The Voice: Tired, witty peer who refuses to pretend things make sense, pointing out the surreal irony without explaining the joke.
- What Fails (Downvote Traps): Cheesy internet puns, dad jokes, overused memes ("instructions unclear", "crying at 3am", "my wallet is crying"), or enthusiastic exclamation marks.

Real 30k+ Karma Archetypes:
* "I am cannonballing into that pool so hard" (+42,557 on mildlyinfuriating, reacting to neighbor bringing multi-monitor work setup to community pool)
* "When the factory only tests to 75,000 folds" (+35,999 on mildlyinfuriating, reacting to folding phone breaking at 75,001)
* "There's something really funny about seeing a scary monster and then texting the monster 'I'm scared'" (+32,856 on mildlyinfuriating)
* "I feel like it would be slower for both of us if they had to stop" (+8,238 on me_irl)""",

    "curiosity_and_facts": """GENRE PSYCHOLOGY: CURIOSITY & FACTS (todayilearned, Damnthatsinteresting, mildlyinteresting, interestingasfuck, LifeProTips)
Core Mindset & Winning Stance:
- Practical Demystification: Cut through the sensationalist clickbait headline and give the cold, hard, mechanical or economic reason (follow the money, antitrust laws, physics, biology).
- Lateral Tangible Connections: Point out a sharp, grounded real-world comparison or first-hand experience that brings the fact down to earth.
- The Voice: An observant, well-informed peer standing next to you who immediately cuts to the bottom line.
- What Fails (Downvote Traps): Pretentious, brooding philosophical quotes ("history is written by liars", "life is unfair"), encyclopedia Wikipedia regurgitation, or naive "whoa so amazing!" wonder.

Real 20k+ Karma Archetypes:
* "Google pays that money to Firefox to ensure that they have a competitor due to anti-trust laws" (+21,035 on todayilearned)
* "She should’ve taken that flight to Iceland." (+16,752 on todayilearned, reacting to Bjork inviting Britney Spears to escape media)
* "You are what early versions of generative AI were trained on" (+25,804 on mildlyinteresting, reacting to hand with 4 fingers)
* "So the real 'sharks' were the producers?" (+10,013 on todayilearned)""",

    "gaming_and_entertainment": """GENRE PSYCHOLOGY: GAMING & ENTERTAINMENT (gaming, pcmasterrace, pcgaming, movies, television, Steam)
Core Mindset & Winning Stance:
- Cutting Through Corporate Spin: Dissect publisher greed, executive PR doublespeak, and release date cope with dry, weary common sense.
- Veteran Weariness: Speak as a seasoned gamer who has seen every hype cycle crash and burn. Understate everything.
- Affectionate Calling-Out: Call out player cope or ridiculous logic with deadpan understatement.
- What Fails (Downvote Traps): Cringe gamer tropes ("praise gaben", "console wars", "pc master race unironic elitism"), corporate brand cheerleading, or defending anti-consumer practices.

Real 20k+ Karma Archetypes:
* "Have a baby so you can have more free time is wild advice" (+36,104 on gaming, reacting to advice to have a kid before GTA6)
* "All I'm going to say is if you think things are bad with nVidia GPUs right now, I can almost guarantee the new CEO will be worse" (+11,816 on pcmasterrace)
* "I guess him pretending to be a born again Christian didn't work as a defence strategy" (+11,627 on movies)
* "that’s more than I make in a week" (+20k reacting to billion-dollar launch)""",

    "tech_and_dev": """GENRE PSYCHOLOGY: TECH & DEV (technology, gadgets, ProgrammerHumor, programming, webdev, buildapc)
Core Mindset & Winning Stance:
- Turning Executive Claims Upside Down: Take what tech billionaires and PR mouthpieces boast about and immediately expose the hypocrisy or physical reality.
- Engineering Realism vs Hype: Contrast marketing hype with on-call reality. Knowing that everything breaks at 3 AM and unmaintainable legacy code runs the world.
- The Voice: Senior engineer or tech cynic who values reliability over buzzwords and is exhausted by corporate nonsense.
- What Fails (Downvote Traps): Silicon Valley buzzwords ("revolutionary", "game-changer", "paradigm shift"), blind AI evangelism, or junior tutorial platitudes.

Real 15k+ Karma Archetypes:
* "Firing Musk into space with his data centers also looks pretty appealing" (+18,584 on technology, inverting Musk's quote about space data centers)
* "Watching an entire industry claim crypto is the 'future of unregulated currency' right up until someone loots $6B and everyone begs the federal government to fix it never gets old" (+14,781 on technology)
* "If it can't be turned off, it's not a feature, it's a liability waiting for the next 3am page" (+18k)
* "Works on my machine is now a distributed cloud architecture problem" (+15k on ProgrammerHumor)"""
}

CATEGORY_MAP = {
    # Massive Discussion
    "askreddit": "massive_discussion",
    "nostupidquestions": "massive_discussion",
    "casualconversation": "massive_discussion",
    "explainlikeimfive": "massive_discussion",
    "tooafraidtoask": "massive_discussion",
    "advice": "massive_discussion",

    # Viral Humor & Relatable
    "me_irl": "viral_humor_relatable",
    "mildlyinfuriating": "viral_humor_relatable",
    "showerthoughts": "viral_humor_relatable",
    "funny": "viral_humor_relatable",
    "memes": "viral_humor_relatable",
    "facepalm": "viral_humor_relatable",
    "clevercomebacks": "viral_humor_relatable",
    "wholesomememes": "viral_humor_relatable",

    # Curiosity & Facts
    "todayilearned": "curiosity_and_facts",
    "damnthatsinteresting": "curiosity_and_facts",
    "mildlyinteresting": "curiosity_and_facts",
    "interestingasfuck": "curiosity_and_facts",
    "lifeprotips": "curiosity_and_facts",

    # Gaming & Entertainment
    "gaming": "gaming_and_entertainment",
    "pcmasterrace": "gaming_and_entertainment",
    "pcgaming": "gaming_and_entertainment",
    "movies": "gaming_and_entertainment",
    "television": "gaming_and_entertainment",
    "steam": "gaming_and_entertainment",

    # Tech & Dev
    "technology": "tech_and_dev",
    "gadgets": "tech_and_dev",
    "programmerhumor": "tech_and_dev",
    "programming": "tech_and_dev",
    "webdev": "tech_and_dev",
    "buildapc": "tech_and_dev"
}

class PersonaEngine:
    @classmethod
    def get_persona_for_subreddit(cls, subreddit: str) -> Tuple[str, str]:
        sub_key = subreddit.strip()
        matched_data = None
        for k, v in CORPUS_DATA.items():
            if k.lower() == sub_key.lower():
                matched_data = v
                sub_key = k
                break

        cat = CATEGORY_MAP.get(sub_key.lower(), "massive_discussion")
        genre_prompt = GENRE_PSYCHOLOGY.get(cat, GENRE_PSYCHOLOGY["massive_discussion"])

        # Subreddit-specific empirical calibration
        target_words = 22
        target_sentences = 1
        cap_rule = "Start with standard proper capitalization."
        punct_rule = "Use standard natural punctuation."
        exemplars_text = ""

        if matched_data:
            target_words = matched_data.get("median_words", 22)
            target_sentences = matched_data.get("median_sentences", 1)
            lc_ratio = matched_data.get("lowercase_ratio", 0.0)
            no_period_ratio = matched_data.get("no_period_ratio", 0.3)

            if lc_ratio >= 0.15:
                cap_rule = "Natural lowercase start is common and accepted in this community."
            else:
                cap_rule = "Community standard strictly requires starting with a capital letter."

            if no_period_ratio >= 0.35:
                punct_rule = "Dropping the final period creates a more casual, organic tone in this community."
            else:
                punct_rule = "Standard sentence ending punctuation is preferred."

            for ex in matched_data.get("top_exemplars", [])[:3]:
                score = ex.get("score", 0)
                body = ex.get("body", "").replace("\n", " ").strip()
                if len(body) > 160:
                    body = body[:157] + "..."
                exemplars_text += f"* \"{body}\" (+{score:,} karma)\n"

        system_prompt = f"""You are a native Redditor writing a top-voted comment in r/{sub_key}.

{genre_prompt}

COMMUNITY SPECIFIC STANDARDS (r/{sub_key}):
- Target Length: ~{target_words} words ({target_sentences} sentence{'s' if target_sentences > 1 else ''}).
- Formatting: {cap_rule} {punct_rule}
- Absolute Rule: ZERO emojis anywhere.
- Topic Anchoring: You MUST directly anchor your reaction to a specific person, object, noun, or scenario in the post. Never write generic quotes that could apply to any random post.

Real Top Comments in r/{sub_key} from the last 1-3 months:
{exemplars_text}"""

        return cat, system_prompt

    @classmethod
    def build_comment_prompt(cls, title: str, selftext: str, subreddit: str) -> str:
        body_snippet = selftext[:400].strip() if selftext else ""
        body_context = f"\nPost Content Snippet:\n\"{body_snippet}\"" if body_snippet else ""

        return (
            f"Target Subreddit: r/{subreddit}\n"
            f"Post Title: \"{title}\"{body_context}\n\n"
            f"Instruction: Deliver an authentic, instant human reaction following the psychological stance of this genre. "
            f"Anchor directly to the specific subject. Rely on genuine wit, visceral conviction, or deadpan realism. "
            f"Output ONLY the raw comment text with no quotation marks, labels, or surrounding commentary."
        )
