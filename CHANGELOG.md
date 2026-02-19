<!-- markdownlint-configure-file {"MD024": false} -->

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-20

### Added

- Slovak media source support and mixed CZ+SK presets.
- Source metadata for country/language/tier/presets to support better filtering and future growth.
- Feed fetch progress callback and cancellation support in the data layer.
- New two-pane desktop UI with:
  - country filters (`ALL`, `CZ`, `SK`)
  - preset selector
  - inline status/progress panel
  - per-source quality table
  - non-modal headlines view
- Quick launcher wrapper script `./czech-media-rss`.
- Feed validation workflow docs for running in `uv` environment.

### Changed

- Main UX redesigned to be more user friendly and transparent about feed quality.
- README updated with UI flow, quick launch wrapper usage, and status legend.
- App and feed-validator user-agent versions bumped to `0.2.0`.

### Fixed

- Removed feed candidates that failed validation (`404` or empty feed).
- Removed Slovak source entries with no working feed candidates.
- Regenerated latest feed validation report after feed cleanup.

## [0.1.0] - 2026-02-18

### Added

- Initial prototype desktop app for Czech media RSS aggregation.
- Searchable multi-select source picker with Czech outlets.
- Top Czech preset and headline limit behavior (10 headlines per source).
- Deterministic scoring to select best feed candidate per source.
- Feed validation script and initial validation report artifacts.
- Initial README and screenshot for public demo context.

