"""
Product Reviews Sentiment Analysis Plugin for Predictor.

Analyses Amazon product reviews to classify sentiment (Positive / Negative),
extract key topics driving satisfaction or dissatisfaction, and highlight
products / reviewers that need attention.

Compatible dataset:
  https://www.kaggle.com/datasets/miriamodeyianypeter/sentiment-analysis-amazon-product-reviews

Algorithm choices
─────────────────
• Sentiment classification  : TF-IDF (1-3 grams, 20k features, sublinear TF)
                               + Logistic Regression with balanced class weights
                               (handles 5:1 pos/neg imbalance without SMOTE overhead)
• Review quality scoring    : Rule-based on helpful_votes / total_votes ratio
                               + review_length + star_rating consistency
• Topic extraction          : Top discriminative TF-IDF terms per class
                               (using model coefficients — no extra model)

Why Logistic Regression over GBT here:
  - TF-IDF produces sparse, high-dimensional feature vectors; LR handles these
    natively and trains 10× faster than tree-based methods on sparse inputs.
  - L2 regularisation avoids overfitting on short reviews.
  - Calibrated probabilities out of the box.
"""

import re
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.ml_plugins.base import MLPluginBase


# ─────────────────────────────────────────────────────────────────────────────
# Column definitions
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_COLS = [
    {"column": "review_body",      "type": "string",  "description": "Full text of the product review"},
    {"column": "star_rating",      "type": "integer", "description": "Star rating 1–5 given by reviewer"},
]

_OPTIONAL_COLS = [
    {"column": "review_id",        "type": "string",  "description": "Unique review identifier"},
    {"column": "product_id",       "type": "string",  "description": "Product ASIN"},
    {"column": "product_title",    "type": "string",  "description": "Human-readable product name"},
    {"column": "product_category", "type": "string",  "description": "Product category"},
    {"column": "customer_id",      "type": "integer", "description": "Reviewer customer ID"},
    {"column": "review_headline",  "type": "string",  "description": "Short review title"},
    {"column": "helpful_votes",    "type": "integer", "description": "Number of helpful votes"},
    {"column": "total_votes",      "type": "integer", "description": "Total votes on the review"},
    {"column": "vine",             "type": "string",  "description": "Vine reviewer (Y/N)"},
    {"column": "verified_purchase","type": "string",  "description": "Verified purchase flag (Y/N)"},
    {"column": "review_date",      "type": "string",  "description": "Date review was written"},
    {"column": "marketplace",      "type": "string",  "description": "Marketplace (e.g. US)"},
    {"column": "sentiment",        "type": "integer", "description": "Ground-truth label: 1=Positive, 0=Negative (for training / evaluation)"},
]

# Sentiment label mapping
_LABEL_TO_NAME = {1: "Positive", 0: "Negative"}
_NAME_TO_LABEL = {"Positive": 1, "Negative": 0}

