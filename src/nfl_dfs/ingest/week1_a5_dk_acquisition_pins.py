"""Activation pins for the governed Week-1 DraftKings collector.

This file is intentionally separate from the collector implementation so an
independent reviewer can pin the already-reviewed module SHA without changing
the bytes that SHA names.  Every value remains absent in the P0-A candidate;
the live collector and publisher therefore fail before creating a client.
"""

from typing import Final

PINNED_COLLECTOR_SOURCE_COMMIT: Final[str | None] = None
PINNED_COLLECTOR_CODE_SHA256: Final[str | None] = None
PINNED_COLLECTOR_IMAGE_DIGEST: Final[str | None] = None
PINNED_COLLECTOR_SERVICE_ACCOUNT: Final[str | None] = None
PINNED_AUTHORITY_READER_SERVICE_ACCOUNT: Final[str | None] = None
PINNED_AUTHORITY_BUCKET_METAGENERATION: Final[str | None] = None
PINNED_AUTHORITY_RETENTION_SECONDS: Final[int | None] = None
PINNED_ACCEPTANCE_EFFECTIVE_LOCATOR_FAMILIES: Final[
    tuple[tuple[str, str, str], ...] | None
] = None
PINNED_CONTEST_DETAIL_EFFECTIVE_LOCATOR_FAMILIES: Final[
    tuple[tuple[str, str, str], ...] | None
] = None
PINNED_STANDINGS_EFFECTIVE_LOCATOR_FAMILIES: Final[
    tuple[tuple[str, str, str], ...] | None
] = None
