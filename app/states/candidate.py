from aiogram.fsm.state import State, StatesGroup


class CandidateRegistration(StatesGroup):
    entering_headline_role = State()
    entering_experience_years = State()
    entering_skills = State()
    entering_location = State()
    entering_work_modes = State()
    uploading_resume = State()
    confirming_profile = State()


class CandidateProfileEdit(StatesGroup):
    choosing_field = State()
    editing_field = State()
