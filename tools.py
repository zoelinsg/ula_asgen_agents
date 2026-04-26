import os
import datetime
import decimal
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from google.cloud import datastore
from google.cloud import bigquery

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_DATASET = os.getenv("BQ_DATASET", "marketdata")
DB_ID = os.getenv("DB_ID", "genasdb")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _json_safe(value: Any) -> Any:
    """Convert Google Cloud client values into JSON-safe values."""
    if value is None:
        return None

    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()

    if isinstance(value, decimal.Decimal):
        return float(value)

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    return value


def _format_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """Format rows as a simple Markdown table for ADK/tool output."""
    if not rows:
        return "Query ran successfully, but returned no rows."

    columns = list(rows[0].keys())

    def fmt(value: Any) -> str:
        safe = _json_safe(value)
        text = str(safe)
        text = text.replace("\n", " ").replace("|", "\\|")
        return text if len(text) <= 120 else text[:117] + "..."

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = [
        "| " + " | ".join(fmt(row.get(col)) for col in columns) + " |"
        for row in rows
    ]

    return "\n".join([header, separator] + body)


def _format_money(amount: float, currency: str = "TWD") -> str:
    """Format money values in a readable way."""
    if float(amount).is_integer():
        return f"{amount:,.0f} {currency}"
    return f"{amount:,.2f} {currency}"


db = datastore.Client(database=DB_ID)


def add_task(title: str) -> str:
    """Create a new task in Datastore."""
    key = db.key("Task")
    task = datastore.Entity(key=key)
    task.update(
        {
            "title": title,
            "completed": False,
            "created_at": _now(),
        }
    )
    db.put(task)
    return f"Task created: '{title}' (ID: {task.key.id})"


def list_tasks() -> str:
    """List recent tasks from Datastore."""
    q = db.query(kind="Task")
    q.order = ["-created_at"]
    tasks = list(q.fetch(limit=50))

    if not tasks:
        return "Your task list is empty."

    lines = ["Current Tasks:"]
    for task in tasks:
        status = "Done" if task.get("completed") else "Pending"
        title = task.get("title", "(untitled)")
        lines.append(f"- {status}: {title} (ID: {task.key.id})")

    return "\n".join(lines)


def complete_task(task_id: str) -> str:
    """Mark a task as completed using its numeric ID."""
    digits = "".join(filter(str.isdigit, str(task_id)))
    if not digits:
        return "Please provide a valid task ID."

    numeric_id = int(digits)
    key = db.key("Task", numeric_id)
    task = db.get(key)

    if not task:
        return f"Task {numeric_id} not found. Tip: run 'List my tasks' and copy the ID."

    task["completed"] = True
    task["completed_at"] = _now()
    db.put(task)

    return f"Task {numeric_id} marked as done."


def add_note(title: str, content: str) -> str:
    """
    Save a general note in Datastore.
    Use this for daily thoughts, quick notes, ideas, reminders, or learning snippets.
    """
    key = db.key("Note")
    note = datastore.Entity(key=key)
    note.update(
        {
            "title": title,
            "content": content,
            "created_at": _now(),
            "note_type": "general",
        }
    )
    db.put(note)

    return f"Note '{title}' saved successfully."


def list_notes(limit: int = 20) -> str:
    """List recent general notes from Datastore."""
    q = db.query(kind="Note")
    q.order = ["-created_at"]

    safe_limit = max(1, min(int(limit), 50))
    notes = list(q.fetch(limit=safe_limit))

    if not notes:
        return "No notes yet."

    lines = ["Recent Notes:"]
    for note in notes:
        title = note.get("title", "(untitled)")
        lines.append(f"- {title} (ID: {note.key.id})")

    return "\n".join(lines)


def summarize_meeting_notes(raw_notes: str) -> str:
    """
    Convert raw meeting notes into a clean meeting summary format.
    Use this when the user pastes meeting notes and asks for meeting minutes.
    """
    raw_notes = raw_notes.strip()

    if not raw_notes:
        return "Please provide the meeting notes you want me to summarize."

    return f"""
## Meeting Notes Summary

### 1. Brief Summary
Summarize the meeting notes into 2-4 concise sentences.

### 2. Key Discussion Points
Extract the important discussion points from the meeting.

### 3. Decisions Made
List any clear decisions made during the meeting. If no clear decision is mentioned, write "No clear decision mentioned."

### 4. Action Items
Extract action items in this format:
- Owner:
- Task:
- Due date:

If owner or due date is missing, mark it as "Not specified."

### 5. Suggested Follow-up
Suggest the next steps based on the meeting notes.

---

Raw meeting notes:
{raw_notes}
""".strip()


