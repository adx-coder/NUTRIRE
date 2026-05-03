"""
Hardware Failure Detection — Variant: v1_port_group_ensemble
=============================================================

This is the ORIGINAL algorithm re-packaged as a named variant.

Architecture:
  Port-group-based training (A_dwdm_full, C_other).
  Recall-focused F2 threshold optimisation.
  Device-level port-agreement + evidence accumulation for FP reduction.

  Base learners   : RandomForest + LightGBM + XGBoost
  Meta-learner    : Logistic Regression stacking
  Threshold focus : F2 (recall priority — catch as many faults as possible)
  Evidence window : 1.5h sustained signal
  Port agreement  : >=25% of ports on device must vote

Reference scripts: train_hw_v4.py, evaluate_hw_v5.py

Why this exists:
  The `hardware_failure_detection.py` file (variant name "original") implements
  this exact algorithm. This file re-packages it as a named variant so that
  when v2_alarm_group_ensemble.py (train_hw_v5 / evaluate_hw_v6) is introduced,
  this implementation is explicitly preserved and permanently referenceable.

How to activate this variant via the admin API:
  PATCH /api/versions/hardware_failure_detection/plugin-variant
  { "variant_name": "v1_port_group_ensemble" }

Naming convention:
  v1_port_group_ensemble   — Groups by port type (DWDM vs other), F2-recall focus
  v2_alarm_group_ensemble  — Groups by alarm type (T1/T2/T3), F0.5-precision focus
"""

import json
import warnings
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_curve
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

from app.ml_plugins.base import MLPluginBase
from app.ml_plugins._gpu_utils import get_lightgbm_device, get_xgboost_tree_method


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS  (mirrors of train_hw_v4.py / evaluate_hw_v5.py)
# ─────────────────────────────────────────────────────────────────────────────

TRAIN_END  = pd.Timestamp("2026-02-14 23:59:59")
VAL_START  = pd.Timestamp("2026-02-15")
VAL_END    = pd.Timestamp("2026-02-28 23:59:59")
TEST_START = pd.Timestamp("2026-03-01")
TEST_END   = pd.Timestamp("2026-03-31 23:59:59")

HW_TYPE_MIN_POS = 200
HW_SYNTH_ALPHA  = (0.10, 0.90)
HW_SYNTH_SEED   = 99

HW_MIN_POS    = 3
HW_NEG_RATIO  = 4.0
RANDOM_SEED   = 42

# F2 — recall priority
HW_PREC_FLOOR_HIGH  = 0.20
HW_PREC_FLOOR_LOW   = 0.10
HW_MIN_RECALL_FLOOR = 0.30
F_BETA = 2.0

RF_N_ESTIMATORS  = 500
RF_MAX_DEPTH     = 15
RF_MIN_SAMPLES_L = 5

LGB_PARAMS = {
    "objective": "binary", "metric": "binary_logloss",
    "n_estimators": 500, "learning_rate": 0.05, "num_leaves": 31,
    "min_child_samples": 5, "subsample": 0.8, "colsample_bytree": 0.8,
    "reg_alpha": 0.3, "reg_lambda": 1.0, "random_state": 42,
    "verbose": -1, "n_jobs": -1,
}

XGB_PARAMS = {
    "objective": "binary:logistic", "eval_metric": "logloss",
    "n_estimators": 500, "learning_rate": 0.05, "max_depth": 5,
    "min_child_weight": 5, "subsample": 0.8, "colsample_bytree": 0.8,
    "reg_alpha": 0.3, "reg_lambda": 1.0, "random_state": 42,
    "verbosity": 0, "n_jobs": -1,
}

# Inference constants
WINDOW_H   = 2
WINDOW_N   = 8
WARMUP_H   = 24
COOLDOWN_H = 6
MAX_LOOKAHEAD_H   = 6
MIN_LEAD_TIME_MIN = 15

EVIDENCE_H    = 1.5
EVIDENCE_N    = int(EVIDENCE_H * 4)  # 6 readings at 15-min intervals
EVIDENCE_FRAC = 0.50

PORT_AGREEMENT_FRAC = 0.25
PORT_AGREEMENT_MIN  = 2

USE_LGB_IN_VOTE = False   # LGB shows inverted discrimination at inference

HW_TIER1 = {"LOC_FLT", "FECRF", "REM_FLT"}
HW_TIER2 = {"High Temperature Warning", "HITEMP", "INT_HITEMPW",
             "BATTERY", "POWER", "AIRCOND", "RECT"}
HW_TIER3 = {"EQPT_MISSING", "EQPT_FAIL", "EQPT_LATCH", "DESKEW_FAIL"}
HARDWARE_ALARMS  = HW_TIER1 | HW_TIER2 | HW_TIER3
FAULT_SEVERITIES = {"Minor", "Major", "Critical"}

FEAT_SUFFIXES = [
    "mean", "std", "min", "max",
    "trend", "roc", "max_drop",
    "frac_below", "cv", "z_last", "delta_half",
]

_ALARM_REQUIRED_COLS = [
    {"column": "NE Label",              "type": "string",   "description": "Network Element (device) label"},
    {"column": "Alarm Name",            "type": "string",   "description": "Name of the alarm (e.g. LOC_FLT, HITEMP)"},
    {"column": "Severity",              "type": "string",   "description": "Alarm severity: Minor / Major / Critical"},
    {"column": "Network Raised Time",   "type": "datetime", "description": "Timestamp when the alarm was raised"},
]
_ALARM_OPTIONAL_COLS = [
    {"column": "Identifier",            "type": "string",   "description": "Alarm identifier"},
    {"column": "NE IP Address",         "type": "string",   "description": "IP address of the NE"},
    {"column": "Alarm State",           "type": "string",   "description": "Current alarm state"},
    {"column": "Network Cleared Time",  "type": "datetime", "description": "Timestamp when the alarm was cleared"},
    {"column": "Life Time (min)",        "type": "float",    "description": "Alarm lifetime in minutes"},
    {"column": "Flap Count",            "type": "integer",  "description": "Number of times alarm flapped"},
]
_PM_REQUIRED_COLS = [
    {"column": "DATE",        "type": "datetime", "description": "PM measurement timestamp (15-min intervals)"},
    {"column": "Device Name", "type": "string",   "description": "Device/NE name"},
    {"column": "OBJECT",      "type": "string",   "description": "Port object identifier (e.g. AM01-1-11)"},
]
_PM_OPTIONAL_COLS = [
    {"column": "OPRMIN",    "type": "float", "description": "Optical power receive minimum"},
    {"column": "OPRAVG",    "type": "float", "description": "Optical power receive average"},
    {"column": "QMIN",      "type": "float", "description": "Q-factor minimum"},
    {"column": "QAVG",      "type": "float", "description": "Q-factor average"},
    {"column": "PRFBERMAX", "type": "float", "description": "Pre-FEC BER maximum"},
    {"column": "ES",        "type": "float", "description": "Errored seconds"},
    {"column": "SES",       "type": "float", "description": "Severely errored seconds"},
]


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _assign_port_group(obj: str) -> str:
    sfx = str(obj).split("-")[-1]
    if sfx in {"11", "12"}:
        return "A_dwdm_full"
    if any(str(obj).upper().startswith(p) for p in ["ODU", "OCH", "OTU"]):
        return "B_subchannel"
    return "C_other"


def _fbeta_score(p: float, r: float, beta: float = 2.0) -> float:
    b2 = beta ** 2
    d  = b2 * p + r
    return (1 + b2) * p * r / d if d > 0 else 0.0


def _find_best_threshold(y_true, y_prob, beta=2.0,
                         prec_floor_high=0.20, prec_floor_low=0.10,
                         min_recall_floor=0.30):
    prec_arr, rec_arr, thresholds = precision_recall_curve(y_true, y_prob)

    def scan(prec_floor=0.0, rec_floor=0.0):
        best = (-1, 0.5, 0.0, 0.0)
        for i, t in enumerate(thresholds):
            p, r = prec_arr[i], rec_arr[i]
            if p < prec_floor or r < rec_floor:
                continue
            fb = _fbeta_score(p, r, beta)
            if fb > best[0]:
                best = (fb, float(t), float(p), float(r))
        return best

    fb, t, p, r = scan(prec_floor_high)
    if fb > 0:
        return t, p, r, fb, 1

    fb, t, p, r = scan(prec_floor_low)
    if fb > 0:
        return t, p, r, fb, 2

    best_p, best_t, best_r, best_fb = 0.0, 0.5, 0.0, 0.0
    for i, t_c in enumerate(thresholds):
        p, r = prec_arr[i], rec_arr[i]
        if r >= min_recall_floor and p > best_p:
            best_p, best_t, best_r = p, float(t_c), r
            best_fb = _fbeta_score(p, r, beta)
    if best_p > 0:
        return best_t, best_p, best_r, best_fb, 3

    fb, t, p, r = scan(0.0)
    return t, p, r, fb, 0


def _prepare_features(df_split, feat_cols, imputer=None, scaler=None, fit=False):
    X = df_split[feat_cols].values.astype(float)
    if fit:
        imputer = SimpleImputer(strategy="median")
        X = imputer.fit_transform(X)
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
    else:
        X = imputer.transform(X)
        X = scaler.transform(X)
    return X, imputer, scaler


