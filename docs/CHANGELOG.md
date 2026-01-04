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

## [0.9.0] - 2026-01-04

### Added - Phase 1: Cost Optimization
- **dateparser integration** - Local date parsing for Russian/English without OpenAI calls
- **Redis state storage** - Bot pending events stored in Redis with 30 min TTL
- **ARQ background workers** - Async job processing for long-running tasks
- **AI Director service** - Smart routing between local parsing and GPT

### Added - Phase 2: New Integrations
- **Zoom connector** - OAuth 2.0 flow + meeting creation API
- **Yandex Calendar** - CalDAV connector with app-specific password auth
- **Google Meet support** - conferenceData added to Google Calendar events
- **Conference buttons** in bot - "📹 + Google Meet" and "📹 + Zoom"

### Added - Phase 3: Rate Limiting
- Per-user rate limits: 50 GPT calls/hour, 20 Whisper calls/hour
- Message complexity analysis for routing decisions
- Idempotency keys in ARQ jobs to prevent duplicates

### Fixed
- Redis connection cleanup on bot shutdown (aclose())
- CalDAV event=True parameter for better server compatibility
- Proper resource cleanup in all async handlers

### Security
- Rate limiting prevents API abuse
- Idempotency prevents duplicate event creation on retries

## [0.8.0] - 2025-01-04

### Added
- All calendar connectors (Google, Outlook, Apple)
- Notion notes connector
- Web OAuth flows for all integrations
- Dashboard with integration status
- Telegram Login Widget authentication
- JWT session management

### Planned

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
