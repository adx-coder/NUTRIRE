## Predictor — ML Analytics Platform

**Predictor** is the web-based frontend for this project. It provides a central hub for running ML models, visualizing results, and collecting feedback — designed for non-technical users.

### Features

- **Plugin Architecture** — Drop in new ML models without changing the platform code
- **Model Versioning** — Every training run creates a new version; roll back anytime
- **Incremental Training** — Update models with new data without full retraining
- **80/20 Holdout Validation** — Training automatically holds out 20% of data and reports method agreement rate, holdout anomaly rate, and confidence breakdown on the model page
- **Single-Entry Scoring** — Score one record at a time via a UI form (plugin opt-in)
- **Events API** — Real-time JSON API for streaming systems (Kafka, webhooks, etc.)
- **Feedback Loop** — Users confirm or reject flagged anomalies (thumbs up/down)
- **Auto-Retrain Triggers** — Automatic recommendations when model drift or feedback thresholds are detected
- **Interactive Charts** — Pie, bar, scatter, histogram visualizations via Recharts
- **Dark / Light Theme** — Defaults to dark mode; toggle available in sidebar
- **Export** — Download results as CSV, charts as PNG, or full reports as branded PDF
- **Schema Validation** — Validates uploaded CSVs and guides users on the expected format
- **Docker Support** — One-command startup with Docker Compose

### Quick Start (Web App)

#### Option A: Docker (recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

This launches:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs

Model artifacts, the SQLite database, uploads, and exports are persisted in named Docker volumes and survive container restarts.

#### Option B: Local dev

```bash
# Install backend dependencies
pip install -r predictor/backend/requirements.txt

# Install frontend dependencies
cd predictor/frontend && npm install && cd ../..

# Start both servers
./predictor/start.sh
```

This launches:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs

### Using the Web App

1. **Dashboard** — See all available models, run history, and stats
2. **Train** — Upload 3 CSV files → click "Start Training" → model version created
3. **Detect (batch)** — Upload new data → click "Run Detection" → see results with charts
4. **Score Single Entry** — Fill in a form and get an immediate anomaly result (models that support it show this tab automatically)
5. **Feedback** — Thumbs up/down on each flagged anomaly to improve future models
6. **Export** — Download anomalies CSV, full results CSV, chart PNGs, or PDF report

### Adding New ML Models

Predictor is built as a plugin platform. To add a new model (e.g., Customer Churn):

1. Create `predictor/backend/app/ml_plugins/customer_churn.py`
2. Subclass `MLPluginBase` and implement `train()`, `detect()`, `get_schema()`, `get_charts_config()`
3. Register it in `predictor/backend/app/ml_plugins/registry.py`:
   ```python
   from app.ml_plugins.customer_churn import CustomerChurnPlugin
   _register(CustomerChurnPlugin)
   ```
4. The model automatically appears in the dashboard, with its own upload/train/detect flow

Currently registered models:
| Model | Status | Single-Entry | Events API |
|-------|--------|:------------:|:----------:|
| Billing Invoice Anomaly Detection | Active | No (needs batch context) | No (needs batch context) |
| Customer Churn Prediction | Coming Soon | — | — |
| Customer Lifetime Value | Active | Yes | Yes |
| Revenue Forecasting | Active | No (needs history) | No (needs history) |

> **Why does Billing Anomaly not support single-entry?** The ensemble uses Local Outlier Factor (LOF), a density-based algorithm that compares each invoice to its neighbours. With a single invoice there are no neighbours — LOF needs at least 2 records to function. Plugins that use only tree-based or statistical models (which can score one record against a pre-trained model) can opt in to both single-entry and the Events API.

---

## Single-Entry Scoring (UI)

Plugins that support it show a **"Score Single Entry"** tab on their model page. Users fill in a form and get an immediate result — no CSV upload needed.

### How It Works

