from asyncio import coroutine
import asyncio
import logging

from .constants import *
from .generic_store import GenericStore
from collections import defaultdict
from .data_types import *
from .exceptions import NotFoundException


def audit_history(funct):
    def fun(self, _entity, values, *args, **kargs):
        fun_result = yield from funct(self, _entity, values, *args, **kargs)
        update_id = values.get(_entity.ID)
        db_operation = DbOperation.UPDATE if update_id else DbOperation.ADD
        _id = fun_result[_entity.ID] if db_operation == DbOperation.ADD else update_id
        comment = values.get(AuditHistory.C_COMMENT, '')
        username = values.get(AuditHistory.C_USERNAME, '')

        if db_operation == DbOperation.ADD:
            result = yield from self.store.get_entity(_entity, {_entity.ID: _id})
            result = result[0]
            self.prepare_get_response(_entity, result)
            values = result
        yield from self.store.audit_history(AuditHistory,
            AuditHistory.get_insert_values(_entity, _id, values, username, comment, db_operation))
        return fun_result

    return fun


_no_record_error_msg = 'No Record Found '

after_methods = defaultdict(dict)
before_methods = defaultdict(dict)
replace_methods = defaultdict(dict)


def after_method(_entity, api_type):
    def decor(fun):
        after_methods[_entity][api_type] = fun
    return decor


def before_method(_entity, api_type):
    def decor(fun):
        before_methods[_entity][api_type] = fun
    return decor


def replace_method(_entity, api_type):
    def decor(fun):
        replace_methods[_entity][api_type] = fun
    return decor


def run_patch(api_type):
    def decor(funct):
        def fun(self, _entity, *args, **kargs):
            before_method = before_methods[_entity].get(api_type)
            if before_method:
                yield from before_method(self, _entity, *args, **kargs)
            replace_method = replace_methods[_entity].get(api_type)
            if replace_method:
                result = yield from replace_method(self, _entity, *args, **kargs)
            else:
                result = yield from funct(self, _entity, *args, **kargs)

            after_method = after_methods[_entity].get(api_type)
            if after_method:
                result = yield from after_method(self, result, _entity, *args, **kargs)
            return result
        return fun
    return decor


