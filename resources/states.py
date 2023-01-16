from aiogram.dispatcher.filters.state import State, StatesGroup

class UserState(StatesGroup):
    user_default_state = State()
    user_authorized = State()
    user_group_required = State()
    user_changing_group = State()
    user_setting_hour = State()
    user_setting_minute = State()