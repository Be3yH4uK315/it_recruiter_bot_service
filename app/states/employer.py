from aiogram.fsm.state import State, StatesGroup

class EmployerSearch(StatesGroup):
    entering_role = State()
    entering_must_skills = State()
    entering_nice_skills = State()
    entering_experience = State()
    entering_location_and_work_modes = State()
    showing_results = State()