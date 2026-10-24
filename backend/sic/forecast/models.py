"""Forecasting models: three baselines, two pooled ML models and one experiment.

Every model implements `forecast(history, origin, horizon)`:
  * `history` maps series ID -> values for weeks 0..origin-1 ONLY. The caller
    (`forecast_at`) truncates the arrays, so no model can read the future.
  * Forecasts are recursive: step h uses the model's own predictions for
    steps 1..h-1, never actual values.

ML models are pooled over all series. Each series is divided by its own scale
(mean absolute value over the last 52 training weeks before the origin), so
one model can learn from large and small series together.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from sic.forecast.calendar import week_features

SIMPLE_TO_COMPLEX = (
    "naive",
    "moving_average_4",
    "seasonal_naive",
    "ridge",
    "hist_gradient_boosting",
    "hist_gradient_boosting_lag52",
)


def series_scale(values: np.ndarray) -> float:
    recent = np.abs(values[-52:])
    scale = float(recent.mean()) if len(recent) else 0.0
    return scale if scale > 0 else 1.0


@dataclass
class Calendar:
    """Calendar features for every week index, including future weeks."""

    weeks: list[date]
    name: str
    matrix: np.ndarray = field(init=False)
    columns: list[str] = field(init=False)

    def __post_init__(self):
        rows = [week_features(w, self.name) for w in self.weeks]
        self.columns = list(rows[0])
        self.matrix = np.array([[r[c] for c in self.columns] for r in rows])


class Model:
    name = ""
    min_history = 1  # weeks of history needed before the first forecast target

    def available(self, origin: int) -> bool:
        return origin >= self.min_history

    def forecast(self, history: dict[str, np.ndarray], origin: int, horizon: int) -> dict:
        raise NotImplementedError


class Naive(Model):
    name = "naive"

    def forecast(self, history, origin, horizon):
        return {k: np.repeat(v[-1], horizon) for k, v in history.items()}


class MovingAverage(Model):
    name = "moving_average_4"
    min_history = 4

    def forecast(self, history, origin, horizon):
        return {k: np.repeat(v[-4:].mean(), horizon) for k, v in history.items()}


class SeasonalNaive(Model):
    """Same week last year; needs 52 weeks of history (h <= 52)."""

    name = "seasonal_naive"
    min_history = 52

    def forecast(self, history, origin, horizon):
        return {
            k: np.array([v[origin - 52 + h] for h in range(horizon)]) for k, v in history.items()
        }


class PooledML(Model):
    def __init__(self, name: str, estimator_factory, calendar: Calendar, cfg: dict, lag52=False):
        self.name = name
        self.factory = estimator_factory
        self.calendar = calendar
        self.lags = cfg["features"]["short_lags"]
        self.window = cfg["features"]["rolling_window"]
        self.lag52 = lag52
        first_target = max(max(self.lags), self.window)
        self.first_target = max(first_target, 52) if lag52 else first_target
        self.min_history = self.first_target + 1  # at least one training row
        self.fitted = None

    def features(self, scaled: np.ndarray, t: int) -> np.ndarray:
        """Inputs for target week t, from scaled values of weeks < t only."""
        past = scaled[t - self.window : t]
        row = [scaled[t - k] for k in self.lags] + [past.mean(), past.std()]
        if self.lag52:
            row.append(scaled[t - 52])
        return np.concatenate([row, self.calendar.matrix[t]])

    def fit(self, history: dict[str, np.ndarray], origin: int) -> None:
        X, y = [], []
        for values in history.values():
            scaled = values / series_scale(values)
            for t in range(self.first_target, origin):
                X.append(self.features(scaled, t))
                y.append(scaled[t])
        self.fitted = self.factory().fit(np.array(X), np.array(y))

    def forecast(self, history, origin, horizon):
        self.fit(history, origin)
        return self.predict(history, origin, horizon)

    def predict(self, history, origin, horizon):
        """Recursive forecast with the already-fitted estimator."""
        ids = list(history)
        scales = np.array([series_scale(history[k]) for k in ids])
        paths = [
            np.concatenate([history[k] / s, np.zeros(horizon)])
            for k, s in zip(ids, scales, strict=True)
        ]
        for h in range(horizon):
            t = origin + h
            X = np.array([self.features(p, t) for p in paths])
            step = self.fitted.predict(X)
            for p, value in zip(paths, step, strict=True):
                p[t] = value  # fed back into later steps
        return {k: p[origin:] * s for k, p, s in zip(ids, paths, scales, strict=True)}


def build_models(cfg: dict, calendar: Calendar) -> dict[str, Model]:
    ridge = cfg["models"]["ridge"]
    hgb = cfg["models"]["hist_gradient_boosting"]

    def make_ridge():
        return make_pipeline(StandardScaler(), Ridge(alpha=ridge["alpha"]))

    def make_hgb():
        return HistGradientBoostingRegressor(**hgb)

    models: list[Model] = [
        Naive(),
        MovingAverage(),
        SeasonalNaive(),
        PooledML("ridge", make_ridge, calendar, cfg),
        PooledML("hist_gradient_boosting", make_hgb, calendar, cfg),
        PooledML("hist_gradient_boosting_lag52", make_hgb, calendar, cfg, lag52=True),
    ]
    return {m.name: m for m in models}


def forecast_at(model: Model, series: dict[str, np.ndarray], origin: int, horizon: int) -> dict:
    """Forecast weeks origin..origin+horizon-1 using only weeks before `origin`."""
    history = {k: np.asarray(v[:origin], dtype=float).copy() for k, v in series.items()}
    return model.forecast(history, origin, horizon)
