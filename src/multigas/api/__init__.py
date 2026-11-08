"""Optional local application API; install with ``uv sync --extra api``."""


def create_app(*args, **kwargs):
    """Construct the local API without loading optional dependencies on import."""
    from multigas.api.app import create_app as factory

    return factory(*args, **kwargs)
