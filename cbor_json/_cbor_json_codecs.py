"""
The implementation of Native <-> CBOR <-> JSONable conversions
"""

from datetime import datetime, date, timezone, timedelta
import base64
from uuid import UUID
from fractions import Fraction
import decimal
import re
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from email.message import Message

import cbor2

from ._custom_objects_base import \
    SerializableToCbor, UnrecognizedCustomObject, CUSTOM_CLASSES_BY_CLASSTAG


# ---------------- native <--> cborable conversions ----------------

def _transform_collection(src, encountered_ids, conv_func):
    res = None

    if isinstance(src, list):
        res = [conv_func(el, encountered_ids) for el in src]
    elif isinstance(src, tuple):
        res = tuple(conv_func(el, encountered_ids) for el in src)
    elif isinstance(src, dict):
        res = {
            conv_func(k, encountered_ids): conv_func(v, encountered_ids)
            for k, v in src.items()
        }
    elif isinstance(src, cbor2.types.FrozenDict):
        res = cbor2.types.FrozenDict([
            [conv_func(k, encountered_ids), conv_func(v, encountered_ids)]
            for k, v in src.items()
        ])
    elif isinstance(src, set):
        res = set(conv_func(el, encountered_ids) for el in src)
    elif isinstance(src, frozenset):
        res = frozenset(conv_func(el, encountered_ids) for el in src)
    else:
        raise ValueError(
            f'Convestion for {type(src).__name__} is not implemented')

    return res


def _cborable_from_native(native, encountered_ids=None):
    if native is None or native == cbor2.undefined \
       or isinstance(native, (str, int, float, bool, datetime, bytes, re.Pattern,
                              Fraction, decimal.Decimal, UUID, cbor2.CBORSimpleValue,
                              IPv4Address, IPv4Network, IPv6Address, IPv6Network, Message)):
        return native
    if isinstance(native, date):
        return cbor2.CBORTag(100, (native - date(1970, 1, 1)).days)

    if encountered_ids is None:
        encountered_ids = set()

    this_id = None
    res = None
    if isinstance(native, (list, tuple, dict, cbor2.types.FrozenDict,
                           set, frozenset, SerializableToCbor, cbor2.CBORTag)):
        this_id = id(native)
        if this_id in encountered_ids:
            raise ValueError('Cannot encode a recursively linked structure')
        encountered_ids.add(this_id)

        if isinstance(native, SerializableToCbor):
            values = [
                _cborable_from_native(el, encountered_ids)
                for el in native.get_cbor_cc_values()
            ]
            res = cbor2.CBORTag(
                27,  # http://cbor.schmorp.de/generic-object
                [native.cbor_cc_classtag, ] + values
            )
        elif isinstance(native, cbor2.CBORTag):
            res = cbor2.CBORTag(
                native.tag,
                _cborable_from_native(native.value, encountered_ids)
            )
        else:
            res = _transform_collection(native, encountered_ids, _cborable_from_native)
    else:
        raise ValueError(f'Cannot convert {type(native).__name__} to cborable format')

    if this_id is not None:
        encountered_ids.remove(this_id)
    return res


