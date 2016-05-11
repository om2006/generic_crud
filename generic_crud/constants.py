from itertools import chain


class SELF:
    pass


class DbOperation:
    ADD = 'add'
    UPDATE = 'update'
    REMOVE = 'remove'


class SuperBase:
    ID = 'id'

    API_NAME = ''
    TABLE_NAME = ''

    B_fields = []  # fields which comes from UI and stores to table
    C_fields = []  # fields which comes from UI and stores to table
    B_mandatory_fields = []
    C_mandatory_fields = []
    B_fields_len_limit = {}
    C_fields_len_limit = {}
    B_no_duplicate_fields = []
    C_no_duplicate_fields = []
    B_fields_datatype = {}
    C_fields_datatype = {}
    B_foreign_fields = {}
    C_foreign_fields = {}
    B_reverse_foreign_fields = {}
    C_reverse_foreign_fields = {}
    B_auto_db_fields = {}
    C_auto_db_fields = {}
    B_db_fields = []
    C_db_fields = []
    B_condition_update_response = []
    C_condition_update_response = []
    B_key_params = {}
    C_key_params = {}
    B_non_ui_fields = []
    C_non_ui_fields = []
    B_auto_ui_fields = {}
    C_auto_ui_fields = {}

    ENTITIES = []
    a = []

    @classmethod
    def set_entities(cls, entities):
        cls.ENTITIES.clear()
        cls.ENTITIES.extend(entities)

    @classmethod
    def get_all_db_fields(cls):
        return ((
            cls.B_fields + list(cls.B_auto_db_fields.keys()) + cls.B_db_fields)
                + (cls.C_fields + list(cls.C_auto_db_fields.keys()) + cls.C_db_fields))

    @classmethod
    def get_non_ui_fields(cls):
        return cls.B_non_ui_fields + cls.C_non_ui_fields

    @classmethod
    def get_reverse_foreign_fields(cls):
        return chain(cls.B_reverse_foreign_fields.items(), cls.C_reverse_foreign_fields.items())

    @classmethod
    def get_reverse_foreign_fields(cls):
        return chain(cls.B_reverse_foreign_fields.items(), cls.C_reverse_foreign_fields.items())

    @classmethod
    def get_foreign_fields(cls):
        return chain( cls.B_foreign_fields.items(), cls.C_foreign_fields.items())

    @classmethod
    def get_auto_ui_fields(cls):
        return chain(cls.B_auto_ui_fields.items(), cls.C_auto_ui_fields.items())

    @classmethod
    def get_fields_len_limit(cls):
        return chain(cls.B_fields_len_limit.items(), cls.C_fields_len_limit.items())

    @classmethod
    def get_search_field(cls):
        search_field = cls.SEARCH_COLUMN
        if not search_field:
            search_field = cls.C_NAME

        return search_field

    @classmethod
    def get_datatype(cls, field):
        type = cls.C_fields_datatype.get(field)
        if type:
            return type
        type = cls.B_fields_datatype.get(field)
        if type:
            return type
        else:
            return cls.default_datatype

    @classmethod
    def get_field_response_value(cls, field, field_var, field_response):
        return field_response

    @classmethod
    def get_field_request_value(cls, field, field_request):
        return field_request, True

    @classmethod
    def get_key_params(cls, field):
        params = cls.C_key_params.get(field)
        if params:
            return params
        params = cls.B_key_params.get(field)
        if params:
            return params
        else:
            return None

    @classmethod
    def should_log_field(cls, field):
        return True


class AuditHistory(SuperBase):
    TABLE_NAME = 'audit_history'
    API_NAME = TABLE_NAME

    ID = 'id'
    C_ENTITY = 'entity'
    C_ENTITY_ID = 'entity_id'
    C_ATTRIBUTE = 'attribute'
    C_VALUE = 'value'
    C_SOURCE = 'data_source'
    C_SOURCE_ID = 'data_source_attribute_id'
    C_COMMENT = 'comment'
    C_DB_OPERATION = 'db_operation'
    C_USERNAME = 'username'

    C_fields = [C_ENTITY, C_ENTITY_ID, C_ATTRIBUTE, C_VALUE, C_SOURCE, C_SOURCE_ID, C_COMMENT, C_USERNAME]

    C_mandatory_fields = [C_ENTITY, C_ENTITY_ID]

    C_fields_datatype = {
        C_ENTITY: str,
        C_ENTITY_ID: str,
        C_ATTRIBUTE: str,
        C_VALUE: str,
        C_SOURCE: str,
        C_SOURCE_ID: str,
        C_COMMENT: str,
        C_USERNAME: str
    }

    C_fields_len_limit = {
        C_ENTITY: 50,
        C_ENTITY_ID: 200,
        C_ATTRIBUTE: 100,
        C_SOURCE: 100,
        C_USERNAME: 200
    }

    @classmethod
    def get_insert_values(cls, _entity: SuperBase, _id: int, values: dict, username: str, comment: str='',
                          db_operation=DbOperation.UPDATE) -> dict:
        source = values.pop(_entity.SOURCE, None)
        source = _entity.get_field_request_value(_entity.SOURCE, source)[0]

        source_id = values.pop(_entity.C_SOURCE_ID, None)
        source_id = _entity.get_field_request_value(_entity.C_SOURCE_ID, source_id)[0]

        common_value = {
            cls.C_ENTITY: _entity.TABLE_NAME,
            cls.C_ENTITY_ID: str(_id),
            cls.C_USERNAME: username,
            cls.C_SOURCE: source,
            cls.C_SOURCE_ID: source_id,
            cls.C_COMMENT: comment,
            cls.C_DB_OPERATION: db_operation
        }

        value_list = []
        for key, value in values.items():
            datatype = _entity.get_datatype(key)
            if _entity.should_log_field(key):
                if type(datatype) == dict:
                    for sub_key, value in datatype.items():
                        history_value_status = common_value.copy()
                        history_value_status.update({
                            cls.C_ATTRIBUTE: key + '_' + sub_key,
                            cls.C_VALUE: str(value) if value else None
                        })
                        value_list.append(history_value_status)
                else:
                    history_value_status = common_value.copy()
                    history_value_status.update({
                        cls.C_ATTRIBUTE: key,
                        cls.C_VALUE: str(value) if value else None
                    })
                    value_list.append(history_value_status)
        return value_list
