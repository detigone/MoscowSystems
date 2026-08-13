from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from bot.services.embeds import RobloxEmbedFactory

if TYPE_CHECKING:
    from bot.cogs.search import SearchCog

PUNISHMENTS_PER_PAGE = 3
HISTORY_BATCH = 100


class SearchPaginationView(discord.ui.View):
    def __init__(
        self,
        cog: SearchCog,
        *,
        guild_id: int,
        guild_name: str | None,
        roblox: dict[str, Any],
        roblox_id: int,
        punishments: list[dict[str, Any]],
        total_points: int,
        total_records: int,
        author: discord.User | discord.Member,
        discord_member: discord.Member | None = None,
        discord_link_source: str | None = None,
        discord_offserver_id: int | None = None,
        page: int = 0,
        history_note: str | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.roblox = roblox
        self.roblox_id = roblox_id
        self.punishments = punishments
        self.total_points = total_points
        self.total_records = total_records
        self.author = author
        self.discord_member = discord_member
        self.discord_link_source = discord_link_source
        self.discord_offserver_id = discord_offserver_id
        self.page = page
        self.history_note = history_note
        self._message: discord.Message | None = None
        self._rebuild_buttons()

    @property
    def has_more(self) -> bool:
        return len(self.punishments) < self.total_records

    @property
    def total_pages(self) -> int:
        if not self.punishments:
            return 1
        detail_pages = (len(self.punishments) + PUNISHMENTS_PER_PAGE - 1) // PUNISHMENTS_PER_PAGE
        return 1 + detail_pages

    def _rebuild_buttons(self) -> None:
        self.clear_items()
        profile = discord.ui.Button(
            label="Профиль Roblox",
            style=discord.ButtonStyle.link,
            url=f"https://www.roblox.com/users/{self.roblox_id}/profile",
            row=0,
        )
        self.add_item(profile)
        if self.total_pages > 1:
            prev = discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.secondary,
                custom_id="search_prev",
                disabled=self.page <= 0,
                row=1,
            )
            prev.callback = self._on_prev
            page_btn = discord.ui.Button(
                label=f"{self.page + 1} / {self.total_pages}",
                style=discord.ButtonStyle.secondary,
                custom_id="search_page",
                disabled=True,
                row=1,
            )
            nxt = discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.secondary,
                custom_id="search_next",
                disabled=self.page >= self.total_pages - 1,
                row=1,
            )
            nxt.callback = self._on_next
            self.add_item(prev)
            self.add_item(page_btn)
            self.add_item(nxt)
        if self.has_more:
            more = discord.ui.Button(
                label="Ещё",
                style=discord.ButtonStyle.primary,
                custom_id="search_load_more",
                row=2,
            )
            more.callback = self._on_load_more
            self.add_item(more)

    def bind_message(self, message: discord.Message) -> None:
        self._message = message

    def build_embed(self) -> discord.Embed:
        if self.page == 0:
            return RobloxEmbedFactory.overview_embed(
                self.roblox,
                punishments=self.punishments,
                total_points=self.total_points,
                author=self.author,
                guild_name=self.guild_name,
                total_pages=self.total_pages,
                history_note=self.history_note,
                discord_member=self.discord_member,
                discord_link_source=self.discord_link_source,
                discord_offserver_id=self.discord_offserver_id,
            )
        start = (self.page - 1) * PUNISHMENTS_PER_PAGE
        chunk = self.punishments[start : start + PUNISHMENTS_PER_PAGE]
        return RobloxEmbedFactory.punishments_embed(
            self.roblox,
            chunk,
            page_index=self.page,
            total_pages=self.total_pages,
            author=self.author,
            guild_name=self.guild_name,
        )

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        if self.page <= 0:
            await interaction.response.defer()
            return
        self.page -= 1
        self._rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        if self.page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.page += 1
        self._rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_load_more(self, interaction: discord.Interaction) -> None:
        try:
            batch = await self.cog.bot.db.list_punishments(
                self.guild_id,
                self.roblox_id,
                include_revoked=True,
                limit=HISTORY_BATCH,
                offset=len(self.punishments),
            )
        except Exception:
            await interaction.response.send_message(
                "Не удалось загрузить записи.",
                ephemeral=True,
            )
            return
        if not batch:
            await interaction.response.send_message(
                "Больше записей нет.",
                ephemeral=True,
            )
            return
        self.punishments.extend(batch)
        loaded = len(self.punishments)
        self.history_note = (
            f"Загружено {loaded} из {self.total_records}"
            if loaded < self.total_records
            else None
        )
        self._rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != getattr(self, "_owner_id", None):
            await interaction.response.send_message(
                "Это меню открыл другой пользователь.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self._message:
            try:
                await self._message.edit(view=self)
            except discord.HTTPException:
                pass
