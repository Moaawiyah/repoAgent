"""Extraction of function parameters and safe expression rendering."""

import ast

from repoagent.analysis.models import Parameter


def unparse(node) -> str | None:
    """Render an AST expression to source text without raising."""
    try:
        return ast.unparse(node) if node is not None else None
    except (ValueError, AttributeError):
        return None


def decorators(node) -> list[str]:
    """Render decorator expressions of a class or function."""
    return [text for item in node.decorator_list if (text := unparse(item))]


def extract_parameters(node) -> list[Parameter]:
    """Convert ``ast.arguments`` into typed parameters in source order."""
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    padding = [None] * (len(positional) - len(arguments.defaults))
    aligned = padding + list(arguments.defaults)
    parameters: list[Parameter] = []
    for index, (argument, default) in enumerate(zip(positional, aligned, strict=True)):
        kind = (
            "positional_only"
            if index < len(arguments.posonlyargs)
            else "positional_or_keyword"
        )
        parameters.append(_parameter(argument, default, kind))
    if arguments.vararg:
        parameters.append(_parameter(arguments.vararg, None, "var_positional"))
    parameters.extend(
        _parameter(argument, default, "keyword_only")
        for argument, default in zip(
            arguments.kwonlyargs, arguments.kw_defaults, strict=True
        )
    )
    if arguments.kwarg:
        parameters.append(_parameter(arguments.kwarg, None, "var_keyword"))
    return parameters


def _parameter(argument, default, kind: str) -> Parameter:
    return Parameter(
        name=argument.arg,
        annotation=unparse(argument.annotation),
        default=unparse(default),
        kind=kind,
    )
