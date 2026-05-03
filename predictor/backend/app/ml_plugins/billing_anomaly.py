"""
Billing Anomaly Detection Plugin for Predictor.

Wraps the existing invoice anomaly detector as a Predictor ML plugin.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root so we can import the existing detector code
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from invoice_anomaly_detector import engineer_invoice_features, select_model_features
from schema_validator import (
    ACCOUNT_SCHEMA, INVOICE_DETAILS_SCHEMA, INVOICE_SCHEMA,
    validate_dataframe,
)

from app.ml_plugins.base import MLPluginBase

# Import ML libraries
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


class BillingAnomalyPlugin(MLPluginBase):
    plugin_id = "billing_anomaly"
    plugin_name = "Billing Invoice Anomaly Detection"
    plugin_description = (
        "Detects billing discrepancies in telecom invoices using an ensemble of "
        "Isolation Forest, Local Outlier Factor, and statistical Z-score methods. "
        "Flags unusual charges, line-item mismatches, and account-level deviations."
    )
    plugin_category = "anomaly_detection"
    plugin_icon = "search"
    required_files = [
        {"key": "invoices", "label": "Invoice CSV", "description": "Main invoice records with amounts and dates"},
        {"key": "details", "label": "Invoice Details CSV", "description": "Line-item breakdown for each invoice"},
        {"key": "accounts", "label": "Account CSV", "description": "Account master data with balances"},
    ]

    def get_schema(self) -> dict:
        return {
            "invoices": INVOICE_SCHEMA,
            "details": INVOICE_DETAILS_SCHEMA,
            "accounts": ACCOUNT_SCHEMA,
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        schema_map = {"invoices": INVOICE_SCHEMA, "details": INVOICE_DETAILS_SCHEMA, "accounts": ACCOUNT_SCHEMA}
        schema = schema_map.get(file_key)
        if not schema:
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        required_cols = [e["column"] for e in schema["required"]]
        optional_cols = [e["column"] for e in schema["optional"]]
        actual = set(df.columns)

        missing_req = [c for c in required_cols if c not in actual]
        missing_opt = [c for c in optional_cols if c not in actual]

        errors = [f"Missing required column: '{c}'" for c in missing_req]
        warnings = [f"Missing optional column: '{c}' (detection still works)" for c in missing_opt]

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def _parse_dates(self, invoices, details, accounts):
        """Parse date columns."""
        date_cols_inv = [
            "due_date", "paid_date", "bill_date", "from_date", "to_date",
            "bill_from_date", "bill_thru_date", "usage_from_date", "usage_to_date",
        ]
        for col in date_cols_inv:
            if col in invoices.columns:
                invoices[col] = pd.to_datetime(invoices[col], errors="coerce")

        for col in ["start_date", "end_date"]:
            if col in details.columns:
                details[col] = pd.to_datetime(details[col], errors="coerce")

        if "plan_date" in accounts.columns:
            accounts["plan_date"] = pd.to_datetime(accounts["plan_date"], errors="coerce")
        if "acct_start_date" in accounts.columns:
            accounts["acct_start_date"] = pd.to_datetime(accounts["acct_start_date"], errors="coerce")

        return invoices, details, accounts

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        invoices, details, accounts = data["invoices"], data["details"], data["accounts"]
        invoices, details, accounts = self._parse_dates(invoices, details, accounts)

        features = engineer_invoice_features(invoices, details, accounts)
        X, feature_cols = select_model_features(features)

        contamination = 0.15

        # --- 80/20 holdout split for validation ---
        n_total = len(X)
        n_test = max(1, int(n_total * 0.2))
        n_train = n_total - n_test

        np.random.seed(42)
        indices = np.random.permutation(n_total)
        train_idx, test_idx = indices[:n_train], indices[n_train:]

        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]

        # If incremental: start from previous scaler stats
        if base_model_dir and (base_model_dir / "scaler.joblib").exists():
            old_scaler = joblib.load(base_model_dir / "scaler.joblib")
            scaler = StandardScaler()
            scaler.fit(X_train)
            # Blend old and new statistics (weighted average)
            scaler.mean_ = 0.7 * old_scaler.mean_ + 0.3 * scaler.mean_
            scaler.scale_ = 0.7 * old_scaler.scale_ + 0.3 * scaler.scale_
            training_mode = "incremental"
        else:
            scaler = StandardScaler()
            scaler.fit(X_train)
            training_mode = "full"

        X_train_scaled = scaler.transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        iso_forest = IsolationForest(
            contamination=contamination, random_state=42,
            n_estimators=200, max_samples="auto",
        )
        iso_forest.fit(X_train_scaled)

        # --- Evaluate on holdout set ---
        holdout_metrics = self._evaluate_holdout(
            iso_forest, scaler, X_test_scaled, features.iloc[test_idx], contamination
        )

        # --- Retrain on full data for the saved model ---
        scaler_full = StandardScaler()
        if base_model_dir and (base_model_dir / "scaler.joblib").exists():
            old_scaler = joblib.load(base_model_dir / "scaler.joblib")
            scaler_full.fit(X)
            scaler_full.mean_ = 0.7 * old_scaler.mean_ + 0.3 * scaler_full.mean_
            scaler_full.scale_ = 0.7 * old_scaler.scale_ + 0.3 * scaler_full.scale_
        else:
            scaler_full.fit(X)

        X_full_scaled = scaler_full.transform(X)
        iso_forest_full = IsolationForest(
            contamination=contamination, random_state=42,
            n_estimators=200, max_samples="auto",
        )
        iso_forest_full.fit(X_full_scaled)

        training_stats = {}
        for col in ["debit", "credit", "total_due", "line_debit_sum"]:
            if col in features.columns:
                training_stats[col] = {
                    "mean": float(features[col].mean()),
                    "std": float(features[col].std()),
                }

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(scaler_full, model_dir / "scaler.joblib")
        joblib.dump(iso_forest_full, model_dir / "isolation_forest.joblib")
        joblib.dump(feature_cols, model_dir / "feature_cols.joblib")
        joblib.dump(training_stats, model_dir / "training_stats.joblib")

        return {
            "n_samples": n_total,
            "n_train": n_train,
            "n_test": n_test,
            "n_features": len(feature_cols),
            "feature_names": feature_cols,
            "contamination": contamination,
            "training_mode": training_mode,
            "training_anomaly_rate": contamination,
            **holdout_metrics,
        }

    def _evaluate_holdout(self, iso_forest, scaler, X_test_scaled, test_features, contamination):
        """Run the full ensemble on the holdout set and compute consistency metrics."""
        n_test = len(X_test_scaled)

        # Isolation Forest predictions on holdout
        iso_pred = iso_forest.predict(X_test_scaled)

        # LOF on holdout (fit fresh — LOF is transductive)
        lof = LocalOutlierFactor(
            n_neighbors=min(20, n_test - 1) if n_test > 1 else 1,
            contamination=contamination,
        )
        lof_pred = lof.fit_predict(X_test_scaled)

        # Statistical Z-score on holdout
        stat_anomaly = np.zeros(n_test, dtype=int)
        for col in ["debit", "total_due", "debit_mismatch_pct"]:
            if col in test_features.columns:
                vals = test_features[col].values
                mean, std = np.nanmean(vals), np.nanstd(vals)
                if std > 0:
                    z = np.abs((vals - mean) / std)
                    if col == "debit_mismatch_pct":
                        stat_anomaly |= (vals > 0.1).astype(int)
                    else:
                        stat_anomaly |= (z > 2).astype(int)

        # Ensemble voting
        iso_flags = (iso_pred == -1).astype(int)
        lof_flags = (lof_pred == -1).astype(int)
        votes = iso_flags + lof_flags + stat_anomaly
        ensemble_flags = (votes >= 2).astype(int)

        # Method agreement: how often do at least 2 methods agree on each sample?
        n_high = int((votes == 3).sum())      # all 3 agree it's anomalous
        n_medium = int((votes == 2).sum())     # 2 agree
        n_single = int((votes == 1).sum())     # only 1 flagged
        n_none = int((votes == 0).sum())       # none flagged

        holdout_anomaly_count = int(ensemble_flags.sum())
        holdout_anomaly_rate = round(holdout_anomaly_count / n_test * 100, 1) if n_test > 0 else 0

        # Method pairwise agreement rate (average of 3 pairs)
        iso_lof_agree = int((iso_flags == lof_flags).sum())
        iso_stat_agree = int((iso_flags == stat_anomaly).sum())
        lof_stat_agree = int((lof_flags == stat_anomaly).sum())
        avg_agreement = round(((iso_lof_agree + iso_stat_agree + lof_stat_agree) / 3) / n_test * 100, 1) if n_test > 0 else 0

        return {
            "holdout_samples": n_test,
            "holdout_anomalies": holdout_anomaly_count,
            "holdout_anomaly_rate": holdout_anomaly_rate,
            "holdout_confidence_high": n_high,
            "holdout_confidence_medium": n_medium,
            "holdout_single_flag": n_single,
            "holdout_no_flag": n_none,
            "method_agreement_rate": avg_agreement,
        }

    def detect(self, data: dict, model_dir: Path) -> dict:
        invoices, details, accounts = data["invoices"], data["details"], data["accounts"]
        invoices, details, accounts = self._parse_dates(invoices, details, accounts)

        scaler = joblib.load(model_dir / "scaler.joblib")
        iso_forest = joblib.load(model_dir / "isolation_forest.joblib")
        feature_cols = joblib.load(model_dir / "feature_cols.joblib")
        training_stats = joblib.load(model_dir / "training_stats.joblib")

        features = engineer_invoice_features(invoices, details, accounts)
        X, _ = select_model_features(features)

        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0
        X = X[feature_cols]

        X_scaled = scaler.transform(X)

        # Isolation Forest
        features["iso_forest_score"] = iso_forest.predict(X_scaled)
        features["iso_forest_raw"] = iso_forest.decision_function(X_scaled)

        # LOF (fit fresh)
        lof = LocalOutlierFactor(
            n_neighbors=min(20, len(X) - 1), contamination=0.15,
        )
        features["lof_score"] = lof.fit_predict(X_scaled)
        features["lof_raw"] = lof.negative_outlier_factor_

        # Statistical Z-score
        for col in ["debit", "credit", "total_due", "line_debit_sum"]:
            if col in features.columns and col in training_stats:
                mean = training_stats[col]["mean"]
                std = training_stats[col]["std"]
                features[f"{col}_zscore"] = (features[col] - mean) / std if std > 0 else 0

        features["stat_anomaly"] = (
            (features.get("debit_zscore", pd.Series(0, index=features.index)).abs() > 2)
            | (features.get("total_due_zscore", pd.Series(0, index=features.index)).abs() > 2)
            | (features.get("debit_mismatch_pct", pd.Series(0, index=features.index)) > 0.1)
        ).astype(int)

        features["anomaly_votes"] = (
            (features["iso_forest_score"] == -1).astype(int)
            + (features["lof_score"] == -1).astype(int)
            + features["stat_anomaly"]
        )
        features["is_anomaly"] = (features["anomaly_votes"] >= 2).astype(int)

        # Build explanations
        anomalies = features[features["is_anomaly"] == 1]
        explanations = []
        for idx in anomalies.index:
            row = features.loc[idx]
            reasons = []
            if abs(row.get("debit_zscore", 0)) > 2:
                direction = "unusually high" if row.get("debit_zscore", 0) > 0 else "unusually low"
                reasons.append(f"Invoice amount ({row['debit']:.2f}) is {direction}")
            if row.get("debit_mismatch_pct", 0) > 0.1:
                reasons.append(f"Line items sum ({row.get('line_debit_sum', 0):.2f}) differs from invoice total ({row['debit']:.2f}) by {row['debit_mismatch_pct']*100:.1f}%")
            if abs(row.get("debit_zscore_acct", 0)) > 2:
                reasons.append(f"Invoice deviates from account average ({row.get('acct_avg_debit', 0):.2f})")
            if row.get("credit_pct", 0) > 0.5:
                reasons.append(f"High credit ratio ({row['credit_pct']*100:.1f}%)")
            if row.get("negative_line_count", 0) > 3:
                reasons.append(f"Unusual number of credit line items ({int(row['negative_line_count'])})")
            if row.get("has_credit_comment", 0) == 1:
                reasons.append("Contains overcharge/credit comments")
            billing_days = row.get("billing_period_days", 30)
            if pd.notna(billing_days) and (billing_days < 25 or billing_days > 35):
                reasons.append(f"Non-standard billing period ({int(billing_days)} days)")
            if not reasons:
                reasons.append("Flagged by ensemble model (combined pattern deviation)")

            explanations.append({
                "record_id": str(int(row["invoice_no"])),
                "invoice_no": int(row["invoice_no"]),
                "acct_no": int(row["acct_no"]),
                "debit": round(float(row["debit"]), 2),
                "credit": round(float(row["credit"]), 2),
                "total_due": round(float(row["total_due"]), 2),
                "anomaly_votes": int(row["anomaly_votes"]),
                "confidence": "HIGH" if row["anomaly_votes"] == 3 else "MEDIUM",
                "reasons": reasons,
            })

        total = len(features)
        flagged = int(features["is_anomaly"].sum())
        iso_count = int((features["iso_forest_score"] == -1).sum())
        lof_count = int((features["lof_score"] == -1).sum())
        stat_count = int(features["stat_anomaly"].sum())

        # Build charts data
        result_cols = [
            "invoice_no", "acct_no", "debit", "credit", "total_due",
            "line_item_count", "line_debit_sum", "debit_mismatch", "debit_mismatch_pct",
            "debit_zscore_acct", "iso_forest_score", "lof_score", "stat_anomaly",
            "anomaly_votes", "is_anomaly",
        ]
        existing_cols = [c for c in result_cols if c in features.columns]
        results_df = features[existing_cols].copy()
        anomalies_df = results_df[results_df["is_anomaly"] == 1].copy()

        # Replace NaN with None for JSON serialization
        results_df = results_df.where(pd.notnull(results_df), None)
        anomalies_df = anomalies_df.where(pd.notnull(anomalies_df), None)

        charts_data = self._build_charts_data(features, iso_count, lof_count, stat_count, flagged, total)

        return {
            "results_df": results_df,
            "anomalies_df": anomalies_df,
            "summary": {
                "total_records": total,
                "anomalies_found": flagged,
                "anomaly_rate": round(flagged / total * 100, 1) if total > 0 else 0,
                "method_counts": {
                    "isolation_forest": iso_count,
                    "local_outlier_factor": lof_count,
                    "statistical": stat_count,
                    "ensemble": flagged,
                },
                "total_discrepancy_amount": round(float(anomalies_df["debit"].sum()), 2) if len(anomalies_df) > 0 else 0,
                "mean_invoice_amount": round(float(features["debit"].mean()), 2),
            },
            "explanations": explanations,
            "charts_data": charts_data,
        }

    def _build_charts_data(self, features, iso_count, lof_count, stat_count, flagged, total):
        """Build data structures for frontend charts."""
        normal = total - flagged

        # Anomaly distribution pie
        anomaly_pie = [
            {"name": "Normal", "value": normal, "color": "#22c55e"},
            {"name": "Anomaly", "value": flagged, "color": "#ef4444"},
        ]

        # Method comparison bar
        method_bar = [
            {"method": "Isolation Forest", "count": iso_count, "color": "#3b82f6"},
            {"method": "Local Outlier Factor", "count": lof_count, "color": "#8b5cf6"},
            {"method": "Statistical Z-score", "count": stat_count, "color": "#f59e0b"},
            {"method": "Ensemble (2+ agree)", "count": flagged, "color": "#ef4444"},
        ]

        # Debit distribution histogram
        debit_bins = pd.cut(features["debit"], bins=20)
        debit_hist = []
        for interval, count in debit_bins.value_counts().sort_index().items():
            debit_hist.append({
                "range": f"{interval.left:.0f}-{interval.right:.0f}",
                "count": int(count),
                "mid": round((interval.left + interval.right) / 2, 2),
            })

        # Anomaly by account
        acct_anomalies = features.groupby("acct_no").agg(
            total_invoices=("invoice_no", "count"),
            anomalies=("is_anomaly", "sum"),
            total_debit=("debit", "sum"),
        ).reset_index()
        acct_anomalies = acct_anomalies[acct_anomalies["anomalies"] > 0].sort_values("anomalies", ascending=False).head(15)
        acct_chart = []
        for _, row in acct_anomalies.iterrows():
            acct_chart.append({
                "account": str(int(row["acct_no"])),
                "total_invoices": int(row["total_invoices"]),
                "anomalies": int(row["anomalies"]),
                "total_debit": round(float(row["total_debit"]), 2),
            })

        # Confidence distribution
        vote_dist = features["anomaly_votes"].value_counts().sort_index()
        confidence_chart = []
        for votes, count in vote_dist.items():
            label = {0: "No flags", 1: "1 method", 2: "2 methods (MEDIUM)", 3: "3 methods (HIGH)"}.get(votes, str(votes))
            confidence_chart.append({"votes": int(votes), "label": label, "count": int(count)})

        # Scatter: debit vs anomaly score
        scatter_data = []
        for _, row in features.iterrows():
            scatter_data.append({
                "invoice_no": int(row["invoice_no"]),
                "debit": round(float(row["debit"]), 2),
                "iso_score": round(float(row["iso_forest_raw"]), 4),
                "is_anomaly": int(row["is_anomaly"]),
            })

        return {
            "anomaly_distribution": anomaly_pie,
            "method_comparison": method_bar,
            "debit_histogram": debit_hist,
            "account_anomalies": acct_chart,
            "confidence_distribution": confidence_chart,
            "anomaly_scatter": scatter_data,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "anomaly_distribution", "title": "Anomaly Distribution", "type": "pie",
             "description": "Normal vs anomalous invoices"},
            {"id": "method_comparison", "title": "Detection Methods Comparison", "type": "bar",
             "description": "How many invoices each detection method flagged"},
            {"id": "debit_histogram", "title": "Invoice Amount Distribution", "type": "histogram",
             "description": "Distribution of invoice debit amounts"},
            {"id": "account_anomalies", "title": "Anomalies by Account", "type": "bar",
             "description": "Which accounts have the most anomalous invoices"},
            {"id": "confidence_distribution", "title": "Detection Confidence", "type": "bar",
             "description": "How many detection methods agreed on each invoice"},
            {"id": "anomaly_scatter", "title": "Invoice Amount vs Anomaly Score", "type": "scatter",
             "description": "Scatter plot of invoice amounts vs isolation forest scores"},
        ]

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": [
                {"field": "invoice_no", "label": "Invoice Number", "type": "number", "required": True, "description": "Unique invoice identifier"},
                {"field": "acct_no", "label": "Account Number", "type": "number", "required": True, "description": "Account this invoice belongs to"},
                {"field": "debit", "label": "Debit Amount", "type": "number", "required": True, "description": "Total debit/charge on the invoice"},
                {"field": "credit", "label": "Credit Amount", "type": "number", "required": True, "description": "Total credit on the invoice"},
                {"field": "total_due", "label": "Total Due", "type": "number", "required": True, "description": "Total amount due"},
                {"field": "status_cd", "label": "Status Code", "type": "number", "required": False, "description": "Invoice status (2 = paid)"},
                {"field": "bill_from_date", "label": "Billing Period Start", "type": "date", "required": False, "description": "Billing cycle start"},
                {"field": "bill_thru_date", "label": "Billing Period End", "type": "date", "required": False, "description": "Billing cycle end"},
                {"field": "due_date", "label": "Due Date", "type": "date", "required": False, "description": "Payment due date"},
                {"field": "bill_date", "label": "Bill Date", "type": "date", "required": False, "description": "Invoice issue date"},
                {"field": "acct_balance", "label": "Account Balance", "type": "number", "required": False, "description": "Current account balance"},
                {"field": "line_items", "label": "Line Items", "type": "array", "required": False,
                 "description": "Optional list of {seq_num, debit, plan_name, service_no, comments, usage_units}"},
            ],
            "example": {
                "invoice_no": 1001,
                "acct_no": 555,
                "debit": 245.50,
                "credit": 0.0,
                "total_due": 245.50,
                "status_cd": 1,
                "bill_from_date": "2026-04-01",
                "bill_thru_date": "2026-04-30",
                "due_date": "2026-05-15",
                "bill_date": "2026-05-01",
                "acct_balance": 0.0,
                "line_items": [
                    {"seq_num": 1, "debit": 100.0, "plan_name": "Voice", "service_no": "5551234", "usage_units": 250},
                    {"seq_num": 2, "debit": 145.50, "plan_name": "Data", "service_no": "5551234", "usage_units": 12.5},
                ],
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        scaler = joblib.load(model_dir / "scaler.joblib")
        iso_forest = joblib.load(model_dir / "isolation_forest.joblib")
        feature_cols = joblib.load(model_dir / "feature_cols.joblib")
        training_stats = joblib.load(model_dir / "training_stats.joblib")

        feat = self._event_features(event, training_stats)
        X = pd.DataFrame([{c: feat.get(c, 0.0) for c in feature_cols}])
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        X_scaled = scaler.transform(X)

        iso_pred = int(iso_forest.predict(X_scaled)[0])
        iso_raw = float(iso_forest.decision_function(X_scaled)[0])
        iso_flag = iso_pred == -1

        zscores = {}
        for col in ["debit", "credit", "total_due", "line_debit_sum"]:
            if col in training_stats and col in feat:
                std = training_stats[col]["std"]
                zscores[col] = (feat[col] - training_stats[col]["mean"]) / std if std > 0 else 0.0

        debit_z = zscores.get("debit", 0.0)
        total_due_z = zscores.get("total_due", 0.0)
        debit_mismatch_pct = float(feat.get("debit_mismatch_pct", 0.0))
        stat_flag = (
            abs(debit_z) > 2
            or abs(total_due_z) > 2
            or debit_mismatch_pct > 0.1
        )

        flags = int(iso_flag) + int(stat_flag)
        confidence = "HIGH" if flags == 2 else ("MEDIUM" if flags == 1 else "NORMAL")

        reasons = []
        if iso_flag:
            reasons.append("Isolation Forest flagged the invoice as a multi-feature outlier")
        if abs(debit_z) > 2:
            direction = "unusually high" if debit_z > 0 else "unusually low"
            reasons.append(f"Debit amount ({feat.get('debit', 0):.2f}) is {direction} (z={debit_z:.2f})")
        if abs(total_due_z) > 2:
            reasons.append(f"Total due ({feat.get('total_due', 0):.2f}) deviates from typical (z={total_due_z:.2f})")
        if debit_mismatch_pct > 0.1:
            reasons.append(
                f"Line items sum ({feat.get('line_debit_sum', 0):.2f}) differs from invoice total "
                f"({feat.get('debit', 0):.2f}) by {debit_mismatch_pct * 100:.1f}%"
            )
        if feat.get("has_credit_comment", 0) == 1:
            reasons.append("Line items contain overcharge/credit comments")
        if not reasons:
            reasons.append("No anomaly signals detected")

        score = float(np.clip(0.5 - iso_raw, 0.0, 1.0))

        return {
            "is_anomaly": bool(flags >= 1),
            "confidence": confidence,
            "score": round(score, 6),
            "reasons": reasons,
            "details": {
                "iso_forest_flag": bool(iso_flag),
                "stat_flag": bool(stat_flag),
                "iso_forest_raw": round(iso_raw, 6),
                "zscores": {k: round(float(v), 4) for k, v in zscores.items()},
                "debit_mismatch_pct": round(debit_mismatch_pct, 6),
                "invoice_no": event.get("invoice_no"),
                "acct_no": event.get("acct_no"),
            },
        }

    def _event_features(self, event: dict, training_stats: dict) -> dict:
        debit = float(event.get("debit", 0) or 0)
        credit = float(event.get("credit", 0) or 0)
        total_due = float(event.get("total_due", 0) or 0)

        line_items = event.get("line_items") or []
        line_debits = [float(li.get("debit", 0) or 0) for li in line_items]
        line_count = len(line_items)
        line_sum = float(np.sum(line_debits)) if line_debits else 0.0
        line_mean = float(np.mean(line_debits)) if line_debits else 0.0
        line_std = float(np.std(line_debits, ddof=1)) if len(line_debits) > 1 else 0.0
        line_min = float(np.min(line_debits)) if line_debits else 0.0
        line_max = float(np.max(line_debits)) if line_debits else 0.0
        negative_lines = sum(1 for d in line_debits if d < 0)
        zero_lines = sum(1 for d in line_debits if d == 0)
        unique_plans = len({str(li.get("plan_name")) for li in line_items if li.get("plan_name") is not None})
        unique_services = len({str(li.get("service_no")) for li in line_items if li.get("service_no") is not None})
        comments = " ".join(str(li.get("comments", "")) for li in line_items)
        has_credit_comment = int(any(k in comments for k in ["Credit", "Overcharge", "credit", "overcharge"]))

        usage_units = [float(li["usage_units"]) for li in line_items if li.get("usage_units") is not None]
        usage_sum = float(np.sum(usage_units)) if usage_units else 0.0
        usage_max = float(np.max(usage_units)) if usage_units else 0.0

        bill_from = pd.to_datetime(event.get("bill_from_date"), errors="coerce")
        bill_thru = pd.to_datetime(event.get("bill_thru_date"), errors="coerce")
        usage_from = pd.to_datetime(event.get("usage_from_date"), errors="coerce")
        usage_to = pd.to_datetime(event.get("usage_to_date"), errors="coerce")
        due_date = pd.to_datetime(event.get("due_date"), errors="coerce")
        bill_date = pd.to_datetime(event.get("bill_date"), errors="coerce")

        billing_period_days = (bill_thru - bill_from).days if pd.notna(bill_from) and pd.notna(bill_thru) else 0
        usage_period_days = (usage_to - usage_from).days if pd.notna(usage_from) and pd.notna(usage_to) else 0
        days_to_due = (due_date - bill_date).days if pd.notna(due_date) and pd.notna(bill_date) else 0

        debit_credit_ratio = debit / credit if credit > 0 else debit
        credit_pct = credit / debit if debit > 0 else 0.0

        debit_mismatch = abs(debit - line_sum) if line_count > 0 else 0.0
        debit_mismatch_pct = debit_mismatch / debit if debit > 0 and line_count > 0 else 0.0

        acct_avg_debit = training_stats.get("debit", {}).get("mean", debit)
        acct_std_debit = training_stats.get("debit", {}).get("std", 0.0)
        debit_zscore_acct = (debit - acct_avg_debit) / acct_std_debit if acct_std_debit > 0 else 0.0

        return {
            "debit": debit,
            "credit": credit,
            "total_due": total_due,
            "billing_period_days": billing_period_days,
            "usage_period_days": usage_period_days,
            "days_to_due": days_to_due,
            "debit_credit_ratio": debit_credit_ratio,
            "credit_pct": credit_pct,
            "line_item_count": line_count,
            "line_debit_sum": line_sum,
            "line_debit_mean": line_mean,
            "line_debit_std": line_std,
            "line_debit_min": line_min,
            "line_debit_max": line_max,
            "negative_line_count": negative_lines,
            "zero_line_count": zero_lines,
            "unique_plans": unique_plans,
            "unique_services": unique_services,
            "has_credit_comment": has_credit_comment,
            "usage_units_sum": usage_sum,
            "usage_units_max": usage_max,
            "debit_mismatch": debit_mismatch,
            "debit_mismatch_pct": debit_mismatch_pct,
            "debit_zscore_acct": debit_zscore_acct,
            "acct_avg_debit": acct_avg_debit,
            "acct_std_debit": acct_std_debit,
            "acct_invoice_count": 1,
            "acct_balance": float(event.get("acct_balance", 0) or 0),
        }

    def supports_incremental_training(self) -> bool:
        return True
