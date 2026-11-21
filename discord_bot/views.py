"""
KarmaForge Discord Views
Interactive UI components for Control Panel and comment deletion.
"""

import time
from datetime import datetime
from typing import Any, Optional
import discord
from core.db import (
    update_comment_score,
    get_daily_comment_count,
    get_recent_comments,
    get_active_comments
)

class DeleteCommentView(discord.ui.View):
    """Button allowing one-click deletion of downvoted comments."""

    def __init__(self, comment_id: str, account_username: str, reddit_manager: Any = None):
        super().__init__(timeout=86400)
        self.comment_id = comment_id
        self.account_username = account_username
        self.reddit_manager = reddit_manager

    @discord.ui.button(label="Delete Comment Now", style=discord.ButtonStyle.danger, custom_id="delete_btn")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        if not self.reddit_manager:
            from core.reddit_client import RedditClientManager
            self.reddit_manager = RedditClientManager()

        session = self.reddit_manager.get_account(self.account_username)
        if not session:
            await interaction.followup.send(f"Account session for /u/{self.account_username} not found.", ephemeral=True)
            return

        success, msg = session.delete_comment_by_id(self.comment_id)
        if success:
            update_comment_score(self.comment_id, score=-99, deleted=True)
            button.disabled = True
            button.label = "Comment Deleted"
            button.style = discord.ButtonStyle.secondary
            await interaction.message.edit(view=self)
            await interaction.followup.send(f"Comment `{self.comment_id}` by /u/{self.account_username} was deleted from Reddit.")
        else:
            await interaction.followup.send(f"Failed to delete comment: {msg}", ephemeral=True)


