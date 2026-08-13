from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.tickets import _require_ticket_admin

if TYPE_CHECKING:
    from bot.app import RoleSyncBot

logger = logging.getLogger(__name__)

mod_setup_group = app_commands.Group(
    name="mod-настройка",
    description="Настройка вызова модераторов (/mod, !mod)",
)


class ModCallsCog(commands.Cog):
    def __init__(self, bot: RoleSyncBot) -> None:
        self.bot = bot

    async def _send_mod_call(
        self,
        guild: discord.Guild,
        caller: discord.Member,
        *,
        reason: str,
        source_channel: discord.abc.GuildChannel | None,
        reply,
    ) -> None:
        ok, message = await self.bot.mod_calls.dispatch(
            guild,
            caller,
            reason=reason,
            source_channel=source_channel,
        )
        await reply(message, ephemeral=ok)

    @app_commands.command(name="mod", description="Вызвать модератора на сервер")
    @app_commands.describe(причина="Что случилось — опишите кратко")
    async def mod_slash(self, interaction: discord.Interaction, причина: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return

        async def reply(text: str, *, ephemeral: bool) -> None:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(text, ephemeral=ephemeral)

        await interaction.response.defer(ephemeral=True)
        await self._send_mod_call(
            interaction.guild,
            interaction.user,
            reason=причина,
            source_channel=interaction.channel,
            reply=reply,
        )

    @commands.command(name="mod")
    async def mod_prefix(self, ctx: commands.Context, *, причина: str | None = None) -> None:
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.reply("Только на сервере.", mention_author=False)
            return
        if not причина or not причина.strip():
            await ctx.reply(
                "Укажите причину: `!mod <что случилось>`",
                mention_author=False,
            )
            return

        async def reply(text: str, *, ephemeral: bool) -> None:
            await ctx.reply(text, mention_author=not ephemeral)

        await self._send_mod_call(
            ctx.guild,
            ctx.author,
            reason=причина,
            source_channel=ctx.channel,
            reply=reply,
        )

    @mod_setup_group.command(name="канал", description="Куда слать вызовы модераторов")
    async def set_channel(
        self,
        interaction: discord.Interaction,
        канал: discord.TextChannel,
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_mod_call_config(
            interaction.guild.id,
            channel_id=канал.id,
        )
        await interaction.response.send_message(
            f"✅ Вызовы модераторов → {канал.mention}",
            ephemeral=True,
        )

    @mod_setup_group.command(name="роль", description="Добавить роль для пинга при вызове")
    async def add_role(self, interaction: discord.Interaction, роль: discord.Role) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.add_mod_call_role(interaction.guild.id, роль.id)
        await interaction.response.send_message(
            f"✅ При `/mod` будет пинговаться {роль.mention}",
            ephemeral=True,
        )

    @mod_setup_group.command(name="роль-убрать", description="Убрать роль из пинга")
    async def remove_role(self, interaction: discord.Interaction, роль: discord.Role) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        ok = await self.bot.db.remove_mod_call_role(interaction.guild.id, роль.id)
        msg = f"✅ Роль {роль.mention} убрана." if ok else "Роль не была в списке."
        await interaction.response.send_message(msg, ephemeral=True)

    @mod_setup_group.command(name="кулдаун", description="Пауза между вызовами одного игрока (сек.)")
    @app_commands.describe(секунды="0 = без ограничения, по умолчанию 300")
    async def set_cooldown(
        self,
        interaction: discord.Interaction,
        секунды: app_commands.Range[int, 0, 3600],
    ) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_mod_call_config(
            interaction.guild.id,
            cooldown_seconds=секунды,
        )
        label = "без ограничения" if секунды == 0 else f"**{секунды}** сек."
        await interaction.response.send_message(f"✅ Кулдаун: {label}.", ephemeral=True)

    @mod_setup_group.command(name="вкл", description="Включить вызов модераторов")
    async def enable(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_mod_call_config(interaction.guild.id, enabled=1)
        await interaction.response.send_message("✅ `/mod` включён.", ephemeral=True)

    @mod_setup_group.command(name="выкл", description="Временно отключить вызов модераторов")
    async def disable(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        await self.bot.db.update_mod_call_config(interaction.guild.id, enabled=0)
        await interaction.response.send_message("⛔ `/mod` отключён.", ephemeral=True)

    @mod_setup_group.command(name="настройки", description="Текущая конфигурация")
    async def settings(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not await _require_ticket_admin(interaction):
            return
        embed = await self.bot.embeds.mod_call_settings_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: RoleSyncBot) -> None:
    cog = ModCallsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(mod_setup_group)
