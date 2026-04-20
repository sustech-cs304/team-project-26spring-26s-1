def iter_exception_chain(exc: BaseException):
    current: BaseException | None = exc
    seen: set[int] = set()
    while current and id(current) not in seen:
        yield current
        seen.add(id(current))
        current = current.__cause__ or current.__context__


def is_langchain_network_failure(exc: BaseException) -> bool:
    network_exception_names = {
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "ConnectionError",
        "PoolTimeout",
        "ProtocolError",
        "ReadError",
        "ReadTimeout",
        "RemoteProtocolError",
        "TimeoutError",
        "TransportError",
        "WriteError",
        "WriteTimeout",
        "RatelimitError"
    }
    network_name_tokens = (
        "Connect",
        "Connection",
        "Disconnect",
        "Network",
        "Protocol",
        "Read",
        "Timeout",
        "Transport",
        "Write",
    )
    network_modules = (
        "aiohttp",
        "anthropic",
        "httpcore",
        "httpx",
        "openai",
    )

    for candidate in iter_exception_chain(exc):
        candidate_type = type(candidate)
        if candidate_type.__name__ in network_exception_names:
            return True
        if (
            candidate_type.__module__.startswith(network_modules)
            and any(token in candidate_type.__name__ for token in network_name_tokens)
        ):
            return True

    return False
