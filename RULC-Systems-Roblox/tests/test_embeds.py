from __future__ import annotations

from bot.services.embeds import (
    build_search_alerts,
    format_points_bar,
    format_points_total,
    risk_emoji,
    risk_level,
)


def test_format_points_total_zero():
    assert format_points_total(0) == "Баллов нет"


def test_format_points_total_positive():
    assert "4" in format_points_total(4)


def test_format_points_bar():
    assert "▰" in format_points_bar(15)
    assert format_points_bar(0) == "▱" * 10


def test_risk_emoji_scale():
    assert risk_emoji(0) == "⚪"
    assert risk_emoji(20) == "🔴"


def test_risk_level_labels_ru():
    assert risk_level(0).label == "Чистый"
    assert risk_level(12).label == "Высокий"


def test_build_search_alerts_no_triggers():
    text = build_search_alerts(
        {"friendCount": 50, "created": "2019-05-12T00:00:00Z"},
        [],
        total_points=0,
    )
    assert "Нет алертов" in text
