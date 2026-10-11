"""The design system of the desktop application — the template project's, shared (ADR-018).

One set of tokens per theme drives Qt's palette and the style sheet: the same colours, font size,
spacing and widget shapes as the desktop application of ``context-synthetic-recognition``, so the
author's applications look alike. Themes: light (default), dark, and *system*, which follows the
Windows light or dark mode with the matching palette. The tinted table cells keep their light
tints and dark ink in every theme — they carry the workbook's meaning (training sample, selected
object, …) and look the same on screen, in Excel and in the HTML report.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent / "assets"
"""Images the style sheet refers to."""
BASE_FONT_PT = 10.0
"""Font size at zoom 1.0 (points) — the template's."""
FONT_SCALES = (0.85, 1.0, 1.15, 1.3, 1.5, 1.75)
"""The steps of View → Zoom."""


class ThemeName(StrEnum):
    """The themes the user can choose (View menu)."""

    LIGHT = "light"
    """White surfaces, dark ink — the default."""
    DARK = "dark"
    """Dark surfaces, light ink."""
    SYSTEM = "system"
    """The light or the dark theme, as Windows is set."""


DEFAULT_THEME = ThemeName.LIGHT


@dataclass(frozen=True)
class Palette:
    """The colours of one theme (the template's tokens)."""

    name: str
    window: str
    surface: str
    surface_alt: str
    """Alternating table rows, the sidebar, the status bar."""
    border: str
    border_strong: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_text: str
    """Text on the accent colour."""
    header: str
    """Table headers."""
    hover: str
    disabled: str
    disabled_text: str
    warning_bg: str
    warning_border: str
    warning_text: str
    error_text: str


LIGHT = Palette(
    name="light",
    window="#f5f6f8",
    surface="#ffffff",
    surface_alt="#f3f5f8",
    border="#d0d4da",
    border_strong="#b6bcc6",
    text="#1f2430",
    text_muted="#5b6472",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    accent_pressed="#1e40af",
    accent_soft="#dbeafe",
    accent_text="#ffffff",
    header="#e8ebf0",
    hover="#eef2f7",
    disabled="#e9ecf0",
    disabled_text="#9aa2ae",
    warning_bg="#fff4e5",
    warning_border="#f0a030",
    warning_text="#7a4100",
    error_text="#b3261e",
)

DARK = Palette(
    name="dark",
    window="#1a1a19",
    surface="#232322",
    surface_alt="#2a2a28",
    border="#3a3a37",
    border_strong="#52514e",
    text="#f1f0ec",
    text_muted="#b0aea6",
    accent="#3987e5",
    accent_hover="#5a9cec",
    accent_pressed="#256abf",
    accent_soft="#1d3557",
    accent_text="#ffffff",
    header="#2f2f2d",
    hover="#323230",
    disabled="#2a2a28",
    disabled_text="#75736c",
    warning_bg="#3d2a10",
    warning_border="#c98500",
    warning_text="#ffd08a",
    error_text="#ff8a80",
)

PALETTES = {ThemeName.LIGHT: LIGHT, ThemeName.DARK: DARK}


def theme_name(value: object) -> ThemeName:
    """The theme for a stored or typed value; anything unknown gives the default (light)."""
    try:
        return ThemeName(str(value).strip().lower())
    except ValueError:
        return DEFAULT_THEME


def system_is_dark(app: QGuiApplication | None = None) -> bool:
    """Whether Windows is in dark mode (Qt 6.5 and later report it; light otherwise)."""
    application = app or QGuiApplication.instance()
    if not isinstance(application, QGuiApplication):
        return False
    hints = application.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    return bool(scheme is not None and scheme() == Qt.ColorScheme.Dark)


def resolve(name: object, app: QGuiApplication | None = None) -> Palette:
    """The palette a theme shows: *system* becomes light or dark as Windows is set."""
    chosen = theme_name(name)
    if chosen is ThemeName.SYSTEM:
        return DARK if system_is_dark(app) else LIGHT
    return PALETTES[chosen]


