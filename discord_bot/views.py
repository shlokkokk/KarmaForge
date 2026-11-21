"""
KarmaForge Discord Views
Interactive UI components for Control Panel and Downvote Shield.
"""

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
    """Persistent interactive Control Panel for mission control."""

    def __init__(self, bot: Any):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Live Karma", style=discord.ButtonStyle.primary, custom_id="btn_karma", row=0)
    async def btn_karma(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.reddit_manager
        embed = discord.Embed(title="Live Karma Breakdown", color=0x3498DB)
        for session in manager.get_all_accounts():
            ok, msg, karma = session.verify_auth()
            today_count = get_daily_comment_count(session.username)
            status_text = "Active" if ok else "Session Expired"
            embed.add_field(
                name=f"/u/{session.username} ({status_text})",
                value=f"Comment Karma: `{karma.get('comment_karma', 0)}`\nPost Karma: `{karma.get('link_karma', 0)}`\nToday's Comments: `{today_count}/6`",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Recent Comments", style=discord.ButtonStyle.secondary, custom_id="btn_recent", row=0)
    async def btn_recent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        recent = get_recent_comments(limit=5)
        if not recent:
            await interaction.followup.send("No comments posted yet.", ephemeral=True)
            return

        embed = discord.Embed(title="Last 5 Comments", color=0x95A5A6)
        for r in recent:
            val = f"Subreddit: r/{r['subreddit']} | Score: {r['score']} pts\n_{r['comment_text'][:120]}..._\n[Link]({r['post_url']})"
            embed.add_field(name=f"/u/{r['account_username']} • {r['posted_at']}", value=val, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Run Shield Scan", style=discord.ButtonStyle.secondary, custom_id="btn_shield", row=0)
    async def btn_shield(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "shield"):
            stats = self.bot.shield.run_check_cycle()
            await interaction.followup.send(f"Shield Scan: Checked {stats['checked']} comments. Deletions: {stats['deleted']}, Milestones: {stats['milestones']}.", ephemeral=True)
        else:
            await interaction.followup.send("Shield scan dispatched.", ephemeral=True)

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.danger, custom_id="btn_toggle", row=1)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator"):
            self.bot.operator.paused = not getattr(self.bot.operator, "paused", False)
            state = "Paused" if self.bot.operator.paused else "Resumed"
            await interaction.followup.send(f"Engine is now: **{state}**.", ephemeral=True)
        else:
            await interaction.followup.send("Operator instance not attached.", ephemeral=True)

    @discord.ui.button(label="Trigger Wave Hunt", style=discord.ButtonStyle.success, custom_id="btn_hunt", row=1)
    async def btn_hunt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator"):
            accounts = self.bot.reddit_manager.get_all_accounts()
            if accounts:
                session = accounts[0]
                await interaction.followup.send(f"Triggering hunt turn for /u/{session.username}...", ephemeral=True)
                success = self.bot.operator.execute_account_turn(session)
                msg = "Turn completed successfully." if success else "Turn finished without posting (no eligible thread or limit reached)."
                await interaction.followup.send(msg, ephemeral=True)
                return
        await interaction.followup.send("Operator not ready.", ephemeral=True)
