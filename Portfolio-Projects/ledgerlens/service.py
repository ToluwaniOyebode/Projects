"""Exact-money expense ledger; atomic CSV ingestion and repeat-import protection."""

import calendar
import csv
import hashlib
import io
import re
import sqlite3
from datetime import date
from decimal import Decimal

from webcore import Problem, Raw, connect, csv_cell, iso_date, text

CATEGORIES = (
    "food",
    "groceries",
    "transport",
    "bills",
    "shopping",
    "health",
    "learning",
    "other",
)
RULES = {
    "food": ("restaurant", "cafe", "lunch", "dinner", "coffee"),
    "groceries": ("grocery", "groceries", "supermarket", "market"),
    "transport": ("uber", "bolt", "bus", "fuel", "taxi"),
    "bills": ("electricity", "internet", "rent", "airtime", "data plan"),
    "shopping": ("clothes", "shoes", "store"),
    "health": ("pharmacy", "hospital", "clinic"),
    "learning": ("course", "book", "tuition"),
}


def amount_cents(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"-?\d{1,10}(?:\.\d{1,2})?", value.strip()
    ):
        raise Problem("amount must be a decimal string with at most two decimal places")
    cents = int(Decimal(value.strip()) * 100)
    if cents == 0:
        raise Problem(
            "amount must be non-zero; positive means expense, negative means refund"
        )
    return cents


def month_value(value):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(value)):
        raise Problem("month must use YYYY-MM")
    iso_date(value + "-01", "month")
    return value


def categorize(description):
    words = description.casefold()
    for category, phrases in RULES.items():
        if any(re.search(r"\b" + re.escape(p) + r"\b", words) for p in phrases):
            return category
    return "other"


def parse_transaction(data):
    day = iso_date(data.get("date", ""), "date")
    description = text(data.get("description", ""), "description", 300)
    cents = amount_cents(data.get("amount"))
    category = data.get("category") or categorize(description)
    if category not in CATEGORIES:
        raise Problem("Unknown category")
    canonical = f'{day}|{" ".join(description.casefold().split())}|{cents}'
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    return day, description, cents, category, fingerprint


