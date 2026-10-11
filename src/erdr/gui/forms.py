"""Parameter forms generated from a plug-in's parameter type.

Every normalizer or metric with parameters declares a frozen pydantic dataclass; this module
builds an editor from its fields (numbers, flags, lists of numbers), with the bounds of the
field's constraints. A plug-in added later gets its form without any GUI code.
"""

from __future__ import annotations

import typing
from typing import Any

import annotated_types
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from erdr.core.registry import Registry

_HUGE = 1e9


def _bounds(metadata: list[Any]) -> tuple[float, float]:
    low, high = -_HUGE, _HUGE
    for item in metadata:
        if isinstance(item, annotated_types.Ge | annotated_types.Gt):
            low = float(getattr(item, "ge", getattr(item, "gt", low)))
        if isinstance(item, annotated_types.Le | annotated_types.Lt):
            high = float(getattr(item, "le", getattr(item, "lt", high)))
    return low, high


class ParamsForm(QWidget):
    """Editors for the parameters of one plug-in (empty when it takes none)."""

    changed = Signal()
    """A value was edited."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty form; :meth:`set_plugin` fills it."""
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(16, 0, 0, 0)
        self._editors: dict[str, QWidget] = {}
        self._defaults: dict[str, Any] = {}

    def set_plugin(self, registry: Registry[Any], name: str, values: dict[str, Any]) -> None:
        """Show the parameters of plug-in ``name`` with ``values`` (defaults for the rest)."""
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors.clear()
        self._defaults.clear()
        params_type = registry.info(name).params_type
        if params_type is None:
            return
        fields = getattr(params_type, "__pydantic_fields__", {})
        for field_name, info in fields.items():
            default = info.default
            self._defaults[field_name] = default
            value = values.get(field_name, default)
            editor = self._editor(info.annotation, info.metadata, value)
            self._editors[field_name] = editor
            label = QLabel(field_name.replace("_", " "))
            if info.description:
                label.setToolTip(info.description)
            self._layout.addRow(label, editor)

    def _editor(self, annotation: Any, metadata: list[Any], value: Any) -> QWidget:
        origin = typing.get_origin(annotation)
        if annotation is bool:
            box = QCheckBox()
            box.setChecked(bool(value))
            box.toggled.connect(self.changed)
            return box
        if annotation is int:
            spin = QSpinBox()
            low, high = _bounds(metadata)
            spin.setRange(int(max(low, -(2**31) + 1)), int(min(high, 2**31 - 1)))
            spin.setValue(int(value))
            spin.valueChanged.connect(self.changed)
            return spin
        if annotation is float:
            spin_f = QDoubleSpinBox()
            low, high = _bounds(metadata)
            spin_f.setDecimals(6)
            spin_f.setRange(low, high)
            spin_f.setValue(float(value))
            spin_f.valueChanged.connect(self.changed)
            return spin_f
        line = QLineEdit()
        if origin is tuple:
            line.setPlaceholderText("comma-separated numbers (empty: default)")
            line.setText(", ".join(str(v) for v in value))
        else:
            line.setText("" if value is None else str(value))
        line.editingFinished.connect(self.changed)
        return line

    def values(self) -> dict[str, Any]:
        """The parameters that differ from their defaults (JSON-compatible)."""
        out: dict[str, Any] = {}
        for name, editor in self._editors.items():
            if isinstance(editor, QCheckBox):
                value: Any = editor.isChecked()
            elif isinstance(editor, QSpinBox | QDoubleSpinBox):
                value = editor.value()
            elif isinstance(editor, QLineEdit):
                text = editor.text().strip()
                default = self._defaults[name]
                if isinstance(default, tuple):
                    value = tuple(float(p) for p in text.replace(";", ",").split(",") if p.strip())
                else:
                    value = text
            else:  # pragma: no cover - every editor type is handled above
                continue
            if value != self._defaults[name]:
                out[name] = list(value) if isinstance(value, tuple) else value
        return out