def save_meeting_summary(title: str, summary: str, raw_notes: str = "") -> str:
    """
    Save a finalized meeting summary in Datastore.
    Use this after a meeting note has been summarized.
    """
    key = db.key("MeetingNote")
    meeting_note = datastore.Entity(key=key)
    meeting_note.update(
        {
            "title": title,
            "summary": summary,
            "raw_notes": raw_notes,
            "created_at": _now(),
        }
    )
    db.put(meeting_note)

    return f"Meeting summary '{title}' saved successfully. (ID: {meeting_note.key.id})"


def list_meeting_summaries(limit: int = 10) -> str:
    """List recent saved meeting summaries."""
    q = db.query(kind="MeetingNote")
    q.order = ["-created_at"]

    safe_limit = max(1, min(int(limit), 30))
    items = list(q.fetch(limit=safe_limit))

    if not items:
        return "No saved meeting summaries yet."

    lines = ["Recent Meeting Summaries:"]
    for item in items:
        title = item.get("title", "(untitled meeting)")
        lines.append(f"- {title} (ID: {item.key.id})")

    return "\n".join(lines)


def add_expense(
    amount: float,
    category: str,
    description: str = "",
    currency: str = "TWD",
) -> str:
    """Add a personal expense record to Datastore."""
    key = db.key("Expense")
    expense = datastore.Entity(key=key)
    expense.update(
        {
            "amount": float(amount),
            "category": category.strip() if category else "Uncategorized",
            "description": description.strip(),
            "currency": currency.strip().upper() if currency else "TWD",
            "created_at": _now(),
        }
    )
    db.put(expense)

    desc = f" for {description}" if description else ""
    return (
        f"Expense added: {_format_money(float(amount), expense['currency'])} "
        f"in category '{expense['category']}'{desc}. "
        f"(ID: {expense.key.id})"
    )


def list_expenses(limit: int = 20) -> str:
    """List recent personal expenses."""
    q = db.query(kind="Expense")
    q.order = ["-created_at"]

    safe_limit = max(1, min(int(limit), 50))
    expenses = list(q.fetch(limit=safe_limit))

    if not expenses:
        return "No expense records yet."

    lines = ["Recent Expenses:"]
    for expense in expenses:
        amount = float(expense.get("amount", 0))
        currency = expense.get("currency", "TWD")
        category = expense.get("category", "Uncategorized")
        description = expense.get("description", "")
        created_at = _json_safe(expense.get("created_at"))

        desc = f" - {description}" if description else ""
        lines.append(
            f"- {_format_money(amount, currency)} | {category}{desc} | {created_at} | ID: {expense.key.id}"
        )

    return "\n".join(lines)


def add_income(
    amount: float,
    category: str = "Income",
    description: str = "",
    currency: str = "TWD",
) -> str:
    """Add a personal income record to Datastore."""
    key = db.key("Income")
    income = datastore.Entity(key=key)
    income.update(
        {
            "amount": float(amount),
            "category": category.strip() if category else "Income",
            "description": description.strip(),
            "currency": currency.strip().upper() if currency else "TWD",
            "created_at": _now(),
        }
    )
    db.put(income)

    desc = f" for {description}" if description else ""
    return (
        f"Income added: {_format_money(float(amount), income['currency'])} "
        f"in category '{income['category']}'{desc}. "
        f"(ID: {income.key.id})"
    )


def list_incomes(limit: int = 20) -> str:
    """List recent personal income records."""
    q = db.query(kind="Income")
    q.order = ["-created_at"]

    safe_limit = max(1, min(int(limit), 50))
    incomes = list(q.fetch(limit=safe_limit))

    if not incomes:
        return "No income records yet."

    lines = ["Recent Income Records:"]
    for income in incomes:
        amount = float(income.get("amount", 0))
        currency = income.get("currency", "TWD")
        category = income.get("category", "Income")
        description = income.get("description", "")
        created_at = _json_safe(income.get("created_at"))

        desc = f" - {description}" if description else ""
        lines.append(
            f"- {_format_money(amount, currency)} | {category}{desc} | {created_at} | ID: {income.key.id}"
        )

    return "\n".join(lines)


