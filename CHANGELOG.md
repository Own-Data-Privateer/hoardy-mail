# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Also, at the bottom of this file there is a [TODO list](#todo) with planned future changes.

## [v2.6.2] - 2024-09-04

### Changed

- Renamed to `hoardy-mail`.
- Improved documentation.

## [v2.6.1] - 2024-05-11

### Fixed

- From now on, IMAP command conflicts between different IMAP clients discovered by `fetch` turn all following `delete`s into noops, instead of aborting the whole program cycle, as it did before.

  This way parallel IMAP sessions will no longer make `imaparms fetch` to leave unmarked messages on the server and leftovers in `./tmp` of `--maildir`.

- Double \^C at inopportune moment should not generate IMAP server errors anymore.

## [v2.6.0] - 2024-02-12

### Added

- Implemented `--timeout` option.

### Changed

- Improved logging for `gmail-trash`.
- Improved documentation.

## [v2.5.1] - 2024-01-26

### Changed

- Improved logging.
- Improved documentation.
- Updated package metadata and screen capture in the `README.md`.

## [v2.5] - 2024-01-23

### Added

- Implemented `--notify-success`, `--notify-failure`, `--success-cmd`, and `--failure-cmd` options.
- Implemented `--quieter` option.
- Implemented colored output when stderr is a tty.

### Changed

- Improved error handling.

  Weird server-side edge cases (like fetching of a batch of messages succeeding but subsequent marking of some of them failing) will be handled in the most paranoid way possible.
- `fetch --maildir` is no longer experimental.
- `fetch --new-mail-cmd` allows multiple values new.
- Improved generated log messages.

## [v2.4] - 2024-01-13

### Added

- Experimental:
    - Implemented internal MDA/LDA via `fetch --maildir` and related options.

### Changed

- Improved documentation.

### Fixed

- Un-hardcoded SSL protocol version.

## [v2.3] - 2024-01-10

### Changed

- Improved documentation.

### Fixed

- Fixed hooks becoming sticky, which also leaks memory.

## [v2.2.5] - 2023-12-19

### Changed

- Improved documentation.

## [v2.2] - 2023-12-18

### Changed

- Minor improvement in performance and consistency of the output via caching of generated search filters.
- Greatly improved documentation.

### Fixed

- Fixed `list` subcommand being broken.

## [v2.1] - 2023-11-22

### Changed

- Multiples of `--older-than` and `--newer-than` are now allowed.
- Improved documentation.

## [v2.0] - 2023-11-16

### Added

- Implemented `for-each` subcommand, thus completing the original intended feature set for this tool.

- Implemented `AUTH=CRAM-MD5` and command line options for authentication settings.

### Changed

- Replaced `--all` command line option with `--any-seen`, which has a slightly different, simpler, semantics.

- Changed rounding semantics of all `--newer-than*` options to match that of `--older-than*` options.

    It makes more sense this way, `--older-than*` options match as little as possible because they are usually used with `delete`, while `--newer-than*` match as much as possible because they are usually used with `fetch`.

- Improved documentation and package metadata.

### Fixed

- Fixed `delete --method auto` not working properly when using multiple accounts.

## [v1.9] - 2023-11-13

### Added

- Implemented `--new-mail-cmd` option.
- Implemented `SIGUSR1` and `SIGINT` signal handlers that wake up `imaparms fetch --every <seconds>` and similar from sleep between cycles.
- Implemented `--older-than-mtime-of`, `--older-than-timestamp-in`, `--newer-than-mtime-of`, `--newer-than-timestamp-in` filters.
- Implemented `--pass-pinentry` option.

### Changed

- Improved documentation.

### Fixed

- Fixes some rare crashes.

## [v1.7.5] - 2023-11-11

### Changed

- Improved \^C behaviour.
- Improved documentation.

### Fixed

- Fixed crashes when no `--every` is specified.

## [v1.7] - 2023-11-10

### Added

- Implemented `list` and `count --porcelain` subcommands.
- Implemented support for doing actions on multiple servers/accounts with a single invocation.
- `--seen`, `--flagged` filters and their negations can now be specified simultaneously.
- Implemented `--all-folders` and `--not-folders` options.
- Implemented polling/daemon mode with `--every SECONDS` option, this works even for commands for which it does not make much sense, like `list`.

### Changed

- Improved UI.
- Improved documentation.

## [v1.5] - 2023-11-08

### Added

- Implemented `mark` and `fetch` subcommands.

### Changed

- `gmail-trash` subcommand is now a special case of `delete` subcommand.
- Improved documentation.

## [v1.1] - 2023-08-12

### Added

Initial public release.

[v2.6.2]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.6.1...v2.6.2
[v2.6.1]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.6.0...v2.6.1
[v2.6.0]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.5.1...v2.6.0
[v2.5.1]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.5...v2.5.1
[v2.5]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.4...v2.5
[v2.4]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.3...v2.4
[v2.3]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.2.5...v2.3
[v2.2.5]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.2...v2.2.5
[v2.2]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.1...v2.2
[v2.1]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v2.0...v2.1
[v2.0]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v1.9...v2.0
[v1.9]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v1.7.5...v1.9
[v1.7.5]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v1.7...v1.7.5
[v1.7]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v1.5...v1.7
[v1.5]: https://github.com/Own-Data-Privateer/hoardy-mail/compare/v1.1...v1.5
[v1.1]: https://github.com/Own-Data-Privateer/hoardy-mail/releases/tag/v1.1

# TODO

Currently empty.
