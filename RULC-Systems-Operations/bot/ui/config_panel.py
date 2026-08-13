from __future__ import annotations

import logging

import discord

from bot.core.checks import is_config_user
from bot.services.webhook_validate import is_valid_discord_webhook

logger = logging.getLogger(__name__)

TIMEOUT = 900

COLOR_PRESETS = {
    "brand": ("#4FC3F7", "RU:LC (основной)"),
    "blurple": ("#5865F2", "Blurple"),
    "green": ("#57F287", "Зелёный"),
    "yellow": ("#FEE75C", "Жёлтый"),
    "red": ("#ED4245", "Красный"),
    "cyan": ("#00A8FC", "Голубой"),
    "purple": ("#9B59B6", "Фиолетовый"),
}


def _allowed(interaction: discord.Interaction, bot) -> bool:
    return is_config_user(bot, interaction.user.id)


async def _deny(interaction: discord.Interaction) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message("Нет доступа.", ephemeral=True)
    else:
        await interaction.followup.send("Нет доступа.", ephemeral=True)


async def open_config_panel(interaction: discord.Interaction, bot) -> None:
    embed = await ConfigPanel.overview_embed(bot, interaction.guild)
    await interaction.response.send_message(
        embed=embed,
        view=MainMenuView(bot),
        ephemeral=True,
    )


