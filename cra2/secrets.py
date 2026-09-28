"""Keep the configured Groq credential out of application data and SDK logs.

This protects exact known credential values, including the active SDK key when
supplied. It is not a general secret scanner or a defense against transformed
credentials, process inspection, or logging deliberately added by callers.
"""

import logging
import os

_LOG_NAMESPACES = ("groq", "httpx", "httpcore")


def reject_credentials(value, *, additional=()) -> None:
    """Reject a known credential in JSON-like data without echoing its value."""
    credentials = tuple(
        credential
        for credential in (os.environ.get("GROQ_API_KEY"), *additional)
        if isinstance(credential, str) and credential
    )
    if not credentials:
        return
    pending, seen = [value], set()
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if any(credential in item for credential in credentials):
                raise ValueError(
                    "Configured credentials must not appear in application data"
                ) from None
        elif isinstance(item, (dict, list, tuple)) and id(item) not in seen:
            seen.add(id(item))
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            else:
                pending.extend(item)


def configure_sdk_logging() -> None:
    """Silence credential-bearing provider/transport diagnostics process-wide.

    Existing descendants may have their own levels or handlers; disable those
    too. Namespace levels and null handlers also cover lazily created children.
    Assessment metadata remains available through CRA2's structured result.
    """
    names = set(_LOG_NAMESPACES)
    names.update(
        name
        for name in list(logging.Logger.manager.loggerDict)
        if any(name.startswith(namespace + ".") for namespace in _LOG_NAMESPACES)
    )
    for name in names:
        logger = logging.getLogger(name)
        logger.disabled = True
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        if not any(
            isinstance(handler, logging.NullHandler) for handler in logger.handlers
        ):
            logger.addHandler(logging.NullHandler())