1. The plugin defines `supports_single_entry() → True`
2. The plugin returns form field definitions via `get_single_entry_schema()`
3. The frontend renders a dynamic form from those field definitions
4. On submit, the frontend calls `POST /api/runs/{model_id}/detect/single` with a JSON body
5. The plugin's `detect_single()` method scores the record and returns:
   - `is_anomaly` — boolean
   - `confidence` — HIGH / MEDIUM / LOW / NORMAL
   - `score` — 0.0 to 1.0
   - `reasons` — human-readable explanations
   - `details` — model-specific metadata

### Adding Single-Entry Support to a Plugin

```python
class MyPlugin(MLPluginBase):

    def supports_single_entry(self):
        return True

    def get_single_entry_schema(self):
        return [
            {"field": "amount",   "label": "Amount",   "type": "number", "required": True,  "description": "Transaction amount"},
            {"field": "category", "label": "Category", "type": "select", "required": True,  "description": "Product category", "options": ["voice", "data", "sms"]},
            {"field": "account",  "label": "Account",  "type": "text",   "required": False, "description": "Account number"},
        ]

    def detect_single(self, record, model_dir):
        # Load pre-trained model, score the record
        model = joblib.load(model_dir / "model.joblib")
        score = model.predict_proba([record["amount"]])[0][1]
        return {
            "is_anomaly": score > 0.5,
            "confidence": "HIGH" if score > 0.8 else "MEDIUM" if score > 0.5 else "NORMAL",
            "score": round(score, 4),
            "reasons": ["Amount exceeds expected range"] if score > 0.5 else [],
            "details": {"raw_score": score},
        }
```

The form and result card appear automatically in the UI — no frontend changes needed.

---

## Events API (Real-Time Streaming Integration)

The Events API is a **machine-to-machine JSON interface** for scoring records in real-time as they happen. It is designed for integration with streaming systems (Kafka, RabbitMQ, AWS Kinesis, webhooks) or any system that generates events and needs an immediate anomaly/prediction response.

### Architecture

```
┌──────────────┐     JSON event      ┌─────────────────┐     result      ┌──────────────────┐
│  Billing     │ ──────────────────→ │  Predictor      │ ─────────────→ │  Alert / Store   │
│  System      │   POST /api/events  │  Events API     │   JSON response │  (Slack, DB, …)  │
│  (producer)  │                     │  (score_event)  │                 │                  │
└──────────────┘                     └─────────────────┘                 └──────────────────┘

┌──────────────┐     micro-batch     ┌─────────────────┐     results     ┌──────────────────┐
│  Kafka /     │ ──────────────────→ │  POST /events/  │ ─────────────→ │  Stream back     │
│  Kinesis     │   POST .../batch    │  {model}/batch  │   JSON array    │  to topic        │
└──────────────┘                     └─────────────────┘                 └──────────────────┘
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/events/{model_id}` | Score a single event |
| `POST` | `/api/events/{model_id}/batch` | Score up to 1,000 events |
| `GET`  | `/api/events/{model_id}/schema` | Get expected event JSON schema |
| `GET`  | `/api/events/{model_id}/status` | Check if Events API is available and model is trained |

### Quick Start — Score a Single Event

```bash
# 1. Check if the model supports the Events API
curl http://localhost:8000/api/events/my_model/status

# 2. Get the expected event format
curl http://localhost:8000/api/events/my_model/schema

# 3. Score an event
curl -X POST http://localhost:8000/api/events/my_model \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5420.00,
    "category": "data",
    "account": "A-10042"
  }'
```

**Response:**
```json
{
  "status": "scored",
  "model_id": "my_model",
  "model_version": 3,
  "is_anomaly": true,
  "confidence": "HIGH",
  "score": 0.87,
  "reasons": ["Amount (5420.00) is unusually high for this category"],
  "details": {
    "iso_forest_score": -0.42,
    "z_score": 3.1
  },
  "scored_at": "2026-03-08T12:00:00"
}
```

### Score a Batch of Events

Send up to 1,000 events in one request for micro-batching from stream processors:

```bash
curl -X POST http://localhost:8000/api/events/my_model/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"amount": 5420.00, "category": "data", "account": "A-10042"},
    {"amount": 42.50,   "category": "voice", "account": "A-10043"},
    {"amount": 9999.99, "category": "sms",   "account": "A-10044"}
  ]'
```

