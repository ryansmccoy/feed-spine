"""Tests for feedspine.storage.data_types module.

Covers DataType enum, DataTypeConfig frozen dataclass, and
the DATA_TYPE_CONFIGS lookup table.
"""

from __future__ import annotations

import pytest

from feedspine.storage.data_types import DATA_TYPE_CONFIGS, DataType, DataTypeConfig


class TestDataType:
    """Tests for the DataType enum."""

    def test_all_expected_members_exist(self):
        expected = {
            "OBSERVATIONS",
            "EVENTS",
            "ENTITIES",
            "DOCUMENTS",
            "PRICES",
            "AUTO_DETECT",
            "GENERIC",
        }
        actual = {m.name for m in DataType}
        assert expected.issubset(actual), f"Missing members: {expected - actual}"

    def test_values_are_strings(self):
        for dt in DataType:
            assert isinstance(dt.value, str)

    def test_enum_from_value(self):
        assert (
            DataType("observations") == DataType.OBSERVATIONS
            or DataType(DataType.OBSERVATIONS.value) == DataType.OBSERVATIONS
        )


class TestDataTypeConfig:
    """Tests for the DataTypeConfig frozen dataclass."""

    def test_is_frozen(self):
        cfg = DataTypeConfig(data_type=DataType.GENERIC)
        with pytest.raises(AttributeError):
            cfg.partition_by = "year"  # type: ignore[misc]

    def test_construction_with_data_type(self):
        cfg = DataTypeConfig(data_type=DataType.OBSERVATIONS)
        assert cfg is not None
        assert cfg.data_type == DataType.OBSERVATIONS


class TestDataTypeConfigsLookup:
    """Tests for the DATA_TYPE_CONFIGS dict."""

    def test_all_data_types_have_config(self):
        for dt in DataType:
            if dt == DataType.AUTO_DETECT:
                continue  # AUTO_DETECT may not have a static config
            assert dt in DATA_TYPE_CONFIGS, f"No config for {dt.name}"

    def test_configs_are_datatype_config_instances(self):
        for dt, cfg in DATA_TYPE_CONFIGS.items():
            assert isinstance(cfg, DataTypeConfig), f"Config for {dt.name} is {type(cfg)}"
