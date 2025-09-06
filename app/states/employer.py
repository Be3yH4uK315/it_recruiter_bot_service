from aiogram.fsm.state import State, StatesGroup

class EmployerSearch(StatesGroup):
    entering_role = State()
    entering_must_skills = State()
    entering_experience = State()
    showing_results = State()