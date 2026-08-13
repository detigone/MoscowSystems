from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import is_config_user

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)

ticket_group = app_commands.Group(name="ticket", description="Система тикетов поддержки")


def _is_ticket_admin(interaction: discord.Interaction) -> bool:
    bot = interaction.client
    if not isinstance(bot, commands.Bot) or not interaction.user:
        return False
    if is_config_user(bot, interaction.user.id):
        return True
    if isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.manage_guild
    return False


async def _require_ticket_admin(interaction: discord.Interaction) -> bool:
    if _is_ticket_admin(interaction):
        return True
    await interaction.response.send_message(
        "Нужны права **Manage Server** или доступ к `/config`.",
        ephemeral=True,
    )
    return False


async def _require_ticket_channel(interaction: discord.Interaction) -> dict | None:
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Команда только в канале тикета.", ephemeral=True)
        return None
    bot = interaction.client
    if not isinstance(bot, commands.Bot):
        return None
    row = await bot.db.get_ticket_by_channel(interaction.channel.id)
    if not row or row["status"] != "open":
        await interaction.response.send_message("Это не активный тикет.", ephemeral=True)
        return None
    return dict(row)


class TicketsCog(commands.Cog):
    def __init__(self, bot: RoleSyncBot) -> None:
        self.bot = bot

    @ticket_group.command(name="панель", description="Опубликовать панель создания тикетов")
    @app_commands.describe(канал="Куда отправить панель (по умолчанию текущий)")
    async def panel(
        self,
        interaction: discord.Interaction,
        канал: discord.TextChannel | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await _require_ticket_admin(interaction):
            return

        target = канал or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("Нужен текстовый канал.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        message = await self.bot.tickets.post_panel(interaction.guild, target)
        await interaction.followup.send(
            f"✅ Панель опубликована: {target.mention} · [перейти]({message.jump_url})",
            ephemeral=True,
        )

    @ticket_group.command(name="настройки", description="Текущие настройки тикетов")
    async def settings(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await _require_ticket_admin(interaction):
            return
        embed = await self.bot.embeds.ticket_settings_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_group.command(name="категория-канал", description="Discord-категория для новых тикетов")
    @app_commands.describe(категория="Категория каналов")
    async def set_discord_category(
        self,
        interaction: discord.Interaction,
        категория: discord.CategoryChannel,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            discord_category_id=категория.id,
        )
        await interaction.response.send_message(
            f"✅ Тикеты будут создаваться в **{категория.name}**.",
            ephemeral=True,
        )

    @ticket_group.command(name="канал-логов", description="Куда слать транскрипты закрытых тикетов")
    async def set_log_channel(
        self,
        interaction: discord.Interaction,
        канал: discord.TextChannel,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            log_channel_id=канал.id,
        )
        await interaction.response.send_message(f"✅ Логи: {канал.mention}", ephemeral=True)

    @ticket_group.command(name="staff-добавить", description="Роль staff для тикетов")
    async def staff_add(self, interaction: discord.Interaction, роль: discord.Role) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.add_ticket_staff_role(interaction.guild.id, роль.id)
        await interaction.response.send_message(f"✅ Staff-роль: {роль.mention}", ephemeral=True)

    @ticket_group.command(name="staff-убрать", description="Убрать staff-роль")
    async def staff_remove(self, interaction: discord.Interaction, роль: discord.Role) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        ok = await self.bot.db.remove_ticket_staff_role(interaction.guild.id, роль.id)
        msg = f"✅ Роль {роль.mention} убрана." if ok else "Роль не была в списке."
        await interaction.response.send_message(msg, ephemeral=True)

    @ticket_group.command(name="тип-добавить", description="Добавить тему в панель тикетов")
    @app_commands.describe(
        название="Название темы",
        emoji="Эмодзи",
        описание="Краткое описание",
    )
    async def type_add(
        self,
        interaction: discord.Interaction,
        название: str,
        emoji: str = "📩",
        описание: str = "",
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        cid = await self.bot.db.add_ticket_category(
            interaction.guild.id,
            название,
            emoji=emoji,
            description=описание,
        )
        if cid is None:
            await interaction.response.send_message(
                f"Тема **{название}** уже существует.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"✅ Тема **{emoji} {название}** добавлена. Обновите `/ticket панель`.",
            ephemeral=True,
        )

    @ticket_group.command(name="тип-убрать", description="Удалить тему тикетов")
    @app_commands.describe(id_темы="ID темы из /ticket настройки")
    async def type_remove(self, interaction: discord.Interaction, id_темы: int) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        ok = await self.bot.db.remove_ticket_category(interaction.guild.id, id_темы)
        await interaction.response.send_message(
            "✅ Тема удалена." if ok else "Тема не найдена.",
            ephemeral=True,
        )

    @ticket_group.command(name="статистика", description="Статистика тикетов сервера")
    async def statistics(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        stats = await self.bot.db.ticket_statistics(interaction.guild.id)
        embed = await self.bot.embeds.ticket_settings_embed(interaction.guild)
        embed.title = "📊 Статистика тикетов"
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_group.command(name="закрыть", description="Закрыть текущий тикет")
    @app_commands.describe(причина="Причина закрытия")
    async def close_cmd(
        self,
        interaction: discord.Interaction,
        причина: str,
    ) -> None:
        ticket = await _require_ticket_channel(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not await self.bot.tickets.can_access_ticket(interaction.user, ticket):
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.bot.tickets.close_ticket_channel(interaction, ticket, reason=причина)

    @ticket_group.command(name="добавить", description="Добавить участника в тикет")
    async def add_member(
        self,
        interaction: discord.Interaction,
        участник: discord.Member,
    ) -> None:
        ticket = await _require_ticket_channel(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not await self.bot.tickets.can_access_ticket(interaction.user, ticket):
            await interaction.response.send_message("Нет доступа.", ephemeral=True)
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        await channel.set_permissions(
            участник,
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True,
        )
        await interaction.response.send_message(f"✅ {участник.mention} добавлен в тикет.")

    @ticket_group.command(name="убрать", description="Убрать участника из тикета")
    async def remove_member(
        self,
        interaction: discord.Interaction,
        участник: discord.Member,
    ) -> None:
        ticket = await _require_ticket_channel(interaction)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if участник.id == ticket["opener_id"]:
            await interaction.response.send_message("Нельзя убрать автора тикета.", ephemeral=True)
            return
        if not await self.bot.tickets.is_staff(interaction.user, ticket["guild_id"]):
            await interaction.response.send_message("Только staff.", ephemeral=True)
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        await channel.set_permissions(участник, overwrite=None)
        await interaction.response.send_message(f"✅ {участник.mention} убран из тикета.")


async def setup(bot: RoleSyncBot) -> None:
    cog = TicketsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(ticket_group)
