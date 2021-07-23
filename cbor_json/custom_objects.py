"""
Predefined serializable object classes:
- HashSha1, HashSha256, HashSha3_224, HashSha3_256, HashMd5, HashCrc32 - hashes:
    algorithm  class         $class_tag
    sha1       HashSha1      "#1"
    sha256     HashSha256    "#2"
    sha3_224   HashSha3_224  "#"
    sha3_256   HashSha3_256  "#3"
    md5        HashMd5       "#5"
    crc32      HashCrc32     "#0"
- DataFrameSerialized - a way to serialize a pandas dataframe
"""

from abc import abstractmethod as _abstractmethod
from hashlib import sha1 as _sha1, sha256 as _sha256, \
    sha3_224 as _sha3_224, sha3_256 as _sha3_256, md5 as _md5
from zlib import crc32 as _crc32
from typing import Dict as _Dict, List as _List

from ._custom_objects_base import SerializableToCbor as _SerializableToCbor, \
    register_custom_class as _register_custom_class


# ---------------- Hashes ----------------

class _HashBase(_SerializableToCbor):
    def __init__(self, data: bytes = None, digest: bytes = None):
        """
        :param data: data to be hashed
        :param digest: calculated hash, used if parameter data is None
        """
        self.digest = None
        self._hash = None
        if data is not None:
            self.calculate(data)
        elif digest is not None:
            self.digest = digest

    @_abstractmethod
    def calculate(self, data: bytes):
        """
        Hashes a data
        :param data: data to hash
        """

    def get_cbor_cc_values(self) -> list:
        return [self.digest, ]

    def put_cbor_cc_values(self, digest):  # pylint: disable=W0221
        self.digest = digest

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.digest == other.digest

    def __hash__(self):
        if self._hash is None:
            if self.digest is not None:
                self._hash = hash((self.cbor_cc_classtag, self.digest))
            else:
                raise TypeError(f'Uninitialized {type(self).__name__} is unhashable')
        return self._hash

    def __repr__(self):
        if self.digest is None:
            return f'{type(self).__name__}()'
        return f"{type(self).__name__}(digest=bytes.fromhex('{self.digest.hex()}'))"


class HashSha3_224(_HashBase):  # pylint: disable=C0103
    """
    CBOR- and JSON-serializable SHA3-224 hash
    """
    cbor_cc_classtag = '#'
    cbor_cc_descr = "SHA3-224 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _sha3_224(data).digest()


class HashSha1(_HashBase):
    """
    CBOR- and JSON-serializable SHA1 hash
    """
    cbor_cc_classtag = '#1'
    cbor_cc_descr = "SHA1 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _sha1(data).digest()


class HashSha256(_HashBase):
    """
    CBOR- and JSON-serializable SHA-256 hash
    """
    cbor_cc_classtag = '#2'
    cbor_cc_descr = "SHA-256 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _sha256(data).digest()


class HashSha3_256(_HashBase):  # pylint: disable=C0103
    """
    CBOR- and JSON-serializable SHA3-256 hash
    """
    cbor_cc_classtag = '#3'
    cbor_cc_descr = "SHA3-256 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _sha3_256(data).digest()


class HashMd5(_HashBase):
    """
    CBOR- and JSON-serializable MD5 hash
    """
    cbor_cc_classtag = '#5'
    cbor_cc_descr = "MD5 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _md5(data).digest()


class HashCrc32(_HashBase):
    """
    CBOR- and JSON-serializable CRC32 checksum
    """
    cbor_cc_classtag = '#0'
    cbor_cc_descr = "CRC32 hash (digest)"

    def calculate(self, data: bytes):
        self.digest = _crc32(data).to_bytes(4, byteorder='big')


_register_custom_class(HashSha3_224)
_register_custom_class(HashSha1)
_register_custom_class(HashSha256)
_register_custom_class(HashSha3_256)
_register_custom_class(HashMd5)
_register_custom_class(HashCrc32)


# ---------------- pandas DataFrame ----------------

class DataFrameSerialized(_SerializableToCbor):
    """
    Serialization to/from CBOR and JSON for pandas dataframe
    """
    cbor_cc_classtag = 'df'
    cbor_cc_descr = "DataFrame (columns, data)"

    def __init__(self, dataframe=None):
        self.columns = self.data = None
        if dataframe is not None:
            self.load_dataframe(dataframe)

    def load_dataframe(self, dataframe):
        """
        Use this function to prepare a pandas dataframe data to serialization
        if the dataframe was not provided to the constructor.
        :param dataframe: a dataframe to load
        """
        self.columns = list(dataframe.columns)
        num_rows = len(dataframe)
        num_columns = len(self.columns)
        if num_rows:
            data_from_df = [list(dataframe[cname]) for cname in self.columns]
            self.data = [
                [data_from_df[cidx][ridx] for cidx in range(num_columns)]
                for ridx in range(num_rows)
            ]
        else:
            self.data = []

    def get_cbor_cc_values(self) -> list:
        return [self.columns, self.data]

    def put_cbor_cc_values(self, columns: _List[str], data: _List[list]):  # pylint: disable=W0221
        """
        :param columns: list of column names
        :param data: list of rows; each row is a list of field values
        """
        assert isinstance(columns, list)
        assert isinstance(data, list)
        assert all(isinstance(r, list) for r in data)
        assert all(len(columns) == len(r) for r in data)
        self.columns = columns
        self.data = data

    def columns_data(self) -> _Dict[str, list]:
        """
        Exracts data from the object in the following form:
          {'column1': [val1, val2, ..], 'column2': [..], ..}
        This is the most usual way to pass deserialized data to a pandas dataframe.
        """
        if self.columns is None:
            return {}
        return {c: [r[cidx] for r in self.data] for cidx, c in enumerate(self.columns)}

    def rows_data(self) -> _List[dict]:
        """
        Exracts data from the object in the following form:
        [
            {'column1': val1, 'column2': .., ..}
            {'column1': val2, 'column2': .., ..}
            ...
        ]
        """
        if self.columns is None:
            return []
        return [{c: r[cidx] for cidx, c in enumerate(self.columns)} for r in self.data]


_register_custom_class(DataFrameSerialized)
