from aiogram.fsm.state import State, StatesGroup


class CandidateRegistration(StatesGroup):
    entering_headline_role = State()
    entering_experience_years = State()
    entering_skills = State()