def _native_from_cborable(cborable, encountered_ids=None):
    if cborable is None or cborable == cbor2.undefined \
       or isinstance(cborable, (str, int, float, bool, datetime, bytes, re.Pattern,
                                Fraction, decimal.Decimal, UUID, cbor2.CBORSimpleValue,
                                IPv4Address, IPv4Network, IPv6Address, IPv6Network)):
        return cborable

    if encountered_ids is None:
        encountered_ids = set()

    this_id = None
    res = None
    if isinstance(cborable, (list, tuple, dict, cbor2.types.FrozenDict,
                             set, frozenset, cbor2.CBORTag)):
        this_id = id(cborable)
        if this_id in encountered_ids:
            raise ValueError('Cannot encode a recursively linked structure')
        encountered_ids.add(this_id)

        if isinstance(cborable, cbor2.CBORTag):
            if cborable.tag == 100:
                res = date(1970, 1, 1) + timedelta(days=cborable.value)
            elif cborable.tag == 27:  # http://cbor.schmorp.de/generic-object
                assert isinstance(cborable.value, list)
                assert len(cborable.value) > 0
                assert isinstance(cborable.value[0], str)
                class_tag = cborable.value[0]
                assert class_tag
                native_values = [
                    _native_from_cborable(el, encountered_ids)
                    for el in cborable.value[1:]]
                if class_tag in CUSTOM_CLASSES_BY_CLASSTAG:
                    res = CUSTOM_CLASSES_BY_CLASSTAG[class_tag]()
                    res.put_cbor_cc_values(*native_values)
                else:
                    res = UnrecognizedCustomObject()
                    res.class_tag = res.cbor_cc_classtag = class_tag
                    res.put_cbor_cc_values(*native_values)
            else:
                res = cbor2.CBORTag(
                    cborable.tag,
                    _native_from_cborable(cborable.value, encountered_ids)
                )
        else:
            res = _transform_collection(cborable, encountered_ids, _native_from_cborable)
    elif isinstance(cborable, Message):
        payload = cborable.as_bytes()
        while payload and payload[:len(b'\n')] == b'\n':
            payload = payload[len(b'\n'):]
        res = Message()
        res.set_payload(payload)
    else:
        raise ValueError(f'Cannot convert {type(cborable).__name__} to native format')

    if this_id is not None:
        encountered_ids.remove(this_id)
    return res


# ---------------- jsonable <--> cborable conversions ----------------

def _freeze(val):
    if isinstance(val, list):
        return tuple(_freeze(el) for el in val)
    if isinstance(val, set):
        return frozenset(_freeze(el) for el in val)
    if isinstance(val, dict):
        return cbor2.types.FrozenDict({_freeze(k): _freeze(v) for k, v in val.items()})
    return val


def _cborable_from_jsonable(jsonable, enforce_object: bool = False):
    if isinstance(jsonable, list):
        return [_cborable_from_jsonable(el) for el in jsonable]
    if isinstance(jsonable, tuple):
        return tuple(_cborable_from_jsonable(el) for el in jsonable)
    if isinstance(jsonable, dict):
        if '$type' in jsonable and not enforce_object:
            val_type = jsonable['$type']
            if val_type == 'datetime':
                return datetime.fromisoformat(jsonable['$value'])
            if val_type == 'date':
                val_as_int = (date.fromisoformat(jsonable['$value']) - date(1970, 1, 1)).days
                return cbor2.CBORTag(100, val_as_int)
            if val_type == 'binary-hex':
                return bytes.fromhex(jsonable['$value'])
            if val_type == 'binary-base58':
                return base58_decode(jsonable['$value'])
            if val_type == 'binary-base64':
                return base64.decodebytes(jsonable['$value'].encode())
            if val_type == 'custom-object':
                class_tag = jsonable['$class_tag']
                assert class_tag
                assert isinstance(jsonable['$value'], list)
                return cbor2.CBORTag(
                    27,  # http://cbor.schmorp.de/generic-object
                    [class_tag, ] + [_cborable_from_jsonable(el) for el in jsonable['$value']])
            if val_type == 'tagged-value':
                tag = jsonable['$cbor_tag']
                return cbor2.CBORTag(tag, _cborable_from_jsonable(jsonable['$value']))
            if val_type == 'map':
                assert isinstance(jsonable['$value'], list)
                res = {}
                for kv_pair in jsonable['$value']:
                    assert isinstance(kv_pair, list)
                    assert len(kv_pair) == 2
                    res[_freeze(_cborable_from_jsonable(kv_pair[0]))] = \
                        _cborable_from_jsonable(kv_pair[1])
                return res
            if val_type == 'set':
                assert isinstance(jsonable['$value'], list)
                return set(_freeze(_cborable_from_jsonable(el)) for el in jsonable['$value'])
            if val_type == 'uuid':
                return UUID(jsonable['$value'])
            if val_type == 'fraction':
                sep_pos = jsonable['$value'].find('/')
                assert sep_pos != -1
                return Fraction(
                    int(jsonable['$value'][:sep_pos]),
                    int(jsonable['$value'][sep_pos+1:]))
            if val_type == 'decimal':
                return decimal.Decimal(jsonable['$value'])
            if val_type == 'regex':
                return re.compile(jsonable['$value'])
            if val_type == 'ipv4-address':
                return IPv4Address(jsonable['$value'])
            if val_type == 'ipv4-network':
                return IPv4Network(jsonable['$value'])
            if val_type == 'ipv6-address':
                return IPv6Address(jsonable['$value'])
            if val_type == 'ipv6-network':
                return IPv6Network(jsonable['$value'])
            if val_type == 'mime':
                res = Message()
                payload = base64.decodebytes(jsonable['$value'].encode())
                while payload and payload[:len(b'\n')] == b'\n':
                    payload = payload[len(b'\n'):]
                res.set_payload(payload)
                return res
            if val_type == 'cbor-simple-value':
                return cbor2.CBORSimpleValue(jsonable['$value'])
            if val_type == 'undefined':
                return cbor2.undefined
            raise ValueError(f'$type "{val_type}" is not supported')
        return {k: _cborable_from_jsonable(v) for k, v in jsonable.items()}
    if jsonable is None or isinstance(jsonable, (str, int, float, bool)):
        return jsonable
    raise TypeError(f'Value of type {type(jsonable).__name__} is not JSONable')


