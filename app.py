from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


# supports both demo snake_case and typical export headers
COLUMN_ALIASES = {
    "first_name": ["first_name", "First Name", "First", "Fname", "Supporter First Name"],
    "last_name": ["last_name", "Last Name", "Last", "Lname", "Supporter Last Name"],
    "email": ["email", "Email", "Email Address", "Supporter Email"],
    "phone": ["phone", "Phone", "Phone Number", "Mobile", "Supporter Phone"],
    "event_name": ["event_name", "Event Name"],
    "activity_type": ["activity_type", "Activity Type"],
    "activity_date": ["activity_date", "Activity Date", "Event Date", "Payment Date"],
    "payment_status": ["payment_status", "Payment Status", "Status"],
    "proceeds_amount": ["proceeds_amount", "Proceeds Amount", "Amount", "Total"],
}


def norm_email(v: Any) -> str:
    return str(v).strip().lower() if v else ""


def norm_phone_key(v: Any) -> str:
    if not v:
        return ""
    return "".join(ch for ch in str(v) if ch.isdigit())


def norm_name(v: Any) -> str:
    return str(v).strip().lower() if v else ""


def _pick(row: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        if k in row and pd.notna(row[k]):
            return str(row[k]).strip()
    return ""


@dataclass
class Record:
    source_file: str
    row_num: int

    first_name: str
    last_name: str
    full_name: str

    email: str
    phone: str

    event_name: str
    activity_type: str
    activity_date: str
    payment_status: str
    proceeds_amount: str

    raw: Dict[str, Any]


def load_records(data_dir: Path) -> List[Record]:
    records: List[Record] = []

    for path in data_dir.glob("*"):
        if path.suffix.lower() not in (".csv", ".xlsx"):
            continue

        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        for idx, row in df.iterrows():
            row_dict = row.to_dict()

            first = _pick(row_dict, COLUMN_ALIASES["first_name"])
            last = _pick(row_dict, COLUMN_ALIASES["last_name"])

            records.append(
                Record(
                    source_file=path.name,
                    row_num=int(idx) + 1,

                    first_name=first,
                    last_name=last,
                    full_name=f"{first} {last}".strip(),

                    email=_pick(row_dict, COLUMN_ALIASES["email"]),
                    phone=_pick(row_dict, COLUMN_ALIASES["phone"]),

                    event_name=_pick(row_dict, COLUMN_ALIASES["event_name"]),
                    activity_type=_pick(row_dict, COLUMN_ALIASES["activity_type"]),
                    activity_date=_pick(row_dict, COLUMN_ALIASES["activity_date"]),
                    payment_status=_pick(row_dict, COLUMN_ALIASES["payment_status"]),
                    proceeds_amount=_pick(row_dict, COLUMN_ALIASES["proceeds_amount"]),

                    raw=row_dict,
                )
            )

    return records