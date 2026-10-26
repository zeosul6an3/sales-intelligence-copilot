"""Operational overrides: built-in only, documented, own intervals, history untouched."""

import json

import numpy as np
import pytest

from sic.config import EVALUATION_DIR
from sic.data import storage
from sic.forecast import config, operational, pipeline

GOOD = """
[[override]]
dataset = "uci"
group = "total"
model = "seasonal_naive"
replaces = "hist_gradient_boosting"
decided_on = "2026-10-26"
decided_by = "project owner"
independent_evaluation = false
reason = "test"
evidence = "test"
"""


def write(tmp_path, text):
    path = tmp_path / "overrides.toml"
    path.write_text(text)
    return path


def test_override_applies_only_to_the_builtin_dataset(tmp_path):
    path = write(tmp_path, GOOD)
    assert operational.load_overrides("uci", path)["total"]["model"] == "seasonal_naive"
    assert operational.load_overrides("upload-0123456789ab", path) == {}


@pytest.mark.parametrize(
    "change, message",
    [
        (('dataset = "uci"', 'dataset = "upload-0123456789ab"'), "Only the built-in"),
        (
            ('model = "seasonal_naive"', 'model = "hist_gradient_boosting_lag52"'),
            "not an evaluated",
        ),
        (("independent_evaluation = false", "independent_evaluation = true"), "must state"),
        (('group = "total"', 'group = "everything"'), "Unknown group"),
    ],
)
def test_invalid_overrides_are_rejected(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        operational.load_overrides("uci", write(tmp_path, GOOD.replace(*change)))


def test_frozen_configuration_is_unchanged_since_selection():
    recorded = json.loads((EVALUATION_DIR / "forecast" / "uci" / "selection.json").read_text())
    assert recorded["config_sha256"] == config.load()["_sha256"]
    assert recorded["decision"]["total"]["selected"] == "hist_gradient_boosting"


def test_builtin_operational_forecast_uses_the_override_with_its_own_intervals(real_uci):
    if pipeline.load_evaluation("uci") is None or pipeline.load_operational("uci") is None:
        pytest.skip("Run scripts/train_forecast.py for all stages first")
    current = pipeline.load_operational("uci")
    evaluation = pipeline.load_evaluation("uci")
    total = current["groups"]["total"]
    assert total["model"] == "seasonal_naive" and total["override"] is not None
    assert total["frozen_selection"] == "hist_gradient_boosting"
    assert "not an independent evaluation" in total["evaluation_note"]
    # Intervals are calibrated on seasonal naive's own residuals, not HGB's.
    assert current["quantiles"]["total"] != evaluation["calibration_quantiles"]["total"]
    assert total["interval_calibration_n"] == {str(h): 13 - h for h in range(1, 9)}
    assert current["groups"]["products"]["model"] == "moving_average_4"
    assert current["groups"]["products"]["override"] is None

    fresh = pipeline.fresh_forecast("uci", "total", 2)
    data = pipeline.load_data("uci", config.load())
    expected = data.adjusted["total"][len(data.weeks) - 52 : len(data.weeks) - 50]
    np.testing.assert_allclose([p["forecast"] for p in fresh["points"]], expected)
    assert fresh["model_source"].startswith("override")


def test_upload_operational_model_is_its_own_frozen_selection(data_dir, make_upload):
    from .test_forecast_uploads import weekly_csv

    dataset = make_upload(weekly_csv(80))
    current = pipeline.run_all(dataset)
    evaluation = pipeline.load_evaluation(dataset)
    for group, g in current["groups"].items():
        assert g["override"] is None and g["source"] == "frozen validation selection"
        assert g["model"] == evaluation["decision"][group]["selected"]
    assert storage.dataset_dir(dataset).parent == data_dir / "uploads"
