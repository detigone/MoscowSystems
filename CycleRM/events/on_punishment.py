import discord
from discord.ext import commands
from bson import ObjectId
from roblox.client import Client
from datamodels.Warnings import WarningItem
from utils.constants import BLANK_COLOR
from utils.rulc_embeds import finish_embed
from utils.rulc_roblox import sync_punishment_created
import roblox
import logging


class OnPunishment(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_punishment(self, objectid: ObjectId):
        warning: WarningItem = await self.bot.punishments.fetch_warning(objectid)
        if not warning:
            return

        await sync_punishment_created(warning)

        guild = self.bot.get_guild(warning.guild_id)
        if guild is None:
            logging.error(f"Guild with ID {warning.guild_id} not found.")
            return

        guild_settings = await self.bot.settings.find_by_id(guild.id)
        if not guild_settings:
            logging.error(f"Settings for guild ID {guild.id} not found.")
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
                "temporary ban": punishments_cfg.get("ban_channel"),
                "bolo": punishments_cfg.get("bolo_channel"),
            }
            try:
                channel = await guild.fetch_channel(
                    associations[warning_type.lower().strip()]
                )
            except discord.HTTPException:
                channel = await guild.fetch_channel(
                    (guild_settings.get("punishments") or {}).get("channel", 0)
                )
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
            logging.error(f"Moderator with ID {warning.moderator_id} not found.")
            return

        if not moderator:
            logging.error(
                f"Moderator with ID {warning.moderator_id} not found in guild {guild.id}."
            )
            return

        roblox_client: Client = Client()
        roblox_user = await roblox_client.get_user(warning.user_id)
        thumbnails = await roblox_client.thumbnails.get_user_avatar_thumbnails(
            [roblox_user], type=roblox.thumbnails.AvatarThumbnailType.headshot
        )
        thumbnail = thumbnails[0].image_url

        async def get_discord_id_by_roblox_id(self, roblox_id):
            linked_account = await self.bot.oauth2_users.db.find_one(
                {"roblox_id": roblox_id}
            )
            if linked_account:
                return linked_account["discord_id"]
            return None

        if channel is not None:
            try:
                warned_discord_id = await get_discord_id_by_roblox_id(
                    self, warning.user_id
                )
            except Exception as e:
                logging.error(f"Error getting warned discord ID: {e}")

            try:
                document = await self.bot.consent.db.find_one(
                    {"_id": warned_discord_id}
                )
                punishments_enabled = (
                    document.get("punishments")
                    if document.get("punishments") is not None
                    else True
                )
                if punishments_enabled:
                    user_to_dm = await guild.fetch_member(warned_discord_id)
                    embed = finish_embed(
                        discord.Embed(
                            title="Moderation",
                            description=(
                                f"{guild.name}\n"
                                f"{warning.warning_type} · {warning.reason}"
                            ),
                            color=BLANK_COLOR,
                        )
                        .set_thumbnail(url=thumbnail),
                    )
                    await user_to_dm.send(embed=embed)
                    logging.info(
                        f"Sent DM to user {warned_discord_id} about punishment."
                    )
            except Exception as e:
                pass

            embed = finish_embed(
                discord.Embed(title="Punishment Issued", color=BLANK_COLOR)
                .add_field(
                    name="Moderator",
                    value=(
                        f"{moderator.mention} · `{warning.snowflake}`\n"
                        f"{warning.reason} · <t:{int(warning.time_epoch)}:R>"
                    ),
                    inline=False,
                )
                .add_field(
                    name="Player",
                    value=(
                        f"{warning.username} · `{warning.user_id}`\n"
                        f"{warning.warning_type}"
                        f"{f' · <t:{int(warning.until_epoch)}:R>' if warning.until_epoch not in [None, 0] else ''}"
                    ),
                    inline=False,
                )
                .set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else "")
                .set_thumbnail(url=thumbnail),
            )

            await channel.send(embed=embed)
            logging.info(f"Sent punishment embed to channel {channel.id}")


async def setup(bot):
    await bot.add_cog(OnPunishment(bot))