def qt_palette(colours: Palette) -> QPalette:
    """The palette for Qt's own drawing (check boxes, spin buttons, scroll bars of the style)."""
    roles = QPalette.ColorRole
    found = QPalette()
    for role, colour in (
        (roles.Window, colours.window),
        (roles.WindowText, colours.text),
        (roles.Base, colours.surface),
        (roles.AlternateBase, colours.surface_alt),
        (roles.Text, colours.text),
        (roles.Button, colours.surface),
        (roles.ButtonText, colours.text),
        (roles.ToolTipBase, colours.surface),
        (roles.ToolTipText, colours.text),
        (roles.PlaceholderText, colours.disabled_text),
        (roles.Highlight, colours.accent),
        (roles.HighlightedText, colours.accent_text),
        (roles.Link, colours.accent),
        (roles.Mid, colours.border),
        (roles.Dark, colours.border_strong),
        (roles.Light, colours.surface),
    ):
        found.setColor(role, QColor(colour))
    for role in (roles.Text, roles.WindowText, roles.ButtonText):
        found.setColor(QPalette.ColorGroup.Disabled, role, QColor(colours.disabled_text))
    return found


def font_points(scale: float) -> float:
    """The base font size at a zoom step."""
    return round(BASE_FONT_PT * scale, 2)


