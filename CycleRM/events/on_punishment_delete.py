import discord
from discord.ext import commands
from bson import ObjectId
from roblox.client import Client
from datamodels.Warnings import WarningItem
from utils.constants import BLANK_COLOR
from utils.rulc_embeds import finish_embed
from utils.rulc_roblox import sync_punishment_revoked
import roblox


class OnPunishmentDelete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_punishment_delete(self, objectid: ObjectId, manager: discord.Member):
        warning: WarningItem = await self.bot.punishments.fetch_warning(objectid)
        if not warning:
            return

        await sync_punishment_revoked(warning, manager)

        guild = self.bot.get_guild(warning.guild_id)
        if guild is None:
            return
        guild_settings = await self.bot.settings.find_by_id(guild.id)
        if not guild_settings:
            return

        punishment_types = await self.bot.punishment_types.get_punishment_types(
            warning.guild_id
        )

        warning_type = warning.warning_type
        custom_warning_type = None
        if warning_type not in ["Warning", "Kick", "Ban", "BOLO"]:
            for item in punishment_types["types"]:
                if isinstance(item, dict):
                    if item["name"] == warning_type:
                        custom_warning_type = item

        if custom_warning_type is None:
            punishments_cfg = guild_settings.get("punishments") or {}
            associations = {
                "warning": punishments_cfg.get("channel"),
                "kick": punishments_cfg.get("kick_channel"),
                "ban": punishments_cfg.get("ban_channel"),
                "bolo": punishments_cfg.get("bolo_channel"),
            }
            try:
                channel = await guild.fetch_channel(
                    associations[warning_type.lower().strip()]
                )
            except discord.HTTPException:
                channel = None
        else:
            try:
                channel = await guild.fetch_channel(
                    custom_warning_type.get("channel", 0)
                )
            except discord.HTTPException:
                try:
                    channel = await guild.fetch_channel(
                        (guild_settings.get("punishments") or {}).get("channel", 0)
                    )
                except discord.HTTPException:
                    channel = None

        try:
            moderator: discord.Member = guild.get_member(warning.moderator_id)
        except discord.NotFound:
            return

        if not moderator:
            return
        roblox_client: Client = Client()
        roblox_user = await roblox_client.get_user(warning.user_id)
        thumbnails = await roblox_client.thumbnails.get_user_avatar_thumbnails(
            [roblox_user], type=roblox.thumbnails.AvatarThumbnailType.headshot
        )
        thumbnail = thumbnails[0].image_url

        if channel is not None:
            await channel.send(
                embed=finish_embed(
                    discord.Embed(title="Punishment Revoked", color=BLANK_COLOR)
                    .add_field(
                        name="Moderator",
                        value=(
                            f"{moderator.mention} · revoked {manager.mention}\n"
                            f"`{warning.snowflake}` · {warning.reason}"
                        ),
                        inline=False,
                    )
                    .add_field(
                        name="Player",
                        value=(
                            f"{warning.username} · `{warning.user_id}`\n"
                            f"{warning.warning_type}"
                        ),
                        inline=False,
                    )
                    .set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else "")
                    .set_thumbnail(url=thumbnail),
                )
            )


async def setup(bot):
    await bot.add_cog(OnPunishmentDelete(bot))
