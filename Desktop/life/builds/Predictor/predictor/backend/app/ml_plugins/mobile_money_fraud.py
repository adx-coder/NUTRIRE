"""
Mobile Money Fraud Detection plugin for Predictor.

This is the production-oriented v1 path from the mobile_money_fraud package:
LightGBM on leakage-audited transaction features, with graph/GNN work kept out
of the runtime dependency until it earns clean lift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

from app.ml_plugins.base import MLPluginBase
from app.ml_plugins._gpu_utils import get_lightgbm_device


REQUIRED_COLUMNS = [
    {"column": "transaction_id", "type": "string", "description": "Unique transaction identifier"},
    {"column": "timestamp", "type": "datetime", "description": "Transaction timestamp"},
    {"column": "amount", "type": "float", "description": "Transaction amount"},
    {"column": "transaction_type", "type": "string", "description": "Transaction type such as CASH_OUT, TRANSFER, PAYMENT"},
    {"column": "source_account_id", "type": "string", "description": "Pseudonymized sender/source account id"},
    {"column": "destination_account_id", "type": "string", "description": "Pseudonymized receiver/destination account id"},
]

OPTIONAL_COLUMNS = [
    {"column": "is_fraud", "type": "boolean", "description": "Fraud label. Required for training; optional for detection metrics."},
    {"column": "channel", "type": "string", "description": "Channel such as app, USSD, agent, API"},
    {"column": "region", "type": "string", "description": "Region or market code"},
    {"column": "kyc_tier", "type": "string", "description": "Customer KYC tier or account tier"},
    {"column": "source_account_age_days", "type": "float", "description": "Age of source account in days"},
    {"column": "destination_account_age_days", "type": "float", "description": "Age of destination account in days"},
]

LABEL_TRUE = {"1", "true", "t", "yes", "y", "fraud", "illicit", "suspicious"}
LABEL_FALSE = {"0", "false", "f", "no", "n", "legit", "licit", "normal", "not_fraud"}
LEAKAGE_COLUMNS = {
    "errorBalanceOrig",
    "errorBalanceDest",
    "isFlaggedFraud",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
}


class MobileMoneyFraudPlugin(MLPluginBase):
    plugin_id = "mobile_money_fraud"
    plugin_name = "Mobile Money Fraud Detection"
    plugin_description = (
        "Scores mobile-money transactions for fraud risk using a leakage-aware "
        "LightGBM model trained on causal transaction and account-history features."
    )
    plugin_category = "anomaly_detection"
    plugin_icon = "search"
    required_files = [
        {
            "key": "transactions",
            "label": "Transactions CSV",
            "description": "Transaction rows. Include is_fraud for training; omit it for scoring new transactions.",
        }
    ]

    def get_schema(self) -> dict:
        return {
            "transactions": {
                "required": REQUIRED_COLUMNS,
                "optional": OPTIONAL_COLUMNS,
            }
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "transactions":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        actual = set(df.columns)
        required = [c["column"] for c in REQUIRED_COLUMNS]
        optional = [c["column"] for c in OPTIONAL_COLUMNS]

        errors = [f"Missing required column: '{c}'" for c in required if c not in actual]
        warnings = [f"Missing optional column: '{c}'" for c in optional if c not in actual]

        leakage_present = sorted(c for c in LEAKAGE_COLUMNS if c in actual)
        if leakage_present:
            warnings.append(
                "Leakage/proxy columns were found and will be ignored: "
                + ", ".join(leakage_present)
            )

        if len(df) < 100:
            warnings.append("Only a small number of rows were found. Use 1,000+ rows for a useful production model.")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def train(self, data: dict[str, pd.DataFrame], model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = self._prepare_frame(data["transactions"])
        if "is_fraud" not in df.columns:
            raise ValueError("Training requires an 'is_fraud' column in the transactions CSV.")

        y = self._parse_label(df["is_fraud"])
        if y.nunique() < 2:
            raise ValueError("Training data must contain both fraudulent and non-fraudulent transactions.")
        class_counts = y.value_counts()
        if int(class_counts.min()) < 2:
            raise ValueError("Training data must contain at least two examples of each class for validation.")

        df = df.assign(_label=y).sort_values("timestamp").reset_index(drop=True)
        train_df, val_df = self._time_split(df)

        train_feat, account_profiles, categorical_levels = self._build_features(train_df, fit=True)
        val_feat, _, _ = self._build_features(
            val_df,
            fit=False,
            account_profiles=account_profiles,
            categorical_levels=categorical_levels,
        )

        X_train, feature_cols, medians = self._finalize_training_features(train_feat)
        X_val = self._finalize_scoring_features(val_feat, feature_cols, medians)
        y_train = train_df["_label"].astype(int).to_numpy()
        y_val = val_df["_label"].astype(int).to_numpy()

        model = self._make_model(y_train)
        model.fit(X_train, y_train)

        val_scores = model.predict_proba(X_val)[:, 1]
        metrics = self._metrics(y_val, val_scores)
        thresholds = self._thresholds(y_val, val_scores)

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_dir / "model.joblib")
        joblib.dump(feature_cols, model_dir / "feature_cols.joblib")
        joblib.dump(medians, model_dir / "medians.joblib")
        joblib.dump(categorical_levels, model_dir / "categorical_levels.joblib")
        _, serving_account_profiles, _ = self._build_features(
            df.drop(columns=["_label"], errors="ignore"),
            fit=True,
            categorical_levels=categorical_levels,
        )

        joblib.dump(serving_account_profiles, model_dir / "account_profiles.joblib")
        joblib.dump(thresholds, model_dir / "thresholds.joblib")

        feature_importance = self._feature_importance(model, feature_cols)
        feature_importance.to_csv(model_dir / "feature_importance.csv", index=False)

        manifest = {
            "model_family": "LightGBM",
            "plugin_id": self.plugin_id,
            "n_samples": int(len(df)),
            "n_train": int(len(train_df)),
            "n_val": int(len(val_df)),
            "n_features": int(len(feature_cols)),
            "fraud_rate": float(y.mean()),
            "split_policy": "chronological_80_20_by_timestamp",
            "leakage_policy": "PaySim balance/proxy fields are ignored if present.",
            "thresholds": thresholds,
        }
        (model_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        return {
            "n_samples": int(len(df)),
            "n_train": int(len(train_df)),
            "n_test": int(len(val_df)),
            "n_features": int(len(feature_cols)),
            "feature_names": feature_cols,
            "training_mode": "full",
            "training_anomaly_rate": round(float(y.mean()), 4),
            "fraud_rate": round(float(y.mean()) * 100, 2),
            "threshold_high": thresholds["high"],
            "threshold_medium": thresholds["medium"],
            "top_features": feature_importance.head(10).values.tolist(),
            **metrics,
        }

    def detect(self, data: dict[str, pd.DataFrame], model_dir: Path) -> dict:
        df = self._prepare_frame(data["transactions"]).sort_values("timestamp").reset_index(drop=True)
        if "transaction_id" not in df.columns:
            df["transaction_id"] = [f"event_{i:06d}" for i in range(len(df))]
        artifacts = self._load_artifacts(model_dir)
        feat, _, _ = self._build_features(
            df,
            fit=False,
            account_profiles=artifacts["account_profiles"],
            categorical_levels=artifacts["categorical_levels"],
        )
        X = self._finalize_scoring_features(feat, artifacts["feature_cols"], artifacts["medians"])
        scores = artifacts["model"].predict_proba(X)[:, 1]

        results = df.copy()
        results["fraud_score"] = np.round(scores, 6)
        results["fraud_prediction"] = (scores >= artifacts["thresholds"]["medium"]).astype(int)
        results["risk_tier"] = [self._risk_tier(s, artifacts["thresholds"]) for s in scores]

        if "is_fraud" in results.columns:
            y_true = self._parse_label(results["is_fraud"]).to_numpy()
            accuracy_metrics = self._classification_metrics(y_true, scores, results["fraud_prediction"].to_numpy())
        else:
            accuracy_metrics = {}

        summary = self._summary(results, accuracy_metrics)
        explanations = self._explanations(results, feat, scores, artifacts["thresholds"])
        charts_data = self._charts_data(results, scores, artifacts["feature_importance"])

        keep_cols = [
            "transaction_id", "timestamp", "source_account_id", "destination_account_id",
            "amount", "transaction_type", "fraud_score", "risk_tier", "fraud_prediction",
        ]
        for col in ["channel", "region", "kyc_tier", "is_fraud"]:
            if col in results.columns:
                keep_cols.append(col)

        results_df = results[keep_cols].copy()
        anomalies_df = results_df[results_df["fraud_prediction"] == 1].copy()

        return {
            "results_df": results_df.where(pd.notnull(results_df), None),
            "anomalies_df": anomalies_df.where(pd.notnull(anomalies_df), None),
            "summary": summary,
            "explanations": explanations,
            "charts_data": charts_data,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "risk_tier_distribution", "title": "Risk Tier Distribution", "type": "bar", "description": "Transactions by risk tier"},
            {"id": "score_histogram", "title": "Fraud Score Distribution", "type": "histogram", "description": "Distribution of fraud scores"},
            {"id": "amount_by_type", "title": "Flagged Amount by Type", "type": "bar", "description": "Flagged amount grouped by transaction type"},
            {"id": "flagged_rate_by_channel", "title": "Flagged Rate by Channel", "type": "bar", "description": "Flagged rate by channel when present"},
            {"id": "feature_importance", "title": "Top Fraud Drivers", "type": "bar", "description": "Top LightGBM feature importances"},
        ]

    def supports_single_entry(self) -> bool:
        return True

    def get_single_entry_schema(self) -> list[dict]:
        return [
            {"field": "transaction_id", "label": "Transaction ID", "type": "text", "required": False, "description": "Unique transaction id"},
            {"field": "timestamp", "label": "Timestamp", "type": "date", "required": True, "description": "Transaction date/time"},
            {"field": "amount", "label": "Amount", "type": "number", "required": True, "description": "Transaction amount"},
            {"field": "transaction_type", "label": "Transaction Type", "type": "select", "required": True, "description": "Type of transaction", "options": ["CASH_OUT", "TRANSFER", "PAYMENT", "CASH_IN", "DEBIT"]},
            {"field": "source_account_id", "label": "Source Account", "type": "text", "required": True, "description": "Pseudonymized source account id"},
            {"field": "destination_account_id", "label": "Destination Account", "type": "text", "required": True, "description": "Pseudonymized destination account id"},
            {"field": "channel", "label": "Channel", "type": "text", "required": False, "description": "Optional channel"},
            {"field": "region", "label": "Region", "type": "text", "required": False, "description": "Optional region"},
            {"field": "kyc_tier", "label": "KYC Tier", "type": "text", "required": False, "description": "Optional KYC tier"},
        ]

    def detect_single(self, record: dict, model_dir: Path) -> dict:
        result = self.score_event(record, model_dir)
        return result

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": self.get_single_entry_schema(),
            "example": {
                "transaction_id": "txn_10001",
                "timestamp": "2026-04-29T09:00:00Z",
                "amount": 245.50,
                "transaction_type": "TRANSFER",
                "source_account_id": "acct_123",
                "destination_account_id": "acct_456",
                "channel": "app",
                "region": "north",
                "kyc_tier": "tier_2",
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        df = pd.DataFrame([event])
        detected = self.detect({"transactions": df}, model_dir)
        row = detected["results_df"].iloc[0].to_dict()
        exp = detected["explanations"][0] if detected["explanations"] else {"reasons": []}
        score = float(row["fraud_score"])
        tier = row["risk_tier"]
        return {
            "is_anomaly": bool(row["fraud_prediction"] == 1),
            "confidence": tier,
            "score": score,
            "reasons": exp.get("reasons", []),
            "details": {
                "risk_tier": tier,
                "transaction_id": row.get("transaction_id"),
                "model_family": "LightGBM",
            },
        }

    def supports_incremental_training(self) -> bool:
        return False

    def _prepare_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out = out.drop(columns=[c for c in LEAKAGE_COLUMNS if c in out.columns], errors="ignore")
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
        out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
        out["transaction_type"] = out["transaction_type"].astype(str).str.strip().str.upper()
        if out["source_account_id"].isna().any() or out["destination_account_id"].isna().any():
            raise ValueError("source_account_id and destination_account_id cannot be blank.")
        out["source_account_id"] = out["source_account_id"].astype(str)
        out["destination_account_id"] = out["destination_account_id"].astype(str)
        for col in ["channel", "region", "kyc_tier"]:
            if col in out.columns:
                out[col] = out[col].astype(str).str.strip().str.lower()
        for col in ["source_account_age_days", "destination_account_age_days"]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
        if out["timestamp"].isna().any():
            raise ValueError("All rows must have a parseable timestamp.")
        if out["amount"].isna().any():
            raise ValueError("All rows must have a numeric amount.")
        return out.reset_index(drop=True)

    def _parse_label(self, series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip().str.lower()
        parsed = s.map(lambda v: 1 if v in LABEL_TRUE else (0 if v in LABEL_FALSE else np.nan))
        if parsed.isna().any():
            bad = sorted(series[parsed.isna()].astype(str).unique())[:5]
            raise ValueError(f"Unrecognized is_fraud label values: {bad}")
        return parsed.astype(int)

    def _time_split(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if len(df) < 20:
            train, val = train_test_split(df, test_size=0.2, random_state=42, stratify=df["_label"])
            return train.sort_values("timestamp").reset_index(drop=True), val.sort_values("timestamp").reset_index(drop=True)

        cut = max(1, int(len(df) * 0.8))
        train_df = df.iloc[:cut].copy()
        val_df = df.iloc[cut:].copy()
        if train_df["_label"].nunique() < 2 or val_df["_label"].nunique() < 2:
            train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["_label"])
        return train_df.sort_values("timestamp").reset_index(drop=True), val_df.sort_values("timestamp").reset_index(drop=True)

    def _build_features(
        self,
        df: pd.DataFrame,
        fit: bool,
        account_profiles: dict[str, Any] | None = None,
        categorical_levels: dict[str, list[str]] | None = None,
    ) -> tuple[pd.DataFrame, dict[str, Any], dict[str, list[str]]]:
        frame = df.sort_values("timestamp").reset_index(drop=True).copy()
        feat = pd.DataFrame(index=frame.index)
        feat["amount"] = frame["amount"].astype(float)
        feat["log_amount"] = np.log1p(frame["amount"].clip(lower=0))
        feat["hour_of_day"] = frame["timestamp"].dt.hour.astype(float)
        feat["day_of_week"] = frame["timestamp"].dt.dayofweek.astype(float)
        feat["is_weekend"] = (frame["timestamp"].dt.dayofweek >= 5).astype(int)

        for col in ["source_account_age_days", "destination_account_age_days"]:
            if col in frame.columns:
                feat[col] = frame[col].astype(float)

        account_profiles = account_profiles or {}
        feat = pd.concat([feat, self._causal_history_features(frame, fit, account_profiles)], axis=1)

        categorical_cols = [c for c in ["transaction_type", "channel", "region", "kyc_tier"] if c in frame.columns]
        if fit:
            categorical_levels = {
                col: sorted(str(v) for v in frame[col].fillna("missing").astype(str).unique())[:50]
                for col in categorical_cols
            }
        categorical_levels = categorical_levels or {}

        for col, levels in categorical_levels.items():
            values = frame[col].fillna("missing").astype(str) if col in frame.columns else pd.Series("missing", index=frame.index)
            for level in levels:
                safe = self._safe_name(level)
                feat[f"{col}__{safe}"] = (values == level).astype(int)

        return feat, account_profiles, categorical_levels

    def _causal_history_features(self, frame: pd.DataFrame, fit: bool, profiles: dict[str, Any]) -> pd.DataFrame:
        rows = []
        src_state = profiles.get("source", {}).copy() if not fit else {}
        dst_state = profiles.get("destination", {}).copy() if not fit else {}
        pair_state = profiles.get("pairs", {}).copy() if not fit else {}

        for _, row in frame.iterrows():
            src = str(row["source_account_id"])
            dst = str(row["destination_account_id"])
            pair = f"{src}->{dst}"
            amount = float(row["amount"])
            src_stats = src_state.get(src, {"count": 0, "sum": 0.0, "max": 0.0})
            dst_stats = dst_state.get(dst, {"count": 0, "sum": 0.0, "max": 0.0})
            pair_stats = pair_state.get(pair, {"count": 0, "sum": 0.0})
            rows.append({
                "src_txn_count_past": src_stats["count"],
                "src_amount_sum_past": src_stats["sum"],
                "src_amount_mean_past": src_stats["sum"] / src_stats["count"] if src_stats["count"] else 0.0,
                "src_amount_max_past": src_stats["max"],
                "dst_txn_count_past": dst_stats["count"],
                "dst_amount_sum_past": dst_stats["sum"],
                "dst_amount_mean_past": dst_stats["sum"] / dst_stats["count"] if dst_stats["count"] else 0.0,
                "dst_amount_max_past": dst_stats["max"],
                "pair_txn_count_past": pair_stats["count"],
                "pair_amount_sum_past": pair_stats["sum"],
                "src_is_cold_start": int(src_stats["count"] == 0),
                "dst_is_cold_start": int(dst_stats["count"] == 0),
            })

            src_state[src] = {
                "count": int(src_stats["count"]) + 1,
                "sum": float(src_stats["sum"]) + amount,
                "max": max(float(src_stats["max"]), amount),
            }
            dst_state[dst] = {
                "count": int(dst_stats["count"]) + 1,
                "sum": float(dst_stats["sum"]) + amount,
                "max": max(float(dst_stats["max"]), amount),
            }
            pair_state[pair] = {
                "count": int(pair_stats["count"]) + 1,
                "sum": float(pair_stats["sum"]) + amount,
            }

        if fit:
            profiles["source"] = src_state
            profiles["destination"] = dst_state
            profiles["pairs"] = pair_state

        return pd.DataFrame(rows, index=frame.index)

    def _finalize_training_features(self, feat: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict[str, float]]:
        out = feat.copy()
        for col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        missing_cols = [c for c in out.columns if out[c].isna().any()]
        for col in missing_cols:
            out[f"{col}__missing"] = out[col].isna().astype(int)
        medians = out.median(numeric_only=True).fillna(0.0).to_dict()
        out = out.fillna(medians).astype("float32")
        return out, list(out.columns), {str(k): float(v) for k, v in medians.items()}

    def _finalize_scoring_features(self, feat: pd.DataFrame, feature_cols: list[str], medians: dict[str, float]) -> pd.DataFrame:
        out = feat.copy()
        for col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        for col in list(out.columns):
            missing_col = f"{col}__missing"
            if missing_col in feature_cols:
                out[missing_col] = out[col].isna().astype(int)
        for col in feature_cols:
            if col not in out.columns:
                out[col] = 0.0
        out = out[feature_cols].fillna(medians).fillna(0.0).astype("float32")
        return out

    def _make_model(self, y_train: np.ndarray) -> LGBMClassifier:
        positives = max(1, int((y_train == 1).sum()))
        negatives = max(1, int((y_train == 0).sum()))
        return LGBMClassifier(
            objective="binary",
            n_estimators=800,
            learning_rate=0.04,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_samples=20,
            reg_lambda=2.0,
            scale_pos_weight=negatives / positives,
            random_state=7,
            n_jobs=-1,
            verbosity=-1,
            device_type=get_lightgbm_device(),
        )

    def _metrics(self, y_true: np.ndarray, scores: np.ndarray) -> dict[str, float]:
        if len(np.unique(y_true)) < 2:
            return {
                "auprc": round(float(average_precision_score(y_true, scores)) * 100, 2),
                "auroc": None,
                "precision_at_pos_count": round(self._precision_at_k(y_true, scores) * 100, 2),
                "recall_at_1pct_fpr": None,
                "recall_at_5pct_fpr": None,
            }
        return {
            "auprc": round(float(average_precision_score(y_true, scores)) * 100, 2),
            "auroc": round(float(roc_auc_score(y_true, scores)) * 100, 2),
            "precision_at_pos_count": round(self._precision_at_k(y_true, scores) * 100, 2),
            "recall_at_1pct_fpr": round(self._recall_at_fpr(y_true, scores, 0.01) * 100, 2),
            "recall_at_5pct_fpr": round(self._recall_at_fpr(y_true, scores, 0.05) * 100, 2),
        }

    def _classification_metrics(self, y_true: np.ndarray, scores: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        metrics = self._metrics(y_true, scores)
        metrics["observed_fraud_rate"] = round(float(y_true.mean()) * 100, 2)
        metrics["predicted_fraud_rate"] = round(float(y_pred.mean()) * 100, 2)
        return metrics

    def _precision_at_k(self, y_true: np.ndarray, scores: np.ndarray, k: int | None = None) -> float:
        if k is None:
            k = int((y_true == 1).sum())
        k = max(1, min(int(k), len(y_true)))
        top = np.argsort(-scores)[:k]
        return float(y_true[top].mean())

    def _recall_at_fpr(self, y_true: np.ndarray, scores: np.ndarray, max_fpr: float) -> float:
        fpr, tpr, _ = roc_curve(y_true, scores)
        ok = fpr <= max_fpr
        return float(tpr[ok].max()) if ok.any() else 0.0

    def _thresholds(self, y_true: np.ndarray, scores: np.ndarray) -> dict[str, float]:
        fraud_rate = float(np.mean(y_true))
        medium_rate = min(max(fraud_rate * 3, 0.01), 0.20)
        high_rate = min(max(fraud_rate, 0.005), medium_rate)
        return {
            "high": round(float(np.quantile(scores, 1 - high_rate)), 6),
            "medium": round(float(np.quantile(scores, 1 - medium_rate)), 6),
        }

    def _risk_tier(self, score: float, thresholds: dict[str, float]) -> str:
        if score >= thresholds["high"]:
            return "HIGH"
        if score >= thresholds["medium"]:
            return "MEDIUM"
        return "LOW"

    def _summary(self, results: pd.DataFrame, accuracy_metrics: dict[str, float]) -> dict[str, Any]:
        total = int(len(results))
        flagged = int((results["fraud_prediction"] == 1).sum())
        high = int((results["risk_tier"] == "HIGH").sum())
        medium = int((results["risk_tier"] == "MEDIUM").sum())
        amount_at_risk = float(results.loc[results["fraud_prediction"] == 1, "amount"].sum())
        return {
            "total_records": total,
            "anomalies_found": flagged,
            "anomaly_rate": round(flagged / max(total, 1) * 100, 2),
            "flagged_transactions": flagged,
            "flagged_rate": round(flagged / max(total, 1) * 100, 2),
            "high_risk": high,
            "medium_risk": medium,
            "mean_fraud_score": round(float(results["fraud_score"].mean()) * 100, 2),
            "amount_at_risk": round(amount_at_risk, 2),
            **accuracy_metrics,
        }

    def _explanations(self, results: pd.DataFrame, feat: pd.DataFrame, scores: np.ndarray, thresholds: dict[str, float]) -> list[dict]:
        flagged = results[results["fraud_prediction"] == 1].copy()
        flagged = flagged.sort_values("fraud_score", ascending=False).head(200)
        explanations = []
        for idx, row in flagged.iterrows():
            reasons = self._reasons(row, feat.loc[idx])
            explanations.append({
                "record_id": str(row.get("transaction_id", idx)),
                "transaction_id": row.get("transaction_id"),
                "amount": float(row.get("amount", 0)),
                "transaction_type": row.get("transaction_type"),
                "source_account_id": row.get("source_account_id"),
                "destination_account_id": row.get("destination_account_id"),
                "fraud_score": float(row["fraud_score"]),
                "risk_tier": row["risk_tier"],
                "reasons": reasons,
            })
        return explanations

    def _reasons(self, row: pd.Series, feat_row: pd.Series) -> list[str]:
        reasons = []
        if float(row.get("amount", 0)) >= max(1.0, float(feat_row.get("src_amount_mean_past", 0)) * 3):
            reasons.append("Amount is much higher than this source account's past average.")
        if int(feat_row.get("src_is_cold_start", 0)) == 1:
            reasons.append("Source account has no prior history in the training profile.")
        if int(feat_row.get("dst_is_cold_start", 0)) == 1:
            reasons.append("Destination account has no prior history in the training profile.")
        if int(feat_row.get("pair_txn_count_past", 0)) == 0:
            reasons.append("This source and destination pair has not been seen before.")
        if str(row.get("transaction_type", "")).upper() in {"CASH_OUT", "TRANSFER"}:
            reasons.append("Transaction type is commonly higher risk in money-movement fraud reviews.")
        if not reasons:
            reasons.append("Combined transaction pattern is high risk under the trained LightGBM model.")
        return reasons[:4]

    def _charts_data(self, results: pd.DataFrame, scores: np.ndarray, feature_importance: pd.DataFrame) -> dict[str, Any]:
        risk_counts = [
            {"tier": "HIGH", "count": int((results["risk_tier"] == "HIGH").sum()), "color": "#ef4444"},
            {"tier": "MEDIUM", "count": int((results["risk_tier"] == "MEDIUM").sum()), "color": "#f59e0b"},
            {"tier": "LOW", "count": int((results["risk_tier"] == "LOW").sum()), "color": "#22c55e"},
        ]
        bins = np.linspace(0, 1, 11)
        hist = []
        for i, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            if i == len(bins) - 2:
                count = int(((scores >= lo) & (scores <= hi)).sum())
            else:
                count = int(((scores >= lo) & (scores < hi)).sum())
            hist.append({"range": f"{lo:.1f}-{hi:.1f}", "count": count})

        flagged = results[results["fraud_prediction"] == 1]
        amount_by_type = [
            {"type": str(k), "amount": round(float(v), 2)}
            for k, v in flagged.groupby("transaction_type")["amount"].sum().sort_values(ascending=False).head(10).items()
        ]

        by_channel = []
        if "channel" in results.columns:
            grouped = results.groupby("channel")["fraud_prediction"].agg(["mean", "count"]).reset_index()
            by_channel = [
                {"channel": str(r["channel"]), "flagged_rate": round(float(r["mean"]) * 100, 2), "count": int(r["count"])}
                for _, r in grouped.iterrows()
            ]

        importance = [
            {"feature": self._pretty_feature(r["feature"]), "importance": round(float(r["importance"]), 2)}
            for _, r in feature_importance.head(10).iterrows()
        ]
        return {
            "risk_tier_distribution": risk_counts,
            "score_histogram": hist,
            "amount_by_type": amount_by_type,
            "flagged_rate_by_channel": by_channel,
            "feature_importance": importance,
        }

    def _feature_importance(self, model: LGBMClassifier, feature_cols: list[str]) -> pd.DataFrame:
        raw = getattr(model, "feature_importances_", np.zeros(len(feature_cols)))
        total = float(np.sum(raw)) or 1.0
        return pd.DataFrame({
            "feature": feature_cols,
            "importance": np.asarray(raw, dtype=float) / total * 100,
        }).sort_values("importance", ascending=False)

    def _load_artifacts(self, model_dir: Path) -> dict[str, Any]:
        feature_importance_path = model_dir / "feature_importance.csv"
        return {
            "model": joblib.load(model_dir / "model.joblib"),
            "feature_cols": joblib.load(model_dir / "feature_cols.joblib"),
            "medians": joblib.load(model_dir / "medians.joblib"),
            "categorical_levels": joblib.load(model_dir / "categorical_levels.joblib"),
            "account_profiles": joblib.load(model_dir / "account_profiles.joblib"),
            "thresholds": joblib.load(model_dir / "thresholds.joblib"),
            "feature_importance": pd.read_csv(feature_importance_path) if feature_importance_path.exists() else pd.DataFrame(columns=["feature", "importance"]),
        }

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in str(value).lower()).strip("_") or "missing"

    def _pretty_feature(self, name: str) -> str:
        mapping = {
            "log_amount": "Log Amount",
            "amount": "Amount",
            "hour_of_day": "Hour of Day",
            "day_of_week": "Day of Week",
            "src_txn_count_past": "Source Past Count",
            "src_amount_mean_past": "Source Avg Amount",
            "dst_txn_count_past": "Destination Past Count",
            "pair_txn_count_past": "Pair Past Count",
            "src_is_cold_start": "New Source",
            "dst_is_cold_start": "New Destination",
        }
        return mapping.get(name, name.replace("_", " ").title())
