# tar.zst bootstrap policy

The package fetcher must prove it can decompress before it downloads a multi-gigabyte `.tar.zst` archive. `zstd` may already exist, and some system `tar` builds can read zstd archives; test either capability rather than assuming one.

For new Macs, prefer a small, checksummed bootstrap archive such as `openclaw-bootstrap-tools-<arch>.tar.gz`. A gzip archive can be extracted by the system tar without zstd. It should contain only the required architecture-specific `zstd` binary, license notices, and a manifest with SHA-256 values. The fetcher then prepends its `bin/` to `PATH` and continues with the normal tar.zst package.

Do not silently run Homebrew during extraction. If bootstrap tools are unavailable, present `brew install zstd` as an explicit fallback, begin it before the main package transfer where safe, and retain the failed download for resume.

Implementation acceptance criteria:

- Verify bootstrap archive checksum before extraction.
- Verify the selected zstd binary architecture before use.
- Record `zstd_source` as `system`, `tar`, `bootstrap`, or `homebrew` in the installation report.
- Do not place bootstrap archives or package payloads in private-secrets.
