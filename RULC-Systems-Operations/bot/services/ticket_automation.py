from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)


@dataclass
class ConfigIssue:
    level: str  # ok | warn | error
    text: str
    code: str = ""


@dataclass
class MaintenanceReport:
    orphans_closed: int = 0
    idle_closed: int = 0
    reminders_sent: int = 0
    panel_repaired: bool = False
    issues: list[ConfigIssue] = field(default_factory=list)


def _parse_db_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class TicketAutomation:
    def __init__(self, bot: RoleSyncBot) -> None:
        self.bot = bot

    async def audit_config(self, guild: discord.Guild) -> list[ConfigIssue]:
        issues: list[ConfigIssue] = []
        config = await self.bot.db.get_ticket_config(guild.id)
        staff = await self.bot.db.list_ticket_staff_roles(guild.id)
        categories = await self.bot.db.list_ticket_categories(guild.id, enabled_only=True)

        if not categories:
            issues.append(ConfigIssue("error", "Нет активных тем на панели."))
        if not staff:
            issues.append(ConfigIssue(
                "warn", "Staff-роли не заданы — только Manage Channels.", "staff_missing"
            ))
        if not config["discord_category_id"]:
            issues.append(ConfigIssue("warn", "Discord-категория не задана."))
        else:
            cat = guild.get_channel(int(config["discord_category_id"]))
            if not isinstance(cat, discord.CategoryChannel):
                issues.append(ConfigIssue("error", "Категория Discord удалена или недоступна."))
        if not config["log_channel_id"]:
            issues.append(ConfigIssue("warn", "Канал логов не задан — транскрипты только в БД."))
        else:
            log_ch = guild.get_channel(int(config["log_channel_id"]))
            if not isinstance(log_ch, discord.TextChannel):
                issues.append(ConfigIssue("error", "Канал логов удалён."))
        if not config["panel_channel_id"] or not config["panel_message_id"]:
            issues.append(ConfigIssue("warn", "Панель тикетов не опубликована.", "panel_missing"))
        elif config["panel_channel_id"]:
            panel_ch = guild.get_channel(int(config["panel_channel_id"]))
            if not isinstance(panel_ch, discord.TextChannel):
                issues.append(ConfigIssue("error", "Канал панели удалён.", "panel_channel_missing"))
            else:
                try:
                    await panel_ch.fetch_message(int(config["panel_message_id"]))
                except discord.HTTPException:
                    issues.append(ConfigIssue(
                        "warn", "Сообщение панели не найдено — нужен repair.", "panel_message_missing"
                    ))

        me = guild.me
        if me and not me.guild_permissions.manage_channels:
            issues.append(ConfigIssue("error", "Боту нужно право **Manage Channels**."))
        if not issues:
            issues.append(ConfigIssue("ok", "Конфигурация в порядке.", "ok"))
        return issues

    async def repair_panel(self, guild: discord.Guild) -> bool:
        config = await self.bot.db.get_ticket_config(guild.id)
        if not config["panel_channel_id"]:
            return False
        channel = guild.get_channel(int(config["panel_channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return False
        if config["panel_message_id"]:
            try:
                await channel.fetch_message(int(config["panel_message_id"]))
                return False
            except discord.HTTPException:
                pass
        try:
            await self.bot.tickets.post_panel(guild, channel)
            logger.info("Repaired ticket panel for guild %s", guild.id)
            return True
        except Exception:
            logger.exception("Panel repair failed for guild %s", guild.id)
            return False

    async def run_guild_maintenance(
        self,
        guild: discord.Guild,
        *,
        repair_panel: bool = True,
    ) -> MaintenanceReport:
        report = MaintenanceReport()
        report.issues = await self.audit_config(guild)

        report.orphans_closed = await self.bot.tickets.sync_orphan_tickets(guild)

        config = await self.bot.db.get_ticket_config(guild.id)
        idle_hours = int(config["idle_close_hours"] or 0)
        remind_hours = int(config["remind_unclaimed_hours"] or 0)

        rows = await self.bot.db.list_open_tickets(guild.id)
        now = datetime.now(timezone.utc)

        for row in rows:
            ticket = dict(row)
            channel = guild.get_channel(int(ticket["channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                continue

            if idle_hours > 0:
                last = _parse_db_time(ticket.get("last_activity_at")) or _parse_db_time(
                    ticket.get("created_at")
                )
                if last and (now - last).total_seconds() >= idle_hours * 3600:
                    closed = await self.bot.tickets.auto_close_ticket(
                        guild,
                        channel,
                        ticket,
                        reason=f"Авто-закрытие: нет активности {idle_hours} ч.",
                    )
                    if closed:
                        report.idle_closed += 1
                    continue

            if remind_hours > 0 and not ticket.get("claimed_by_id"):
                last_ping = _parse_db_time(ticket.get("last_staff_ping_at"))
                created = _parse_db_time(ticket.get("created_at"))
                anchor = last_ping or created
                if anchor and (now - anchor).total_seconds() >= remind_hours * 3600:
                    staff_roles = await self.bot.db.list_ticket_staff_roles(guild.id)
                    mention = " ".join(f"<@&{r}>" for r in staff_roles[:5])
                    if not mention and guild.me:
                        mention = guild.me.mention
                    if mention:
                        try:
                            await channel.send(
                                f"⏰ Тикет #{ticket.get('ticket_number') or ticket['id']} "
                                f"ожидает staff. {mention}"
                            )
                            await self.bot.db.mark_staff_ping(int(ticket["id"]))
                            report.reminders_sent += 1
                        except discord.HTTPException:
                            logger.debug("Staff remind failed for ticket %s", ticket["id"])

        if repair_panel and any(i.code == "panel_message_missing" for i in report.issues):
            report.panel_repaired = await self.repair_panel(guild)

        return report

    async def run_all_guilds(self) -> dict[int, MaintenanceReport]:
        results: dict[int, MaintenanceReport] = {}
        for guild in self.bot.guilds:
            try:
                results[guild.id] = await self.run_guild_maintenance(guild)
            except Exception:
                logger.exception("Ticket maintenance failed for guild %s", guild.id)
        return results
