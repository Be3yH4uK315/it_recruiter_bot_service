from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from app.states.candidate import CandidateRegistration
from app.services.api_client import candidate_api_client
from app.keyboards.inline import (
    get_work_modes_keyboard, WorkModeCallback,
    get_skill_kind_keyboard, SkillKindCallback,
    get_skill_level_keyboard, SkillLevelCallback,
    get_confirmation_keyboard, ConfirmationCallback,
    get_contacts_visibility_keyboard, ContactsVisibilityCallback,
)
from app.core.messages import Messages
from app.utils.validators import validate_list_length
from app.handlers.common_blocks import (
    process_add_experience_responsibilities, process_confirm_add_experience,
    process_skill_level, process_confirm_add_skill,
    process_project_links, process_confirm_add_project,
    process_contacts, process_contacts_visibility,
    process_resume_upload, process_avatar_upload
)

router = Router()

# =============================================================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ НАВИГАЦИИ ПО АНКЕТЕ ===
# =============================================================================

async def _ask_for_experience(message: Message, state: FSMContext):
    await state.update_data(experiences=[])
    await message.answer(
        Messages.Profile.ENTER_EXPERIENCE,
        reply_markup=get_confirmation_keyboard(step="start_exp")
    )
    await state.set_state(CandidateRegistration.confirm_start_adding_experience)

async def _ask_for_skills(message: Message, state: FSMContext):
    await state.update_data(skills=[])
    await message.answer(Messages.Profile.ENTER_SKILL_NAME)
    await state.set_state(CandidateRegistration.adding_skill_name)

async def _ask_for_projects(message: Message, state: FSMContext):
    await state.update_data(projects=[])
    await message.answer(
        Messages.Profile.ENTER_PROJECT,
        reply_markup=get_confirmation_keyboard(step="start_project")
    )
    await state.set_state(CandidateRegistration.confirm_start_adding_projects)

async def _ask_for_location(message: Message, state: FSMContext):
    await message.answer(Messages.Profile.ENTER_LOCATION)
    await state.set_state(CandidateRegistration.entering_location)

async def _ask_for_contacts(message: Message, state: FSMContext):
    await message.answer(Messages.Profile.ENTER_CONTACTS)
    await state.set_state(CandidateRegistration.entering_contacts)

