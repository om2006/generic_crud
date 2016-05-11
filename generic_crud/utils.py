from enum import Enum
import json
import logging

from vyked import VykedServiceException
from psycopg2 import IntegrityError

from .exceptions import NotFoundException, ValidationException

logger = logging.getLogger()


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
