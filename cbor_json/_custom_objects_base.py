"""
Classes:
- SerializableToCbor - abstract base class for objects that to be serializable to CBOR
- UnrecognizedCustomObject - used when unregistered class tag encountered

Function:
- register_custom_class - use it to register your custom serializable class

Usage examples of SerializableToCbor and register_custom_class you can find
in the custom_objects.py module.
"""

from abc import ABC, abstractmethod


class SerializableToCbor(ABC):
    """
    Abstract base class for objects that to be serializable to CBOR.
    In the implementation define cbor_cc_classtag, cbor_cc_descr,
    and implement get_cbor_cc_values and put_cbor_cc_values methods.
    """
    cbor_cc_classtag = None  # Keep it short
    cbor_cc_descr = None  # Good practice to specify parameters here. E.g. "Point (x, y)"

    @classmethod
    def get_cbor_cc_descr(cls) -> str:
        """
        Responds a string to show in the "$class" parameter in jsonable form
        """
        return cls.cbor_cc_descr or f'Object with class tag "{cls.cbor_cc_classtag}">'

    @abstractmethod
    def get_cbor_cc_values(self) -> list:
        """
        This function is used to serialize an object.
        Implement this function in your class. Return data as list of some values.
        """

    @abstractmethod
    def put_cbor_cc_values(self, *values):
        """
        This function is used in the object deserialization.
        Implement this function in your class.
        Parameters are elements of the list produced by get_cbor_cc_values function.
        """


CUSTOM_CLASSES_BY_CLASSTAG = {}
CUSTOM_CLASTAGS_BY_CLASS = {}


def register_custom_class(a_class: type):
    """
    When serializable class is only declared, codec does not know about it yet. Use
    this function to register your class for the codec.
    :param a_class: a class to register. Should be a subclass of SerializableToCbor.
    """
    if a_class not in CUSTOM_CLASTAGS_BY_CLASS:
        if not issubclass(a_class, SerializableToCbor):
            raise ValueError(f'Class {a_class.__name__} is not a subclass of SerializableToCbor')
        if a_class.cbor_cc_classtag is None:
            raise ValueError(f'Class tag is not defined for class {a_class.__name__}')
        if a_class.cbor_cc_classtag.startswith('~'):
            raise ValueError('Registering class tags that start with "~" sign is prohibited')
        classtag = a_class.cbor_cc_classtag
        if classtag in CUSTOM_CLASSES_BY_CLASSTAG:
            raise ValueError(
                f'Cannot register {a_class.__name__} with class tag "{classtag}" because '
                f'this tag is already used for {CUSTOM_CLASSES_BY_CLASSTAG[classtag].__name__}')

        CUSTOM_CLASSES_BY_CLASSTAG[classtag] = a_class
        CUSTOM_CLASTAGS_BY_CLASS[a_class] = classtag


class UnrecognizedCustomObject(SerializableToCbor):
    """
    Used when unregistered class tag encountered.
    """
    def __init__(self):
        self.class_tag = self.value = None

    def get_cbor_cc_values(self):
        return self.value

    def put_cbor_cc_values(self, *values):
        self.value = list(values)
