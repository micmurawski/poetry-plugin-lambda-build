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
