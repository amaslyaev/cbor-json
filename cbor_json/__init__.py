"""
Three-way conversion between "native" Python data representation, CBOR, and JSON.
See README.md for details.
"""

from ._cbor_json_codecs import (  # noqa: F401
    native_from_cbor, cbor_from_native,
    jsonable_from_native, native_from_jsonable,
    jsonable_from_cbor, cbor_from_jsonable,
    base58_encode, base58_decode
)

from ._custom_objects_base import (  # noqa: F401
    SerializableToCbor, UnrecognizedCustomObject, register_custom_class
)

from . import custom_objects  # noqa: F401
