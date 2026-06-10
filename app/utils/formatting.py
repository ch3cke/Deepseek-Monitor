def redact_value(value):
    if value is None:
        return ""

    text = str(value)
    if len(text) <= 8:
        return text
    return f"{text[:4]}...{text[-4:]}"
