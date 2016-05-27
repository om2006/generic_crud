from asyncio import coroutine
import asyncio

from cauldron import PostgresStore
from cauldron.sql import cursor

from .constants import SuperBase

_BULK_INSERT_SQL = "INSERT INTO {}({}) VALUES ({})"


class GenericStore(PostgresStore):
    @classmethod
    @coroutine
    def create_entity(cls, _entity, value: dict) -> dict:
        row = yield from cls.insert(table=_entity.TABLE_NAME, values=value)
        if row:
            row = dict(vars(row))
        return row

    @classmethod
    @coroutine
    def get_entity(cls, _entity: SuperBase, where_key_val: dict) -> dict:
        for key, val in where_key_val.items():
            where_key_val[key] = ('=', val)
        rows = yield from cls.select(table=_entity.TABLE_NAME, order_by=_entity.ID + ' desc',
                                     where_keys=[where_key_val])
        if rows:
            rows = [dict(vars(row)) for row in rows]
        return rows

    @classmethod
    @coroutine
    def update_entity(cls, _entity: SuperBase, _id: str, value: dict) -> dict:
        row = yield from cls.update(table=_entity.TABLE_NAME, values=value,
                                    where_keys=[{_entity.ID: ('=', _id)}])
        result = None
        if row:
            result = dict(vars(row[0]))
        return result

    @classmethod
    @coroutine
    def search_entity(cls, _entity: SuperBase, term: str, limit: int, offset: int, where_clause=None, fields: list=None):
        fields = fields if fields else None

        search_column = _entity.get_search_field()
        if not search_column:
            return None

        where_keys = where_clause if where_clause else {}
        if term:
            where_keys[search_column] = ('ilike', term + '%')
        where_keys = [where_keys] if where_keys else None

        rows = yield from cls.select(table=_entity.TABLE_NAME, columns=fields, order_by=search_column,
                                     where_keys=where_keys, limit=limit, offset=offset)

        rows = [dict(vars(row)) for row in rows]
        return rows

    @classmethod
    @cursor
    @coroutine
    def audit_history(cls, cur, _entity, values: list) -> dict:
        _tasks = []
        for value in values:
            _tasks.append(cls.create_entity(_entity, value))
        yield from asyncio.gather(*_tasks)

    @classmethod
    @cursor
    @coroutine
    def raw_sql_duplicate_column(cls, cur, sql: str, params: tuple=tuple()) -> dict:
        yield from cur.execute(sql, params)
        return [row for row in cur]

