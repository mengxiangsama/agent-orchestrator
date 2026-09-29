"""Validated, stable pagination without modifying input records."""


def paginate(records, page, page_size):
    """Return the requested page sorted by strict-integer record IDs.

    The returned list is independent; its dictionaries may refer to input
    records. Invalid arguments always raise ValueError("INVALID_ARGUMENT").
    """
    if not isinstance(records, list):
        raise ValueError("INVALID_ARGUMENT")
    if type(page) is not int or page < 1:
        raise ValueError("INVALID_ARGUMENT")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("INVALID_ARGUMENT")

    for record in records:
        if (not isinstance(record, dict)
                or "id" not in record
                or type(record["id"]) is not int):
            raise ValueError("INVALID_ARGUMENT")

    ordered = sorted(records, key=lambda record: record["id"])
    start = (page - 1) * page_size
    return ordered[start:start + page_size]
