"""
KarmaForge Discord Bot
Mission Control router dispatching events to their respective dedicated categories.
"""

import os
import sys
import asyncio
from typing import Optional, Dict, Any, List

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.channels import ChannelRouter
from discord_bot.views import DeleteCommentView, ControlPanelView
from core.db import (
    get_daily_comment_count,
    get_recent_comments,
    get_active_comments
)

class KarmaForgeBot(commands.Bot):
    """Discord Bot controlling and monitoring KarmaForge operations."""

    def __init__(self, reddit_manager: Any = None, operator: Any = None, shield: Any = None):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.reddit_manager = reddit_manager
        self.operator = operator
        self.shield = shield
        self.router = ChannelRouter()

    async def setup_hook(self):
        self.add_view(ControlPanelView(bot=self))
        self.tree.add_command(app_commands.Command(name="panel", description="Post or refresh the live Control Panel", callback=self.cmd_panel))
        self.tree.add_command(app_commands.Command(name="karma", description="View live Reddit karma breakdown", callback=self.cmd_karma))
        self.tree.add_command(app_commands.Command(name="recent", description="List recent wave-riding comments", callback=self.cmd_recent))
        self.tree.add_command(app_commands.Command(name="status", description="Inspect KarmaForge engine and quota status", callback=self.cmd_status))
        self.tree.add_command(app_commands.Command(name="pause", description="Pause autonomous wave-riding", callback=self.cmd_pause))
        self.tree.add_command(app_commands.Command(name="resume", description="Resume autonomous wave-riding", callback=self.cmd_resume))

    async def on_ready(self):
        print(f"\n[Discord] Connected as: {self.user.name} ({self.user.id})")
        for guild in self.guilds:
            print(f"  [Discord] Initializing guild: {guild.name}")
            channels = await self.router.ensure_categories_and_channels(guild)

            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"  [Discord] Synced slash commands to {guild.name}")
            except Exception as e:
                print(f"  [Discord] Slash sync error: {e}")

            panel_chan = channels.get("panel")
            if panel_chan:
                try:
                    await panel_chan.purge(limit=10)
                except Exception:
                    pass

                embed = discord.Embed(
                    title="Reddit Bot Control Panel",
                    description=(
                        "Click any button below to check account karma, view recent comments, "
                        "post immediately, or pause the bot."
                    ),
                    color=0x2B2D31
                )
                embed.add_field(
                    name="Slash Commands",
                    value="`/karma` - View karma\n`/recent` - View last 5 comments\n`/status` - Check limits & timer\n`/pause` - Pause bot\n`/resume` - Resume bot",
                    inline=False
                )
                await panel_chan.send(embed=embed, view=ControlPanelView(bot=self))

    async def cmd_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Reddit Bot Control Panel",
            description=(
                "**Action Row**:\n"
                "- `Post: Jake` - Drops comment on /u/jakee-peraltaa\n"
                "- `Post: Jamie` - Drops comment on /u/jamieee_e\n"
                "- `Post: Both Accounts` - Drops Jake now, waits 2m, drops Jamie\n\n"
                "Click any button below to trigger posts or inspect account stats."
            ),
            color=0x2B2D31
        )
        panel_chan = self.router.get_channel("panel")
        if panel_chan:
            try:
                await panel_chan.purge(limit=5)
            except Exception:
                pass
            await panel_chan.send(embed=embed, view=ControlPanelView(bot=self))
            await interaction.followup.send("Control Panel refreshed in #control-panel!", ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, view=ControlPanelView(bot=self), ephemeral=False)

    async def cmd_karma(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not self.reddit_manager:
            from core.reddit_client import RedditClientManager
            self.reddit_manager = RedditClientManager()

        embed = discord.Embed(title="Live Karma Breakdown", color=0x3498DB)
        for session in self.reddit_manager.get_all_accounts():
            ok, msg, karma = session.verify_auth()
            today_count = get_daily_comment_count(session.username)
            status_text = "Active" if ok else "Session Expired"
            embed.add_field(
                name=f"/u/{session.username} ({status_text})",
                value=f"Comment Karma: `{karma.get('comment_karma', 0)}`\nPost Karma: `{karma.get('link_karma', 0)}`\nToday's Comments: `{today_count}/6`",
                inline=False
            )
        await interaction.followup.send(embed=embed)

    async def cmd_recent(self, interaction: discord.Interaction):
        await interaction.response.defer()
        recent = get_recent_comments(limit=5)
        if not recent:
            await interaction.followup.send("No comments recorded yet.")
            return

        embed = discord.Embed(title="Last 5 Comments", color=0x95A5A6)
        for r in recent:
            val = f"Subreddit: r/{r['subreddit']} | Score: {r['score']} pts\n_{r['comment_text'][:120]}..._\n[Open on Reddit]({r['post_url']})"
            embed.add_field(name=f"/u/{r['account_username']} • {r['posted_at']}", value=val, inline=False)
        await interaction.followup.send(embed=embed)

    async def cmd_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_shield = get_active_comments()
        paused = getattr(self.operator, "paused", False) if self.operator else False
        embed = discord.Embed(title="Engine Status", color=0x2ECC71)
        embed.add_field(name="Engine State", value="Paused" if paused else "Running", inline=True)
        embed.add_field(name="Downvote Shield", value=f"{len(active_shield)} comments monitored", inline=True)
        embed.add_field(name="Circadian Sleep", value="00:30 - 08:30 local time", inline=False)
        await interaction.followup.send(embed=embed)

    async def cmd_pause(self, interaction: discord.Interaction):
        if self.operator:
            self.operator.paused = True
            await interaction.response.send_message("Autonomous wave-riding paused.")
        else:
            await interaction.response.send_message("Operator not attached.")

    async def cmd_resume(self, interaction: discord.Interaction):
        if self.operator:
            self.operator.paused = False
            await interaction.response.send_message("Autonomous wave-riding resumed.")
        else:
            await interaction.response.send_message("Operator not attached.")

    # Category 2: Radar & Engagement Event Dispatchers
    async def log_radar(self, subreddit: str, candidate_title: str, age_m: float, comments_count: int, momentum: float, qualified: bool, reason: str):
        chan = self.router.get_channel("radar")
        if chan:
            color = 0x2ECC71 if qualified else 0x95A5A6
            embed = discord.Embed(title=f"Radar Scan: r/{subreddit}", color=color)
            embed.add_field(name="Post Title", value=candidate_title[:200], inline=False)
            embed.add_field(name="Metrics", value=f"Age: `{age_m:.1f}m` | Comments: `{comments_count}` | Velocity: `{momentum:.3f}`", inline=True)
            embed.add_field(name="Result", value=f"{'Target Selected' if qualified else 'Skipped (' + reason + ')'}", inline=True)
            await chan.send(embed=embed)

    async def log_activity(self, username: str, subreddit: str, post_title: str, comment_text: str, post_url: str, persona: str):
        chan = self.router.get_channel("activity")
        if chan:
            embed = discord.Embed(title=f"New Comment Posted by /u/{username}", color=0xE67E22)
            embed.add_field(name="Subreddit", value=f"r/{subreddit}", inline=True)
            embed.add_field(name="Persona", value=persona, inline=True)
            embed.add_field(name="Title", value=post_title[:250], inline=False)
            embed.add_field(name="Comment", value=f"_{comment_text}_", inline=False)
            embed.add_field(name="Link", value=f"[Open Discussion]({post_url})", inline=False)
            await chan.send(embed=embed)

    async def log_upvote(self, username: str, post_title: str, post_url: str):
        chan = self.router.get_channel("upvotes")
        if chan:
            embed = discord.Embed(title=f"Parent Thread Upvoted by /u/{username}", color=0xE67E22)
            embed.add_field(name="Thread", value=f"[{post_title[:200]}]({post_url})", inline=False)
            await chan.send(embed=embed)

    # Category 3: Karma & Analytics Event Dispatchers
    async def log_milestone(self, username: str, comment_text: str, score: int, post_url: str):
        chan = self.router.get_channel("milestones")
        if chan:
            embed = discord.Embed(title=f"Karma Milestone: +{score} Upvotes", color=0x2ECC71)
            embed.add_field(name="Account", value=f"/u/{username}", inline=True)
            embed.add_field(name="Score", value=f"+{score} points", inline=True)
            embed.add_field(name="Comment", value=f"_{comment_text[:250]}_", inline=False)
            embed.add_field(name="Link", value=f"[Open on Reddit]({post_url})", inline=False)
            await chan.send(embed=embed)

    # Category 4: Downvote Shield & Defense Event Dispatchers
    async def log_shield_warning(self, username: str, comment_id: str, score: int, comment_text: str, post_url: str):
        chan = self.router.get_channel("shield")
        if chan:
            embed = discord.Embed(title=f"Downvote Alert: {score} pts (/u/{username})", description="Negative score warning. Action required or comment will auto-delete at -2.", color=0xF39C12)
            embed.add_field(name="Comment Text", value=f"_{comment_text[:200]}_", inline=False)
            embed.add_field(name="Link", value=f"[View Thread]({post_url})", inline=False)
            view = DeleteCommentView(comment_id=comment_id, account_username=username, reddit_manager=self.reddit_manager)
            await chan.send(embed=embed, view=view)

    async def log_auto_deletion(self, username: str, comment_id: str, score: int, comment_text: str, post_url: str):
        chan = self.router.get_channel("deletions")
        if chan:
            embed = discord.Embed(title=f"Auto-Deletion Executed: {score} pts", description=f"Comment by /u/{username} hit threshold. Automatically deleted from Reddit to protect karma.", color=0xE74C3C)
            embed.add_field(name="Deleted Comment", value=f"_{comment_text[:200]}_", inline=False)
            embed.add_field(name="Thread Link", value=f"[View Thread]({post_url})", inline=False)
            await chan.send(embed=embed)

    async def log_quarantine(self, subreddit: str, reason: str):
        chan = self.router.get_channel("blacklist")
        if chan:
            embed = discord.Embed(title=f"Subreddit Quarantined: r/{subreddit}", description=f"Reason: {reason}. Blacklisted for 24 hours.", color=0xE74C3C)
            await chan.send(embed=embed)

    # Category 5: System Health & Telemetry Event Dispatchers
    async def log_session_alert(self, username: str, status: str, details: str):
        chan = self.router.get_channel("sessions")
        if chan:
            embed = discord.Embed(title=f"Session Health: /u/{username} - {status}", description=details, color=0xE74C3C if status == "EXPIRED" else 0x2ECC71)
            await chan.send(embed=embed)

    async def log_ai_telemetry(self, tier: str, model: str, status: str, failover: bool = False):
        chan = self.router.get_channel("ai_brain")
        if chan:
            color = 0xF39C12 if failover else 0x3498DB
            embed = discord.Embed(title=f"AI Telemetry: {tier} ({model})", description=f"Status: {status}\nFailover: {failover}", color=color)
            await chan.send(embed=embed)

    async def log_ratelimit(self, username: str, wait_seconds: int):
        chan = self.router.get_channel("ratelimits")
        if chan:
            embed = discord.Embed(title=f"Reddit Rate-Limit Triggered (/u/{username})", description=f"Cooling down for {wait_seconds} seconds before resuming actions.", color=0xF39C12)
            await chan.send(embed=embed)

    async def log_error(self, title: str, error_trace: str):
        chan = self.router.get_channel("errors")
        if chan:
            embed = discord.Embed(title=f"Error Diagnostic: {title}", description=f"```{error_trace[:1500]}```", color=0xE74C3C)
            await chan.send(embed=embed)
