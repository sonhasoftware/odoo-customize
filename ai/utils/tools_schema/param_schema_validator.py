class ParamSchemaValidator:

    AVAILABLE_TYPES = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'null']
    REQUIRED_PARAMETER_ATTRIBUTES = ['type']
    REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE = {
        'array': ['items'],
        'string': ['maxLength'],
        'object': ['properties', 'required']
    }
    OPTIONAL_PARAMETER_ATTRIBUTES = ['pattern', 'description', 'enum']

    def __init__(self, param_name, param_definition, is_object_property=False):
        self.param_name = param_name
        self.param_definition = param_definition
        self.is_object_property = is_object_property
        self.param_type = self.param_definition.get('type')

    def _validate(self):
        self._check_missing_required_attributes()
        self._check_unsupported_attributes()
        self._is_valid_param_type()
        self._check_pattern_only_with_allowed_types()
        if self.param_type == 'array':
            self._perform_array_checks()
        elif self.param_type == 'object':
            self._perform_object_checks()

    def _check_missing_required_attributes(self):
        missing_required_attributes = []
        for required_attribute in self.REQUIRED_PARAMETER_ATTRIBUTES:
            if required_attribute not in self.param_definition:
                missing_required_attributes.append(required_attribute)

        if missing_required_attributes:
            raise ValueError(
                f"The attributes '{missing_required_attributes}' must be defined for the parameter '{self.param_name}'."
            )

    def _check_unsupported_attributes(self):
        unsupported_attributes = [
            attribute for attribute in list(self.param_definition.keys())
            if attribute not in self._get_supported_param_attributes()
        ]
        if unsupported_attributes:
            raise ValueError(
                f"The attributes '{unsupported_attributes}' defined for the param '{self.param_name}' are not supported."
            )

    def _get_supported_param_attributes(self):
        return (
            self.REQUIRED_PARAMETER_ATTRIBUTES
            + self.REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE.get(self.param_type, [])
            + self.OPTIONAL_PARAMETER_ATTRIBUTES
        )

    def _check_pattern_only_with_allowed_types(self):
        pattern = self.param_definition.get('pattern')
        if pattern and self.param_type not in ['string', 'array']:
            raise ValueError(
                f"The pattern attribute cannot be defined for the parameter '{self.param_name}'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )

    def _is_valid_param_type(self):
        if self.param_type not in self.AVAILABLE_TYPES:
            raise ValueError(
                f"The type '{self.param_type}' of parameter '{self.param_name}' is wrong. The available types are '{self.AVAILABLE_TYPES}'."
            )

    def _perform_array_checks(self):
        self._check_missing_required_attributes_by_type('array')
        self._check_array_item_types()
        self._check_pattern_defined_only_if_string_array_item()

    def _check_missing_required_attributes_by_type(self, param_type):
        missing_required_attributes = []
        for required_attribute in self.REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE.get(param_type, []):
            if required_attribute not in self.param_definition:
                missing_required_attributes.append(required_attribute)

        if missing_required_attributes:
            raise ValueError(
                f"The attributes '{missing_required_attributes}' must be defined for a parameter of type '{self.param_type}'. "
                f"They are missing for the parameter '{self.param_name}'."
            )

    def _check_array_item_types(self):
        # array_item_types can be a single type '{'type': 'string'}' or a list of types {'anyOf': [{'type': 'string'}, {'type': 'number'}]}
        failure_message = (
            f"The types of the items of the 'array' param '{self.param_name}' are not defined correctly. "
            "The types of the items must be defined as ('items': {'type': 'string'}) if all items are of the same type "
            "or ('items': { 'anyOf': [ {'type': 'string'}, {'type': 'number'} ] }) if items are of different types"
        )
        array_item_types = self.param_definition.get('items')
        if (
            not isinstance(array_item_types, dict)
            or len(array_item_types) > 1
            or array_item_types.get('anyOf') and not isinstance(array_item_types['anyOf'], list)
        ):
            raise ValueError(
                failure_message
            )
        available_types = list(
            set(self.AVAILABLE_TYPES) - {'array', 'object'}
        )
        array_item_types = array_item_types.get('anyOf') if 'anyOf' in array_item_types else [
            array_item_types]
        for item_type in array_item_types:
            if not isinstance(item_type, dict) or len(item_type) > 1 or not item_type.get('type'):
                raise ValueError(
                    failure_message
                )
            if item_type['type'] not in available_types:
                raise ValueError(
                    f"The type '{item_type}' of the items of the 'array' parameter '{self.param_name}' is wrong. The available types are '{available_types}'."
                )

    def _check_pattern_defined_only_if_string_array_item(self):
        pattern = self.param_definition.get('pattern')
        array_item_types = self.param_definition.get('items')
        array_item_types = array_item_types.get('anyOf', [array_item_types])
        if pattern and not (len(array_item_types) == 1 and array_item_types[0]['type'] == 'string'):
            raise ValueError(
                f"The pattern attribute cannot be defined for the parameter '{self.param_name}'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )

    def _perform_object_checks(self):
        self._check_nested_object()
        self._check_missing_required_attributes_by_type('object')
        self._check_required_attribute_is_list()
        self._validate_object_properties()

    def _check_nested_object(self):
        if self.is_object_property:
            raise ValueError(
                f"Nested objects are not supported. The parameter '{self.param_name}' is defined as an object inside another object."
            )

    def _check_required_attribute_is_list(self):
        if not isinstance(self.param_definition['required'], list):
            raise TypeError(
                f"The attribute 'required' for the object param '{self.param_name}' must be a 'list' containing "
                "the required properties of the object or empty if all of them are not required."
            )

    def _validate_object_properties(self):
        object_properties = self.param_definition['properties']
        for object_property_name, object_property_definition in object_properties.items():
            param_validator = ParamSchemaValidator(
                object_property_name, object_property_definition, is_object_property=True)
            param_validator._validate()
