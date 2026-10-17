"""Configuration models, presets, serialisation and hashing."""

from pathlib import Path

import pytest

from erdr.config import (
    ConfigFormat,
    ExperimentConfig,
    PresetName,
    config_hash,
    dumps,
    format_for,
    from_data,
    load_config,
    loads,
    matching_preset,
    plugin,
    preset,
    reading_notes,
    save_config,
)
from erdr.core.readings import CLOSEST, LITERAL
from erdr.errors import ConfigError
from tests.conftest import CONFIGS


def test_defaults_are_the_workbook_settings():
    config = ExperimentConfig()
    assert config.preprocessing.normalizer.name == "minmax"
    assert config.distance.metric.name == "auto"  # Zhuravlev on heterogeneous data (ADR-022)
    assert config.distance.type_metrics.for_type("heterogeneous").name == "zhuravlev"
    assert config.distance.type_metrics.for_type("quantitative").name == "manhattan"
    assert config.distance.type_metrics.for_type("nominal").name == "hamming"
    assert config.distance.decimals == 10
    assert config.erdr.k == 3
    assert config.erdr.epsilon == 0.001
    assert config.erdr.readings.to_readings() == LITERAL
    assert matching_preset(config) is PresetName.LITERAL
    assert reading_notes(config) == ()


def test_presets():
    closest = preset("closest")
    assert closest.erdr.readings.to_readings() == CLOSEST
    assert matching_preset(closest) is PresetName.CLOSEST
    assert [note.switch for note in reading_notes(closest)] == ["B", "z"]
    custom = closest.model_copy(
        update={
            "erdr": closest.erdr.model_copy(
                update={
                    "readings": closest.erdr.readings.model_copy(
                        update={"self_in_l": "excluded", "step5_return": "first-move"}
                    )
                }
            )
        }
    )
    assert matching_preset(custom) is None
    assert [note.switch for note in reading_notes(custom)] == ["A", "B", "C", "z"]


@pytest.mark.parametrize("fmt", list(ConfigFormat))
def test_round_trip_and_hash(fmt: ConfigFormat):
    config = preset("closest").model_copy(update={"description": "ρ test"})
    text = dumps(config, fmt)
    again = loads(text, fmt)
    assert again == config
    assert config_hash(again) == config_hash(config)
    if fmt is not ConfigFormat.JSON:
        assert "⚠ reading B" in text


def test_strictness():
    with pytest.raises(ConfigError, match=r"erdr.unknown"):
        from_data({"erdr": {"unknown": 1}})
    with pytest.raises(ConfigError, match="epsilon"):
        from_data({"erdr": {"epsilon": 0}})
    with pytest.raises(ConfigError, match="mapping"):
        from_data([1, 2])
    with pytest.raises(ConfigError, match="not valid YAML"):
        loads("a: [", "yaml")
    with pytest.raises(ConfigError, match="must not repeat"):
        from_data({"distance": {"features": ["x1", "x1"]}})
    with pytest.raises(ConfigError, match="must not be empty"):
        from_data({"distance": {"features": []}})
    assert from_data(None) == ExperimentConfig()
    assert from_data({"preprocessing": {"normalizer": "rank"}}).preprocessing.normalizer == plugin(
        "rank"
    )


def test_files(tmp_path: Path):
    path = save_config(preset(), tmp_path / "a.toml")
    assert load_config(path) == preset()
    with pytest.raises(ConfigError, match="already exists"):
        save_config(preset(), path)
    with pytest.raises(ConfigError, match="unknown configuration extension"):
        format_for(tmp_path / "a.ini")
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "missing.yaml")


@pytest.mark.parametrize("path", sorted(CONFIGS.glob("*.yaml")), ids=lambda p: p.name)
def test_shipped_configurations_are_valid(path: Path):
    config = load_config(path)
    assert config.schema_version == 1
