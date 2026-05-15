def iter_exception_chain(exc: BaseException):
    current: BaseException | None = exc
    seen: set[int] = set()
    while current and id(current) not in seen:
        yield current
        seen.add(id(current))
        current = current.__cause__ or current.__context__


def describe_exception(exc: BaseException) -> tuple[str, str]:
    exception_name = type(exc).__name__
    exception_description = str(exc).strip()

    if exception_description:
        return exception_name, exception_description

    for candidate in iter_exception_chain(exc):
        candidate_description = str(candidate).strip()
        if candidate_description:
            return exception_name, candidate_description

    return exception_name, "An unexpected error occurred."