**Response:**
```json
{
  "status": "scored",
  "model_id": "my_model",
  "model_version": 3,
  "total": 3,
  "anomalies": 2,
  "results": [
    {"event_index": 0, "is_anomaly": true,  "confidence": "HIGH",   "score": 0.87, "reasons": ["..."]},
    {"event_index": 1, "is_anomaly": false, "confidence": "NORMAL", "score": 0.12, "reasons": []},
    {"event_index": 2, "is_anomaly": true,  "confidence": "HIGH",   "score": 0.95, "reasons": ["..."]}
  ],
  "scored_at": "2026-03-08T12:00:00"
}
```

### Integration Examples

**Python — webhook handler:**
```python
import requests

def on_invoice_created(invoice_data):
    """Called when a new invoice is generated in the billing system."""
    resp = requests.post(
        "http://predictor:8000/api/events/my_model",
        json=invoice_data,
    )
    result = resp.json()
    if result["is_anomaly"]:
        send_alert(f"Anomaly detected: {result['reasons']}")
```

**Kafka consumer (Python):**
```python
from kafka import KafkaConsumer, KafkaProducer
import requests, json

consumer = KafkaConsumer("invoices", bootstrap_servers="kafka:9092")
producer = KafkaProducer(bootstrap_servers="kafka:9092")

buffer = []
for msg in consumer:
    buffer.append(json.loads(msg.value))
    if len(buffer) >= 50:  # micro-batch every 50 events
        resp = requests.post(
            "http://predictor:8000/api/events/my_model/batch",
            json=buffer,
        )
        for result in resp.json()["results"]:
            if result["is_anomaly"]:
                producer.send("anomalies", json.dumps(result).encode())
        buffer.clear()
```

**Node.js — Express middleware:**
```javascript
const axios = require('axios');

app.post('/api/invoices', async (req, res, next) => {
  // Score the invoice before saving
  const { data: score } = await axios.post(
    'http://predictor:8000/api/events/my_model',
    req.body
  );
  req.anomalyScore = score;
  if (score.is_anomaly) {
    req.body.flagged = true;
    req.body.flag_reasons = score.reasons;
  }
  next();
});
```

### Adding Events API Support to a Plugin

```python
class MyPlugin(MLPluginBase):

    def supports_event_api(self):
        return True

    def get_event_schema(self):
        return {
            "fields": [
                {"field": "amount",   "type": "number", "required": True,  "description": "Transaction amount"},
                {"field": "category", "type": "string", "required": True,  "description": "Product category"},
                {"field": "account",  "type": "string", "required": False, "description": "Account number"},
            ],
            "example": {
                "amount": 150.00,
                "category": "voice",
                "account": "A-10042",
            }
        }

    def score_event(self, event, model_dir):
        # Load pre-trained model, score the event, return result
        model = joblib.load(model_dir / "model.joblib")
        score = model.predict(...)
        return {
            "is_anomaly": score > threshold,
            "confidence": "HIGH" if score > 0.8 else "MEDIUM" if score > 0.5 else "NORMAL",
            "score": round(score, 4),
            "reasons": [...],
            "details": {...},
        }
```

### Events API vs Single-Entry vs Batch Detect

| Feature | Events API | Single-Entry (UI) | Batch Detect |
|---------|-----------|-------------------|--------------|
| **Interface** | JSON REST API | Web form | CSV file upload |
| **Designed for** | Machines / streaming systems | Humans in the browser | Analysts running periodic checks |
| **Records per request** | 1 or up to 1,000 | 1 | Unlimited (full CSV) |
| **Returns charts?** | No | No | Yes |
| **Saves to run history?** | No | No | Yes |
| **Requires trained model?** | Yes | Yes | Yes |

---

## CLI Tool (Standalone)

The core ML pipeline also works as a standalone CLI tool without the web app.

### How It Works

The detector combines three complementary anomaly detection methods via majority voting:

