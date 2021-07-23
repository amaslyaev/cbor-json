import json
import base64
from datetime import datetime
from datetime import date, timezone  # noqa: F401

# Need for "assert" expressions in the "ext_jsons.json" testcases
import decimal  # noqa: F401
import math  # noqa: F401
import uuid  # noqa: F401
import fractions  # noqa: F401
import cbor2  # noqa: F401

import pytest
import pandas as pd  # noqa: F401

from cbor_json import cbor_from_jsonable, jsonable_from_cbor, \
    native_from_jsonable, native_from_cbor, cbor_from_native, jsonable_from_native, \
    SerializableToCbor, register_custom_class
from cbor_json._cbor_json_codecs import _native_from_cborable, _transform_collection
from cbor_json import custom_objects
from cbor_json import UnrecognizedCustomObject  # noqa: F401


def test_vectors():
    with open('tests/cbor-test-vectors/appendix_a.json', encoding='utf-8') as jsonf:
        vectors = json.load(jsonf)
    for idx, vector in enumerate(vectors):

        # Given: base64-encoded cbor in vector['cbor']
        #        "roundtrip" flag in vector['roundtrip']
        #
        # Check:
        # - jfc - jsonable_from_cbor
        # - cfj - cbor_from_jsonable
        # - cfn - cbor_from_native
        # - nfc - native_from_cbor
        # - nfj - native_from_jsonable
        # - jfn - jsonable_from_native
        #
        # cbor1_b -(jfc)→ jsonable1 → json -(nfj)→ native1 -(cfn)→ cbor2_b → check roundtrip
        #     -(nfc)→ native2 -(jfn)→ jsonable2 -(cfj)→ cbor3_b → check cbor3_b == cbor2_b

        cbor1_b = base64.decodebytes(vector['cbor'].encode())
        jsonable1 = jsonable_from_cbor(cbor1_b)
        jsonable1 = json.loads(json.dumps(jsonable1))
        native1 = native_from_jsonable(jsonable1)
        cbor2_b = cbor_from_native(native1)

        # check roundtrip
        if cbor2_b != cbor1_b and vector["roundtrip"]:
            native_x = native_from_cbor(cbor2_b)
            if isinstance(native1, float) and isinstance(native_x, float) \
                    and round(native1 * 1000) == round(native_x * 1000):
                print('  ...it\'s float')
            elif isinstance(native1, datetime) and isinstance(native_x, datetime) \
                    and native1 == native_x:
                print('  ...it\'s datetime')
            else:
                raise Exception(
                    f'{idx} Filed on roundtrip: encoded {cbor2_b.hex()}; '
                    f'expected {cbor1_b.hex()}')

        native2 = native_from_cbor(cbor1_b)
        jsonable2 = jsonable_from_native(native2)
        cbor3_b = cbor_from_jsonable(jsonable2)

        # check cbor3_b == cbor2_b
        if cbor3_b != cbor2_b:
            raise Exception(
                f'{idx} Filed on second encoding: encoded {cbor3_b.hex()}; '
                f'expected {cbor2_b.hex()}')


class Example1(SerializableToCbor):
    cbor_cc_classtag = 'e1'
    cbor_cc_descr = 'Example 1 (event, date)'

    def get_cbor_cc_values(self):
        return [self.event, self.date]

    def put_cbor_cc_values(self, event, a_date):
        self.event = event
        self.date = a_date

    def __str__(self):
        return (
            f'Example1(\'{self.event}\' ({type(self.event).__name__}), '
            f'{self.date} ({type(self.date).__name__}))'
        )


register_custom_class(Example1)


def test_jsons():
    with open('tests/cbor-test-vectors/ext_jsons.json', encoding='utf-8') as jsonf:
        ext_jsons = json.load(jsonf)

    passed = True
    for case_name, case_data in ext_jsons.items():
        if isinstance(case_data, str):
            continue

        jsonable1 = case_data['data']

        # Given: jsoned something in case_data['data']
        #        expected cbor in case_data['cbor']
        #        assertion expression for "native" in case_data['assert']
        #
        # Check:
        # - cfj - cbor_from_jsonable
        # - jfc - jsonable_from_cbor
        # - cfn - cbor_from_native
        # - nfc - native_from_cbor
        # - nfj - native_from_jsonable
        # - jfn - jsonable_from_native
        #
        # jsonable1 -(cfj)→ cbor1_b → check cbor1_b
        #                      -(nfc)→ native1 → check native1
        #                                 -(jfn)→ jsonable2 → json -(cfj)→ cbor2_b → check cbor2_b
        #                      -(jfc)→ jsonable3 -(nfj)→ native2 -(cfn)→ cbor3_b → check cbor3_b

        cbor1_b = cbor_from_jsonable(jsonable1)

        # check cbor1_b
        cbor1_hex = cbor1_b.hex()
        if cbor1_hex != case_data['cbor']:
            print(
                f'{case_name}: wrong first encoding: "{cbor1_hex}", '
                f'expected "{case_data["cbor"]}"')
            passed = False

        native1 = native_from_cbor(cbor1_b)

        # check native
        native = native1
        if 'assert' in case_data:
            if not eval(case_data['assert']):
                print(f'{case_name}: "assert" failed; native={native} ({type(native).__name__})')
                passed = False
        elif native != case_data['data']:
            print(
                f'{case_name}: wrong decoding: {native} ({type(native).__name__}); '
                f'expected {case_data["data"]} ({type(case_data["data"]).__name__})')
            passed = False

        jsonable2 = jsonable_from_native(native1)
        jsonable2 = json.loads(json.dumps(jsonable2))
        cbor2_b = cbor_from_jsonable(jsonable2)

        # check cbor2_b
        cbor2_hex = cbor2_b.hex()
        if cbor2_hex != cbor1_hex:
            print(
                f'{case_name}: second encoding not equals first: "{cbor2_hex}", '
                f'first is "{cbor1_hex}"')
            passed = False

        jsonable3 = jsonable_from_cbor(cbor1_b)
        native2 = native_from_jsonable(jsonable3)
        cbor3_b = cbor_from_native(native2)

        # check cbor3_b
        cbor3_hex = cbor3_b.hex()
        if cbor3_hex != cbor1_hex:
            print(
                f'{case_name}: third encoding not equals first: "{cbor3_hex}", '
                f'first is "{cbor1_hex}"')
            passed = False

    assert passed


