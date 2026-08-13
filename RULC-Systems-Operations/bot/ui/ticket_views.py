from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import discord

from bot.services.tickets import make_transcript_files

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)


class CloseTicketModal(discord.ui.Modal, title="Закрытие тикета"):
    reason = discord.ui.TextInput(
        label="Причина закрытия",
        placeholder="Кратко опишите итог…",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, bot: RoleSyncBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket or ticket["status"] != "open":
            await interaction.response.send_message("Тикет не найден или уже закрыт.", ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            return
        ticket_dict = dict(ticket)
        if not await self.bot.tickets.can_access_ticket(member, ticket_dict):
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return
        if not await self.bot.tickets.can_close_ticket(member, ticket_dict):
            await interaction.response.send_message(
                "Закрыть тикет может только staff.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await self.bot.tickets.close_ticket_channel(
            interaction,
            ticket_dict,
            reason=str(self.reason.value),
        )


class OpenTicketModal(discord.ui.Modal, title="Новый тикет"):
    details = discord.ui.TextInput(
        label="Суть обращения",
        placeholder="Кратко опишите проблему или вопрос…",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, bot: RoleSyncBot, category_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.category_id = category_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        note = str(self.details.value).strip() or None
        await self.bot.tickets.open_ticket(interaction, self.category_id, user_note=note)


class TicketControlView(discord.ui.View):
    def __init__(self, bot: RoleSyncBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def _ticket(self, interaction: discord.Interaction) -> dict | None:
        if not interaction.channel:
            return None
        row = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not row or row["status"] != "open":
            if interaction.response.is_done():
                await interaction.followup.send("Тикет закрыт или не найден.", ephemeral=True)
            else:
                await interaction.response.send_message("Тикет закрыт или не найден.", ephemeral=True)
            return None
        return dict(row)

    @discord.ui.button(
        label="Закрыть",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close",
        row=0,
    )
    async def close_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        ticket = await self._ticket(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not await self.bot.tickets.can_access_ticket(interaction.user, ticket):
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return
        if not await self.bot.tickets.can_close_ticket(interaction.user, ticket):
            await interaction.response.send_message(
                "Закрыть тикет может только staff.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(CloseTicketModal(self.bot))

    @discord.ui.button(
        label="Взять",
        style=discord.ButtonStyle.primary,
        emoji="✋",
        custom_id="ticket:claim",
        row=0,
    )
    async def claim_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        ticket = await self._ticket(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not await self.bot.tickets.is_staff(interaction.user, ticket["guild_id"]):
            await interaction.response.send_message("Только для staff.", ephemeral=True)
            return
        if ticket.get("claimed_by_id"):
            if ticket.get("claimed_by_id") == interaction.user.id:
                await interaction.response.send_message("Вы уже взяли этот тикет.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Тикет уже в работе у <@{ticket['claimed_by_id']}>.",
                    ephemeral=True,
                )
            return

        ok = await self.bot.db.claim_ticket(int(ticket["id"]), interaction.user.id)
        if not ok:
            fresh = await self.bot.db.get_ticket(int(ticket["id"]))
            claimer = fresh["claimed_by_id"] if fresh else None
            msg = (
                f"Тикет уже взял <@{claimer}>."
                if claimer
                else "Не удалось взять тикет."
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return
        ticket["claimed_by_id"] = interaction.user.id
        if isinstance(interaction.channel, discord.TextChannel):
            await self.bot.tickets.rename_ticket_channel(interaction.channel, ticket, "claimed")
            await self.bot.tickets.update_welcome_embed(
                interaction.channel, ticket, claimed_by=interaction.user
            )
        await interaction.response.send_message(
            f"✋ {interaction.user.mention} взял тикет в работу.",
        )

    @discord.ui.button(
        label="Отпустить",
        style=discord.ButtonStyle.secondary,
        emoji="↩",
        custom_id="ticket:unclaim",
        row=0,
    )
    async def unclaim_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        ticket = await self._ticket(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        claimer_id = ticket.get("claimed_by_id")
        if not claimer_id:
            await interaction.response.send_message("Тикет ещё не взят.", ephemeral=True)
            return
        is_claimer = interaction.user.id == claimer_id
        is_admin = await self.bot.tickets.is_staff(interaction.user, ticket["guild_id"])
        if not is_claimer and not is_admin:
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return
        ok = await self.bot.db.unclaim_ticket(int(ticket["id"]))
        if not ok:
            await interaction.response.send_message("Не удалось отпустить тикет.", ephemeral=True)
            return
        ticket["claimed_by_id"] = None
        if isinstance(interaction.channel, discord.TextChannel):
            await self.bot.tickets.rename_ticket_channel(interaction.channel, ticket, "open")
            await self.bot.tickets.update_welcome_embed(interaction.channel, ticket, claimed_by=None)
        await interaction.response.send_message("↩ Тикет снова ожидает staff.")

    @discord.ui.button(
        label="Транскрипт",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        custom_id="ticket:transcript",
        row=1,
    )
    async def transcript_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self._ticket(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not await self.bot.tickets.can_access_ticket(interaction.user, ticket):
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        result = await self.bot.tickets.build_transcript(interaction.channel)
        text = result.text
        if len(text) <= 1900:
            note = (
                f"\n\n⚠️ Показаны первые {result.message_count} сообщений."
                if result.truncated
                else ""
            )
            await interaction.followup.send(f"```\n{text[:1900]}\n```{note}", ephemeral=True)
        else:
            files = make_transcript_files(text, f"transcript-{interaction.channel.name}")
            note = " ⚠️ Обрезано." if result.truncated else ""
            await interaction.followup.send(f"📋 Транскрипт:{note}", files=files, ephemeral=True)

    @discord.ui.button(
        label="Помощь",
        style=discord.ButtonStyle.secondary,
        emoji="❔",
        custom_id="ticket:help",
        row=1,
    )
    async def help_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "**Кнопки:** 🔒 закрыть · ✋ взять · ↩ отпустить · 📋 транскрипт\n\n"
            "**Команды:**\n"
            "`/ticket добавить` — участник\n"
            "`/ticket убрать` — убрать (staff)\n"
            "`/ticket закрыть` — закрыть с причиной",
            ephemeral=True,
        )


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot: RoleSyncBot, guild_id: int, categories: list) -> None:
        self.bot = bot
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label=c["name"][:100],
                value=str(c["id"]),
                description=(c["description"] or "")[:100] or None,
                emoji=c["emoji"] if c["emoji"] else None,
            )
            for c in categories[:25]
        ]
        if not options:
            options = [
                discord.SelectOption(
                    label="Нет категорий",
                    value="_none",
                    description="Настройте через /ticket",
                )
            ]
        super().__init__(
            placeholder="📂 Выберите тему обращения…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"ticket:open:{guild_id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "_none":
            await interaction.response.send_message(
                "Категории не настроены. Обратитесь к администрации.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            OpenTicketModal(self.bot, int(self.values[0]))
        )


class TicketPanelView(discord.ui.View):
    def __init__(self, bot: RoleSyncBot, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @classmethod
    async def build(cls, bot: RoleSyncBot, guild_id: int) -> TicketPanelView:
        view = cls(bot, guild_id)
        categories = await bot.db.list_ticket_categories(guild_id, enabled_only=True)
        view.add_item(TicketCategorySelect(bot, guild_id, categories))
        return view
