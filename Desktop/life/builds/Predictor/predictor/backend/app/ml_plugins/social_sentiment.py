"""
Social Media Sentiment Analysis Plugin for Predictor.

Analyses social media posts using a two-tier emotion taxonomy:

  Tier 1 — Canonical emotion (~20 classes, what the model is trained on)
    Collapsed from 279 messy raw labels via a fuzzy mapping table.
    E.g. "JoyfulReunion", "PlayfulJoy", "Overjoyed"  →  "Joy"
         "EmotionalStorm", "Despair", "Grief"         →  "Sadness"

  Tier 2 — Valence bucket (3 classes, used for summary counts & charts)
    Positive  = Joy, Excitement, Happiness, Love, Gratitude, Pride,
                Hope, Admiration, Amusement, Surprise
    Negative  = Sadness, Anger, Fear, Disgust, Shame
    Neutral   = Neutral, Curiosity, Confusion, Nostalgia

Both tiers are stored on every prediction row.  The TF-IDF classifier is
trained on the ~20-class canonical target (much richer signal than 3 classes,
completely achievable unlike 279).  Valence is derived deterministically from
the predicted canonical emotion — no extra model needed.

Algorithm choices
─────────────────
• Sentiment classification  : TF-IDF (1-2 grams, 15k features, sublinear TF)
                               + Logistic Regression (C=1.5, balanced weights)
• User persona clustering   : K-Means (k=5) on log-engagement + RobustScaler
• Negativity spike detection: Per-user Z-score on negative-valence post ratio
"""

import re
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report,
    f1_score, precision_score, recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from app.ml_plugins.base import MLPluginBase


# ─────────────────────────────────────────────────────────────────────────────
# Tier-1: Raw label → Canonical emotion
# Every unique value seen in the Kaggle dataset is mapped below (case-insensitive,
# whitespace-stripped).  Unknown labels fall back to "Neutral".
# ─────────────────────────────────────────────────────────────────────────────