| Model | Type | What It Catches |
|-------|------|-----------------|
| **Isolation Forest** | Tree-based | Global outliers — invoices with unusual feature combinations |
| **Local Outlier Factor** | Density-based | Local anomalies — invoices that differ from similar neighbours |
| **Statistical Z-Score** | Statistical | Extreme values — amounts beyond 2 standard deviations |

An invoice is flagged as anomalous only when **2 or more models agree**, reducing false positives while maintaining detection coverage.

### What It Detects

- Line-item totals that don't match invoice totals
- Unusually high or low invoice amounts
- Abnormal credit ratios (e.g., 100% credits)
- Non-standard billing periods (e.g., 60-day or 364-day cycles)
- Usage spikes far above account norms
- Overcharge/credit comments in line items
- Invoices deviating from account historical patterns

### Prerequisites

```bash
pip install -r requirements.txt
```

### Option 1: One-Command Analysis

Trains models and detects anomalies in a single pass:

```bash
python run_detector.py full \
    --invoices invoice.csv \
    --details invoice_details.csv \
    --accounts account.csv \
    --output results/ \
    --model-dir models/
```

### Option 2: Train Once, Detect Many Times

**Step 1 — Train:**

```bash
python run_detector.py train \
    --invoices baseline/invoice.csv \
    --details baseline/invoice_details.csv \
    --accounts baseline/account.csv \
    --model-dir models/
```

**Step 2 — Detect:**

```bash
python run_detector.py detect \
    --invoices new_month/invoice.csv \
    --details new_month/invoice_details.csv \
    --accounts new_month/account.csv \
    --model-dir models/ \
    --output results/march_2026/
```

### View Expected Schema

```bash
python run_detector.py schema
```

Prints the full expected CSV schema with required/optional columns, types, and descriptions. CSVs are validated automatically on every run — missing required columns produce clear error messages with "Did you mean?" suggestions for misspelled column names.

---

## Input Data Format

The detector requires three CSV files. Column names are **case-sensitive**. Extra columns are ignored.

### invoice.csv

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `invoice_no` | int | Yes | Unique invoice identifier |
| `acct_no` | int | Yes | Customer account number |
| `debit` | float | Yes | Invoice total charges |
| `credit` | float | Yes | Credit/discount amount |
| `total_due` | float | Yes | Amount due after credits |
| `status_cd` | int | Yes | Payment status (0=unpaid, 2=paid) |
| `bill_date` | date | No | Invoice generation date |
| `bill_from_date` | date | No | Billing period start |
| `bill_thru_date` | date | No | Billing period end |
| `usage_from_date` | date | No | Usage period start |
| `usage_to_date` | date | No | Usage period end |
| `due_date` | date | No | Payment due date |
| `paid_date` | date | No | Date payment was received |
| `from_date` | date | No | Billing period start (alt) |
| `to_date` | date | No | Billing period end (alt) |

### invoice_details.csv

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `invoice_no` | int | Yes | Invoice reference (FK) |
| `seq_num` | int | Yes | Line item sequence number |
| `debit` | float | Yes | Charge amount (negative = credit) |
| `service_no` | str | No | Service/phone number |
| `plan_name` | str | No | Billing plan name |
| `comments` | str | No | Line item notes |
| `usage_units` | float | No | Consumed units (minutes, GB, etc.) |
| `usage_rate` | float | No | Per-unit rate |
| `start_date` | date | No | Service period start |
| `end_date` | date | No | Service period end |

### account.csv

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `acct_no` | int | Yes | Account identifier (PK) |
| `acct_balance` | float | No | Current account balance |
| `plan_date` | date | No | Current plan activation date |
| `acct_start_date` | date | No | Account creation date |

---

## Output

### Console Output

```
======================================================================
  BILLING DISCREPANCY DETECTION RESULTS
  2026-03-07 10:00:00
======================================================================

  Total invoices analysed:  92
  Anomalies detected:       15 (16.3%)

  Method breakdown:
    Isolation Forest:       14 flagged
    Local Outlier Factor:   14 flagged
    Statistical Z-score:    37 flagged
    Ensemble (2+ agree):    15 confirmed

  [1] Invoice #923634  (Account: 387649)  [HIGH]
      Amount: 74.48  Credit: 33.34  Due: 82.14
        - Line items sum (41.14) differs from invoice total (74.48) by 44.8%
        - Contains overcharge/credit comments in line items
  ...
```

