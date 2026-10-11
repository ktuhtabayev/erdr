"""Registry, normalizers, metrics and Step 0 (the distance pipeline)."""

import numpy as np
import pytest

from erdr.core.distances import compute_distances, select_features
from erdr.core.metrics import METRICS, traits, traits_of
from erdr.core.neighbours import neighbour_order, rank_matrix
from erdr.core.normalizers import NORMALIZERS, decimal_power
from erdr.core.registry import Registry, normalize_name
from erdr.errors import ConfigError, RegistryError

X = np.array([[1.0, 0.0, 10.0], [2.0, 1.0, 10.0], [4.0, 1.0, 30.0], [8.0, 2.0, 20.0]])
QUANT = np.array([True, False, True])


# ---------------------------------------------------------------- registry


def test_registry_names_aliases_and_errors():
    registry: Registry[int] = Registry("things")
    registry.add("My Thing", 1, aliases=("other_name",), summary="one")
    assert normalize_name(" My_Thing ") == "my-thing"
    assert registry.get("my-thing") == 1
    assert registry.get("OTHER NAME") == 1
    assert "my thing" in registry
    assert 3 not in registry
    assert len(registry) == 1
    assert "things" in repr(registry)
    assert registry.entry_point_group == "erdr.things"
    with pytest.raises(RegistryError, match="already registered"):
        registry.add("my-thing", 2)
    registry.add("my-thing", 2, replace=True)
    assert registry.get("my-thing") == 2
    with pytest.raises(RegistryError, match="Available: my-thing"):
        registry.get("missing")
    with pytest.raises(RegistryError):
        normalize_name("  ")
    assert registry.load_entry_points() == 0


def test_registry_parameter_validation():
    with pytest.raises(ConfigError, match="takes no parameters"):
        METRICS.make_params("zhuravlev", {"p": 2})
    with pytest.raises(ConfigError, match="invalid parameters"):
        METRICS.make_params("minkowski", {"p": 0.5})
    assert METRICS.make_params("minkowski", {"p": 2}).p == 2
    assert METRICS.make_params("zhuravlev") is None


# ---------------------------------------------------------------- normalizers


@pytest.mark.parametrize("name", NORMALIZERS.names())
def test_every_normalizer_keeps_nominal_codes(name: str):
    scaling = NORMALIZERS.get(name)(X, QUANT, NORMALIZERS.make_params(name))
    Z = scaling.transform(X)
    assert Z.shape == X.shape
    assert np.array_equal(Z[:, 1], X[:, 1])
    assert np.all(np.isfinite(Z))


def test_minmax_maps_to_unit_interval_and_constant_to_zero():
    data = np.array([[1.0, 5.0], [3.0, 5.0], [2.0, 5.0]])
    scaling = NORMALIZERS.get("minmax")(data, np.array([True, True]), None)
    Z = scaling.transform(data)
    assert Z[:, 0].tolist() == [0.0, 1.0, 0.5]
    assert Z[:, 1].tolist() == [0.0, 0.0, 0.0]
    assert scaling.statistics["min"].tolist() == [1.0, 5.0]
    with pytest.raises(ValueError, match="features"):
        scaling.transform(np.zeros((1, 3)))


def test_other_normalizers():
    z = NORMALIZERS.get("z-score")(X, QUANT, NORMALIZERS.make_params("z-score")).transform(X)
    assert z[:, 0].mean() == pytest.approx(0.0)
    assert z[:, 0].std(ddof=1) == pytest.approx(1.0)
    r = NORMALIZERS.get("rank")(X, QUANT, None).transform(X)
    assert r[:, 0].tolist() == [0.0, 1 / 3, 2 / 3, 1.0]
    m = NORMALIZERS.get("max-abs")(X, QUANT, None).transform(X)
    assert m[:, 0].max() == 1.0
    u = NORMALIZERS.get("unit-length")(X, QUANT, None).transform(X)
    assert np.allclose(np.linalg.norm(u[:, QUANT], axis=1), 1.0)
    d = NORMALIZERS.get("decimal-scaling")(X, QUANT, None).transform(X)
    assert np.abs(d[:, QUANT]).max() < 1.0
    assert decimal_power(0.0) == 0
    assert decimal_power(100.0) == 3
    assert decimal_power(99.0) == 2