def _jsonable_from_cborable(cborable):
    if isinstance(cborable, list):
        return [_jsonable_from_cborable(el) for el in cborable]
    if isinstance(cborable, (dict, cbor2.types.FrozenDict)):
        if '$type' not in cborable and all(isinstance(k, str) for k in cborable.keys()):
            return {k: _jsonable_from_cborable(v) for k, v in cborable.items()}
        return {'$type': 'map',
                '$value': [
                    [_jsonable_from_cborable(k), _jsonable_from_cborable(v)]
                    for k, v in cborable.items()
                ]}
    if isinstance(cborable, (set, frozenset)):
        return {'$type': 'set',
                '$value': [_jsonable_from_cborable(el) for el in cborable]}
    if isinstance(cborable, datetime):
        # cborable = cborable.replace(tzinfo=None)
        return {'$type': 'datetime',
                '$value': cborable.isoformat()}
    if isinstance(cborable, bytes):
        if len(cborable) <= 16:
            return {'$type': 'binary-hex',
                    '$value': cborable.hex()}
        if len(cborable) <= 32:
            return {'$type': 'binary-base58',
                    '$value': base58_encode(cborable)}
        return {'$type': 'binary-base64',
                '$value': base64.encodebytes(cborable).decode().rstrip('\n')}
    if isinstance(cborable, cbor2.CBORTag):
        if cborable.tag == 27:
            assert isinstance(cborable.value, list)
            assert len(cborable.value) > 0
            class_tag = cborable.value[0]
            class_descr = CUSTOM_CLASSES_BY_CLASSTAG[class_tag].get_cbor_cc_descr() \
                if class_tag in CUSTOM_CLASSES_BY_CLASSTAG \
                else f'<unrecognized class tag "{class_tag}">'
            return {'$type': 'custom-object',
                    '$class': class_descr,
                    '$class_tag': class_tag,
                    '$value': [_jsonable_from_cborable(el) for el in cborable.value[1:]]}

        if cborable.tag == 100:
            return {'$type': 'date',
                    '$value': (date(1970, 1, 1) + timedelta(days=cborable.value)).isoformat()}

        return {'$type': 'tagged-value',
                '$cbor_tag': cborable.tag,
                '$value': _jsonable_from_cborable(cborable.value)}
    if cborable == cbor2.undefined:
        return {'$type': 'undefined'}
    if isinstance(cborable, UUID):
        return {'$type': 'uuid',
                '$value': str(cborable)}
    if isinstance(cborable, Fraction):
        return {'$type': 'fraction',
                '$value': f'{cborable.numerator}/{cborable.denominator}'}
    if isinstance(cborable, decimal.Decimal):
        return {'$type': 'decimal',
                '$value': str(cborable)}
    if isinstance(cborable, re.Pattern):
        return {'$type': 'regex',
                '$value': cborable.pattern}
    if isinstance(cborable, IPv4Address):
        return {'$type': 'ipv4-address',
                '$value': str(cborable)}
    if isinstance(cborable, IPv4Network):
        return {'$type': 'ipv4-network',
                '$value': str(cborable)}
    if isinstance(cborable, IPv6Address):
        return {'$type': 'ipv6-address',
                '$value': str(cborable)}
    if isinstance(cborable, IPv6Network):
        return {'$type': 'ipv6-network',
                '$value': str(cborable)}
    if isinstance(cborable, Message):
        return {'$type': 'mime',
                '$value': base64.encodebytes(cborable.as_bytes()).decode().rstrip('\n')}
    if isinstance(cborable, cbor2.CBORSimpleValue):
        return {'$type': 'cbor-simple-value',
                '$value': cborable.value}
    return cborable


