"""Named presets and the readings that differ from the literal article text (ADR-004).

``literal`` (default)
    The literal reading of §1.1 on the workbook's settings; reproduces the ERDR workbook.
``closest``
    B = 2 (processed objects stop covering) with z(Sᵢ, k) from the own class — the reading
    closest to the article's Table 1 on all 270 objects (sheet *Article Table 1 Check*).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from erdr.config.models import ERDRConfig, ExperimentConfig, ReadingsConfig
from erdr.core.readings import CLOSEST, LITERAL, BlockedCover, SelfInL, Step5Return, ZScope


class PresetName(StrEnum):
    """Names of the built-in presets."""

    LITERAL = "literal"
    CLOSEST = "closest"


def preset(name: PresetName | str = PresetName.LITERAL) -> ExperimentConfig:
    """The configuration of a named preset."""
    chosen = PresetName(name)
    readings = LITERAL if chosen is PresetName.LITERAL else CLOSEST
    return ExperimentConfig(
        name=f"erdr-{chosen.value}",
        erdr=ERDRConfig(readings=ReadingsConfig.from_readings(readings)),
    )


def matching_preset(config: ExperimentConfig) -> PresetName | None:
    """The preset whose readings ``config`` uses, if any (other settings are free)."""
    readings = config.erdr.readings.to_readings()
    if readings == LITERAL:
        return PresetName.LITERAL
    if readings == CLOSEST:
        return PresetName.CLOSEST
    return None


@dataclass(frozen=True)
class ReadingNote:
    """A reading that differs from the literal article text."""

    switch: str
    """``A``, ``B``, ``C`` or ``z``."""
    statement: str
    """What the configuration does instead of the literal text."""


def reading_notes(config: ExperimentConfig) -> tuple[ReadingNote, ...]:
    """The switches of ``config`` that differ from the literal article reading.

    The CLI, the GUI and every export show them, so a non-literal result is never mistaken for
    the article's algorithm.
    """
    r = config.erdr.readings
    notes: list[ReadingNote] = []
    if r.self_in_l == SelfInL.EXCLUDED:
        notes.append(ReadingNote("A", "Sᵢ is never a member of its own L (A = 2)"))
    if r.blocked_cover == BlockedCover.DROPPED:
        notes.append(ReadingNote("B", "processed objects stop covering (B = 2)"))
    if r.step5_return == Step5Return.FIRST_MOVE:
        notes.append(ReadingNote("C", "Step 5 returns to Step 2 after the first move (C = 2)"))
    if r.z_scope == ZScope.OWN_CLASS:
        notes.append(ReadingNote("z", "z(Sᵢ, k) is taken over the own class only"))
    return tuple(notes)
