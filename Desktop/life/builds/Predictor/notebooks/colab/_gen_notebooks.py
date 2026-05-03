"""Generator script for Predictor Colab notebooks.

Run once after editing to regenerate every plugin notebook with a consistent
shape (mount Drive, sync repo, install deps, load CSVs from Drive, call the
plugin's `train()` directly, persist artifacts back to Drive).

    python notebooks/colab/_gen_notebooks.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_URL = "https://github.com/adx-coder/NUTRIRE.git"
HERE = Path(__file__).resolve().parent


def md(*lines: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": list(lines)}


def code(*lines: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": list(lines),
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
            "accelerator": "GPU",
            "colab": {"provenance": []},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


SETUP_NOTEBOOK = notebook([
    md("# Predictor — Colab Setup\n",
       "\n",
       "Run this notebook **once per Colab VM** to mount Google Drive, clone the\n",
       "Predictor repo, and install backend requirements (incl. GPU extras).\n"),
    md("## 1. Mount Google Drive"),
    code("from google.colab import drive\n",
         "drive.mount('/content/drive')\n"),
    md("## 2. Set up workspace"),
    code("import os, pathlib\n",
         "DRIVE_ROOT = pathlib.Path('/content/drive/MyDrive/Predictor')\n",
         "for sub in ['datasets', 'models', 'logs']:\n",
         "    (DRIVE_ROOT / sub).mkdir(parents=True, exist_ok=True)\n",
         "print('Drive root:', DRIVE_ROOT)\n"),
    md("## 3. Clone or pull the repo"),
    code(f"REPO_URL = '{REPO_URL}'\n",
         "REPO_DIR = pathlib.Path('/content/Predictor')\n",
         "if not REPO_DIR.exists():\n",
         "    !git clone $REPO_URL $REPO_DIR\n",
         "else:\n",
         "    !cd $REPO_DIR && git pull --ff-only\n",
         "print('Repo at:', REPO_DIR)\n"),
    md("## 4. Install backend requirements"),
    code("!pip install -q -r /content/Predictor/predictor/backend/requirements.txt\n",
         "!pip install -q torch --index-url https://download.pytorch.org/whl/cu121\n"),
    md("## 5. Verify GPU"),
    code("import sys\n",
         "sys.path.insert(0, '/content/Predictor/predictor/backend')\n",
         "from app.ml_plugins._gpu_utils import detect_gpu, get_lightgbm_device, get_xgboost_tree_method\n",
         "print('GPU:', detect_gpu())\n",
         "print('LightGBM device:', get_lightgbm_device())\n",
         "print('XGBoost tree_method:', get_xgboost_tree_method())\n"),
])


def _train_notebook(plugin_id: str, *, file_keys: list[str], description: str, placeholder: bool = False) -> dict:
    cells: list[dict] = [
        md(f"# Train `{plugin_id}`\n",
           "\n",
           f"{description}\n",
           "\n",
           "Drive layout (created by `00_setup.ipynb`):\n",
           "```\n",
           f"/content/drive/MyDrive/Predictor/datasets/{plugin_id}/   # CSVs go here\n",
           f"/content/drive/MyDrive/Predictor/models/{plugin_id}/     # trained artifacts\n",
           "```\n"),
    ]
    if placeholder:
        cells.append(md(
            "> **Placeholder.** This plugin is still being built; once `train()` lands\n",
            "> on `app.ml_plugins.registry.get_plugin('"
            + plugin_id + "')` the cells below will work without further edits.\n",
        ))

    cells.extend([
        md("## 1. Mount Drive & sync repo"),
        code("from google.colab import drive\n",
             "drive.mount('/content/drive', force_remount=False)\n",
             "import pathlib, sys\n",
             f"REPO_URL = '{REPO_URL}'\n",
             "REPO_DIR = pathlib.Path('/content/Predictor')\n",
             "if not REPO_DIR.exists():\n",
             "    !git clone $REPO_URL $REPO_DIR\n",
             "else:\n",
             "    !cd $REPO_DIR && git pull --ff-only\n",
             "sys.path.insert(0, str(REPO_DIR / 'predictor' / 'backend'))\n"),
        md("## 2. Install requirements (CPU defaults + CUDA torch)"),
        code("!pip install -q -r /content/Predictor/predictor/backend/requirements.txt\n",
             "!pip install -q torch --index-url https://download.pytorch.org/whl/cu121\n"),
        md("## 3. Configure dataset / model paths"),
        code("import pathlib\n",
             f"PLUGIN_ID = '{plugin_id}'\n",
             "DATA_DIR  = pathlib.Path('/content/drive/MyDrive/Predictor/datasets') / PLUGIN_ID\n",
             "MODEL_DIR = pathlib.Path('/content/drive/MyDrive/Predictor/models')   / PLUGIN_ID\n",
             "MODEL_DIR.mkdir(parents=True, exist_ok=True)\n",
             "print('Data:', DATA_DIR)\n",
             "print('Model:', MODEL_DIR)\n",
             "assert DATA_DIR.exists(), f'Upload CSVs to {DATA_DIR} before training.'\n"),
        md("## 4. Detect GPU (sanity check)"),
        code("from app.ml_plugins._gpu_utils import detect_gpu\n",
             "print(detect_gpu())\n"),
        md("## 5. Load training CSVs"),
    ])
    load_lines: list[str] = ["import pandas as pd\n", "data = {}\n"]
    for key in file_keys:
        load_lines.append(f"data['{key}'] = pd.read_csv(DATA_DIR / '{key}.csv')\n")
        load_lines.append(f"print('{key}:', data['{key}'].shape)\n")
    cells.append(code(*load_lines))

    cells.extend([
        md("## 6. Train the plugin"),
        code("from app.ml_plugins.registry import get_plugin\n",
             "plugin = get_plugin(PLUGIN_ID)\n",
             "assert plugin is not None, f'Plugin {PLUGIN_ID} not registered.'\n",
             "metrics = plugin.train(data, MODEL_DIR)\n"),
        md("## 7. Inspect metrics"),
        code("import json\n",
             "print(json.dumps({k: v for k, v in metrics.items() if k != 'feature_names'}, indent=2, default=str))\n"),
        md("## 8. Verify artifacts on Drive"),
        code("for p in sorted(MODEL_DIR.iterdir()):\n",
             "    print(p.name, p.stat().st_size, 'bytes')\n"),
    ])
    return notebook(cells)


PLUGIN_NOTEBOOKS = {
    "billing_anomaly": _train_notebook(
        "billing_anomaly",
        file_keys=["invoice", "invoice_details", "account"],
        description="Trains the billing anomaly Isolation Forest on telco invoice data.",
    ),
    "telecom_churn": _train_notebook(
        "telecom_churn",
        file_keys=["customers"],
        description="Trains the telecom churn classifier on subscriber CSVs.",
    ),
    "telco_customer_churn": _train_notebook(
        "telco_customer_churn",
        file_keys=["customers"],
        description="Trains the Telco Customer Churn MLP on the 21-column public schema.",
    ),
    "social_sentiment": _train_notebook(
        "social_sentiment",
        file_keys=["posts"],
        description="Trains the TF-IDF + LR social sentiment classifier (CPU-bound; GPU is unused but harmless).",
    ),
    "product_reviews_sentiment": _train_notebook(
        "product_reviews_sentiment",
        file_keys=["reviews"],
        description="Trains the Amazon-style product review sentiment classifier.",
    ),
    "hardware_failure_detection": _train_notebook(
        "hardware_failure_detection",
        file_keys=["telemetry", "alarms", "topology"],
        description=(
            "Trains the port-group ensemble for hardware failure detection. "
            "Uses LightGBM + XGBoost; both pick up the GPU automatically via `_gpu_utils`."
        ),
    ),
    "mobile_money_fraud": _train_notebook(
        "mobile_money_fraud",
        file_keys=["transactions"],
        description="Trains the LightGBM mobile-money fraud detector with leakage-aware features.",
    ),
    "revenue_forecasting": _train_notebook(
        "revenue_forecasting",
        file_keys=["revenue"],
        description="Trains the revenue forecasting plugin (under active development).",
        placeholder=True,
    ),
    "customer_lifetime_value": _train_notebook(
        "customer_lifetime_value",
        file_keys=["transactions"],
        description="Trains the BG/NBD + Gamma-Gamma CLV plugin.",
        placeholder=True,
    ),
}


def main() -> None:
    out_paths: list[Path] = []
    setup_path = HERE / "00_setup.ipynb"
    setup_path.write_text(json.dumps(SETUP_NOTEBOOK, indent=1) + "\n", encoding="utf-8")
    out_paths.append(setup_path)
    for plugin_id, nb in PLUGIN_NOTEBOOKS.items():
        path = HERE / f"train_{plugin_id}.ipynb"
        path.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8")
        out_paths.append(path)
    for p in out_paths:
        print("wrote", p.name)


if __name__ == "__main__":
    main()
