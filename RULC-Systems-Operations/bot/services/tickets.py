from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING, Literal

import discord

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)

TicketStep = Literal["open", "claimed", "closed"]

TICKET_STEP_EMOJI: dict[TicketStep, str] = {
    "open": "🟢",
    "claimed": "🟡",
    "closed": "🔴",
}

DEFAULT_NAME_TEMPLATE = "・{step}・{category}-{number}"

LEGACY_TEMPLATES = frozenset({"ticket-{number}", "{category}-{number}"})


def slugify_category(name: str) -> str:
    slug = name.strip().lower().replace(" ", "-")
    slug = re.sub(r"[^\w\-а-яё]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80] or "ticket"


def normalize_name_template(template: str | None) -> str:
    raw = (template or DEFAULT_NAME_TEMPLATE).strip()
    if raw in LEGACY_TEMPLATES:
        return DEFAULT_NAME_TEMPLATE
    return raw


def build_ticket_channel_name(
    *,
    category_name: str,
    ticket_number: int,
    template: str,
    step: TicketStep,
    opener_name: str,
) -> str:
    category_slug = slugify_category(category_name)
    user_slug = slugify_category(opener_name)[:12]
    step_emoji = TICKET_STEP_EMOJI[step]
    name = (
        normalize_name_template(template)
        .replace("{step}", step_emoji)
        .replace("{category}", category_slug)
        .replace("{number}", str(ticket_number))
        .replace("{user}", user_slug)
        .replace("{id}", "0000")
    )
    return name[:100]


def parse_ticket_number_from_topic(topic: str | None) -> int | None:
    if not topic:
        return None
    match = re.search(r"#(\d+)", topic)
    return int(match.group(1)) if match else None


class TicketService:
    def __init__(self, bot: RoleSyncBot) -> None:
        self.bot = bot

    async def is_staff(self, member: discord.Member, guild_id: int) -> bool:
        if member.guild_permissions.manage_channels:
            return True
        if member.id in self.bot.settings.config_discord_ids:
            return True
        staff_roles = await self.bot.db.list_ticket_staff_roles(guild_id)
        return any(r.id in staff_roles for r in member.roles)

    async def can_access_ticket(
        self, member: discord.Member, ticket: dict, *, staff_ok: bool = True
    ) -> bool:
        if ticket["opener_id"] == member.id:
            return True
        if staff_ok and await self.is_staff(member, ticket["guild_id"]):
            return True
        return False

    async def _category_name(self, ticket: dict) -> str:
        if ticket.get("category_id"):
            row = await self.bot.db.get_ticket_category(int(ticket["category_id"]))
            if row:
                return str(row["name"])
        return str(ticket.get("subject") or "ticket")

    async def _ticket_number(self, ticket: dict, channel: discord.TextChannel | None = None) -> int:
        if ticket.get("ticket_number"):
            return int(ticket["ticket_number"])
        if channel and channel.topic:
            parsed = parse_ticket_number_from_topic(channel.topic)
            if parsed is not None:
                return parsed
        return int(ticket["id"])

    async def rename_ticket_channel(
        self,
        channel: discord.TextChannel,
        ticket: dict,
        step: TicketStep,
    ) -> None:
        config = await self.bot.db.get_ticket_config(channel.guild.id)
        template = normalize_name_template(str(config["name_template"]))
        category_name = await self._category_name(ticket)
        ticket_number = await self._ticket_number(ticket, channel)
        opener_name = str(ticket.get("opener_name") or "user")

        new_name = build_ticket_channel_name(
            category_name=category_name,
            ticket_number=ticket_number,
            template=template,
            step=step,
            opener_name=opener_name,
        )
        if channel.name == new_name:
            return
        try:
            await channel.edit(name=new_name, reason=f"Ticket status → {step}")
        except discord.HTTPException:
            logger.exception("Failed to rename ticket channel %s", channel.id)

    def _channel_overwrites(
        self,
        guild: discord.Guild,
        opener: discord.Member,
        staff_role_ids: list[int],
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            opener: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            ),
        }
        for role_id in staff_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )
        return overwrites

    async def open_ticket(
        self,
        interaction: discord.Interaction,
        category_id: int,
    ) -> discord.TextChannel | None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return None

        guild = interaction.guild
        config = await self.bot.db.get_ticket_config(guild.id)
        category_row = await self.bot.db.get_ticket_category(category_id)
        if not category_row or category_row["guild_id"] != guild.id:
            await interaction.followup.send("Категория не найдена.", ephemeral=True)
            return None

        open_count = await self.bot.db.count_open_tickets(guild.id, interaction.user.id)
        max_open = int(config["max_open_per_user"])
        if open_count >= max_open:
            await interaction.followup.send(
                f"У вас уже **{open_count}** открытых тикетов (лимит: **{max_open}**).",
                ephemeral=True,
            )
            return None

        discord_category = None
        if config["discord_category_id"]:
            discord_category = guild.get_channel(int(config["discord_category_id"]))

        ticket_num = await self.bot.db.next_ticket_number(guild.id)
        template = normalize_name_template(str(config["name_template"]))
        channel_name = build_ticket_channel_name(
            category_name=str(category_row["name"]),
            ticket_number=ticket_num,
            template=template,
            step="open",
            opener_name=interaction.user.display_name or interaction.user.name,
        )

        staff_roles = await self.bot.db.list_ticket_staff_roles(guild.id)
        overwrites = self._channel_overwrites(guild, interaction.user, staff_roles)

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=discord_category if isinstance(discord_category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                topic=f"Тикет #{ticket_num} · {interaction.user} · {category_row['name']}",
                reason=f"Ticket opened by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Нет прав создать канал. Проверьте права бота.",
                ephemeral=True,
            )
            return None
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Ошибка создания канала: {exc}", ephemeral=True)
            return None

        ticket_id = await self.bot.db.create_ticket(
            guild_id=guild.id,
            category_id=category_id,
            channel_id=channel.id,
            opener_id=interaction.user.id,
            opener_name=str(interaction.user),
            subject=category_row["name"],
            ticket_number=ticket_num,
        )

        embed = await self.bot.embeds.ticket_welcome_embed(
            guild,
            ticket_id=ticket_id,
            ticket_number=ticket_num,
            category=category_row,
            opener=interaction.user,
        )
        from bot.ui.ticket_views import TicketControlView

        await channel.send(
            content=f"{interaction.user.mention}"
            + (" " + " ".join(f"<@&{r}>" for r in staff_roles) if staff_roles else ""),
            embed=embed,
            view=TicketControlView(self.bot),
        )
        await interaction.followup.send(
            f"✅ Тикет создан: {channel.mention}",
            ephemeral=True,
        )
        return channel

    async def build_transcript(self, channel: discord.TextChannel) -> str:
        lines = [f"=== Transcript: #{channel.name} ===", ""]
        try:
            async for message in channel.history(limit=500, oldest_first=True):
                ts = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                author = f"{message.author} ({message.author.id})"
                content = message.content or ""
                if message.embeds and not content:
                    content = "[embed]"
                if message.attachments:
                    names = ", ".join(a.filename for a in message.attachments)
                    content = (content + f" [attachments: {names}]").strip()
                lines.append(f"[{ts}] {author}: {content}")
        except discord.Forbidden:
            lines.append("[could not read history]")
        return "\n".join(lines)

    async def close_ticket_channel(
        self,
        interaction: discord.Interaction,
        ticket: dict,
        *,
        reason: str,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return

        channel = interaction.channel
        await self.rename_ticket_channel(channel, ticket, "closed")

        transcript = await self.build_transcript(channel)
        await self.bot.db.close_ticket(
            int(ticket["id"]),
            closed_by_id=interaction.user.id,
            reason=reason,
            transcript=transcript,
        )

        config = await self.bot.db.get_ticket_config(interaction.guild.id)
        log_channel_id = config["log_channel_id"]
        category_row = None
        if ticket["category_id"]:
            category_row = await self.bot.db.get_ticket_category(int(ticket["category_id"]))

        log_embed = await self.bot.embeds.ticket_closed_embed(
            interaction.guild,
            ticket=ticket,
            ticket_number=channel.name,
            category=category_row,
            closed_by=interaction.user,
            reason=reason,
        )

        transcript_file = discord.File(
            io.BytesIO(transcript.encode("utf-8")),
            filename=f"transcript-{channel.name}.txt",
        )

        if log_channel_id:
            log_ch = interaction.guild.get_channel(int(log_channel_id))
            if isinstance(log_ch, discord.TextChannel):
                try:
                    await log_ch.send(embed=log_embed, file=transcript_file)
                except discord.HTTPException:
                    logger.exception("Failed to send ticket log")

        await interaction.followup.send(embed=log_embed, ephemeral=False)

        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}: {reason}")
        except discord.HTTPException:
            logger.exception("Failed to delete ticket channel %s", channel.id)

    async def post_panel(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
    ) -> discord.Message:
        embed = await self.bot.embeds.ticket_panel_embed(guild)
        from bot.ui.ticket_views import TicketPanelView

        view = await TicketPanelView.build(self.bot, guild.id)
        message = await channel.send(embed=embed, view=view)
        await self.bot.db.update_ticket_config(
            guild.id,
            panel_channel_id=channel.id,
            panel_message_id=message.id,
        )
        self.bot.add_view(view)
        return message

    async def register_persistent_views(self) -> None:
        from bot.ui.ticket_views import TicketControlView, TicketPanelView

        self.bot.add_view(TicketControlView(self.bot))
        rows = await self.bot.db.guilds_with_ticket_panels()
        for row in rows:
            try:
                view = await TicketPanelView.build(self.bot, int(row["guild_id"]))
                self.bot.add_view(view)
            except Exception:
                logger.exception("Ticket panel view restore failed for guild %s", row["guild_id"])
