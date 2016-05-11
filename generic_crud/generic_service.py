import logging

from vyked import TCPService as tc, api
from again.decorate import silence_coroutine
from psycopg2 import IntegrityError

from .utils import tcp_exception_handler
from .generic_validation import GenericValidation
from .generic_manager import GenericManager
from .exceptions import ValidationException, NotFoundException
from .constants import SuperBase

logger = logging.getLogger()
_exceptions = [ValidationException, NotFoundException, IntegrityError]

manager = None


class GenericTCPService(tc):
    def __init__(self, _name, _version, host, port, ext_manager):
        super(GenericTCPService, self).__init__(_name, _version, host, port)
        global manager
        manager = ext_manager if ext_manager else GenericManager()
        GenericValidation.init_class(manager)
        self.generate_apis()

    def generate_apis(self):
        for entity in SuperBase.ENTITIES:
            apis = apis_generator(entity.API_NAME, entity)
            for api_name, method in apis.items():
                setattr(GenericTCPService, api_name, method)


def apis_generator(api_suffix, _entity: SuperBase):
    def get_api_name(prefix, api_suffix):
        return prefix + '_' + api_suffix

    def prepare_api(api_name, funct, apis):
        funct.__name__ = api_name
        apis[api_name] = funct

    apis = {}

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def create_entity(self, values: dict, username: str) -> dict:
        values[_entity.USERNAME] = username
        yield from GenericValidation.create_entity(_entity, values)
        result = yield from manager.create_entity(_entity, values)
        return result

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def update_entity(self, values: dict, username: str):
        values[_entity.USERNAME] = username
        yield from GenericValidation.update_entity(_entity, values)
        yield from manager.update_entity(_entity, values)

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def get_entity(self, values: dict, fields=[]):
        response = (yield from manager.get_entity_start(_entity, values, fields=fields))
        return response

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def search_entity(self, term: str, fields: list=None, limit: int=20, offset: int=0):
        return (yield from manager.search_entity(_entity, term, fields=fields, limit=limit, offset=offset))

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def get_all_entity(self, fields: list=None, limit: int=20, offset: int=0):
        return (yield from manager.get_all_entity(_entity, fields=fields, limit=limit, offset=offset))

    prepare_api(get_api_name('create', api_suffix), create_entity, apis)
    prepare_api(get_api_name('update', api_suffix), update_entity, apis)
    prepare_api(get_api_name('get', api_suffix), get_entity, apis)
    prepare_api(get_api_name('search', api_suffix), search_entity, apis)
    prepare_api(get_api_name('get_all', api_suffix), get_all_entity, apis)

    return apis




