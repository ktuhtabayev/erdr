"""Dataset summaries: sizes, feature types, classes and the k that ERDR can use."""

from __future__ import annotations

from dataclasses import dataclass

from erdr.core.k_rule import PermittedK, largest_defined_k, permitted_k
from erdr.core.readings import ZScope
from erdr.data.schema import Dataset, Label
from erdr.notation import class_name


@dataclass(frozen=True)
class DatasetSummary:
    """What ``erdr data info`` and the GUI's dataset page show."""

    name: str
    source: str | None
    m: int
    n: int
    classes: tuple[Label, ...]
    """Class labels in class order (K1, K2, …)."""
    class_sizes: tuple[int, ...]
    """|K1|, |K2|, …"""
    quantitative: tuple[str, ...]
    """Names of the features of set I."""
    nominal: tuple[str, ...]
    """Names of the features of set J."""
    permitted: PermittedK
    """The k rule: odd k from 3 to 2·min|Kᵢ| − 3."""
    largest_k: int
    """Largest k for which z(Sᵢ, k) exists (neighbours of any class)."""
    largest_k_own_class: int
    """Largest k for which z(Sᵢ, k) exists over the own class."""
    content_hash: str

    @property
    def shape(self) -> str:
        """``(7, 13, 2)``."""
        return f"({self.m}, {self.n}, {len(self.classes)})"

    @property
    def class_text(self) -> str:
        """``K1 = 1: 3 · K2 = 2: 4``."""
        return " · ".join(
            f"{class_name(i)} = {label}: {size}"
            for i, (label, size) in enumerate(zip(self.classes, self.class_sizes, strict=True))
        )


def summarize(dataset: Dataset) -> DatasetSummary:
    """Summarize ``dataset`` for display."""
    sizes = dataset.class_sizes
    present = [s for s in sizes if s > 0]
    names = dataset.feature_names
    quantitative = dataset.quantitative
    return DatasetSummary(
        name=dataset.name,
        source=dataset.source,
        m=dataset.m,
        n=dataset.n,
        classes=dataset.classes,
        class_sizes=sizes,
        quantitative=tuple(name for name, q in zip(names, quantitative, strict=True) if q),
        nominal=tuple(name for name, q in zip(names, quantitative, strict=True) if not q),
        permitted=permitted_k(present),
        largest_k=largest_defined_k(present, ZScope.ALL) if len(present) > 1 else 0,
        largest_k_own_class=(
            largest_defined_k(present, ZScope.OWN_CLASS) if len(present) > 1 else 0
        ),
        content_hash=dataset.content_hash(),
    )