### File Outputs

| File | Contents |
|------|----------|
| `anomaly_results.csv` | All invoices with model scores and anomaly flags |
| `anomalous_invoices.csv` | Only flagged invoices (for quick review) |
| `anomaly_report.json` | Structured report with explanations per invoice |

### Anomaly Confidence Levels

| Level | Meaning |
|-------|---------|
| **HIGH** (3/3 models) | All three methods agree — strongest evidence |
| **MEDIUM** (2/3 models) | Two methods agree — warrants investigation |

---

## Generating Visualizations and Reports

### Via Web App (Recommended)

Run detection through Predictor and charts are generated automatically. Export as PNG (individual charts) or PDF (full branded report with logo).

### Via CLI

```bash
# Generate 8 PNG charts
python generate_visualizations.py

# Generate professional Word document report
python generate_report_docx.py
```

### Charts Produced

| Chart | Description |
|-------|-------------|
| Anomaly Distribution | Normal vs anomalous classification pie chart |
| Detection Methods | How many invoices each method flagged |
| Detection Confidence | Voting distribution (0/1/2/3 methods agreed) |
| Anomalies by Account | Which accounts have the most flagged invoices |
| Invoice Amount Distribution | Histogram of debit amounts across all invoices |
| Amount vs Anomaly Score | Scatter plot showing anomalies at score extremes |

---

## Training & Retraining

### When to Retrain

- New billing plans or pricing changes are introduced
- Anomaly rate suddenly spikes or drops (model drift)
- 50+ feedback items collected (auto-retrain threshold)
- Every 3-6 months as routine maintenance

### How to Retrain

**CLI:**
```bash
python run_detector.py train \
    --invoices updated_data/invoice.csv \
    --details updated_data/invoice_details.csv \
    --accounts updated_data/account.csv \
    --model-dir models/
```

**Web App:** Upload new training data → select "Train Model" tab → optionally check "Incremental training" → click "Start Training". A new model version is created automatically.

### Training Data Guidelines

- **Minimum**: 50 invoices
- **Recommended**: 200+ invoices across 3+ billing cycles
- **Ideal**: 6-12 months of historical data
- Data should represent "normal" billing — models learn what normal looks like
- No labels required — fully unsupervised

---

## Project Structure

```
BillingDiscrepencyDetector/
├── run_detector.py                  # CLI app (train / detect / full / schema)
├── invoice_anomaly_detector.py      # Core ML pipeline & feature engineering
├── schema_validator.py              # CSV schema validation & guidance
├── generate_visualizations.py       # Chart generation (8 PNGs)
├── generate_report_docx.py          # Word document report generator
├── requirements.txt                 # Python dependencies (CLI)
├── docker-compose.yml               # Start frontend + backend with one command
│
├── models/                          # Saved model artifacts (CLI)
├── results/                         # Detection output (CLI)
├── charts/                          # Generated visualizations (CLI)
│
├── predictor/                       # Web application
│   ├── start.sh                     # Start both servers (local dev)
│   ├── backend/
│   │   ├── Dockerfile               # Backend container image
│   │   ├── requirements.txt         # Backend Python dependencies
│   │   └── app/
│   │       ├── main.py              # FastAPI application
│   │       ├── database.py          # SQLAlchemy models (SQLite)
│   │       ├── core/
│   │       │   └── config.py        # Paths, DB URL, retrain thresholds
│   │       ├── ml_plugins/
│   │       │   ├── base.py          # Plugin base class (extend this)
│   │       │   ├── registry.py      # Plugin registration
│   │       │   └── billing_anomaly.py  # Billing anomaly plugin
│   │       ├── routers/
│   │       │   ├── models.py        # Model listing & schema APIs
│   │       │   ├── runs.py          # Train, detect, single-entry, feedback
│   │       │   ├── events.py        # Real-time Events API (single + batch)
│   │       │   └── exports.py       # PDF & CSV export APIs
│   │       └── services/            # Business logic (retrain triggers, etc.)
│   └── frontend/
│       ├── Dockerfile               # Frontend container image
│       ├── package.json
│       └── src/
│           ├── App.jsx              # Main app with routing
│           ├── components/
│           │   └── Sidebar.jsx      # Navigation sidebar
│           ├── pages/
│           │   ├── Dashboard.jsx    # Model catalog & stats
│           │   ├── ModelDetail.jsx  # Upload, train, detect, training metrics
│           │   └── RunResults.jsx   # Charts, anomalies, feedback
│           └── hooks/
│               ├── useApi.js        # API client
│               └── useTheme.jsx     # Dark/light theme (default: dark)
│
├── invoice.csv                      # Sample invoice data
├── invoice_details.csv              # Sample line-item data
└── account.csv                      # Sample account data
```

