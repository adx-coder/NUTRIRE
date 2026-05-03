"""
ML Plugin Registry.

Central registry for all ML model plugins. To add a new plugin:
1. Create a new plugin class extending MLPluginBase
2. Import and register it below

─────────────────────────────────────────────────────────────────────────────
PLUGIN VARIANT SYSTEM (company-side versioning)
─────────────────────────────────────────────────────────────────────────────

Problem: When we want to swap the ML algorithm for a use case (e.g. switch
billing_anomaly from IsolationForest to XGBoost), editing the existing plugin
file loses the old implementation — even though it's in git history, it's
awkward to navigate and cross-reference.

Solution: Each plugin can have multiple *named variants* living as separate
Python files inside a dedicated subfolder:

    ml_plugins/
        billing_anomaly.py              ← original (still loaded as "original")
        billing_anomaly/                ← variant folder (same name as plugin_id)
            __init__.py
            v1_isolation_forest.py      ← variant name: "v1_isolation_forest"
            v2_xgboost.py               ← variant name: "v2_xgboost"
        hardware_failure_detection.py   ← original variant
        hardware_failure_detection_variants/
            __init__.py
            v1_port_group_ensemble.py   ← port-group based, F2-recall (train_hw_v4 / evaluate_hw_v5)
            v2_alarm_group_ensemble.py  ← alarm-group based, F0.5-precision (train_hw_v5 / evaluate_hw_v6)
        telecom_churn.py
        telecom_churn/
            v1_logistic.py
            v2_random_forest.py
        ...

Rules:
  • The original plugin file (e.g. billing_anomaly.py) is always registered
    as variant "original". This preserves every existing model untouched.
  • Variants inside the subfolder are registered as their filename stem
    (e.g. "v1_isolation_forest", "v2_xgboost").
  • The DB column MLModel.active_plugin_variant tracks which variant is
    currently active per model. Defaults to "original".
  • Each ModelVersion.plugin_variant records which variant trained that
    specific version snapshot — so we can always load the right code for
    historical inference even after the active variant has changed.
  • get_plugin(model_id) returns the "original" variant (backward compat).
  • get_plugin_variant(model_id, variant_name) returns a specific variant.
  • get_active_plugin(model_id, db) queries the DB for the active variant.

Adding a new variant:
  1. Create ml_plugins/billing_anomaly/v2_xgboost.py with a class that
     subclasses MLPluginBase (same interface as always).
  2. The variant is auto-discovered at startup — no registry change needed.
  3. Use the admin API  PATCH /api/versions/{model_id}/plugin-variant
     to set "v2_xgboost" as the active variant for that model.
  4. The old "original" / "v1_isolation_forest" variant remains intact and
     will be used for inference on any ModelVersion that was trained with it.

Hardware Failure Detection variants:
  "original"               → hardware_failure_detection.py (port-group, F2)
  "v1_port_group_ensemble" → explicitly named re-package of the original
  "v2_alarm_group_ensemble"→ alarm-group based (T1/T2/T3), F0.5 precision,
                             M2 trend + M3 cross-device (train_hw_v5 / evaluate_hw_v6)

  The "original" variant is the currently ACTIVE variant. To switch to v2:
      PATCH /api/versions/hardware_failure_detection/plugin-variant
      { "variant_name": "v2_alarm_group_ensemble" }
"""

import importlib
import importlib.util
from pathlib import Path
from typing import Optional

from app.ml_plugins.base import MLPluginBase
from app.ml_plugins.billing_anomaly import BillingAnomalyPlugin
from app.ml_plugins.telecom_churn import TelecomChurnPlugin
from app.ml_plugins.customer_segmentation import CustomerSegmentationPlugin
from app.ml_plugins.social_sentiment import SocialSentimentPlugin
from app.ml_plugins.product_reviews_sentiment import ProductReviewsSentimentPlugin
from app.ml_plugins.telco_customer_churn import TelcoCustomerChurnPlugin
from app.ml_plugins.hardware_failure_detection import HardwareFailureDetectionPlugin
from app.ml_plugins.mobile_money_fraud import MobileMoneyFraudPlugin
from app.ml_plugins.customer_lifetime_value import CustomerLifetimeValuePlugin
from app.ml_plugins.revenue_forecasting import RevenueForecastingPlugin

# ---------------------------------------------------------------------------
# Internal storage
# ---------------------------------------------------------------------------

# Primary registry: model_id → plugin instance (always the "original" variant)
_PLUGINS: dict[str, MLPluginBase] = {}

# Variant registry: (model_id, variant_name) → plugin instance
_VARIANTS: dict[tuple[str, str], MLPluginBase] = {}


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------

def _register(plugin_class):
    """Register a plugin class as the canonical (original) variant."""
    instance = plugin_class()
    _PLUGINS[instance.plugin_id] = instance
    _VARIANTS[(instance.plugin_id, "original")] = instance