class ConfigPanel:
    @staticmethod
    async def overview_embed(bot, guild: discord.Guild) -> discord.Embed:
        gid = guild.id
        theme = await bot.embeds.theme(gid)
        erlc = await bot.db.get_erlc_server(gid)
        voice = await bot.db.get_voice_counter(gid)
        autoroles = await bot.db.get_guild_autoroles(gid)
        groups = await bot.db.get_groups_for_guild(gid)
        broadcasts = await bot.db.list_broadcast_sources(gid)
        rules = await bot.db.get_conditional_rules(gid)
        ticket_stats = await bot.db.ticket_statistics(gid)

        embed = discord.Embed(
            title="⚙️ Панель управления",
            description=(
                f"**{theme.brand_name}** · настройки сервера\n\n"
                "Выберите **раздел** в меню ниже.\n"
                "Все изменения сохраняются сразу."
            ),
            color=theme.color_primary,
        )
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(
            name="🎮 ER:LC",
            value=f"✅ {erlc['server_name']}" if erlc else "❌ не подключён",
            inline=True,
        )
        embed.add_field(
            name="🔊 Онлайн-канал",
            value=f"✅ <#{voice['channel_id']}>" if voice else "—",
            inline=True,
        )
        embed.add_field(name="👤 Autorole", value="✅ включён" if autoroles else "—", inline=True)
        embed.add_field(name="🔄 Sync-группы", value=f"`{len(groups)}`", inline=True)
        embed.add_field(name="📢 Рассылки", value=f"`{len(broadcasts)}`", inline=True)
        embed.add_field(name="🧩 Условные роли", value=f"`{len(rules)}`", inline=True)
        embed.add_field(
            name="🎫 Тикеты",
            value=f"открыто **`{ticket_stats.get('open_count', 0)}`**",
            inline=True,
        )
        embed.set_footer(text=f"{theme.brand_name} · доступ ограничен")
        return embed

    @staticmethod
    async def section_embed(bot, guild: discord.Guild, section: str) -> discord.Embed:
        theme = await bot.embeds.theme(guild.id)
        meta = {
            "sync": ("🔄 Синхронизация ролей", "Группы серверов и роли для автосинхронизации."),
            "autorole": ("👤 Autorole", "Роли при входе участника и при добавлении бота."),
            "conditional": ("🧩 Условные роли", "Выдать роль **A**, если есть роль **B**."),
            "broadcast": ("📢 Рассылка", "Сообщения из канала → webhooks фракций."),
            "voice": ("🔊 Счётчик онлайна", "Голосовой канал с количеством игроков ER:LC."),
            "erlc": ("🎮 ER:LC", "Подключение API-ключа приватного сервера."),
            "appearance": ("🎨 Оформление", "Цвета, бренд и стиль embed-сообщений."),
            "tickets": ("🎫 Тикеты", "Панель поддержки, staff-роли и категории обращений."),
        }
        title, desc = meta[section]

        if section == "appearance":
            embed = await bot.embeds.settings_preview_embed(guild)
            embed.title = title
            embed.description = desc + "\n\n" + (embed.description or "")
            embed.set_footer(text="◀ Главная — вернуться в меню")
            return embed

        embed = discord.Embed(title=title, description=desc, color=theme.color_primary)
        gid = guild.id

        if section == "sync":
            groups = await bot.db.get_groups_for_guild(gid)
            if not groups:
                embed.add_field(name="Статус", value="Групп пока нет — создайте кнопкой **➕**", inline=False)
            for g in groups[:6]:
                roles = await bot.db.get_synced_roles(g["id"])
                embed.add_field(name=g["name"], value=f"Ролей: **{len(roles)}**", inline=True)

        elif section == "autorole":
            ar = await bot.db.get_guild_autoroles(gid)
            if ar:
                mr = guild.get_role(ar["member_role_id"]) if ar["member_role_id"] else None
                br = guild.get_role(ar["bot_role_id"]) if ar["bot_role_id"] else None
                embed.add_field(name="Участник", value=mr.mention if mr else "—", inline=True)
                embed.add_field(name="Бот", value=br.mention if br else "—", inline=True)
            else:
                embed.add_field(name="Статус", value="Не настроено", inline=False)

        elif section == "conditional":
            rules = await bot.db.get_conditional_rules(gid)
            if not rules:
                embed.add_field(name="Правила", value="Пока нет — добавьте кнопкой **➕**", inline=False)
            for rule in rules[:6]:
                target = guild.get_role(rule["target_role_id"])
                tids = await bot.db.get_conditional_triggers(rule["id"])
                tr = ", ".join(
                    guild.get_role(t).name for t in tids[:3] if guild.get_role(t)
                ) or "—"
                embed.add_field(
                    name=f"#{rule['id']} · {rule['name']}",
                    value=f"→ {target.mention if target else '?'} | если: {tr}",
                    inline=False,
                )

        elif section == "broadcast":
            sources = await bot.db.list_broadcast_sources(gid)
            if not sources:
                embed.add_field(name="Рассылки", value="Не настроены", inline=False)
            for src in sources[:5]:
                ch = guild.get_channel(src["source_channel_id"])
                n = len(await bot.db.get_broadcast_targets(src["id"]))
                embed.add_field(
                    name=src["name"],
                    value=f"{ch.mention if ch else '?'} · **{n}** webhook(s)",
                    inline=False,
                )

        elif section == "voice":
            vc = await bot.db.get_voice_counter(gid)
            if vc:
                ch = guild.get_channel(vc["channel_id"])
                embed.add_field(name="Канал", value=ch.mention if ch else "?", inline=True)
                embed.add_field(name="Шаблон", value=f"`{vc['name_template']}`", inline=False)
            else:
                embed.add_field(name="Статус", value="Выберите голосовой канал ниже", inline=False)

        elif section == "erlc":
            erlc = await bot.db.get_erlc_server(gid)
            if erlc:
                embed.add_field(name="Сервер", value=erlc["server_name"] or "—", inline=True)
                try:
                    info = await bot.erlc.fetch_server_info(gid)
                    embed.add_field(
                        name="Онлайн",
                        value=f"{info.get('players')}/{info.get('max_players')}",
                        inline=True,
                    )
                except Exception:
                    pass
            else:
                embed.add_field(name="Статус", value="Нажмите **🔑 API ключ**", inline=False)

        elif section == "tickets":
            ts = await bot.db.ticket_statistics(gid)
            cfg = await bot.db.get_ticket_config(gid)
            staff = await bot.db.list_ticket_staff_roles(gid)
            cat = guild.get_channel(int(cfg["discord_category_id"])) if cfg["discord_category_id"] else None
            embed.add_field(
                name="Статус",
                value=(
                    f"Открыто: **`{ts.get('open_count', 0)}`** · "
                    f"Всего: **`{ts.get('total', 0)}`**"
                ),
                inline=False,
            )
            embed.add_field(
                name="Категория Discord",
                value=cat.name if cat else "— (`/ticket категория-канал`)",
                inline=True,
            )
            embed.add_field(
                name="Staff-роли",
                value=str(len(staff)),
                inline=True,
            )
            embed.add_field(
                name="Быстрый старт",
                value=(
                    "1. `/ticket категория-канал`\n"
                    "2. `/ticket staff-добавить`\n"
                    "3. `/ticket канал-логов`\n"
                    "4. `/ticket панель`"
                ),
                inline=False,
            )

        embed.set_footer(text="◀ Главная — вернуться в меню")
        return embed


