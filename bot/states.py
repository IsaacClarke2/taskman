"""
FSM states for Telegram bot.

Defines state groups for multi-step workflows like event editing.
"""

from aiogram.fsm.state import State, StatesGroup


class EventEdit(StatesGroup):
    """States for event editing workflow."""

    # Choosing what to edit
    choose_field = State()

    # Editing specific fields
    edit_title = State()
    edit_time = State()
    edit_location = State()
    edit_description = State()

    # Confirmation
    confirm = State()


class CalendarSelect(StatesGroup):
    """States for calendar selection."""

    choose_calendar = State()


class SettingsFlow(StatesGroup):
    """States for user settings configuration."""

    # Timezone setting
    set_timezone = State()

    # Default calendar
    set_default_calendar = State()

    # Notification preferences
    set_notifications = State()
