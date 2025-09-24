from aiogram.fsm.state import State, StatesGroup

class EmployerSearch(StatesGroup):
    entering_filters = State()
    showing_results = State()