async def build_section_view(bot, guild: discord.Guild, section: str) -> discord.ui.View:
    builders = {
        "sync": _build_sync_view,
        "autorole": _build_autorole_view,
        "conditional": _build_conditional_view,
        "broadcast": _build_broadcast_view,
        "voice": _build_voice_view,
        "erlc": _build_erlc_view,
        "appearance": _build_appearance_view,
        "tickets": _build_tickets_view,
    }
    return await builders[section](bot, guild)


async def _refresh_section(
    interaction: discord.Interaction,
    bot,
    section: str,
    *,
    note: str | None = None,
) -> None:
    embed = await ConfigPanel.section_embed(bot, interaction.guild, section)
    view = await build_section_view(bot, interaction.guild, section)
    await interaction.response.edit_message(embed=embed, view=view, content=note)


async def _refresh_home(interaction: discord.Interaction, bot, *, note: str | None = None) -> None:
    embed = await ConfigPanel.overview_embed(bot, interaction.guild)
    if note:
        embed.description = f"{embed.description}\n\n{note}"
    await interaction.response.edit_message(embed=embed, view=MainMenuView(bot), content=None)


# ── Shared ──────────────────────────────────────────────────────────────────

class BackButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Главная", style=discord.ButtonStyle.secondary, emoji="◀", row=4)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        bot = view.bot  # type: ignore[attr-defined]
        if not _allowed(interaction, bot):
            return await _deny(interaction)
        await _refresh_home(interaction, bot)


class ConfigBaseView(discord.ui.View):
    section: str = ""

    def __init__(self, bot) -> None:
        super().__init__(timeout=TIMEOUT)
        self.bot = bot
        self.add_item(BackButton())


class MainMenuView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=TIMEOUT)
        self.bot = bot
        self.add_item(SectionSelect(bot))
        self.add_item(RefreshButton(bot))


class RefreshButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Обновить", style=discord.ButtonStyle.primary, emoji="🔁", row=4)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _allowed(interaction, self.bot):
            return await _deny(interaction)
        await _refresh_home(interaction, self.bot)


