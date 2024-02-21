from copy import copy


def get_path(
    obj, path: str, separator: str = ".", getter=lambda obj, attr: obj.get(attr)
):
    attrs = path.split(separator)
    value = obj
    while True:
        try:
            attr = attrs.pop(0)
            value = getter(value, attr)
        except IndexError:
            return value


def merge_options(a: dict, b: dict) -> dict:
    result = copy(a)
    for k in b:
        val = b[k]
        result[k] = merge_options(
            result[k], val) if isinstance(val, dict) else val
    return result