def list_finance_records(limit: int = 20) -> str:
    """List recent income and expense records together."""
    safe_limit = max(1, min(int(limit), 50))

    expense_q = db.query(kind="Expense")
    expenses = list(expense_q.fetch(limit=200))

    income_q = db.query(kind="Income")
    incomes = list(income_q.fetch(limit=200))

    records = []

    for expense in expenses:
        records.append(
            {
                "type": "Expense",
                "amount": float(expense.get("amount", 0)),
                "currency": expense.get("currency", "TWD"),
                "category": expense.get("category", "Uncategorized"),
                "description": expense.get("description", ""),
                "created_at": expense.get("created_at"),
                "id": expense.key.id,
            }
        )

    for income in incomes:
        records.append(
            {
                "type": "Income",
                "amount": float(income.get("amount", 0)),
                "currency": income.get("currency", "TWD"),
                "category": income.get("category", "Income"),
                "description": income.get("description", ""),
                "created_at": income.get("created_at"),
                "id": income.key.id,
            }
        )

    records.sort(
        key=lambda item: item.get("created_at")
        or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
        reverse=True,
    )

    if not records:
        return "No finance records yet."

    lines = ["Recent Finance Records:"]
    for record in records[:safe_limit]:
        sign = "+" if record["type"] == "Income" else "-"
        desc = f" - {record['description']}" if record["description"] else ""
        created_at = _json_safe(record.get("created_at"))

        lines.append(
            f"- {record['type']} {sign}{_format_money(record['amount'], record['currency'])} "
            f"| {record['category']}{desc} | {created_at} | ID: {record['id']}"
        )

    return "\n".join(lines)


def finance_summary(limit: int = 500) -> str:
    """Summarize income, expenses, and net balance by currency and category."""
    safe_limit = max(1, min(int(limit), 1000))

    expense_q = db.query(kind="Expense")
    expenses = list(expense_q.fetch(limit=safe_limit))

    income_q = db.query(kind="Income")
    incomes = list(income_q.fetch(limit=safe_limit))

    if not expenses and not incomes:
        return "No finance records yet."

    currencies = set()
    income_totals: Dict[str, float] = {}
    expense_totals: Dict[str, float] = {}
    income_by_category: Dict[str, Dict[str, float]] = {}
    expense_by_category: Dict[str, Dict[str, float]] = {}

    for income in incomes:
        amount = float(income.get("amount", 0))
        currency = income.get("currency", "TWD")
        category = income.get("category", "Income")

        currencies.add(currency)
        income_totals[currency] = income_totals.get(currency, 0) + amount

        if currency not in income_by_category:
            income_by_category[currency] = {}
        income_by_category[currency][category] = (
            income_by_category[currency].get(category, 0) + amount
        )

    for expense in expenses:
        amount = float(expense.get("amount", 0))
        currency = expense.get("currency", "TWD")
        category = expense.get("category", "Uncategorized")

        currencies.add(currency)
        expense_totals[currency] = expense_totals.get(currency, 0) + amount

        if currency not in expense_by_category:
            expense_by_category[currency] = {}
        expense_by_category[currency][category] = (
            expense_by_category[currency].get(category, 0) + amount
        )

    lines = ["Finance Summary"]

    for currency in sorted(currencies):
        total_income = income_totals.get(currency, 0)
        total_expense = expense_totals.get(currency, 0)
        net_balance = total_income - total_expense

        lines.append(f"\nCurrency: {currency}")
        lines.append(f"- Income: {_format_money(total_income, currency)}")
        lines.append(f"- Expenses: {_format_money(total_expense, currency)}")
        lines.append(f"- Net Balance: {_format_money(net_balance, currency)}")

        if income_by_category.get(currency):
            lines.append("\nIncome by category:")
            for category, amount in sorted(
                income_by_category[currency].items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                lines.append(f"- {category}: {_format_money(amount, currency)}")

        if expense_by_category.get(currency):
            lines.append("\nExpenses by category:")
            for category, amount in sorted(
                expense_by_category[currency].items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                lines.append(f"- {category}: {_format_money(amount, currency)}")

    return "\n".join(lines)


def expense_summary(limit: int = 500) -> str:
    """Backward-compatible expense summary. Redirects to finance_summary."""
    return finance_summary(limit=limit)


WEATHER_CODE_TEXT = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def _resolve_city_coordinates(city: str) -> Dict[str, Any]:
    """Resolve a city name into latitude and longitude using Open-Meteo Geocoding API."""
    city = city.strip()

    if not city:
        raise ValueError("Please provide a city name.")

    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        raise ValueError(
            f"Could not find weather location for '{city}'. "
            "Please try a more specific city name, such as 'Taipei', 'Tokyo', or 'New York'."
        )

    location = results[0]

    return {
        "name": location.get("name", city),
        "country": location.get("country", ""),
        "admin1": location.get("admin1", ""),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location.get("timezone", "auto"),
    }


def _weather_reminder(
    max_temp: Optional[float],
    min_temp: Optional[float],
    rain_prob: Optional[float],
    weather_code: Optional[int],
) -> str:
    reminders = []

    if rain_prob is not None and rain_prob >= 50:
        reminders.append("bring an umbrella")
    elif weather_code in {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}:
        reminders.append("prepare rain gear")

    if min_temp is not None and min_temp <= 14:
        reminders.append("dress warmly")
    elif min_temp is not None and min_temp <= 18:
        reminders.append("wear a light jacket")

    if max_temp is not None and max_temp >= 30:
        reminders.append("stay hydrated and avoid staying outdoors too long")

    if not reminders:
        return "comfortable weather overall"

    return ", ".join(reminders)


def get_weather_advice(city: str = "Taipei", days: int = 3) -> str:
    """
    Get weather forecast and practical reminders for a city worldwide.
    Use this for city weather, rain probability, or umbrella reminders.
    """
    try:
        location = _resolve_city_coordinates(city)
    except Exception as exc:
        return str(exc)

    safe_days = max(1, min(int(days), 7))
    timezone = location.get("timezone") or "auto"

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                ]
            ),
            "forecast_days": safe_days,
            "timezone": timezone,
        },
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    daily = data.get("daily", {})

    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])

    location_parts = [
        location.get("name"),
        location.get("admin1"),
        location.get("country"),
    ]
    location_label = ", ".join([part for part in location_parts if part])

    lines = [f"{location_label} weather advice for the next {safe_days} day(s):"]

    for index, date_str in enumerate(dates):
        code = codes[index] if index < len(codes) else None
        max_temp = max_temps[index] if index < len(max_temps) else None
        min_temp = min_temps[index] if index < len(min_temps) else None
        rain_prob = rain_probs[index] if index < len(rain_probs) else None

        description = WEATHER_CODE_TEXT.get(code, "Weather data available")
        reminder = _weather_reminder(max_temp, min_temp, rain_prob, code)

        temp_text = (
            f"{min_temp:.0f}-{max_temp:.0f}°C"
            if min_temp is not None and max_temp is not None
            else "temperature data unavailable"
        )
        rain_text = (
            f"rain chance {rain_prob:.0f}%"
            if rain_prob is not None
            else "rain chance unavailable"
        )

        lines.append(
            f"- {date_str}: {description}, {temp_text}, {rain_text}. Suggestion: {reminder}."
        )

    return "\n".join(lines)