class SectionSelect(discord.ui.Select):
    def __init__(self, bot) -> None:
        self.bot = bot
        super().__init__(
            placeholder="📂 Выберите раздел настроек…",
            row=0,
            options=[
                discord.SelectOption(label="Синхронизация ролей", value="sync", emoji="🔄"),
                discord.SelectOption(label="Autorole", value="autorole", emoji="👤"),
                discord.SelectOption(label="Условные роли", value="conditional", emoji="🧩"),
                discord.SelectOption(label="Рассылка", value="broadcast", emoji="📢"),
                discord.SelectOption(label="Счётчик онлайна", value="voice", emoji="🔊"),
                discord.SelectOption(label="ER:LC", value="erlc", emoji="🎮"),
                discord.SelectOption(label="Оформление", value="appearance", emoji="🎨"),
                discord.SelectOption(label="Тикеты", value="tickets", emoji="🎫"),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _allowed(interaction, self.bot):
            return await _deny(interaction)
        section = self.values[0]
        embed = await ConfigPanel.section_embed(self.bot, interaction.guild, section)
        view = await build_section_view(self.bot, interaction.guild, section)
        await interaction.response.edit_message(embed=embed, view=view, content=None)


# ── Sync ────────────────────────────────────────────────────────────────────

class SyncSectionView(ConfigBaseView):
    section = "sync"

    def __init__(self, bot, *, selected: str | None = None) -> None:
        super().__init__(bot)
        self.selected_group = selected


async def _build_sync_view(bot, guild: discord.Guild) -> SyncSectionView:
    view = SyncSectionView(bot)
    all_groups = await bot.db.list_sync_groups()
    options = [
        discord.SelectOption(label=g["name"], value=g["name"])
        for g in all_groups[:25]
    ] or [discord.SelectOption(label="Нет групп — создайте ➕", value="_none")]

    picker = SyncGroupSelect(bot, view)
    picker.options = options
    view.add_item(picker)
    view.add_item(SyncCreateButton(bot))
    view.add_item(SyncAddServerButton(bot))
    view.add_item(SyncAddRoleSelect(bot))
    return view


class SyncGroupSelect(discord.ui.Select):
    def __init__(self, bot, parent: SyncSectionView) -> None:
        self.bot = bot
        self.parent = parent
        super().__init__(placeholder="Выберите группу sync…", row=1, options=[
            discord.SelectOption(label="—", value="_")
        ])

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "_none":
            return await interaction.response.defer()
        self.parent.selected_group = self.values[0]
        await interaction.response.send_message(
            f"Группа **`{self.values[0]}`** выбрана.",
            ephemeral=True,
        )


class SyncCreateModal(discord.ui.Modal, title="Новая группа sync"):
    name = discord.ui.TextInput(label="Название", placeholder="moscow-network", max_length=48)

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await self.bot.db.create_sync_group(self.name.value.strip())
            note = f"✅ Группа `{self.name.value}` создана."
        except Exception:
            note = "❌ Такая группа уже есть."
        await _refresh_section(interaction, self.bot, "sync", note=note)


class SyncCreateButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Создать", style=discord.ButtonStyle.success, emoji="➕", row=2)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SyncCreateModal(self.bot))


class SyncAddServerButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Добавить сервер", style=discord.ButtonStyle.primary, emoji="🏛️", row=2)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SyncSectionView = self.view  # type: ignore
        group = view.selected_group
        if not group:
            gs = await self.bot.db.get_groups_for_guild(interaction.guild.id)
            group = gs[0]["name"] if len(gs) == 1 else None
        if not group:
            return await interaction.response.send_message("Выберите группу в списке.", ephemeral=True)
        ok = await self.bot.db.add_guild_to_group(group, interaction.guild.id)
        note = "✅ Сервер добавлен." if ok else "❌ Группа не найдена."
        await _refresh_section(interaction, self.bot, "sync", note=note)


class SyncAddRoleSelect(discord.ui.RoleSelect):
    def __init__(self, bot) -> None:
        super().__init__(placeholder="➕ Роль для синхронизации…", max_values=1, row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SyncSectionView = self.view  # type: ignore
        role = self.values[0]
        group = view.selected_group
        if not group:
            gs = await self.bot.db.get_groups_for_guild(interaction.guild.id)
            group = gs[0]["name"] if len(gs) == 1 else None
        if not group:
            return await interaction.response.send_message("Выберите группу.", ephemeral=True)
        ok = await self.bot.db.add_synced_role(group, role.name)
        note = f"✅ `{role.name}` добавлена." if ok else "❌ Ошибка."
        await _refresh_section(interaction, self.bot, "sync", note=note)


# ── Autorole ──────────────────────────────────────────────────────────────

class AutoroleSectionView(ConfigBaseView):
    section = "autorole"


async def _build_autorole_view(bot, guild: discord.Guild) -> AutoroleSectionView:
    view = AutoroleSectionView(bot)
    view.add_item(MemberRolePicker(bot))
    view.add_item(BotRolePicker(bot))
    view.add_item(ApplyBotRoleButton(bot))
    return view


class MemberRolePicker(discord.ui.RoleSelect):
    def __init__(self, bot) -> None:
        super().__init__(placeholder="👤 Autorole участника…", max_values=1, row=1)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        role = self.values[0]
        await self.bot.db.set_guild_autoroles(interaction.guild.id, member_role_id=role.id)
        await _refresh_section(
            interaction, self.bot, "autorole", note=f"✅ Участник: {role.mention}"
        )


class BotRolePicker(discord.ui.RoleSelect):
    def __init__(self, bot) -> None:
        super().__init__(placeholder="🤖 Autorole бота…", max_values=1, row=2)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        role = self.values[0]
        await self.bot.db.set_guild_autoroles(interaction.guild.id, bot_role_id=role.id)
        await _refresh_section(interaction, self.bot, "autorole", note=f"✅ Бот: {role.mention}")


class ApplyBotRoleButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Выдать боту сейчас", style=discord.ButtonStyle.primary, emoji="🤖", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.bot.user:
            await self.bot.autorole.apply_bot_autorole(interaction.guild, self.bot.user)
        await interaction.response.send_message("✅ Готово.", ephemeral=True)


# ── Conditional ───────────────────────────────────────────────────────────

class ConditionalSectionView(ConfigBaseView):
    section = "conditional"


async def _build_conditional_view(bot, guild: discord.Guild) -> ConditionalSectionView:
    view = ConditionalSectionView(bot)
    view.add_item(ConditionalAddButton(bot))
    rules = await bot.db.get_conditional_rules(guild.id)
    picker = ConditionalDeletePicker(bot)
    picker.options = [
        discord.SelectOption(label=f"#{r['id']} {r['name']}", value=str(r["id"]))
        for r in rules[:25]
    ] or [discord.SelectOption(label="Нет правил", value="_none")]
    view.add_item(picker)
    return view


class ConditionalAddButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Добавить правило", style=discord.ButtonStyle.success, emoji="➕", row=1)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ConditionalNameModal(self.bot))


class ConditionalNameModal(discord.ui.Modal, title="Новое правило"):
    name = discord.ui.TextInput(label="Название", placeholder="Ветеран → Доступ", max_length=48)

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        rule_name = self.name.value.strip()
        embed = discord.Embed(
            title="🧩 Выберите роли",
            description=(
                f"Правило: **{rule_name}**\n"
                "1️⃣ Целевая роль **(A)** — выдаётся\n"
                "2️⃣ Триггер **(B)** — должна быть у участника"
            ),
            color=0x4FC3F7,
        )
        await interaction.response.edit_message(
            embed=embed,
            view=ConditionalRolePickView(self.bot, rule_name),
            content=None,
        )


class ConditionalRolePickView(discord.ui.View):
    def __init__(self, bot, rule_name: str) -> None:
        super().__init__(timeout=TIMEOUT)
        self.bot = bot
        self.rule_name = rule_name
        self.target_id: int | None = None
        self.add_item(ConditionalTargetPicker(self))
        self.add_item(ConditionalTriggerPicker(self))
        self.add_item(ConditionalPickBackButton(bot))


class ConditionalPickBackButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Отмена", style=discord.ButtonStyle.secondary, emoji="◀", row=4)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await _refresh_section(interaction, self.bot, "conditional")


class ConditionalTargetPicker(discord.ui.RoleSelect):
    def __init__(self, parent: ConditionalRolePickView) -> None:
        super().__init__(placeholder="🎯 Целевая роль (A)…", max_values=1, row=0)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent.target_id = self.values[0].id
        await interaction.response.send_message(f"Цель: {self.values[0].mention}", ephemeral=True)


class ConditionalTriggerPicker(discord.ui.RoleSelect):
    def __init__(self, parent: ConditionalRolePickView) -> None:
        super().__init__(placeholder="⚡ Триггер-роль (B)…", max_values=1, row=1)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.parent.target_id:
            return await interaction.response.send_message(
                "Сначала выберите целевую роль.", ephemeral=True
            )
        await self.parent.bot.db.create_conditional_rule(
            interaction.guild.id,
            self.parent.rule_name,
            self.parent.target_id,
            [self.values[0].id],
        )
        await _refresh_section(
            interaction,
            self.parent.bot,
            "conditional",
            note=f"✅ Правило **{self.parent.rule_name}** создано.",
        )


class ConditionalDeletePicker(discord.ui.Select):
    def __init__(self, bot) -> None:
        self.bot = bot
        super().__init__(placeholder="🗑️ Удалить правило…", row=2, options=[
            discord.SelectOption(label="—", value="_")
        ])

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "_none":
            return await interaction.response.defer()
        await self.bot.db.delete_conditional_rule(int(self.values[0]))
        await _refresh_section(interaction, self.bot, "conditional", note="✅ Правило удалено.")


# ── Broadcast ─────────────────────────────────────────────────────────────

class BroadcastSectionView(ConfigBaseView):
    section = "broadcast"

    def __init__(self, bot, *, selected_source: int | None = None) -> None:
        super().__init__(bot)
        self.selected_source = selected_source


async def _build_broadcast_view(bot, guild: discord.Guild) -> BroadcastSectionView:
    view = BroadcastSectionView(bot)
    sources = await bot.db.list_broadcast_sources(guild.id)
    view.add_item(BroadcastAddButton(bot))
    picker = BroadcastSourcePicker(bot, view)
    picker.options = [
        discord.SelectOption(label=s["name"], value=str(s["id"]))
        for s in sources[:25]
    ] or [discord.SelectOption(label="Нет рассылок", value="_none")]
    view.add_item(picker)
    view.add_item(BroadcastWebhookButton(bot))
    return view


class BroadcastAddButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Новая рассылка", style=discord.ButtonStyle.success, emoji="➕", row=1)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Выберите **текстовый канал** для рассылки:",
            view=BroadcastChannelPickView(self.bot),
            ephemeral=True,
        )


class BroadcastChannelPickView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.add_item(BroadcastChannelSelect(bot))


class BroadcastChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, bot) -> None:
        super().__init__(
            placeholder="📢 Канал-источник…",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            max_values=1,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = self.values[0]
        await interaction.response.send_modal(BroadcastNameModal(self.bot, channel.id))


class BroadcastNameModal(discord.ui.Modal, title="Название рассылки"):
    name = discord.ui.TextInput(label="Название", placeholder="Объявления штаба", max_length=48)

    def __init__(self, bot, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.bot.db.create_broadcast_source(
            interaction.guild.id,
            self.channel_id,
            self.name.value.strip(),
        )
        await interaction.response.edit_message(
            content=f"✅ Рассылка **{self.name.value}** создана.",
            view=None,
        )
        # Refresh main panel if possible — user opened from ephemeral sub-message


class BroadcastSourcePicker(discord.ui.Select):
    def __init__(self, bot, parent: BroadcastSectionView) -> None:
        self.bot = bot
        self.parent = parent
        super().__init__(placeholder="Выберите рассылку…", row=2, options=[
            discord.SelectOption(label="—", value="_")
        ])

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "_none":
            return await interaction.response.defer()
        self.parent.selected_source = int(self.values[0])
        await interaction.response.send_message(
            f"Рассылка **#{self.values[0]}** выбрана. Нажмите **Webhook**.",
            ephemeral=True,
        )


class BroadcastWebhookButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Webhook", style=discord.ButtonStyle.primary, emoji="🔗", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        view: BroadcastSectionView = self.view  # type: ignore
        source_id = view.selected_source
        if not source_id:
            sources = await self.bot.db.list_broadcast_sources(interaction.guild.id)
            if len(sources) == 1:
                source_id = sources[0]["id"]
            else:
                return await interaction.response.send_message(
                    "Выберите рассылку в списке.", ephemeral=True
                )
        await interaction.response.send_modal(BroadcastWebhookModal(self.bot, source_id))


class BroadcastWebhookModal(discord.ui.Modal, title="Webhook фракции"):
    faction = discord.ui.TextInput(label="Название фракции", placeholder="Полиция", max_length=48)
    url = discord.ui.TextInput(label="Webhook URL", placeholder="https://discord.com/api/webhooks/…")

    def __init__(self, bot, source_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.source_id = source_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        url = self.url.value.strip()
        if not is_valid_discord_webhook(url):
            await interaction.response.send_message(
                "Неверный URL. Разрешены только Discord webhooks "
                "(https://discord.com/api/webhooks/…).",
                ephemeral=True,
            )
            return
        await self.bot.db.add_broadcast_target(
            self.source_id,
            self.faction.value.strip(),
            url,
        )
        await _refresh_section(
            interaction,
            self.bot,
            "broadcast",
            note=f"✅ Webhook **{self.faction.value}** добавлен.",
        )


# ── Voice ─────────────────────────────────────────────────────────────────

class VoiceSectionView(ConfigBaseView):
    section = "voice"

    def __init__(self, bot, *, pending_channel: int | None = None) -> None:
        super().__init__(bot)
        self.pending_channel = pending_channel


async def _build_voice_view(bot, guild: discord.Guild) -> VoiceSectionView:
    view = VoiceSectionView(bot)
    view.add_item(VoiceChannelSelect(bot))
    view.add_item(VoiceTemplateButton(bot))
    view.add_item(VoiceDisableButton(bot))
    return view


class VoiceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, bot) -> None:
        super().__init__(
            placeholder="🔊 Голосовой канал…",
            channel_types=[discord.ChannelType.voice, discord.ChannelType.stage_voice],
            max_values=1,
            row=1,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VoiceSectionView = self.view  # type: ignore
        view.pending_channel = self.values[0].id
        template = "╭・📡 ・Игроков на сервере: {count}"
        vc = await self.bot.db.get_voice_counter(interaction.guild.id)
        if vc:
            template = vc["name_template"]
        await self.bot.db.set_voice_counter(interaction.guild.id, view.pending_channel, template)
        await _refresh_section(
            interaction,
            self.bot,
            "voice",
            note=f"✅ Канал {self.values[0].mention} привязан.",
        )


class VoiceTemplateButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Шаблон имени", style=discord.ButtonStyle.primary, emoji="✏️", row=2)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(VoiceTemplateModal(self.bot))


class VoiceTemplateModal(discord.ui.Modal, title="Шаблон имени канала"):
    template = discord.ui.TextInput(
        label="Шаблон (обязательно {count})",
        default="╭・📡 ・Игроков на сервере: {count}",
        max_length=100,
    )

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tpl = self.template.value.strip()
        if "{count}" not in tpl:
            return await interaction.response.send_message(
                "Шаблон должен содержать `{count}`.", ephemeral=True
            )
        vc = await self.bot.db.get_voice_counter(interaction.guild.id)
        if not vc:
            return await interaction.response.send_message(
                "Сначала выберите голосовой канал.", ephemeral=True
            )
        await self.bot.db.set_voice_counter(interaction.guild.id, vc["channel_id"], tpl)
        await _refresh_section(interaction, self.bot, "voice", note="✅ Шаблон обновлён.")


class VoiceDisableButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Отключить", style=discord.ButtonStyle.danger, emoji="🚫", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.bot.db.disable_voice_counter(interaction.guild.id)
        await _refresh_section(interaction, self.bot, "voice", note="✅ Счётчик отключён.")


# ── ER:LC ─────────────────────────────────────────────────────────────────

class ErlcSectionView(ConfigBaseView):
    section = "erlc"


async def _build_erlc_view(bot, guild: discord.Guild) -> ErlcSectionView:
    view = ErlcSectionView(bot)
    view.add_item(ErlcKeyButton(bot))
    view.add_item(ErlcRefreshButton(bot))
    return view


class ErlcKeyButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="API ключ", style=discord.ButtonStyle.primary, emoji="🔑", row=1)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ErlcKeyModal(self.bot))


class ErlcKeyModal(discord.ui.Modal, title="ER:LC API ключ"):
    server_key = discord.ui.TextInput(
        label="Ключ приватного сервера",
        placeholder="Из настроек ER:LC",
        style=discord.TextStyle.short,
    )

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        key = self.server_key.value.strip()
        try:
            info = await self.bot.erlc.fetch_server_info_with_key(key)
        except Exception as exc:
            return await interaction.response.send_message(f"❌ Ошибка: {exc}", ephemeral=True)
        await self.bot.db.set_erlc_server(
            interaction.guild.id,
            key,
            info.get("name"),
        )
        note = f"✅ Подключён: **{info.get('name')}** ({info.get('players')}/{info.get('max_players')})"
        await _refresh_section(interaction, self.bot, "erlc", note=note)


class ErlcRefreshButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Обновить", style=discord.ButtonStyle.secondary, emoji="🔁", row=2)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await _refresh_section(interaction, self.bot, "erlc")


# ── Appearance ────────────────────────────────────────────────────────────

class AppearanceSectionView(ConfigBaseView):
    section = "appearance"


async def _build_appearance_view(bot, guild: discord.Guild) -> AppearanceSectionView:
    view = AppearanceSectionView(bot)
    for idx, (key, (_, label)) in enumerate(list(COLOR_PRESETS.items())[:5]):
        view.add_item(ColorPresetButton(bot, key, label, row=1 if idx < 3 else 2))
    view.add_item(BrandButton(bot))
    view.add_item(ToggleTimestampButton(bot))
    view.add_item(ResetAppearanceButton(bot))
    return view


class ColorPresetButton(discord.ui.Button):
    def __init__(self, bot, preset_key: str, label: str, *, row: int) -> None:
        hex_color, _ = COLOR_PRESETS[preset_key]
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"color_{preset_key}",
            row=row,
        )
        self.bot = bot
        self.hex_color = hex_color

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.bot.db.update_embed_settings(
            interaction.guild.id,
            color_primary=self.hex_color,
        )
        await _refresh_section(
            interaction, self.bot, "appearance", note=f"✅ Цвет: `{self.hex_color}`"
        )


class BrandButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Бренд / Footer", style=discord.ButtonStyle.secondary, emoji="✏️", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(BrandModal(self.bot))


class BrandModal(discord.ui.Modal, title="Бренд и footer"):
    brand = discord.ui.TextInput(label="Название бренда", placeholder="RU:LC Systems", required=False)
    footer = discord.ui.TextInput(
        label="Footer embed",
        placeholder="RU:LC Systems · Operations",
        required=False,
    )

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        kwargs: dict = {}
        if self.brand.value.strip():
            kwargs["brand_name"] = self.brand.value.strip()
        if self.footer.value.strip():
            kwargs["footer_text"] = self.footer.value.strip()
        if kwargs:
            await self.bot.db.update_embed_settings(interaction.guild.id, **kwargs)
        await _refresh_section(interaction, self.bot, "appearance", note="✅ Оформление обновлено.")


class ToggleTimestampButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Timestamp", style=discord.ButtonStyle.secondary, emoji="🕐", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        row = await self.bot.db.get_embed_settings(interaction.guild.id)
        new_val = not bool(row["show_timestamp"])
        await self.bot.db.update_embed_settings(interaction.guild.id, show_timestamp=new_val)
        state = "включён" if new_val else "выключен"
        await _refresh_section(
            interaction, self.bot, "appearance", note=f"✅ Timestamp {state}."
        )


class ResetAppearanceButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(label="Сброс", style=discord.ButtonStyle.danger, emoji="↩️", row=3)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.bot.db.reset_embed_settings(interaction.guild.id)
        await _refresh_section(interaction, self.bot, "appearance", note="✅ Сброшено к стандарту.")


async def _build_tickets_view(bot, guild: discord.Guild) -> discord.ui.View:
    class TicketsConfigView(ConfigBaseView):
        section = "tickets"

        def __init__(self) -> None:
            super().__init__(bot)
            self.add_item(PublishTicketPanelButton(bot))
            self.add_item(TicketSettingsButton(bot))

    return TicketsConfigView()


class PublishTicketPanelButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(
            label="Опубликовать панель",
            style=discord.ButtonStyle.success,
            emoji="📨",
            row=1,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _allowed(interaction, self.bot):
            return await _deny(interaction)
        modal = TicketPanelChannelModal(self.bot)
        await interaction.response.send_modal(modal)


class TicketPanelChannelModal(discord.ui.Modal, title="Канал для панели тикетов"):
    channel_id = discord.ui.TextInput(
        label="ID текстового канала",
        placeholder="123456789012345678",
        required=True,
        max_length=20,
    )

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        try:
            cid = int(str(self.channel_id.value).strip())
        except ValueError:
            await interaction.response.send_message("Неверный ID.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(cid)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Канал не найден.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        msg = await self.bot.tickets.post_panel(interaction.guild, channel)
        await interaction.followup.send(
            f"✅ Панель: {channel.mention} · [ссылка]({msg.jump_url})",
            ephemeral=True,
        )


class TicketSettingsButton(discord.ui.Button):
    def __init__(self, bot) -> None:
        super().__init__(
            label="Настройки",
            style=discord.ButtonStyle.secondary,
            emoji="⚙️",
            row=1,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _allowed(interaction, self.bot):
            return await _deny(interaction)
        embed = await self.bot.embeds.ticket_settings_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
