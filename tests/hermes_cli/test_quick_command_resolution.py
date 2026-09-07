"""Las entradas vacías del resolvedor no deben romper el despacho."""

import pytest

from hermes_cli.commands import resolve_quick_command


@pytest.mark.parametrize("typed", ["", " ", "/", "///", None])
def test_empty_quick_command_is_not_resolved(typed):
    assert resolve_quick_command({"brief": {"type": "exec"}}, typed) == (None, None)
