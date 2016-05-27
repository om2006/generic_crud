import logging

from aiohttp.web import Request, Response
from asyncio import coroutine
from vyked import TCPService as tc, HTTPService, api, post, get, put
from again.decorate import silence_coroutine
from psycopg2 import IntegrityError

from .utils import tcp_exception_handler, HTTPStatusCodes, json_response, http_error_handler
from .generic_validation import GenericValidation
from .generic_manager import GenericManager
from .exceptions import ValidationException, NotFoundException
from .constants import SuperBase, ApiTypes

logger = logging.getLogger()
_exceptions = [ValidationException, NotFoundException, IntegrityError]

manager = None


class GenericTCPService(tc):
    def __init__(self, _name, _version, host, port, ext_manager: GenericManager):
        super(GenericTCPService, self).__init__(_name, _version, host, port)
        global manager
        manager = ext_manager if ext_manager else GenericManager(None)
        GenericValidation.init_class(manager)
        self.generate_apis()

    def generate_apis(self):
        for entity in SuperBase.ENTITIES:
            apis = apis_generator(entity.API_NAME, entity)
            for api_name, method in apis.items():
                setattr(GenericTCPService, api_name, method)


class GenericHTTPService(HTTPService):
    def __init__(self, _name, _version, host, port, ext_manager: GenericManager):
        super(GenericHTTPService, self).__init__(_name, _version, host, port)
        global manager
        manager = ext_manager if ext_manager else GenericManager(None)
        GenericValidation.init_class(manager)
        self.generate_apis()

    def generate_apis(self):
        for entity in SuperBase.ENTITIES:
            apis = http_apis_generator(entity.API_NAME, entity)
            for api_name, method in apis.items():
                setattr(GenericHTTPService, api_name, method)
                self.__ordered__.append(api_name)


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
    def search_entity(self, term: str, limit: int=20, offset: int=0, filter: dict=None, fields: list=None):
        filter = {k: ('=', v) for k,v in filter.items()} if filter is not None else None
        return (yield from manager.search_entity(_entity, term, limit=limit, offset=offset, where_clause=filter, fields=fields))

    @api
    @silence_coroutine(_exceptions, tcp_exception_handler)
    def get_all_entity(self, fields: list=None, limit: int=20, offset: int=0, filter: dict=None, order_by: dict=None):
        return (yield from manager.get_all_entity(_entity, fields=fields, limit=limit, offset=offset, filter=filter, order_by=order_by))

    prepare_api(get_api_name('create', api_suffix), create_entity, apis)
    prepare_api(get_api_name('update', api_suffix), update_entity, apis)
    prepare_api(get_api_name('get', api_suffix), get_entity, apis)
    prepare_api(get_api_name('search', api_suffix), search_entity, apis)
    prepare_api(get_api_name('get_all', api_suffix), get_all_entity, apis)

    return apis


update_success_message = {
    "message": "Updated Successfully"
}


def http_apis_generator(api_suffix, _entity: SuperBase):
    def get_api_name(prefix, api_suffix):
        return prefix + '_' + api_suffix

    def prepare_api(api_name, funct, apis):
        funct.__name__ = api_name
        apis[api_name] = funct

    apis = {}

    @silence_coroutine(_exceptions, http_error_handler)
    @coroutine
    @post('/' + api_suffix)
    def create_entity(self, request: Request) -> Response:
        values = yield from request.json()
        yield from GenericValidation.create_entity(_entity, values)
        result = yield from manager.create_entity(_entity, values)
        return json_response(result, status=HTTPStatusCodes.CREATED.value)

    @silence_coroutine(_exceptions, http_error_handler)
    @coroutine
    @put('/' + api_suffix)
    def update_entity(self, request: Request) -> Response:
        values = yield from request.json()
        yield from GenericValidation.update_entity(_entity, values)
        yield from manager.update_entity(_entity, values)
        return json_response(update_success_message, status=HTTPStatusCodes.SUCCESS.value)

    @silence_coroutine(_exceptions, http_error_handler)
    @coroutine
    @get('/' + api_suffix + '/search')
    def search_entity(self, request: Request) -> Response:
        query, limit = GenericValidation.search_fields(request.GET)
        fields = GenericValidation._get_fields(request.GET)
        filter = GenericValidation._get_filter(request.GET)
        response = yield from manager.search_entity(_entity, query, fields=fields, limit=limit, offset=0, where_clause=filter)
        return json_response(response)

    @silence_coroutine(_exceptions, http_error_handler)
    @coroutine
    @get('/' + api_suffix + '/{id}')
    def get_entity(self, request: Request) -> Response:
        _id = request.match_info['id']
        limit, offset, fields, filter, order_by= GenericValidation.get_all_fields(request.GET)
        response = (yield from manager.get_entity_start(_entity, {_entity.ID: _id}, fields=fields))
        return json_response(response)

    @silence_coroutine(_exceptions, http_error_handler)
    @coroutine
    @get('/list-' + api_suffix)
    def get_all_entity(self, request: Request) -> Response:
        limit, offset, fields, filter, order_by = GenericValidation.get_all_fields(request.GET)
        response = (yield from manager.get_all_entity(_entity, fields=fields, limit=limit, offset=offset, filter=filter, order_by=order_by))
        return json_response(response)

    prepare_api(get_api_name(ApiTypes.CREATE, api_suffix), create_entity, apis)
    prepare_api(get_api_name(ApiTypes.UPDATE, api_suffix), update_entity, apis)
    prepare_api(get_api_name(ApiTypes.GET, api_suffix), get_entity, apis)
    prepare_api(get_api_name(ApiTypes.SEARCH, api_suffix), search_entity, apis)
    prepare_api(get_api_name(ApiTypes.GET_ALL, api_suffix), get_all_entity, apis)

    return apis