def _autodiscover_variants():
    """
    Scan for variant subfolders alongside each plugin file and dynamically
    load every .py file inside as an additional named variant.

    Convention:
        ml_plugins/billing_anomaly/v2_xgboost.py
            → variant key: ("billing_anomaly", "v2_xgboost")
            → the file must contain exactly ONE class that subclasses MLPluginBase

    Also supports the _variants suffix convention:
        ml_plugins/hardware_failure_detection_variants/v1_port_group_ensemble.py
            → variant key: ("hardware_failure_detection", "v1_port_group_ensemble")
    """
    plugins_dir = Path(__file__).resolve().parent

    for model_id in list(_PLUGINS.keys()):
        # Support both <model_id>/ and <model_id>_variants/ subfolder conventions
        candidate_dirs = [
            plugins_dir / f"{model_id}_variants",
            plugins_dir / model_id,
        ]

        for variant_dir in candidate_dirs:
            if not variant_dir.is_dir():
                continue

            for variant_file in sorted(variant_dir.glob("*.py")):
                if variant_file.name.startswith("_"):
                    continue  # skip __init__.py etc.

                variant_name = variant_file.stem  # e.g. "v2_xgboost"
                key = (model_id, variant_name)

                if key in _VARIANTS:
                    continue  # already registered (e.g. on reload)

                try:
                    spec = importlib.util.spec_from_file_location(
                        f"app.ml_plugins.{model_id}.{variant_name}", variant_file
                    )
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Find the MLPluginBase subclass defined in this module
                    plugin_cls = None
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, MLPluginBase)
                            and attr is not MLPluginBase
                            and attr.__module__ == mod.__name__
                        ):
                            plugin_cls = attr
                            break

                    if plugin_cls is None:
                        print(f"[registry] WARNING: No MLPluginBase subclass found in {variant_file}, skipping.")
                        continue

                    instance = plugin_cls()
                    _VARIANTS[key] = instance
                    print(f"[registry] Loaded variant '{variant_name}' for model '{model_id}'")

                except Exception as exc:
                    print(f"[registry] ERROR loading variant {variant_file}: {exc}")


# ---------------------------------------------------------------------------
# Register all built-in plugins (original variants)
# ---------------------------------------------------------------------------

_register(BillingAnomalyPlugin)
_register(TelecomChurnPlugin)
_register(CustomerSegmentationPlugin)
_register(SocialSentimentPlugin)
_register(ProductReviewsSentimentPlugin)
_register(TelcoCustomerChurnPlugin)
_register(HardwareFailureDetectionPlugin)
_register(MobileMoneyFraudPlugin)
_register(CustomerLifetimeValuePlugin)
_register(RevenueForecastingPlugin)

# Future plugins:
# _register(RevenueForecastPlugin)

# Auto-discover any variant subfolders that have been added
_autodiscover_variants()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_plugin(plugin_id: str) -> Optional[MLPluginBase]:
    """Return the canonical (original) plugin instance for a model_id."""
    return _PLUGINS.get(plugin_id)


def get_plugin_variant(plugin_id: str, variant_name: str) -> Optional[MLPluginBase]:
    """
    Return a specific variant of a plugin by name.

    Falls back to the "original" variant if the requested variant is not found,
    so that historical runs continue to work even if a variant file is later
    renamed (with a warning logged).
    """
    key = (plugin_id, variant_name)
    if key in _VARIANTS:
        return _VARIANTS[key]

    # Fallback: warn and return original
    if variant_name != "original":
        print(
            f"[registry] WARNING: Variant '{variant_name}' for model '{plugin_id}' "
            f"not found — falling back to 'original'. "
            f"Ensure ml_plugins/{plugin_id}_variants/{variant_name}.py exists."
        )
    return _PLUGINS.get(plugin_id)


def get_active_plugin(plugin_id: str, db) -> Optional[MLPluginBase]:
    """
    Return the currently active plugin variant for a model, as stored in the DB.

    Used by train/detect routes so they always use the variant the admin has
    configured — not hard-coded to "original".

    Falls back to the "original" variant if the DB row doesn't exist yet.
    """
    from app.database.ml_models import MLModel

    db_model = db.query(MLModel).filter(MLModel.id == plugin_id).first()
    variant_name = (db_model.active_plugin_variant or "original") if db_model else "original"
    return get_plugin_variant(plugin_id, variant_name)


def get_all_plugins() -> dict[str, MLPluginBase]:
    """Return all canonical plugin instances."""
    return _PLUGINS.copy()


def list_plugins() -> list[dict]:
    """Return plugin metadata for the frontend (canonical variants only)."""
    return [
        {
            "id": p.plugin_id,
            "name": p.plugin_name,
            "description": p.plugin_description,
            "category": p.plugin_category,
            "icon": p.plugin_icon,
            "required_files": p.required_files,
            "supports_incremental_training": p.supports_incremental_training(),
            "supports_single_entry": p.supports_single_entry(),
            "supports_event_api": p.supports_event_api(),
            "charts": p.get_charts_config(),
        }
        for p in _PLUGINS.values()
    ]


def list_variants_for_model(plugin_id: str) -> list[dict]:
    """
    Return all registered variant names for a model.
    Used by the admin API to show available choices.
    """
    results = []
    for (mid, vname), instance in _VARIANTS.items():
        if mid == plugin_id:
            results.append({
                "variant_name": vname,
                "plugin_class": type(instance).__name__,
            })
    return sorted(results, key=lambda x: x["variant_name"])
