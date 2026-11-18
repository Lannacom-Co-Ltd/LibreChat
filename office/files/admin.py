"""Administrator tools on LibreChat's own database: usage report and token credits.

LibreChat reaches these tools through a second MCP entry, office-admin, whose headers carry
X-AIHub-Scope: admin and the signed-in user's id and role (X-User-Id: '{{LIBRECHAT_USER_ID}}',
X-User-Role: '{{LIBRECHAT_USER_ROLE}}'). The user placeholders make that entry per-user, which
is why it is kept apart from office-files: a per-user entry is not loaded for every chat. The
MCP endpoint is guarded by the shared API key, so only LibreChat can set these headers, and
every call refuses anyone who is not an administrator.

Credits are LibreChat's token credits: 1,000,000 credits = 1 USD.
"""

import io
import os
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "")
ADMIN_ROLE = "ADMIN"
CREDITS_PER_USD = 1_000_000
MAX_CREDITS = 1_000_000_000_000
HEADER_FILL = PatternFill("solid", fgColor="1F1E1D")
HEADER_FONT = Font(bold=True, color="FFFFFF")

_client: MongoClient | None = None


def db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=True)
    return _client.get_default_database()


def require_admin(headers: dict[str, str]) -> str:
    """The caller's user id, or a refusal for anyone who is not an administrator."""
    if (headers.get("x-user-role") or "").upper() != ADMIN_ROLE:
        raise PermissionError("only administrators can use this tool")
    return headers.get("x-user-id") or "unknown"


def is_admin(headers: dict[str, str]) -> bool:
    return (headers.get("x-user-role") or "").upper() == ADMIN_ROLE


def usd(credits: float) -> float:
    return round(credits / CREDITS_PER_USD, 4)


def find_user(email: str) -> dict:
    user = db().users.find_one({"email": email.strip().lower()}, {"email": 1, "name": 1})
    if not user:
        raise ValueError(f"no user with email {email}")
    return user


def sheet(book: Workbook, title: str, header: list[str], rows: list[list]) -> None:
    ws = book.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for row in rows:
        ws.append(row)
    for i, name in enumerate(header, 1):
        longest = max([len(str(name))] + [len(str(r[i - 1])) for r in rows[:500]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 48)
    ws.freeze_panes = "A2"


def usage_workbook(days: int) -> tuple[bytes, str]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    d = db()
    users = {u["_id"]: u for u in d.users.find({}, {"email": 1, "name": 1})}
    spend = list(d.transactions.aggregate([
        {"$match": {"createdAt": {"$gte": since}, "tokenType": {"$in": ["prompt", "completion"]}}},
        {"$group": {
            "_id": {"user": "$user", "model": "$model", "type": "$tokenType",
                    "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}}},
            "tokens": {"$sum": {"$abs": "$rawAmount"}},
            "credits": {"$sum": {"$abs": "$tokenValue"}},
        }},
    ]))
    messages = {
        row["_id"]: row
        for row in d.messages.aggregate([
            {"$match": {"createdAt": {"$gte": since}, "isCreatedByUser": True}},
            {"$group": {"_id": "$user", "messages": {"$sum": 1}, "chats": {"$addToSet": "$conversationId"}}},
        ])
    }

    by_user, by_model, by_day = {}, {}, {}
    for row in spend:
        key = row["_id"]
        prompt = row["tokens"] if key["type"] == "prompt" else 0
        completion = row["tokens"] if key["type"] == "completion" else 0
        for table, k in ((by_user, key["user"]), (by_model, key.get("model") or "-"), (by_day, key["day"])):
            entry = table.setdefault(k, [0, 0, 0.0])
            entry[0] += prompt
            entry[1] += completion
            entry[2] += row["credits"]

    def who(user_id) -> tuple[str, str]:
        user = users.get(user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))) if user_id else None
        return (user or {}).get("email", str(user_id)), (user or {}).get("name", "")

    user_ids = set(by_user) | {ObjectId(u) for u in messages if ObjectId.is_valid(str(u))}
    user_rows = []
    for user_id in user_ids:
        prompt, completion, credits = by_user.get(user_id, [0, 0, 0.0])
        activity = messages.get(str(user_id), {})
        email, name = who(user_id)
        user_rows.append([email, name, activity.get("messages", 0), len(activity.get("chats", [])),
                          prompt, completion, prompt + completion, usd(credits)])
    user_rows.sort(key=lambda r: r[-1], reverse=True)
    model_rows = sorted(([m, p, c, p + c, usd(v)] for m, (p, c, v) in by_model.items()), key=lambda r: r[-1], reverse=True)
    day_rows = sorted([d_, p, c, p + c, usd(v)] for d_, (p, c, v) in by_day.items())

    book = Workbook()
    book.remove(book.active)
    tokens = ["Prompt tokens", "Completion tokens", "Total tokens", "Cost (USD)"]
    sheet(book, "By user", ["Email", "Name", "Messages sent", "Chats", *tokens], user_rows)
    sheet(book, "By model", ["Model", *tokens], model_rows)
    sheet(book, "By day", ["Date (UTC)", *tokens], day_rows)
    out = io.BytesIO()
    book.save(out)
    total = sum(r[-1] for r in user_rows)
    summary = (
        f"Last {days} days: {len(user_rows)} active users, "
        f"{sum(r[2] for r in user_rows)} messages, cost {total:.2f} USD."
    )
    return out.getvalue(), summary


