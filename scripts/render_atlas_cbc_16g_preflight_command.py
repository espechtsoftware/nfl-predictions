#!/usr/bin/env python3
"""Render a fail-closed injected command for the ATLAS 16 GiB preflight."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path


def render(source: bytes, protocol_id: str, prefix: str) -> str:
    """Embed the immutable resource diagnostic and patch only its identity."""
    source_b64 = base64.b64encode(source).decode("ascii")
    wrapper = (
        "import base64\n"
        "ns={'__name__':'atlas_cbc_resource_base',"
        "'__file__':'injected_atlas_cbc_resource_diagnostic.py'}\n"
        f"exec(compile(base64.b64decode({source_b64!r}),ns['__file__'],'exec'),ns)\n"
        f"ns['PROTOCOL_ID']={protocol_id!r}\n"
        f"ns['PREFIX']={prefix!r}\n"
        "ns['ALLOWED_CELLS']={(2024,15)}\n"
        "ns['main']()\n"
    )
    wrapper_b64 = base64.b64encode(wrapper.encode("utf-8")).decode("ascii")
    return f"exec(__import__('base64').b64decode({wrapper_b64!r}))"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--protocol-id", required=True)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    print(render(args.source.read_bytes(), args.protocol_id, args.prefix))


if __name__ == "__main__":
    main()

