"""What the desktop application remembers between sessions (the user's registry, ``erdr/erdr``).

The theme, the zoom and the window's geometry. Tests and the self-test pass their own store (an
ini file), so they never touch the user's settings.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

from erdr.gui.theme import FONT_SCALES, ThemeName, theme_name

ORGANIZATION = "erdr"
APPLICATION = "erdr"


class Settings:
    """Typed access to the stored settings."""

    def __init__(self, store: QSettings | None = None) -> None:
        """Use ``store``, or the user's settings of the application."""
        self.store = store if store is not None else QSettings(ORGANIZATION, APPLICATION)

    @property
    def theme(self) -> ThemeName:
        """The chosen theme (light by default)."""
        return theme_name(self.store.value("appearance/theme", ThemeName.LIGHT.value))

    @theme.setter
    def theme(self, name: ThemeName | str) -> None:
        self.store.setValue("appearance/theme", theme_name(name).value)

    @property
    def font_scale(self) -> float:
        """Zoom of the interface (one of :data:`~erdr.gui.theme.FONT_SCALES`)."""
        try:
            value = float(str(self.store.value("appearance/font_scale", 1.0)))
        except ValueError:
            return 1.0
        return value if value in FONT_SCALES else 1.0

    @font_scale.setter
    def font_scale(self, scale: float) -> None:
        self.store.setValue("appearance/font_scale", scale)

    def geometry(self) -> QByteArray | None:
        """The window geometry of the last session, if any."""
        value = self.store.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def save_geometry(self, geometry: QByteArray) -> None:
        """Remember the window geometry."""
        self.store.setValue("window/geometry", geometry)

    def sync(self) -> None:
        """Write pending changes to the store."""
        self.store.sync()