class App:
    name = "LedgerLens"

    def __init__(self, path, demo=True):
        self.path = path
        with connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
              CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, date TEXT NOT NULL,
                description TEXT NOT NULL, cents INTEGER NOT NULL CHECK(cents != 0),
                category TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE);
              CREATE INDEX IF NOT EXISTS transactions_date ON transactions(date);
              CREATE TABLE IF NOT EXISTS budgets(month TEXT NOT NULL, category TEXT NOT NULL, cents INTEGER NOT NULL CHECK(cents>0), PRIMARY KEY(month,category));
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY);
            """
            )
            if (
                demo
                and not db.execute(
                    "SELECT 1 FROM metadata WHERE key='seeded'"
                ).fetchone()
            ):
                today = date.today()
                for offset in range(4):
                    idx = today.year * 12 + today.month - 1 - offset
                    year, month = divmod(idx, 12)
                    for day, desc, cost in [
                        (2, "Weekly grocery market", "18250.00"),
                        (4, "Bolt ride", "4800.00"),
                        (6, "Internet subscription", "22000.00"),
                        (9, "Lunch at the cafe", "6500.00"),
                        (12, "Python course", "15000.00"),
                        (15, "Supermarket essentials", "12300.00"),
                        (19, "Pharmacy visit", "8400.00"),
                        (22, "Fuel refill", "28000.00"),
                        (25, "Coffee with friends", "3200.00"),
                        (26, "Course refund", "-2500.00"),
                    ]:
                        values = parse_transaction(
                            {
                                "date": f"{year:04d}-{month+1:02d}-{min(day,today.day) if offset==0 else day:02d}",
                                "description": desc,
                                "amount": str(Decimal(cost) + offset * 250),
                            }
                        )
                        db.execute(
                            "INSERT OR IGNORE INTO transactions(date,description,cents,category,fingerprint) VALUES(?,?,?,?,?)",
                            values,
                        )
                for category, cents in [
                    ("food", 1500000),
                    ("groceries", 4000000),
                    ("transport", 4000000),
                    ("bills", 3000000),
                ]:
                    db.execute(
                        "INSERT INTO budgets VALUES(?,?,?)",
                        (today.strftime("%Y-%m"), category, cents),
                    )
                db.execute("INSERT INTO metadata VALUES('seeded')")

    def add(self, data):
        values = parse_transaction(data)
        with connect(self.path) as db:
            try:
                result = db.execute(
                    "INSERT INTO transactions(date,description,cents,category,fingerprint) VALUES(?,?,?,?,?)",
                    values,
                )
            except sqlite3.IntegrityError:
                raise Problem("An identical transaction already exists", 409) from None
            return dict(
                db.execute(
                    "SELECT * FROM transactions WHERE id=?", (result.lastrowid,)
                ).fetchone()
            )

    def import_csv(self, source):
        source = text(source, "csv", 800000)
        reader = csv.DictReader(io.StringIO(source.lstrip("\ufeff")))
        if not reader.fieldnames or not {"date", "description", "amount"}.issubset(
            reader.fieldnames
        ):
            raise Problem(
                "CSV needs date, description and amount columns; category is optional"
            )
        parsed = []
        try:
            for number, row in enumerate(reader, start=2):
                if number > 2001:
                    raise Problem("CSV is limited to 2,000 transactions")
                try:
                    parsed.append(parse_transaction(row))
                except Problem as error:
                    raise Problem(f"Row {number}: {error}") from None
        except csv.Error as error:
            raise Problem(f"Invalid CSV: {error}") from None
        if not parsed:
            raise Problem("CSV contains no transactions")
        with connect(self.path) as db:
            inserted = 0
            for values in parsed:
                inserted += db.execute(
                    "INSERT OR IGNORE INTO transactions(date,description,cents,category,fingerprint) VALUES(?,?,?,?,?)",
                    values,
                ).rowcount
        return {
            "inserted": inserted,
            "duplicates": len(parsed) - inserted,
            "rows": len(parsed),
        }

    def transactions(self, month):
        month = month_value(month)
        with connect(self.path) as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM transactions WHERE substr(date,1,7)=? ORDER BY date DESC,id DESC",
                    (month,),
                )
            ]

    def summary(self, month):
        rows = self.transactions(month)
        with connect(self.path) as db:
            budgets = {
                r["category"]: r["cents"]
                for r in db.execute("SELECT * FROM budgets WHERE month=?", (month,))
            }
            trend = [
                dict(r)
                for r in db.execute(
                    "SELECT substr(date,1,7) month,sum(cents) cents FROM transactions GROUP BY month ORDER BY month DESC LIMIT 6"
                )
            ][::-1]
        categories = [
            {
                "category": c,
                "cents": sum(r["cents"] for r in rows if r["category"] == c),
                "budget_cents": budgets.get(c, 0),
            }
            for c in CATEGORIES
        ]
        return {
            "month": month,
            "currency": "NGN",
            "count": len(rows),
            "net_cents": sum(r["cents"] for r in rows),
            "gross_cents": sum(r["cents"] for r in rows if r["cents"] > 0),
            "refund_cents": -sum(r["cents"] for r in rows if r["cents"] < 0),
            "budget_cents": sum(budgets.values()),
            "categories": categories,
            "trend": trend,
        }

    def handle(self, method, path, query, body):
        month = query.get("month", date.today().strftime("%Y-%m"))
        if path == "/api/transactions" and method == "GET":
            return self.transactions(month)
        if path == "/api/transactions" and method == "POST":
            return self.add(body)
        if path == "/api/import" and method == "POST":
            return self.import_csv(body.get("csv"))
        if path == "/api/summary" and method == "GET":
            return self.summary(month)
        if path == "/api/budgets" and method == "POST":
            month = month_value(body.get("month"))
            category = body.get("category")
            if category not in CATEGORIES:
                raise Problem("Unknown category")
            cents = amount_cents(body.get("amount"))
            if cents < 0:
                raise Problem("Budget must be positive")
            with connect(self.path) as db:
                db.execute(
                    "INSERT INTO budgets VALUES(?,?,?) ON CONFLICT(month,category) DO UPDATE SET cents=excluded.cents",
                    (month, category, cents),
                )
            return {"month": month, "category": category, "cents": cents}
        if path == "/api/export.csv" and method == "GET":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["date", "description", "amount", "category"])
            for row in self.transactions(month):
                writer.writerow(
                    [
                        row["date"],
                        csv_cell(row["description"]),
                        f"{Decimal(row['cents'])/100:.2f}",
                        row["category"],
                    ]
                )
            return Raw(output.getvalue(), "text/csv; charset=utf-8", "expenses.csv")
        match = re.fullmatch(r"/api/transactions/(\d+)", path)
        if match and method in ("PATCH", "DELETE"):
            with connect(self.path) as db:
                if method == "DELETE":
                    result = db.execute(
                        "DELETE FROM transactions WHERE id=?", (int(match[1]),)
                    )
                else:
                    if body.get("category") not in CATEGORIES:
                        raise Problem("Unknown category")
                    result = db.execute(
                        "UPDATE transactions SET category=? WHERE id=?",
                        (body["category"], int(match[1])),
                    )
                if not result.rowcount:
                    raise Problem("Transaction not found", 404)
            return {"ok": True}
        raise Problem("Not found", 404)