# ---------------------------------------------------------------- metrics


@pytest.mark.parametrize("name", METRICS.names())
def test_every_metric_is_a_symmetric_distance(name: str):
    domain = traits_of(METRICS.get(name)).domain
    result = compute_distances(X, QUANT, metric=name)
    D = result.matrix
    assert D.shape == (4, 4)
    assert np.array_equal(D, D.T)
    assert np.all(np.diag(D) == 0.0)
    assert np.all(D >= 0.0)
    expected = {"any": [0, 1, 2], "quantitative": [0, 2], "nominal": [1]}[domain]
    assert result.features.tolist() == expected


def test_zhuravlev_parts_and_relations():
    zh = compute_distances(X, QUANT)
    assert zh.quantitative_part is not None
    assert zh.nominal_part is not None
    assert np.allclose(zh.matrix, zh.quantitative_part + zh.nominal_part)
    weighted = compute_distances(X, QUANT, metric="weighted-zhuravlev")
    assert np.array_equal(weighted.matrix, zh.matrix)  # every weight 1 → bit for bit
    gower = compute_distances(X, QUANT, metric="gower")
    assert np.allclose(gower.matrix, zh.matrix / 3)
    assert compute_distances(X, QUANT, metric="euclidean").quantitative_part is None
    m1 = compute_distances(X, QUANT, metric="minkowski", metric_params={"p": 1})
    assert np.allclose(m1.matrix, compute_distances(X, QUANT, metric="manhattan").matrix)
    assert compute_distances(X, QUANT, metric="hamming").matrix[0, 3] == 1.0


def test_weighted_zhuravlev_weights():
    weighted = compute_distances(
        X, QUANT, metric="weighted-zhuravlev", metric_params={"nominal_weight": 0.0}
    )
    plain = compute_distances(X, QUANT, features="quantitative")
    assert np.allclose(weighted.matrix, plain.matrix)
    with pytest.raises(ConfigError, match="feature weights"):
        compute_distances(
            X, QUANT, metric="weighted-zhuravlev", metric_params={"feature_weights": [1.0]}
        )
    with pytest.raises(ConfigError):
        METRICS.make_params("weighted-zhuravlev", {"feature_weights": [-1.0, 1.0, 1.0]})


def test_traits_of_an_undeclared_metric_is_heterogeneous():
    def plain(*args):  # pragma: no cover - never called
        return None

    assert traits_of(plain).domain == "any"
    decorated = traits(domain="nominal")(plain)
    assert traits_of(decorated).domain == "nominal"


# ---------------------------------------------------------------- Step 0


def test_feature_selection():
    assert select_features(QUANT, "all").tolist() == [0, 1, 2]
    assert select_features(QUANT, "quantitative").tolist() == [0, 2]
    assert select_features(QUANT, "nominal").tolist() == [1]
    assert select_features(QUANT, [2, 0]).tolist() == [2, 0]
    with pytest.raises(ConfigError, match="nominal features x2"):
        select_features(QUANT, "all", domain="quantitative")
    with pytest.raises(ConfigError, match="quantitative features x1"):
        select_features(QUANT, [0, 1], domain="nominal")
    with pytest.raises(ConfigError, match="out of range"):
        select_features(QUANT, [5])
    with pytest.raises(ConfigError, match="repeats"):
        select_features(QUANT, [0, 0])
    with pytest.raises(ConfigError, match="empty"):
        select_features(np.array([True, True]), "nominal")
    with pytest.raises(ConfigError, match="unknown"):
        select_features(QUANT, "most")  # type: ignore[arg-type]


def test_compute_distances_checks_the_types():
    with pytest.raises(ConfigError, match="feature types"):
        compute_distances(X, np.array([True]))


def test_neighbour_order_breaks_ties_by_index():
    D = np.array([[0, 1, 1, 2], [1, 0, 2, 1], [1, 2, 0, 1], [2, 1, 1, 0]], dtype=float)
    order = neighbour_order(D)
    assert order[0].tolist() == [1, 2, 3]
    assert order[3].tolist() == [1, 2, 0]
    ranks = rank_matrix(order)
    assert ranks[0].tolist() == [0, 1, 2, 3]
    restricted = neighbour_order(D, allowed=np.array([[True, False, True, False]] * 4))
    assert restricted[0].tolist() == [2, -1, -1]
