"""Account names are unique (ignoring case and extra spaces), so every path that would
create an account (new deal form, sample data, LMDA link) reuses or refuses instead of
adding a look-alike."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Account


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def find_account(db: Session, name: str, *, exclude_id: int | None = None) -> Account | None:
    key = name_key(name)
    return next((a for a in db.query(Account).order_by(Account.id) if a.id != exclude_id and name_key(a.name) == key),
                None)
