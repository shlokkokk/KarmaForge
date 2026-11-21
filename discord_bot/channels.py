"""
KarmaForge Enterprise Operations Matrix
Multi-Category Discord Mission Control provisioning all monitoring,
safety, analytics, and control channels.
"""

import discord
from typing import Dict, Optional, List, Any

# Enterprise Category & Channel Taxonomy
STRUCTURE = {
    "OVERVIEW AND CONTROLS": {
        "guide": "welcome-and-guide",
        "panel": "control-panel",
        "rules": "anti-ai-heuristics"
    },
    "RADAR AND ENGAGEMENT": {
        "radar": "hunter-feed-radar",
        "activity": "comment-activity",
        "upvotes": "parent-upvotes",
        "inbox": "thread-replies"
    },
    "KARMA AND ANALYTICS": {
        "milestones": "karma-milestones",
        "daily": "daily-analytics",
        "leaderboard": "account-leaderboard"
    },
    "DOWNVOTE SHIELD AND DEFENSE": {
        "shield": "downvote-alerts",
        "deletions": "auto-deletions-audit",
        "blacklist": "subreddit-quarantine"
    },
    "SYSTEM HEALTH AND TELEMETRY": {
        "sessions": "session-health",
        "ai_brain": "ai-keypool-telemetry",
        "ratelimits": "ratelimit-monitor",
        "errors": "error-diagnostics"
    }
}

GUIDE_TEXT = """**KarmaForge Operations & Architecture Manual**

KarmaForge is an autonomous organic Reddit engagement engine engineered to build authentic comment karma (+200 to +500) without triggering spam heuristics, bot detectors, or community downvotes.

---

**Mission Control Category Breakdown:**

**1. OVERVIEW & CONTROLS**
- `#welcome-and-guide`: This complete manual, architecture specs, and recovery procedures.
- `#control-panel`: Interactive persistent control center with real-time buttons.
- `#anti-ai-heuristics`: The strict negative constraints enforced on generated comments.

**2. RADAR & ENGAGEMENT**
- `#hunter-feed-radar`: Real-time post qualification logs (momentum calculation, post age, comment counts).
- `#comment-activity`: Live embeds of every comment submitted across both accounts.
- `#parent-upvotes`: Log of natural parent post upvotes leaving organic human engagement footprints.
- `#thread-replies`: Logs when Redditors reply to our comments.

**3. KARMA & ANALYTICS**
- `#karma-milestones`: High-velocity alerts when comments cross +10, +25, +50, +100 upvotes.
- `#daily-analytics`: End-of-day karma delta and posting volume breakdown.
- `#account-leaderboard`: Head-to-head comparison between `jakee-peraltaa` and `jamieee_e`.

**4. DOWNVOTE SHIELD & DEFENSE**
- `#downvote-alerts`: Warnings when any comment drops to -1 score, featuring a one-click delete button.
- `#auto-deletions-audit`: Log of comments automatically nuked at -2 score to freeze karma bleed.
- `#subreddit-quarantine`: Subreddits temporarily blacklisted due to strict automods or locked threads.

**5. SYSTEM HEALTH & TELEMETRY**
- `#session-health`: Real-time cookie validity monitor. Pings if a cookie expires with replacement steps.
- `#ai-keypool-telemetry`: Logs Mika keypool rotation and CurioCut Groq failovers.
- `#ratelimit-monitor`: Tracks Reddit API cooldowns and pacing timers.
- `#error-diagnostics`: Full diagnostic stack traces for network drops or HTTP anomalies.
"""

HEURISTICS_TEXT = """**Enforced Anti-AI Generation Constraints**

KarmaForge enforces strict programmatic negative constraints so that every comment reads like a native Redditor:

1. **Zero Emojis**: Programmatically stripped via regex unicode filter. Reddit culture rejects emojis.
2. **Length Limit**: 1 to 2 sharp sentences max. Concise punchlines and focused questions earn the highest upvote ratios.
3. **Natural Formatting**: Contractions (`dont`, `didnt`, `im`), lowercase starts, conversational delivery.
4. **Zero Corporate Fluff**: Strictly bans corporate praise (*"Great post!", "Keep up the great work!"*).
5. **Subreddit Tone Matching**:
   - Dev & Tech (`r/programming`, `r/webdev`): Pragmatic, slightly cynical, architectural edge cases.
   - Hardware & Audio (`r/headphones`, `r/buildapc`): Build quality, clamp force, real-world buyer checks.
   - Casual Discussion (`r/AskReddit`, `r/NoStupidQuestions`): Deadpan observational wit.
   - Memes & Irony (`r/me_irl`, `r/mildlyinfuriating`): Understated sarcasm.
"""

class ChannelRouter:
    """Provisions all operational categories and channels dynamically."""

    def __init__(self):
        self.channel_map: Dict[str, discord.TextChannel] = {}

    async def ensure_categories_and_channels(self, guild: discord.Guild) -> Dict[str, discord.TextChannel]:
        # Clean up legacy single category if present
        old_cat = discord.utils.get(guild.categories, name="KARMAFORGE CONTROL")
        if old_cat:
            for ch in old_cat.text_channels:
                pass  # Keep or let new ones take precedence

        for cat_name, channel_dict in STRUCTURE.items():
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                category = await guild.create_category(cat_name)
                print(f"  [Discord] Created Category: {cat_name}")

            for key, chan_name in channel_dict.items():
                channel = discord.utils.get(guild.text_channels, name=chan_name, category=category)
                if not channel:
                    channel = await guild.create_text_channel(name=chan_name, category=category)
                    print(f"    [Discord] Created Channel: #{chan_name} in {cat_name}")
                self.channel_map[key] = channel

        # Populate guide channel
        guide_chan = self.channel_map.get("guide")
        if guide_chan:
            msgs = [m async for m in guide_chan.history(limit=5)]
            if not msgs:
                embed = discord.Embed(
                    title="KarmaForge Operations & Architecture Manual",
                    description=GUIDE_TEXT,
                    color=0x2B2D31
                )
                await guide_chan.send(embed=embed)

        # Populate heuristics channel
        rules_chan = self.channel_map.get("rules")
        if rules_chan:
            msgs = [m async for m in rules_chan.history(limit=5)]
            if not msgs:
                embed = discord.Embed(
                    title="Anti-AI Rules & Persona Specifications",
                    description=HEURISTICS_TEXT,
                    color=0x2B2D31
                )
                await rules_chan.send(embed=embed)

        return self.channel_map

    def get_channel(self, key: str) -> Optional[discord.TextChannel]:
        return self.channel_map.get(key)
