"""
Revenue Forecasting Plugin for Predictor.

Forecasts future revenue from a historical date+revenue series using Prophet
(preferred) and falling back to statsmodels SARIMAX when Prophet is not
installable on the target machine. When optional `segment` or `product_line`
columns are present, one model is trained per group; otherwise a single
global series is fit.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml_plugins.base import MLPluginBase

try:
    from prophet import Prophet
    _HAS_PROPHET = True
except Exception:
    _HAS_PROPHET = False

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    _HAS_SARIMAX = True
except Exception:
    _HAS_SARIMAX = False


_REQUIRED_COLS = [
    {"column": "date",    "type": "date",  "description": "Observation date (YYYY-MM-DD or any pandas-parseable format)"},
    {"column": "revenue", "type": "float", "description": "Numeric revenue for that date"},
]

_OPTIONAL_COLS = [
    {"column": "segment",      "type": "string", "description": "Optional grouping column — one model is trained per segment"},
    {"column": "product_line", "type": "string", "description": "Optional grouping column — one model is trained per product line"},
]

_DEFAULT_HORIZON = 30


class RevenueForecastingPlugin(MLPluginBase):
    plugin_id          = "revenue_forecasting"
    plugin_name        = "Revenue Forecasting"
    plugin_description = (
        "Forecasts future revenue from a historical date+revenue series using "
        "Prophet (with statsmodels SARIMAX fallback). Detects per-segment / "
        "per-product seasonality and flags forecast periods that deviate "
        "significantly from the trend baseline."
    )
    plugin_category    = "prediction"
    plugin_icon        = "trending-up"
    required_files     = [
        {
            "key":         "revenue",
            "label":       "Revenue history CSV",
            "description": "date + revenue (optional segment, product_line)",
        }
    ]

    # ------------------------------------------------------------------
    # Schema & validation
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        return {
            "revenue": {
                "required": _REQUIRED_COLS,
                "optional": _OPTIONAL_COLS,
            }
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "revenue":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        errors, warnings = [], []
        cols = set(df.columns)

        if "date" not in cols:
            errors.append("Missing required column: 'date'")
        if "revenue" not in cols:
            errors.append("Missing required column: 'revenue'")

        if "date" in cols:
            parsed = pd.to_datetime(df["date"], errors="coerce")
            if parsed.isna().all():
                errors.append("Column 'date' could not be parsed as dates")
            elif parsed.isna().any():
                warnings.append(f"{int(parsed.isna().sum())} 'date' values failed to parse and will be dropped")

        if "revenue" in cols:
            num = pd.to_numeric(df["revenue"], errors="coerce")
            if num.isna().all():
                errors.append("Column 'revenue' is not numeric")
            elif num.isna().any():
                warnings.append(f"{int(num.isna().sum())} 'revenue' values are not numeric")

        if len(df) < 30:
            warnings.append(f"Only {len(df)} rows — at least 60+ observations recommended for stable forecasts")

        if "segment" not in cols and "product_line" not in cols:
            warnings.append("No 'segment' or 'product_line' column — fitting a single global model")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prepare(self, df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str]:
        """Return (clean_df, group_col, freq) sorted by date and aggregated to one row per (group, date)."""
        out = df.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out["revenue"] = pd.to_numeric(out["revenue"], errors="coerce")
        out = out.dropna(subset=["date", "revenue"])

        group_col = "segment" if "segment" in out.columns else ("product_line" if "product_line" in out.columns else None)

        agg_keys = ["date"] + ([group_col] if group_col else [])
        out = out.groupby(agg_keys, as_index=False)["revenue"].sum().sort_values(agg_keys)

        sample = out if group_col is None else out[out[group_col] == out[group_col].iloc[0]]
        inferred = pd.infer_freq(sample["date"]) if len(sample) >= 3 else None
        freq = inferred or "D"

        return out, group_col, freq

    def _fit_one(self, series: pd.DataFrame, freq: str):
        """Fit a forecaster on a single (date, revenue) series. Returns dict describing the fitted model."""
        s = series.rename(columns={"date": "ds", "revenue": "y"})[["ds", "y"]].sort_values("ds")

        if _HAS_PROPHET and len(s) >= 10:
            model = Prophet(
                interval_width=0.95,
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=len(s) >= 365,
            )
            model.fit(s)
            return {"backend": "prophet", "model": model, "history": s, "freq": freq}

        if _HAS_SARIMAX and len(s) >= 10:
            ts = s.set_index("ds")["y"].asfreq(freq).interpolate()
            seasonal_period = {"D": 7, "W": 52, "M": 12, "MS": 12, "Q": 4, "QS": 4, "Y": 1, "A": 1}.get(freq, 7)
            try:
                model = SARIMAX(
                    ts, order=(1, 1, 1),
                    seasonal_order=(1, 1, 1, seasonal_period) if len(ts) >= 2 * seasonal_period else (0, 0, 0, 0),
                    enforce_stationarity=False, enforce_invertibility=False,
                ).fit(disp=False)
            except Exception:
                model = SARIMAX(ts, order=(1, 1, 1)).fit(disp=False)
            return {"backend": "sarimax", "model": model, "history": s, "freq": freq}

        # Last-resort naive: mean + std
        return {"backend": "naive", "mean": float(s["y"].mean()), "std": float(s["y"].std() or 1.0),
                "history": s, "freq": freq}

    def _forecast_one(self, fitted: dict, horizon: int) -> pd.DataFrame:
        """Return DataFrame with columns: ds, yhat, yhat_lower, yhat_upper."""
        backend = fitted["backend"]
        history = fitted["history"]
        freq = fitted["freq"]

        if backend == "prophet":
            future = fitted["model"].make_future_dataframe(periods=horizon, freq=freq, include_history=False)
            fc = fitted["model"].predict(future)
            return fc[["ds", "yhat", "yhat_lower", "yhat_upper", "trend"]].copy()

        if backend == "sarimax":
            res = fitted["model"].get_forecast(steps=horizon)
            mean = res.predicted_mean
            ci = res.conf_int(alpha=0.05)
            ds = pd.date_range(start=history["ds"].iloc[-1], periods=horizon + 1, freq=freq)[1:]
            trend = pd.Series(np.linspace(history["y"].iloc[-min(len(history), 30):].mean(),
                                          float(mean.iloc[-1]), horizon), index=ds)
            return pd.DataFrame({
                "ds": ds,
                "yhat": mean.values,
                "yhat_lower": ci.iloc[:, 0].values,
                "yhat_upper": ci.iloc[:, 1].values,
                "trend": trend.values,
            })

        # Naive
        ds = pd.date_range(start=history["ds"].iloc[-1], periods=horizon + 1, freq=freq)[1:]
        m, s = fitted["mean"], fitted["std"]
        return pd.DataFrame({
            "ds": ds,
            "yhat": [m] * horizon,
            "yhat_lower": [m - 1.96 * s] * horizon,
            "yhat_upper": [m + 1.96 * s] * horizon,
            "trend": [m] * horizon,
        })

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = data["revenue"].copy()
        clean, group_col, freq = self._prepare(df)

        if len(clean) < 5:
            raise ValueError("Need at least 5 valid (date, revenue) observations to train a forecast model.")

        groups = ["__global__"] if group_col is None else sorted(clean[group_col].astype(str).unique().tolist())

        fitted_models = {}
        in_sample_metrics = {}
        for g in groups:
            sub = clean if group_col is None else clean[clean[group_col].astype(str) == g]
            if len(sub) < 5:
                continue
            fitted = self._fit_one(sub, freq)
            fitted_models[g] = fitted

            n = len(sub)
            n_test = max(1, int(n * 0.2))
            train_sub, test_sub = sub.iloc[:-n_test], sub.iloc[-n_test:]
            if len(train_sub) >= 5:
                tmp = self._fit_one(train_sub, freq)
                fc = self._forecast_one(tmp, len(test_sub))
                actual = test_sub["revenue"].values
                pred = fc["yhat"].values[:len(actual)]
                mape = float(np.mean(np.abs((actual - pred) / np.where(actual == 0, 1, actual))) * 100)
                in_sample_metrics[g] = {"mape": round(mape, 2), "n_test": int(len(test_sub))}

        if not fitted_models:
            raise ValueError("No group had enough data to train a forecast model.")

        backend_used = next(iter(fitted_models.values()))["backend"]

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(fitted_models, model_dir / "forecasters.joblib")
        joblib.dump({
            "group_col": group_col,
            "groups": groups,
            "freq": freq,
            "backend": backend_used,
            "horizon_default": _DEFAULT_HORIZON,
            "metrics": in_sample_metrics,
        }, model_dir / "training_stats.joblib")

        return {
            "n_samples":     int(len(clean)),
            "n_groups":      len(fitted_models),
            "group_col":     group_col,
            "freq":          freq,
            "backend":       backend_used,
            "horizon":       _DEFAULT_HORIZON,
            "metrics":       in_sample_metrics,
            "training_mode": "incremental" if base_model_dir else "full",
        }

    # ------------------------------------------------------------------
    # Detection / Forecasting
    # ------------------------------------------------------------------

    def detect(self, data: dict, model_dir: Path) -> dict:
        forecasters = joblib.load(model_dir / "forecasters.joblib")
        stats       = joblib.load(model_dir / "training_stats.joblib")

        group_col = stats["group_col"]
        horizon   = stats.get("horizon_default", _DEFAULT_HORIZON)

        # If new history was supplied, refit Prophet incrementally for matching groups
        if "revenue" in data and data["revenue"] is not None and len(data["revenue"]) > 0:
            clean, _, freq = self._prepare(data["revenue"])
            groups = ["__global__"] if group_col is None else sorted(clean[group_col].astype(str).unique().tolist())
            for g in groups:
                sub = clean if group_col is None else clean[clean[group_col].astype(str) == g]
                if len(sub) >= 5:
                    forecasters[g] = self._fit_one(sub, freq)

        all_rows = []
        anomaly_rows = []
        per_group_summary = {}

        for g, fitted in forecasters.items():
            fc = self._forecast_one(fitted, horizon)
            fc = fc.copy()
            fc["group"] = g
            fc["yhat"] = fc["yhat"].astype(float)
            fc["yhat_lower"] = fc["yhat_lower"].astype(float)
            fc["yhat_upper"] = fc["yhat_upper"].astype(float)
            if "trend" not in fc.columns:
                fc["trend"] = fc["yhat"]

            sigma = (fc["yhat_upper"] - fc["yhat_lower"]) / (2 * 1.96)
            sigma = sigma.replace(0, sigma[sigma > 0].mean() if (sigma > 0).any() else 1.0)
            deviation = (fc["yhat"] - fc["trend"]).abs() / sigma
            fc["is_anomaly"] = (deviation > 2).astype(int)
            fc["deviation_sigma"] = deviation.round(2)

            per_group_summary[g] = {
                "total_forecast":    round(float(fc["yhat"].sum()), 2),
                "mean_forecast":     round(float(fc["yhat"].mean()), 2),
                "anomaly_periods":   int(fc["is_anomaly"].sum()),
                "horizon":           horizon,
            }

            all_rows.append(fc)
            anomaly_rows.append(fc[fc["is_anomaly"] == 1])

        results_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
        anomalies_df = pd.concat(anomaly_rows, ignore_index=True) if anomaly_rows else pd.DataFrame()

        if not results_df.empty:
            results_df["timestamp"] = results_df["ds"].dt.strftime("%Y-%m-%d")
            results_df = results_df[["timestamp", "group", "yhat", "yhat_lower", "yhat_upper",
                                     "trend", "deviation_sigma", "is_anomaly"]]
            results_df = results_df.where(pd.notnull(results_df), None)
        if not anomalies_df.empty:
            anomalies_df["timestamp"] = anomalies_df["ds"].dt.strftime("%Y-%m-%d")
            anomalies_df = anomalies_df[["timestamp", "group", "yhat", "yhat_lower", "yhat_upper",
                                          "trend", "deviation_sigma", "is_anomaly"]]
            anomalies_df = anomalies_df.where(pd.notnull(anomalies_df), None)

        explanations = []
        if not anomalies_df.empty:
            for _, row in anomalies_df.iterrows():
                explanations.append({
                    "record_id":  f"{row['group']}::{row['timestamp']}",
                    "group":      row["group"],
                    "timestamp":  row["timestamp"],
                    "yhat":       round(float(row["yhat"]), 2),
                    "trend":      round(float(row["trend"]), 2),
                    "sigma":      float(row["deviation_sigma"]),
                    "confidence": "HIGH" if row["deviation_sigma"] >= 3 else "MEDIUM",
                    "reasons":    [
                        f"Forecast {row['yhat']:.2f} deviates {row['deviation_sigma']:.1f}σ from trend baseline {row['trend']:.2f}"
                    ],
                })

        total = len(results_df)
        flagged = int(results_df["is_anomaly"].sum()) if not results_df.empty else 0

        summary = {
            "total_records":   total,
            "anomalies_found": flagged,
            "anomaly_rate":    round(flagged / total * 100, 1) if total else 0,
            "horizon":         horizon,
            "n_groups":        len(forecasters),
            "backend":         stats.get("backend", "unknown"),
            "total_forecast":  round(float(results_df["yhat"].sum()), 2) if not results_df.empty else 0,
            "per_group":       per_group_summary,
        }

        charts_data = self._build_charts_data(forecasters, results_df, horizon)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def _build_charts_data(self, forecasters: dict, results_df: pd.DataFrame, horizon: int) -> dict:
        forecast_chart = []
        components_chart = []

        for g, fitted in forecasters.items():
            history = fitted["history"]
            for _, row in history.tail(90).iterrows():
                forecast_chart.append({
                    "group":     g,
                    "timestamp": pd.to_datetime(row["ds"]).strftime("%Y-%m-%d"),
                    "actual":    round(float(row["y"]), 2),
                    "yhat":      None, "yhat_lower": None, "yhat_upper": None,
                })

        if not results_df.empty:
            for _, row in results_df.iterrows():
                forecast_chart.append({
                    "group":      row["group"],
                    "timestamp":  row["timestamp"],
                    "actual":     None,
                    "yhat":       round(float(row["yhat"]), 2),
                    "yhat_lower": round(float(row["yhat_lower"]), 2),
                    "yhat_upper": round(float(row["yhat_upper"]), 2),
                })

            for _, row in results_df.iterrows():
                components_chart.append({
                    "group":     row["group"],
                    "timestamp": row["timestamp"],
                    "trend":     round(float(row["trend"]), 2),
                    "residual":  round(float(row["yhat"] - row["trend"]), 2),
                })

        per_group = []
        for g, fitted in forecasters.items():
            history = fitted["history"]
            per_group.append({
                "group":         g,
                "history_mean":  round(float(history["y"].mean()), 2),
                "history_max":   round(float(history["y"].max()), 2),
                "history_min":   round(float(history["y"].min()), 2),
                "n_history":     int(len(history)),
            })

        return {
            "forecast":   forecast_chart,
            "components": components_chart,
            "per_group":  per_group,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "forecast",   "title": "Revenue Forecast",        "type": "line",
             "description": "Recent history plus projected revenue with prediction intervals"},
            {"id": "components", "title": "Trend & Residual",        "type": "line",
             "description": "Decomposed forecast trend and per-period residual"},
            {"id": "per_group",  "title": "Per-Group Statistics",    "type": "bar",
             "description": "History mean / min / max per segment or product line"},
        ]

    # ------------------------------------------------------------------
    # Capability flags
    # ------------------------------------------------------------------

    def supports_single_entry(self) -> bool:
        return False

    def supports_event_api(self) -> bool:
        return False

    def supports_incremental_training(self) -> bool:
        return True
