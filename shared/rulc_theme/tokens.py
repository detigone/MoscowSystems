"""Shared RU:LC Systems visual tokens for all Discord bots."""

from __future__ import annotations

from dataclasses import dataclass

NETWORK = "RU:LC Systems"

PRODUCT_ROBLOX = "Roblox"
PRODUCT_OPERATIONS = "Operations"
PRODUCT_CYCLERM = "CycleRM"


@dataclass(frozen=True)
class Palette:
    neutral: int = 0x2B2D31
    primary: int = 0x4FC3F7
    primary_dark: int = 0x0288D1
    success: int = 0x57F287
    warning: int = 0xFEE75C
    danger: int = 0xED4245
    info: int = 0x00A8FC


PALETTE = Palette()

HEX_PRIMARY = "#2B2D31"
HEX_NEUTRAL = "#2B2D31"
HEX_SUCCESS = "#57F287"
HEX_WARNING = "#FEE75C"
HEX_DANGER = "#ED4245"
HEX_INFO = "#00A8FC"

DEFAULT_BRAND = NETWORK
DEFAULT_FOOTER_ROBLOX = f"{NETWORK} · {PRODUCT_ROBLOX}"
DEFAULT_FOOTER_OPERATIONS = f"{NETWORK} · {PRODUCT_OPERATIONS}"
DEFAULT_FOOTER_CYCLERM = f"{NETWORK} · {PRODUCT_CYCLERM}"