class WrongSerializable1(SerializableToCbor):
    def get_cbor_cc_values(self) -> list: pass
    def put_cbor_cc_values(self, *values): pass


class WrongSerializable2(SerializableToCbor):
    cbor_cc_classtag = '#'
    def get_cbor_cc_values(self) -> list: pass
    def put_cbor_cc_values(self, *values): pass


class WrongSerializable3(SerializableToCbor):
    cbor_cc_classtag = '~willfail'
    def get_cbor_cc_values(self) -> list: pass
    def put_cbor_cc_values(self, *values): pass


def test_rising():
    with pytest.raises(ValueError) as exc:
        cbor_from_native(test_rising)
    assert str(exc.value) == 'Cannot convert function to cborable format'

    with pytest.raises(ValueError) as exc:
        _native_from_cborable(test_rising)
    assert str(exc.value) == 'Cannot convert function to native format'

    with pytest.raises(ValueError) as exc:
        _transform_collection(1, 2, 3)  # absurdic, but anyway...
    assert str(exc.value) == 'Convestion for int is not implemented'

    a1 = [1, ]
    a2 = [2, a1]
    a1.append(a2)

    with pytest.raises(ValueError) as exc:
        cbor_from_native(a1)
    assert str(exc.value) == 'Cannot encode a recursively linked structure'

    with pytest.raises(ValueError) as exc:
        _native_from_cborable(a1)
    assert str(exc.value) == 'Cannot encode a recursively linked structure'

    with pytest.raises(ValueError) as exc:
        cbor_from_jsonable({'$type': 'haha'})
    assert str(exc.value) == '$type "haha" is not supported'

    with pytest.raises(TypeError) as exc:
        cbor_from_jsonable(test_rising)
    assert str(exc.value) == 'Value of type function is not JSONable'

    with pytest.raises(ValueError) as exc:
        register_custom_class(datetime)
    assert str(exc.value) == 'Class datetime is not a subclass of SerializableToCbor'

    with pytest.raises(ValueError) as exc:
        register_custom_class(WrongSerializable1)
    assert str(exc.value) == 'Class tag is not defined for class WrongSerializable1'

    with pytest.raises(ValueError) as exc:
        register_custom_class(WrongSerializable2)
    assert str(exc.value) == \
        'Cannot register WrongSerializable2 with class tag "#" because this tag ' + \
        'is already used for HashSha3_224'

    with pytest.raises(ValueError) as exc:
        register_custom_class(WrongSerializable3)
    assert str(exc.value) == 'Registering class tags that start with "~" sign is prohibited'


def test_custom_objects():
    assert str(custom_objects.HashCrc32()) == "HashCrc32()"
    assert str(custom_objects.HashCrc32(b'hi')) == "HashCrc32(digest=bytes.fromhex('d8932aac'))"
    assert str(custom_objects.HashMd5(b'hi')) == \
        "HashMd5(digest=bytes.fromhex('49f68a5c8493ec2c0bf489821c21fc3b'))"
    assert str(custom_objects.HashSha1(b'hi')) == \
        "HashSha1(digest=bytes.fromhex('c22b5f9178342609428d6f51b2c5af4c0bde6a42'))"
    assert str(custom_objects.HashSha256(b'hi')) == \
        "HashSha256(digest=bytes.fromhex(" + \
        "'8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4'))"
    assert str(custom_objects.HashSha3_224(b'hi')) == \
        "HashSha3_224(digest=bytes.fromhex('" + \
        "4538aacc6ccae167eb462bd2d6ced3537edf6f8d88af709be7b130c0'))"
    assert str(custom_objects.HashSha3_256(b'hi')) == \
        "HashSha3_256(digest=bytes.fromhex('" + \
        "b39c14c8da3b23811f6415b7e0b33526d7e07a46f2cf0484179435767e4a8804'))"

    assert {custom_objects.HashCrc32(digest=bytes.fromhex('d8932aac')): 1}  # is hashable
    with pytest.raises(TypeError) as exc:
        assert {custom_objects.HashCrc32(): 1}  # is unhashable
    assert str(exc.value) == 'Uninitialized HashCrc32 is unhashable'

    no_rows_df = pd.DataFrame({'a': [], 'b': []})
    no_rows_dfs = custom_objects.DataFrameSerialized(no_rows_df)
    assert no_rows_dfs.rows_data() == []
    assert no_rows_dfs.columns_data() == {'a': [], 'b': []}

    empty_df = pd.DataFrame()
    empty_dfs = custom_objects.DataFrameSerialized(empty_df)
    assert empty_dfs.rows_data() == []
    assert empty_dfs.columns_data() == {}

    unitialized_dfs = custom_objects.DataFrameSerialized()
    assert unitialized_dfs.rows_data() == []
    assert unitialized_dfs.columns_data() == {}
