"""Read-only recall synthesis workflow."""

__all__ = ["execute_build_context"]


def __getattr__(name: str):
    if name == "execute_build_context":
        from app.core.use_cases.retrieval.build_context.execute import (
            execute_build_context,
        )

        return execute_build_context
    raise AttributeError(name)
