# Multi-seed factorial report-transport repair

Frozen 2026-08-14 after execution
`analyze-multiseed-candidate-world-v1-blhp5` completed successfully and the
first harvest failed to parse its single JSON log entry. The entry is 102,428
bytes including the following container-exit line and ends inside a JSON
string. Python raises `Unterminated string` at column 102,369. No complete
scientific report or decision was recovered.

The licensed repair changes only report transport: deterministic sorted JSON
is zlib-compressed, base64-encoded and emitted as numbered chunks no larger
than 75,000 characters. The harvester requires exactly one copy of every chunk
and reconstructs the original JSON before applying the unchanged mechanical
and decision checks.

The retry must verify that the original execution is terminal successful, the
stored log begins with the old report marker and is at least 100,000 bytes, and
the first log line's JSON payload fails only with the registered
unterminated-string signature. It preserves the source panels, code, source
arm, candidate/world cells, metrics, gate, CPU, memory and timeout. The retry
image/code and durable execution are recorded separately. The truncated log
and zero-byte report placeholder remain tracked as failure evidence; the
placeholder records that no parseable report was materialized, and neither
artifact may be cited as a result.
