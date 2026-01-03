# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project documentation
- PROJECT_SPEC.md with full product and engineering requirements
- ARCHITECTURE.md with system design
- CLAUDE.md for Claude Code configuration
- PROJECT_STATUS.md for tracking progress

### Planned
- Project scaffolding (docker-compose, basic structure)
- Telegram bot skeleton
- Database models and migrations
- Google Calendar OAuth integration

---

## Version History

*No releases yet*

---

## Upcoming Release

### [1.0.0] - Target: 5 weeks

**Telegram Bot**
- Text message handling
- Voice message transcription (Whisper)
- Forwarded message handling
- Inline keyboard confirmations
- Event/note type detection (GPT)

**Calendar Integrations**
- Google Calendar (OAuth)
- Microsoft Outlook (OAuth)
- Apple Calendar (CalDAV)
- Multiple calendars per account
- Primary calendar selection
- Conflict detection
- Smart slot suggestions

**Notes Integrations**
- Notion (OAuth)
- Apple Notes (iOS Shortcut)

**Web Panel**
- Telegram Login Widget auth
- Integration management
- Calendar settings
- Apple setup instructions

**Team Mode (API only)**
- Organizations data model
- Permissions system
- Multi-user slot finder
