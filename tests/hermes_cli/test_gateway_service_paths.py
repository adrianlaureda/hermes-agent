from unittest.mock import patch


def test_service_path_skips_nonexistent_node_modules(tmp_path):
    """Service PATH should not include node_modules/.bin if it doesn't exist."""
    from hermes_cli.gateway import _build_service_path_dirs
    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    node_modules_bin = str(tmp_path / "node_modules" / ".bin")
    assert node_modules_bin not in dirs


def test_service_path_includes_node_modules_when_present(tmp_path):
    """Service PATH should include node_modules/.bin when it exists."""
    nm_bin = tmp_path / "node_modules" / ".bin"
    nm_bin.mkdir(parents=True)
    from hermes_cli.gateway import _build_service_path_dirs
    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    assert str(nm_bin) in dirs




def test_service_paths_follow_context_profile(tmp_path):
    """El Node administrado del perfil activo precede a las rutas comunes."""
    from hermes_cli.gateway import _build_service_path_dirs
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    first = tmp_path / "first"
    second = tmp_path / "second"
    for home in (first, second):
        (home / "node/bin").mkdir(parents=True)
    for home, other in ((first, second), (second, first)):
        token = set_hermes_home_override(home)
        try:
            paths = _build_service_path_dirs(project_root=tmp_path / "repo")
            assert str(home / "node/bin") in paths
            assert str(other / "node/bin") not in paths
        finally:
            reset_hermes_home_override(token)
