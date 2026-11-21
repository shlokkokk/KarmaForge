"""
KarmaForge Discord Views
Interactive UI components for Control Panel and comment deletion.
"""

import time
import random
import asyncio
from datetime import datetime
from typing import Any, Optional
import discord
from core.db import (
    update_comment_score,
    get_daily_comment_count,
    get_recent_comments,
    get_active_comments
)

class ConfirmDeleteView(discord.ui.View):
    """Confirmation prompt before permanently deleting a comment from Reddit."""

    def __init__(self, comment_id: str, account_username: str, reddit_manager: Any = None, original_message: Optional[discord.Message] = None, original_view: Optional[discord.ui.View] = None):
        super().__init__(timeout=60)
        self.comment_id = comment_id
        self.account_username = account_username
        self.reddit_manager = reddit_manager
        self.original_message = original_message
        self.original_view = original_view

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, custom_id="btn_confirm_del")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
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
            if self.original_message and self.original_view:
                for child in self.original_view.children:
                    if isinstance(child, discord.ui.Button) and child.label in ["Delete Comment", "Delete Comment Now"]:
                        child.disabled = True
                        child.label = "Deleted from Reddit"
                        child.style = discord.ButtonStyle.secondary
                try:
                    await self.original_message.edit(view=self.original_view)
                except Exception:
                    pass
            await interaction.followup.send(f"Comment `{self.comment_id}` by /u/{self.account_username} was permanently deleted from Reddit.", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to delete comment: {msg}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="btn_cancel_del")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Comment deletion cancelled.", view=None)


class ConfirmActionView(discord.ui.View):
    """Reusable confirmation view for actions that post or change state."""

    def __init__(self, action_description: str, on_confirm_callback, confirm_label: str = "Confirm", confirm_style: discord.ButtonStyle = discord.ButtonStyle.danger):
        super().__init__(timeout=60)
        self.action_description = action_description
        self.on_confirm_callback = on_confirm_callback
        confirm_btn = discord.ui.Button(label=confirm_label, style=confirm_style, custom_id="btn_action_confirm")
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="btn_action_cancel")
        confirm_btn.callback = self._confirm_callback
        cancel_btn.callback = self._cancel_callback
        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

    async def _confirm_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=f"Confirmed: {self.action_description}. Starting...", view=None)
        await self.on_confirm_callback(interaction)

    async def _cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=f"Cancelled: {self.action_description}.", view=None)


class DeleteCommentButton(discord.ui.Button):
    """Emergency deletion button attached to comment embeds."""

    def __init__(self, comment_id: str, account_username: str, reddit_manager: Any = None):
        super().__init__(label="Delete Comment", style=discord.ButtonStyle.danger, custom_id=f"del_{comment_id[:30]}")
        self.comment_id = comment_id
        self.account_username = account_username
        self.reddit_manager = reddit_manager

    async def callback(self, interaction: discord.Interaction):
        view = ConfirmDeleteView(
            comment_id=self.comment_id,
            account_username=self.account_username,
            reddit_manager=self.reddit_manager,
            original_message=interaction.message,
            original_view=self.view
        )
        await interaction.response.send_message(
            f"Are you sure you want to permanently delete this comment by /u/{self.account_username} from Reddit?",
            view=view,
            ephemeral=True
        )


class CommentActionView(discord.ui.View):
    """Renders a direct clickable 'Open on Reddit' button and an optional Delete button."""

    def __init__(self, comment_url: str, comment_id: Optional[str] = None, account_username: Optional[str] = None, reddit_manager: Any = None):
        super().__init__(timeout=None)
        if comment_url:
            self.add_item(discord.ui.Button(label="Open on Reddit", url=comment_url, style=discord.ButtonStyle.link))
        if comment_id and account_username:
            self.add_item(DeleteCommentButton(comment_id=comment_id, account_username=account_username, reddit_manager=reddit_manager))


class DeleteCommentView(discord.ui.View):
    """Button allowing one-click deletion of downvoted comments."""

    def __init__(self, comment_id: str, account_username: str, reddit_manager: Any = None):
        super().__init__(timeout=86400)
        self.comment_id = comment_id
        self.account_username = account_username
        self.reddit_manager = reddit_manager

    @discord.ui.button(label="Delete Comment Now", style=discord.ButtonStyle.danger, custom_id="delete_btn")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmDeleteView(
            comment_id=self.comment_id,
            account_username=self.account_username,
            reddit_manager=self.reddit_manager,
            original_message=interaction.message,
            original_view=self
        )
        await interaction.response.send_message(
            f"Are you sure you want to delete downvoted comment `{self.comment_id}` by /u/{self.account_username} from Reddit?",
            view=view,
            ephemeral=True
        )


