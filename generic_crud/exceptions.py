from vyked.exceptions import VykedServiceException


class NotFoundException(VykedServiceException):
    def __init__(self, message, code=404):
        self.message = message
        self.code = code


class ValidationException(VykedServiceException):
    def __init__(self, message, code=400):
        self.message = message
        self.code = code


class UnauthorisedError(VykedServiceException):
    def __init__(self, message, code=400):
        self.message = message
        self.code = code


class GenericServiceException(VykedServiceException):
    def __init__(self, message, code=1):
        self.message = message
        self.code = code
