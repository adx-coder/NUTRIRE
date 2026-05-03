"""
Customer Lifetime Value (CLV) plugin for Predictor.

Standalone CLV predictor based on Pareto/NBD + Gamma-Gamma (lifetimes library):
  - BetaGeoFitter (BG/NBD) for repeat-purchase frequency over a horizon.
  - GammaGammaFitter for monetary value per transaction.
  - 12-month CLV = predicted_purchases x predicted_avg_value.

Input is a transactional CSV with columns: customer_id, transaction_date, amount.
We collapse it into per-customer RFM stats via lifetimes.utils.summary_data_from_transaction_data.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data

from app.ml_plugins.base import MLPluginBase


_REQUIRED_COLS = [
    {"column": "customer_id",      "type": "string",   "description": "Unique customer identifier"},
    {"column": "transaction_date", "type": "datetime", "description": "Date of the transaction"},
    {"column": "amount",           "type": "float",    "description": "Monetary value of the transaction"},
]

_HORIZON_MONTHS = 12
_HORIZON_DAYS = _HORIZON_MONTHS * 30
_DISCOUNT_RATE = 0.01  # ~12.7% annual when compounded monthly


class CustomerLifetimeValuePlugin(MLPluginBase):
    plugin_id = "customer_lifetime_value"
    plugin_name = "Customer Lifetime Value"
    plugin_description = (
        "Predicts each customer's 12-month Customer Lifetime Value using a "
        "Pareto/NBD (BG/NBD) repeat-purchase model and a Gamma-Gamma monetary model. "
        "Upload a transactions CSV (customer_id, transaction_date, amount) to score "
        "future revenue per customer and identify your high-value cohort."
    )
    plugin_category = "prediction"
    plugin_icon = "dollar-sign"
    required_files = [
        {
            "key": "transactions",
            "label": "Transaction history CSV",
            "description": "customer_id, transaction_date, amount",
        }
    ]

    # ------------------------------------------------------------------
    # Schema & validation
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        return {
            "transactions": {
                "required": _REQUIRED_COLS,
                "optional": [],
            }
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "transactions":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        actual = set(df.columns)
        errors, warnings = [], []
        for col_def in _REQUIRED_COLS:
            col = col_def["column"]
            if col not in actual:
                errors.append(f"Missing required column: '{col}'")

        if not errors:
            n_customers = df["customer_id"].nunique()
            if len(df) < 50:
                warnings.append(f"Only {len(df)} rows. 500+ rows recommended for stable CLV fits.")
            if n_customers < 20:
                warnings.append(f"Only {n_customers} unique customers. 50+ recommended.")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # RFM summary
    # ------------------------------------------------------------------

    def _build_summary(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
        df = df.copy()
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["transaction_date", "amount", "customer_id"])
        df["customer_id"] = df["customer_id"].astype(str)
        # Drop non-positive transactions — Gamma-Gamma requires monetary_value > 0.
        df = df[df["amount"] > 0]

        observation_end = df["transaction_date"].max()
        summary = summary_data_from_transaction_data(
            df,
            customer_id_col="customer_id",
            datetime_col="transaction_date",
            monetary_value_col="amount",
            observation_period_end=observation_end,
            freq="D",
        )
        return summary, observation_end

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = data["transactions"]
        summary, observation_end = self._build_summary(df)

        if len(summary) < 10:
            raise ValueError("Need at least 10 unique customers to fit CLV models.")

        bgf = BetaGeoFitter(penalizer_coef=0.01)
        bgf.fit(summary["frequency"], summary["recency"], summary["T"])

        # Gamma-Gamma is fit on repeat customers (frequency > 0) with positive monetary value.
        repeat_mask = (summary["frequency"] > 0) & (summary["monetary_value"] > 0)
        repeat = summary[repeat_mask]
        if len(repeat) < 5:
            raise ValueError(
                "Not enough repeat customers (frequency > 0) to fit the Gamma-Gamma monetary model."
            )

        ggf = GammaGammaFitter(penalizer_coef=0.01)
        ggf.fit(repeat["frequency"], repeat["monetary_value"])

        clv_train = self._score_summary(summary, bgf, ggf)
        avg_clv = float(clv_train["clv_12m"].mean())
        total_clv = float(clv_train["clv_12m"].sum())
        high_value_threshold = (
            float(clv_train["clv_12m"].quantile(0.9)) if len(clv_train) >= 10
            else float(clv_train["clv_12m"].max())
        )

        model_dir.mkdir(parents=True, exist_ok=True)
        # lifetimes fitters wrap closures that joblib can't serialize, so use their save_model.
        bgf.save_model(str(model_dir / "bgf.lt"))
        ggf.save_model(str(model_dir / "ggf.lt"))
        joblib.dump({
            "observation_end": observation_end,
            "horizon_months": _HORIZON_MONTHS,
            "horizon_days": _HORIZON_DAYS,
            "discount_rate": _DISCOUNT_RATE,
            "n_customers": int(len(summary)),
            "n_repeat_customers": int(len(repeat)),
            "high_value_threshold": high_value_threshold,
        }, model_dir / "training_meta.joblib")

        return {
            "n_samples": int(len(df)),
            "n_customers": int(len(summary)),
            "n_repeat_customers": int(len(repeat)),
            "avg_clv_12m": round(avg_clv, 2),
            "total_predicted_revenue_12m": round(total_clv, 2),
            "horizon_months": _HORIZON_MONTHS,
        }

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _score_summary(self, summary: pd.DataFrame, bgf: BetaGeoFitter,
                       ggf: GammaGammaFitter) -> pd.DataFrame:
        out = summary.copy()
        out["predicted_purchases_12m"] = bgf.conditional_expected_number_of_purchases_up_to_time(
            _HORIZON_DAYS, out["frequency"], out["recency"], out["T"]
        ).clip(lower=0)

        # conditional_expected_average_profit needs frequency >= 1 with positive monetary value.
        repeat_mask = (out["frequency"] > 0) & (out["monetary_value"] > 0)
        avg_profit = pd.Series(0.0, index=out.index)
        if repeat_mask.any():
            avg_profit.loc[repeat_mask] = ggf.conditional_expected_average_profit(
                out.loc[repeat_mask, "frequency"], out.loc[repeat_mask, "monetary_value"]
            )
        # For one-time buyers fall back to their observed amount as best monetary estimate.
        avg_profit.loc[~repeat_mask] = out.loc[~repeat_mask, "monetary_value"].fillna(0.0)
        out["predicted_avg_value"] = avg_profit.clip(lower=0)

        # Use the library's discounted CLV when we have repeat history; else use simple product.
        clv = pd.Series(0.0, index=out.index)
        if repeat_mask.any():
            clv.loc[repeat_mask] = ggf.customer_lifetime_value(
                bgf,
                out.loc[repeat_mask, "frequency"],
                out.loc[repeat_mask, "recency"],
                out.loc[repeat_mask, "T"],
                out.loc[repeat_mask, "monetary_value"],
                time=_HORIZON_MONTHS,
                discount_rate=_DISCOUNT_RATE,
                freq="D",
            )
        clv.loc[~repeat_mask] = (
            out.loc[~repeat_mask, "predicted_purchases_12m"]
            * out.loc[~repeat_mask, "predicted_avg_value"]
        )
        out["clv_12m"] = clv.clip(lower=0).round(2)
        out["predicted_purchases_12m"] = out["predicted_purchases_12m"].round(3)
        out["predicted_avg_value"] = out["predicted_avg_value"].round(2)
        return out

    def _load_fitters(self, model_dir: Path) -> tuple[BetaGeoFitter, GammaGammaFitter]:
        bgf = BetaGeoFitter()
        ggf = GammaGammaFitter()
        bgf.load_model(str(model_dir / "bgf.lt"))
        ggf.load_model(str(model_dir / "ggf.lt"))
        return bgf, ggf

    # ------------------------------------------------------------------
    # Detection / Scoring
    # ------------------------------------------------------------------

    def detect(self, data: dict, model_dir: Path) -> dict:
        df = data["transactions"]
        bgf, ggf = self._load_fitters(model_dir)

        summary, _ = self._build_summary(df)
        if len(summary) == 0:
            raise ValueError("No usable customers found in transactions (after cleaning).")

        scored = self._score_summary(summary, bgf, ggf)
        scored = scored.reset_index().rename(columns={"index": "customer_id"})

        # "High-value" = top decile by predicted CLV — mapped onto the anomaly interface.
        top_decile_cutoff = float(scored["clv_12m"].quantile(0.9)) if len(scored) >= 10 else float(scored["clv_12m"].max())
        scored["is_high_value"] = (scored["clv_12m"] >= top_decile_cutoff).astype(int)

        results_df = scored[[
            "customer_id", "frequency", "recency", "T", "monetary_value",
            "predicted_purchases_12m", "predicted_avg_value", "clv_12m", "is_high_value",
        ]].copy()
        results_df.columns = [
            "customer_id", "frequency", "recency_days", "tenure_days", "avg_transaction_value",
            "predicted_purchases_12m", "predicted_avg_value", "clv_12m", "is_high_value",
        ]
        results_df = results_df.where(pd.notnull(results_df), None)

        anomalies_df = results_df[results_df["is_high_value"] == 1].copy()

        explanations = []
        for _, row in anomalies_df.iterrows():
            explanations.append({
                "record_id": str(row["customer_id"]),
                "customer_id": str(row["customer_id"]),
                "clv_12m": float(row["clv_12m"]),
                "predicted_purchases_12m": float(row["predicted_purchases_12m"]),
                "predicted_avg_value": float(row["predicted_avg_value"]),
                "confidence": "HIGH",
                "reasons": [
                    f"Predicted 12-month CLV {float(row['clv_12m']):.2f} is in the top 10% of customers.",
                    f"Expected {float(row['predicted_purchases_12m']):.2f} purchases over the next {_HORIZON_MONTHS} months.",
                    f"Expected avg transaction value {float(row['predicted_avg_value']):.2f}.",
                ],
            })

        total = len(results_df)
        high_value = int(results_df["is_high_value"].sum())
        summary_dict = {
            "total_records": total,
            "anomalies_found": high_value,
            "anomaly_rate": round(high_value / total * 100, 1) if total else 0,
            "total_customers": total,
            "high_value_customers": high_value,
            "avg_clv_12m": round(float(results_df["clv_12m"].mean()), 2),
            "total_predicted_revenue_12m": round(float(results_df["clv_12m"].sum()), 2),
            "high_value_threshold": round(top_decile_cutoff, 2),
            "horizon_months": _HORIZON_MONTHS,
        }

        charts_data = self._build_charts_data(results_df)

        return {
            "results_df": results_df,
            "anomalies_df": anomalies_df,
            "summary": summary_dict,
            "explanations": explanations,
            "charts_data": charts_data,
        }

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def _build_charts_data(self, results_df: pd.DataFrame) -> dict:
        clv_vals = results_df["clv_12m"].values.astype(float)
        max_clv = float(np.percentile(clv_vals, 95)) if len(clv_vals) else 0.0
        bins = np.linspace(0, max(max_clv, 1.0), 11)
        clv_distribution = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            count = int(((clv_vals >= lo) & (clv_vals < hi)).sum())
            clv_distribution.append({"range": f"{lo:.0f}-{hi:.0f}", "count": count})

        sample = results_df.sample(min(500, len(results_df)), random_state=42)
        clv_vs_frequency = [
            {
                "customer_id": str(r["customer_id"]),
                "frequency": float(r["frequency"]),
                "clv_12m": float(r["clv_12m"]),
                "high_value": int(r["is_high_value"]),
            }
            for _, r in sample.iterrows()
        ]

        top = results_df.nlargest(10, "clv_12m")
        top_customers = [
            {
                "customer_id": str(r["customer_id"])[-8:],
                "clv_12m": float(r["clv_12m"]),
                "predicted_purchases_12m": float(r["predicted_purchases_12m"]),
                "predicted_avg_value": float(r["predicted_avg_value"]),
            }
            for _, r in top.iterrows()
        ]

        return {
            "clv_distribution": clv_distribution,
            "clv_vs_frequency": clv_vs_frequency,
            "top_customers": top_customers,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "clv_distribution", "title": "CLV Distribution",        "type": "histogram", "description": "Histogram of predicted 12-month CLV across the customer base"},
            {"id": "clv_vs_frequency", "title": "CLV vs Purchase Frequency", "type": "scatter",   "description": "How predicted CLV scales with each customer's historical purchase frequency"},
            {"id": "top_customers",    "title": "Top 10 Customers by CLV",  "type": "bar",       "description": "Highest predicted 12-month CLV customers"},
        ]

    # ------------------------------------------------------------------
    # Single-entry / Events API
    # ------------------------------------------------------------------

    def supports_single_entry(self) -> bool:
        return True

    def get_single_entry_schema(self) -> list[dict]:
        return [
            {"field": "frequency",      "label": "Repeat Purchases",        "type": "number", "required": True,  "description": "Number of repeat purchases (total purchases - 1)"},
            {"field": "recency",        "label": "Recency (days)",           "type": "number", "required": True,  "description": "Days between first and last purchase"},
            {"field": "T",              "label": "Tenure (days)",            "type": "number", "required": True,  "description": "Days between first purchase and observation end"},
            {"field": "monetary_value", "label": "Avg Transaction Value",    "type": "number", "required": True,  "description": "Average value of repeat transactions"},
        ]

    def detect_single(self, record: dict, model_dir: Path) -> dict:
        return self.score_event(record, model_dir)

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": self.get_single_entry_schema(),
            "example": {
                "frequency": 6,
                "recency": 240,
                "T": 360,
                "monetary_value": 85.50,
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        bgf, ggf = self._load_fitters(model_dir)

        frequency = float(event.get("frequency", 0))
        recency   = float(event.get("recency", 0))
        T         = float(event.get("T", recency))
        monetary  = float(event.get("monetary_value", 0))

        predicted_purchases = max(0.0, float(
            bgf.conditional_expected_number_of_purchases_up_to_time(
                _HORIZON_DAYS,
                pd.Series([frequency]),
                pd.Series([recency]),
                pd.Series([T]),
            ).iloc[0]
        ))

        if frequency > 0 and monetary > 0:
            predicted_avg = float(
                ggf.conditional_expected_average_profit(
                    pd.Series([frequency]), pd.Series([monetary])
                ).iloc[0]
            )
            clv = float(
                ggf.customer_lifetime_value(
                    bgf,
                    pd.Series([frequency]),
                    pd.Series([recency]),
                    pd.Series([T]),
                    pd.Series([monetary]),
                    time=_HORIZON_MONTHS,
                    discount_rate=_DISCOUNT_RATE,
                    freq="D",
                ).iloc[0]
            )
        else:
            predicted_avg = monetary
            clv = predicted_purchases * predicted_avg

        predicted_avg = max(predicted_avg, 0.0)
        clv = max(clv, 0.0)

        meta_path = model_dir / "training_meta.joblib"
        meta = joblib.load(meta_path) if meta_path.exists() else {}
        threshold = float(meta.get("high_value_threshold", 0.0))
        is_high_value = bool(threshold > 0 and clv >= threshold)

        if predicted_purchases >= 5:
            confidence = "HIGH"
        elif predicted_purchases >= 2:
            confidence = "MEDIUM"
        elif predicted_purchases >= 0.5:
            confidence = "LOW"
        else:
            confidence = "NORMAL"

        # Map score onto 0-1: saturating function of CLV so the events API has a comparable score.
        score = float(1.0 - np.exp(-clv / 1000.0))

        reasons = [
            f"Predicted {predicted_purchases:.2f} purchases over the next {_HORIZON_MONTHS} months.",
            f"Predicted avg transaction value {predicted_avg:.2f}.",
            f"Predicted 12-month CLV {clv:.2f}.",
        ]

        return {
            "is_anomaly": is_high_value,
            "confidence": confidence,
            "score": round(score, 4),
            "clv_12m": round(clv, 2),
            "reasons": reasons,
            "details": {
                "predicted_purchases_12m": round(predicted_purchases, 3),
                "predicted_avg_value": round(predicted_avg, 2),
                "clv_12m": round(clv, 2),
                "horizon_months": _HORIZON_MONTHS,
                "model_family": "BG/NBD + Gamma-Gamma",
            },
        }
