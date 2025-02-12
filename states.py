from aiogram.fsm.state import State, StatesGroup

class ProfileInfo(StatesGroup):
    weight = State()
    mins_active = State()
    city = State()
    age = State()
    height = State()

class CaloriesCount(StatesGroup):
    calories = State()