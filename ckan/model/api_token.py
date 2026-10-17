from __future__ import annotations

import copy
import datetime
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import types, Column, Table, ForeignKey, orm
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from typing_extensions import Self

from ckan.model import meta, User, DomainObject
from ckan.common import config

__all__ = ["ApiToken", "api_token_table"]

Mapped = orm.Mapped


def _make_token() -> str:
    nbytes = config.get("api_token.nbytes")
    return token_urlsafe(nbytes)


api_token_table = Table(
    "api_token",
    meta.metadata,
    Column("id", types.UnicodeText, primary_key=True, default=_make_token),
    Column("name", types.UnicodeText),
    Column("user_id", types.UnicodeText, ForeignKey("user.id")),
    Column("created_at", types.DateTime, default=datetime.datetime.utcnow),
    Column("last_access", types.DateTime, nullable=True),
    Column("plugin_extras", MutableDict.as_mutable(JSONB)),
)


class ApiToken(DomainObject):
    id: Mapped[str]
    name: Mapped[str]
    user_id: Mapped[str | None]
    created_at: Mapped[datetime.datetime]
    last_access: Mapped[datetime.datetime | None]
    plugin_extras: Mapped[dict[str, Any]]
    owner: Mapped[User | None]

    def __init__(
            self, user_id: str | None = None,
            name: str = 'Unnamed') -> None:
        self.id = _make_token()
        self.user_id = user_id
        self.name = name

    @classmethod
    def get(cls, id: str | None) -> Self | None:
        if not id:
            return None

        return meta.Session.get(cls, id)

    @classmethod
    def revoke(cls, id: str | None) -> bool:
        token = cls.get(id)
        if token:
            meta.Session.delete(token)
            meta.Session.commit()
            return True
        return False

    def touch(self, commit: bool = False) -> None:
        self.last_access = datetime.datetime.utcnow()
        if commit:
            meta.Session.commit()

    def set_extra(self, key: str, value: Any, commit: bool = False) -> None:
        extras = self.plugin_extras or {}
        extras[key] = value
        self.plugin_extras = copy.deepcopy(extras)
        if commit:
            meta.Session.commit()


meta.registry.map_imperatively(
    ApiToken,
    api_token_table,
    properties={
        "owner": orm.relationship(
            User, backref=orm.backref("api_tokens",
                                      cascade="all, delete")
        )
    },
)
