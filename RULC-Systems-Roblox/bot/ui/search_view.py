from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from bot.services.embeds import RobloxEmbedFactory

if TYPE_CHECKING:
    from bot.cogs.search import SearchCog

PUNISHMENTS_PER_PAGE = 3


class SearchPaginationView(discord.ui.View):
    def __init__(
        self,
        cog: SearchCog,
        *,
        guild_id: int,
        guild_name: str | None,
        roblox: dict[str, Any],
        punishments: list[dict[str, Any]],
        total_points: int,
        author: discord.User | discord.Member,
        page: int = 0,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.roblox = roblox
        self.punishments = punishments
        self.total_points = total_points
        self.author = author
        self.page = page
        self._sync_buttons()

    @property
    def total_pages(self) -> int:
        if not self.punishments:
            return 1
        detail_pages = (len(self.punishments) + PUNISHMENTS_PER_PAGE - 1) // PUNISHMENTS_PER_PAGE
        return 1 + detail_pages

    def build_embed(self) -> discord.Embed:
        if self.page == 0:
            return RobloxEmbedFactory.overview_embed(
                self.roblox,
                punishments=self.punishments,
                total_points=self.total_points,
                author=self.author,
                guild_name=self.guild_name,
                total_pages=self.total_pages,
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

    def _sync_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "search_prev":
                    child.disabled = self.page <= 0
                elif child.custom_id == "search_next":
                    child.disabled = self.page >= self.total_pages - 1
                elif child.custom_id == "search_page":
                    child.label = f"{self.page + 1} / {self.total_pages}"

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="search_prev")
    async def prev_page(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        if self.page <= 0:
            await interaction.response.defer()
            return
        self.page -= 1
        await self._refresh(interaction)

    @discord.ui.button(
        label="1 / 1",
        style=discord.ButtonStyle.secondary,
        disabled=True,
        custom_id="search_page",
    )
    async def page_indicator(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="search_next")
    async def next_page(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        if self.page >= self.total_pages - 1:
            await interaction.response.defer()
            return
        self.page += 1
        await self._refresh(interaction)

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
