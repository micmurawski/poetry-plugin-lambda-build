def remove_prefix(text: str, prefix: str) -> str:
    return text[len(prefix):] if text.startswith(prefix) and prefix else text


def remove_suffix(text: str, suffix: str) -> str:
    return text[:-len(suffix)] if text.endswith(suffix) and suffix else text