## Feature Engineering

28 features are automatically engineered from the raw CSV data:

| Category | Count | Features |
|----------|-------|----------|
| **Invoice-Level** | 8 | debit, credit, total_due, billing_period_days, usage_period_days, days_to_due, debit_credit_ratio, credit_pct |
| **Line-Item Aggregations** | 13 | count, sum, mean, std, min, max of charges; negative/zero line counts; unique plans/services; credit comments; usage sums |
| **Discrepancy Measures** | 2 | debit_mismatch (absolute), debit_mismatch_pct (percentage) |
| **Account Context** | 5 | account z-score, avg debit, std debit, invoice count, balance |

## Model Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Contamination | 0.15 | Expect ~15% anomaly rate in billing data |
| Isolation Forest trees | 200 | Higher = more stable, diminishing returns past 200 |
| LOF neighbours | 20 | Balances local sensitivity vs noise |
| Z-score threshold | 2.0 | Flags values beyond 2 standard deviations |
| Ensemble rule | 2/3 vote | Reduces false positives vs any single method |
| Random seed | 42 | Ensures reproducible results |

## GPU & Colab Training

Predictor runs CPU-first by default. Heavier plugins (`hardware_failure_detection`,
`mobile_money_fraud`, future transformer-backed sentiment models) opt into GPU
training via `predictor/backend/app/ml_plugins/_gpu_utils.py`, which detects
CUDA at runtime and rewrites the LightGBM `device_type` and XGBoost
`tree_method` arguments accordingly. Falling back to CPU is silent.

### Local — RTX 4070 (Windows / Linux)

Install the NVIDIA driver and a CUDA 12.1+ runtime that matches the LightGBM and
XGBoost wheels on PyPI (both ship CUDA kernels in their default wheels — no
custom build needed). Then install GPU extras on top of the standard requirements:

```bash
pip install -r requirements.txt
pip install -r requirements-gpu.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Verify detection:

```bash
python -c "from app.ml_plugins._gpu_utils import detect_gpu; print(detect_gpu())"
```

Optional — pin the active GPU with `PREDICTOR_CUDA_DEVICES=0`.

### Colab workflow

Notebooks under `notebooks/colab/` are designed for free / Pro Colab runtimes
with Drive mounted. They clone this repo, install backend requirements, and
call each plugin's `train()` directly so the same training code runs locally
on a 4070 or in Colab without modification.

| Notebook | Purpose |
|----------|---------|
| `00_setup.ipynb` | Mount Drive, clone repo, install deps, verify GPU |
| `train_billing_anomaly.ipynb` | Billing anomaly Isolation Forest |
| `train_telecom_churn.ipynb` | Telecom churn classifier |
| `train_telco_customer_churn.ipynb` | Public Telco Customer Churn MLP |
| `train_social_sentiment.ipynb` | TF-IDF social sentiment |
| `train_product_reviews_sentiment.ipynb` | Amazon-style review sentiment |
| `train_hardware_failure_detection.ipynb` | Port-group LGB + XGB ensemble |
| `train_mobile_money_fraud.ipynb` | LightGBM fraud detector |
| `train_revenue_forecasting.ipynb` | Placeholder — plugin in flight |
| `train_customer_lifetime_value.ipynb` | Placeholder — BG/NBD + Gamma-Gamma |

Drive layout the notebooks expect:

```text
/MyDrive/Predictor/
    datasets/<plugin_id>/<file_key>.csv     # one CSV per plugin file_key
    models/<plugin_id>/                      # plugin.train() persists here
    logs/                                    # optional run logs