class ControlPanelView(discord.ui.View):
    """Simple, clean Control Panel with practical, normal buttons."""

    def __init__(self, bot: Any):
        super().__init__(timeout=None)
        self.bot = bot

    # ==========================================
    # ROW 0: ACCOUNT & COMMENT STATS
    # ==========================================

    @discord.ui.button(label="Check Karma", style=discord.ButtonStyle.primary, custom_id="btn_karma", row=0)
    async def btn_karma(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.reddit_manager
        if not manager:
            from core.reddit_client import RedditClientManager
            manager = RedditClientManager()
            self.bot.reddit_manager = manager

        embed = discord.Embed(title="Account Karma Breakdown", color=0x3498DB)
        for session in manager.get_all_accounts():
            ok, msg, karma = session.verify_auth()
            today_count = get_daily_comment_count(session.username)
            status_text = "Working" if ok else f"Login Failed ({msg})"
            embed.add_field(
                name=f"/u/{session.username} [{status_text}]",
                value=(
                    f"Comment Karma: **{karma.get('comment_karma', 0)}**\n"
                    f"Post Karma: **{karma.get('link_karma', 0)}**\n"
                    f"Comments Posted Today: `{today_count}/6`"
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Recent Comments", style=discord.ButtonStyle.secondary, custom_id="btn_recent", row=0)
    async def btn_recent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        recent = get_recent_comments(limit=6)
        if not recent:
            await interaction.followup.send("No comments posted yet.", ephemeral=True)
            return

        embed = discord.Embed(title="Last Comments Posted", color=0x2B2D31)
        for r in recent:
            val = (
                f"Subreddit: `r/{r['subreddit']}` | Score: **{r['score']} pts**\n"
                f"> \"{r['comment_text'][:120]}\"\n"
                f"[Link to Post]({r['post_url']})"
            )
            embed.add_field(name=f"/u/{r['account_username']} • {r['posted_at']}", value=val, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Daily Limit", style=discord.ButtonStyle.secondary, custom_id="btn_quota", row=0)
    async def btn_quota(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.reddit_manager
        accounts = manager.get_all_accounts() if manager else []
        embed = discord.Embed(title="Daily Comments (6 per account max)", color=0x1ABC9C)
        for acc in accounts:
            c = get_daily_comment_count(acc.username)
            rem = max(0, 6 - c)
            embed.add_field(
                name=f"/u/{acc.username}",
                value=f"Posted: `{c}/6` | Left: `{rem}`",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Account Health", style=discord.ButtonStyle.secondary, custom_id="btn_health", row=0)
    async def btn_health(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.reddit_manager
        accounts = manager.get_all_accounts() if manager else []
        embed = discord.Embed(title="Reddit Login Check", color=0x9B59B6)
        for acc in accounts:
            ok, msg, karma = acc.verify_auth()
            embed.add_field(
                name=f"/u/{acc.username}",
                value=f"Login Status: `{'Valid' if ok else 'Expired'}`\nDetails: {msg}",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # ROW 1: ACTIONS & CONTROLS
    # ==========================================

    @discord.ui.button(label="Post Comment Now", style=discord.ButtonStyle.success, custom_id="btn_hunt", row=1)
    async def btn_hunt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator") and self.bot.operator:
            accounts = self.bot.reddit_manager.get_all_accounts()
            available = [a for a in accounts if not a.is_on_cooldown() and get_daily_comment_count(a.username) < 6]
            if not available:
                await interaction.followup.send("All accounts have either reached today's 6-comment limit or are cooling down.", ephemeral=True)
                return

            # Pick account with lowest daily comments
            available.sort(key=lambda a: get_daily_comment_count(a.username))
            session = available[0]

            await interaction.followup.send(f"Scanning rising posts for /u/{session.username}...", ephemeral=True)
            success = self.bot.operator.execute_account_turn(session)
            if success:
                msg = f"Comment posted by /u/{session.username}! Check the category channel."
            else:
                msg = "Scan finished. No rising posts met qualification criteria on this pass."
            await interaction.followup.send(msg, ephemeral=True)
            return
        await interaction.followup.send("Bot operator is starting up or paused.", ephemeral=True)

    @discord.ui.button(label="Check Downvotes", style=discord.ButtonStyle.secondary, custom_id="btn_shield", row=1)
    async def btn_shield(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "shield") and self.bot.shield:
            stats = self.bot.shield.run_check_cycle()
            await interaction.followup.send(
                f"Downvote Check Done:\n- Checked: `{stats['checked']}` comments\n- Auto-Deleted (score <= -2): `{stats['deleted']}`\n- Good comments (+10+ pts): `{stats['milestones']}`",
                ephemeral=True
            )
        else:
            await interaction.followup.send("Downvote checker is initializing.", ephemeral=True)

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.danger, custom_id="btn_toggle", row=1)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator") and self.bot.operator:
            self.bot.operator.paused = not getattr(self.bot.operator, "paused", False)
            state = "PAUSED" if self.bot.operator.paused else "RUNNING"
            await interaction.followup.send(f"Bot is now: **{state}**.", ephemeral=True)
        else:
            await interaction.followup.send("Operator not attached.", ephemeral=True)

    @discord.ui.button(label="Next Run Timer", style=discord.ButtonStyle.secondary, custom_id="btn_timer", row=1)
    async def btn_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator") and self.bot.operator:
            is_sleep = self.bot.operator.is_in_circadian_rest()
            p = "PAUSED" if self.bot.operator.paused else "RUNNING"
            msg = (
                f"**Bot State**: `{p}`\n"
                f"**Night Sleep (00:30-08:30)**: `{'Sleeping now' if is_sleep else 'Active hours'}`\n"
                f"**Interval**: `45 to 115 minutes between posts`"
            )
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.followup.send("Operator not attached.", ephemeral=True)

    # ==========================================
    # ROW 2: TESTS & UTILITIES
    # ==========================================

    @discord.ui.button(label="Test AI Reply", style=discord.ButtonStyle.secondary, custom_id="btn_test_ai", row=2)
    async def btn_test_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from core.ai_gateway import AIGateway
        from core.persona_engine import PersonaEngine

        gw = AIGateway()
        cat, prompt = PersonaEngine.get_persona_for_subreddit("AskReddit")
        test_comment = gw.generate_comment(
            PersonaEngine.build_comment_prompt("What is an unspoken rule of life?", "", "AskReddit"),
            prompt
        )
        await interaction.followup.send(f"Test Reply Generated:\n> \"{test_comment}\"", ephemeral=True)

    @discord.ui.button(label="Refresh Panel", style=discord.ButtonStyle.primary, custom_id="btn_refresh_panel", row=2)
    async def btn_refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.reddit_manager
        acc_text = []
        if manager:
            for acc in manager.get_all_accounts():
                today_count = get_daily_comment_count(acc.username)
                acc_text.append(f"- **/u/{acc.username}**: `{today_count}/6` comments today")

        is_paused = getattr(self.bot.operator, "paused", False) if hasattr(self.bot, "operator") and self.bot.operator else False
        embed = discord.Embed(
            title="Reddit Bot Control Panel",
            description=(
                f"**Status**: `{'PAUSED' if is_paused else 'RUNNING'}`\n"
                f"**Updated**: <t:{int(time.time())}:R>\n\n"
                f"**Accounts**:\n" + ("\n".join(acc_text) if acc_text else "None") + "\n\n"
                "Click any button below to check stats or control the bot."
            ),
            color=0x2B2D31
        )
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("Panel refreshed.", ephemeral=True)
