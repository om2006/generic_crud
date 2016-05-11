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

    url_regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    manager = None

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
            elif data_type == IntArrayType:
                try:
                    int_list = []
                    for val in payload[key]:
                        int_list.append(int(val))
                    payload[key] = int_list
                except ValueError:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif data_type == StrArrayType:
                try:
                    for val in payload[key]:
                        if not isinstance(val, str):
                            raise ValidationException(cls.invalid_type_error.format(error_msg))
                except ValueError:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif data_type == float:
                try:
                    payload[key] = float(payload[key])
                except ValueError:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif issubclass(data_type, EnumType):
                if payload[key] not in data_type.values:
                    raise ValidationException(cls.invalid_value_error.format(payload[key], error_msg))
            elif data_type == int:
                try:
                    payload[key] = int(payload[key])
                except:
                    raise ValidationException(cls.invalid_type_error.format(error_msg))
            elif data_type == UrlType:
                if not cls.url_regex.findall(payload[key]):
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

        values[_entity.VERIFICATION_STATUS] = response.get(_entity.VERIFICATION_STATUS)

    @classmethod
    def create_entity(cls, _entity: SuperBase, values: dict):
        """
        validate consume type payload for creating

        :param values: dict
            Example: {'name':{'value': '' , 'validation_status': 1}, ... }
        :param username
        :raise ValidationError
        """
        mandatory_fields = _entity.C_mandatory_fields + _entity.B_mandatory_fields
        # if _entity == Products:
        #     yield from cls._product_name_formula_patch(values)
        yield from cls.common_validate(_entity, values, mandatory_fields)

    @classmethod
    def common_validate(cls, _entity: SuperBase, values: dict, mandatory_fields=[], fields=[]):
        _id = values.get(_entity.ID)

        for field in mandatory_fields:
            cls._is_exist(values, field)

        fields += _entity.C_fields + _entity.B_fields

        for field in fields:
            if field in values:
                data_type = _entity.get_datatype(field)
                cls._is_empty(values, field)
                cls._data_type(values, field, data_type)

        for field, len_limit in _entity.get_fields_len_limit():
            if field in values:
                cls._check_length(_entity, values, field, len_limit)

        for fields in (_entity.B_no_duplicate_fields + _entity.C_no_duplicate_fields):
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

        for foreign_field, field_entity in _entity.get_foreign_fields():
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
