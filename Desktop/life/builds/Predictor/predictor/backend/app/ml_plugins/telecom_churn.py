"""
Telecom Customer Churn Prediction Plugin for Predictor.

Predicts which telecom customers are likely to churn using a
gradient boosting classifier (XGBoost with scikit-learn fallback).

Compatible dataset: https://www.kaggle.com/datasets/mnassrib/telecom-churn-datasets
The dataset has two CSV files (churn-bigml-80.csv for training,
churn-bigml-20.csv for testing), but this plugin accepts a single
merged or either file — any CSV with the expected columns works.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.ml_plugins.base import MLPluginBase


# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

# Columns in the Kaggle telecom churn dataset
_REQUIRED_COLS = [
    {"column": "State",                  "type": "string",  "description": "US state abbreviation (e.g. KS, OH)"},
    {"column": "Account length",         "type": "integer", "description": "Number of days the account has been active"},
    {"column": "Area code",              "type": "integer", "description": "Customer area code"},
    {"column": "International plan",     "type": "string",  "description": "Whether customer has international plan (yes/no)"},
    {"column": "Voice mail plan",        "type": "string",  "description": "Whether customer has voice mail plan (yes/no)"},
    {"column": "Number vmail messages",  "type": "integer", "description": "Number of voicemail messages"},
    {"column": "Total day minutes",      "type": "float",   "description": "Total daytime call minutes"},
    {"column": "Total day calls",        "type": "integer", "description": "Total daytime calls"},
    {"column": "Total day charge",       "type": "float",   "description": "Total daytime charges"},
    {"column": "Total eve minutes",      "type": "float",   "description": "Total evening call minutes"},
    {"column": "Total eve calls",        "type": "integer", "description": "Total evening calls"},
    {"column": "Total eve charge",       "type": "float",   "description": "Total evening charges"},
    {"column": "Total night minutes",    "type": "float",   "description": "Total night call minutes"},
    {"column": "Total night calls",      "type": "integer", "description": "Total night calls"},
    {"column": "Total night charge",     "type": "float",   "description": "Total night charges"},
    {"column": "Total intl minutes",     "type": "float",   "description": "Total international call minutes"},
    {"column": "Total intl calls",       "type": "integer", "description": "Total international calls"},
    {"column": "Total intl charge",      "type": "float",   "description": "Total international charges"},
    {"column": "Customer service calls", "type": "integer", "description": "Number of customer service calls made"},
]

_OPTIONAL_COLS = [
    {"column": "Churn",                  "type": "boolean", "description": "Whether the customer churned (True/False). Required for training, optional for prediction."},
    {"column": "Phone number",           "type": "string",  "description": "Customer phone number (used as identifier)"},
]


class TelecomChurnPlugin(MLPluginBase):
    plugin_id          = "telecom_churn"
    plugin_name        = "Telecom Customer Churn Prediction"
    plugin_description = (
        "Predicts which telecom customers are likely to churn using a gradient boosting "
        "classifier. Analyzes usage patterns, service plans, and customer service interactions "
        "to identify at-risk customers before they leave. Upload your customer data CSV and "
        "get churn probability scores with actionable reasons for each customer."
    )
    plugin_category    = "prediction"
    plugin_icon        = "users"
    required_files     = [
        {
            "key":         "customers",
            "label":       "Customer Data CSV",
            "description": "Customer records with usage stats. For training, include a 'Churn' column (True/False). For prediction, this column is optional.",
        }
    ]

    # ------------------------------------------------------------------
    # Schema & validation
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        return {
            "customers": {
                "required": _REQUIRED_COLS,
                "optional": _OPTIONAL_COLS,
            }
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "customers":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        actual = set(df.columns)
        required = [c["column"] for c in _REQUIRED_COLS]
        optional = [c["column"] for c in _OPTIONAL_COLS]

        errors   = [f"Missing required column: '{c}'" for c in required if c not in actual]
        warnings = [f"Missing optional column: '{c}'" for c in optional if c not in actual]

        if len(df) < 50:
            warnings.append(f"Only {len(df)} rows found. For reliable predictions, 200+ rows are recommended.")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _engineer_features(self, df: pd.DataFrame):
        """Build feature matrix from raw customer dataframe."""
        feat = df.copy()

        # Encode binary categoricals
        for col in ["International plan", "Voice mail plan"]:
            if col in feat.columns:
                feat[col] = feat[col].str.strip().str.lower().map({"yes": 1, "no": 0}).fillna(0).astype(int)

        # Encode State as label-encoded integer (low cardinality but useful signal)
        if "State" in feat.columns:
            le = LabelEncoder()
            feat["State_enc"] = le.fit_transform(feat["State"].astype(str))
        else:
            feat["State_enc"] = 0

        # Derived features — these carry significant churn signal
        feat["total_minutes"]     = feat.get("Total day minutes",   0) + feat.get("Total eve minutes",   0) + feat.get("Total night minutes", 0) + feat.get("Total intl minutes", 0)
        feat["total_calls"]       = feat.get("Total day calls",     0) + feat.get("Total eve calls",     0) + feat.get("Total night calls",   0) + feat.get("Total intl calls",   0)
        feat["total_charges"]     = feat.get("Total day charge",    0) + feat.get("Total eve charge",    0) + feat.get("Total night charge",  0) + feat.get("Total intl charge",  0)
        feat["charge_per_minute"] = np.where(feat["total_minutes"] > 0, feat["total_charges"] / feat["total_minutes"], 0)
        feat["intl_call_rate"]    = np.where(feat["total_calls"] > 0,   feat.get("Total intl calls", 0) / feat["total_calls"], 0)
        feat["day_usage_ratio"]   = np.where(feat["total_minutes"] > 0, feat.get("Total day minutes", 0) / feat["total_minutes"], 0)
        feat["eve_usage_ratio"]   = np.where(feat["total_minutes"] > 0, feat.get("Total eve minutes", 0) / feat["total_minutes"], 0)
        # High service call count is a strong churn indicator
        feat["high_service_calls"] = (feat.get("Customer service calls", 0) >= 4).astype(int)
        feat["no_voicemail"]       = (feat.get("Number vmail messages",   0) == 0).astype(int)

        feature_cols = [
            "Account length", "Area code",
            "International plan", "Voice mail plan",
            "Number vmail messages",
            "Total day minutes", "Total day calls", "Total day charge",
            "Total eve minutes", "Total eve calls", "Total eve charge",
            "Total night minutes", "Total night calls", "Total night charge",
            "Total intl minutes", "Total intl calls", "Total intl charge",
            "Customer service calls",
            "State_enc",
            "total_minutes", "total_calls", "total_charges",
            "charge_per_minute", "intl_call_rate",
            "day_usage_ratio", "eve_usage_ratio",
            "high_service_calls", "no_voicemail",
        ]

        # Keep only columns that exist (some may be missing in edge cases)
        feature_cols = [c for c in feature_cols if c in feat.columns]
        X = feat[feature_cols].fillna(0)
        return X, feature_cols

    def _parse_churn_label(self, series: pd.Series) -> pd.Series:
        """Normalize churn column: True/False strings, 1/0, yes/no → int."""
        s = series.astype(str).str.strip().str.lower()
        mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
        return s.map(mapping).fillna(0).astype(int)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = data["customers"].copy()

        if "Churn" not in df.columns:
            raise ValueError(
                "Training requires a 'Churn' column (True/False) in the customer CSV. "
                "For prediction without labels, use the 'Run Detection' mode instead."
            )

        y = self._parse_churn_label(df["Churn"])
        X, feature_cols = self._engineer_features(df)

        if len(y.unique()) < 2:
            raise ValueError("Training data must contain both churned (True) and non-churned (False) customers.")

        # Stratified 80/20 split to preserve churn ratio
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s  = scaler.transform(X_test)

        # Try GradientBoosting first (best results), fallback to RandomForest
        model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.08,
            max_depth=4,
            min_samples_leaf=10,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X_train_s, y_train)

        # Evaluate
        y_pred      = model.predict(X_test_s)
        y_pred_prob = model.predict_proba(X_test_s)[:, 1]

        accuracy  = round(float(accuracy_score(y_test, y_pred)) * 100, 1)
        precision = round(float(precision_score(y_test, y_pred, zero_division=0)) * 100, 1)
        recall    = round(float(recall_score(y_test, y_pred, zero_division=0)) * 100, 1)
        f1        = round(float(f1_score(y_test, y_pred, zero_division=0)) * 100, 1)
        try:
            auc = round(float(roc_auc_score(y_test, y_pred_prob)) * 100, 1)
        except Exception:
            auc = None

        cm = confusion_matrix(y_test, y_pred).tolist()

        # Feature importances for explainability
        importances = dict(zip(feature_cols, model.feature_importances_.tolist()))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

        # Training-time churn stats (used for context in detection)
        churn_rate = round(float(y.mean()) * 100, 1)

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(scaler,       model_dir / "scaler.joblib")
        joblib.dump(model,        model_dir / "model.joblib")
        joblib.dump(feature_cols, model_dir / "feature_cols.joblib")
        joblib.dump({
            "churn_rate":    churn_rate,
            "n_train":       len(X_train),
            "feature_means": dict(zip(feature_cols, X_train.mean().tolist())),
            "top_features":  top_features,
        }, model_dir / "training_stats.joblib")

        return {
            "n_samples":       len(X),
            "n_train":         len(X_train),
            "n_test":          len(X_test),
            "n_features":      len(feature_cols),
            "feature_names":   feature_cols,
            "churn_rate":      churn_rate,
            "accuracy":        accuracy,
            "precision":       precision,
            "recall":          recall,
            "f1_score":        f1,
            "auc_roc":         auc,
            "confusion_matrix": cm,
            "top_features":    top_features,
            "training_mode":   "full",
        }

    # ------------------------------------------------------------------
    # Detection / Prediction
    # ------------------------------------------------------------------

    def detect(self, data: dict, model_dir: Path) -> dict:
        df = data["customers"].copy()

        scaler        = joblib.load(model_dir / "scaler.joblib")
        model         = joblib.load(model_dir / "model.joblib")
        feature_cols  = joblib.load(model_dir / "feature_cols.joblib")
        train_stats   = joblib.load(model_dir / "training_stats.joblib")

        X, _ = self._engineer_features(df)

        # Align columns to what was trained on
        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0
        X = X[feature_cols].fillna(0)

        X_scaled     = scaler.transform(X)
        y_pred       = model.predict(X_scaled)
        y_pred_prob  = model.predict_proba(X_scaled)[:, 1]

        # Ground truth labels (if present — for validation runs)
        has_labels = "Churn" in df.columns
        if has_labels:
            y_true = self._parse_churn_label(df["Churn"])
        else:
            y_true = None

        # Build results DataFrame
        results = df.copy()
        results["churn_prediction"]   = y_pred
        results["churn_probability"]  = np.round(y_pred_prob * 100, 1)

        # Risk tier
        def _risk(prob):
            if prob >= 70:   return "HIGH"
            elif prob >= 40: return "MEDIUM"
            else:            return "LOW"

        results["risk_tier"] = results["churn_probability"].apply(_risk)

        # Identifier column — prefer Phone number, else row index
        if "Phone number" in results.columns:
            results["customer_id"] = results["Phone number"].astype(str)
        else:
            results["customer_id"] = (results.index + 1).astype(str)

        # Build per-customer explanations for churners
        top_feat_names = [f for f, _ in train_stats["top_features"][:8]]
        feat_means     = train_stats["feature_means"]
        explanations   = []

        churn_mask = results["churn_prediction"] == 1
        for idx in results[churn_mask].index:
            row = results.loc[idx]
            raw = df.loc[idx]
            reasons = self._explain_churn(raw, feat_means, train_stats)
            explanations.append({
                "record_id":        row["customer_id"],
                "customer_id":      row["customer_id"],
                "churn_probability": float(row["churn_probability"]),
                "risk_tier":        row["risk_tier"],
                "reasons":          reasons,
                # Key metrics for display
                "customer_service_calls": int(raw.get("Customer service calls", 0)),
                "total_charges":    round(float(raw.get("Total day charge", 0) + raw.get("Total eve charge", 0) + raw.get("Total night charge", 0) + raw.get("Total intl charge", 0)), 2),
                "intl_plan":        str(raw.get("International plan", "no")),
                "account_length":   int(raw.get("Account length", 0)),
                # Confidence label (repurposing the base field name used by RunResults)
                "confidence":       row["risk_tier"],
            })

        # Summary
        total    = len(results)
        churners = int(churn_mask.sum())
        churn_pct = round(churners / total * 100, 1) if total > 0 else 0

        high_risk   = int((results["risk_tier"] == "HIGH").sum())
        medium_risk = int((results["risk_tier"] == "MEDIUM").sum())
        low_risk    = int((results["risk_tier"] == "LOW").sum())

        # Optional accuracy metrics if labels present
        accuracy_metrics = {}
        if has_labels and y_true is not None:
            accuracy_metrics = {
                "accuracy":  round(float(accuracy_score(y_true, y_pred)) * 100, 1),
                "precision": round(float(precision_score(y_true, y_pred, zero_division=0)) * 100, 1),
                "recall":    round(float(recall_score(y_true, y_pred, zero_division=0)) * 100, 1),
                "f1_score":  round(float(f1_score(y_true, y_pred, zero_division=0)) * 100, 1),
            }

        summary = {
            "total_records":    total,
            "anomalies_found":  churners,   # reusing base field for compatibility
            "anomaly_rate":     churn_pct,  # reusing base field for compatibility
            "churners_found":   churners,
            "churn_rate":       churn_pct,
            "high_risk":        high_risk,
            "medium_risk":      medium_risk,
            "low_risk":         low_risk,
            "mean_churn_probability": round(float(y_pred_prob.mean() * 100), 1),
            **accuracy_metrics,
        }

        charts_data = self._build_charts_data(results, y_pred_prob, train_stats)

        # Trim results_df to useful columns
        keep_cols = ["customer_id", "churn_prediction", "churn_probability", "risk_tier"]
        for col in ["State", "Account length", "International plan", "Voice mail plan",
                    "Customer service calls", "Total day charge", "Total eve charge",
                    "Total night charge", "Total intl charge"]:
            if col in results.columns:
                keep_cols.append(col)
        if "Churn" in results.columns:
            keep_cols.append("Churn")

        results_df   = results[keep_cols].copy()
        anomalies_df = results[churn_mask][keep_cols].copy()

        results_df   = results_df.where(pd.notnull(results_df), None)
        anomalies_df = anomalies_df.where(pd.notnull(anomalies_df), None)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    def _explain_churn(self, row: pd.Series, feat_means: dict, train_stats: dict) -> list[str]:
        """Generate human-readable reasons why this customer is predicted to churn."""
        reasons = []

        svc_calls = int(row.get("Customer service calls", 0))
        if svc_calls >= 4:
            reasons.append(f"High number of customer service calls ({svc_calls}) — a strong churn indicator")

        if str(row.get("International plan", "no")).strip().lower() == "yes":
            intl_charge = float(row.get("Total intl charge", 0))
            avg_intl    = feat_means.get("Total intl charge", 3.0)
            if intl_charge > avg_intl * 1.3:
                reasons.append(f"International plan with above-average charges (${intl_charge:.2f} vs avg ${avg_intl:.2f})")
            else:
                reasons.append("Has an international plan (associated with higher churn rates)")

        day_min = float(row.get("Total day minutes", 0))
        avg_day = feat_means.get("Total day minutes", 180)
        if day_min > avg_day * 1.4:
            reasons.append(f"Unusually high daytime usage ({day_min:.0f} min vs avg {avg_day:.0f} min)")

        day_charge = float(row.get("Total day charge", 0))
        avg_charge = feat_means.get("Total day charge", 30)
        if day_charge > avg_charge * 1.4:
            reasons.append(f"High daytime charges (${day_charge:.2f} vs avg ${avg_charge:.2f})")

        vmail = int(row.get("Number vmail messages", 0))
        if vmail == 0 and str(row.get("Voice mail plan", "no")).strip().lower() == "no":
            reasons.append("No voicemail plan and no voicemail messages — low service engagement")

        acc_len = int(row.get("Account length", 0))
        avg_len = feat_means.get("Account length", 100)
        if acc_len < avg_len * 0.5:
            reasons.append(f"Relatively new account ({acc_len} days) — early churn risk")

        if not reasons:
            reasons.append("Combined usage pattern deviates from typical non-churning customers")

        return reasons

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def _build_charts_data(self, results: pd.DataFrame, y_pred_prob: np.ndarray, train_stats: dict) -> dict:
        # 1. Churn distribution pie
        churners = int((results["churn_prediction"] == 1).sum())
        non_churners = len(results) - churners
        churn_pie = [
            {"name": "Retained",  "value": non_churners, "color": "#22c55e"},
            {"name": "Will Churn", "value": churners,    "color": "#ef4444"},
        ]

        # 2. Risk tier distribution bar
        risk_bar = [
            {"tier": "LOW",    "count": int((results["risk_tier"] == "LOW").sum()),    "color": "#22c55e"},
            {"tier": "MEDIUM", "count": int((results["risk_tier"] == "MEDIUM").sum()), "color": "#f59e0b"},
            {"tier": "HIGH",   "count": int((results["risk_tier"] == "HIGH").sum()),   "color": "#ef4444"},
        ]

        # 3. Churn probability histogram
        bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        probs = results["churn_probability"].values
        prob_hist = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            count = int(((probs >= lo) & (probs < hi)).sum())
            prob_hist.append({"range": f"{lo}-{hi}%", "count": count, "mid": (lo + hi) / 2})

        # 4. Feature importance bar
        feature_importance = [
            {"feature": _pretty_feature(f), "importance": round(float(imp) * 100, 1)}
            for f, imp in train_stats["top_features"][:10]
        ]

        # 5. Churn by international plan
        intl_churn = []
        if "International plan" in results.columns:
            for plan_val in ["yes", "no"]:
                mask = results["International plan"].astype(str).str.strip().str.lower() == plan_val
                if mask.sum() > 0:
                    rate = round(float(results[mask]["churn_prediction"].mean()) * 100, 1)
                    intl_churn.append({"plan": f"Intl Plan: {plan_val.capitalize()}", "churn_rate": rate, "count": int(mask.sum())})

        # 6. Churn by customer service call count
        svc_churn = []
        if "Customer service calls" in results.columns:
            for calls in sorted(results["Customer service calls"].dropna().unique()):
                calls = int(calls)
                mask = results["Customer service calls"] == calls
                if mask.sum() >= 1:
                    rate = round(float(results[mask]["churn_prediction"].mean()) * 100, 1) if mask.sum() > 0 else 0
                    svc_churn.append({"calls": str(calls), "churn_rate": rate, "count": int(mask.sum())})
            svc_churn = svc_churn[:10]  # cap at 10 buckets

        return {
            "churn_distribution":   churn_pie,
            "risk_tier_distribution": risk_bar,
            "probability_histogram":  prob_hist,
            "feature_importance":     feature_importance,
            "churn_by_intl_plan":    intl_churn,
            "churn_by_service_calls": svc_churn,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "churn_distribution",    "title": "Churn Distribution",              "type": "pie",       "description": "Predicted churners vs retained customers"},
            {"id": "risk_tier_distribution","title": "Risk Tier Breakdown",              "type": "bar",       "description": "Customers by HIGH / MEDIUM / LOW churn risk"},
            {"id": "probability_histogram", "title": "Churn Probability Distribution",  "type": "histogram", "description": "How many customers fall in each probability bucket"},
            {"id": "feature_importance",    "title": "Top Churn Drivers",               "type": "bar",       "description": "Which features drive the churn prediction most"},
            {"id": "churn_by_intl_plan",    "title": "Churn Rate by International Plan","type": "bar",       "description": "Churn rate for customers with vs without international plan"},
            {"id": "churn_by_service_calls","title": "Churn Rate by Service Calls",     "type": "bar",       "description": "Churn rate broken down by number of customer service calls"},
        ]

    # ------------------------------------------------------------------
    # Single-entry support
    # ------------------------------------------------------------------

    def supports_single_entry(self) -> bool:
        return True

    def get_single_entry_schema(self) -> list[dict]:
        return [
            {"field": "Account length",         "label": "Account Length (days)",     "type": "number",  "required": True,  "description": "How many days the account has been active"},
            {"field": "International plan",      "label": "International Plan",        "type": "select",  "required": True,  "description": "Does the customer have an international plan?", "options": ["yes", "no"]},
            {"field": "Voice mail plan",         "label": "Voice Mail Plan",           "type": "select",  "required": True,  "description": "Does the customer have a voicemail plan?",     "options": ["yes", "no"]},
            {"field": "Number vmail messages",   "label": "Voicemail Messages",        "type": "number",  "required": True,  "description": "Number of voicemail messages"},
            {"field": "Total day minutes",       "label": "Total Day Minutes",         "type": "number",  "required": True,  "description": "Total daytime usage in minutes"},
            {"field": "Total day charge",        "label": "Total Day Charge ($)",      "type": "number",  "required": True,  "description": "Total daytime charges in dollars"},
            {"field": "Total eve minutes",       "label": "Total Evening Minutes",     "type": "number",  "required": False, "description": "Total evening usage in minutes"},
            {"field": "Total eve charge",        "label": "Total Evening Charge ($)",  "type": "number",  "required": False, "description": "Total evening charges"},
            {"field": "Total night minutes",     "label": "Total Night Minutes",       "type": "number",  "required": False, "description": "Total night usage in minutes"},
            {"field": "Total night charge",      "label": "Total Night Charge ($)",    "type": "number",  "required": False, "description": "Total night charges"},
            {"field": "Total intl minutes",      "label": "Total Intl Minutes",        "type": "number",  "required": False, "description": "Total international usage in minutes"},
            {"field": "Total intl calls",        "label": "Total Intl Calls",          "type": "number",  "required": False, "description": "Number of international calls"},
            {"field": "Total intl charge",       "label": "Total Intl Charge ($)",     "type": "number",  "required": False, "description": "Total international charges"},
            {"field": "Customer service calls",  "label": "Customer Service Calls",    "type": "number",  "required": True,  "description": "How many times the customer called support"},
        ]

    def detect_single(self, record: dict, model_dir: Path) -> dict:
        return self.score_event(record, model_dir)

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": self.get_single_entry_schema(),
            "example": {
                "Account length": 128,
                "International plan": "no",
                "Voice mail plan": "yes",
                "Number vmail messages": 25,
                "Total day minutes": 265.1,
                "Total day charge": 45.07,
                "Total eve minutes": 197.4,
                "Total eve charge": 16.78,
                "Total night minutes": 244.7,
                "Total night charge": 11.01,
                "Total intl minutes": 10.0,
                "Total intl calls": 3,
                "Total intl charge": 2.70,
                "Customer service calls": 1,
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        scaler       = joblib.load(model_dir / "scaler.joblib")
        model        = joblib.load(model_dir / "model.joblib")
        feature_cols = joblib.load(model_dir / "feature_cols.joblib")
        train_stats  = joblib.load(model_dir / "training_stats.joblib")

        row = {col: 0 for col in feature_cols}
        row.update(event)

        defaults = {
            "State": "CA", "Area code": 415,
            "Total day calls": 100, "Total eve calls": 100,
            "Total night calls": 100, "Total intl calls": 3,
        }
        for k, v in defaults.items():
            if k not in event:
                row[k] = v

        df_single = pd.DataFrame([row])

        X_single, _ = self._engineer_features(df_single)
        for col in feature_cols:
            if col not in X_single.columns:
                X_single[col] = 0
        X_single = X_single[feature_cols].fillna(0)

        X_scaled = scaler.transform(X_single)
        pred     = model.predict(X_scaled)[0]
        prob     = float(model.predict_proba(X_scaled)[0, 1])

        if prob >= 0.70:   confidence = "HIGH"
        elif prob >= 0.40: confidence = "MEDIUM"
        else:              confidence = "LOW" if prob < 0.20 else "NORMAL"

        risk_tier = "HIGH" if prob >= 0.70 else ("MEDIUM" if prob >= 0.40 else "LOW")
        reasons = self._explain_churn(pd.Series(event), train_stats["feature_means"], train_stats)

        return {
            "is_anomaly":   bool(pred == 1),
            "confidence":   confidence,
            "score":        round(prob, 4),
            "reasons":      reasons,
            "details": {
                "risk_tier":         risk_tier,
                "churn_probability": round(prob * 100, 1),
                "model_family":      "GradientBoosting",
            },
        }


def _pretty_feature(name: str) -> str:
    """Make feature names more readable for charts."""
    mapping = {
        "Customer service calls": "Service Calls",
        "Total day charge":       "Day Charges",
        "Total day minutes":      "Day Minutes",
        "International plan":     "Intl Plan",
        "Total intl charge":      "Intl Charges",
        "Total intl minutes":     "Intl Minutes",
        "Account length":         "Account Age",
        "total_charges":          "Total Charges",
        "total_minutes":          "Total Minutes",
        "charge_per_minute":      "Charge/Minute",
        "Voice mail plan":        "Voicemail Plan",
        "Number vmail messages":  "Voicemail Msgs",
        "high_service_calls":     "High Svc Calls",
        "Total eve charge":       "Eve Charges",
        "Total night charge":     "Night Charges",
        "Total eve minutes":      "Eve Minutes",
        "Total night minutes":    "Night Minutes",
        "day_usage_ratio":        "Day Usage Ratio",
        "intl_call_rate":         "Intl Call Rate",
    }
    return mapping.get(name, name)