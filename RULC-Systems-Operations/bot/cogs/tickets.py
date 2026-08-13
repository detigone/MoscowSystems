from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import is_config_user
from bot.services.tickets import make_transcript_files

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

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.TextChannel):
            return
        if await self.bot.tickets.handle_channel_deleted(channel.id):
            logger.info("Closed orphan ticket for deleted channel %s", channel.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        row = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if row and row["status"] == "open":
            await self.bot.db.touch_ticket_activity(message.channel.id)

    async def _refresh_panel_after_config(self, guild: discord.Guild) -> None:
        try:
            await self.bot.tickets.refresh_panel(guild)
        except Exception:
            logger.exception("Panel refresh failed for guild %s", guild.id)

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

    @ticket_group.command(name="лимит", description="Макс. открытых тикетов на одного пользователя")
    @app_commands.describe(количество="От 1 до 10")
    async def set_limit(
        self,
        interaction: discord.Interaction,
        количество: app_commands.Range[int, 1, 10],
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            max_open_per_user=количество,
        )
        await self.bot.tickets.refresh_panel(interaction.guild)
        await interaction.response.send_message(
            f"✅ Лимит: **{количество}** открытых тикетов на человека.",
            ephemeral=True,
        )

    @ticket_group.command(name="шаблон-имени", description="Шаблон названия канала тикета")
    @app_commands.describe(
        шаблон="Плейсхолдеры: {step} {category} {number} {user} {id}",
    )
    async def set_name_template(
        self,
        interaction: discord.Interaction,
        шаблон: str,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        tpl = шаблон.strip()
        if len(tpl) < 3 or "{" not in tpl:
            await interaction.response.send_message(
                "Шаблон слишком короткий. Пример: `・{step}・{category}-{number}`",
                ephemeral=True,
            )
            return
        await self.bot.db.update_ticket_config(interaction.guild.id, name_template=tpl)
        await interaction.response.send_message(f"✅ Шаблон: `{tpl}`", ephemeral=True)

    @ticket_group.command(
        name="автор-закрывает",
        description="Может ли автор тикета закрывать его сам",
    )
    async def set_opener_close(
        self,
        interaction: discord.Interaction,
        разрешить: bool,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            opener_can_close=int(разрешить),
        )
        label = "может" if разрешить else "не может"
        await interaction.response.send_message(
            f"✅ Автор тикета **{label}** закрывать обращение.",
            ephemeral=True,
        )

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
        await self._refresh_panel_after_config(interaction.guild)
        await interaction.response.send_message(
            f"✅ Тема **{emoji} {название}** добавлена. Панель обновлена.",
            ephemeral=True,
        )

    @ticket_group.command(name="тип-убрать", description="Удалить тему тикетов")
    @app_commands.describe(id_темы="ID темы из /ticket настройки")
    async def type_remove(self, interaction: discord.Interaction, id_темы: int) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        open_count = await self.bot.db.count_open_tickets_for_category(
            interaction.guild.id, id_темы
        )
        if open_count > 0:
            await interaction.response.send_message(
                f"Нельзя удалить: **{open_count}** открытых тикетов с этой темой. "
                "Используйте `/ticket тип-выкл`.",
                ephemeral=True,
            )
            return
        ok = await self.bot.db.remove_ticket_category(interaction.guild.id, id_темы)
        if ok:
            await self._refresh_panel_after_config(interaction.guild)
        await interaction.response.send_message(
            "✅ Тема удалена. Панель обновлена." if ok else "Тема не найдена.",
            ephemeral=True,
        )

    @ticket_group.command(name="тип-выкл", description="Скрыть тему с панели (не удаляя)")
    async def type_disable(self, interaction: discord.Interaction, id_темы: int) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        ok = await self.bot.db.set_ticket_category_enabled(
            interaction.guild.id, id_темы, enabled=False
        )
        if ok:
            await self._refresh_panel_after_config(interaction.guild)
        await interaction.response.send_message(
            "✅ Тема скрыта с панели." if ok else "Тема не найдена.",
            ephemeral=True,
        )

    @ticket_group.command(name="тип-вкл", description="Снова показать тему на панели")
    async def type_enable(self, interaction: discord.Interaction, id_темы: int) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        ok = await self.bot.db.set_ticket_category_enabled(
            interaction.guild.id, id_темы, enabled=True
        )
        if ok:
            await self._refresh_panel_after_config(interaction.guild)
        await interaction.response.send_message(
            "✅ Тема снова на панели." if ok else "Тема не найдена.",
            ephemeral=True,
        )

    @ticket_group.command(name="список", description="Список тикетов сервера")
    @app_commands.describe(статус="Фильтр по статусу")
    async def list_tickets(
        self,
        interaction: discord.Interaction,
        статус: Literal["открытые", "закрытые", "все"] = "открытые",
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        status_map = {"открытые": "open", "закрытые": "closed", "все": None}
        db_status = status_map[статус]
        rows = await self.bot.db.list_tickets(
            interaction.guild.id,
            status=db_status,
            limit=15,
        )
        embed = await self.bot.embeds.ticket_list_embed(
            interaction.guild,
            [dict(r) for r in rows],
            status_label=статус,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_group.command(name="транскрипт", description="Транскрипт закрытого тикета по номеру")
    @app_commands.describe(номер="Номер тикета (# из канала или логов)")
    async def fetch_transcript(
        self,
        interaction: discord.Interaction,
        номер: app_commands.Range[int, 1, 999999],
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        row = await self.bot.db.get_ticket_by_number(interaction.guild.id, номер)
        if not row or not row["transcript"]:
            await interaction.response.send_message(
                "Транскрипт не найден (тикет открыт или канал удалён без сохранения).",
                ephemeral=True,
            )
            return
        text = str(row["transcript"])
        files = make_transcript_files(text, f"ticket-{номер}")
        await interaction.response.send_message(
            f"📋 Транскрипт тикета **#{номер}**",
            files=files,
            ephemeral=True,
        )

    @ticket_group.command(name="синхронизация", description="Закрыть «висячие» тикеты без канала")
    async def sync_orphans(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        fixed = await self.bot.tickets.sync_orphan_tickets(interaction.guild)
        await interaction.followup.send(
            f"✅ Синхронизировано: **{fixed}** записей.",
            ephemeral=True,
        )

    @ticket_group.command(name="проверка", description="Проверить конфигурацию и запустить обслуживание")
    @app_commands.describe(восстановить_панель="Пересоздать панель, если сообщение удалено")
    async def health_check(
        self,
        interaction: discord.Interaction,
        восстановить_панель: bool = True,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        report = await self.bot.ticket_automation.run_guild_maintenance(
            interaction.guild,
            repair_panel=восстановить_панель,
        )
        embed = await self.bot.embeds.ticket_audit_embed(
            interaction.guild,
            report.issues,
            report=report,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ticket_group.command(
        name="авто-закрытие",
        description="Закрывать тикеты без активности (0 = выключено)",
    )
    @app_commands.describe(часы="Часов без сообщений до авто-закрытия (0–720)")
    async def set_idle_close(
        self,
        interaction: discord.Interaction,
        часы: app_commands.Range[int, 0, 720],
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            idle_close_hours=часы,
        )
        label = "выключено" if часы == 0 else f"через **{часы}** ч без активности"
        await interaction.response.send_message(
            f"✅ Авто-закрытие: {label}.",
            ephemeral=True,
        )

    @ticket_group.command(
        name="напоминание-staff",
        description="Пинг staff в не взятых тикетах (0 = выключено)",
    )
    @app_commands.describe(часы="Интервал напоминаний в часах (0–168)")
    async def set_staff_reminder(
        self,
        interaction: discord.Interaction,
        часы: app_commands.Range[int, 0, 168],
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_ticket_config(
            interaction.guild.id,
            remind_unclaimed_hours=часы,
        )
        label = "выключено" if часы == 0 else f"каждые **{часы}** ч"
        await interaction.response.send_message(
            f"✅ Напоминания staff: {label}.",
            ephemeral=True,
        )

    @ticket_group.command(name="обслуживание", description="Фоновое обслуживание без полной проверки")
    async def run_maintenance(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        report = await self.bot.ticket_automation.run_guild_maintenance(
            interaction.guild,
            repair_panel=False,
        )
        parts: list[str] = []
        if report.orphans_closed:
            parts.append(f"Сирот закрыто: **{report.orphans_closed}**")
        if report.idle_closed:
            parts.append(f"Авто-закрыто: **{report.idle_closed}**")
        if report.reminders_sent:
            parts.append(f"Напоминаний: **{report.reminders_sent}**")
        if not parts:
            parts.append("Нечего делать — всё в порядке.")
        await interaction.followup.send("\n".join(parts), ephemeral=True)

    @ticket_group.command(name="статистика", description="Статистика тикетов сервера")
    async def statistics(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        stats = await self.bot.db.ticket_statistics(interaction.guild.id)
        embed = await self.bot.embeds.ticket_statistics_embed(interaction.guild, stats)
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
        if not await self.bot.tickets.can_close_ticket(interaction.user, ticket):
            await interaction.response.send_message(
                "Закрыть тикет может только staff.",
                ephemeral=True,
            )
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
