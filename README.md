[![PyPI pyversions](https://img.shields.io/pypi/pyversions/cbor-json.svg)](https://pypi.python.org/pypi/cbor-json/)
[![PyPI status](https://img.shields.io/pypi/status/cbor-json.svg)](https://pypi.python.org/pypi/cbor-json/)
[![GitHub license](https://img.shields.io/github/license/Naereen/StrapDown.js.svg)](https://github.com/amaslyaev/cbor-json/blob/master/LICENSE)

# cbor-json

This library provides three-way conversion between "native" Python data representation, [CBOR](https://cbor.io/) (Concise Binary Object Representation), and human- and machine-readable JSON (and also YAML, TOML, etc.) form.

## Installation and import
You need at least Python 3.6 to use this library
```shell
pip install cbor-json
```
Import:
```python
import cbor_json
```

## Objective
Binary data form is better than text because it consumes less space, and what is more important, better keeps its own identity. Sequence of zeros and ones equals itself and nothing else. Working with text data we always have to take into account that some "small" and "invisible" changes can occur at any stage of transmission/processing - changes in line ends, encoding adjustments, "illegal" symbols replacements, trailing line breaks removals, etc.

Text data representation is better because we can read it, understand and edit.

This library provides a simple way to enjoy benefits of both approaches: convert any valid CBOR to JSON (or YAML or TOML if you like), inspect it, make necessary changes, and convert to CBOR back.

## Data forms
1. **CBOR** - binary data format with excellent support in wide variety of languages including Python, C, C++, C#, Java, JavaScript, Go, Rust, PHP, Scala and many others. This library uses [cbor2](https://pypi.org/project/cbor2/) library as CBOR codec.
2. **Native** Python representation - data as we use it in our scripts - strings, numbers, booleans, lists, dictionaries, sets, "bytes", datetimes. Also this library provides a possibility to implement three-way serialization (to/from CBOR and JSON) for custom classes.
3. **Jsonable** representation - form that can be dumped to JSON without additional tricks.

## Usage
Conversions:
- **native_from_cbor** - decodes CBOR to the "native" Python representation
- **cbor_from_native** - encodes Python data to CBOR
- **jsonable_from_native** - transforms Python data to the form that can be passed to <code>json.dump</code> function without exceptions
- **native_from_jsonable** - transformation back from jsonable form
- **jsonable_from_cbor** and **cbor_from_jsonable** - decoding/encoding CBOR to/from jsonable representation

Let's play with it
```python
>>> import cbor_json
>>> c1 = cbor_json.cbor_from_native('Hello')
>>> c1
b'eHello'
>>> print(cbor_json.native_from_cbor(c1))
Hello
>>> import json
>>> json.dumps(cbor_json.jsonable_from_native('hello'))
'"hello"'
>>> json.dumps(cbor_json.jsonable_from_cbor(c1))
'"Hello"'
```
Dump the current datetime to cbor and json:
```python
>>> import datetime
>>> now = datetime.datetime.utcnow()
>>> now
datetime.datetime(2021, 7, 21, 22, 44, 16, 381609)
>>> cbor_json.cbor_from_native(now)
b'\xc1\xfbA\xd8>(\xd0\x18lH'
>>> cbor_json.cbor_from_native(now).hex()
'c1fb41d83e28d0186c48'
>>> cbor_json.jsonable_from_native(now)
{'$type': 'datetime', '$value': '2021-07-21T22:44:16.381609'}
>>> print(json.dumps(cbor_json.jsonable_from_native(now), indent=2))
{
  "$type": "datetime",
  "$value": "2021-07-21T22:44:16.381609"
}
>>> # Roundtrip: native -> cbor -> json -> native
>>> c2 = cbor_json.cbor_from_native(now)
>>> jsoned = json.dumps(cbor_json.jsonable_from_cbor(c2))
>>> cbor_json.native_from_jsonable(json.loads(jsoned))
datetime.datetime(2021, 7, 21, 22, 44, 16, 381609, tzinfo=datetime.timezone.utc)
```
Notice <code>tzinfo=datetime.timezone.utc</code> acquired after conversion to/from CBOR.

More encoding examples:
```python
>>> import math
>>> import decimal
>>> import fractions
>>> import uuid
>>> example = {'simple values': [None, True, False], 'numbers': [0, 123, 0.123, math.nan, fractions.Fraction(1, 3), decimal.Decimal('123.45')], 'id': uuid.uuid4()}
>>> cbor_json.cbor_from_native(example).hex()
'a3626964d82550962529e447f94237808137d11b1bb033676e756d626572738600187bfb3fbf7ced916872b0f97e00d81e820103c482211930396d73696d706c652076616c75657383f6f5f4'
>>> print(json.dumps(cbor_json.jsonable_from_native(example), indent=2))
{
  "simple values": [
    null,
    true,
    false
  ],
  "numbers": [
    0,
    123,
    0.123,
    NaN,
    {
      "$type": "fraction",
      "$value": "1/3"
    },
    {
      "$type": "decimal",
      "$value": "123.45"
    }
  ],
  "id": {
    "$type": "uuid",
    "$value": "962529e4-47f9-4237-8081-37d11b1bb033"
  }
}
```

Let's try to encode something recursive
```python
>>> a1 = [1, ]
>>> a2 = [2, a1]
>>> a1.append(a2)
>>> a1
[1, [2, [...]]]
>>> a2
[2, [1, [...]]]
>>> cbor_json.cbor_from_native(a1)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  ... cut ...
  File "***/cbor_json/_cbor_json_codecs.py", line 60, in _cborable_from_native
    raise ValueError('Cannot encode a recursively linked structure')
ValueError: Cannot encode a recursively linked structure
```
It is not possible. Get rid of recursive links before encoding.

Let's encode a pandas dataframe
```python
>>> import pandas as pd  # assume it is pip-installed
>>> dframe = pd.DataFrame({'name': ['John', 'Jane'], 'age': [23, 22]})
>>> dframe
   name  age
0  John   23
1  Jane   22
>>> from cbor_json.custom_objects import DataFrameSerialized
>>> c3 = cbor_json.cbor_from_native(DataFrameSerialized(dframe))
>>> c3.hex()
'd81b8362646682646e616d65636167658282644a6f686e1782644a616e6516'
>>> dframe_decoded = pd.DataFrame(cbor_json.native_from_cbor(c3).columns_data())
>>> dframe_decoded
   name  age
0  John   23
1  Jane   22
>>> print(json.dumps(cbor_json.jsonable_from_cbor(c3), indent=2))
{
  "$type": "custom-object",
  "$class": "DataFrame (columns, data)",
  "$class_tag": "df",
  "$value": [
    [
      "name",
      "age"
    ],
    [
      [
        "John",
        23
      ],
      [
        "Jane",
        22
      ]
    ]
  ]
}
```

### Defining your own custom class serialization
1. Inherit from <code>cbor_json.SerializableToCbor</code>.
2. In the implementation define cbor_cc_classtag and cbor_cc_descr class variables.
3. Implement get_cbor_cc_values and put_cbor_cc_values methods.
4. Call a cbor_json.register_custom_class to register your class for codec.

```python
>>> class Point(cbor_json.SerializableToCbor):
...     cbor_cc_classtag = 'p'
...     cbor_cc_descr = 'Point (x, y)'
...     def __init__(self, x=None, y=None):
...         self.x, self.y = x, y
...     def get_cbor_cc_values(self):
...         return [self.x, self.y]
...     def put_cbor_cc_values(self, x, y):
...         self.x, self.y = x, y
... 
>>> cbor_json.register_custom_class(Point)
>>> c4 = cbor_json.cbor_from_native(Point(1.23, 4.56))
>>> c4.hex()
'd81b836170fb3ff3ae147ae147aefb40123d70a3d70a3d'
>>> cbor_json.native_from_cbor(c4).x
1.23
>>> print(json.dumps(cbor_json.jsonable_from_cbor(c4), indent=2))
{
  "$type": "custom-object",
  "$class": "Point (x, y)",
  "$class_tag": "p",
  "$value": [
    1.23,
    4.56
  ]
}
```

### Guidelines for assigning class tags

1. At the moment these class tags are in use:

| class tag | class | Description |
| :---:     | :---  |  :---       |
| #   | cbor_json.custom_objects.HashSha3_224 | sha3_224 hash |
| #1  | cbor_json.custom_objects.HashSha1     | sha1 hash |
| #2  | cbor_json.custom_objects.HashSha256   | sha256 hash |
| #3  | cbor_json.custom_objects.HashSha3_256 | sha3_256 hash |
| #5  | cbor_json.custom_objects.HashMd5      | md5 hash |
| #0  | cbor_json.custom_objects.HashCrc32    | crc32 checksum |
| df  | cbor_json.custom_objects.DataFrameSerialized | pandas dataframe |

2. Keep class tags short.
3. Tags of 1 and 2 characters long meant to be a subject of general consent. If you have an idea to add something undoubtedly useful, create an issue and/or a PR.
4. Registering class tags that start with "~" sign is prohibited. Data marked this way is meant to be interpreted as <code>cbor_json.UnrecognizedCustomObject</code>, and it might be useful sometimes.

## Additional notes
- Roundtrip "CBOR -> decode -> encode -> CBOR" usually produces exactly the same result, but with some exceptions:
  - Encoding always produces so called "canonical" format, so if decoded cbor was not canonical, the result will be different.
  - Here we encode datetimes as timestamps (cbor tag 1), so if they were encoded as datetime strings (cbor tag 0), the result will change.
  - Floats... No guarantees for them, as usual.
- Roundtrip "Native -> CBOR -> native" logically produces the same result except dicts keys order.
- Roundtrip "JSON -> native or CBOR -> JSON" sometimes produces the same result, but no guarantees at all.
- Not every imaginable json can be processed by this tool. For instance, '{"$type": "Hahaha"}' will fail.
- If some valid CBOR cannot be processed by this tool, please create an issue.
- Please take care of backward compatibility. Do not redefine class tags.