# ---------------- native <--> jsonable conversions ----------------

def jsonable_from_native(native):
    """
    :param native: 'native' data to convert to jsonable form
    :return: jsonable data
    """
    return _jsonable_from_cborable(_cborable_from_native(native))


def native_from_jsonable(jsonable):
    """
    :param native: 'jsonable' data to convert to native form
    :return: native data
    """
    return _native_from_cborable(_cborable_from_jsonable(jsonable))


# ---------------- native <--> cbor conversions ----------------

def cbor_from_native(native) -> bytes:
    """
    :param native: 'native' data to encode to CBOR
    :return: CBOR bytes
    """
    return cbor2.dumps(
        _cborable_from_native(native),
        canonical=True,
        timezone=timezone.utc,
        datetime_as_timestamp=True
    )


def native_from_cbor(data: bytes):
    """
    :param native: CBOR bytes
    :return: decoded 'native' data
    """
    return _native_from_cborable(cbor2.loads(data))


# ---------------- jsonable <--> cbor conversions ----------------

def cbor_from_jsonable(jsonable) -> bytes:
    """
    :param native: 'jsonable' data to encode to CBOR
    :return: CBOR bytes
    """
    return cbor2.dumps(
        _cborable_from_jsonable(jsonable),
        canonical=True,
        timezone=timezone.utc,
        datetime_as_timestamp=True
    )


def jsonable_from_cbor(data: bytes):
    """
    :param native: CBOR bytes
    :return: decoded data in jsonable form
    """
    return _jsonable_from_cborable(cbor2.loads(data))


# ---------------- base58 coding/decoding ----------------
# Details: https://en.wikipedia.org/wiki/Base58

_BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_BASE58_ALPHA_IDXS = {a: i for i, a in enumerate(_BASE58_ALPHABET)}


def base58_encode(decoded: bytes) -> str:
    """
    Returns base58-encoded string. Using Bitcoin alphabet.
    :param decoded: bytes-like object to encode.
    :return: base58 representation of b'\x01' + decoded (to make a difference between 0xabcd
        and 0x000000abcd.)
    """
    int_v = int.from_bytes(b'\x01' + decoded, byteorder='big')
    chrs = []
    while int_v:
        int_v, reminder = divmod(int_v, 58)
        chrs.append(_BASE58_ALPHABET[reminder])
    return ''.join(reversed(chrs))


def base58_decode(encoded: str) -> bytes:
    """
    Decodes base58-encoded string and returns bytes. Using Bitcoin alphabet.
    :param encoded: string to decode.
    :return: decoded bytes. Throws away first byte (see base58_encode description).
    """
    int_v = 0
    for char in encoded:
        int_v = int_v * 58 + _BASE58_ALPHA_IDXS[char]
    return int_v.to_bytes((int_v.bit_length() - 1) // 8 + 1, byteorder='big')[1:]
