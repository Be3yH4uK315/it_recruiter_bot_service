from aiogram.fsm.state import State, StatesGroup

# --- CANDIDATE ---
class CandidateRegistration(StatesGroup):
    entering_display_name = State()
    entering_headline_role = State()
    confirm_start_adding_experience = State()
    adding_exp_company = State()
    adding_exp_position = State()
    adding_exp_start_date = State()
    adding_exp_end_date = State()
    adding_exp_responsibilities = State()
    confirm_add_another_experience = State()
    adding_skill_name = State()
    adding_skill_kind = State()
    adding_skill_level = State()
    confirm_add_another_skill = State()
    confirm_start_adding_projects = State()
    adding_project_title = State()
    adding_project_description = State()
    adding_project_links = State()
    confirm_add_another_project = State()
    entering_location = State()
    entering_work_modes = State()
    entering_contacts = State()
    choosing_contacts_visibility = State()
    uploading_resume = State()
    uploading_avatar = State()
    confirm_skip_avatar = State()

class CandidateProfileEdit(StatesGroup):

    editing_visibility = State()
    confirm_edit_another_experience = State()
    editing_exp_responsibilities = State()
    editing_exp_end_date = State()
    editing_exp_start_date = State()
    editing_exp_position = State()
    editing_exp_company = State()
    choosing_field = State()
    editing_field = State()

    editing_skill_name = State()
    editing_skill_kind = State()
    editing_skill_level = State()
    confirm_edit_another_skill = State()

    editing_project_title = State()
    editing_project_description = State()
    editing_project_links = State()
    confirm_edit_another_project = State()

    editing_work_modes = State()

    uploading_resume = State()

    uploading_avatar = State()

    confirm_edit_experience = State()

    editing_contacts = State()
