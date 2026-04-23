# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog.

## [Unreleased]

## [0.1.2] - 2026-04-23

### Fixed

- Decoded Windows command output with platform-aware codec fallbacks instead of assuming UTF-8.
- Restored interface detection for localized Windows `ipconfig` and `route print` output, including Chinese systems.

## [0.1.1] - 2026-04-23

### Fixed

- Added support for localized Windows `ipconfig` output, including Chinese field names.
- Improved Windows default route and primary-interface detection.
- Kept the compact grouped default view working for localized Windows environments.

### Changed

- Simplified version management so releases only need one version bump in `src/nic/__init__.py`.
- Added README release-install instructions, badges, and a reusable GitHub release notes template.

## [0.1.0] - 2026-04-23

### Added

- Initial public release of `nic`.
- Compact grouped default summary for active interfaces.
- `detail`, `physical`, `all`, `show <iface>`, `raw`, and `--json` CLI modes.
- Cross-platform support for macOS, Linux, and Windows.
- GitHub Actions CI and automated GitHub Release packaging.
- English and Simplified Chinese documentation.

[Unreleased]: https://github.com/Kidder1/nic/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Kidder1/nic/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Kidder1/nic/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Kidder1/nic/releases/tag/v0.1.0