class GenericManager:

    def __init__(self, store):
        super(GenericManager, self).__init__()
        self.store = store if store else GenericStore

    @run_patch(ApiTypes.CREATE)
    @audit_history
    @coroutine
    def create_entity(self, _entity: SuperBase, values: dict) -> dict:
        values = self.get_values(_entity, values)
        result = yield from self.store.create_entity(_entity, values)
        result = yield from self.get_entity_start(_entity, {_entity.ID: result[_entity.ID]})
        result = result[0]
        return result

    @run_patch(ApiTypes.UPDATE)
    @audit_history
    @coroutine
    def update_entity(self, _entity: SuperBase, values: dict):
        _id = values[_entity.ID]
        values = self.get_values(_entity, values)
        yield from self.store.update_entity(_entity, _id, values)

    @run_patch(ApiTypes.SEARCH)
    @coroutine
    def search_entity(self, _entity: SuperBase, term: str, limit: int, offset: int, where_clause=None, fields=None):
        search_result = yield from self.store.search_entity(_entity, term, limit, offset, where_clause, fields)
        return search_result

    @coroutine
    def get_entity_start(self, _entity: SuperBase, values: dict, limit=None, offset=None, fields=[]):
        self._add_default_operators(values)
        results = yield from self.get_entity_internal(_entity, values, limit=limit, offset=offset, fields=fields)
        self.validate_data_get(results)
        return results

    @staticmethod
    def _add_default_operators(values):
        for k, v in values.items():
            if isinstance(v, list):
                values[k] = ('in', tuple(v))
            else:
                values[k] = ('=', v)

    @coroutine
    def get_entity_by_id(self, _entity: SuperBase, _id: int, limit=None, offset=None):
        results = yield from self.get_entity_internal(_entity, {_entity.ID: ('=', _id)}, limit, offset)
        self.validate_data_get(results)
        return results

    @coroutine
    def get_all_entity(self, _entity: SuperBase, limit=20, offset=0, fields=[], filter: dict=None, order_by: list=None):
        if filter:
            self._add_default_operators(filter)
        results = yield from self.get_entity_internal(_entity, filter, limit=limit, offset=offset, fields=fields, order_by=order_by)
        where_clause = [filter] if filter else None
        count = yield from self.store.count(_entity.TABLE_NAME, where_clause)
        return {
            "limit": limit,
            "offset": offset,
            "count": count,
            "data": results
        }

    @run_patch(ApiTypes.GET_BASIC)
    @coroutine
    def get_entity_internal(self, _entity: SuperBase, values: dict, limit=None, offset=None, fields=[], order_by=None):
        results = yield from self.get_entity_single_query(_entity, values, limit=limit, offset=offset, fields=fields, order_by=order_by)
        return results

    @coroutine
    def get_entity_single_query(self, _entity: SuperBase, values: dict, limit=None, offset=None, fields=[], order_by=None):
        select_list, from_list, join_where_list = [], [], {}
        table_alias = self._get_psql_query_parmas(_entity, select_list, from_list, join_where_list, fields=fields)
        where_list = []
        params = []
        if values:
            for k, v in values.items():
                if v[0].upper() == 'IN' and not v[1]:
                    raise NotFoundException(_no_record_error_msg)
                where_list.append(table_alias[1] + '.' + k + ' ' + v[0] + ' ' + "%s")
                params.append(v[1])

        from_condition = ' as '.join(from_list[0])
        from_list = from_list[1:]
        for table_name_alias in from_list:
            from_condition += ' FULL OUTER JOIN ' + ' as '.join(table_name_alias) + ' on (' + join_where_list[
                table_name_alias[1]] + ')'

        where_clause = ' WHERE ' if where_list else ''
        sql = "Select {} from {} {}".format(', '.join(select_list), from_condition,
                                            where_clause + (' and '.join(where_list)))

        if order_by is not None:
            if isinstance(order_by, str):
                sql += (' ORDER BY ' + table_alias[1] + '.' + order_by)
            elif isinstance(order_by, list):
                order_by_query = ''
                for field_order in order_by:
                    order = field_order[1]
                    field = field_order[0]
                    order = order.upper() if (order and order.upper() == 'DESC') else ''
                    if order_by_query:
                        order_by_query += ', '
                    order_by_query += (table_alias[1] + '.' + field + ' ' + order)
                sql += (' ORDER BY ' + order_by_query)

        if limit is not None:
            sql += ' LIMIT %s'
            params.append(limit)
        if offset is not None:
            sql += ' OFFSET %s'
            params.append(offset)

        logging.debug(sql)
        rows = yield from self.store.raw_sql_duplicate_column(sql, params=tuple(params))

        results = []
        size = 100
        for i in range(0, len(rows), size):
            tasks = []
            for row in rows[i:i + size]:
                tasks.append(self._prepare_entity_from_result(_entity, row, select_list, fields=fields))
            results += (yield from asyncio.gather(*tasks))
        return results

    @coroutine
    def _prepare_entity_from_result(self, _entity: SuperBase, row, select_list: list, parent_table='', fields=[]):
        table_alias = parent_table + '__' + _entity.TABLE_NAME
        result = self._prepare_response_single_query(row, select_list, table_alias)
        if not result:
            return None

        self.prepare_get_response(_entity, result, fields=fields)

        tasks = []
        for field, r_foreign_entity_list in _entity.get_reverse_foreign_fields().items():
            for r_foreign_entity in r_foreign_entity_list:
                if not fields or r_foreign_entity.TABLE_NAME in fields:
                    tasks.append(self._prepare_reverse_foreign_key_data(result, r_foreign_entity, _entity, field))

        for field, foreign_entity in _entity.get_foreign_fields().items():
            if not fields or field in fields:
                tasks.append(
                    self._prepare_foreign_key_data(result, _entity, field, foreign_entity, row, select_list,
                                                   table_alias))
        yield from asyncio.gather(*tasks)

        return result

    def _prepare_reverse_foreign_key_data(self, result, r_foreign_entity, _entity, field):
        result[r_foreign_entity.TABLE_NAME] = yield from self.get_entity_single_query(r_foreign_entity, {
            field: ('=', result.get(_entity.ID))})

    def _prepare_foreign_key_data(self, result, _entity, field, foreign_entity, row, select_list, table_alias):
        if result.get(field):
            field_value = result.pop(field)
            datatype = _entity.get_datatype(field)
            if foreign_entity == SELF:
                foreign_entity = _entity
                val_ = _entity.get_field_request_value(field, field_value)[0]
                if val_:
                    res = yield from self.get_entity_single_query(foreign_entity, {
                        foreign_entity.ID: ('=', val_)})
                    res = res[0] if res else None
                    field_value = _entity.get_field_response_value(field, field_value, res)
            elif hasattr(foreign_entity, 'is_custom'):
                val_ = _entity.get_field_request_value(field, field_value)[0]
                if val_:
                    api_name = getattr(getattr(self, foreign_entity.client_name), foreign_entity.api_name)
                    args = foreign_entity.args.copy()
                    args.insert(foreign_entity.val_position, val_)
                    res = yield from api_name(*args)
                    field_value = _entity.get_field_response_value(field, field_value, res)
            elif type(datatype) == dict and [int] == _entity.get_field_request_value(field, datatype)[0]:
                val_ = _entity.get_field_request_value(field, field_value)[0]
                if val_:
                    res_list = yield from self.get_entity_single_query(foreign_entity, {foreign_entity.ID: ('in', tuple(val_))})
                    field_value = _entity.get_field_response_value(field, field_value, res_list)
            else:
                val_ = _entity.get_field_request_value(field, field_value)[0]
                if val_:
                    res = yield from self._prepare_entity_from_result(foreign_entity, row, select_list, table_alias)
                    field_value = _entity.get_field_response_value(field, field_value, res)
            result[field.replace('_' + SuperBase.ID, '')] = field_value

    def _prepare_response_single_query(self, row, select_list, table_alias):
        result = {}
        is_empty = True
        for i, field_alias in enumerate(select_list):
            if field_alias.startswith(table_alias + '.'):
                field = field_alias.split('.')[1]
                result[field] = row[i]
                if result[field] is not None:
                    is_empty = False
        if is_empty:
            result = {}
        return result

    def get_values(self, _entity, values: dict) -> dict:
        """
        get values for insert or update, including verification_status

        :param values:
        :return values dict for db{
            'name': '',
            ...
        }
        """
        insert_value = {}
        for field in _entity.get_fields():
            if field in values:
                val = values.get(field)
                val, is_exist = _entity.get_field_request_value(field, val)
                if is_exist:
                    insert_value[field] = val

        for field, fun in _entity.get_auto_db_fields().items():
            insert_value[field] = fun(_entity, values)

        return insert_value

    def prepare_get_response(self, _entity, response: dict, fields=[]):
        for key in response:
            if not fields or key in fields:
                for fun in _entity.get_condition_update_response():
                    if fun(_entity, key, response):
                        break
        for field, fun in _entity.get_auto_ui_fields().items():
            if not fields or field in fields:
                response[field] = fun(_entity, field, response)
        for key in _entity.get_non_ui_fields():
            response.pop(key, None)

    def _get_psql_query_parmas(self, _entity, select_list, from_list, where_list: dict, parent_table='', fields=[]):
        from_table_alias = (parent_table + '__' + _entity.TABLE_NAME)
        if parent_table or not fields:
            select_list += [from_table_alias + '.' + field for field in _entity.get_all_db_fields()]
        else:
            select_list += [from_table_alias + '.' + field for field in _entity.get_all_db_fields()
                            if field in fields or field in _entity.get_non_ui_fields()]

        from_entry = [_entity.TABLE_NAME, from_table_alias]
        from_list.append(from_entry)
        for field, field_entity in _entity.get_foreign_fields().items():
            if not (parent_table or not fields):
                if not (field in fields or field in _entity.get_non_ui_fields()):
                    continue
            if field_entity == SELF or hasattr(field_entity, 'is_custom'):
                continue
            datatype = _entity.get_datatype(field)
            val_datatype = _entity.get_field_request_value(field, datatype)[0]
            if val_datatype == [int] or val_datatype == [str]:
                continue
            field_table_alias = self._get_psql_query_parmas(field_entity, select_list, from_list, where_list,
                                                            from_table_alias)
            where_list[field_table_alias[1]] = from_table_alias + '.' + field + ' = ' + field_table_alias[1] + '.' + field_entity.ID
        return from_entry

    @staticmethod
    def validate_data_get(result):
        if not result or len(result) <= 0:
            raise NotFoundException(_no_record_error_msg)
        return True

