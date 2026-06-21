
import json
text = '{"desc": "foo {bar} [baz] "qux"", "val": 42}'
print(repr(text))
print(text)
json.loads(text)
print('OK')