# Colours used in charts
_COLORS = {
    "Positive": "#22c55e",
    "Negative": "#ef4444",
    "HIGH":     "#ef4444",
    "MEDIUM":   "#f59e0b",
    "LOW":      "#22c55e",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: text cleaning
# ─────────────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Minimal but effective text cleaning for product reviews."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # remove URLs
    text = re.sub(r"https?://\S+", " ", text)
    # keep letters, digits, common punctuation that carries sentiment signal
    text = re.sub(r"[^a-z0-9\s!?.,-]", " ", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_text(row: pd.Series) -> str:
    """Concatenate headline + body for richer signal."""
    parts = []
    if isinstance(row.get("review_headline"), str) and row["review_headline"].strip():
        parts.append(row["review_headline"].strip())
    if isinstance(row.get("review_body"), str) and row["review_body"].strip():
        parts.append(row["review_body"].strip())
    return " ".join(parts)


def _safe_float(val, default: float = 0.0) -> float:
    """Return a JSON-safe float, replacing NaN/inf with default."""
    try:
        v = float(val)
        if v != v or v == float("inf") or v == float("-inf"):
            return default
        return round(v, 6)
    except Exception:
        return default


def _safe_int(val, default: int = 0) -> int:
    """Return a safe int, replacing NaN with default."""
    try:
        v = float(val)
        if v != v:
            return default
        return int(v)
    except Exception:
        return default


def _clean_val(v):
    """Recursively make a value JSON-safe (no NaN/inf)."""
    if isinstance(v, dict):
        return {k: _clean_val(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean_val(x) for x in v]
    if isinstance(v, float):
        return _safe_float(v)
    if hasattr(v, "item"):          # numpy scalar
        raw = v.item()
        if isinstance(raw, float):
            return _safe_float(raw)
        return raw
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Plugin class
# ─────────────────────────────────────────────────────────────────────────────

class ProductReviewsSentimentPlugin(MLPluginBase):
    plugin_id          = "product_reviews_sentiment"
    plugin_name        = "Product Reviews Sentiment Analysis"
    plugin_description = (
        "Classifies Amazon product reviews as Positive or Negative using a TF-IDF "
        "and Logistic Regression pipeline. Identifies the key words driving each "
        "sentiment class, flags low-confidence predictions, surfaces products with "
        "the highest share of negative reviews, and tracks sentiment trends over time. "
        "Upload your reviews CSV and get actionable insights instantly."
    )
    plugin_category    = "classification"
    plugin_icon        = "star"
    required_files     = [
        {
            "key":         "reviews",
            "label":       "Product Reviews CSV",
            "description": (
                "Review data with at minimum 'review_body' and 'star_rating' columns. "
                "Include a 'sentiment' column (1=Positive, 0=Negative) for training. "
                "Optional: review_id, product_id, product_title, helpful_votes, review_date."
            ),
        }
    ]

    # ------------------------------------------------------------------
    # Schema & validation
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        return {
            "reviews": {
                "required": _REQUIRED_COLS,
                "optional": _OPTIONAL_COLS,
            }
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "reviews":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        actual   = set(df.columns)
        required = [c["column"] for c in _REQUIRED_COLS]
        optional = [c["column"] for c in _OPTIONAL_COLS]

        errors   = [f"Missing required column: '{c}'" for c in required if c not in actual]
        warnings = [f"Missing optional column: '{c}' (adds context/charts)" for c in optional if c not in actual]

        if "review_body" in actual:
            empty = df["review_body"].isna().sum() + (df["review_body"].astype(str).str.strip() == "").sum()
            if empty > 0:
                warnings.append(f"{empty} rows have empty review_body — they will be skipped during detection.")

        if len(df) < 100:
            warnings.append(f"Only {len(df)} rows found. For reliable classification 500+ rows are recommended.")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = data["reviews"].copy()

        if "sentiment" not in df.columns:
            raise ValueError(
                "Training requires a 'sentiment' column (1=Positive, 0=Negative). "
                "For inference without labels use 'Run Detection' instead."
            )

        # Build combined text
        df["_text_raw"] = df.apply(_build_text, axis=1)
        df["_text"]     = df["_text_raw"].apply(_clean_text)

        # Drop rows with empty text
        mask = df["_text"].str.strip() != ""
        if mask.sum() < 50:
            raise ValueError("Too few non-empty review texts to train on (need at least 50).")
        df = df[mask].copy()

        y = df["sentiment"].astype(int)
        if set(y.unique()) - {0, 1}:
            # Try to normalise: 4-5 → 1 (positive), 1-2 → 0 (negative)
            y = (y >= 4).astype(int)
        if len(y.unique()) < 2:
            raise ValueError("Training data must contain both Positive (1) and Negative (0) reviews.")

        X_text = df["_text"].tolist()

        # 80/20 stratified split
        X_train, X_test, y_train, y_test = train_test_split(
            X_text, y, test_size=0.2, random_state=42, stratify=y
        )

        # Pipeline: TF-IDF + Logistic Regression
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 3),
                max_features=20_000,
                sublinear_tf=True,
                min_df=3,
                max_df=0.95,
                strip_accents="unicode",
                analyzer="word",
            )),
            ("clf", LogisticRegression(
                C=1.0,
                class_weight="balanced",   # handles 5:1 pos/neg imbalance
                max_iter=500,
                solver="lbfgs",
                random_state=42,
            )),
        ])

        pipeline.fit(X_train, y_train)

        # Evaluate
        y_pred      = pipeline.predict(X_test)
        y_pred_prob = pipeline.predict_proba(X_test)[:, 1]

        accuracy  = round(float(accuracy_score(y_test, y_pred)) * 100, 1)
        precision = round(float(precision_score(y_test, y_pred, zero_division=0)) * 100, 1)
        recall    = round(float(recall_score(y_test, y_pred, zero_division=0)) * 100, 1)
        f1        = round(float(f1_score(y_test, y_pred, zero_division=0, average="binary")) * 100, 1)
        f1_macro  = round(float(f1_score(y_test, y_pred, zero_division=0, average="macro")) * 100, 1)
        try:
            auc = round(float(roc_auc_score(y_test, y_pred_prob)) * 100, 1)
        except Exception:
            auc = None

        # Per-class breakdown
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        per_class = {}
        for lbl_int, lbl_name in _LABEL_TO_NAME.items():
            key = str(lbl_int)
            if key in report:
                per_class[lbl_name] = {
                    "precision": round(report[key]["precision"] * 100, 1),
                    "recall":    round(report[key]["recall"] * 100, 1),
                    "f1":        round(report[key]["f1-score"] * 100, 1),
                    "support":   int(report[key]["support"]),
                }

        # Top discriminative terms per class
        tfidf    = pipeline.named_steps["tfidf"]
        clf      = pipeline.named_steps["clf"]
        vocab    = np.array(tfidf.get_feature_names_out())
        coefs    = clf.coef_[0]  # positive = Positive sentiment
        top_n    = 15
        top_pos_idx = np.argsort(coefs)[-top_n:][::-1]
        top_neg_idx = np.argsort(coefs)[:top_n]
        top_terms = {
            "Positive": vocab[top_pos_idx].tolist(),
            "Negative": vocab[top_neg_idx].tolist(),
        }

        # Dataset stats
        pos_rate = round(float((y == 1).mean()) * 100, 1)
        neg_rate = round(100.0 - pos_rate, 1)

        # Avg review length
        df["_review_len"] = df["_text_raw"].str.split().str.len().fillna(0)
        avg_review_len = round(float(df["_review_len"].mean()), 1)

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, model_dir / "pipeline.joblib")
        joblib.dump({
            "pos_rate":       pos_rate,
            "neg_rate":       neg_rate,
            "n_train":        len(X_train),
            "avg_review_len": avg_review_len,
            "top_terms":      top_terms,
        }, model_dir / "training_stats.joblib")

        return {
            "n_samples":      len(df),
            "n_train":        len(X_train),
            "n_test":         len(X_test),
            "n_features":     20_000,
            "pos_rate":       pos_rate,
            "neg_rate":       neg_rate,
            "avg_review_len": avg_review_len,
            "accuracy":       accuracy,
            "precision":      precision,
            "recall":         recall,
            "f1_score":       f1,
            "f1_macro":       f1_macro,
            "auc_roc":        auc,
            "per_class":      per_class,
            "top_terms":      top_terms,
            "training_mode":  "full",
        }

    # ------------------------------------------------------------------
    # Detection / Inference
    # ------------------------------------------------------------------

    def detect(self, data: dict, model_dir: Path) -> dict:
        df = data["reviews"].copy()

        pipeline      = joblib.load(model_dir / "pipeline.joblib")
        train_stats   = joblib.load(model_dir / "training_stats.joblib")

        # Build text
        df["_text_raw"] = df.apply(_build_text, axis=1)
        df["_text"]     = df["_text_raw"].apply(_clean_text)

        # Flag empty reviews — still run, but mark separately
        empty_mask = df["_text"].str.strip() == ""

        texts = df["_text"].tolist()

        # Predict (even empty ones — they'll get 0.5 score)
        y_pred_prob_raw = pipeline.predict_proba(texts)
        pos_probs = y_pred_prob_raw[:, 1]
        y_pred    = (pos_probs >= 0.5).astype(int)

        # Confidence tier
        def _confidence(p):
            if p >= 0.80 or p <= 0.20:  return "HIGH"
            if p >= 0.65 or p <= 0.35:  return "MEDIUM"
            return "LOW"

        # Ground truth if available
        has_labels = "sentiment" in df.columns
        if has_labels:
            y_true = df["sentiment"].astype(int)
        else:
            y_true = None

        # Build results DataFrame
        results = df.copy()
        results["predicted_sentiment"] = [_LABEL_TO_NAME[p] for p in y_pred]
        results["sentiment_score"]     = np.round(pos_probs * 100, 1)
        results["confidence"]          = [_confidence(p) for p in pos_probs]
        results["_is_negative"]        = y_pred == 0

        # Review ID
        if "review_id" in results.columns:
            results["_rid"] = results["review_id"].astype(str)
        else:
            results["_rid"] = (results.index + 1).astype(str)

        # Review length
        results["review_length"] = df["_text_raw"].str.split().str.len().fillna(0).astype(int)

        # Helpful rate — fill NaN inputs first to avoid NaN propagation
        if "helpful_votes" in results.columns and "total_votes" in results.columns:
            hv = pd.to_numeric(results["helpful_votes"], errors="coerce").fillna(0)
            tv = pd.to_numeric(results["total_votes"],   errors="coerce").fillna(0)
            results["helpful_rate"] = np.where(
                tv > 0,
                (hv / tv * 100).round(1),
                0.0,
            ).astype(float)
            results["helpful_rate"] = results["helpful_rate"].fillna(0.0)
        else:
            results["helpful_rate"] = 0.0

        # Star vs sentiment consistency flag
        if "star_rating" in results.columns:
            results["rating_sentiment_mismatch"] = (
                ((results["star_rating"] >= 4) & (results["_is_negative"])) |
                ((results["star_rating"] <= 2) & (~results["_is_negative"]))
            )
        else:
            results["rating_sentiment_mismatch"] = False

        # ── Summary ──────────────────────────────────────────────────────────
        total    = len(results)
        neg_count = int(results["_is_negative"].sum())
        pos_count = total - neg_count

        neg_rate  = round(neg_count / total * 100, 1) if total > 0 else 0.0
        pos_rate  = round(100.0 - neg_rate, 1)

        high_conf  = int((results["confidence"] == "HIGH").sum())
        med_conf   = int((results["confidence"] == "MEDIUM").sum())
        low_conf   = int((results["confidence"] == "LOW").sum())

        mismatch_count = int(results["rating_sentiment_mismatch"].sum())

        # Mean star rating — guard against all-NaN column
        if "star_rating" in results.columns:
            _star_mean = pd.to_numeric(results["star_rating"], errors="coerce").mean()
            mean_stars = round(_safe_float(_star_mean, 0.0), 2) if _star_mean == _star_mean else None
        else:
            mean_stars = None

        # Avg review length
        avg_len = round(_safe_float(results["review_length"].mean(), 0.0), 1)

        # Optional evaluation metrics
        eval_metrics = {}
        if has_labels and y_true is not None:
            y_pred_arr = y_pred
            eval_metrics = {
                "accuracy":  round(float(accuracy_score(y_true, y_pred_arr)) * 100, 1),
                "precision": round(float(precision_score(y_true, y_pred_arr, zero_division=0)) * 100, 1),
                "recall":    round(float(recall_score(y_true, y_pred_arr, zero_division=0)) * 100, 1),
                "f1_score":  round(float(f1_score(y_true, y_pred_arr, zero_division=0)) * 100, 1),
                "auc_roc":   None,
            }
            try:
                eval_metrics["auc_roc"] = round(float(roc_auc_score(y_true, pos_probs)) * 100, 1)
            except Exception:
                pass

        summary = {
            # ── base keys (required by DB + frontend) ──
            "total_records":          total,
            "anomalies_found":        neg_count,   # negative reviews = "anomalies"
            "anomaly_rate":           neg_rate,
            # ── model-specific (detection field for frontend) ──
            "reviews_analysed":       total,
            "positive_count":         pos_count,
            "negative_count":         neg_count,
            "positive_rate":          pos_rate,
            "negative_rate":          neg_rate,
            "high_confidence":        high_conf,
            "medium_confidence":      med_conf,
            "low_confidence":         low_conf,
            "rating_sentiment_mismatch": mismatch_count,
            "avg_review_length":      avg_len,
            "mean_star_rating":       mean_stars,
            **eval_metrics,
        }

        # ── Explanations (negative reviews → need attention) ──────────────────
        neg_mask = results["_is_negative"]
        explanations = []

        top_neg_terms = set(train_stats["top_terms"].get("Negative", [])[:20])

        for idx in results[neg_mask].index:
            row = results.loc[idx]
            raw_row = df.loc[idx]

            reasons = self._explain_negative(row, raw_row, top_neg_terms, train_stats)

            exp = {
                "record_id":           str(row["_rid"]),
                "review_id":           str(row["_rid"]),
                "confidence":          str(row["confidence"]),
                "sentiment_score":     _safe_float(row["sentiment_score"], 50.0),
                "predicted_sentiment": str(row["predicted_sentiment"]),
                "reasons":             reasons,
                "star_rating":         _safe_int(raw_row.get("star_rating", 0)),
                "review_length":       _safe_int(row["review_length"]),
                "helpful_rate":        _safe_float(row.get("helpful_rate", 0.0), 0.0),
                "rating_mismatch":     bool(row.get("rating_sentiment_mismatch", False)),
            }

            # Optional enrichment fields
            for col in ["product_id", "product_title", "product_category",
                        "customer_id", "review_date", "review_headline"]:
                if col in results.columns and row.get(col) is not None:
                    exp[col] = str(row[col]) if not isinstance(row[col], (int, float)) else row[col]

            if "review_body" in df.columns:
                body = str(raw_row.get("review_body", ""))
                exp["text_preview"] = body[:160]

            explanations.append(exp)

        # Sort: HIGH confidence first, then by lowest sentiment score
        explanations.sort(key=lambda e: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(e["confidence"], 3),
            e["sentiment_score"],
        ))

        # ── Charts data ───────────────────────────────────────────────────────
        charts_data = self._build_charts_data(results, pos_probs, train_stats)

        # ── Trim results_df ───────────────────────────────────────────────────
        keep_cols = ["_rid", "predicted_sentiment", "sentiment_score", "confidence",
                     "review_length", "rating_sentiment_mismatch"]
        for col in ["star_rating", "product_id", "product_title", "product_category",
                    "review_date", "helpful_votes", "total_votes", "helpful_rate"]:
            if col in results.columns:
                keep_cols.append(col)
        if "sentiment" in results.columns:
            keep_cols.append("sentiment")

        results_df   = results[keep_cols].rename(columns={"_rid": "review_id"}).copy()
        anomalies_df = results[neg_mask][keep_cols].rename(columns={"_rid": "review_id"}).copy()

        results_df   = results_df.where(pd.notnull(results_df), None)
        anomalies_df = anomalies_df.where(pd.notnull(anomalies_df), None)

        # Final NaN sweep — ensures nothing leaks into JSON serialisation
        summary      = _clean_val(summary)
        explanations = _clean_val(explanations)
        charts_data  = _clean_val(charts_data)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    def _explain_negative(self, row: pd.Series, raw_row: pd.Series,
                           top_neg_terms: set, train_stats: dict) -> list[str]:
        """Generate human-readable reasons why this review is classified Negative."""
        reasons = []

        # Star rating clue
        stars = raw_row.get("star_rating", None)
        if stars is not None:
            stars = int(stars)
            if stars <= 2:
                reasons.append(f"Low star rating ({stars}★) is consistent with negative sentiment")
            elif stars >= 4:
                reasons.append(
                    f"Star rating ({stars}★) is unexpectedly high — model detected negative language in the review text"
                )

        # Short vs long review signal
        rev_len = int(row.get("review_length", 0))
        if rev_len < 10:
            reasons.append("Very short review — limited positive language detected")
        elif rev_len > 300:
            reasons.append("Long review — the model detected predominantly negative vocabulary across the text")

        # Review text keyword matching with known negative terms
        body = str(raw_row.get("review_body", "")).lower()
        headline = str(raw_row.get("review_headline", "")).lower()
        combined = body + " " + headline

        matched_neg = [t for t in top_neg_terms if t in combined][:5]
        if matched_neg:
            reasons.append(f"Contains negative signal words: {', '.join(matched_neg[:3])}")

        # Helpful signal — if low helpful_rate but many votes, polarising review
        helpful_rate = _safe_float(row.get("helpful_rate", 0.0), 0.0)
        total_votes  = _safe_int(raw_row.get("total_votes", 0) if "total_votes" in raw_row.index else 0)
        if total_votes >= 5 and helpful_rate < 30:
            reasons.append(f"Low helpfulness ratio ({helpful_rate:.0f}%) with {total_votes} votes — community may dispute the review")
        elif total_votes >= 10 and helpful_rate >= 70:
            reasons.append(f"Highly rated helpful review ({helpful_rate:.0f}%) — negative opinion is likely genuine")

        # Confidence score explanation
        score = float(row.get("sentiment_score", 50))
        conf  = row.get("confidence", "MEDIUM")
        if conf == "HIGH" and score < 30:
            reasons.append(f"Model is highly confident (score {score:.0f}/100) — strong negative signal")
        elif conf == "LOW":
            reasons.append(f"Borderline classification (confidence score {score:.0f}/100) — review may have mixed sentiment")

        if not reasons:
            reasons.append("Combined review vocabulary aligns with negative sentiment patterns learned during training")

        return reasons

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def _build_charts_data(self, results: pd.DataFrame, pos_probs: np.ndarray,
                            train_stats: dict) -> dict:
        charts = {}

        # 1. Sentiment distribution — donut
        pos = int((~results["_is_negative"]).sum())
        neg = int(results["_is_negative"].sum())
        charts["sentiment_distribution"] = [
            {"name": "Positive", "value": pos, "color": _COLORS["Positive"]},
            {"name": "Negative", "value": neg, "color": _COLORS["Negative"]},
        ]

        # 2. Confidence tier distribution — bar
        charts["confidence_distribution"] = [
            {"tier": "HIGH",   "count": int((results["confidence"] == "HIGH").sum()),   "color": "#22c55e"},
            {"tier": "MEDIUM", "count": int((results["confidence"] == "MEDIUM").sum()), "color": "#f59e0b"},
            {"tier": "LOW",    "count": int((results["confidence"] == "LOW").sum()),    "color": "#94a3b8"},
        ]

        # 3. Sentiment score histogram (10 bins)
        scores  = results["sentiment_score"].values
        bins    = list(range(0, 101, 10))
        hist    = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            cnt = int(((scores >= lo) & (scores < hi)).sum())
            hist.append({"range": f"{lo}–{hi}", "count": cnt})
        charts["score_histogram"] = hist

        # 4. Sentiment by star rating
        if "star_rating" in results.columns:
            star_data = []
            for star in sorted(results["star_rating"].dropna().unique()):
                star = int(star)
                mask = results["star_rating"] == star
                total = int(mask.sum())
                if total == 0:
                    continue
                neg_cnt = int(results[mask]["_is_negative"].sum())
                pos_cnt = total - neg_cnt
                star_data.append({
                    "stars":    f"{star}★",
                    "Positive": pos_cnt,
                    "Negative": neg_cnt,
                    "total":    total,
                })
            charts["sentiment_by_star"] = star_data

        # 5. Top negative signal words (from training stats)
        neg_terms = train_stats.get("top_terms", {}).get("Negative", [])
        charts["top_negative_terms"] = [
            {"term": t, "rank": i + 1} for i, t in enumerate(neg_terms[:15])
        ]

        # 6. Top positive signal words
        pos_terms = train_stats.get("top_terms", {}).get("Positive", [])
        charts["top_positive_terms"] = [
            {"term": t, "rank": i + 1} for i, t in enumerate(pos_terms[:15])
        ]

        # 7. Sentiment by product category
        if "product_category" in results.columns:
            cat_data = []
            top_cats = results["product_category"].value_counts().head(10).index
            for cat in top_cats:
                mask = results["product_category"] == cat
                total = int(mask.sum())
                neg_cnt = int(results[mask]["_is_negative"].sum())
                neg_pct = round(neg_cnt / total * 100, 1) if total > 0 else 0
                cat_data.append({
                    "category":   str(cat)[:25],
                    "negative_rate": neg_pct,
                    "total_reviews": total,
                })
            cat_data.sort(key=lambda x: x["negative_rate"], reverse=True)
            charts["sentiment_by_category"] = cat_data

        # 8. Sentiment trend over time
        if "review_date" in results.columns:
            try:
                results["_date"] = pd.to_datetime(results["review_date"], errors="coerce")
                results["_month"] = results["_date"].dt.to_period("M").astype(str)
                monthly = results.groupby("_month").apply(
                    lambda g: pd.Series({
                        "Positive": int((~g["_is_negative"]).sum()),
                        "Negative": int(g["_is_negative"].sum()),
                    })
                ).reset_index()
                monthly.columns = ["month", "Positive", "Negative"]
                monthly = monthly.sort_values("month").tail(24)
                charts["sentiment_over_time"] = monthly.to_dict(orient="records")
            except Exception:
                pass

        # 9. Products with most negative reviews
        if "product_title" in results.columns:
            prod_neg = (
                results.groupby("product_title")
                .agg(
                    total=("_is_negative", "count"),
                    negative=("_is_negative", "sum"),
                )
                .reset_index()
            )
            prod_neg["neg_rate"] = (prod_neg["negative"] / prod_neg["total"] * 100).round(1).fillna(0)
            prod_neg = prod_neg[prod_neg["total"] >= 3]
            prod_neg = prod_neg.sort_values("neg_rate", ascending=False).head(10)
            charts["products_negative_rate"] = [
                {
                    "product":    str(row["product_title"])[:30],
                    "neg_rate":   _safe_float(row["neg_rate"], 0.0),
                    "total":      _safe_int(row["total"]),
                    "negative":   _safe_int(row["negative"]),
                }
                for _, row in prod_neg.iterrows()
            ]
        elif "product_id" in results.columns:
            prod_neg = (
                results.groupby("product_id")
                .agg(total=("_is_negative", "count"), negative=("_is_negative", "sum"))
                .reset_index()
            )
            prod_neg["neg_rate"] = (prod_neg["negative"] / prod_neg["total"] * 100).round(1).fillna(0)
            prod_neg = prod_neg[prod_neg["total"] >= 3]
            prod_neg = prod_neg.sort_values("neg_rate", ascending=False).head(10)
            charts["products_negative_rate"] = [
                {"product": str(r["product_id"]), "neg_rate": _safe_float(r["neg_rate"], 0.0),
                 "total": _safe_int(r["total"]), "negative": _safe_int(r["negative"])}
                for _, r in prod_neg.iterrows()
            ]

        # 10. Review length vs sentiment (scatter-friendly binned data)
        len_bins = [0, 25, 50, 100, 200, 400, 1000, 9999]
        len_labels = ["<25", "25–50", "50–100", "100–200", "200–400", "400–1000", ">1000"]
        results["_len_bin"] = pd.cut(
            results["review_length"], bins=len_bins, labels=len_labels, right=False
        )
        len_data = []
        for lbl in len_labels:
            mask = results["_len_bin"] == lbl
            total = int(mask.sum())
            if total == 0:
                continue
            neg_cnt = int(results[mask]["_is_negative"].sum())
            neg_rate = _safe_float(round(neg_cnt / total * 100, 1) if total > 0 else 0.0)
            len_data.append({
                "length_range": str(lbl),
                "Positive":     int(total - neg_cnt),
                "Negative":     int(neg_cnt),
                "neg_rate":     neg_rate,
            })
        charts["sentiment_by_length"] = len_data

        return charts

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "sentiment_distribution",  "title": "Sentiment Distribution",            "type": "pie",       "description": "Positive vs Negative review breakdown"},
            {"id": "confidence_distribution",  "title": "Prediction Confidence Tiers",       "type": "bar",       "description": "HIGH / MEDIUM / LOW confidence predictions"},
            {"id": "score_histogram",          "title": "Sentiment Score Distribution",      "type": "histogram", "description": "How many reviews fall in each probability bucket"},
            {"id": "sentiment_by_star",        "title": "Sentiment by Star Rating",          "type": "bar",       "description": "Positive/Negative breakdown per star level"},
            {"id": "top_negative_terms",       "title": "Top Negative Signal Words",         "type": "bar",       "description": "Most predictive words for negative sentiment"},
            {"id": "top_positive_terms",       "title": "Top Positive Signal Words",         "type": "bar",       "description": "Most predictive words for positive sentiment"},
            {"id": "sentiment_by_category",    "title": "Negative Rate by Product Category", "type": "bar",       "description": "Which product categories attract the most negative reviews"},
            {"id": "sentiment_over_time",      "title": "Sentiment Trend Over Time",         "type": "line",      "description": "Monthly positive/negative review counts"},
            {"id": "products_negative_rate",   "title": "Products with Most Negative Reviews","type": "bar",      "description": "Top products ranked by negative review rate"},
            {"id": "sentiment_by_length",      "title": "Sentiment by Review Length",        "type": "bar",       "description": "How review length correlates with sentiment"},
        ]

    # ------------------------------------------------------------------
    # Single-entry support (score one review)
    # ------------------------------------------------------------------

    def supports_single_entry(self) -> bool:
        return True

    def get_single_entry_schema(self) -> list[dict]:
        return [
            {
                "field":       "review_body",
                "label":       "Review Text",
                "type":        "text",
                "required":    True,
                "description": "Paste the full product review here",
            },
            {
                "field":       "star_rating",
                "label":       "Star Rating",
                "type":        "select",
                "required":    False,
                "description": "Star rating given by reviewer (1–5)",
                "options":     ["1", "2", "3", "4", "5"],
            },
            {
                "field":       "review_headline",
                "label":       "Review Headline (optional)",
                "type":        "text",
                "required":    False,
                "description": "Short title of the review",
            },
        ]

    def detect_single(self, record: dict, model_dir: Path) -> dict:
        return self.score_event(record, model_dir)

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": [
                {"field": "review_body", "type": "string", "required": True, "description": "Full text of the product review"},
                {"field": "star_rating", "type": "integer", "required": False, "description": "Star rating 1-5 given by the reviewer"},
                {"field": "review_headline", "type": "string", "required": False, "description": "Short title of the review"},
                {"field": "product_id", "type": "string", "required": False, "description": "Product identifier (ASIN or SKU)"},
                {"field": "review_id", "type": "string", "required": False, "description": "Unique review identifier"},
            ],
            "example": {
                "review_id": "rev_10001",
                "product_id": "B07ABC1234",
                "review_headline": "Stopped working after a week",
                "review_body": "Terrible quality. Battery died within days and customer support never replied.",
                "star_rating": 1,
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        pipeline    = joblib.load(model_dir / "pipeline.joblib")
        train_stats = joblib.load(model_dir / "training_stats.joblib")

        row = pd.Series(event)
        text_combined = _build_text(row)
        text_clean    = _clean_text(text_combined)

        if not text_clean.strip():
            return {
                "is_anomaly": False,
                "confidence": "LOW",
                "score":      0.5,
                "reasons":    ["Empty review text - cannot classify"],
                "details":    {"review_id": event.get("review_id"), "product_id": event.get("product_id")},
            }

        probs    = pipeline.predict_proba([text_clean])[0]
        pos_prob = float(probs[1])
        neg_prob = float(probs[0])
        margin   = abs(pos_prob - neg_prob)

        stars = _safe_int(event.get("star_rating", 0)) if event.get("star_rating") is not None else 0
        is_neg = (pos_prob < 0.5) or (1 <= stars <= 2)

        if margin >= 0.60:   conf = "HIGH"
        elif margin >= 0.30: conf = "MEDIUM"
        else:                conf = "LOW"

        top_neg_terms = set(train_stats.get("top_terms", {}).get("Negative", [])[:20])
        if is_neg:
            reasons = self._explain_negative(
                pd.Series({"sentiment_score": neg_prob * 100, "confidence": conf,
                           "review_length": len(text_clean.split()), "helpful_rate": 0.0}),
                row, top_neg_terms, train_stats,
            )
        else:
            reasons = [f"The review language is predominantly positive (score {pos_prob * 100:.0f}/100)"]

        return {
            "is_anomaly":          bool(is_neg),
            "confidence":          conf,
            "score":               round(neg_prob, 4),
            "sentiment_score":     round(pos_prob * 100, 1),
            "predicted_sentiment": "Negative" if is_neg else "Positive",
            "reasons":             reasons,
            "details": {
                "positive_probability": round(pos_prob * 100, 1),
                "negative_probability": round(neg_prob * 100, 1),
                "probability_margin":   round(margin, 4),
                "review_id":            event.get("review_id"),
                "product_id":           event.get("product_id"),
                "star_rating":          stars or None,
                "model_family":         "TF-IDF + LogisticRegression",
            },
        }