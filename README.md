# Ula - Personal Workspace Assistant

Ula is a lightweight AI workspace and life operations assistant built with Google Agent Development Kit (ADK).
It helps users manage daily work, personal routines, and lightweight data questions through natural language.

Deployed on Google Cloud Run with the ADK Dev UI.

## Features

- Task management: create, list, and complete tasks
- Notes management: save and list quick notes
- Meeting notes summary: extract summaries, decisions, and action items
- Weather advice: check worldwide city forecasts with practical reminders
- Personal finance: record income/expenses and view summaries
- Shopping list: add, list, and mark items as bought
- Work email drafting: generate professional email drafts
- Wikipedia lookup: search and summarize topics
- BigQuery analytics: query prepared market datasets with read-only SQL

## Tech Stack

- Python
- Google Agent Development Kit (ADK)
- Gemini via Vertex AI
- Google Cloud Run
- Firestore in Datastore mode
- BigQuery
- LangChain Wikipedia tool
- Open-Meteo Weather API

## Project Structure

```text
.
├── __init__.py
├── agent.py
├── tools.py
├── requirements.txt
├── .env.example
└── README.md
```

## Environment Variables

Create a .env file in the project root:
```bash
PROJECT_ID=your-gcp-project-id
PROJECT_NUMBER=your-project-number
SA_NAME=your-service-account-name
SERVICE_ACCOUNT=your-service-account@your-project-id.iam.gserviceaccount.com

MODEL=gemini-2.5-flash-lite
DB_ID=genasdb
BQ_DATASET=marketdata

GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_API_KEY=""
```

### Required Google Cloud Services

Enable these services in your Google Cloud project:

* Vertex AI API
* Cloud Run API
* Cloud Build API
* IAM API
* Firestore / Datastore API
* BigQuery API
* BigQuery Storage API

### Recommended roles for the Cloud Run service account:

* roles/aiplatform.user
* roles/datastore.user
* roles/bigquery.jobUser
* roles/bigquery.dataViewer

### Run Locally
```bash
cd ~/ula_asgen_agents

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

set -a
source .env
set +a

adk run .
```

### Deploy to Cloud Run
```bash
cd ~/ula_asgen_agents

export UV_CACHE_DIR=/tmp/uv-cache
export PIP_CACHE_DIR=/tmp/pip-cache

set -a
source .env
set +a

uvx --from google-adk==1.14.0 \
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=europe-west1 \
  --service_name=ula-asgen-guide \
  --with_ui \
  . \
  -- \
  --labels=dev-tutorial=asgen-adk \
  --service-account=$SERVICE_ACCOUNT
```

### Example Prompts
```bash
Who are you?
```
```bash
What can you do?
```
```bash
Add a task: prepare the final demo video.
```
```bash
Summarize this meeting note: Today we discussed the final submission. Zoe will finish the GitHub repo and demo video before Friday.
```
```bash
Check the weather in Tokyo for the next 3 days and tell me whether I should bring an umbrella.
```
```bash
Add income: 50000 TWD salary in category salary.
```
```bash
Add an expense: 120 TWD for lunch in category food.
```
```bash
Show my finance summary.
```
```bash
Add a shopping item: milk, quantity 1 bottle, category groceries.
```
```bash
Draft a professional work email asking my manager for a deadline extension.
```
```bash
Look up Docker on Wikipedia and summarize it in 3 bullet points.
```
```bash
Using BigQuery, list the top 10 cryptocurrencies by market cap.
```

### BigQuery Dataset

The assistant is configured to work with a prepared BigQuery dataset:
```bash
marketdata
```
Expected tables:
```bash
gold_silver_raw
crypto_top1000_raw
company_financials_raw
```
BigQuery tools are read-only and only allow SELECT or WITH queries.

## Notes

If the ADK Dev UI returns 429 RESOURCE_EXHAUSTED, wait a few minutes and retry.
This usually means the Vertex AI / Gemini quota or rate limit was temporarily reached.

## Demo

[▶ Watch Demo on YouTube](https://www.youtube.com/watch?v=wC11d3a3whs)

[![Demo Video](https://img.youtube.com/vi/wC11d3a3whs/hqdefault.jpg)](https://www.youtube.com/watch?v=wC11d3a3whs)