def _per_type_hw_upsample(tr_hw, feat_cols, min_pos, alpha_range, seed):
    if tr_hw.empty or not feat_cols:
        return pd.DataFrame()
    rng  = np.random.default_rng(seed)
    rows = []
    for alarm_type, grp in tr_hw.groupby("alarm_name"):
        n_have = len(grp)
        n_need = max(0, min_pos - n_have)
        if n_need == 0:
            continue
        if n_have < 2:
            for _ in range(n_need):
                rows.append(grp.iloc[0].to_dict())
            continue
        feat_vals = grp[feat_cols].values.astype(float)
        col_meds  = np.nanmedian(feat_vals, axis=0)
        for ci in range(feat_vals.shape[1]):
            nans = np.isnan(feat_vals[:, ci])
            if nans.any():
                feat_vals[nans, ci] = col_meds[ci]
        idx_arr = np.arange(n_have)
        generated = 0
        attempts  = 0
        while generated < n_need and attempts < n_need * 50:
            attempts += 1
            i, j  = rng.choice(idx_arr, size=2, replace=False)
            alpha = rng.uniform(*alpha_range)
            synth = alpha * feat_vals[i] + (1 - alpha) * feat_vals[j]
            base    = grp.iloc[i]
            t_i     = base["split_date"]
            t_j     = grp.iloc[j]["split_date"]
            synth_split = (
                t_i + alpha * (t_j - t_i)
                if pd.notna(t_i) and pd.notna(t_j) else t_i
            )
            row = dict(zip(feat_cols, synth))
            row.update({
                "label": 2, "is_synthetic": True,
                "window_end": pd.NaT, "split_date": synth_split,
                "device": base.get("device", ""),
                "object": base.get("object", ""),
                "port_group": base.get("port_group", ""),
                "alarm_time": pd.NaT, "alarm_name": alarm_type,
                "window_len": base.get("window_len", 8),
                "hw_excl": False,
            })
            rows.append(row)
            generated += 1
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _downsample_negatives_stratified(neg_df, target_n, seed):
    if len(neg_df) <= target_n:
        return neg_df.copy()
    rng = np.random.default_rng(seed)
    neg_df = neg_df.copy()
    neg_df["_month"] = neg_df["split_date"].dt.to_period("M")
    month_counts = neg_df["_month"].value_counts()
    n_months     = len(month_counts)
    per_month    = max(1, target_n // n_months)
    kept, budget = [], target_n
    for mo in month_counts.index:
        mo_df = neg_df[neg_df["_month"] == mo]
        quota = min(per_month, len(mo_df), budget)
        if quota <= 0:
            continue
        kept.append(mo_df.iloc[rng.choice(len(mo_df), size=quota, replace=False)])
        budget -= quota
    return pd.concat(kept, ignore_index=True).drop(columns=["_month"])


def _exclude_hw_zone_negatives(neg_df):
    if "hw_excl" not in neg_df.columns:
        return neg_df
    return neg_df[~neg_df["hw_excl"]].copy()


def _compute_window_features_vec(port_df, metrics, metric_feat_cols, window_n):
    n_rows     = len(port_df)
    n_features = len(metric_feat_cols)
    X = np.full((n_rows, n_features), np.nan, dtype=np.float64)

    feat_idx_map = {}
    for idx, fc in enumerate(metric_feat_cols):
        for suf in FEAT_SUFFIXES:
            if fc.endswith(f"_{suf}"):
                base = fc[:-(len(suf) + 1)]
                feat_idx_map[(base, suf)] = idx
                break

    for m in metrics:
        if m not in port_df.columns:
            continue
        col = port_df[m].values.astype(np.float64)
        for i in range(n_rows):
            start = max(0, i - window_n + 1)
            w     = col[start: i + 1]
            valid = w[~np.isnan(w)]
            if len(valid) == 0:
                continue
            mean_v  = float(np.mean(valid))
            std_v   = float(np.std(valid)) if len(valid) > 1 else 0.0
            min_v   = float(np.min(valid))
            max_v   = float(np.max(valid))
            trend_v = float(np.polyfit(np.arange(len(valid), dtype=float), valid, 1)[0]) if len(valid) >= 3 else 0.0
            roc_v        = float(valid[-1] - valid[0]) if len(valid) >= 2 else 0.0
            max_drop_v   = float(np.max(valid) - np.min(valid)) if len(valid) >= 2 else 0.0
            frac_below_v = float(np.mean(valid < mean_v))
            cv_v         = (std_v / abs(mean_v)) if abs(mean_v) > 1e-9 else 0.0
            z_last_v     = ((valid[-1] - mean_v) / std_v) if std_v > 1e-9 else 0.0
            mid          = max(1, len(valid) // 2)
            delta_half_v = float(np.mean(valid[mid:]) - np.mean(valid[:mid])) if len(valid) >= 4 else 0.0
            for suf, val in {
                "mean": mean_v, "std": std_v, "min": min_v, "max": max_v,
                "trend": trend_v, "roc": roc_v, "max_drop": max_drop_v,
                "frac_below": frac_below_v, "cv": cv_v,
                "z_last": z_last_v, "delta_half": delta_half_v,
            }.items():
                idx2 = feat_idx_map.get((m, suf))
                if idx2 is not None:
                    X[i, idx2] = val
    return X


def _window_features_from_values(valid: np.ndarray) -> dict:
    if len(valid) == 0:
        return {}
    mean_v  = float(np.mean(valid))
    std_v   = float(np.std(valid)) if len(valid) > 1 else 0.0
    trend_v = float(np.polyfit(np.arange(len(valid), dtype=float), valid, 1)[0]) if len(valid) >= 3 else 0.0
    mid     = max(1, len(valid) // 2)
    return {
        "mean":       mean_v,
        "std":        std_v,
        "min":        float(np.min(valid)),
        "max":        float(np.max(valid)),
        "trend":      trend_v,
        "roc":        float(valid[-1] - valid[0]) if len(valid) >= 2 else 0.0,
        "max_drop":   float(np.max(valid) - np.min(valid)) if len(valid) >= 2 else 0.0,
        "frac_below": float(np.mean(valid < mean_v)),
        "cv":         (std_v / abs(mean_v)) if abs(mean_v) > 1e-9 else 0.0,
        "z_last":     ((valid[-1] - mean_v) / std_v) if std_v > 1e-9 else 0.0,
        "delta_half": float(np.mean(valid[mid:]) - np.mean(valid[:mid])) if len(valid) >= 4 else 0.0,
    }


def _build_feature_mask_from_pm(pm_df: pd.DataFrame, min_fill_rate: float = 0.10) -> dict:
    non_metric_cols = {"DATE", "Device Name", "IP Address", "OBJECT",
                       "OCHESTLENGTH", "fault_label", "fault_tier",
                       "alarm_name", "alarm_time"}
    metric_candidates = [c for c in pm_df.columns if c not in non_metric_cols]
    feature_mask: dict = {}
    for pg in ["A_dwdm_full", "C_other"]:
        pg_mask = pm_df["OBJECT"].apply(_assign_port_group) == pg
        pg_df   = pm_df[pg_mask]
        if pg_df.empty:
            continue
        good_metrics = [
            m for m in metric_candidates
            if m in pg_df.columns and pg_df[m].notna().mean() >= min_fill_rate
        ]
        if good_metrics:
            feature_mask[pg] = good_metrics
    return feature_mask


def _build_feature_mask_from_windows(windows_df: pd.DataFrame, min_fill_rate: float = 0.10) -> dict:
    """Derive feature mask from pre-processed windows DataFrame."""
    meta_cols = {"split_date", "window_end", "device", "object", "port_group",
                 "label", "alarm_name", "alarm_group", "alarm_time",
                 "window_len", "is_synthetic", "hw_excl"}
    metric_cols = [c for c in windows_df.columns if c not in meta_cols]
    base_metrics = set()
    for col in metric_cols:
        for suffix in ["mean", "std", "min", "max", "trend", "roc", "max_drop", "frac_below", "cv", "z_last", "delta_half"]:
            if col.endswith(f"_{suffix}"):
                base_metrics.add(col.rsplit(f"_{suffix}", 1)[0])
                break
    feature_mask: dict = {}
    for pg in ["A_dwdm_full", "C_other"]:
        pg_df = windows_df[windows_df["port_group"] == pg]
        if pg_df.empty:
            continue
        good_metrics = []
        for m in base_metrics:
            metric_pattern = f"{m}_"
            metric_cols_for_m = [c for c in metric_cols if c.startswith(metric_pattern)]
            if not metric_cols_for_m:
                continue
            fill = pg_df[metric_cols_for_m].notna().mean().mean()
            if fill >= min_fill_rate:
                good_metrics.append(m)
        if good_metrics:
            feature_mask[pg] = good_metrics
    return feature_mask


def _build_windows_from_labeled_pm(pm_df: pd.DataFrame, alarm_df: pd.DataFrame,
                                    feature_mask: dict) -> pd.DataFrame:
    """Build windows from pre-labeled PM data (merged dataset with fault_label column)."""
    pm_df = pm_df.copy()
    pm_df["DATE"] = pd.to_datetime(pm_df["DATE"], errors="coerce")
    pm_df["Device Name"] = pm_df["Device Name"].astype(str).str.strip()
    pm_df["OBJECT"] = pm_df["OBJECT"].astype(str).str.strip()
    pm_df = pm_df.dropna(subset=["DATE"]).sort_values(["Device Name", "OBJECT", "DATE"]).reset_index(drop=True)
    if "fault_label" not in pm_df.columns:
        raise ValueError("Merged dataset must contain 'fault_label' column")
    window_rows = []
    for (device, obj), port_df in pm_df.groupby(["Device Name", "OBJECT"], sort=False):
        pg = _assign_port_group(obj)
        if pg not in feature_mask:
            continue
        group_metrics = feature_mask.get(pg, [])
        if not group_metrics:
            continue
        port_df = port_df.sort_values("DATE").reset_index(drop=True)
        port_times = port_df["DATE"].values
        n = len(port_df)
        if "fault_label" not in port_df.columns:
            continue
        labels = port_df["fault_label"].values
        for i in range(7, n):  # WINDOW_N=8
            t_split = pd.Timestamp(port_times[i])
            start = max(0, i - 7)
            window = port_df.iloc[start: i + 1]
            if len(window) < 4:
                continue
            lbl = int(labels[i])
            alarm_name_val = str(port_df.iloc[i].get("alarm_name", "")) if lbl == 2 else str(port_df.iloc[i].get("alarm_name", ""))
            row_data = {"split_date": t_split, "device": device, "object": obj,
                        "port_group": pg, "label": lbl, "alarm_name": alarm_name_val,
                        "is_synthetic": False, "window_end": t_split, "window_len": len(window)}
            for m in group_metrics:
                if m not in window.columns:
                    continue
                col_vals = window[m].values.astype(float)
                valid = col_vals[~np.isnan(col_vals)]
                if len(valid) == 0:
                    continue
                row_data[f"{m}_mean"] = float(np.mean(valid))
                row_data[f"{m}_std"] = float(np.std(valid)) if len(valid) > 1 else 0.0
                row_data[f"{m}_min"] = float(np.min(valid))
                row_data[f"{m}_max"] = float(np.max(valid))
            window_rows.append(row_data)
    if not window_rows:
        raise ValueError("No windows could be built from the provided merged dataset.")
    return pd.DataFrame(window_rows)


def _build_windows_from_raw(pm_df: pd.DataFrame, alarm_df: pd.DataFrame,
                              feature_mask: dict) -> pd.DataFrame:
    pm_df = pm_df.copy()
    pm_df["DATE"]        = pd.to_datetime(pm_df["DATE"], errors="coerce")
    pm_df["Device Name"] = pm_df["Device Name"].astype(str).str.strip()
    pm_df["OBJECT"]      = pm_df["OBJECT"].astype(str).str.strip()
    pm_df = pm_df.dropna(subset=["DATE"]).sort_values(["Device Name", "OBJECT", "DATE"]).reset_index(drop=True)

    alarm_df = alarm_df.copy()
    alarm_df.columns = [str(c).strip() for c in alarm_df.columns]

    col_map = {}
    for c in alarm_df.columns:
        cl = c.lower().replace(" ", "_")
        if "alarm_name" in cl or "alarm name" in c.lower():
            col_map[c] = "alarm_name"
        elif "ne_label" in cl or "ne label" in c.lower():
            col_map[c] = "device"
        elif ("network_raised" in cl or "raised" in cl) and "raised_time" not in col_map.values():
            col_map[c] = "raised_time"
        elif "severity" in cl and "severity" not in col_map.values():
            col_map[c] = "severity"
    alarm_df = alarm_df.rename(columns=col_map)

    required_alarm_cols = {"alarm_name", "device", "raised_time", "severity"}
    if not required_alarm_cols.issubset(set(alarm_df.columns)):
        missing = required_alarm_cols - set(alarm_df.columns)
        raise ValueError(f"Alarm data missing columns after normalisation: {missing}")

    alarm_df["raised_time"] = pd.to_datetime(alarm_df["raised_time"], errors="coerce")
    alarm_df = alarm_df.dropna(subset=["raised_time"])
    alarm_df["device"]     = alarm_df["device"].astype(str).str.strip()
    alarm_df["alarm_name"] = alarm_df["alarm_name"].astype(str).str.strip()
    alarm_df["severity"]   = alarm_df["severity"].astype(str).str.strip()

    hw_alarms = alarm_df[
        alarm_df["alarm_name"].isin(HARDWARE_ALARMS) &
        alarm_df["severity"].isin(FAULT_SEVERITIES)
    ].copy()

    pm_devices = set(pm_df["Device Name"].unique())
    def _norm(s):
        return str(s).upper().strip().replace("_", "-")
    pm_norm_map = {_norm(d): d for d in pm_devices}
    alarm_remap = {
        adev: pm_norm_map.get(_norm(adev))
        for adev in set(hw_alarms["device"].unique()) - pm_devices
        if pm_norm_map.get(_norm(adev))
    }
    if alarm_remap:
        hw_alarms["device"] = hw_alarms["device"].replace(alarm_remap)

    window_rows = []
    for (device, obj), port_df in pm_df.groupby(["Device Name", "OBJECT"], sort=False):
        pg = _assign_port_group(obj)
        if pg not in feature_mask:
            continue
        group_metrics = feature_mask.get(pg, [])
        all_cols      = [c for c in pm_df.columns if c not in {"DATE", "Device Name", "OBJECT", "IP Address"}]
        feat_cols_pg  = [c for c in all_cols
                         if any(c.startswith(m + "_") or c == m for m in group_metrics)
                         and c in pm_df.columns]
        if not feat_cols_pg:
            continue

        port_df = port_df.sort_values("DATE").reset_index(drop=True)
        port_times = port_df["DATE"].values
        n = len(port_df)
        dev_hw = hw_alarms[hw_alarms["device"] == device].copy()

        for i in range(WINDOW_N - 1, n):
            t_split = pd.Timestamp(port_times[i])
            start   = max(0, i - WINDOW_N + 1)
            window  = port_df.iloc[start: i + 1]
            if len(window) < 4:
                continue

            label = 0
            alarm_name_val = ""
            is_hw_excl = False

            for _, alarm_row in dev_hw.iterrows():
                t_alarm = alarm_row["raised_time"]
                if (t_alarm - pd.Timedelta(hours=6)) <= t_split <= t_alarm:
                    label = 2
                    alarm_name_val = alarm_row["alarm_name"]
                    break
                if t_alarm < t_split <= (t_alarm + pd.Timedelta(hours=6)):
                    is_hw_excl = True

            row_data = {
                "split_date": t_split, "device": device, "object": obj,
                "port_group": pg, "label": label, "alarm_name": alarm_name_val,
                "hw_excl": is_hw_excl, "is_synthetic": False,
                "window_end": t_split, "window_len": len(window), "alarm_time": pd.NaT,
            }

            for m in group_metrics:
                if m not in port_df.columns:
                    continue
                col_vals = window[m].values.astype(float)
                valid    = col_vals[~np.isnan(col_vals)]
                if len(valid) == 0:
                    continue
                mean_v  = float(np.mean(valid))
                std_v   = float(np.std(valid)) if len(valid) > 1 else 0.0
                min_v   = float(np.min(valid))
                max_v   = float(np.max(valid))
                trend_v = float(np.polyfit(np.arange(len(valid), dtype=float), valid, 1)[0]) if len(valid) >= 3 else 0.0
                roc_v   = float(valid[-1] - valid[0]) if len(valid) >= 2 else 0.0
                max_drop_v   = float(np.max(valid) - np.min(valid)) if len(valid) >= 2 else 0.0
                frac_below_v = float(np.mean(valid < mean_v))
                cv_v         = (std_v / abs(mean_v)) if abs(mean_v) > 1e-9 else 0.0
                z_last_v     = ((valid[-1] - mean_v) / std_v) if std_v > 1e-9 else 0.0
                mid          = max(1, len(valid) // 2)
                delta_half_v = float(np.mean(valid[mid:]) - np.mean(valid[:mid])) if len(valid) >= 4 else 0.0
                row_data[f"{m}_mean"]       = mean_v
                row_data[f"{m}_std"]        = std_v
                row_data[f"{m}_min"]        = min_v
                row_data[f"{m}_max"]        = max_v
                row_data[f"{m}_trend"]      = trend_v
                row_data[f"{m}_roc"]        = roc_v
                row_data[f"{m}_max_drop"]   = max_drop_v
                row_data[f"{m}_frac_below"] = frac_below_v
                row_data[f"{m}_cv"]         = cv_v
                row_data[f"{m}_z_last"]     = z_last_v
                row_data[f"{m}_delta_half"] = delta_half_v
            window_rows.append(row_data)

    if not window_rows:
        raise ValueError(
            "No windows could be built from the provided PM and alarm data. "
            "Check that PM and alarm device names match and time ranges overlap."
        )
    windows_df = pd.DataFrame(window_rows)
    windows_df["split_date"] = pd.to_datetime(windows_df["split_date"])
    return windows_df


def _compute_group_test_metrics(te_df, y_test_hw, all_probs_test, all_thresholds) -> dict:
    if y_test_hw.sum() == 0 or not all_probs_test:
        return {}
    best_key = next((k for k in ["stack_hw", "xgb_hw", "lgb_hw", "rf_hw"]
                     if k in all_probs_test), None)
    if best_key is None:
        return {}
    prob   = all_probs_test[best_key]
    thresh = all_thresholds.get(best_key, 0.5)
    pred   = (prob >= thresh).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test_hw, pred, labels=[0, 1]).ravel()
    prec = tp / max(tp + fp, 1)
    rec  = tp / max(tp + fn, 1)
    f1   = 2 * prec * rec / max(prec + rec, 1e-9)
    f2   = _fbeta_score(prec, rec, 2.0)
    return {
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "precision_pct": round(prec * 100, 1),
        "recall_pct":    round(rec  * 100, 1),
        "f1_pct":        round(f1   * 100, 1),
        "f2_pct":        round(f2   * 100, 1),
        "best_model":    best_key,
        "threshold":     round(thresh, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class HardwareFailureDetectionPlugin(MLPluginBase):
    """
    Hardware failure detection — port-group-based ensemble (v1).

    Groups: A_dwdm_full (DWDM line ports), C_other.
    Threshold optimisation: F2 (recall priority).
    Evidence: 1.5h sustained signal. Port agreement: >=25%.

    Functionally identical to the "original" variant in hardware_failure_detection.py.
    Exists as a named variant so it remains permanently referenceable after v2 is
    introduced and set as active.
    """

    plugin_id          = "hardware_failure_detection"
    plugin_name        = "Hardware Failure Detection"
    plugin_description = (
        "Predicts impending hardware faults in telecom network equipment "
        "(DWDM / transport) using Performance Monitoring (PM) metrics. "
        "Port-group-based stacked ensemble with recall-focused F2 thresholds."
    )
    plugin_category = "anomaly_detection"
    plugin_icon     = "cpu"
    required_files  = [
        {
            "key":         "alarm_data",
            "label":       "Alarm History (XLSX)",
            "description": (
                "Excel file (.xlsx) containing alarm history. "
                "Required columns: NE Label, Alarm Name, Severity, Network Raised Time."
            ),
            "accept":      ".xlsx",
            "upload_mode": "separate",
        },
        {
            "key":         "pm_data",
            "label":       "PM Data (XLSB)",
            "description": (
                "Binary Excel file (.xlsb) containing Performance Monitoring data. "
                "Required columns: DATE, Device Name, OBJECT, and PM metric columns."
            ),
            "accept":      ".xlsb",
            "upload_mode": "separate",
        },
        {
            "key":         "merged_dataset",
            "label":       "Merged Dataset (CSV)",
            "description": (
                "Pre-merged CSV file containing PM data + fault labels "
                "(output of merge_and_label_v2.py). "
                "Required columns: DATE, Device Name, OBJECT, fault_label, plus PM metric columns."
            ),
            "accept":      ".csv",
            "upload_mode": "merged",
        },
        {
            "key":         "windows_pkl",
            "label":       "Processed Windows (PKL)",
            "description": (
                "Pre-processed windowed dataset (output of prepare_dataset_v2.py + label_hw_v3.py). "
                "Upload this to skip data preparation and train immediately."
            ),
            "accept":      ".pkl",
            "upload_mode": "preprocessed",
        },
        {
            "key":         "alarm_data_pkl",
            "label":       "Alarm History for PKL Eval (XLSX)",
            "description": (
                "Alarm history Excel file (.xlsx) used to reconstruct ground-truth alarm events "
                "for evaluation when uploading a PKL. "
                "Without this, event-level metrics (detection rate, lead time) cannot be computed "
                "accurately. Required columns: NE Label, Alarm Name, Severity, Network Raised Time."
            ),
            "accept":      ".xlsx",
            "upload_mode": "preprocessed",
            "required":    False,
        },
    ]

    def get_schema(self) -> dict:
        return {
            "alarm_data": {"required": _ALARM_REQUIRED_COLS, "optional": _ALARM_OPTIONAL_COLS},
            "pm_data":    {"required": _PM_REQUIRED_COLS,    "optional": _PM_OPTIONAL_COLS},
        }

    def validate_data(self, file_key: str, df: pd.DataFrame) -> dict:
        errors   = []
        warnings = []
        
        if file_key == "alarm_data":
            alarm_aliases = {
                "NE Label":            {"ne label", "ne_label", "NE Label"},
                "Alarm Name":          {"alarm name", "alarm_name", "Alarm Name"},
                "Severity":            {"severity"},
                "Network Raised Time": {"network raised time", "network_raised_time", "raised_time", "raised time"},
            }
            actual_lower = {c.lower().replace("_", " "): c for c in df.columns}
            for canonical, aliases in alarm_aliases.items():
                if not any(a.lower().replace("_", " ") in actual_lower for a in aliases):
                    errors.append(f"Missing required column: '{canonical}' (or equivalent)")
            hw_present = df.get("Alarm Name", df.get("alarm_name", pd.Series(dtype=str))).astype(str)
            if hw_present.isin(HARDWARE_ALARMS).sum() == 0:
                warnings.append(f"No hardware alarm events found. Expected: {sorted(HARDWARE_ALARMS)}")

        elif file_key == "pm_data":
            for col in ["DATE", "Device Name", "OBJECT"]:
                if col not in df.columns:
                    errors.append(f"Missing required column: '{col}'")
            if len(df) < 100:
                warnings.append(f"Only {len(df)} PM rows found.")

        elif file_key == "merged_dataset":
            for col in ["DATE", "Device Name", "OBJECT", "fault_label"]:
                if col not in df.columns:
                    errors.append(f"Missing required column: '{col}'")
            if len(df) < 100:
                warnings.append(f"Only {len(df)} rows found in merged dataset.")

        elif file_key == "windows_pkl":
            required_cols = {"split_date", "device", "object", "port_group", "label"}
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                errors.append(f"Missing required columns in PKL: {missing}")
            if len(df) < 100:
                warnings.append(f"Only {len(df)} rows found in windows dataset.")
            label_col = df.get("label")
            if label_col is not None:
                n_hw = (label_col == 2).sum()
                if n_hw == 0:
                    warnings.append("No label=2 (hardware fault) rows found.")

        elif file_key == "alarm_data_pkl":
            # Same validation as alarm_data — this is the alarm XLSX companion for PKL mode
            alarm_aliases = {
                "NE Label":            {"ne label", "ne_label", "NE Label"},
                "Alarm Name":          {"alarm name", "alarm_name", "Alarm Name"},
                "Severity":            {"severity"},
                "Network Raised Time": {"network raised time", "network_raised_time", "raised_time", "raised time"},
            }
            actual_lower = {c.lower().replace("_", " "): c for c in df.columns}
            for canonical, aliases in alarm_aliases.items():
                if not any(a.lower().replace("_", " ") in actual_lower for a in aliases):
                    errors.append(f"Missing required column: '{canonical}' (or equivalent)")
            hw_col = df.get("Alarm Name", df.get("alarm_name", pd.Series(dtype=str)))
            if hw_col.astype(str).isin(HARDWARE_ALARMS).sum() == 0:
                warnings.append(f"No hardware alarm events found in alarm file. Expected: {sorted(HARDWARE_ALARMS)}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def read_upload(self, file_key: str, content: bytes, filename: str = "") -> pd.DataFrame:
        import io
        buf = io.BytesIO(content)
        if file_key == "alarm_data":
            return pd.read_excel(buf, engine="openpyxl")
        elif file_key == "alarm_data_pkl":
            # Alarm XLSX companion for preprocessed (PKL) upload mode
            return pd.read_excel(buf, engine="openpyxl")
        elif file_key == "pm_data":
            return _merge_pm_sheets(content)
        elif file_key == "merged_dataset":
            return pd.read_csv(buf, low_memory=False)
        elif file_key == "windows_pkl":
            return pd.read_pickle(buf)
        else:
            return pd.read_csv(buf)

    # ──────────────────────────────────────────────────────────────────────────
    # Training  (mirrors train_hw_v4.py — port-group-based, F2-recall)
    # ──────────────────────────────────────────────────────────────────────────

    def train(self, data: dict, model_dir: Path,
              base_model_dir: Path | None = None) -> dict:
        upload_mode = data.pop("__upload_mode__", "separate")

        if upload_mode == "preprocessed":
            # User uploaded pre-processed windows (PKL file)
            windows_df = data["windows_pkl"].copy()
            # Alarm XLSX companion — used for accurate event-level evaluation.
            # Optional: if absent we fall back to PKL-based alarm reconstruction.
            alarm_df_for_eval = data.get("alarm_data_pkl", None)
            feature_mask = None  # Will derive from windows
        elif upload_mode == "merged":
            # User uploaded merged dataset CSV
            alarm_df_for_eval = None
            pm_df = data["merged_dataset"].copy()
            pm_df["DATE"] = pd.to_datetime(pm_df["DATE"], errors="coerce")
            pm_df["Device Name"] = pm_df["Device Name"].astype(str).str.strip()
            pm_df["OBJECT"] = pm_df["OBJECT"].astype(str).str.strip()
            pm_df = pm_df.dropna(subset=["DATE"]).sort_values(["Device Name", "OBJECT", "DATE"]).reset_index(drop=True)
            
            # Build alarm stub from fault_label=1 rows
            fault_rows = pm_df[pm_df["fault_label"] == 1].copy()
            alarm_df_stub = pd.DataFrame({
                "device": fault_rows["Device Name"].values,
                "raised_time": fault_rows["DATE"].values,
                "alarm_name": fault_rows.get("alarm_name", pd.Series("unknown", index=fault_rows.index)).values,
                "severity": fault_rows.get("alarm_severity", pd.Series("Major", index=fault_rows.index)).values,
            })
            
            feature_mask = _build_feature_mask_from_pm(pm_df)
            if not feature_mask:
                raise ValueError("Could not derive feature mask from merged PM data.")
            windows_df = _build_windows_from_labeled_pm(pm_df, alarm_df_stub, feature_mask)
        else:
            # Separate files mode
            alarm_df_for_eval = None
            alarm_df = data["alarm_data"]
            pm_df = data["pm_data"]
            feature_mask = _build_feature_mask_from_pm(pm_df)
            if not feature_mask:
                raise ValueError("Could not derive feature mask from PM data.")
            windows_df = _build_windows_from_raw(pm_df, alarm_df, feature_mask)

        # Derive feature mask from windows if not set
        if feature_mask is None:
            feature_mask = _build_feature_mask_from_windows(windows_df)
            if not feature_mask:
                raise ValueError("Could not derive feature mask from preprocessed windows.")

        windows_df["split_date"]   = pd.to_datetime(windows_df["split_date"])
        windows_df["is_synthetic"] = windows_df["is_synthetic"].fillna(False)

        if (windows_df["label"] == 2).sum() == 0:
            raise ValueError(
                "No hardware fault windows could be labelled from the provided data."
            )

        train_mask = (windows_df["split_date"] <= TRAIN_END) & ~windows_df["is_synthetic"]
        val_mask   = (
            (windows_df["split_date"] >= VAL_START) &
            (windows_df["split_date"] <= VAL_END)   &
            ~windows_df["is_synthetic"]
        )
        test_mask  = (
            (windows_df["split_date"] >= TEST_START) &
            (windows_df["split_date"] <= TEST_END)   &
            ~windows_df["is_synthetic"]
        )

        df_train = windows_df[train_mask].copy().reset_index(drop=True)
        df_val   = windows_df[val_mask].copy().reset_index(drop=True)
        df_test  = windows_df[test_mask].copy().reset_index(drop=True)

        if len(df_val) == 0 and len(df_test) == 0:
            from sklearn.model_selection import train_test_split as tts
            idx = windows_df.index.tolist()
            tr_idx, val_idx = tts(idx, test_size=0.2, random_state=RANDOM_SEED)
            df_train = windows_df.loc[tr_idx].copy().reset_index(drop=True)
            df_val   = windows_df.loc[val_idx].copy().reset_index(drop=True)
            df_test  = df_val.copy()

        model_dir.mkdir(parents=True, exist_ok=True)
        with open(model_dir / "feature_mask.json", "w") as f:
            json.dump(feature_mask, f, indent=2)

        # Save variant marker so inference knows which arch to use
        with open(model_dir / "variant.json", "w") as f:
            json.dump({"variant": "v1_port_group_ensemble", "arch": "port_group"}, f)

        summary_rows  = []
        all_metrics   = {}
        total_trained = 0

        for pg in ["A_dwdm_full", "C_other"]:
            group_metrics = feature_mask.get(pg, [])
            if not group_metrics:
                continue

            meta_cols    = {"label", "is_synthetic", "window_end", "split_date",
                            "device", "object", "port_group", "alarm_time",
                            "window_len", "alarm_name", "hw_excl"}
            all_non_meta = [c for c in windows_df.columns if c not in meta_cols]
            feat_cols    = [c for c in all_non_meta
                            if any(c.startswith(m + "_") or c == m for m in group_metrics)
                            and c in windows_df.columns]
            if not feat_cols:
                continue

            tr = df_train[df_train["port_group"] == pg].copy().reset_index(drop=True)
            va = df_val[df_val["port_group"]     == pg].copy().reset_index(drop=True)
            te = df_test[df_test["port_group"]   == pg].copy().reset_index(drop=True)

            n_hw_tr = int((tr["label"] == 2).sum())
            n_hw_va = int((va["label"] == 2).sum())
            n_hw_te = int((te["label"] == 2).sum())

            if n_hw_tr < HW_MIN_POS:
                summary_rows.append({
                    "group": pg, "status": "SKIPPED_INSUFFICIENT_HW_POS",
                    "hw_train_pos": n_hw_tr,
                })
                continue

            va_hw = va[va["label"] == 2].copy()
            tr_hw = tr[tr["label"] == 2].copy()
            val_alarm_types  = set(va_hw["alarm_name"].unique()) if len(va_hw) > 0 else set()
            test_alarm_types = set(te[te["label"] == 2]["alarm_name"].unique()) if len(te) > 0 else set()
            train_alarm_types = set(tr_hw["alarm_name"].unique())

            coverage_extra = []
            for missing_type in (val_alarm_types | test_alarm_types) - train_alarm_types:
                extra = va_hw[va_hw["alarm_name"] == missing_type].copy()
                if len(extra) > 0:
                    coverage_extra.append(extra)
            if coverage_extra:
                tr_hw = pd.concat([tr_hw] + coverage_extra, ignore_index=True)

            X_tr_base, imputer, scaler = _prepare_features(tr, feat_cols, fit=True)
            X_va_base, _, _            = _prepare_features(va, feat_cols, imputer=imputer, scaler=scaler)
            X_te_base, _, _            = _prepare_features(te, feat_cols, imputer=imputer, scaler=scaler)

            joblib.dump(imputer, model_dir / f"{pg}_imputer_hw.pkl")
            joblib.dump(scaler,  model_dir / f"{pg}_scaler_hw.pkl")
            with open(model_dir / f"{pg}_feature_cols_hw.json", "w") as f:
                json.dump(feat_cols, f, indent=2)
            with open(model_dir / f"{pg}_alarm_dummy_names.json", "w") as f:
                json.dump([], f)

            synth_hw  = _per_type_hw_upsample(tr_hw, feat_cols, HW_TYPE_MIN_POS,
                                               HW_SYNTH_ALPHA, HW_SYNTH_SEED)
            tr_hw_aug = pd.concat([tr_hw, synth_hw], ignore_index=True) if not synth_hw.empty else tr_hw.copy()

            tr_neg        = tr[tr["label"] != 2].copy()
            tr_neg_clean  = _exclude_hw_zone_negatives(tr_neg)
            n_neg_target  = int(HW_NEG_RATIO * len(tr_hw_aug))
            tr_neg_ds     = _downsample_negatives_stratified(tr_neg_clean, n_neg_target, RANDOM_SEED)

            tr_combined = pd.concat([tr_hw_aug, tr_neg_ds], ignore_index=True)
            X_tr_comb, _, _ = _prepare_features(tr_combined, feat_cols, imputer=imputer, scaler=scaler)
            y_train_hw = (tr_combined["label"] == 2).astype(int).values
            y_val_hw   = (va["label"] == 2).astype(int).values
            y_test_hw  = (te["label"] == 2).astype(int).values

            spw = (y_train_hw == 0).sum() / max(y_train_hw.sum(), 1)

            all_thresholds = {}
            all_probs_val  = {}
            all_probs_test = {}

            # RF
            rf = RandomForestClassifier(
                n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                min_samples_leaf=RF_MIN_SAMPLES_L, class_weight="balanced",
                n_jobs=-1, random_state=RANDOM_SEED,
            )
            rf.fit(X_tr_comb, y_train_hw)
            rf_prob_val  = rf.predict_proba(X_va_base)[:, 1] if len(X_va_base) > 0 else np.array([])
            rf_prob_test = rf.predict_proba(X_te_base)[:, 1] if len(X_te_base) > 0 else np.array([])
            if len(rf_prob_val) > 0 and y_val_hw.sum() > 0:
                t_rf, _, _, _, _ = _find_best_threshold(y_val_hw, rf_prob_val, F_BETA,
                                                         HW_PREC_FLOOR_HIGH, HW_PREC_FLOOR_LOW, HW_MIN_RECALL_FLOOR)
                all_thresholds["rf_hw"] = t_rf
                all_probs_val["rf_hw"]  = rf_prob_val
                all_probs_test["rf_hw"] = rf_prob_test
            else:
                all_thresholds["rf_hw"] = 0.5
                if len(rf_prob_test) > 0:
                    all_probs_test["rf_hw"] = rf_prob_test
            joblib.dump(rf, model_dir / f"{pg}_rf_hw.pkl")

            # LGB
            if HAS_LGB:
                lgb_model = lgb.LGBMClassifier(**LGB_PARAMS, scale_pos_weight=min(spw, 10.0), device_type=get_lightgbm_device())
                lgb_model.fit(X_tr_comb, y_train_hw)
                lgb_prob_val  = lgb_model.predict_proba(X_va_base)[:, 1] if len(X_va_base) > 0 else np.array([])
                lgb_prob_test = lgb_model.predict_proba(X_te_base)[:, 1] if len(X_te_base) > 0 else np.array([])
                if len(lgb_prob_val) > 0 and y_val_hw.sum() > 0:
                    t_lgb, _, _, _, _ = _find_best_threshold(y_val_hw, lgb_prob_val, F_BETA,
                                                              HW_PREC_FLOOR_HIGH, HW_PREC_FLOOR_LOW, HW_MIN_RECALL_FLOOR)
                    all_thresholds["lgb_hw"] = t_lgb
                    all_probs_val["lgb_hw"]  = lgb_prob_val
                    all_probs_test["lgb_hw"] = lgb_prob_test
                else:
                    all_thresholds["lgb_hw"] = 0.5
                    if len(lgb_prob_test) > 0:
                        all_probs_test["lgb_hw"] = lgb_prob_test
                joblib.dump(lgb_model, model_dir / f"{pg}_lgb_hw.pkl")

            # XGB
            if HAS_XGB:
                xgb_model = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=min(spw, 10.0), tree_method=get_xgboost_tree_method())
                xgb_model.fit(X_tr_comb, y_train_hw)
                xgb_prob_val  = xgb_model.predict_proba(X_va_base)[:, 1] if len(X_va_base) > 0 else np.array([])
                xgb_prob_test = xgb_model.predict_proba(X_te_base)[:, 1] if len(X_te_base) > 0 else np.array([])
                if len(xgb_prob_val) > 0 and y_val_hw.sum() > 0:
                    t_xgb, _, _, _, _ = _find_best_threshold(y_val_hw, xgb_prob_val, F_BETA,
                                                              HW_PREC_FLOOR_HIGH, HW_PREC_FLOOR_LOW, HW_MIN_RECALL_FLOOR)
                    all_thresholds["xgb_hw"] = t_xgb
                    all_probs_val["xgb_hw"]  = xgb_prob_val
                    all_probs_test["xgb_hw"] = xgb_prob_test
                else:
                    all_thresholds["xgb_hw"] = 0.5
                    if len(xgb_prob_test) > 0:
                        all_probs_test["xgb_hw"] = xgb_prob_test
                joblib.dump(xgb_model, model_dir / f"{pg}_xgb_hw.pkl")

            # Stacking
            trained_models = [m for m in ["rf_hw", "lgb_hw", "xgb_hw"] if m in all_probs_val]
            
            # Only stack if we have 2+ models available in BOTH val AND test
            can_stack = (
                len(trained_models) >= 2 and 
                y_val_hw.sum() >= 2 and
                all(m in all_probs_test for m in trained_models)
            )
            
            if can_stack:
                stack_val_input = np.column_stack([all_probs_val[m] for m in trained_models])
                stack_test_input = np.column_stack([all_probs_test[m] for m in trained_models])
                meta = LogisticRegression(C=1.0, max_iter=1000,
                                          random_state=RANDOM_SEED, class_weight="balanced")
                meta.fit(stack_val_input, y_val_hw)
                stack_prob_val  = meta.predict_proba(stack_val_input)[:, 1]
                stack_prob_test = meta.predict_proba(stack_test_input)[:, 1]
                t_st, _, _, _, _ = _find_best_threshold(y_val_hw, stack_prob_val, F_BETA,
                                                        HW_PREC_FLOOR_HIGH, HW_PREC_FLOOR_LOW, HW_MIN_RECALL_FLOOR)
                all_thresholds["stack_hw"] = t_st
                all_probs_test["stack_hw"] = stack_prob_test
                joblib.dump(meta, model_dir / f"{pg}_stack_hw.pkl")
            else:
                # Cannot stack - only 1 model available or insufficient positive samples
                trained_models = []

            # Save metadata with prefixes
            with open(model_dir / f"{pg}_thresholds_hw.json", "w") as f:
                json.dump(all_thresholds, f, indent=2)
            with open(model_dir / f"{pg}_base_model_order.json", "w") as f:
                json.dump(trained_models, f, indent=2)

            group_test_metrics = _compute_group_test_metrics(te, y_test_hw, all_probs_test, all_thresholds)
            all_metrics[pg] = group_test_metrics

            summary_rows.append({
                "group": pg, "status": "TRAINED",
                "n_metric_feat":  len(feat_cols),
                "hw_train_real":  len(tr_hw),
                "hw_train_synth": len(synth_hw),
                "hw_train_total": len(tr_hw_aug),
                "neg_train":      len(tr_neg_ds),
                "hw_val_pos":     n_hw_va,
                "hw_test_pos":    n_hw_te,
            })
            total_trained += 1

        if total_trained == 0:
            raise ValueError("No port groups could be trained.")

        agg_detection_rate = 0.0
        agg_precision      = 0.0
        best_group = next(iter(all_metrics), None)
        if best_group and all_metrics[best_group]:
            m = all_metrics[best_group]
            agg_detection_rate = m.get("recall_pct", 0.0)
            agg_precision      = m.get("precision_pct", 0.0)

        n_hw_windows   = int((windows_df["label"] == 2).sum())
        hw_alarm_types = sorted(windows_df[windows_df["label"] == 2]["alarm_name"].unique().tolist())

        # Run detection evaluation on test data to compute event-level metrics
        try:
            event_metrics = self._run_detection_evaluation(
                df_test, feature_mask, model_dir, windows_df,
                alarm_df_raw=alarm_df_for_eval,
            )
        except Exception as e:
            print(f"[WARN] Detection evaluation failed: {e}")
            event_metrics = {
                "detection_rate_pm_pct": 0,
                "alert_precision_pct": 0,
                "n_alarm_events": 0,
                "n_detected_events": 0,
                "n_detectable_events": 0,
                "n_device_alerts": 0,
                "n_true_positives": 0,
                "n_false_positives": 0,
                "median_lead_time_min": None,
                "pct_ge_60min_lead": 0,
            }

        return {
            "n_samples":         len(windows_df),
            "n_hw_windows":      n_hw_windows,
            "n_features":        sum(len(feature_mask.get(pg, [])) * len(FEAT_SUFFIXES)
                                     for pg in ["A_dwdm_full", "C_other"]),
            "groups_trained":    [r["group"] for r in summary_rows if r.get("status") == "TRAINED"],
            "hw_alarm_types":    hw_alarm_types,
            # Event-level metrics (from detection evaluation)
            "event_detection_rate": event_metrics.get("detection_rate_pm_pct", 0),
            "event_precision":      event_metrics.get("alert_precision_pct", 0),
            "n_alarm_events":       event_metrics.get("n_alarm_events", 0),
            "n_detected_events":    event_metrics.get("n_detected_events", 0),
            "n_detectable_events":  event_metrics.get("n_detectable_events", 0),
            "n_device_alerts":      event_metrics.get("n_device_alerts", 0),
            "n_true_positives":     event_metrics.get("n_true_positives", 0),
            "n_false_positives":   event_metrics.get("n_false_positives", 0),
            "median_lead_time_min": event_metrics.get("median_lead_time_min"),
            "pct_ge_60min_lead":    event_metrics.get("pct_ge_60min_lead", 0),
            # Window-level metrics
            "detection_rate":    agg_detection_rate,
            "precision":         agg_precision,
            "per_group_metrics": all_metrics,
            "training_mode":     "hw_stacked_ensemble_v1_port_group",
        }

    def _run_detection_evaluation(self, df_test: pd.DataFrame, feature_mask: dict,
                                  model_dir: Path,
                                  windows_df: pd.DataFrame | None = None,
                                  alarm_df_raw: pd.DataFrame | None = None) -> dict:
        """
        Run event-level detection evaluation on test data.

        This mirrors evaluate_hw_v5.py exactly. Three critical correctness rules:

        1. ALARM EVENT RECONSTRUCTION:
           When alarm_df_raw is provided (the raw alarm XLSX uploaded alongside the PKL),
           alarm events are built directly from it — exactly as evaluate_hw_v5.py does.
           This is the only way to get the correct 42 PM-detectable test events.

           Fallback (no alarm_df_raw): filter full windows_df on alarm_time in
           [TEST_START, TEST_END], label==2, deduplicate by (device, alarm_name, alarm_time).
           This is less accurate but avoids a hard failure.

        2. FEATURE REUSE:
           The PKL windows already contain all 11 pre-computed feature columns.
           We use those directly (from df_test, which has split_date >= TEST_START)
           instead of recomputing only 4 of them.

        3. ALERT MATCHING WINDOW:
           An alert counts as a true positive only if it fires within
           [t_alarm - MAX_LOOKAHEAD_H, t_alarm - MIN_LEAD_TIME_MIN],
           matching evaluate_hw_v5.py exactly.
        """
        from collections import defaultdict

        # ── Load models and preprocessors ────────────────────────────────────
        loaded_models_hw     = {}
        loaded_thresholds_hw = {}
        loaded_preprocessors = {}

        for pg in ["A_dwdm_full", "C_other"]:
            thresh_path   = model_dir / f"{pg}_thresholds_hw.json"
            feat_col_path = model_dir / f"{pg}_feature_cols_hw.json"
            imputer_path  = model_dir / f"{pg}_imputer_hw.pkl"
            scaler_path   = model_dir / f"{pg}_scaler_hw.pkl"
            bmo_path      = model_dir / f"{pg}_base_model_order.json"

            if not all(p.exists() for p in [thresh_path, feat_col_path, imputer_path, scaler_path]):
                continue

            with open(thresh_path) as f:
                thresholds_all = json.load(f)
            with open(feat_col_path) as f:
                metric_feat_cols = json.load(f)

            imputer = joblib.load(imputer_path)
            scaler  = joblib.load(scaler_path)

            n_imp = getattr(imputer, "n_features_in_", len(metric_feat_cols))
            if n_imp != len(metric_feat_cols):
                metric_feat_cols = metric_feat_cols[:n_imp]

            models_hw  = {}
            thresholds = {}
            base_model_order = []

            for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
                mpath = model_dir / f"{pg}_{mname}.pkl"
                if mpath.exists():
                    models_hw[mname]  = joblib.load(mpath)
                    thresholds[mname] = thresholds_all.get(mname, 0.5)
                    base_model_order.append(mname)

            stack_path = model_dir / f"{pg}_stack_hw.pkl"
            if stack_path.exists():
                models_hw["stack_hw"]  = joblib.load(stack_path)
                thresholds["stack_hw"] = thresholds_all.get("stack_hw", 0.5)

            loaded_models_hw[pg]     = models_hw
            loaded_thresholds_hw[pg] = thresholds
            loaded_preprocessors[pg] = {
                "imputer":          imputer,
                "scaler":           scaler,
                "metric_feat_cols": metric_feat_cols,
                "base_model_order": base_model_order,
            }

        if not loaded_models_hw:
            return {}

        # ── FIX 1: Reconstruct alarm events ──────────────────────────────────
        #
        # PATH A (preferred): raw alarm XLSX was uploaded alongside the PKL.
        #   Normalise column names, filter to HARDWARE_ALARMS + FAULT_SEVERITIES
        #   in [TEST_START, TEST_END], build hw_alarm_events_by_device.
        #   This is identical to what evaluate_hw_v5.py does and produces the
        #   correct 42 PM-detectable events for the March-2026 test month.
        #
        # PATH B (fallback): no alarm XLSX available — reconstruct from PKL.
        #   Filter full windows_df (label==2) on alarm_time in [TEST_START, TEST_END],
        #   deduplicate by (device, alarm_name, alarm_time).  Less accurate but
        #   avoids a hard failure when the alarm file is absent.

        # Prepare evaluation dataframe from df_test (PKL test-split windows)
        df_eval = df_test.copy()
        df_eval["DATE"] = pd.to_datetime(df_eval["split_date"])
        df_eval = df_eval.sort_values(["device", "object", "DATE"]).reset_index(drop=True)
        pm_devices = set(df_eval["device"].unique())

        hw_alarm_events_by_device: dict = defaultdict(list)

        if alarm_df_raw is not None:
            # ── PATH A: use the raw alarm XLSX ────────────────────────────────
            alarm_df = alarm_df_raw.copy()
            alarm_df.columns = [str(c).strip() for c in alarm_df.columns]

            col_map = {}
            for c in alarm_df.columns:
                cl = c.lower().replace(" ", "_")
                if cl not in col_map.values():
                    if "alarm_name" in cl or "alarm name" in c.lower():
                        col_map[c] = "alarm_name"
                    elif "ne_label" in cl or "ne label" in c.lower():
                        col_map[c] = "device"
                    elif ("network_raised" in cl or "raised" in cl) and "raised_time" not in col_map.values():
                        col_map[c] = "raised_time"
                    elif "severity" in cl and "severity" not in col_map.values():
                        col_map[c] = "severity"
            alarm_df = alarm_df.rename(columns=col_map)

            alarm_df["raised_time"] = pd.to_datetime(alarm_df["raised_time"], errors="coerce")
            alarm_df = alarm_df.dropna(subset=["raised_time"])
            alarm_df["device"]     = alarm_df["device"].astype(str).str.strip()
            alarm_df["alarm_name"] = alarm_df["alarm_name"].astype(str).str.strip()
            alarm_df["severity"]   = alarm_df["severity"].astype(str).str.strip()

            # Normalise device names against PM device list (same as evaluate_hw_v5.py)
            def _norm(s):
                return str(s).upper().strip().replace("_", "-")
            pm_norm_map = {_norm(d): d for d in pm_devices}
            alarm_remap = {}
            for adev in set(alarm_df["device"].unique()) - pm_devices:
                candidate = pm_norm_map.get(_norm(adev))
                if candidate:
                    alarm_remap[adev] = candidate
            if alarm_remap:
                alarm_df["device"] = alarm_df["device"].replace(alarm_remap)

            # Filter to hardware alarms in the test window — identical to evaluate_hw_v5.py
            hw_alarms_test = alarm_df[
                alarm_df["alarm_name"].isin(HARDWARE_ALARMS) &
                alarm_df["severity"].isin(FAULT_SEVERITIES) &
                (alarm_df["raised_time"] >= TEST_START) &
                (alarm_df["raised_time"] <= TEST_END)
            ].copy()

            for _, row in hw_alarms_test.iterrows():
                hw_alarm_events_by_device[row["device"]].append({
                    "raised_time": row["raised_time"],
                    "alarm_name":  row["alarm_name"],
                    "severity":    row["severity"],
                })

        else:
            # ── PATH B: reconstruct from PKL alarm_time column ────────────────
            source_df = windows_df if windows_df is not None else df_test
            hw_label2 = source_df[source_df["label"] == 2].copy()

            has_alarm_time_col = (
                "alarm_time" in hw_label2.columns and
                hw_label2["alarm_time"].notna().any()
            )

            seen_events: set = set()

            if has_alarm_time_col:
                hw_label2["alarm_time"] = pd.to_datetime(hw_label2["alarm_time"], errors="coerce")
                in_test = (
                    (hw_label2["alarm_time"] >= TEST_START) &
                    (hw_label2["alarm_time"] <= TEST_END)
                )
                hw_label2 = hw_label2[in_test]
                for _, row in hw_label2.iterrows():
                    t_alarm = row["alarm_time"]
                    if pd.isna(t_alarm):
                        continue
                    aname = str(row.get("alarm_name", "unknown"))
                    sev   = str(row.get("severity", "Major"))
                    key   = (row["device"], aname, t_alarm)
                    if key not in seen_events:
                        seen_events.add(key)
                        hw_alarm_events_by_device[row["device"]].append({
                            "raised_time": pd.Timestamp(t_alarm),
                            "alarm_name":  aname,
                            "severity":    sev,
                        })
            else:
                # alarm_time column absent — use split_date max per group as proxy
                hw_test = hw_label2[
                    (hw_label2["split_date"] >= TEST_START) &
                    (hw_label2["split_date"] <= TEST_END)
                ]
                for (device, aname), grp in hw_test.groupby(["device", "alarm_name"]):
                    t_alarm = grp["split_date"].max()
                    key = (device, str(aname), t_alarm)
                    if key not in seen_events:
                        seen_events.add(key)
                        hw_alarm_events_by_device[device].append({
                            "raised_time": pd.Timestamp(t_alarm),
                            "alarm_name":  str(aname),
                            "severity":    "Major",
                        })

        # ── FIX 2 + 3: Use pre-computed features from PKL directly ───────────
        #
        # The PKL window rows already have all 11 FEAT_SUFFIXES computed per
        # metric (e.g. OPRMIN_mean, OPRMIN_trend, OPRMIN_z_last …). We simply
        # align those columns to metric_feat_cols and pass them through the
        # saved imputer+scaler — identical to what evaluate_hw_v5.py does via
        # compute_window_features_vec().
        #
        # Previously the code re-computed features from scratch and only
        # produced 4 of the 11 suffixes, leaving trend/roc/max_drop/frac_below/
        # cv/z_last/delta_half as NaN. The imputer would fill those NaNs with
        # training medians, but the resulting feature vectors were completely
        # wrong, causing models to output near-zero probabilities and no alerts.
        port_scores: dict = {}

        for (device, obj), port_df in df_eval.groupby(["device", "object"], sort=False):
            pg = _assign_port_group(obj)
            if pg not in loaded_models_hw:
                continue

            preprocessors    = loaded_preprocessors[pg]
            metric_feat_cols = preprocessors["metric_feat_cols"]

            port_df = port_df.sort_values("DATE").reset_index(drop=True)
            if len(port_df) == 0:
                continue

            # Build feature matrix by selecting pre-computed columns from PKL.
            # Columns present in the PKL but not in metric_feat_cols are ignored;
            # columns expected by the model but missing from the PKL are filled
            # with NaN (the imputer handles them with training-set medians).
            X_df = pd.DataFrame(index=port_df.index)
            for col in metric_feat_cols:
                X_df[col] = port_df[col].values if col in port_df.columns else np.nan

            try:
                X_imp    = preprocessors["imputer"].transform(X_df.values.astype(float))
                X_scaled = preprocessors["scaler"].transform(X_imp)
            except Exception:
                continue

            n_rows    = len(port_df)
            all_times = port_df["DATE"].tolist()

            models_hw        = loaded_models_hw[pg]
            base_model_order = preprocessors["base_model_order"]
            thresholds       = loaded_thresholds_hw[pg]

            probs: dict = {}
            for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
                if mname not in models_hw:
                    continue
                try:
                    probs[mname] = models_hw[mname].predict_proba(X_scaled)[:, 1]
                except Exception:
                    probs[mname] = np.zeros(n_rows)

            if "stack_hw" in models_hw:
                avail = [m for m in base_model_order if m in probs]
                if len(avail) >= 2:
                    try:
                        stack_in = np.column_stack([probs[m] for m in avail])
                        probs["stack_hw"] = models_hw["stack_hw"].predict_proba(stack_in)[:, 1]
                    except Exception:
                        probs["stack_hw"] = np.zeros(n_rows)

            port_scores[(device, obj)] = {
                "times":      all_times,
                "probs":      probs,
                "thresholds": thresholds,
            }

        # ── Device-level aggregation (mirrors evaluate_hw_v5.py exactly) ─────
        _EV_N    = EVIDENCE_N       # 6 readings = 1.5 h
        _EV_FRAC = EVIDENCE_FRAC    # 0.50
        _PA_FRAC = PORT_AGREEMENT_FRAC  # 0.25
        _PA_MIN  = PORT_AGREEMENT_MIN   # 2
        _CD_H    = COOLDOWN_H           # 6 h

        device_last_alert: dict = {}
        all_hw_alerts: list     = []

        # Group port scores by device
        device_obj_map: dict = defaultdict(dict)
        for (device, obj), sc in port_scores.items():
            device_obj_map[device][obj] = sc

        for device in sorted(device_obj_map):
            obj_scores = device_obj_map[device]

            all_times = sorted(set(
                pd.Timestamp(t)
                for sc in obj_scores.values()
                for t in sc["times"]
                if pd.Timestamp(t) >= TEST_START
            ))

            for t_now in all_times:
                last_t = device_last_alert.get(device)
                if last_t is not None and (t_now - last_t).total_seconds() / 3600 < _CD_H:
                    continue

                n_active      = 0
                n_voting      = 0
                best_prob_sum = 0.0

                for obj, sc in obj_scores.items():
                    times_arr  = np.array([pd.Timestamp(t) for t in sc["times"]])
                    probs      = sc["probs"]
                    thresholds = sc["thresholds"]

                    idx_arr = np.where(times_arr == t_now)[0]
                    if len(idx_arr) == 0:
                        continue
                    idx_now = idx_arr[0]
                    if idx_now < _EV_N - 1:
                        continue

                    n_active += 1
                    ev_slice  = slice(max(0, idx_now - _EV_N + 1), idx_now + 1)

                    t_rf  = thresholds.get("rf_hw",  0.5)
                    t_xgb = thresholds.get("xgb_hw", 0.5)

                    rf_probs  = probs.get("rf_hw",  np.zeros(len(sc["times"])))[ev_slice]
                    xgb_probs = probs.get("xgb_hw", np.zeros(len(sc["times"])))[ev_slice]
                    rf_frac   = float(np.mean(rf_probs  >= t_rf))
                    xgb_frac  = float(np.mean(xgb_probs >= t_xgb))

                    # LGB excluded from vote (USE_LGB_IN_VOTE = False),
                    # matching the standalone evaluate_hw_v5.py behaviour.
                    vote_frac = float(np.mean([rf_frac, xgb_frac]))

                    t_stack     = thresholds.get("stack_hw", 0.5)
                    stack_probs = probs.get("stack_hw", np.zeros(len(sc["times"])))[ev_slice]
                    stack_frac  = float(np.mean(stack_probs >= t_stack))

                    port_votes = (vote_frac >= _EV_FRAC) or (stack_frac >= _EV_FRAC)

                    if port_votes:
                        n_voting      += 1
                        best_prob_sum += max(
                            float(probs.get("rf_hw",    np.zeros(len(sc["times"])))[idx_now]),
                            float(probs.get("xgb_hw",   np.zeros(len(sc["times"])))[idx_now]),
                            float(probs.get("stack_hw", np.zeros(len(sc["times"])))[idx_now]),
                        )

                if n_active == 0:
                    continue

                frac_voting = n_voting / n_active
                if frac_voting >= _PA_FRAC and n_voting >= _PA_MIN:
                    device_last_alert[device] = t_now
                    all_hw_alerts.append({
                        "device":        device,
                        "alert_time":    t_now,
                        "n_voting":      n_voting,
                        "n_active":      n_active,
                        "frac_voting":   round(frac_voting, 3),
                        "avg_best_prob": round(best_prob_sum / max(n_voting, 1), 4),
                    })

        alerts_df = pd.DataFrame(all_hw_alerts) if all_hw_alerts else pd.DataFrame(
            columns=["device", "alert_time", "n_voting", "n_active", "frac_voting", "avg_best_prob"]
        )
        if not alerts_df.empty:
            alerts_df["alert_time"] = pd.to_datetime(alerts_df["alert_time"])

        # ── Match alerts to alarm events ──────────────────────────────────────
        # An alert counts only if it fires in [t_alarm - MAX_LOOKAHEAD_H,
        # t_alarm - MIN_LEAD_TIME_MIN], mirroring evaluate_hw_v5.py.
        used_alert_idx: set = set()
        event_results: list = []

        for device, hw_list in hw_alarm_events_by_device.items():
            dev_alerts = (
                alerts_df[alerts_df["device"] == device].copy()
                if not alerts_df.empty else pd.DataFrame()
            )

            for ev in hw_list:
                t_alarm    = ev["raised_time"]
                alarm_name = ev["alarm_name"]
                severity   = ev["severity"]
                has_pm     = device in pm_devices

                t_det_start = t_alarm - pd.Timedelta(hours=MAX_LOOKAHEAD_H)
                t_det_end   = t_alarm - pd.Timedelta(minutes=MIN_LEAD_TIME_MIN)

                valid_alerts = pd.DataFrame()
                if not dev_alerts.empty:
                    valid_alerts = dev_alerts[
                        (dev_alerts["alert_time"] >= t_det_start) &
                        (dev_alerts["alert_time"] <= t_det_end)
                    ]

                if len(valid_alerts) > 0:
                    alert_idx   = valid_alerts["alert_time"].idxmin()
                    first_alert = valid_alerts.loc[alert_idx]
                    used_alert_idx.add(alert_idx)
                    lead_min = (t_alarm - first_alert["alert_time"]).total_seconds() / 60
                    event_results.append({
                        "device":          device,
                        "alarm_name":      alarm_name,
                        "severity":        severity,
                        "alarm_time":      t_alarm,
                        "detected":        True,
                        "has_pm_data":     has_pm,
                        "lead_time_min":   lead_min,
                        "n_voting_ports":  int(first_alert.get("n_voting", 0)),
                    })
                else:
                    event_results.append({
                        "device":          device,
                        "alarm_name":      alarm_name,
                        "severity":        severity,
                        "alarm_time":      t_alarm,
                        "detected":        False,
                        "has_pm_data":     has_pm,
                        "lead_time_min":   None,
                        "n_voting_ports":  0,
                    })

        if not alerts_df.empty:
            alerts_df["is_true_positive"] = alerts_df.index.isin(used_alert_idx)

        events_df = pd.DataFrame(event_results) if event_results else pd.DataFrame()

        # ── Compute final metrics ─────────────────────────────────────────────
        n_events      = len(events_df)
        n_with_pm     = int(events_df["has_pm_data"].sum())     if n_events > 0 else 0
        n_detected    = int(events_df["detected"].sum())         if n_events > 0 else 0
        n_detected_pm = (
            int(events_df[events_df["has_pm_data"]]["detected"].sum())
            if n_with_pm > 0 else 0
        )
        det_rate    = n_detected    / max(n_events,  1)
        det_rate_pm = n_detected_pm / max(n_with_pm, 1)

        n_alerts = len(alerts_df)
        n_tp = int(alerts_df["is_true_positive"].sum()) if not alerts_df.empty and "is_true_positive" in alerts_df.columns else 0
        n_fp = n_alerts - n_tp
        prec = n_tp / max(n_alerts, 1)

        lead_times = (
            events_df.loc[events_df["detected"], "lead_time_min"].dropna()
            if n_detected > 0 else pd.Series(dtype=float)
        )
        n_ge_60   = int((lead_times >= 60).sum())
        pct_ge_60 = 100.0 * n_ge_60 / max(len(lead_times), 1)

        return {
            "n_alarm_events":       n_events,
            "n_detectable_events":  n_with_pm,
            "n_detected_events":    n_detected,
            "n_detected_pm_only":   n_detected_pm,
            "detection_rate_pct":   round(det_rate     * 100, 1),
            "detection_rate_pm_pct":round(det_rate_pm  * 100, 1),
            "n_device_alerts":      n_alerts,
            "n_true_positives":     n_tp,
            "n_false_positives":    n_fp,
            "alert_precision_pct":  round(prec         * 100, 1),
            "median_lead_time_min": round(float(lead_times.median()), 1) if len(lead_times) > 0 else None,
            "pct_ge_60min_lead":    round(pct_ge_60, 1),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # _detect_from_pkl  — PKL (preprocessed) detection path
    #
    # Called by detect() when upload_mode == "preprocessed".
    # windows_df already has all 11 FEAT_SUFFIXES pre-computed, so we reuse
    # them directly (identical to the feature-reuse logic in
    # _run_detection_evaluation).  alarm_df_raw is optional; if absent we
    # fall back to reconstructing alarm events from label==2 rows in the PKL.
    # ──────────────────────────────────────────────────────────────────────────

    def _detect_from_pkl(
        self,
        windows_df: "pd.DataFrame",
        alarm_df_raw: "pd.DataFrame | None",
        loaded_models_hw: dict,
        loaded_thresholds_hw: dict,
        loaded_preprocessors: dict,
    ) -> dict:
        df_eval = windows_df.copy()
        df_eval["DATE"] = pd.to_datetime(df_eval["split_date"], errors="coerce")
        df_eval = df_eval.sort_values(["device", "object", "DATE"]).reset_index(drop=True)
        pm_devices = set(df_eval["device"].unique())

        # Use the latest split_date as the "current" time; test window = last 31 days
        # test_start = df_eval["DATE"].max() - pd.Timedelta(days=31)
        test_start = df_eval["DATE"].min() # Use the full dataset start

        # ── Alarm event reconstruction (mirrors _run_detection_evaluation) ───
        hw_alarm_events_by_device: dict = defaultdict(list)

        if alarm_df_raw is not None:
            # PATH A: raw alarm XLSX provided — identical normalisation to
            # _run_detection_evaluation PATH A and evaluate_hw_v5.py
            alarm_df = alarm_df_raw.copy()
            alarm_df.columns = [str(c).strip() for c in alarm_df.columns]
            col_map = {}
            for c in alarm_df.columns:
                cl = c.lower().replace(" ", "_")
                if cl not in col_map.values():
                    if "alarm_name" in cl or "alarm name" in c.lower():
                        col_map[c] = "alarm_name"
                    elif "ne_label" in cl or "ne label" in c.lower():
                        col_map[c] = "device"
                    elif ("network_raised" in cl or "raised" in cl) and "raised_time" not in col_map.values():
                        col_map[c] = "raised_time"
                    elif "severity" in cl and "severity" not in col_map.values():
                        col_map[c] = "severity"
            alarm_df = alarm_df.rename(columns=col_map)
            alarm_df["raised_time"] = pd.to_datetime(alarm_df["raised_time"], errors="coerce")
            alarm_df = alarm_df.dropna(subset=["raised_time"])
            alarm_df["device"]     = alarm_df["device"].astype(str).str.strip()
            alarm_df["alarm_name"] = alarm_df["alarm_name"].astype(str).str.strip()
            alarm_df["severity"]   = alarm_df["severity"].astype(str).str.strip()

            def _norm(s):
                return str(s).upper().strip().replace("_", "-")
            pm_norm_map = {_norm(d): d for d in pm_devices}
            alarm_remap = {}
            for adev in set(alarm_df["device"].unique()) - pm_devices:
                candidate = pm_norm_map.get(_norm(adev))
                if candidate:
                    alarm_remap[adev] = candidate
            if alarm_remap:
                alarm_df["device"] = alarm_df["device"].replace(alarm_remap)

            hw_alarms_eval = alarm_df[
                alarm_df["alarm_name"].isin(HARDWARE_ALARMS) &
                alarm_df["severity"].isin(FAULT_SEVERITIES) &
                (alarm_df["raised_time"] >= test_start)
            ].copy()
            for _, row in hw_alarms_eval.iterrows():
                hw_alarm_events_by_device[row["device"]].append({
                    "raised_time": row["raised_time"],
                    "alarm_name":  row["alarm_name"],
                    "severity":    row["severity"],
                })

        else:
            # PATH B: reconstruct from label==2 rows in windows_df
            hw_label2 = windows_df[windows_df["label"] == 2].copy()
            has_alarm_time_col = (
                "alarm_time" in hw_label2.columns and
                hw_label2["alarm_time"].notna().any()
            )
            seen_events: set = set()
            if has_alarm_time_col:
                hw_label2["alarm_time"] = pd.to_datetime(hw_label2["alarm_time"], errors="coerce")
                hw_label2 = hw_label2[hw_label2["alarm_time"] >= test_start]
                for _, row in hw_label2.iterrows():
                    t_alarm = row["alarm_time"]
                    if pd.isna(t_alarm):
                        continue
                    aname = str(row.get("alarm_name", "unknown"))
                    sev   = str(row.get("severity", "Major"))
                    key   = (row["device"], aname, t_alarm)
                    if key not in seen_events:
                        seen_events.add(key)
                        hw_alarm_events_by_device[row["device"]].append({
                            "raised_time": pd.Timestamp(t_alarm),
                            "alarm_name":  aname,
                            "severity":    sev,
                        })
            else:
                hw_test = hw_label2[hw_label2["split_date"] >= test_start]
                for (device, aname), grp in hw_test.groupby(["device", "alarm_name"]):
                    t_alarm = grp["split_date"].max()
                    key = (device, str(aname), t_alarm)
                    if key not in seen_events:
                        seen_events.add(key)
                        hw_alarm_events_by_device[device].append({
                            "raised_time": pd.Timestamp(t_alarm),
                            "alarm_name":  str(aname),
                            "severity":    "Major",
                        })

        # ── Score each (device, object) using pre-computed PKL features ───────
        port_scores: dict = defaultdict(dict)
        n_ports_done = 0
        n_ports_skip = 0

        for (device, obj), port_df in df_eval.groupby(["device", "object"], sort=False):
            pg = _assign_port_group(obj)
            if pg not in loaded_models_hw:
                n_ports_skip += 1
                continue

            preprocessors    = loaded_preprocessors[pg]
            metric_feat_cols = preprocessors["metric_feat_cols"]
            base_model_order = preprocessors["base_model_order"]
            models_hw        = loaded_models_hw[pg]
            thresholds       = loaded_thresholds_hw[pg]

            port_df = port_df.sort_values("DATE").reset_index(drop=True)
            if len(port_df) == 0:
                n_ports_skip += 1
                continue

            # Reuse pre-computed feature columns from the PKL directly
            X_df = pd.DataFrame(index=port_df.index)
            for col in metric_feat_cols:
                X_df[col] = port_df[col].values if col in port_df.columns else np.nan

            try:
                X_imp    = preprocessors["imputer"].transform(X_df.values.astype(float))
                X_scaled = preprocessors["scaler"].transform(X_imp)
            except Exception:
                n_ports_skip += 1
                continue

            n_rows    = len(port_df)
            all_times = port_df["DATE"].tolist()

            probs: dict = {}
            for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
                if mname not in models_hw:
                    continue
                try:
                    probs[mname] = models_hw[mname].predict_proba(X_scaled)[:, 1]
                except Exception:
                    probs[mname] = np.zeros(n_rows)

            if "stack_hw" in models_hw:
                avail = [m for m in base_model_order if m in probs]
                if len(avail) >= 2:
                    try:
                        stack_in = np.column_stack([probs[m] for m in avail])
                        probs["stack_hw"] = models_hw["stack_hw"].predict_proba(stack_in)[:, 1]
                    except Exception:
                        probs["stack_hw"] = np.zeros(n_rows)

            port_scores[device][obj] = {
                "times":      all_times,
                "probs":      probs,
                "thresholds": thresholds,
                "pg":         pg,
            }
            n_ports_done += 1

        # ── Device-level alert aggregation (evidence + port agreement) ────────
        all_hw_alerts: list  = []
        device_last_alert: dict = {}

        for device, obj_scores in port_scores.items():
            if not obj_scores:
                continue
            all_times_dev = sorted(set(
                pd.Timestamp(t)
                for sc in obj_scores.values()
                for t in sc["times"]
                if pd.Timestamp(t) >= test_start
            ))
            for t_now in all_times_dev:
                last_t = device_last_alert.get(device)
                if last_t is not None and (t_now - last_t).total_seconds() / 3600 < COOLDOWN_H:
                    continue
                n_active = 0
                n_voting = 0
                best_prob_sum = 0.0
                for obj, sc in obj_scores.items():
                    times_arr  = np.array([pd.Timestamp(t) for t in sc["times"]])
                    probs_sc   = sc["probs"]
                    thresholds = sc["thresholds"]
                    idx_arr = np.where(times_arr == t_now)[0]
                    if len(idx_arr) == 0:
                        continue
                    idx_now = idx_arr[0]
                    if idx_now < WINDOW_N - 1:
                        continue
                    n_active  += 1
                    idx_start  = max(0, idx_now - EVIDENCE_N + 1)
                    ev_slice   = slice(idx_start, idx_now + 1)
                    t_rf   = thresholds.get("rf_hw",    0.5)
                    t_xgb  = thresholds.get("xgb_hw",  0.5)
                    t_stk  = thresholds.get("stack_hw", 0.5)
                    rf_probs  = probs_sc.get("rf_hw",    np.zeros(len(sc["times"])))[ev_slice]
                    xgb_probs = probs_sc.get("xgb_hw",   np.zeros(len(sc["times"])))[ev_slice]
                    stk_probs = probs_sc.get("stack_hw", np.zeros(len(sc["times"])))[ev_slice]
                    rf_frac   = np.mean(rf_probs  >= t_rf)
                    xgb_frac  = np.mean(xgb_probs >= t_xgb)
                    stk_frac  = np.mean(stk_probs >= t_stk)
                    vote_frac  = np.mean([rf_frac, xgb_frac])
                    port_votes = (vote_frac >= EVIDENCE_FRAC) or (stk_frac >= EVIDENCE_FRAC)
                    if port_votes:
                        n_voting += 1
                        best_prob_sum += max(
                            float(probs_sc.get("rf_hw",    np.zeros(len(sc["times"])))[idx_now]),
                            float(probs_sc.get("xgb_hw",   np.zeros(len(sc["times"])))[idx_now]),
                            float(probs_sc.get("stack_hw", np.zeros(len(sc["times"])))[idx_now]),
                        )
                if n_active == 0:
                    continue
                frac_voting = n_voting / n_active
                if frac_voting >= PORT_AGREEMENT_FRAC and n_voting >= PORT_AGREEMENT_MIN:
                    device_last_alert[device] = t_now
                    all_hw_alerts.append({
                        "device":        device,
                        "alert_time":    t_now,
                        "n_voting":      n_voting,
                        "n_active":      n_active,
                        "frac_voting":   round(frac_voting, 3),
                        "avg_best_prob": round(best_prob_sum / max(n_voting, 1), 4),
                    })

        # ── Match alerts → alarm events, compute summary ──────────────────────
        alerts_df = pd.DataFrame(all_hw_alerts) if all_hw_alerts else pd.DataFrame(
            columns=["device", "alert_time", "n_voting", "n_active", "frac_voting", "avg_best_prob"]
        )

        event_results: list  = []
        used_alert_idx: set  = set()

        for device, hw_list in hw_alarm_events_by_device.items():
            dev_alerts = alerts_df[alerts_df["device"] == device].copy() if not alerts_df.empty else pd.DataFrame()
            for ev in hw_list:
                t_alarm    = ev["raised_time"]
                alarm_name = ev["alarm_name"]
                severity   = ev["severity"]
                has_pm     = device in pm_devices
                t_det_start = t_alarm - pd.Timedelta(hours=MAX_LOOKAHEAD_H)
                t_det_end   = t_alarm - pd.Timedelta(minutes=MIN_LEAD_TIME_MIN)
                valid_alerts = pd.DataFrame()
                if not dev_alerts.empty:
                    valid_alerts = dev_alerts[
                        (dev_alerts["alert_time"] >= t_det_start) &
                        (dev_alerts["alert_time"] <= t_det_end)
                    ]
                tier = "T1" if alarm_name in HW_TIER1 else "T2" if alarm_name in HW_TIER2 else "T3"
                if len(valid_alerts) > 0:
                    alert_idx   = valid_alerts["alert_time"].idxmin()
                    first_alert = valid_alerts.loc[alert_idx]
                    used_alert_idx.add(alert_idx)
                    lead_min    = (t_alarm - first_alert["alert_time"]).total_seconds() / 60
                    event_results.append({
                        "device": device, "alarm_name": alarm_name, "severity": severity,
                        "alarm_time": t_alarm, "detected": True, "has_pm_data": has_pm,
                        "first_alert_time": first_alert["alert_time"], "lead_time_min": lead_min,
                        "n_voting_ports": int(first_alert.get("n_voting", 0)), "alarm_tier": tier,
                        "avg_best_prob": float(first_alert.get("avg_best_prob", 0.0)),
                    })
                else:
                    event_results.append({
                        "device": device, "alarm_name": alarm_name, "severity": severity,
                        "alarm_time": t_alarm, "detected": False, "has_pm_data": has_pm,
                        "first_alert_time": pd.NaT, "lead_time_min": None,
                        "n_voting_ports": 0, "alarm_tier": tier,
                        "avg_best_prob": None,
                    })

        if not alerts_df.empty:
            alerts_df["is_true_positive"] = alerts_df.index.isin(used_alert_idx)

        events_df    = pd.DataFrame(event_results) if event_results else pd.DataFrame()
        n_events     = len(events_df)
        n_with_pm    = int(events_df["has_pm_data"].sum()) if n_events > 0 else 0
        n_detected   = int(events_df["detected"].sum())    if n_events > 0 else 0
        n_detected_pm = int(events_df[events_df["has_pm_data"]]["detected"].sum()) if n_with_pm > 0 else 0
        det_rate     = n_detected    / max(n_events,  1)
        det_rate_pm  = n_detected_pm / max(n_with_pm, 1)
        n_alerts     = len(alerts_df)
        n_tp = int(alerts_df["is_true_positive"].sum()) if not alerts_df.empty and "is_true_positive" in alerts_df.columns else 0
        n_fp = n_alerts - n_tp
        prec = n_tp / max(n_alerts, 1)
        lead_times = events_df.loc[events_df["detected"], "lead_time_min"].dropna() if n_detected > 0 else pd.Series(dtype=float)
        n_ge_60    = int((lead_times >= 60).sum())
        pct_ge_60  = 100.0 * n_ge_60 / max(len(lead_times), 1)

        summary = {
            "total_records":        n_events,
            "n_with_pm":            n_with_pm,
            "anomalies_found":      n_detected,
            "anomaly_rate":         round(det_rate_pm * 100, 1),
            "detectable_events":    n_with_pm,
            "detected_pm_only":     n_detected_pm,
            "detection_rate_pm":    round(det_rate_pm * 100, 1),
            "total_alerts":         n_alerts,
            "true_positives":       n_tp,
            "false_positives":      n_fp,
            "alert_precision":      round(prec * 100, 1),
            "median_lead_time_min": round(float(lead_times.median()), 1) if len(lead_times) > 0 else None,
            "mean_lead_time_min":   round(float(lead_times.mean()),   1) if len(lead_times) > 0 else None,
            "max_lead_time_min":    round(float(lead_times.max()),    1) if len(lead_times) > 0 else None,
            "min_lead_time_min":    round(float(lead_times.min()),    1) if len(lead_times) > 0 else None,
            "pct_ge_60min_lead":    round(pct_ge_60, 1),
            "ports_scored":         n_ports_done,
            "ports_skipped":        n_ports_skip,
        }

        tier_label_map = {
            "T1": "Critical fault signal",
            "T2": "Environmental / power warning",
            "T3": "Equipment fault",
        }

        explanations = []
        if n_events > 0:
            # Include both true positives (detected events) and false positives (unmatched alerts)
            detected_events = events_df[events_df["detected"]] if n_detected > 0 else pd.DataFrame()
            for _, row in detected_events.iterrows():
                lead_str   = f"{row['lead_time_min']:.0f} min" if pd.notna(row.get("lead_time_min")) else "N/A"
                tier_label = tier_label_map.get(row.get("alarm_tier", ""), "Hardware fault")
                alarm_time_iso = row.get("alarm_time").isoformat() if pd.notna(row.get("alarm_time")) else None
                avg_prob = row.get("avg_best_prob")

                # Ensure this only returns the window, not the whole 6 months
                timeline = self._build_event_detection_timeline(
                    str(row.get("device", "")), 
                    alarm_time_iso, 
                    port_scores,
                    pre_h=2.0,  # 2 hours before
                    post_h=4.0   # 4 hours after
                )

                explanations.append({
                    "record_id":         str(row.get("device", "")),
                    "device":            str(row.get("device", "")),
                    "alarm_name":        str(row.get("alarm_name", "")),
                    "severity":          str(row.get("severity", "")),
                    "alarm_tier":        str(row.get("alarm_tier", "")),
                    "is_anomaly":        True,
                    "is_false_positive": False,
                    "confidence":        "HIGH" if row.get("alarm_tier") == "T1" else "MEDIUM",
                    "avg_confidence":    round(float(avg_prob), 3) if avg_prob is not None else None,
                    "lead_time_min":     row.get("lead_time_min"),
                    "alarm_time":        alarm_time_iso,
                    "first_alert_time":  row.get("first_alert_time").isoformat() if pd.notna(row.get("first_alert_time")) else None,
                    "reasons": [
                        f"{tier_label}: {row.get('alarm_name', '')} detected on {row.get('device', '')}",
                        f"Predicted {lead_str} before alarm raised",
                        f"Severity: {row.get('severity', 'Unknown')}",
                    ],
                    "n_voting_ports":    int(row.get("n_voting_ports", 0)),
                    "detection_timeline": timeline,
                })

            # Append false negative events (alarm events the model missed)
            missed_events = events_df[~events_df["detected"]] if n_events > 0 else pd.DataFrame()
            for _, row in missed_events.iterrows():
                alarm_time_iso = row.get("alarm_time").isoformat() if pd.notna(row.get("alarm_time")) else None
                tier_label = tier_label_map.get(row.get("alarm_tier", ""), "Hardware fault")
                has_pm = bool(row.get("has_pm_data", False))

                timeline = self._build_event_detection_timeline(
                    str(row.get("device", "")),
                    alarm_time_iso,
                    port_scores,
                    pre_h=2.0,
                    post_h=4.0,
                )

                # ── Diagnose why this alarm event was missed ───────────────
                # All port-voting data we need already exists in alerts_df
                # (every alert that fired on this device, with n_voting /
                # n_active / frac_voting recorded).  We just look up the
                # closest alert to the alarm window — no extra loops needed.
                device     = str(row.get("device", ""))
                t_alarm_ts = pd.Timestamp(alarm_time_iso) if alarm_time_iso else None
                t_det_start = t_alarm_ts - pd.Timedelta(hours=MAX_LOOKAHEAD_H)
                t_det_end   = t_alarm_ts - pd.Timedelta(minutes=MIN_LEAD_TIME_MIN)

                has_timeline_data = any(slot.get("has_data", False) for slot in timeline)
                max_prob = max((slot.get("prob", 0) for slot in timeline), default=0)

                # Find any alert that fired on this device near the alarm
                # (could be outside the window, or consumed by another event)
                best_alert_row = None
                if not alerts_df.empty and t_alarm_ts is not None:
                    dev_alerts_fn = alerts_df[alerts_df["device"] == device]
                    if not dev_alerts_fn.empty:
                        # Look in a ±MAX_LOOKAHEAD_H band around the alarm
                        nearby = dev_alerts_fn[
                            (dev_alerts_fn["alert_time"] >= t_det_start) &
                            (dev_alerts_fn["alert_time"] <= t_alarm_ts)
                        ]
                        if not nearby.empty:
                            # Pick the alert with the highest frac_voting
                            best_alert_row = nearby.loc[nearby["frac_voting"].idxmax()]

                reasons = [
                    f"{tier_label}: {row.get('alarm_name', '')} on {device} — NOT detected",
                    f"Severity: {row.get('severity', 'Unknown')}",
                ]

                if not has_pm or device not in port_scores:
                    reasons.append(
                        "No PM data available for this device — model could not score it"
                        if not has_pm
                        else "Device was not scored (no compatible ports found)"
                    )
                elif not has_timeline_data:
                    reasons.append(
                        "No PM data found in the detection window — "
                        "device may have been scored outside this time range"
                    )
                elif best_alert_row is not None:
                    # An alert DID fire on this device in the band — it was
                    # either just outside the window or already used by another
                    # event.  Report the real n_voting/n_active from that alert.
                    nv = int(best_alert_row.get("n_voting", 0))
                    na = int(best_alert_row.get("n_active", 0))
                    fv = float(best_alert_row.get("frac_voting", 0))
                    at = best_alert_row.get("alert_time")
                    at_str = pd.Timestamp(at).strftime("%b %d, %H:%M") if pd.notna(at) else "?"
                    in_window = (t_det_start <= pd.Timestamp(at) <= t_det_end) if pd.notna(at) else False
                    if in_window:
                        # Alert was in-window but matched to a different alarm event
                        reasons.append(
                            f"Alert fired at {at_str} ({nv}/{na} ports = {fv*100:.0f}%) "
                            f"but was already matched to a different alarm event on this device"
                        )
                    else:
                        # Alert fired too close to the alarm (< MIN_LEAD_TIME_MIN)
                        reasons.append(
                            f"Alert fired at {at_str} ({nv}/{na} ports = {fv*100:.0f}%) "
                            f"but was outside the valid window "
                            f"(requires ≥{MIN_LEAD_TIME_MIN} min lead before alarm)"
                        )
                elif max_prob > 0:
                    # No alert fired at all — probability was present but never
                    # crossed the evidence-accumulation + port-agreement bar
                    reasons.append(
                        f"PM data present (max confidence: {max_prob*100:.1f}%) but no device-level "
                        f"alert fired — signal did not meet evidence accumulation "
                        f"(≥{int(EVIDENCE_FRAC*100)}% of {EVIDENCE_N}-slot window) "
                        f"or port agreement (≥{int(PORT_AGREEMENT_FRAC*100)}%, ≥{PORT_AGREEMENT_MIN} ports) threshold"
                    )
                else:
                    reasons.append(
                        "PM data present but model confidence stayed at or near zero "
                        "throughout the detection window"
                    )

                explanations.append({
                    "record_id":         f"fn_{row.get('device', '')}_{alarm_time_iso}",
                    "device":            str(row.get("device", "")),
                    "alarm_name":        str(row.get("alarm_name", "")),
                    "severity":          str(row.get("severity", "")),
                    "alarm_tier":        str(row.get("alarm_tier", "")),
                    "is_anomaly":        False,
                    "is_false_positive": False,
                    "is_false_negative": True,
                    "has_pm_data":       has_pm,
                    "confidence":        "—",
                    "avg_confidence":    None,
                    "lead_time_min":     None,
                    "alarm_time":        alarm_time_iso,
                    "first_alert_time":  None,
                    "reasons":           reasons,
                    "n_voting_ports":    0,
                    "detection_timeline": timeline,
                })


            if not alerts_df.empty and "is_true_positive" in alerts_df.columns:
                fp_alerts = alerts_df[~alerts_df["is_true_positive"]]
                for _, row in fp_alerts.iterrows():
                    alert_time_iso = row["alert_time"].isoformat() if pd.notna(row.get("alert_time")) else None
                    avg_prob = float(row.get("avg_best_prob", 0.0))
                    explanations.append({
                        "record_id":         f"fp_{row.get('device', '')}_{alert_time_iso}",
                        "device":            str(row.get("device", "")),
                        "alarm_name":        "—",
                        "severity":          "—",
                        "alarm_tier":        "—",
                        "is_anomaly":        True,
                        "is_false_positive": True,
                        "confidence":        "LOW",
                        "avg_confidence":    round(avg_prob, 3),
                        "lead_time_min":     None,
                        "alarm_time":        None,
                        "alert_time":        alert_time_iso,
                        "reasons": [
                            f"Alert fired on {row.get('device', '')} at {alert_time_iso} — no matching alarm event found",
                            f"Voting ports: {int(row.get('n_voting', 0))} of {int(row.get('n_active', 0))} active",
                        ],
                        "n_voting_ports":    int(row.get("n_voting", 0)),
                        "detection_timeline": self._build_event_detection_timeline(
                            str(row.get("device", "")), alert_time_iso, port_scores,
                        ),
                    })

        charts_data = self._build_charts_data(events_df, alerts_df, lead_times, port_scores=port_scores)

        results_df   = alerts_df.copy() if not alerts_df.empty else pd.DataFrame(
            columns=["device", "alert_time", "frac_voting", "avg_best_prob", "is_true_positive"])
        anomalies_df = events_df[events_df["detected"]].copy() if n_events > 0 and n_detected > 0 else pd.DataFrame()

        for df_ in [results_df, anomalies_df, events_df]:
            if df_ is not None and not df_.empty:
                for col in df_.select_dtypes(include=["datetime64", "datetimetz"]).columns:
                    df_[col] = df_[col].astype(str).where(df_[col].notna(), None)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Detection  (mirrors evaluate_hw_v5.py — port-group inference)
    # ──────────────────────────────────────────────────────────────────────────

    def detect(self, data: dict, model_dir: Path) -> dict:
        upload_mode = data.pop("__upload_mode__", "separate")

        # ── Resolve inputs based on upload mode ───────────────────────────────
        if upload_mode == "preprocessed":
            # User uploaded pre-processed windows PKL + optional alarm XLSX
            windows_df = data["windows_pkl"].copy()
            alarm_df_raw = data.get("alarm_data_pkl", None)

            # Build a synthetic pm_df-like structure from windows for feature computation
            # The windows PKL already has all features pre-computed — we use them directly
            # (same path as _run_detection_evaluation with the PKL feature reuse logic)
            pm_df = None

        else:
            # "separate" mode: user uploaded pm_data XLSB + alarm_data XLSX
            # alarm_data is REQUIRED for separate mode
            if "alarm_data" not in data:
                raise ValueError(
                    "alarm_data file is required for detection in 'separate' mode. "
                    "Upload the Alarm History XLSX file."
                )
            if "pm_data" not in data:
                raise ValueError(
                    "pm_data file is required for detection in 'separate' mode. "
                    "Upload the PM Data XLSB file."
                )
            alarm_df_raw = data["alarm_data"]
            pm_df = data["pm_data"]
            windows_df = None

        fm_path = model_dir / "feature_mask.json"
        if not fm_path.exists():
            raise RuntimeError("feature_mask.json not found. Retrain the model first.")
        with open(fm_path) as f:
            feature_mask = json.load(f)

        loaded_models_hw     = {}
        loaded_thresholds_hw = {}
        loaded_preprocessors = {}

        for pg in ["A_dwdm_full", "C_other"]:
            thresh_path   = model_dir / f"{pg}_thresholds_hw.json"
            feat_col_path = model_dir / f"{pg}_feature_cols_hw.json"
            imputer_path  = model_dir / f"{pg}_imputer_hw.pkl"
            scaler_path   = model_dir / f"{pg}_scaler_hw.pkl"
            bmo_path      = model_dir / f"{pg}_base_model_order.json"

            if not thresh_path.exists() or not feat_col_path.exists():
                continue
            if not imputer_path.exists() or not scaler_path.exists():
                continue
            
            with open(thresh_path) as f:
                thresholds_all = json.load(f)
            with open(feat_col_path) as f:
                metric_feat_cols = json.load(f)
            # FIX 1: guard against missing base_model_order.json (absent in
            # older trained models). Fall back to an empty list — the loop
            # below that loads individual model .pkl files will rebuild it.
            base_model_order = []
            if bmo_path.exists():
                with open(bmo_path) as f:
                    base_model_order = json.load(f)
            imputer = joblib.load(imputer_path)
            scaler  = joblib.load(scaler_path)
            n_imp = imputer.n_features_in_
            if n_imp != len(metric_feat_cols):
                metric_feat_cols = metric_feat_cols[:n_imp]
            models_hw  = {}
            thresholds = {}
            for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
                mpath = model_dir / f"{pg}_{mname}.pkl"
                if mpath.exists():
                    models_hw[mname]  = joblib.load(mpath)
                    thresholds[mname] = thresholds_all.get(mname, 0.5)
            stack_path = model_dir / f"{pg}_stack_hw.pkl"
            if stack_path.exists():
                models_hw["stack_hw"]  = joblib.load(stack_path)
                thresholds["stack_hw"] = thresholds_all.get("stack_hw", 0.5)
            # If base_model_order.json was missing, reconstruct from what loaded
            if not base_model_order:
                base_model_order = [m for m in ["rf_hw", "lgb_hw", "xgb_hw"] if m in models_hw]
            loaded_models_hw[pg]     = models_hw
            loaded_thresholds_hw[pg] = thresholds
            loaded_preprocessors[pg] = {
                "imputer":          imputer,
                "scaler":           scaler,
                "metric_feat_cols": metric_feat_cols,
                "base_model_order": base_model_order,
            }

        if not loaded_models_hw:
            raise RuntimeError("No trained models found. Train the model first.")

        # ── FIX 2 + 3: Split execution path by upload mode ───────────────────
        # In "preprocessed" mode pm_df is None — all feature data comes from
        # the uploaded windows PKL.  The original code fell straight through to
        # `pm_df = pm_df.copy()` which crashed with AttributeError.
        # In "separate" mode alarm_df_raw was never assigned to alarm_df, which
        # caused a NameError further down.  Both paths are now explicit.

        if upload_mode == "preprocessed":
            return self._detect_from_pkl(
                windows_df, alarm_df_raw,
                loaded_models_hw, loaded_thresholds_hw, loaded_preprocessors,
            )

        # ── Separate mode: raw pm_data XLSB + alarm_data XLSX ────────────────
        alarm_df = alarm_df_raw.copy()   # FIX 3: was referenced as alarm_df but never assigned
        pm_df = pm_df.copy()
        pm_df["DATE"]        = pd.to_datetime(pm_df["DATE"], errors="coerce")
        pm_df["Device Name"] = pm_df["Device Name"].astype(str).str.strip()
        pm_df["OBJECT"]      = pm_df["OBJECT"].astype(str).str.strip()
        pm_df = pm_df.dropna(subset=["DATE"]).sort_values(["Device Name", "OBJECT", "DATE"]).reset_index(drop=True)

        pm_max_date  = pm_df["DATE"].max()
        test_start   = pm_df["DATE"].min() # Previously: pm_max_date - pd.Timedelta(days=31)
        warmup_start = test_start  - pd.Timedelta(hours=WARMUP_H)
        df_eval      = pm_df[pm_df["DATE"] >= warmup_start].copy()

        alarm_df.columns = [str(c).strip() for c in alarm_df.columns]
        col_map = {}
        for c in alarm_df.columns:
            cl = c.lower().replace(" ", "_")
            if "alarm_name" in cl or "alarm name" in c.lower():
                col_map[c] = "alarm_name"
            elif "ne_label" in cl or "ne label" in c.lower():
                col_map[c] = "device"
            elif ("network_raised" in cl or "raised" in cl) and "raised_time" not in col_map.values():
                col_map[c] = "raised_time"
            elif "severity" in cl and "severity" not in col_map.values():
                col_map[c] = "severity"
        alarm_df = alarm_df.rename(columns=col_map)
        alarm_df["raised_time"] = pd.to_datetime(alarm_df["raised_time"], errors="coerce")
        alarm_df = alarm_df.dropna(subset=["raised_time"])
        alarm_df["device"]     = alarm_df["device"].astype(str).str.strip()
        alarm_df["alarm_name"] = alarm_df["alarm_name"].astype(str).str.strip()
        alarm_df["severity"]   = alarm_df["severity"].astype(str).str.strip()

        pm_devices = set(df_eval["Device Name"].unique())
        def _norm(s):
            return str(s).upper().strip().replace("_", "-")
        pm_norm_map = {_norm(d): d for d in pm_devices}
        alarm_remap = {}
        for adev in set(alarm_df["device"].unique()) - pm_devices:
            candidate = pm_norm_map.get(_norm(adev))
            if candidate:
                alarm_remap[adev] = candidate
        if alarm_remap:
            alarm_df["device"] = alarm_df["device"].replace(alarm_remap)

        hw_alarms_eval = alarm_df[
            alarm_df["alarm_name"].isin(HARDWARE_ALARMS) &
            alarm_df["severity"].isin(FAULT_SEVERITIES) &
            (alarm_df["raised_time"] >= test_start)
        ].copy()

        hw_alarm_events_by_device = defaultdict(list)
        for _, row in hw_alarms_eval.iterrows():
            hw_alarm_events_by_device[row["device"]].append({
                "raised_time": row["raised_time"],
                "alarm_name":  row["alarm_name"],
                "severity":    row["severity"],
            })

        port_scores  = defaultdict(dict)
        n_ports_done = 0
        n_ports_skip = 0

        for (device, obj), port_df_all in df_eval.groupby(["Device Name", "OBJECT"], sort=False):
            pg = _assign_port_group(obj)
            if pg not in loaded_models_hw:
                n_ports_skip += 1
                continue
            models_hw        = loaded_models_hw[pg]
            thresholds       = loaded_thresholds_hw[pg]
            preprocessors    = loaded_preprocessors[pg]
            metric_feat_cols = preprocessors["metric_feat_cols"]
            base_model_order = preprocessors["base_model_order"]
            imputer_pg       = preprocessors["imputer"]
            scaler_pg        = preprocessors["scaler"]
            group_metrics    = feature_mask.get(pg, [])

            port_df_all = port_df_all.sort_values("DATE").reset_index(drop=True)
            port_df_all["DATE"] = pd.to_datetime(port_df_all["DATE"])
            test_mask_port   = port_df_all["DATE"] >= test_start
            warmup_mask_port = (port_df_all["DATE"] >= warmup_start) & ~test_mask_port
            test_df   = port_df_all[test_mask_port].reset_index(drop=True)
            warmup_df = port_df_all[warmup_mask_port]
            if len(test_df) == 0:
                n_ports_skip += 1
                continue

            full_df       = pd.concat([warmup_df, test_df], ignore_index=True).sort_values("DATE").reset_index(drop=True)
            valid_metrics = [m for m in group_metrics if m in full_df.columns]
            X_metric_raw  = _compute_window_features_vec(full_df, valid_metrics, metric_feat_cols, WINDOW_N)
            try:
                X_scaled = scaler_pg.transform(imputer_pg.transform(X_metric_raw))
            except Exception:
                n_ports_skip += 1
                continue

            n_warmup   = len(warmup_df)
            X_test_pg  = X_scaled[n_warmup:]
            test_times = test_df["DATE"].values
            n_rows     = len(X_test_pg)
            if n_rows == 0:
                n_ports_skip += 1
                continue

            probs = {}
            for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
                if mname not in models_hw:
                    continue
                try:
                    probs[mname] = models_hw[mname].predict_proba(X_test_pg)[:, 1]
                except Exception:
                    probs[mname] = np.zeros(n_rows)

            if "stack_hw" in models_hw:
                avail = [m for m in base_model_order if m in probs]
                if len(avail) >= 2:
                    try:
                        stack_in = np.column_stack([probs[m] for m in avail])
                        probs["stack_hw"] = models_hw["stack_hw"].predict_proba(stack_in)[:, 1]
                    except Exception:
                        probs["stack_hw"] = np.zeros(n_rows)

            port_scores[device][obj] = {
                "times":      test_times,
                "probs":      probs,
                "thresholds": thresholds,
                "pg":         pg,
            }
            n_ports_done += 1

        all_hw_alerts     = []
        device_last_alert = {}

        for device, obj_scores in port_scores.items():
            if not obj_scores:
                continue
            all_times = sorted(set(
                pd.Timestamp(t)
                for sc in obj_scores.values()
                for t in sc["times"]
                if pd.Timestamp(t) >= test_start
            ))
            for t_now in all_times:
                last_t = device_last_alert.get(device)
                if last_t is not None and (t_now - last_t).total_seconds() / 3600 < COOLDOWN_H:
                    continue
                n_active = 0
                n_voting = 0
                best_prob_sum = 0.0
                for obj, sc in obj_scores.items():
                    times_arr  = np.array([pd.Timestamp(t) for t in sc["times"]])
                    probs      = sc["probs"]
                    thresholds = sc["thresholds"]
                    idx_arr = np.where(times_arr == t_now)[0]
                    if len(idx_arr) == 0:
                        continue
                    idx_now = idx_arr[0]
                    if idx_now < WINDOW_N - 1:
                        continue
                    n_active  += 1
                    idx_start  = max(0, idx_now - EVIDENCE_N + 1)
                    ev_slice   = slice(idx_start, idx_now + 1)
                    t_rf  = thresholds.get("rf_hw",  0.5)
                    t_xgb = thresholds.get("xgb_hw", 0.5)
                    t_stk = thresholds.get("stack_hw", 0.5)
                    rf_probs  = probs.get("rf_hw",  np.zeros(len(sc["times"])))[ev_slice]
                    xgb_probs = probs.get("xgb_hw", np.zeros(len(sc["times"])))[ev_slice]
                    stk_probs = probs.get("stack_hw", np.zeros(len(sc["times"])))[ev_slice]
                    rf_frac   = np.mean(rf_probs  >= t_rf)
                    xgb_frac  = np.mean(xgb_probs >= t_xgb)
                    stk_frac  = np.mean(stk_probs >= t_stk)
                    vote_frac = np.mean([rf_frac, xgb_frac])
                    port_votes = (vote_frac >= EVIDENCE_FRAC) or (stk_frac >= EVIDENCE_FRAC)
                    if port_votes:
                        n_voting += 1
                        best_prob_sum += max(
                            float(probs.get("rf_hw",    np.zeros(len(sc["times"])))[idx_now]),
                            float(probs.get("xgb_hw",   np.zeros(len(sc["times"])))[idx_now]),
                            float(probs.get("stack_hw", np.zeros(len(sc["times"])))[idx_now]),
                        )
                if n_active == 0:
                    continue
                frac_voting = n_voting / n_active
                if frac_voting >= PORT_AGREEMENT_FRAC and n_voting >= PORT_AGREEMENT_MIN:
                    device_last_alert[device] = t_now
                    all_hw_alerts.append({
                        "device":        device,
                        "alert_time":    t_now,
                        "n_voting":      n_voting,
                        "n_active":      n_active,
                        "frac_voting":   round(frac_voting, 3),
                        "avg_best_prob": round(best_prob_sum / max(n_voting, 1), 4),
                    })

        alerts_df = pd.DataFrame(all_hw_alerts) if all_hw_alerts else pd.DataFrame(
            columns=["device", "alert_time", "n_voting", "n_active", "frac_voting", "avg_best_prob"]
        )

        event_results  = []
        used_alert_idx = set()

        for device, hw_list in hw_alarm_events_by_device.items():
            dev_alerts = alerts_df[alerts_df["device"] == device].copy() if not alerts_df.empty else pd.DataFrame()
            for ev in hw_list:
                t_alarm    = ev["raised_time"]
                alarm_name = ev["alarm_name"]
                severity   = ev["severity"]
                has_pm     = device in pm_devices
                t_det_start = t_alarm - pd.Timedelta(hours=MAX_LOOKAHEAD_H)
                t_det_end   = t_alarm - pd.Timedelta(minutes=MIN_LEAD_TIME_MIN)
                valid_alerts = pd.DataFrame()
                if not dev_alerts.empty:
                    valid_alerts = dev_alerts[
                        (dev_alerts["alert_time"] >= t_det_start) &
                        (dev_alerts["alert_time"] <= t_det_end)
                    ]
                if len(valid_alerts) > 0:
                    first_alert = valid_alerts.sort_values("alert_time").iloc[0]
                    alert_idx   = valid_alerts["alert_time"].idxmin()
                    used_alert_idx.add(alert_idx)
                    lead_min    = (t_alarm - first_alert["alert_time"]).total_seconds() / 60
                    tier = "T1" if alarm_name in HW_TIER1 else "T2" if alarm_name in HW_TIER2 else "T3"
                    event_results.append({
                        "device": device, "alarm_name": alarm_name, "severity": severity,
                        "alarm_time": t_alarm, "detected": True, "has_pm_data": has_pm,
                        "first_alert_time": first_alert["alert_time"], "lead_time_min": lead_min,
                        "n_voting_ports": first_alert.get("n_voting", 0), "alarm_tier": tier,
                        "avg_best_prob": float(first_alert.get("avg_best_prob", 0.0)),
                    })
                else:
                    tier = "T1" if alarm_name in HW_TIER1 else "T2" if alarm_name in HW_TIER2 else "T3"
                    event_results.append({
                        "device": device, "alarm_name": alarm_name, "severity": severity,
                        "alarm_time": t_alarm, "detected": False, "has_pm_data": has_pm,
                        "first_alert_time": pd.NaT, "lead_time_min": None,
                        "n_voting_ports": 0, "alarm_tier": tier,
                        "avg_best_prob": None,
                    })

        if not alerts_df.empty:
            alerts_df["is_true_positive"] = alerts_df.index.isin(used_alert_idx)

        events_df = pd.DataFrame(event_results) if event_results else pd.DataFrame()

        n_events      = len(events_df)
        n_with_pm     = int(events_df["has_pm_data"].sum()) if n_events > 0 else 0
        n_detected    = int(events_df["detected"].sum()) if n_events > 0 else 0
        n_detected_pm = int(events_df[events_df["has_pm_data"]]["detected"].sum()) if n_with_pm > 0 else 0
        det_rate      = n_detected    / max(n_events,  1)
        det_rate_pm   = n_detected_pm / max(n_with_pm, 1)
        n_alerts = len(alerts_df)
        n_tp = int(alerts_df["is_true_positive"].sum()) if not alerts_df.empty and "is_true_positive" in alerts_df.columns else 0
        n_fp = n_alerts - n_tp
        prec = n_tp / max(n_alerts, 1)
        lead_times = events_df.loc[events_df["detected"], "lead_time_min"].dropna() if n_detected > 0 else pd.Series(dtype=float)
        n_ge_60    = int((lead_times >= 60).sum())
        pct_ge_60  = 100.0 * n_ge_60 / max(len(lead_times), 1)

        summary = {
            "total_records":        n_events,
            "n_with_pm":            n_with_pm,
            "anomalies_found":      n_detected,
            "anomaly_rate":         round(det_rate_pm * 100, 1),
            "detectable_events":    n_with_pm,
            "detected_pm_only":     n_detected_pm,
            "detection_rate_pm":    round(det_rate_pm * 100, 1),
            "total_alerts":         n_alerts,
            "true_positives":       n_tp,
            "false_positives":      n_fp,
            "alert_precision":      round(prec * 100, 1),
            "median_lead_time_min": round(float(lead_times.median()), 1) if len(lead_times) > 0 else None,
            "mean_lead_time_min":   round(float(lead_times.mean()),   1) if len(lead_times) > 0 else None,
            "max_lead_time_min":    round(float(lead_times.max()),    1) if len(lead_times) > 0 else None,
            "min_lead_time_min":    round(float(lead_times.min()),    1) if len(lead_times) > 0 else None,
            "pct_ge_60min_lead":    round(pct_ge_60, 1),
            "ports_scored":         n_ports_done,
            "ports_skipped":        n_ports_skip,
        }

        tier_label_map = {
            "T1": "Critical fault signal",
            "T2": "Environmental / power warning",
            "T3": "Equipment fault",
        }

        explanations = []
        if n_events > 0:
            # True positives — detected alarm events
            detected_events = events_df[events_df["detected"]] if "detected" in events_df.columns else pd.DataFrame()
            for _, row in detected_events.iterrows():
                lead_str   = f"{row['lead_time_min']:.0f} min" if pd.notna(row.get("lead_time_min")) else "N/A"
                tier_label = tier_label_map.get(row.get("alarm_tier", ""), "Hardware fault")
                alarm_time_iso = row.get("alarm_time").isoformat() if pd.notna(row.get("alarm_time")) else None
                avg_prob = row.get("avg_best_prob")

                timeline = self._build_event_detection_timeline(
                    str(row.get("device", "")), 
                    alarm_time_iso, 
                    port_scores,
                    pre_h=2.0,  # 2 hours before
                    post_h=4.0   # 4 hours after
                )

                explanations.append({
                    "record_id":         str(row.get("device", "")),
                    "device":            str(row.get("device", "")),
                    "alarm_name":        str(row.get("alarm_name", "")),
                    "severity":          str(row.get("severity", "")),
                    "alarm_tier":        str(row.get("alarm_tier", "")),
                    "is_anomaly":        True,
                    "is_false_positive": False,
                    "confidence":        "HIGH" if row.get("alarm_tier") == "T1" else "MEDIUM",
                    "avg_confidence":    round(float(avg_prob), 3) if avg_prob is not None else None,
                    "lead_time_min":     row.get("lead_time_min"),
                    "alarm_time":        alarm_time_iso,
                    "reasons": [
                        f"{tier_label}: {row.get('alarm_name', '')} detected on {row.get('device', '')}",
                        f"Predicted {lead_str} before alarm raised",
                        f"Severity: {row.get('severity', 'Unknown')}",
                    ],
                    "n_voting_ports":    int(row.get("n_voting_ports", 0)),
                    "detection_timeline": timeline,
                })

            # False positives — alerts that did not match any alarm event
            if not alerts_df.empty and "is_true_positive" in alerts_df.columns:
                fp_alerts = alerts_df[~alerts_df["is_true_positive"]]
                for _, row in fp_alerts.iterrows():
                    alert_time_iso = row["alert_time"].isoformat() if pd.notna(row.get("alert_time")) else None
                    avg_prob = float(row.get("avg_best_prob", 0.0))
                    explanations.append({
                        "record_id":         f"fp_{row.get('device', '')}_{alert_time_iso}",
                        "device":            str(row.get("device", "")),
                        "alarm_name":        "—",
                        "severity":          "—",
                        "alarm_tier":        "—",
                        "is_anomaly":        True,
                        "is_false_positive": True,
                        "confidence":        "LOW",
                        "avg_confidence":    round(avg_prob, 3),
                        "lead_time_min":     None,
                        "alarm_time":        None,
                        "alert_time":        alert_time_iso,
                        "reasons": [
                            f"Alert fired on {row.get('device', '')} at {alert_time_iso} — no matching alarm event found",
                            f"Voting ports: {int(row.get('n_voting', 0))} of {int(row.get('n_active', 0))} active",
                        ],
                        "n_voting_ports":    int(row.get("n_voting", 0)),
                        "detection_timeline": self._build_event_detection_timeline(
                            str(row.get("device", "")), alert_time_iso, port_scores,
                        ),
                    })

        charts_data = self._build_charts_data(events_df, alerts_df, lead_times, port_scores=port_scores)

        results_df   = alerts_df.copy() if not alerts_df.empty else pd.DataFrame(
            columns=["device", "alert_time", "frac_voting", "avg_best_prob", "is_true_positive"])
        anomalies_df = events_df[events_df["detected"]].copy() if n_events > 0 and n_detected > 0 else pd.DataFrame()

        for df_ in [results_df, anomalies_df, events_df]:
            if df_ is not None and not df_.empty:
                for col in df_.select_dtypes(include=["datetime64", "datetimetz"]).columns:
                    df_[col] = df_[col].astype(str).where(df_[col].notna(), None)

        return {
            "results_df":   results_df,
            "anomalies_df": anomalies_df,
            "summary":      summary,
            "explanations": explanations,
            "charts_data":  charts_data,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # _build_device_alerts_timeline
    #
    # Builds the `device_alerts_timeline` array consumed by the frontend's
    # AlertTimeline component (runCharts.jsx).
    #
    # Shape:
    #   [
    #     {
    #       "device": "NE-001",
    #       "slots": [
    #         {"t": "2024-03-01T08:00", "fired": true,  "prob": 0.87, "is_tp": true,  "n_voting": 3},
    #         {"t": "2024-03-01T08:15", "fired": false, "prob": 0.12, "is_tp": false, "n_voting": 0},
    #         ...
    #       ]
    #     },
    #     ...
    #   ]
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_device_alerts_timeline(
        port_scores: dict,
        alerts_df: "pd.DataFrame",
        max_slots_per_device: int = 5000,
    ) -> list:
        """Build per-device slot arrays for the 15-Min Alert Timeline chart.

        For long datasets (> max_slots_per_device 15-min windows) the slots are
        downsampled to hourly resolution by taking the max probability and OR-ing
        the fired/is_tp flags within each 1-hour bucket.  This keeps the JSON
        payload small enough to store in the DB while preserving the visual shape
        of the signal over the full date range.
        """
        timeline = []

        tp_alert_times: dict = defaultdict(set)
        all_alert_times: dict = defaultdict(set)
        if not alerts_df.empty and "alert_time" in alerts_df.columns:
            for _, row in alerts_df.iterrows():
                t = pd.Timestamp(row["alert_time"])
                device = str(row["device"])
                all_alert_times[device].add(t)
                if row.get("is_true_positive"):
                    tp_alert_times[device].add(t)

        for device, obj_scores in port_scores.items():
            if not obj_scores:
                continue

            time_prob_map: dict = {}
            time_voting_map: dict = {}

            for obj, sc in obj_scores.items():
                times_arr  = [pd.Timestamp(t) for t in sc["times"]]
                probs      = sc["probs"]
                thresholds = sc["thresholds"]

                if "stack_hw" in probs:
                    best_probs = probs["stack_hw"]
                else:
                    candidates = [probs[m] for m in ["rf_hw", "xgb_hw", "lgb_hw"] if m in probs]
                    if candidates:
                        best_probs = np.max(np.column_stack(candidates), axis=1) if len(candidates) > 1 else candidates[0]
                    else:
                        best_probs = np.zeros(len(times_arr))

                t_stk = thresholds.get("stack_hw", thresholds.get("xgb_hw", 0.5))

                for i, t in enumerate(times_arr):
                    p = float(best_probs[i])
                    fired_port = p >= t_stk
                    if t not in time_prob_map:
                        time_prob_map[t]   = p
                        time_voting_map[t] = 1 if fired_port else 0
                    else:
                        time_prob_map[t]   = max(time_prob_map[t], p)
                        if fired_port:
                            time_voting_map[t] += 1

            if not time_prob_map:
                continue

            fired_times = all_alert_times.get(device, set())
            tp_times    = tp_alert_times.get(device, set())

            # Build raw 15-min slots
            raw_slots = []
            for t in sorted(time_prob_map.keys()):
                raw_slots.append({
                    "t":        t,
                    "fired":    t in fired_times,
                    "prob":     round(time_prob_map[t], 4),
                    "is_tp":    t in tp_times,
                    "n_voting": time_voting_map.get(t, 0),
                })

            # ── Downsample to hourly if dataset is too large ──────────────────
            if len(raw_slots) > max_slots_per_device:
                hourly: dict = {}  # hour_bucket -> aggregated slot
                for s in raw_slots:
                    # Floor to the hour
                    bucket = s["t"].floor("h")
                    if bucket not in hourly:
                        hourly[bucket] = {
                            "t":        bucket,
                            "fired":    s["fired"],
                            "prob":     s["prob"],
                            "is_tp":    s["is_tp"],
                            "n_voting": s["n_voting"],
                        }
                    else:
                        h = hourly[bucket]
                        h["prob"]     = max(h["prob"],  s["prob"])
                        h["fired"]    = h["fired"]    or s["fired"]
                        h["is_tp"]    = h["is_tp"]    or s["is_tp"]
                        h["n_voting"] = max(h["n_voting"], s["n_voting"])
                raw_slots = list(hourly.values())
            # ──────────────────────────────────────────────────────────────────

            slots = [
                {
                    "t":        s["t"].isoformat(),
                    "fired":    s["fired"],
                    "prob":     s["prob"],
                    "is_tp":    s["is_tp"],
                    "n_voting": s["n_voting"],
                }
                for s in sorted(raw_slots, key=lambda x: x["t"])
            ]

            if slots:
                timeline.append({"device": device, "slots": slots})

        timeline.sort(key=lambda x: x["device"])
        return timeline

    # ──────────────────────────────────────────────────────────────────────────
    # _build_event_detection_timeline
    #
    # For a single detected alarm event, collect 2h before the alarm_time
    # and up to POST_H hours after, at 15-min resolution.
    # Aggregates across all ports of that device (max probability).
    #
    # Shape (per event):
    #   [
    #     {"t": "...", "prob": 0.82, "fired": true},
    #     ...
    #   ]
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_event_detection_timeline(
        device: str,
        alarm_time_iso: "str | None",
        port_scores: dict,
        pre_h: float = 2.0,
        post_h: float = 4.0,
    ) -> list:
        """Return per-slot probability data centred on an alarm event.

        Always emits a full 15-min grid from (alarm_time - pre_h) to
        (alarm_time + post_h).  Slots with no PM data get prob=0 /
        fired=False, so the frontend always shows a complete, uniform
        timeline regardless of how sparse the underlying data is.
        """
        if alarm_time_iso is None:
            return []

        try:
            t_alarm = pd.Timestamp(alarm_time_iso)
        except Exception:
            return []

        STEP    = pd.Timedelta(minutes=15)
        t_start = (t_alarm - pd.Timedelta(hours=pre_h)).floor("15min")
        t_end   = (t_alarm + pd.Timedelta(hours=post_h)).ceil("15min")

        # Build the canonical 15-min grid that covers the full window.
        # Both t_start and t_end are snapped to 15-min boundaries so that
        # grid slot keys will always match the snapped PM timestamps below.
        grid_times: list[pd.Timestamp] = []
        cur = t_start
        while cur <= t_end:
            grid_times.append(cur)
            cur += STEP

        # Maps: grid_timestamp → best probability / threshold seen so far
        time_prob_map:      dict = {}
        time_threshold_map: dict = {}

        if device in port_scores:
            obj_scores = port_scores[device]

            for obj, sc in obj_scores.items():
                times_arr  = [pd.Timestamp(t) for t in sc["times"]]
                probs      = sc["probs"]
                thresholds = sc["thresholds"]

                if "stack_hw" in probs:
                    best_probs = probs["stack_hw"]
                else:
                    candidates = [probs[m] for m in ["rf_hw", "xgb_hw", "lgb_hw"] if m in probs]
                    if candidates:
                        best_probs = (
                            np.max(np.column_stack(candidates), axis=1)
                            if len(candidates) > 1
                            else candidates[0]
                        )
                    else:
                        best_probs = np.zeros(len(times_arr))

                t_thresh = thresholds.get("stack_hw", thresholds.get("xgb_hw", 0.5))

                for i, t in enumerate(times_arr):
                    if not (t_start <= t <= t_end):
                        continue
                    # Snap to nearest 15-min grid slot
                    snapped = t.floor("15min")
                    p = float(best_probs[i])
                    if snapped not in time_prob_map or p > time_prob_map[snapped]:
                        time_prob_map[snapped]      = p
                        time_threshold_map[snapped] = t_thresh

        # Determine a single representative threshold (fallback = 0.5)
        default_thresh = (
            next(iter(time_threshold_map.values()))
            if time_threshold_map
            else 0.5
        )

        # Emit one slot per grid step; gaps get prob=0
        result = []
        for t in grid_times:
            prob   = round(time_prob_map.get(t, 0.0), 4)
            thresh = time_threshold_map.get(t, default_thresh)
            has_data = t in time_prob_map
            result.append({
                "t":        t.isoformat(),
                "prob":     prob,
                "fired":    prob >= thresh,
                "has_data": has_data,
            })
        
        return result

    def _build_charts_data(self, events_df, alerts_df, lead_times, port_scores: dict | None = None) -> dict:
        if events_df.empty:
            detection_pie = [
                {"name": "Detected", "value": 0, "color": "#22c55e"},
                {"name": "Missed",   "value": 0, "color": "#ef4444"},
            ]
        else:
            n_det    = int(events_df["detected"].sum())
            n_missed = len(events_df) - n_det
            detection_pie = [
                {"name": "Detected", "value": n_det,    "color": "#22c55e"},
                {"name": "Missed",   "value": n_missed,  "color": "#ef4444"},
            ]
        n_tp = int(alerts_df["is_true_positive"].sum()) if not alerts_df.empty and "is_true_positive" in alerts_df.columns else 0
        n_fp = len(alerts_df) - n_tp
        alert_breakdown = [
            {"name": "True Positive",  "value": n_tp, "color": "#22c55e"},
            {"name": "False Positive", "value": n_fp, "color": "#f59e0b"},
        ]
        alarm_type_dist = []
        if not events_df.empty and "alarm_name" in events_df.columns:
            for aname, grp in events_df.groupby("alarm_name"):
                n_e   = len(grp)
                n_det = int(grp["detected"].sum()) if "detected" in grp else 0
                tier  = "T1" if aname in HW_TIER1 else "T2" if aname in HW_TIER2 else "T3"
                alarm_type_dist.append({
                    "alarm": aname, "total": n_e, "detected": n_det,
                    "missed": n_e - n_det, "tier": tier,
                })
        lead_time_hist = []
        if len(lead_times) > 0:
            bins = [0, 15, 30, 60, 120, 240, 9999]
            labels_lt = ["0-15m", "15-30m", "30-60m", "1-2h", "2-4h", "4h+"]
            for i in range(len(bins) - 1):
                lo, hi = bins[i], bins[i + 1]
                count = int(((lead_times >= lo) & (lead_times < hi)).sum())
                lead_time_hist.append({"bucket": labels_lt[i], "count": count})
        device_det = []
        if not events_df.empty and "device" in events_df.columns:
            for dev, grp in events_df.groupby("device"):
                n_e   = len(grp)
                n_det = int(grp["detected"].sum()) if "detected" in grp else 0
                has_pm = bool(grp["has_pm_data"].any()) if "has_pm_data" in grp else False
                device_det.append({
                    "device":   str(dev), "total": n_e,
                    "detected": n_det, "missed": n_e - n_det, "has_pm": has_pm,
                })
        prob_dist = []
        if not alerts_df.empty and "avg_best_prob" in alerts_df.columns:
            bins_p = [0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0]
            labels_p = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0"]
            for i in range(len(bins_p) - 1):
                lo, hi = bins_p[i], bins_p[i + 1]
                count = int(((alerts_df["avg_best_prob"] >= lo) & (alerts_df["avg_best_prob"] < hi)).sum())
                prob_dist.append({"range": labels_p[i], "count": count})

        # Build per-device alert timeline (powers the AlertTimeline chart)
        # Temporarily disabled due to large data causing DB issues
        # device_alerts_timeline = []
        # if port_scores:
        #     device_alerts_timeline = self._build_device_alerts_timeline(port_scores, alerts_df)

        return {
            "detection_overview":    detection_pie,
            "alert_breakdown":       alert_breakdown,
            "alarm_type_dist":       alarm_type_dist,
            "lead_time_histogram":   lead_time_hist,
            "device_detection":      device_det,
            "prob_distribution":     prob_dist,
            # "device_alerts_timeline": device_alerts_timeline,
        }

    def get_charts_config(self) -> list[dict]:
        return [
            {"id": "detection_overview",  "title": "Detection Overview",            "type": "pie",       "description": "Detected vs missed hardware fault events"},
            {"id": "alert_breakdown",     "title": "Alert Quality",                 "type": "pie",       "description": "True positives vs false positives in raised alerts"},
            {"id": "alarm_type_dist",     "title": "Events by Alarm Type",          "type": "bar",       "description": "Detection breakdown by hardware alarm category"},
            {"id": "lead_time_histogram", "title": "Lead Time Distribution",        "type": "histogram", "description": "How far ahead of the alarm the system fired alerts"},
            {"id": "device_detection",    "title": "Detection by Device",           "type": "bar",       "description": "Per-device detection count and PM data availability"},
            {"id": "prob_distribution",   "title": "Alert Confidence Distribution", "type": "histogram", "description": "Distribution of model confidence scores on raised alerts"},
        ]

    def supports_event_api(self) -> bool:
        return True

    def get_event_schema(self) -> dict:
        return {
            "fields": [
                {"field": "device",    "type": "string",   "required": True,
                 "description": "Network element / device label (Device Name)"},
                {"field": "object",    "type": "string",   "required": True,
                 "description": "Port object identifier (e.g. AM01-1-11). Determines port group."},
                {"field": "timestamp", "type": "datetime", "required": True,
                 "description": "Reading timestamp for the most recent PM sample in pm_window."},
                {"field": "pm_window", "type": "array",    "required": True,
                 "description": (
                     f"Last {WINDOW_N} PM readings for this device/port at 15-min intervals "
                     f"(2-hour rolling window). Each entry is an object of metric name -> numeric "
                     f"value (e.g. OPRMIN, OPRAVG, QMIN, QAVG, PRFBERMAX, ES, SES). "
                     f"Minimum 4 readings, recommended {WINDOW_N}. Older readings first, current last."
                 )},
                {"field": "alarm_name", "type": "string",  "required": False,
                 "description": "Optional concurrent alarm name for context-aware reasons."},
                {"field": "severity",   "type": "string",  "required": False,
                 "description": "Optional alarm severity (Minor / Major / Critical)."},
            ],
            "example": {
                "device": "NE-AM01",
                "object": "AM01-1-11",
                "timestamp": "2026-05-03T09:30:00Z",
                "pm_window": [
                    {"OPRMIN": -9.2, "OPRAVG": -8.8, "QMIN": 9.5, "QAVG": 10.1, "PRFBERMAX": 1e-5, "ES": 0, "SES": 0},
                    {"OPRMIN": -9.4, "OPRAVG": -8.9, "QMIN": 9.4, "QAVG": 10.0, "PRFBERMAX": 1e-5, "ES": 0, "SES": 0},
                    {"OPRMIN": -9.6, "OPRAVG": -9.1, "QMIN": 9.2, "QAVG": 9.8,  "PRFBERMAX": 2e-5, "ES": 1, "SES": 0},
                    {"OPRMIN": -9.9, "OPRAVG": -9.3, "QMIN": 9.0, "QAVG": 9.6,  "PRFBERMAX": 3e-5, "ES": 1, "SES": 0},
                    {"OPRMIN": -10.2, "OPRAVG": -9.6, "QMIN": 8.7, "QAVG": 9.3, "PRFBERMAX": 5e-5, "ES": 2, "SES": 1},
                    {"OPRMIN": -10.5, "OPRAVG": -9.9, "QMIN": 8.4, "QAVG": 9.0, "PRFBERMAX": 8e-5, "ES": 3, "SES": 1},
                    {"OPRMIN": -10.9, "OPRAVG": -10.3, "QMIN": 8.0, "QAVG": 8.6, "PRFBERMAX": 1.2e-4, "ES": 4, "SES": 2},
                    {"OPRMIN": -11.4, "OPRAVG": -10.8, "QMIN": 7.5, "QAVG": 8.1, "PRFBERMAX": 2e-4,  "ES": 6, "SES": 3},
                ],
                "alarm_name": "LOC_FLT",
                "severity": "Major",
            },
            "context_window": {
                "window_size": WINDOW_N,
                "interval_minutes": 15,
                "min_readings": 4,
                "rationale": (
                    "Model is trained on rolling-window PM features (mean/std/trend/roc/...). "
                    "Single-row scoring requires the prior window of PM samples; a single instant "
                    "reading carries no trend information."
                ),
            },
        }

    def score_event(self, event: dict, model_dir: Path) -> dict:
        device = str(event.get("device", "")).strip()
        obj    = str(event.get("object", "")).strip()
        ts_raw = event.get("timestamp")
        pm_window = event.get("pm_window") or []

        if not device or not obj:
            raise ValueError("score_event requires non-empty 'device' and 'object'.")
        if not isinstance(pm_window, list) or len(pm_window) < 4:
            raise ValueError(
                f"score_event requires 'pm_window' with at least 4 readings "
                f"(recommended {WINDOW_N}). See get_event_schema() for the contract."
            )
        try:
            ts = pd.to_datetime(ts_raw)
        except Exception:
            raise ValueError(f"Unparseable 'timestamp': {ts_raw!r}")

        pg = _assign_port_group(obj)
        feat_col_path = model_dir / f"{pg}_feature_cols_hw.json"
        thresh_path   = model_dir / f"{pg}_thresholds_hw.json"
        imputer_path  = model_dir / f"{pg}_imputer_hw.pkl"
        scaler_path   = model_dir / f"{pg}_scaler_hw.pkl"
        bmo_path      = model_dir / f"{pg}_base_model_order.json"
        if not (feat_col_path.exists() and thresh_path.exists()
                and imputer_path.exists() and scaler_path.exists()):
            raise RuntimeError(
                f"No trained artifacts for port group '{pg}'. "
                f"Train the model first or send events for a supported port group."
            )

        with open(feat_col_path) as f:
            feat_cols = json.load(f)
        with open(thresh_path) as f:
            thresholds_all = json.load(f)
        imputer = joblib.load(imputer_path)
        scaler  = joblib.load(scaler_path)
        n_imp = imputer.n_features_in_
        if n_imp != len(feat_cols):
            feat_cols = feat_cols[:n_imp]
        base_model_order = []
        if bmo_path.exists():
            with open(bmo_path) as f:
                base_model_order = json.load(f)

        models_hw: dict = {}
        for mname in ["rf_hw", "lgb_hw", "xgb_hw"]:
            mpath = model_dir / f"{pg}_{mname}.pkl"
            if mpath.exists():
                models_hw[mname] = joblib.load(mpath)
        stack_path = model_dir / f"{pg}_stack_hw.pkl"
        if stack_path.exists():
            models_hw["stack_hw"] = joblib.load(stack_path)
        if not base_model_order:
            base_model_order = [m for m in ["rf_hw", "lgb_hw", "xgb_hw"] if m in models_hw]
        if not models_hw:
            raise RuntimeError(f"No trained classifiers found for port group '{pg}'.")

        base_metrics = sorted({fc.rsplit("_", 1)[0] for fc in feat_cols
                               if any(fc.endswith(f"_{s}") for s in FEAT_SUFFIXES)})

        row_data: dict = {}
        for m in base_metrics:
            vals = []
            for sample in pm_window:
                v = sample.get(m) if isinstance(sample, dict) else None
                if v is None:
                    continue
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    continue
            feats = _window_features_from_values(np.array(vals, dtype=float))
            for suf, val in feats.items():
                row_data[f"{m}_{suf}"] = val

        feat_vec = np.array([[row_data.get(c, np.nan) for c in feat_cols]], dtype=float)
        X = scaler.transform(imputer.transform(feat_vec))

        probs: dict = {}
        for mname, mdl in models_hw.items():
            if mname == "stack_hw":
                continue
            try:
                probs[mname] = float(mdl.predict_proba(X)[0, 1])
            except Exception:
                probs[mname] = 0.0
        if "stack_hw" in models_hw:
            avail = [m for m in base_model_order if m in probs]
            if len(avail) >= 2:
                try:
                    stack_in = np.array([[probs[m] for m in avail]])
                    probs["stack_hw"] = float(models_hw["stack_hw"].predict_proba(stack_in)[0, 1])
                except Exception:
                    probs["stack_hw"] = 0.0

        thresholds = {m: float(thresholds_all.get(m, 0.5)) for m in probs}
        votes = {m: probs[m] >= thresholds[m] for m in probs}
        any_base = any(votes.get(m, False) for m in ["rf_hw", "xgb_hw"]) or (USE_LGB_IN_VOTE and votes.get("lgb_hw", False))
        stack_vote = votes.get("stack_hw", False)
        is_anomaly = bool(any_base or stack_vote)

        score = max(probs.values()) if probs else 0.0
        best_model = max(probs, key=probs.get) if probs else "rf_hw"
        margin = probs[best_model] - thresholds.get(best_model, 0.5) if probs else 0.0

        if is_anomaly:
            confidence = "HIGH" if margin >= 0.15 else ("MEDIUM" if margin >= 0.0 else "LOW")
        else:
            confidence = "NORMAL"

        reasons: list = []
        alarm_name_in = str(event.get("alarm_name", "")).strip()
        severity_in   = str(event.get("severity",   "")).strip()
        if alarm_name_in in HW_TIER1:
            reasons.append(f"Concurrent T1 hardware alarm '{alarm_name_in}' indicates loss-of-frame / fault-equipment class.")
        elif alarm_name_in in HW_TIER2:
            reasons.append(f"Concurrent T2 environment alarm '{alarm_name_in}' (temperature/power/cooling).")
        elif alarm_name_in in HW_TIER3:
            reasons.append(f"Concurrent T3 equipment alarm '{alarm_name_in}' (missing/failed/latch/deskew).")
        if severity_in in {"Major", "Critical"}:
            reasons.append(f"Alarm severity '{severity_in}' is in the fault-tracked range.")

        if is_anomaly:
            reasons.append(
                f"{best_model.replace('_hw', '').upper()} prob {probs[best_model]:.3f} "
                f">= tuned threshold {thresholds.get(best_model, 0.5):.3f} on port group {pg}."
            )
            ranked_metrics = []
            for m in base_metrics:
                z = abs(row_data.get(f"{m}_z_last", 0.0))
                trend = abs(row_data.get(f"{m}_trend", 0.0))
                ranked_metrics.append((m, z + trend))
            ranked_metrics.sort(key=lambda kv: kv[1], reverse=True)
            for m, _w in ranked_metrics[:2]:
                z = row_data.get(f"{m}_z_last", 0.0)
                tr = row_data.get(f"{m}_trend", 0.0)
                reasons.append(f"{m}: z_last={z:+.2f}, trend={tr:+.4f} over the {len(pm_window)}-sample window.")
        else:
            reasons.append(
                f"All model votes below threshold on port group {pg} "
                f"(top score {score:.3f} from {best_model.replace('_hw','').upper()})."
            )

        return {
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "score": float(score),
            "reasons": reasons[:6],
            "details": {
                "device": device,
                "object": obj,
                "port_group": pg,
                "timestamp": ts.isoformat(),
                "model_probs": {m: round(probs[m], 6) for m in probs},
                "thresholds": {m: round(thresholds[m], 6) for m in probs},
                "votes": votes,
                "window_size": len(pm_window),
                "best_model": best_model,
                "model_family": "RF+XGB+LGB stacked (port-group ensemble)",
            },
        }