def stylesheet(colours: Palette, scale: float = 1.0) -> str:
    """The application style sheet for a palette and a zoom step (the template's)."""
    c = colours
    size = font_points(scale)
    small = round(size * 0.9, 2)
    large = round(size * 1.35, 2)
    check = (ASSETS / "check.svg").as_posix()
    return f"""
QWidget {{
    background-color: {c.window};
    color: {c.text};
    font-size: {size}pt;
}}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QToolTip {{
    background-color: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    padding: 4px 6px;
}}

/* ---- navigation */
QListWidget#sidebar {{
    background-color: {c.surface_alt};
    border: none;
    border-right: 1px solid {c.border};
    outline: 0;
    padding: 8px 0;
}}
QListWidget#sidebar::item {{
    padding: 9px 16px;
    border-left: 3px solid transparent;
}}
QListWidget#sidebar::item:hover {{ background-color: {c.hover}; }}
QListWidget#sidebar::item:selected {{
    background-color: {c.accent_soft};
    color: {c.text};
    border-left: 3px solid {c.accent};
    font-weight: 600;
}}

/* ---- text */
QLabel#pageTitle {{ font-size: {large}pt; font-weight: 600; }}
QLabel#pageHint, QLabel#note {{ color: {c.text_muted}; font-size: {small}pt; }}
QLabel#sectionTitle {{ font-weight: 600; }}
QLabel#badge {{
    background-color: {c.accent_soft};
    border: 1px solid {c.accent};
    border-radius: 9px;
    padding: 1px 9px;
    font-size: {small}pt;
}}
QLabel#warningBadge, QPushButton#warningBadge {{
    background-color: {c.warning_bg};
    color: {c.warning_text};
    border: 1px solid {c.warning_border};
    border-radius: 9px;
    padding: 1px 9px;
    font-size: {small}pt;
    font-weight: 600;
}}
QFrame#warningBox {{
    background-color: {c.warning_bg};
    border: 1px solid {c.warning_border};
    border-radius: 6px;
}}
QFrame#warningBox QLabel {{ color: {c.warning_text}; }}
QLabel#outcome {{
    background-color: {c.accent_soft};
    border: 1px solid {c.accent};
    border-radius: 6px;
    padding: 8px 14px;
}}

/* ---- cards */
QFrame#card, QGroupBox {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 8px;
}}
QGroupBox {{ margin-top: 12px; padding: 12px 10px 10px 10px; font-weight: 600; }}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    background-color: {c.window};
}}
QFrame#card QWidget, QGroupBox QWidget {{ background-color: transparent; font-weight: normal; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ border: none; }}

/* ---- inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit,
QFrame#card QLineEdit, QFrame#card QComboBox, QFrame#card QSpinBox, QFrame#card QDoubleSpinBox,
QGroupBox QLineEdit, QGroupBox QComboBox, QGroupBox QSpinBox, QGroupBox QDoubleSpinBox,
QGroupBox QPlainTextEdit {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 5px;
    padding: 3px 6px;
    selection-background-color: {c.accent};
    selection-color: {c.accent_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {c.accent};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {c.disabled};
    color: {c.disabled_text};
}}
QComboBox QAbstractItemView {{
    background-color: {c.surface};
    border: 1px solid {c.border_strong};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}

QCheckBox::indicator, QGroupBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {c.border_strong};
    border-radius: 3px;
    background-color: {c.surface};
}}
QCheckBox::indicator:hover, QGroupBox::indicator:hover {{ border: 1px solid {c.accent}; }}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{
    background-color: {c.accent};
    border: 1px solid {c.accent};
    image: url({check});
}}
QCheckBox::indicator:disabled, QGroupBox::indicator:disabled {{
    background-color: {c.disabled};
    border: 1px solid {c.border};
}}
QCheckBox {{ spacing: 7px; }}

/* ---- buttons */
QPushButton, QFrame#card QPushButton, QGroupBox QPushButton {{
    background-color: {c.surface};
    border: 1px solid {c.border_strong};
    border-radius: 5px;
    padding: 5px 14px;
}}
QPushButton:hover {{ background-color: {c.hover}; }}
QPushButton:pressed {{ background-color: {c.header}; }}
QPushButton:disabled {{ background-color: {c.disabled}; color: {c.disabled_text}; }}
QPushButton#primary, QFrame#card QPushButton#primary, QGroupBox QPushButton#primary {{
    background-color: {c.accent};
    color: {c.accent_text};
    border: 1px solid {c.accent};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {c.accent_hover}; }}
QPushButton#primary:pressed {{ background-color: {c.accent_pressed}; }}
QPushButton#primary:disabled {{
    background-color: {c.disabled};
    color: {c.disabled_text};
    border: 1px solid {c.border};
}}

/* ---- tables */
QTableView, QListWidget, QFrame#card QTableView, QGroupBox QTableView,
QGroupBox QListWidget, QFrame#card QListWidget {{
    background-color: {c.surface};
    alternate-background-color: {c.surface_alt};
    border: 1px solid {c.border};
    gridline-color: {c.border};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}
QHeaderView::section {{
    background-color: {c.header};
    color: {c.text};
    border: none;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    padding: 4px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background-color: {c.header}; border: none; }}
QListWidget::item:selected {{ background-color: {c.accent_soft}; color: {c.text}; }}

/* ---- tabs */
QTabWidget::pane {{ border: 1px solid {c.border}; border-radius: 4px; top: -1px; }}
QTabBar::tab {{
    background-color: transparent;
    color: {c.text_muted};
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {c.text}; }}
QTabBar::tab:selected {{ color: {c.text}; border-bottom: 2px solid {c.accent}; font-weight: 600; }}

/* ---- the rest */
QProgressBar {{
    background-color: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 5px;
    text-align: center;
    min-height: 16px;
}}
QProgressBar::chunk {{ background-color: {c.accent}; border-radius: 4px; }}
QPlainTextEdit#console {{ font-family: Consolas, "DejaVu Sans Mono", monospace; }}
QMenuBar {{ background-color: {c.window}; }}
QMenuBar::item:selected {{ background-color: {c.hover}; }}
QMenu {{ background-color: {c.surface}; border: 1px solid {c.border_strong}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px; }}
QMenu::item:selected {{ background-color: {c.accent_soft}; color: {c.text}; }}
QMenu::item:disabled {{ color: {c.disabled_text}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 4px 8px; }}
QStatusBar {{ background-color: {c.surface_alt}; border-top: 1px solid {c.border}; }}
QStatusBar QLabel {{ padding: 0 6px; }}
QSplitter::handle {{ background-color: {c.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QScrollBar:vertical {{ background: {c.window}; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: {c.window}; height: 12px; margin: 0; }}
QScrollBar::handle {{ background: {c.border_strong}; border-radius: 5px; min-height: 24px;
    min-width: 24px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {c.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""


def apply_theme(app: QGuiApplication, name: object, scale: float = 1.0) -> Palette:
    """Apply a theme and a zoom step to the whole application; returns the palette shown."""
    chosen = theme_name(name)
    hints = app.styleHints()
    scheme = {
        ThemeName.LIGHT: Qt.ColorScheme.Light,
        ThemeName.DARK: Qt.ColorScheme.Dark,
        ThemeName.SYSTEM: Qt.ColorScheme.Unknown,  # back to the Windows setting
    }[chosen]
    # Qt 6.8+: the native window frame (the title bar) follows the theme; set only on a change
    if hasattr(hints, "setColorScheme") and app.property("erdrColorScheme") != scheme.value:
        hints.setColorScheme(scheme)
        app.setProperty("erdrColorScheme", scheme.value)
    colours = resolve(chosen, app)
    # only what changes is applied: a new style sheet re-styles every widget of the application
    target = qt_palette(colours)
    if app.palette() != target:
        app.setPalette(target)
    if isinstance(app, QApplication):  # fonts and style sheets belong to the widgets application
        font = app.font()
        if font.pointSizeF() != font_points(scale):
            font.setPointSizeF(font_points(scale))
            app.setFont(font)
        sheet = stylesheet(colours, scale)
        if app.styleSheet() != sheet:
            app.setStyleSheet(sheet)
    return colours


def is_dark(palette: QPalette) -> bool:
    """Whether a palette draws light text on a dark window."""
    return palette.color(QPalette.ColorRole.Window).lightness() < 128