def draft_work_email(
    purpose: str,
    context: str,
    recipient: str = "",
    tone: str = "professional",
    language: str = "English",
) -> str:
    """
    Prepare a professional work email draft from a short description.
    Use this when the user asks to write, polish, or draft a work email.
    """
    purpose = purpose.strip()
    context = context.strip()
    recipient = recipient.strip() or "the recipient"
    tone = tone.strip() or "professional"
    language = language.strip() or "English"

    if not purpose and not context:
        return "Please provide the purpose and context for the work email."

    return f"""
Please draft a {tone} work email in {language}.

Email purpose:
{purpose}

Recipient:
{recipient}

Context:
{context}

Requirements:
- Include a clear subject line.
- Keep the tone polite, concise, and professional.
- Make the ask or next step clear.
- Avoid being too wordy.
- Use a natural human writing style.
- If information is missing, use neutral wording instead of inventing details.
- Do not use emojis.

Output format:
Subject: ...

Hi ...,

...

Best regards,
""".strip()


def add_shopping_item(
    item: str,
    quantity: str = "1",
    category: str = "General",
) -> str:
    """Add an item to the shopping list."""
    item = item.strip()
    quantity = str(quantity).strip() if quantity else "1"
    category = category.strip() if category else "General"

    if not item:
        return "Please provide the shopping item name."

    key = db.key("ShoppingItem")
    shopping_item = datastore.Entity(key=key)
    shopping_item.update(
        {
            "item": item,
            "quantity": quantity,
            "category": category,
            "bought": False,
            "created_at": _now(),
        }
    )
    db.put(shopping_item)

    return (
        f"Added to shopping list: {item} x {quantity} "
        f"in category '{category}'. (ID: {shopping_item.key.id})"
    )


def list_shopping_items(show_bought: bool = False) -> str:
    """List shopping items. By default, only show unbought items."""
    q = db.query(kind="ShoppingItem")
    q.order = ["-created_at"]
    items = list(q.fetch(limit=100))

    if not show_bought:
        items = [item for item in items if not item.get("bought", False)]

    if not items:
        return "Your shopping list is empty."

    grouped: Dict[str, List[Any]] = {}
    for item in items:
        category = item.get("category", "General")
        grouped.setdefault(category, []).append(item)

    title = "Shopping List" if not show_bought else "Shopping List Including Bought Items"
    lines = [title]

    for category in sorted(grouped.keys()):
        lines.append(f"\n{category}:")
        for item in grouped[category]:
            status = "Done" if item.get("bought") else "Pending"
            name = item.get("item", "(unnamed)")
            quantity = item.get("quantity", "1")
            lines.append(f"- {status}: {name} x {quantity} (ID: {item.key.id})")

    return "\n".join(lines)


