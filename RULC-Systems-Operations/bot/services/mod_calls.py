from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)


class ModCallService:
    def __init__(self, bot: RoleSyncBot) -> None:
        self.bot = bot

    async def dispatch(
        self,
        guild: discord.Guild,
        caller: discord.Member,
        *,
        reason: str,
        source_channel: discord.abc.GuildChannel | None = None,
    ) -> tuple[bool, str]:
        config = await self.bot.db.get_mod_call_config(guild.id)
        if not int(config["enabled"]):
            return False, "Вызов модераторов отключён на этом сервере."

        channel_id = config["channel_id"]
        if not channel_id:
            return False, "Канал для вызова модераторов не настроен. Админ: `/mod-настройка канал`."

        alert_channel = guild.get_channel(int(channel_id))
        if not isinstance(alert_channel, discord.TextChannel):
            return False, "Канал вызова модераторов удалён или недоступен."

        roles = await self.bot.db.list_mod_call_roles(guild.id)
        if not roles:
            return False, "Роли модераторов не настроены. Админ: `/mod-настройка роль`."

        remaining = await self.bot.db.mod_call_cooldown_remaining(guild.id, caller.id)
        if remaining > 0:
            return False, f"Подождите **{remaining}** сек. перед повторным вызовом."

        reason_clean = reason.strip()
        if len(reason_clean) < 3:
            return False, "Укажите причину вызова (минимум 3 символа)."
        if len(reason_clean) > 500:
            reason_clean = reason_clean[:500] + "…"

        mention = " ".join(f"<@&{role_id}>" for role_id in roles[:8])
        embed = await self.bot.embeds.mod_call_embed(
            guild,
            caller=caller,
            reason=reason_clean,
            source_channel=source_channel,
        )

        try:
            await alert_channel.send(content=mention, embed=embed)
        except discord.Forbidden:
            return False, "Бот не может отправить сообщение в канал модераторов."
        except discord.HTTPException:
            logger.exception("Mod call send failed for guild %s", guild.id)
            return False, "Не удалось отправить вызов. Попробуйте позже."

        await self.bot.db.touch_mod_call_cooldown(guild.id, caller.id)
        logger.info(
            "Mod call from %s in guild %s -> #%s",
            caller.id,
            guild.id,
            alert_channel.name,
        )
        return True, f"Модераторы оповещены в {alert_channel.mention}."
