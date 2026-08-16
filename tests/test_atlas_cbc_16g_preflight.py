from __future__ import annotations

from scripts.render_atlas_cbc_16g_preflight_command import render


def test_render_patches_only_preflight_identity(capsys) -> None:
    source = b"""
PROTOCOL_ID = 'old'
PREFIX = 'old-prefix'
ALLOWED_CELLS = set()
def main():
    print(PROTOCOL_ID, PREFIX, sorted(ALLOWED_CELLS))
if __name__ == '__main__':
    raise AssertionError('embedded source executed main before identity patch')
"""
    command = render(source, "preflight-v1", "gs://bucket/preflight-v1")
    namespace: dict[str, object] = {}
    exec(command, namespace)
    assert capsys.readouterr().out.strip() == (
        "preflight-v1 gs://bucket/preflight-v1 [(2024, 15)]"
    )