async def _ask_for_visibility(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("contacts"):
        await state.update_data(contacts_visibility="hidden")
        await _ask_for_resume(message, state)
        return
    await message.answer(
        Messages.Profile.CONTACTS_VISIBILITY_SELECT,
        reply_markup=get_contacts_visibility_keyboard()
    )
    await state.set_state(CandidateRegistration.choosing_contacts_visibility)

async def _ask_for_resume(message: Message, state: FSMContext):
    await message.answer(Messages.Profile.UPLOAD_RESUME)
    await state.set_state(CandidateRegistration.uploading_resume)

async def _ask_for_avatar(message: Message, state: FSMContext):
    await message.answer(Messages.Profile.UPLOAD_AVATAR)
    await state.set_state(CandidateRegistration.uploading_avatar)

async def _finish_registration(message: Message, state: FSMContext):
    user_data = await state.get_data()
    telegram_id = message.from_user.id

    if not user_data.get('display_name') or not user_data.get('headline_role'):
        await message.answer(Messages.Profile.FINISH_ERROR)
        await state.clear()
        return

    if user_data.get("contacts") and not user_data.get("contacts_visibility"):
        user_data["contacts_visibility"] = "on_request"

    try:
        if 'experiences' in user_data:
            validate_list_length(user_data['experiences'], max_length=10, item_type="опытов работы")
        if 'skills' in user_data:
            validate_list_length(user_data['skills'], max_length=20, item_type="навыков")
        if 'projects' in user_data:
            validate_list_length(user_data['projects'], max_length=10, item_type="проектов")
    except ValueError as e:
        await message.answer(Messages.Profile.EXPERIENCE_LIMIT_EXCEEDED if 'experiences' in str(e) else str(e))
        await state.clear()
        return

    profile_success = await candidate_api_client.update_candidate_profile(telegram_id, user_data)

    if profile_success:
        await message.answer(Messages.Profile.FINISH_OK)
    else:
        await message.answer(Messages.Profile.FINISH_ERROR)

    await state.clear()

# =============================================================================
# === ХЕНДЛЕРЫ FSM (ШАГИ АНКЕТЫ) ===
# =============================================================================

# --- ШАГ 1: ФИО ---
@router.message(CandidateRegistration.entering_display_name)
async def handle_display_name(message: Message, state: FSMContext):
    await state.update_data(display_name=message.text)
    await message.answer(Messages.Profile.ENTER_ROLE)
    await state.set_state(CandidateRegistration.entering_headline_role)

# --- ШАГ 2: Должность ---
@router.message(CandidateRegistration.entering_headline_role)
async def handle_headline_role(message: Message, state: FSMContext):
    await state.update_data(headline_role=message.text)
    await _ask_for_experience(message, state)

# --- ШАГ 3: Блок опыта работы ---
@router.callback_query(ConfirmationCallback.filter(F.step == "start_exp"), CandidateRegistration.confirm_start_adding_experience)
async def handle_start_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
        await state.set_state(CandidateRegistration.adding_exp_company)
    else:
        await callback.message.delete()
        await _ask_for_skills(callback.message, state)
    await callback.answer()

@router.message(CandidateRegistration.adding_exp_company)
async def handle_exp_company(message: Message, state: FSMContext):
    await state.update_data(current_exp_company=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_POSITION)
    await state.set_state(CandidateRegistration.adding_exp_position)

@router.message(CandidateRegistration.adding_exp_position)
async def handle_exp_position(message: Message, state: FSMContext):
    await state.update_data(current_exp_position=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_START)
    await state.set_state(CandidateRegistration.adding_exp_start_date)

@router.message(CandidateRegistration.adding_exp_start_date)
async def handle_exp_start_date(message: Message, state: FSMContext):
    await state.update_data(current_exp_start_date=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_END)
    await state.set_state(CandidateRegistration.adding_exp_end_date)

@router.message(CandidateRegistration.adding_exp_end_date)
async def handle_exp_end_date(message: Message, state: FSMContext):
    await state.update_data(current_exp_end_date=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_RESP)
    await state.set_state(CandidateRegistration.adding_exp_responsibilities)

@router.message(CandidateRegistration.adding_exp_responsibilities)
@router.message(Command("skip"), CandidateRegistration.adding_exp_responsibilities)
async def handle_exp_responsibilities(message: Message, state: FSMContext):
    await process_add_experience_responsibilities(message, state, is_edit_mode=False)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_exp"), CandidateRegistration.confirm_add_another_experience)
async def handle_confirm_add_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    await process_confirm_add_experience(callback, callback_data, state, is_edit_mode=False, next_func=_ask_for_skills, show_profile_func=None)

# --- ШАГ 4: Блок навыков ---
@router.message(CandidateRegistration.adding_skill_name)
async def handle_skill_name(message: Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer(Messages.Profile.ENTER_SKILL_KIND, reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateRegistration.adding_skill_kind)
async def handle_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(Messages.Profile.ENTER_SKILL_LEVEL, reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateRegistration.adding_skill_level)
async def handle_skill_level_cb(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    await process_skill_level(callback, callback_data, state, is_edit_mode=False)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_skill"), CandidateRegistration.confirm_add_another_skill)
async def handle_confirm_add_skill_cb(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    await process_confirm_add_skill(callback, callback_data, state, is_edit_mode=False, next_func=_ask_for_projects, show_profile_func=None)

# --- ШАГ 5: Блок проектов ---
@router.callback_query(ConfirmationCallback.filter(F.step == "start_project"),
                       CandidateRegistration.confirm_start_adding_projects)
async def handle_start_projects(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)
        await state.set_state(CandidateRegistration.adding_project_title)
    else:
        await callback.message.delete()
        await callback.message.answer(Messages.Common.CANCELLED)
        await _ask_for_location(callback.message, state)
    await callback.answer()

@router.message(CandidateRegistration.adding_project_title)
async def handle_project_title(message: Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer(Messages.Profile.ENTER_PROJECT_DESCRIPTION)
    await state.set_state(CandidateRegistration.adding_project_description)

@router.message(CandidateRegistration.adding_project_description)
@router.message(Command("skip"), CandidateRegistration.adding_project_description)
async def handle_project_description(message: Message, state: FSMContext):
    description = message.text if message.text and not message.text.startswith('/skip') else None
    await state.update_data(current_project_description=description)
    await message.answer(Messages.Profile.ENTER_PROJECT_LINKS)
    await state.set_state(CandidateRegistration.adding_project_links)

@router.message(CandidateRegistration.adding_project_links)
@router.message(Command("skip"), CandidateRegistration.adding_project_links)
async def handle_project_links_cb(message: Message, state: FSMContext):
    await process_project_links(message, state, is_edit_mode=False)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_project"), CandidateRegistration.confirm_add_another_project)
async def handle_confirm_add_project_cb(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    await process_confirm_add_project(callback, callback_data, state, is_edit_mode=False, next_func=_ask_for_location, show_profile_func=None)

# --- ШАГ 6-7: Локация и формат работы ---
@router.message(CandidateRegistration.entering_location)
async def handle_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text.capitalize())
    await state.update_data(work_modes=[])
    await message.answer(
        Messages.Profile.WORK_MODE_SELECT,
        reply_markup=get_work_modes_keyboard(selected=set())
    )
    await state.set_state(CandidateRegistration.entering_work_modes)

@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateRegistration.entering_work_modes)
async def handle_work_mode_selection(callback: CallbackQuery, callback_data: WorkModeCallback, state: FSMContext):
    data = await state.get_data()
    selected_modes = set(data.get("work_modes", []))
    if callback_data.mode in selected_modes:
        selected_modes.remove(callback_data.mode)
    else:
        selected_modes.add(callback_data.mode)
    await state.update_data(work_modes=list(selected_modes))
    await callback.message.edit_text(
        Messages.Profile.WORK_MODE_SELECT + f"\nТекущий выбор: {', '.join(selected_modes) if selected_modes else 'пусто'}",
        reply_markup=get_work_modes_keyboard(selected=selected_modes)
    )
    await callback.answer()

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateRegistration.entering_work_modes)
async def handle_work_mode_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_modes = data.get("work_modes", [])
    if not selected_modes:
        await callback.message.edit_text(Messages.Common.INVALID_INPUT)
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Форматы работы выбраны: {', '.join(selected_modes)} ✅",
        reply_markup=None
    )
    await _ask_for_contacts(callback.message, state)
    await callback.answer()

# --- ШАГ 8: Контакты ---
@router.message(CandidateRegistration.entering_contacts)
@router.message(Command("skip"), CandidateRegistration.entering_contacts)
async def handle_contacts_cb(message: Message, state: FSMContext):
    await process_contacts(message, state, is_edit_mode=False, next_func=_ask_for_visibility)

# --- ШАГ 9: Видимость контактов ---
@router.callback_query(ContactsVisibilityCallback.filter(), CandidateRegistration.choosing_contacts_visibility)
async def handle_contacts_visibility_cb(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext):
    await process_contacts_visibility(callback, callback_data, state, is_edit_mode=False, next_func=_ask_for_resume, show_profile_func=None)

# --- ШАГ 10: Резюме ---
@router.message(F.document, CandidateRegistration.uploading_resume)
async def handle_resume_upload_cb(message: Message, state: FSMContext):
    success = await process_resume_upload(message, state, message.from_user.id)
    if success:
        await _ask_for_avatar(message, state)

@router.message(Command("skip"), CandidateRegistration.uploading_resume)
async def handle_skip_resume(message: Message, state: FSMContext):
    await message.answer(Messages.Common.CANCELLED)
    await _ask_for_avatar(message, state)

# --- ШАГ 11: Аватар и завершение ---
@router.message(F.photo, CandidateRegistration.uploading_avatar)
async def handle_avatar_upload_cb(message: Message, state: FSMContext):
    success = await process_avatar_upload(message, state, message.from_user.id)
    if success:
        await _finish_registration(message, state)

@router.message(Command("skip"), CandidateRegistration.uploading_avatar)
async def handle_skip_avatar(message: Message, state: FSMContext):
    await message.answer(Messages.Common.CANCELLED)
    await _finish_registration(message, state)

# --- Общий хендлер отмены ---
@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None: return
    await state.clear()
    await message.answer(Messages.Common.CANCELLED)

# --- Fallback для неверного ввода в любых состояниях CandidateRegistration ---
@router.message(StateFilter("CandidateRegistration:*"))
async def invalid_input(message: Message):
    await message.answer(Messages.Common.INVALID_INPUT)