class ControlPanelView(discord.ui.View):
    """Clean, comprehensive Control Panel with individual and dual posting triggers."""

    def __init__(self, bot: Any):
        super().__init__(timeout=None)
        self.bot = bot

    # ==========================================
    # ROW 0: POSTING TRIGGERS (INDIVIDUAL & BOTH)
    # ==========================================

    @discord.ui.button(label="Post: Jake", style=discord.ButtonStyle.success, custom_id="btn_post_jake", row=0)
    async def btn_post_jake(self, interaction: discord.Interaction, button: discord.ui.Button):
        async def on_confirm(inter: discord.Interaction):
            await self._trigger_single_account(inter, "jakee-peraltaa")

        view = ConfirmActionView(
            action_description="Post comment for /u/jakee-peraltaa",
            on_confirm_callback=on_confirm,
            confirm_label="Confirm Post",
            confirm_style=discord.ButtonStyle.success
        )
        await interaction.response.send_message(
            "Are you sure you want to trigger an immediate comment for **/u/jakee-peraltaa**?",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Post: Jamie", style=discord.ButtonStyle.success, custom_id="btn_post_jamie", row=0)
    async def btn_post_jamie(self, interaction: discord.Interaction, button: discord.ui.Button):
        async def on_confirm(inter: discord.Interaction):
            await self._trigger_single_account(inter, "jamieee_e")

        view = ConfirmActionView(
            action_description="Post comment for /u/jamieee_e",
            on_confirm_callback=on_confirm,
            confirm_label="Confirm Post",
            confirm_style=discord.ButtonStyle.success
        )
        await interaction.response.send_message(
            "Are you sure you want to trigger an immediate comment for **/u/jamieee_e**?",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Post: Both Accounts", style=discord.ButtonStyle.primary, custom_id="btn_post_both", row=0)
    async def btn_post_both(self, interaction: discord.Interaction, button: discord.ui.Button):
        async def on_confirm(inter: discord.Interaction):
            await self._trigger_both_accounts(inter)

        view = ConfirmActionView(
            action_description="Post comments on both accounts",
            on_confirm_callback=on_confirm,
            confirm_label="Confirm Both Posts",
            confirm_style=discord.ButtonStyle.primary
        )
        await interaction.response.send_message(
            "Are you sure you want to trigger immediate comments for **both accounts** in this round?",
            view=view,
            ephemeral=True
        )

    async def _trigger_both_accounts(self, interaction: discord.Interaction):
        if not (hasattr(self.bot, "operator") and self.bot.operator):
            await interaction.followup.send("Bot operator is initializing.", ephemeral=True)
            return

        manager = self.bot.reddit_manager
        acc1 = manager.get_account("jakee-peraltaa")
        acc2 = manager.get_account("jamieee_e")

        targets = [a for a in [acc1, acc2] if a and not a.is_on_cooldown() and get_daily_comment_count(a.username) < 6]
        if not targets:
            await interaction.followup.send("Both accounts have reached today's 6-comment limit or are on cooldown.", ephemeral=True)
            return

        names = ", ".join(f"/u/{a.username}" for a in targets)
        await interaction.followup.send(f"Starting dual-account round for {names}. Second post will drop in ~2 minutes.", ephemeral=True)

        async def run_dual_round():
            for idx, session in enumerate(targets):
                self.bot.operator.execute_account_turn(session)
                if idx < len(targets) - 1:
                    await asyncio.sleep(random.uniform(120, 180))

        asyncio.create_task(run_dual_round())

    async def _trigger_single_account(self, interaction: discord.Interaction, username: str):
        if not (hasattr(self.bot, "operator") and self.bot.operator):
            await interaction.followup.send("Bot operator is initializing.", ephemeral=True)
            return

        session = self.bot.reddit_manager.get_account(username)
        if not session:
            await interaction.followup.send(f"Account /u/{username} not found in manager.", ephemeral=True)
            return

        if session.is_on_cooldown():
            await interaction.followup.send(f"/u/{username} is on a Reddit cooldown ({session.get_remaining_cooldown()}s remaining).", ephemeral=True)
            return

        daily_count = get_daily_comment_count(username)
        if daily_count >= 6:
            await interaction.followup.send(f"/u/{username} has reached today's limit ({daily_count}/6). Resting.", ephemeral=True)
            return

        await interaction.followup.send(f"Scanning rising posts for /u/{username}...", ephemeral=True)
        success, msg = self.bot.operator.execute_account_turn(session)
        if success:
            await interaction.followup.send(f"Success: {msg} Check the activity channel.", ephemeral=True)
        else:
            await interaction.followup.send(f"Pass complete for /u/{username}: {msg}", ephemeral=True)

    # ==========================================
    # ROW 1: KARMA & LIMIT TELEMETRY
    # ==========================================

    @discord.ui.button(label="Check Karma", style=discord.ButtonStyle.primary, custom_id="btn_karma", row=1)
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

    @discord.ui.button(label="Recent Comments", style=discord.ButtonStyle.secondary, custom_id="btn_recent", row=1)
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

    @discord.ui.button(label="Daily Limit", style=discord.ButtonStyle.secondary, custom_id="btn_quota", row=1)
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

    @discord.ui.button(label="Account Health", style=discord.ButtonStyle.secondary, custom_id="btn_health", row=1)
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
    # ROW 2: CONTROLS & SAFETY
    # ==========================================

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.danger, custom_id="btn_toggle", row=2)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (hasattr(self.bot, "operator") and self.bot.operator):
            await interaction.response.send_message("Operator not attached.", ephemeral=True)
            return

        is_paused = getattr(self.bot.operator, "paused", False)
        target_action = "RESUME" if is_paused else "PAUSE"

        async def on_confirm(inter: discord.Interaction):
            self.bot.operator.paused = not is_paused
            state = "PAUSED" if self.bot.operator.paused else "RUNNING"
            await inter.followup.send(f"Engine is now: **{state}**.", ephemeral=True)

        view = ConfirmActionView(
            action_description=f"{target_action.lower()} the engine",
            on_confirm_callback=on_confirm,
            confirm_label=f"Confirm {target_action}",
            confirm_style=discord.ButtonStyle.danger if target_action == "PAUSE" else discord.ButtonStyle.success
        )
        await interaction.response.send_message(
            f"Are you sure you want to **{target_action}** autonomous scheduling?",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Check Downvotes", style=discord.ButtonStyle.secondary, custom_id="btn_shield", row=2)
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

    @discord.ui.button(label="Next Run Timer", style=discord.ButtonStyle.secondary, custom_id="btn_timer", row=2)
    async def btn_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if hasattr(self.bot, "operator") and self.bot.operator:
            is_sleep = self.bot.operator.is_in_circadian_rest()
            p = "PAUSED" if self.bot.operator.paused else "RUNNING"
            rem_mins = int(max(0, self.bot.operator.next_cycle_at - time.time()) // 60)
            msg = (
                f"**Bot State**: `{p}`\n"
                f"**Next Auto-Scan**: in ~{rem_mins} minutes\n"
                f"**Night Sleep (00:30-08:30)**: `{'Sleeping now' if is_sleep else 'Active hours'}`"
            )
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.followup.send("Operator not attached.", ephemeral=True)

    # ==========================================
    # ROW 3: UTILITIES
    # ==========================================

    @discord.ui.button(label="Test AI Reply", style=discord.ButtonStyle.secondary, custom_id="btn_test_ai", row=3)
    async def btn_test_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from core.ai_gateway import AIGateway
        from core.persona_engine import PersonaEngine

        gw = AIGateway()
        cat, prompt = PersonaEngine.get_persona_for_subreddit("AskReddit")

        telemetry_cb = None
        if hasattr(self.bot, "create_ai_telemetry_session"):
            t_session = self.bot.create_ai_telemetry_session("AskReddit", "What is an unspoken rule of life?")
            if t_session:
                def on_step(status: str, detail: str, is_final: bool = False, success: bool = True, output_preview: str = ""):
                    asyncio.create_task(t_session.update(status, detail, is_final, success, output_preview))
                telemetry_cb = on_step

        test_comment = gw.generate_comment(
            PersonaEngine.build_comment_prompt("What is an unspoken rule of life?", "", "AskReddit"),
            prompt,
            telemetry_cb=telemetry_cb
        )
        await interaction.followup.send(f"Test Reply Generated:\n> \"{test_comment}\"\n\nLive telemetry card posted in `#ai-keypool-telemetry`.", ephemeral=True)

    @discord.ui.button(label="Refresh Panel", style=discord.ButtonStyle.primary, custom_id="btn_refresh_panel", row=3)
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
                "Click any button below to trigger posts, check stats, or pause the bot."
            ),
            color=0x2B2D31
        )
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("Panel refreshed.", ephemeral=True)