_RAW_TO_CANONICAL: dict[str, str] = {
    # ── Positive ─────────────────────────────────────────────────────────────
    "joy": "Joy", "joyfulreunion": "Joy", "playfujoy": "Joy",
    "playful joy": "Joy", "overjoyed": "Joy",
    "festive joy": "Joy", "festivejoy": "Joy",
    "elation": "Joy", "euphoria": "Joy", "ecstasy": "Joy",
    "zest": "Joy", "thrill": "Joy", "thrilling journey": "Joy",
    "adrenaline": "Joy",

    "excitement": "Excitement", "enthusiasm": "Excitement",
    "energy": "Excitement", "celebration": "Excitement",
    "engagement": "Excitement", "charged": "Excitement",

    "happiness": "Happiness", "happy": "Happiness",
    "contentment": "Happiness", "satisfaction": "Happiness",
    "fulfillment": "Happiness", "fulfilment": "Happiness",
    "blessed": "Happiness", "serenity": "Happiness",
    "calmness": "Happiness", "calm": "Happiness",
    "tranquility": "Happiness", "harmony": "Happiness",
    "mindfulness": "Happiness", "rejuvenation": "Happiness",
    "coziness": "Happiness", "freedom": "Happiness",
    "relief": "Happiness", "acceptance": "Happiness",
    "positive": "Happiness",    # explicit "Positive" label

    "love": "Love", "affection": "Love", "romance": "Love",
    "adoration": "Love", "tenderness": "Love",
    "compassion": "Love", "compassionate": "Love",
    "empathetic": "Love", "empathy": "Love",
    "kindness": "Love", "kind": "Love",
    "friendship": "Love", "heartwarming": "Love",
    "connection": "Love", "sympathy": "Love", "touched": "Love",

    "gratitude": "Gratitude", "grateful": "Gratitude",
    "appreciation": "Gratitude", "thankfulness": "Gratitude",

    "pride": "Pride", "proud": "Pride",
    "accomplishment": "Pride", "triumph": "Pride",
    "success": "Pride", "confidence": "Pride",
    "empowerment": "Pride", "determination": "Pride",
    "resilience": "Pride",

    "hope": "Hope", "hopeful": "Hope", "optimism": "Hope",
    "anticipation": "Hope", "inspiration": "Hope",
    "inspired": "Hope", "motivation": "Hope",
    "dreamchaser": "Hope", "spark": "Hope", "breakthrough": "Hope",
    "renewed effort": "Hope",

    "admiration": "Admiration", "reverence": "Admiration",
    "awe": "Admiration", "wonder": "Admiration",
    "wonderment": "Admiration", "amazement": "Admiration",
    "grandeur": "Admiration", "mesmerizing": "Admiration",
    "dazzle": "Admiration", "enchantment": "Admiration",
    "captivation": "Admiration", "hypnotic": "Admiration",
    "iconic": "Admiration", "radiance": "Admiration",
    "elegance": "Admiration", "vibrancy": "Admiration",
    "colorful": "Admiration", "creative inspiration": "Admiration",
    "creativity": "Admiration", "artisticburst": "Admiration",
    "artistic burst": "Admiration", "runway creativity": "Admiration",
    "winter magic": "Admiration", "celestial wonder": "Admiration",
    "nature's beauty": "Admiration", "ocean's freedom": "Admiration",
    "marvel": "Admiration",

    "amusement": "Amusement", "playful": "Amusement",
    "enjoyment": "Amusement", "fun": "Amusement",
    "whimsy": "Amusement", "charm": "Amusement",
    "free-spirited": "Amusement", "free spirited": "Amusement",
    "mischievous": "Amusement",
    "culinary odyssey": "Amusement", "culinary adventure": "Amusement",
    "joy in baking": "Amusement",

    "surprise": "Surprise",

    # ── Negative ─────────────────────────────────────────────────────────────
    "sadness": "Sadness", "sad": "Sadness", "grief": "Sadness",
    "sorrow": "Sadness", "melancholy": "Sadness",
    "heartbreak": "Sadness", "heartache": "Sadness",
    "lostlove": "Sadness", "lost love": "Sadness",
    "solitude": "Sadness", "loneliness": "Sadness", "lonely": "Sadness",
    "isolation": "Sadness", "despair": "Sadness",
    "desperation": "Sadness", "desolation": "Sadness",
    "ruins": "Sadness", "darkness": "Sadness",
    "emotionalstorm": "Sadness", "emotional storm": "Sadness",
    "suffering": "Sadness", "exhaustion": "Sadness",
    "loss": "Sadness", "disappointment": "Sadness",
    "disappointed": "Sadness", "bittersweet": "Sadness",
    "bitter": "Sadness", "bitterness": "Sadness",
    "yearning": "Sadness", "negative": "Sadness",

    "anger": "Anger", "rage": "Anger", "resentment": "Anger",
    "frustration": "Anger", "frustrated": "Anger",
    "hate": "Anger", "envy": "Anger", "envious": "Anger",
    "jealousy": "Anger", "jealous": "Anger",
    "betrayal": "Anger", "regret": "Anger",
    "dismissive": "Anger", "bad": "Anger",

    "fear": "Fear", "fearful": "Fear", "anxiety": "Fear",
    "anxious": "Fear", "apprehensive": "Fear",
    "intimidation": "Fear", "intimidated": "Fear",
    "helplessness": "Fear", "overwhelmed": "Fear",
    "devastated": "Fear", "suspense": "Fear", "pressure": "Fear",

    "disgust": "Disgust",
    "shame": "Shame", "embarrassed": "Shame",
    "guilt": "Shame", "ashamed": "Shame",

    # ── Neutral / Ambiguous ───────────────────────────────────────────────────
    "neutral": "Neutral", "indifference": "Neutral",
    "boredom": "Neutral", "bored": "Neutral",
    "numbness": "Neutral", "numb": "Neutral",
    "ambivalence": "Neutral", "ambivalent": "Neutral",
    "pensive": "Neutral", "contemplation": "Neutral",
    "reflection": "Neutral", "introspection": "Neutral",
    "innerjourney": "Neutral", "inner journey": "Neutral",
    "solace": "Neutral", "obstacle": "Neutral",
    "miscalculation": "Neutral", "challenge": "Neutral",
    "emotion": "Neutral", "imagination": "Curiosity",

    "curiosity": "Curiosity", "curious": "Curiosity",
    "intrigue": "Curiosity", "exploration": "Curiosity",
    "adventure": "Curiosity", "journey": "Curiosity",
    "immersion": "Curiosity",

    "confusion": "Confusion",

    "nostalgia": "Nostalgia", "nostalgic": "Nostalgia",
    "whispers of the past": "Nostalgia",
    "envisioning history": "Nostalgia",
}

# ─────────────────────────────────────────────────────────────────────────────
# Tier-2: Canonical emotion → Valence
# ─────────────────────────────────────────────────────────────────────────────

_CANONICAL_TO_VALENCE: dict[str, str] = {
    "Joy":        "Positive",
    "Excitement": "Positive",
    "Happiness":  "Positive",
    "Love":       "Positive",
    "Gratitude":  "Positive",
    "Pride":      "Positive",
    "Hope":       "Positive",
    "Admiration": "Positive",
    "Amusement":  "Positive",
    "Surprise":   "Positive",
    "Sadness":    "Negative",
    "Anger":      "Negative",
    "Fear":       "Negative",
    "Disgust":    "Negative",
    "Shame":      "Negative",
    "Neutral":    "Neutral",
    "Curiosity":  "Neutral",
    "Confusion":  "Neutral",
    "Nostalgia":  "Neutral",
}

_VALENCE_COLORS  = {"Positive": "#22c55e", "Negative": "#ef4444", "Neutral": "#f59e0b"}

_EMOTION_COLORS: dict[str, str] = {
    "Joy":        "#facc15", "Excitement": "#f97316", "Happiness":  "#22c55e",
    "Love":       "#ec4899", "Gratitude":  "#84cc16", "Pride":      "#06b6d4",
    "Hope":       "#3b82f6", "Admiration": "#8b5cf6", "Amusement":  "#f59e0b",
    "Surprise":   "#a78bfa", "Sadness":    "#64748b", "Anger":      "#ef4444",
    "Fear":       "#7c3aed", "Disgust":    "#854d0e", "Shame":      "#9f1239",
    "Neutral":    "#94a3b8", "Curiosity":  "#0ea5e9", "Confusion":  "#d97706",
    "Nostalgia":  "#a16207",
}

