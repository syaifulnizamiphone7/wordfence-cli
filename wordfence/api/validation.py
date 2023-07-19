from .exceptions import ValidationException


class JsonValidationException(ValidationException):

    def __init__(self, key: list, message: str, value=None):
        self.key = key
        self.value = value
        super().__init__(
                self.get_key_as_string() +
                ': ' +
                message +
                ', received: ' +
                repr(value)
            )

    def get_key_as_string(self) -> str:
        return '.'.join([str(component) for component in self.key])


class JsonValidator:

    def validate(self, data, parent_key: list = []):
        pass

    def validate_type(self, key, value, expected_type) -> None:
        if isinstance(expected_type, JsonValidator):
            expected_type.validate(value, key)
        elif not isinstance(value, expected_type):
            raise JsonValidationException(
                    key,
                    'Value must be of type ' + str(expected_type),
                    value
                )


class JsonObjectValidator(JsonValidator):

    def __init__(self, expected: dict = {}):
        self.expected = expected

    def validate(self, data, parent_key: list = []) -> None:
        if not isinstance(data, dict):
            raise JsonValidationException(
                    parent_key,
                    'Element must be a JSON object',
                    data
                )
        for key, expected_type in self.expected.items():
            aggregate_key = parent_key + [key]
            try:
                value = data[key]
                self.validate_type(aggregate_key, value, expected_type)
            except KeyError:
                raise JsonValidationException(aggregate_key, 'Key not present')


class JsonArrayValidator(JsonValidator):

    def __init__(self, expected):
        self.expected = expected

    def validate(self, data, parent_key: list = []) -> None:
        if not isinstance(data, list):
            raise JsonValidationException(
                    parent_key,
                    'Element must be a JSON array',
                    data
                )
        if isinstance(self.expected, dict):
            for index, expected_type in self.expected.items():
                key = parent_key + [index]
                try:
                    value = data[index]
                    self.validate_type(key, data[index], expected_type)
                except IndexError:
                    raise JsonValidationException(
                            key,
                            'Index does not exist in array'
                        )
        else:
            for index, value in enumerate(data):
                self.validate_type(parent_key + [index], value, self.expected)