def balances(limit: int = 30) -> tuple[bytes, str]:
    d = db()
    users = {u["_id"]: u for u in d.users.find({}, {"email": 1, "name": 1})}
    rows = []
    for bal in d.balances.find({}):
        user = users.get(bal.get("user"), {})
        credits = round(bal.get("tokenCredits", 0))
        last = bal.get("lastRefill")
        rows.append([user.get("email", str(bal.get("user"))), user.get("name", ""), credits, usd(credits),
                     last.strftime("%Y-%m-%d %H:%M") if last else ""])
    rows.sort(key=lambda r: r[2])
    book = Workbook()
    book.remove(book.active)
    sheet(book, "Credits", ["Email", "Name", "Credits", "USD", "Last refill (UTC)"], rows)
    out = io.BytesIO()
    book.save(out)
    lines = [f"{len(rows)} users have a credit balance (lowest first):"]
    lines += [f"- {r[0]}: {r[2]:,} credits ({r[3]} USD)" for r in rows[:limit]]
    if len(rows) > limit:
        lines.append(f"... and {len(rows) - limit} more in the file")
    return out.getvalue(), "\n".join(lines)


def change_credits(action: str, email: str, credits: int, admin_id: str) -> str:
    if credits < 0 or credits > MAX_CREDITS:
        raise ValueError(f"credits must be between 0 and {MAX_CREDITS:,}")
    if action == "add" and credits == 0:
        raise ValueError("credits to add must be more than 0")
    user = find_user(email)
    d = db()
    now = datetime.now(timezone.utc)
    current = round((d.balances.find_one({"user": user["_id"]}) or {}).get("tokenCredits", 0))
    change = credits if action == "add" else credits - current
    d.balances.update_one(
        {"user": user["_id"]},
        {"$inc": {"tokenCredits": change}} if action == "add" else {"$set": {"tokenCredits": credits}},
        upsert=True,
    )
    d.transactions.insert_one({
        "user": user["_id"], "tokenType": "credits", "context": "admin", "rawAmount": change,
        "tokenValue": change, "rate": 1, "createdAt": now, "updatedAt": now,
    })
    after = current + change
    print(f"admin {admin_id} {action} credits for {user['email']}: {current} -> {after}", flush=True)
    return f"{user['email']}: {current:,} -> {after:,} credits ({usd(after)} USD)."