_PERSONA_LABELS = [
    "Viral Amplifiers", "Positive Advocates",
    "Neutral Observers", "Negative Voices", "Silent Lurkers",
]
_PERSONA_COLORS = ["#8b5cf6", "#22c55e", "#06b6d4", "#ef4444", "#6b7280"]

_REQUIRED_COLS = [
    {"column": "Text",      "type": "string",  "description": "The post / tweet body"},
    {"column": "Timestamp", "type": "string",  "description": "Date/time the post was created"},
    {"column": "Platform",  "type": "string",  "description": "Social platform (Twitter, Instagram, …)"},
    {"column": "Likes",     "type": "integer", "description": "Number of likes received"},
    {"column": "Retweets",  "type": "integer", "description": "Number of shares/retweets"},
]
_OPTIONAL_COLS = [
    {"column": "User",      "type": "string",  "description": "Username or user ID"},
    {"column": "Hashtags",  "type": "string",  "description": "Hashtags in the post"},
    {"column": "Country",   "type": "string",  "description": "Country of the post"},
    {"column": "Year",      "type": "integer", "description": "Year extracted from timestamp"},
    {"column": "Month",     "type": "integer", "description": "Month extracted from timestamp"},
    {"column": "Day",       "type": "integer", "description": "Day extracted from timestamp"},
    {"column": "Hour",      "type": "integer", "description": "Hour extracted from timestamp"},
    {"column": "Sentiment", "type": "string",
     "description": "Ground-truth label — any of the 279 dataset values or any canonical/valence label. Required for training."},
]


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _raw_to_canonical(raw: str) -> str | None:
    key = str(raw).strip().lower()
    if key in _RAW_TO_CANONICAL:
        return _RAW_TO_CANONICAL[key]
    key2 = re.sub(r"[^a-z\s]", "", key).strip()
    if key2 in _RAW_TO_CANONICAL:
        return _RAW_TO_CANONICAL[key2]
    for token, canonical in _RAW_TO_CANONICAL.items():
        if len(token) >= 4 and key.startswith(token):
            return canonical
    return None


def _canonical_to_valence(canonical: str) -> str:
    return _CANONICAL_TO_VALENCE.get(canonical, "Neutral")


# ─────────────────────────────────────────────────────────────────────────────
# Plugin
# ─────────────────────────────────────────────────────────────────────────────