def mark_shopping_item_bought(item_id: str) -> str:
    """Mark a shopping item as bought using its numeric ID."""
    digits = "".join(filter(str.isdigit, str(item_id)))
    if not digits:
        return "Please provide a valid shopping item ID."

    numeric_id = int(digits)
    key = db.key("ShoppingItem", numeric_id)
    item = db.get(key)

    if not item:
        return f"Shopping item {numeric_id} not found. Tip: run 'List my shopping list' and copy the ID."

    item["bought"] = True
    item["bought_at"] = _now()
    db.put(item)

    return f"Marked shopping item as bought: {item.get('item', numeric_id)}."


def clear_bought_shopping_items() -> str:
    """Delete bought shopping items from the shopping list."""
    q = db.query(kind="ShoppingItem")
    items = list(q.fetch(limit=200))
    bought_items = [item for item in items if item.get("bought", False)]

    if not bought_items:
        return "No bought shopping items to clear."

    for item in bought_items:
        db.delete(item.key)

    return f"Cleared {len(bought_items)} bought shopping item(s)."


bq = bigquery.Client(project=PROJECT_ID)


def _fq_table(table: str) -> str:
    """
    Accepts table, dataset.table, or project.dataset.table.
    Returns a fully qualified BigQuery table name.
    """
    table = table.strip().strip("`")
    parts = table.split(".")

    if len(parts) == 1:
        return f"`{PROJECT_ID}.{BQ_DATASET}.{parts[0]}`"

    if len(parts) == 2:
        return f"`{PROJECT_ID}.{parts[0]}.{parts[1]}`"

    if len(parts) == 3:
        return f"`{parts[0]}.{parts[1]}.{parts[2]}`"

    raise ValueError(
        "Invalid table name. Use table, dataset.table, or project.dataset.table."
    )


def _is_safe_select_sql(sql: str) -> bool:
    """Allow read-only SELECT or WITH queries only."""
    normalized = sql.strip().lower()

    if not (normalized.startswith("select") or normalized.startswith("with")):
        return False

    blocked_keywords = [
        " insert ",
        " update ",
        " delete ",
        " merge ",
        " drop ",
        " alter ",
        " create ",
        " truncate ",
        " grant ",
        " revoke ",
        " call ",
        " begin ",
        " commit ",
        " rollback ",
    ]

    padded = f" {normalized} "
    return not any(keyword in padded for keyword in blocked_keywords)


def bq_list_tables() -> str:
    """List available BigQuery tables in the configured dataset."""
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, BQ_DATASET)
    tables = [table.table_id for table in bq.list_tables(dataset_ref)]

    if not tables:
        return f"No tables found in `{PROJECT_ID}.{BQ_DATASET}`."

    return "Available BigQuery tables:\n" + "\n".join(f"- {table}" for table in tables)


def bq_schema(table: str) -> str:
    """Show the schema of a BigQuery table."""
    table_ref = _fq_table(table).strip("`")
    target = bq.get_table(table_ref)

    rows = [
        {
            "name": field.name,
            "type": field.field_type,
            "mode": field.mode,
        }
        for field in target.schema
    ]

    return f"Schema for `{table_ref}`:\n\n" + _format_markdown_table(rows)


def bq_preview(table: str, limit: int = 5) -> str:
    """Preview rows from a BigQuery table."""
    safe_limit = max(1, min(int(limit), 50))
    sql = f"SELECT * FROM {_fq_table(table)} LIMIT {safe_limit}"
    return bq_sql(sql)


def bq_sql(sql: str) -> str:
    """Run a read-only BigQuery SQL query and return results as a Markdown table."""
    if not _is_safe_select_sql(sql):
        return "Only SELECT/WITH queries are allowed."

    job = bq.query(sql)
    rows = job.result()

    safe_rows = [
        {str(key): _json_safe(value) for key, value in dict(row).items()}
        for row in rows
    ]

    return _format_markdown_table(safe_rows)


def bq_latest_gold_silver_date() -> str:
    """Get the latest available date from gold_silver_raw."""
    sql = f"""
    SELECT MAX(date) AS latest_date
    FROM `{PROJECT_ID}.{BQ_DATASET}.gold_silver_raw`
    """
    return bq_sql(sql)