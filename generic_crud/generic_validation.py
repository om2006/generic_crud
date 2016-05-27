import logging
import re

from .constants import *
from .exceptions import *
from .data_types import *
from .generic_store import GenericStore
from .generic_manager import GenericManager

logger = logging.getLogger()


class GenericValidation:
    required_error = "'{}' is required field"
    invalid_type_error = "invalid data type of '{}'"
    empty_error = "'{}' can not be empty"
    number_error = "'{}' must be a valid number"
    not_found_error = "'{}={}' not found"
    invalid_data_error = "'{}' is invalid"
    max_length_error = "'{}' length cannot be more than {}"
    duplicate_error = "'{}' is duplicate"
    foreign_key_error = "'{}' foreign key not found"
    invalid_url_error = "invalid data type of '{}'"
    invalid_value_error = "invalid value '{}' of '{}'"
    self_is_self_error = "'{}' foreign key cannot be self"
    dependent_fields_error = "'{}' are dependent. '{}' {} required"

    url_regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    manager = None

    @classmethod
    def get_all_fields(cls, get_param):
        """
        validate search query parameter

        :param get_param: dict
            Example: {'query': 'XXX', 'limit': 10}

        :raise: ValidationError
        :return: name, url
        """
        limit = get_param.get('limit', 20)
        try:
            limit = int(limit)
        except ValueError:
            raise ValidationException(cls.number_error.format('limit'))

        offset = get_param.get('offset', 0)
        try:
            offset = int(offset)
        except ValueError:
            raise ValidationException(cls.number_error.format('offset'))

        return limit, offset, cls._get_fields(get_param), cls._get_filter(get_param), cls._get_order_by(get_param)

    @classmethod
    def _get_fields(cls, get_param):
        try:
            fields = get_param.get('fields', None)
            fields = fields.split(',') if fields else None
        except:
            raise ValidationException(cls.invalid_data_error.format('fields'))
        return fields

    @classmethod
    def _get_filter(cls, get_param):
        try:
            filter = get_param.get('filter', None)
            fields = {key_val.split(':', 1)[0]: key_val.split(':', 1)[1] for key_val in filter.split(',')} if filter else None
        except:
            raise ValidationException(cls.invalid_data_error.format('filter'))
        return fields

    @classmethod
    def _get_order_by(cls, get_param):
        try:
            order_by = get_param.get('order_by', None)
            order_by = [(key_val.split(':', 1)[0], (key_val.split(':', 1)[1] if len(key_val.split(':', 1)) > 1 else None)) for key_val in order_by.split(',')] if order_by else None
        except:
            raise ValidationException(cls.invalid_data_error.format('order_by'))
        return order_by

    @classmethod
    def search_fields(cls, get_param):
        """
        validate search query parameter

        :param get_param: dict
            Example: {'query': 'XXX', 'limit': 10}

        :raise: ValidationError
        :return: name, url
        """
        if 'query' not in get_param:
            raise ValidationException(cls.required_error.format('query'))
        query = get_param['query']
        if query == '':
            raise ValidationException(cls.empty_error.format('query'))
        limit = get_param.get('limit', 10)
        try:
            limit = int(limit)
        except ValueError:
            raise ValidationException(cls.number_error.format('limit'))

        return query, limit

    @classmethod
    def init_class(cls, manager = None):
        cls.manager = manager if manager else GenericManager()

    @classmethod
    def _data_type(cls, payload: dict, key: str, data_type: type, error_msg: str=None):
        error_msg = error_msg if error_msg else key
        if key in payload:
            if payload[key] == None:
                pass
            elif type(data_type) == dict:
                for k, v in data_type.items():
                    if type(v) == type:
                        cls._data_type(payload[key], k, v, error_msg + '_' + k)
            elif type(data_type) == list:
                try:
                    v_list = []
                    for val in payload[key]:
                        v_list.append(data_type[0](val))
                    payload[key] = v_list
                except ValueError:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif issubclass(data_type, EnumType):
                if payload[key] not in data_type.values:
                    raise ValidationException(cls.invalid_value_error.format(payload[key], error_msg))
            elif data_type == UrlType:
                if not cls.url_regex.findall(payload[key]):
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif data_type == float or data_type == int:
                try:
                    payload[key] = data_type(payload[key])
                except ValueError:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            else:
                if not isinstance(payload[key], data_type):
                    raise ValidationException(cls.invalid_type_error.format(error_msg))

    @classmethod
    def _is_empty(cls, payload: dict, key: str, error_msg: str=None):
        error_msg = error_msg if error_msg else key
        val = payload.get(key)
        # if type(val) in [bool, int]:
        #     if payload.get(key) is None:
        #         raise ValidationException(cls.empty_error.format(error_msg))
        # elif not payload.get(key):
        #     raise ValidationException(cls.empty_error.format(error_msg))

    @classmethod
    def _is_exist(cls, payload: dict, key: str, error_msg: str=None):
        error_msg = error_msg if error_msg else key
        if key not in payload:
            raise ValidationException(cls.required_error.format(error_msg))

    @classmethod
    def _check_length(cls, _entity, payload: dict, key: str, max_length: int):
        val = _entity.get_field_request_value(key, payload.get(key))
        if len(val) > max_length:
            raise ValidationException(cls.max_length_error.format(key, max_length))

    @classmethod
    def update_entity(cls, _entity: SuperBase, values: dict):
        """
        validate consume type payload for updating

        :param values: dict
            Example: {'name': {'value': '' , 'validation_status': 1},... }
        :param username
        :raise ValidationError

        """

        _id = values.get(_entity.ID)
        response = yield from GenericStore.get_entity(_entity, {_entity.ID: _id})
        if not response:
            raise ValidationException(cls.not_found_error.format(_entity.ID, _id))
        response = response[0]
        # if _entity == Products:
        #     for key, val in values.items():
        #         if key in response:
        #             if type(val) == dict:
        #                 response[key] = {VALUE: val.get(VALUE)}
        #             else:
        #                 response[key] = val
        #     yield from cls._product_name_formula_patch(response)
        #     values[Products.C_NAME] = response.get(Products.C_NAME)

        yield from cls.common_validate(_entity, values, mandatory_fields=[_entity.ID], fields=[_entity.ID])

        for field, fun in _entity.get_auto_db_fields().items():
            values[field] = response.get(field)

    @classmethod
    def create_entity(cls, _entity: SuperBase, values: dict):
        """
        validate consume type payload for creating

        :param values: dict
            Example: {'name':{'value': '' , 'validation_status': 1}, ... }
        :param username
        :raise ValidationError
        """
        mandatory_fields = _entity.get_mandatory_fields()
        # if _entity == Products:
        #     yield from cls._product_name_formula_patch(values)
        yield from cls.common_validate(_entity, values, mandatory_fields.copy())

    @classmethod
    def common_validate(cls, _entity: SuperBase, values: dict, mandatory_fields=[], fields=None):
        _id = values.get(_entity.ID)

        for field in mandatory_fields:
            cls._is_exist(values, field)

        fields = [] if fields is None else fields
        fields += _entity.get_fields()
        for field in fields:
            if field in values:
                data_type = _entity.get_datatype(field)
                cls._is_empty(values, field)
                cls._data_type(values, field, data_type)

        for field, len_limit in _entity.get_fields_len_limit().items():
            if field in values:
                cls._check_length(_entity, values, field, len_limit)

        for dep_fields in _entity.get_dependent_fields():
            req_fields = []
            for field in dep_fields:
                if isinstance(field, tuple):
                    val = values.get(field[0])
                    val = _entity.get_field_request_value(field[0], val)[0]
                    if val != field[1]:
                        req_fields.append(field)
                elif field not in values:
                    req_fields.append(field)
            if 0 < len(req_fields) < len(dep_fields):
                dep_fields_msg = [(str(field[0]) + '=' + str(field[1])) if isinstance(field, tuple) else field for field in dep_fields]
                req_fields_msg = [(str(field[0]) + '=' + str(field[1])) if isinstance(field, tuple) else field for field in req_fields]
                is_or_are = 'is' if len(req_fields_msg) == 1 else 'are'
                raise ValidationException(cls.dependent_fields_error.format(', '.join(dep_fields_msg), ', '.join(req_fields_msg), is_or_are))

        for fields in _entity.get_no_duplicate_fields():
            if type(fields) != list:
                fields = [fields]
            where_condition = {}
            for field in fields:
                if field in values:
                    val = values.get(field)
                    where_condition[field] = _entity.get_field_request_value(field, val)[0]
            if where_condition and len(where_condition) == len(fields):
                response = yield from GenericStore.get_entity(_entity, where_condition)
                if response:
                    raise ValidationException(cls.duplicate_error.format(
                        ', '.join([field + '=' + str(where_condition.get(field)[1]) for field in fields])))

        for foreign_field, field_entity in _entity.get_foreign_fields().items():
            if field_entity == SELF:
                field_entity = _entity

            if foreign_field in values:
                val = values.get(foreign_field)
                val = _entity.get_field_request_value(foreign_field, val)[0]
                if type(val) != list:
                    val = [val]
                for v in val:
                    if v is not None:
                        if field_entity == _entity and v == _id:
                            raise ValidationException(cls.self_is_self_error.format(foreign_field))
                        response = None
                        if hasattr(field_entity, 'is_custom'):
                            api_name = getattr(getattr(cls.manager, field_entity.client_name), field_entity.api_name)
                            args = field_entity.args.copy()
                            args.insert(field_entity.val_position, v)
                            response = yield from api_name(*args)
                        else:
                            response = yield from GenericStore.get_entity(field_entity, {field_entity.ID: v})
                        if not response:
                            raise ValidationException(cls.foreign_key_error.format(foreign_field))