class SocialSentimentPlugin(MLPluginBase):
    plugin_id          = "social_sentiment"
    plugin_name        = "Social Media Sentiment Analysis"
    plugin_description = (
        "Classifies social media posts using a two-tier emotion taxonomy: "
        "20 canonical emotions (Joy, Sadness, Anger, Fear, Love, …) that roll up to "
        "Positive / Negative / Neutral valence. Handles all 279 messy raw labels in the "
        "Kaggle dataset via a fuzzy mapping table. Clusters users into behavioural personas, "
        "surfaces platform/hashtag/time trends, and flags accounts with abnormal negativity spikes."
    )
    plugin_category = "classification"
    plugin_icon     = "message-circle"
    required_files  = [
        {
            "key":         "posts",
            "label":       "Social Media Posts CSV",
            "description": (
                "Kaggle Social Media Sentiments dataset CSV (or any CSV with "
                "Text, Timestamp, Platform, Likes, Retweets columns). "
                "Include a 'Sentiment' column with any emotion label for training."
            ),
        }
    ]

    # ── Schema & validation ──────────────────────────────────────────────────

    def get_schema(self) -> dict:
        return {"posts": {"required": _REQUIRED_COLS, "optional": _OPTIONAL_COLS}}

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        if file_key != "posts":
            return {"valid": False, "errors": [f"Unknown file key: {file_key}"], "warnings": []}

        actual   = set(df.columns)
        required = [c["column"] for c in _REQUIRED_COLS]
        errors   = [f"Missing required column: '{c}'" for c in required if c not in actual]
        warnings = []

        if "Text" in actual and df["Text"].dropna().str.strip().eq("").mean() > 0.3:
            warnings.append("More than 30% of Text values are empty — results may be unreliable.")
        if len(df) < 100:
            warnings.append(f"Only {len(df)} rows — 500+ rows recommended for robust classification.")
        if "Sentiment" in actual:
            raw_labels = df["Sentiment"].dropna().astype(str).str.strip().unique()
            unmapped   = [l for l in raw_labels if _raw_to_canonical(l) is None]
            if unmapped:
                warnings.append(
                    f"{len(unmapped)} unrecognised label(s) will map to Neutral "
                    f"(e.g. {unmapped[:3]}). Training will still proceed."
                )
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ── Feature helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _clean_text(series: pd.Series) -> pd.Series:
        def clean(t):
            if not isinstance(t, str):
                return ""
            t = re.sub(r"http\S+",      " ", t)
            t = re.sub(r"@\w+",         " ", t)
            t = re.sub(r"#(\w+)",  r" \1 ", t)
            t = re.sub(r"[^a-zA-Z\s']", " ", t)
            return t.lower().strip()
        return series.apply(clean)

    @staticmethod
    def _map_labels(series: pd.Series) -> pd.DataFrame:
        canonical = series.astype(str).apply(lambda x: _raw_to_canonical(x) or "Neutral")
        valence   = canonical.apply(_canonical_to_valence)
        return pd.DataFrame({"canonical": canonical, "valence": valence})

    @staticmethod
    def _engagement_features(df: pd.DataFrame) -> pd.DataFrame:
        f = pd.DataFrame(index=df.index)
        f["likes"]          = pd.to_numeric(df.get("Likes",    0), errors="coerce").fillna(0)
        f["retweets"]       = pd.to_numeric(df.get("Retweets", 0), errors="coerce").fillna(0)
        f["log_likes"]      = np.log1p(f["likes"])
        f["log_retweets"]   = np.log1p(f["retweets"])
        f["log_engagement"] = np.log1p(f["likes"] + f["retweets"])
        return f

    # ── Training ─────────────────────────────────────────────────────────────

    def train(self, data: dict, model_dir: Path, base_model_dir: Path | None = None) -> dict:
        df = data["posts"].copy()

        if "Sentiment" not in df.columns:
            raise ValueError(
                "Training requires a 'Sentiment' column with emotion labels. "
                "For inference on unlabelled data use 'Run Detection' instead."
            )

        label_df = self._map_labels(df["Sentiment"])
        df["canonical_emotion"] = label_df["canonical"].values
        df["valence"]           = label_df["valence"].values
        df["clean_text"]        = self._clean_text(df["Text"])
        df = df[df["clean_text"].str.len() > 0].copy()

        if len(df) < 50:
            raise ValueError("Need at least 50 non-empty posts to train.")

        canonical_dist = df["canonical_emotion"].value_counts()
        valence_dist   = df["valence"].value_counts()

        # Keep only classes with ≥ 5 samples to allow stratified split
        valid_classes = canonical_dist[canonical_dist >= 5].index.tolist()
        df_train      = df[df["canonical_emotion"].isin(valid_classes)].copy()

        if len(df_train) < 50 or len(valid_classes) < 2:
            raise ValueError(
                f"After filtering rare classes, only {len(df_train)} samples / "
                f"{len(valid_classes)} classes remain. Need ≥50 samples and ≥2 classes."
            )

        X = df_train["clean_text"]
        y = df_train["canonical_emotion"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=15000,
                ngram_range=(1, 2),
                sublinear_tf=True,
                min_df=2,
                stop_words="english",
            )),
            ("clf", LogisticRegression(
                C=1.5,
                max_iter=1000,
                class_weight="balanced",
                solver="lbfgs",
                random_state=42,
            )),
        ])
        pipe.fit(X_train, y_train)

        y_pred = pipe.predict(X_test)
        acc  = round(float(accuracy_score(y_test, y_pred)) * 100, 1)
        f1   = round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)) * 100, 1)
        prec = round(float(precision_score(y_test, y_pred, average="weighted", zero_division=0)) * 100, 1)
        rec  = round(float(recall_score(y_test, y_pred, average="weighted", zero_division=0)) * 100, 1)

        # Valence-level accuracy (derived)
        y_test_val = y_test.apply(_canonical_to_valence)
        y_pred_val = pd.Series(y_pred, index=y_test.index).apply(_canonical_to_valence)
        valence_acc = round(float(accuracy_score(y_test_val, y_pred_val)) * 100, 1)

        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        per_class = {
            lbl: {
                "precision": round(v["precision"] * 100, 1),
                "recall":    round(v["recall"] * 100, 1),
                "f1":        round(v["f1-score"] * 100, 1),
                "support":   int(v["support"]),
            }
            for lbl, v in report.items()
            if lbl in valid_classes
        }

        tfidf = pipe.named_steps["tfidf"]
        clf   = pipe.named_steps["clf"]
        terms = tfidf.get_feature_names_out()
        top_terms = {}
        for i, cls in enumerate(clf.classes_):
            coefs = clf.coef_[i]
            idx   = np.argsort(coefs)[-12:][::-1]
            top_terms[cls] = [terms[j] for j in idx]

        # Persona clustering
        eng        = self._engagement_features(df_train)
        scaler     = RobustScaler()
        eng_scaled = scaler.fit_transform(eng[["log_likes", "log_retweets", "log_engagement"]])
        n_clusters = min(5, max(2, len(df_train) // 50))
        kmeans     = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(eng_scaled)
        centroids  = kmeans.cluster_centers_
        order      = np.lexsort((-centroids[:, 0], -centroids[:, 2]))
        persona_map = {
            int(cidx): _PERSONA_LABELS[min(rank, len(_PERSONA_LABELS) - 1)]
            for rank, cidx in enumerate(order)
        }

        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipe,        model_dir / "sentiment_pipe.joblib")
        joblib.dump(kmeans,      model_dir / "kmeans.joblib")
        joblib.dump(scaler,      model_dir / "eng_scaler.joblib")
        joblib.dump(persona_map, model_dir / "persona_map.joblib")
        joblib.dump({
            "top_terms":      top_terms,
            "valence_dist":   valence_dist.to_dict(),
            "canonical_dist": canonical_dist.to_dict(),
            "n_clusters":     n_clusters,
            "per_class":      per_class,
            "classes":        clf.classes_.tolist(),
            "valid_classes":  valid_classes,
        }, model_dir / "training_meta.joblib")

        return {
            "n_samples":            len(df_train),
            "n_train":              len(X_train),
            "n_test":               len(X_test),
            "n_features":           len(terms),
            "n_clusters":           n_clusters,
            "n_emotion_classes":    len(valid_classes),
            "accuracy":             acc,
            "f1_weighted":          f1,
            "precision":            prec,
            "recall":               rec,
            "valence_accuracy":     valence_acc,
            "per_class":            per_class,
            "top_terms":            top_terms,
            "canonical_dist":       canonical_dist.to_dict(),
            "valence_dist":         valence_dist.to_dict(),
            "training_mode":        "full",
        }

    # ── Detection / Inference ────────────────────────────────────────────────

    def detect(self, data: dict, model_dir: Path) -> dict:
        df = data["posts"].copy()

        pipe        = joblib.load(model_dir / "sentiment_pipe.joblib")
        kmeans      = joblib.load(model_dir / "kmeans.joblib")
        scaler      = joblib.load(model_dir / "eng_scaler.joblib")
        persona_map = joblib.load(model_dir / "persona_map.joblib")
        meta        = joblib.load(model_dir / "training_meta.joblib")

        df["clean_text"] = self._clean_text(df["Text"])
        probs   = pipe.predict_proba(df["clean_text"])
        classes = pipe.classes_
        top_idx = probs.argmax(axis=1)

        df["predicted_emotion"]    = [classes[i] for i in top_idx]
        df["predicted_sentiment"]  = df["predicted_emotion"].apply(_canonical_to_valence)
        df["sentiment_confidence"] = probs.max(axis=1).round(4)
        df["confidence"] = df["sentiment_confidence"].apply(
            lambda p: "HIGH" if p >= 0.80 else ("MEDIUM" if p >= 0.55 else "LOW")
        )

        # Ground-truth mapping if Sentiment column present
        if "Sentiment" in df.columns:
            gt = self._map_labels(df["Sentiment"])
            df["gt_canonical"] = gt["canonical"].values
            df["gt_valence"]   = gt["valence"].values

        df["record_id"] = (
            df["User"].astype(str) + "_" + df.index.astype(str)
            if "User" in df.columns
            else "post_" + df.index.astype(str)
        )

        eng = self._engagement_features(df)
        eng_scaled  = scaler.transform(eng[["log_likes", "log_retweets", "log_engagement"]])
        cluster_ids = kmeans.predict(eng_scaled)
        df["persona"] = [persona_map.get(int(c), f"Cluster {c}") for c in cluster_ids]

        # Negativity spike detection
        flagged_mask = pd.Series(False, index=df.index)
        if "User" in df.columns:
            user_neg = df.groupby("User")["predicted_sentiment"].apply(
                lambda s: (s == "Negative").mean()
            )
            neg_std  = user_neg.std() if len(user_neg) > 1 else 0
            z_scores = (user_neg - user_neg.mean()) / (neg_std + 1e-9)
            spiked   = z_scores[z_scores > 2.0].index
            flagged_mask = df["User"].isin(spiked)
        else:
            flagged_mask = (df["predicted_sentiment"] == "Negative") & (df["confidence"] == "HIGH")

        # Explanations
        top_terms    = meta.get("top_terms", {})
        explanations = []
        for idx in df[flagged_mask].index:
            row     = df.loc[idx]
            reasons = self._explain_post(row, top_terms)
            explanations.append({
                "record_id":            row["record_id"],
                "user":                 str(row.get("User", f"post_{idx}")),
                "platform":             str(row.get("Platform", "Unknown")),
                "predicted_sentiment":  row["predicted_sentiment"],
                "predicted_emotion":    row["predicted_emotion"],
                "sentiment_confidence": round(float(row["sentiment_confidence"]) * 100, 1),
                "confidence":           row["confidence"],
                "persona":              row["persona"],
                "likes":                int(eng.loc[idx, "likes"]),
                "retweets":             int(eng.loc[idx, "retweets"]),
                "reasons":              reasons,
                "text_preview":         str(row.get("Text", ""))[:140],
            })

        # Summary
        total      = len(df)
        neg_count  = int((df["predicted_sentiment"] == "Negative").sum())
        pos_count  = int((df["predicted_sentiment"] == "Positive").sum())
        neu_count  = int((df["predicted_sentiment"] == "Neutral").sum())
        flagged_ct = int(flagged_mask.sum())

        top_emotion = df["predicted_emotion"].value_counts().idxmax() if total > 0 else "N/A"

        accuracy_metrics = {}
        if "gt_valence" in df.columns:
            valid = df["gt_valence"].notna()
            if valid.sum() > 10:
                accuracy_metrics = {
                    "accuracy": round(float(accuracy_score(
                        df.loc[valid, "gt_valence"],
                        df.loc[valid, "predicted_sentiment"]
                    )) * 100, 1),
                    "f1_score": round(float(f1_score(
                        df.loc[valid, "gt_valence"],
                        df.loc[valid, "predicted_sentiment"],
                        average="weighted", zero_division=0
                    )) * 100, 1),
                }

        summary = {
            "total_records":            total,
            "anomalies_found":          flagged_ct,
            "anomaly_rate":             round(flagged_ct / total * 100, 1) if total > 0 else 0,
            "sentiment_posts_analysed": total,
            "positive_count":           pos_count,
            "negative_count":           neg_count,
            "neutral_count":            neu_count,
            "positive_rate":            round(pos_count / total * 100, 1) if total > 0 else 0,
            "negative_rate":            round(neg_count / total * 100, 1) if total > 0 else 0,
            "flagged_accounts":         flagged_ct,
            "avg_likes":                round(float(eng["likes"].mean()), 1),
            "avg_retweets":             round(float(eng["retweets"].mean()), 1),
            "personas_found":           int(df["persona"].nunique()),
            "top_emotion":              top_emotion,
            "emotion_classes_detected": int(df["predicted_emotion"].nunique()),
            **accuracy_metrics,
        }

        charts_data = self._build_charts(df, eng, meta)

        keep = ["record_id", "predicted_emotion", "predicted_sentiment",
                "sentiment_confidence", "confidence", "persona"]
        for c in ["User", "Platform", "Likes", "Retweets", "Country", "Text", "Sentiment"]:
            if c in df.columns:
                keep.append(c)

        results_df   = df[keep].copy().where(pd.notnull(df[keep]), None)
        anomalies_df = df[flagged_mask][keep].copy().where(pd.notnull(df[flagged_mask][keep]), None)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    def _explain_post(self, row: pd.Series, top_terms: dict) -> list[str]:
        reasons = []
        emotion = str(row.get("predicted_emotion", ""))
        valence = str(row.get("predicted_sentiment", ""))
        conf    = float(row.get("sentiment_confidence", 0))
        text    = str(row.get("Text", "")).lower()
        likes   = float(row.get("Likes", 0) or 0)
        rts     = float(row.get("Retweets", 0) or 0)

        reasons.append(f"Detected emotion: {emotion} ({valence}, {conf*100:.0f}% confidence)")

        sig  = top_terms.get(emotion, []) + top_terms.get("Sadness", []) + top_terms.get("Anger", [])
        matched = [t for t in dict.fromkeys(sig[:30]) if t in text]
        if matched:
            reasons.append(f"Strong '{emotion}' language detected: {', '.join(matched[:5])}")

        if likes > 500:
            reasons.append(f"High reach — {int(likes):,} likes amplify sentiment impact")
        if rts > 200:
            reasons.append(f"Widely shared — {int(rts):,} retweets/shares")

        platform = str(row.get("Platform", ""))
        if platform and platform != "nan":
            reasons.append(f"Platform: {platform}")

        return reasons

    # ── Charts ───────────────────────────────────────────────────────────────

    def _build_charts(self, df: pd.DataFrame, eng: pd.DataFrame, meta: dict) -> dict:
        out = {}

        # 1. Valence split (pie)
        vcounts = df["predicted_sentiment"].value_counts()
        out["sentiment_distribution"] = [
            {"name": v, "value": int(vcounts.get(v, 0)), "color": _VALENCE_COLORS.get(v, "#888")}
            for v in ["Positive", "Neutral", "Negative"]
        ]

        # 2. Top canonical emotions (bar)
        ecounts = df["predicted_emotion"].value_counts().head(10)
        out["emotion_breakdown"] = [
            {"emotion": e, "count": int(c),
             "color": _EMOTION_COLORS.get(e, "#94a3b8"),
             "valence": _canonical_to_valence(e)}
            for e, c in ecounts.items()
        ]

        # 3. Sentiment by platform (stacked bar)
        if "Platform" in df.columns:
            plat_sent = (
                df.groupby(["Platform", "predicted_sentiment"])
                  .size().unstack(fill_value=0).reset_index()
            )
            out["sentiment_by_platform"] = [
                {"platform": str(r["Platform"]),
                 "Positive": int(r.get("Positive", 0)),
                 "Negative": int(r.get("Negative", 0)),
                 "Neutral":  int(r.get("Neutral",  0))}
                for _, r in plat_sent.iterrows()
            ]

        # 4. Persona distribution (pie)
        pcounts = df["persona"].value_counts()
        out["persona_distribution"] = [
            {"name": p, "value": int(pcounts.get(p, 0)),
             "color": _PERSONA_COLORS[i % len(_PERSONA_COLORS)]}
            for i, p in enumerate(df["persona"].unique())
        ]

        # 5. Engagement by persona
        df2 = df.copy()
        df2["likes_val"]    = eng["likes"].values
        df2["retweets_val"] = eng["retweets"].values
        out["engagement_by_persona"] = (
            df2.groupby("persona")[["likes_val", "retweets_val"]]
               .mean().round(1).reset_index()
               .rename(columns={"likes_val": "avg_likes", "retweets_val": "avg_retweets"})
               .to_dict(orient="records")
        )

        # 6. Sentiment mix per persona (stacked bar)
        ps = (
            df.groupby(["persona", "predicted_sentiment"])
              .size().unstack(fill_value=0).reset_index()
        )
        out["sentiment_by_persona"] = [
            {"persona":  str(r["persona"]),
             "Positive": int(r.get("Positive", 0)),
             "Negative": int(r.get("Negative", 0)),
             "Neutral":  int(r.get("Neutral",  0))}
            for _, r in ps.iterrows()
        ]

        # 7. Emotion breakdown per persona (grouped bar — top 5 emotions per persona)
        ep = (
            df.groupby(["persona", "predicted_emotion"])
              .size().reset_index(name="count")
        )
        out["emotion_by_persona"] = ep.to_dict(orient="records")

        # 8. Confidence distribution
        bins   = [0, 0.55, 0.70, 0.80, 0.90, 1.01]
        labels = ["<55%", "55–70%", "70–80%", "80–90%", "90–100%"]
        cvals  = df["sentiment_confidence"].values
        out["confidence_distribution"] = [
            {"range": lbl,
             "count": int(((cvals >= bins[i]) & (cvals < bins[i + 1])).sum())}
            for i, lbl in enumerate(labels)
        ]

        # 9. Top hashtags
        if "Hashtags" in df.columns:
            all_tags = []
            for ht in df["Hashtags"].dropna():
                all_tags.extend(re.findall(r"#?(\w+)", str(ht).lower()))
            top_ht = Counter(all_tags).most_common(15)
            out["top_hashtags"] = [{"tag": f"#{t}", "count": c} for t, c in top_ht if t]

        # 10. Sentiment over time (monthly)
        if "Timestamp" in df.columns:
            try:
                ts  = pd.to_datetime(df["Timestamp"], errors="coerce")
                df2 = df.copy()
                df2["_month"] = ts.dt.to_period("M").astype(str)
                monthly = (
                    df2.groupby(["_month", "predicted_sentiment"])
                       .size().unstack(fill_value=0).reset_index()
                       .rename(columns={"_month": "month"}).sort_values("month")
                )
                rows = [
                    {"month":    str(r["month"]),
                     "Positive": int(r.get("Positive", 0)),
                     "Negative": int(r.get("Negative", 0)),
                     "Neutral":  int(r.get("Neutral",  0))}
                    for _, r in monthly.iterrows()
                ]
                if len(rows) >= 2:
                    out["sentiment_over_time"] = rows
            except Exception:
                pass

        # 11. Top-10 most-liked posts
        df2 = df.copy()
        df2["_likes"] = eng["likes"].values
        top_liked = df2.nlargest(10, "_likes")
        out["top_liked_posts"] = [
            {"id":        str(r["record_id"]),
             "sentiment": str(r["predicted_sentiment"]),
             "emotion":   str(r["predicted_emotion"]),
             "likes":     int(r["_likes"]),
             "platform":  str(r.get("Platform", "")),
             "color":     _VALENCE_COLORS.get(str(r["predicted_sentiment"]), "#888")}
            for _, r in top_liked.iterrows()
        ]

        # 12. Country distribution
        if "Country" in df.columns:
            ccounts = df["Country"].value_counts().head(12)
            out["country_distribution"] = [
                {"country": str(c), "posts": int(n)} for c, n in ccounts.items()
            ]

        # 13. Sentiment by hour
        hour_col = None
        if "Hour" in df.columns:
            hour_col = df["Hour"]
        elif "Timestamp" in df.columns:
            try:
                hour_col = pd.to_datetime(df["Timestamp"], errors="coerce").dt.hour
            except Exception:
                pass
        if hour_col is not None:
            df2 = df.copy()
            df2["_hour"]  = hour_col
            df2["_score"] = df2["predicted_sentiment"].map(
                {"Positive": 1, "Neutral": 0, "Negative": -1}
            )
            hourly = (
                df2.groupby("_hour")["_score"].mean().round(3)
                   .reset_index()
                   .rename(columns={"_hour": "hour", "_score": "avg_score"})
                   .sort_values("hour")
            )
            if len(hourly) >= 3:
                out["sentiment_by_hour"] = hourly.to_dict(orient="records")

        return out

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "sentiment_distribution",  "title": "Valence Split (Pos/Neu/Neg)",           "type": "pie",  "description": "High-level sentiment across all posts"},
            {"id": "emotion_breakdown",        "title": "Top Emotions Detected",                  "type": "bar",  "description": "Top 10 canonical emotions by frequency"},
            {"id": "sentiment_by_platform",    "title": "Sentiment by Platform",                  "type": "bar",  "description": "Stacked valence breakdown per social platform"},
            {"id": "persona_distribution",     "title": "User Persona Distribution",              "type": "pie",  "description": "How users cluster into behavioural personas"},
            {"id": "engagement_by_persona",    "title": "Avg Engagement by Persona",              "type": "bar",  "description": "Average likes & retweets for each persona"},
            {"id": "sentiment_by_persona",     "title": "Sentiment Mix per Persona",              "type": "bar",  "description": "Pos/Neg/Neu breakdown within each persona"},
            {"id": "emotion_by_persona",       "title": "Emotion Breakdown by Persona",           "type": "bar",  "description": "Which emotions dominate each persona cluster"},
            {"id": "confidence_distribution",  "title": "Prediction Confidence Distribution",     "type": "bar",  "description": "How confident the model is in its predictions"},
            {"id": "top_hashtags",             "title": "Top Hashtags",                           "type": "bar",  "description": "Most used hashtags across all posts"},
            {"id": "sentiment_over_time",      "title": "Sentiment Trend Over Time",              "type": "line", "description": "Monthly valence volume trend"},
            {"id": "top_liked_posts",          "title": "Top 10 Most-Liked Posts",                "type": "bar",  "description": "Highest-engagement posts coloured by valence"},
            {"id": "country_distribution",     "title": "Posts by Country",                       "type": "bar",  "description": "Geographic distribution of posts"},
            {"id": "sentiment_by_hour",        "title": "Sentiment Score by Hour of Day",         "type": "line", "description": "Avg sentiment score by posting hour (1=Pos, 0=Neu, -1=Neg)"},
        ]

    # ── Single-entry ─────────────────────────────────────────────────────────

    def supports_single_entry(self) -> bool:
        return True

    def get_single_entry_schema(self) -> list[dict]:
        return [
            {"field": "Text",     "label": "Post Text",  "type": "text",   "required": True,
             "description": "The social media post or tweet to analyse"},
            {"field": "Likes",    "label": "Likes",       "type": "number", "required": False,
             "description": "Number of likes"},
            {"field": "Retweets", "label": "Retweets",    "type": "number", "required": False,
             "description": "Number of retweets / shares"},
            {"field": "Platform", "label": "Platform",    "type": "select", "required": False,
             "description": "Social platform",
             "options": ["Twitter", "Instagram", "Facebook", "LinkedIn", "Other"]},
        ]

    def detect_single(self, record: dict, model_dir: Path) -> dict:
        pipe        = joblib.load(model_dir / "sentiment_pipe.joblib")
        kmeans      = joblib.load(model_dir / "kmeans.joblib")
        scaler      = joblib.load(model_dir / "eng_scaler.joblib")
        persona_map = joblib.load(model_dir / "persona_map.joblib")
        meta        = joblib.load(model_dir / "training_meta.joblib")

        text_clean = re.sub(r"http\S+|@\w+|[^a-zA-Z\s']", " ",
                            str(record.get("Text", ""))).lower().strip()

        probs   = pipe.predict_proba([text_clean])[0]
        classes = pipe.classes_
        top_idx = np.argsort(probs)[::-1]
        emotion = classes[top_idx[0]]
        valence = _canonical_to_valence(emotion)
        conf    = float(probs[top_idx[0]])
        confidence = "HIGH" if conf >= 0.80 else ("MEDIUM" if conf >= 0.55 else "LOW")

        likes    = float(record.get("Likes",    0) or 0)
        retweets = float(record.get("Retweets", 0) or 0)
        eng_row  = np.array([[np.log1p(likes), np.log1p(retweets), np.log1p(likes + retweets)]])
        persona  = persona_map.get(
            int(kmeans.predict(scaler.transform(eng_row))[0]), "Unknown"
        )

        top_terms = meta.get("top_terms", {})
        matched   = [t for t in top_terms.get(emotion, [])[:20] if t in text_clean]

        top3 = [
            {"emotion":  classes[i],
             "valence":  _canonical_to_valence(classes[i]),
             "prob":     round(float(probs[i]) * 100, 1)}
            for i in top_idx[:3]
        ]

        reasons = [f"Detected emotion: {emotion} ({valence}, {conf*100:.0f}% confidence)"]
        if matched:
            reasons.append(f"Key '{emotion}' language: {', '.join(matched[:5])}")
        reasons.append(f"Assigned persona: {persona}")

        return {
            "is_anomaly":          valence == "Negative" and confidence in ("HIGH", "MEDIUM"),
            "confidence":          confidence,
            "score":               round(conf, 4),
            "predicted_sentiment": valence,
            "predicted_emotion":   emotion,
            "reasons":             reasons,
            "details": {
                "persona":       persona,
                "top_emotions":  top3,
                "probabilities": {classes[i]: round(float(probs[i]), 4) for i in top_idx[:5]},
            },
        }

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": self.get_single_entry_schema(),
            "example": {
                "Text":     "This service is absolutely terrible, I'm so frustrated!",
                "Likes":    12,
                "Retweets": 3,
                "Platform": "Twitter",
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        pipe = joblib.load(model_dir / "sentiment_pipe.joblib")
        meta = joblib.load(model_dir / "training_meta.joblib")

        text_clean = re.sub(r"http\S+|@\w+|[^a-zA-Z\s']", " ",
                            str(event.get("Text", ""))).lower().strip()

        probs   = pipe.predict_proba([text_clean])[0]
        classes = pipe.classes_
        top_idx = int(np.argmax(probs))
        emotion = classes[top_idx]
        valence = _canonical_to_valence(emotion)
        conf    = float(probs[top_idx])
        confidence = "HIGH" if conf >= 0.80 else ("MEDIUM" if conf >= 0.55 else "LOW")

        neg_prob = float(sum(
            probs[i] for i, cls in enumerate(classes)
            if _canonical_to_valence(cls) == "Negative"
        ))

        is_negative = valence == "Negative"
        top_terms = meta.get("top_terms", {}).get(emotion, [])[:20]
        matched = [t for t in top_terms if t in text_clean]
        if matched:
            reasons = matched[:5]
        elif is_negative:
            reasons = ["matched negative pattern"]
        else:
            reasons = [f"Detected {emotion} ({valence}, {conf*100:.0f}% confidence)"]

        return {
            "is_anomaly": is_negative,
            "confidence": confidence,
            "score":      round(neg_prob, 4),
            "reasons":    reasons,
            "details": {
                "predicted_emotion":   emotion,
                "predicted_sentiment": valence,
                "negative_prob":       round(neg_prob, 4),
                "model_family":        "TF-IDF + LogisticRegression",
            },
        }