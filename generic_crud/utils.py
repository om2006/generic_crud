from enum import Enum
import json
import logging

from aiohttp.web import Request, Response
from vyked import VykedServiceException
from psycopg2 import IntegrityError

import datetime
from time import mktime
from builtins import dict

from .exceptions import NotFoundException, ValidationException

logger = logging.getLogger()


class HTTPStatusCodes(Enum):
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400


class TCPStatusCode(Enum):
    BAD_REQUEST_101 = 101
    NOT_FOUND_204 = 204
    UNAUTHORIZED_201 = 201


def tcp_exception_handler(e: Exception, *args, **kwargs) -> Exception:
    """
    Raise exception which is tcp complaints

    :param Exception e: exception which raised
    :param args: arguments passed to function
    :param kwargs:kwargs passed to function

    :return: formatted tcp exception
    :rtype: Exception
    """
    error = None
    if isinstance(e, ValidationException):
        error = '{}_{}'.format(TCPStatusCode.BAD_REQUEST_101.value, e.message)
        raise VykedServiceException(error)
    elif isinstance(e, NotFoundException):
        error = '{}_{}'.format(TCPStatusCode.NOT_FOUND_204.value, e.message)
        raise VykedServiceException(error)
    elif isinstance(e, IntegrityError):
        error = '{}_{}'.format(TCPStatusCode.BAD_REQUEST_101.value, str(e))
        raise VykedServiceException(error)
    else:
        raise Exception(error)


def http_error_handler(e, *args, **kwargs):
    return json_response(e.error, status=HTTPStatusCodes.BAD_REQUEST.value)


def json_file_to_dict(_file: str) -> dict:
    """
    convert json file data to dict

    :param str _file: file location including name

    :rtype: dict
    :return: converted json to dict
    """
    config = None
    with open(_file) as config_file:
        config = json.load(config_file)

    return config


class MyEncoder(json.JSONEncoder):
    """
    json dump encoder class
    """

    def default(self, obj):
        """
        convert datetime instance to str datetime
        """
        if isinstance(obj, datetime.datetime):
            return int(mktime(obj.timetuple()))
        return json.JSONEncoder.default(self, obj)


def json_response(body: object=None, status: int=200) -> Response:
    """
    generate response for the body object,
        Note: converts datetime to long timestamp

    :param object body:
    :param int status: http status code, default is 200 OK

    :return: json response object
    :rtype: Response
    """
    return Response(status=status, body=json.dumps(body, cls=MyEncoder).encode(), content_type='application/json')