```

To train a plugin in Colab:

1. Run `00_setup.ipynb` once per VM.
2. Upload the plugin's CSVs to `MyDrive/Predictor/datasets/<plugin_id>/` using
   the same file keys the plugin declares in `required_files` (e.g. for
   `mobile_money_fraud` the file is `transactions.csv`).
3. Open the matching `train_<plugin_id>.ipynb` and run all cells.

Model artifacts are written back to Drive, so subsequent runs on either the
4070 or Colab can resume from the same `MODEL_DIR`.

## Google Drive

Predictor includes a first-class Google Drive connector for (a) pulling
training datasets from Drive, (b) syncing model artifacts produced in Colab
back into the platform, and (c) optional code/dataset backups.

### Auth

Two auth modes are supported. The connector picks whichever is configured —
service account first, OAuth token second.

**Option 1: Service account (recommended for server / Colab)**
1. Create a service account in Google Cloud Console and download its JSON.
2. Share the target Drive folder with the service account's email address.
3. Point `GOOGLE_DRIVE_CREDENTIALS_JSON` at the JSON path:
   ```bash
   export GOOGLE_DRIVE_CREDENTIALS_JSON=/secrets/drive-sa.json
   ```

**Option 2: OAuth user flow**
1. Create an OAuth client (Desktop app) and download `client_secrets.json`.
2. Kick off the flow:
   ```bash
   curl -X POST http://localhost:8000/api/data-sources/drive/connect \
     -H 'Content-Type: application/json' \
     -d '{"client_secrets_path":"/path/to/client_secrets.json","redirect_uri":"http://localhost:8000/oauth/callback"}'
   ```
3. Open `authorization_url` from the response, approve, then exchange the code:
   ```bash
   curl -X POST http://localhost:8000/api/data-sources/drive/connect \
     -H 'Content-Type: application/json' \
     -d '{"client_secrets_path":"/path/to/client_secrets.json","auth_code":"<paste>"}'
   ```
The token is cached in `predictor/backend/.cache/drive_token.json` and refreshed automatically.

### Scopes

- `https://www.googleapis.com/auth/drive.file`     — read/write app-created files
- `https://www.googleapis.com/auth/drive.readonly` — list/read existing files

### Endpoints

- `POST /api/data-sources/drive/connect` — start / complete OAuth
- `POST /api/data-sources/drive/list`    — browse a folder
- `POST /api/data-sources/drive/import`  — import a Drive file as a DatasetVersion
- `GET  /api/drive/status`               — auth + last-sync diagnostics
- `POST /api/drive/models/{model_id}/sync_up`   — push artifacts to Drive
- `POST /api/drive/models/{model_id}/sync_down` — pull artifacts from Drive

### Colab loop

In Colab, mount Drive (`drive.mount("/content/drive")`) and write trained
artifacts to the same Drive folder you registered with Predictor. Then call
`POST /api/drive/models/{model_id}/sync_down` to materialise the artifacts
into MinIO at the model version's prefix.

## Requirements

### Docker (simplest)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — no other dependencies needed

### CLI Tool (local)
- Python 3.9+
- pandas >= 2.0.0
- numpy >= 1.24.0
- scikit-learn >= 1.3.0
- matplotlib >= 3.7.0 (for charts)
- seaborn >= 0.12.0 (for charts)
- python-docx >= 1.0.0 (for Word report)
- joblib (included with scikit-learn)

### Web App — local dev (additional)
- Node.js >= 18
- FastAPI >= 0.104.0
- uvicorn >= 0.24.0
- SQLAlchemy >= 2.0.0
- reportlab >= 4.0.0 (for PDF export)
