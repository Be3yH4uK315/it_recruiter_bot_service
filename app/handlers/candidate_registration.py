import re
from urllib.parse import urlparse
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from app.states.candidate import CandidateRegistration
from app.services.api_client import candidate_api_client, file_api_client
from app.keyboards.inline import (
    get_work_modes_keyboard, WorkModeCallback,
    get_skill_kind_keyboard, SkillKindCallback,
    get_skill_level_keyboard, SkillLevelCallback,
    get_confirmation_keyboard, ConfirmationCallback,
    get_contacts_visibility_keyboard, ContactsVisibilityCallback,
)
from app.core.messages import Messages

router = Router()

# Валидация URL
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# =============================================================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ НАВИГАЦИИ ПО АНКЕТЕ ===
# =============================================================================

async def _ask_for_experience(message: Message, state: FSMContext):
    await state.update_data(experiences=[])
    await message.answer(
        Messages.CandidateRegistration.STEP_3,
        reply_markup=get_confirmation_keyboard(step="start_exp")
    )
    await state.set_state(CandidateRegistration.confirm_start_adding_experience)

async def _ask_for_skills(message: Message, state: FSMContext):
    await state.update_data(skills=[])
    await message.answer(Messages.CandidateRegistration.STEP_4)
    await state.set_state(CandidateRegistration.adding_skill_name)

async def _ask_for_projects(message: Message, state: FSMContext):
    await state.update_data(projects=[])
    await message.answer(
        Messages.CandidateRegistration.STEP_5,
        reply_markup=get_confirmation_keyboard(step="start_project")
    )
    await state.set_state(CandidateRegistration.confirm_start_adding_projects)

async def _ask_for_location(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.STEP_6)
    await state.set_state(CandidateRegistration.entering_location)

async def _ask_for_contacts(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.STEP_8)
    await state.set_state(CandidateRegistration.entering_contacts)

async def _ask_for_visibility(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("contacts"):
        await state.update_data(contacts_visibility="hidden")
        await _ask_for_resume(message, state)
        return
    await message.answer(
        Messages.CandidateRegistration.STEP_9,
        reply_markup=get_contacts_visibility_keyboard()
    )
    await state.set_state(CandidateRegistration.choosing_contacts_visibility)

async def _ask_for_resume(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.STEP_10)
    await state.set_state(CandidateRegistration.uploading_resume)

async def _ask_for_avatar(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.STEP_11)
    await state.set_state(CandidateRegistration.uploading_avatar)

async def _finish_registration(message: Message, state: FSMContext):
    user_data = await state.get_data()
    telegram_id = message.from_user.id

    if not user_data.get('display_name') or not user_data.get('headline_role'):
        await message.answer(Messages.CandidateRegistration.FINISH_ERROR)
        await state.clear()
        return

    if user_data.get("contacts") and not user_data.get("contacts_visibility"):
        user_data["contacts_visibility"] = "on_request"

    await message.answer(Messages.CandidateRegistration.FINISH_SAVING)

    profile_success = await candidate_api_client.update_candidate_profile(telegram_id, user_data)

    if profile_success:
        await message.answer(Messages.CandidateRegistration.FINISH_OK)
    else:
        await message.answer(Messages.CandidateRegistration.FINISH_ERROR_SAVE)

    await state.clear()

# =============================================================================
# === ХЕНДЛЕРЫ FSM (ШАГИ АНКЕТЫ) ===
# =============================================================================

# --- ШАГ 1: ФИО ---
@router.message(CandidateRegistration.entering_display_name)
async def handle_display_name(message: Message, state: FSMContext):
    await state.update_data(display_name=message.text)
    await message.answer(Messages.CandidateRegistration.STEP_2)
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
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_EXPERIENCE_COMPANY)
        await state.set_state(CandidateRegistration.adding_exp_company)
    else:
        await callback.message.delete()
        await _ask_for_skills(callback.message, state)
    await callback.answer()

@router.message(CandidateRegistration.adding_exp_company)
async def handle_exp_company(message: Message, state: FSMContext):
    await state.update_data(current_exp_company=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_POSITION)
    await state.set_state(CandidateRegistration.adding_exp_position)

@router.message(CandidateRegistration.adding_exp_position)
async def handle_exp_position(message: Message, state: FSMContext):
    await state.update_data(current_exp_position=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_START)
    await state.set_state(CandidateRegistration.adding_exp_start_date)

@router.message(CandidateRegistration.adding_exp_start_date)
async def handle_exp_start_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d").date()
        await state.update_data(current_exp_start_date=message.text)
        await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_END)
        await state.set_state(CandidateRegistration.adding_exp_end_date)
    except ValueError:
        await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_START_ERROR)

@router.message(CandidateRegistration.adding_exp_end_date)
async def handle_exp_end_date(message: Message, state: FSMContext):
    end_date_str = message.text.lower()
    end_date = None
    if end_date_str not in ['сейчас', 'н.в.', 'present', 'текущее', 'настоящее', 'настоящее время']:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            data = await state.get_data()
            start_date = datetime.strptime(data["current_exp_start_date"], "%Y-%m-%d").date()
            if start_date > end_date:
                await message.answer(Messages.CandidateRegistration.EXPERIENCE_DATE_ORDER_ERROR)
                return
            if end_date > date.today():
                await message.answer(Messages.CandidateRegistration.EXPERIENCE_DATE_FUTURE_ERROR)
                return
            end_date = end_date_str
        except ValueError:
            await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_END_ERROR)
            return

    await state.update_data(current_exp_end_date=end_date)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_RESP)
    await state.set_state(CandidateRegistration.adding_exp_responsibilities)

@router.message(CandidateRegistration.adding_exp_responsibilities)
@router.message(Command("skip"), CandidateRegistration.adding_exp_responsibilities)
async def handle_exp_responsibilities(message: Message, state: FSMContext):
    responsibilities = None
    if message.text and not message.text.startswith('/skip'):
        responsibilities = message.text

    data = await state.get_data()
    new_experience = {
        "company": data.get("current_exp_company"),
        "position": data.get("current_exp_position"),
        "start_date": data.get("current_exp_start_date"),
        "end_date": data.get("current_exp_end_date"),
        "responsibilities": responsibilities
    }
    experiences_list = data.get("experiences", [])
    experiences_list.append(new_experience)
    await state.update_data(experiences=experiences_list)

    await state.update_data(current_exp_company=None, current_exp_position=None, current_exp_start_date=None, current_exp_end_date=None)
    await message.answer(
        Messages.CandidateRegistration.EXPERIENCE_ADDED.format(company=new_experience['company']),
        reply_markup=get_confirmation_keyboard(step="add_exp")
    )
    await state.set_state(CandidateRegistration.confirm_add_another_experience)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_exp"), CandidateRegistration.confirm_add_another_experience)
async def handle_confirm_add_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_EXPERIENCE_COMPANY)
        await state.set_state(CandidateRegistration.adding_exp_company)
    else:
        await callback.message.delete()
        await _ask_for_skills(callback.message, state)
    await callback.answer()

# --- ШАГ 4: Блок навыков ---
@router.message(CandidateRegistration.adding_skill_name)
async def handle_skill_name(message: Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_SKILL_KIND, reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateRegistration.adding_skill_kind)
async def handle_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(Messages.CandidateProfile.ENTER_SKILL_LEVEL, reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateRegistration.adding_skill_level)
async def handle_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    data = await state.get_data()

    new_skill = {
        "skill": data.get("current_skill_name"),
        "kind": data.get("current_skill_kind"),
        "level": callback_data.level
    }

    skills_list = data.get("skills", [])
    skills_list.append(new_skill)
    await state.update_data(skills=skills_list)

    await state.update_data(current_skill_name=None, current_skill_kind=None)

    await callback.message.edit_text(
        Messages.CandidateRegistration.SKILL_ADDED.format(skill=new_skill['skill']),
        reply_markup=get_confirmation_keyboard(step="add_skill")
    )
    await state.set_state(CandidateRegistration.confirm_add_another_skill)
    await callback.answer()

@router.callback_query(ConfirmationCallback.filter(F.step == "add_skill"), CandidateRegistration.confirm_add_another_skill)
async def handle_confirm_add_skill(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_SKILL_NAME)
        await state.set_state(CandidateRegistration.adding_skill_name)
    else:
        await callback.message.delete()
        await _ask_for_projects(callback.message, state)
    await callback.answer()

# --- ШАГ 5: Блок проектов ---
@router.callback_query(ConfirmationCallback.filter(F.step == "start_project"),
                       CandidateRegistration.confirm_start_adding_projects)
async def handle_start_projects(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_PROJECT_TITLE)
        await state.set_state(CandidateRegistration.adding_project_title)
    else:
        await callback.message.delete()
        await callback.message.answer(Messages.Common.CANCELLED)
        await _ask_for_location(callback.message, state)
    await callback.answer()

@router.message(CandidateRegistration.adding_project_title)
async def handle_project_title(message: Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_PROJECT_DESCRIPTION)
    await state.set_state(CandidateRegistration.adding_project_description)

@router.message(CandidateRegistration.adding_project_description)
@router.message(Command("skip"), CandidateRegistration.adding_project_description)
async def handle_project_description(message: Message, state: FSMContext):
    if message.text and not message.text.startswith('/skip'):
        await state.update_data(current_project_description=message.text)
    else:
        await state.update_data(current_project_description=None)

    await message.answer(Messages.CandidateProfile.ENTER_PROJECT_LINKS)
    await state.set_state(CandidateRegistration.adding_project_links)

@router.message(CandidateRegistration.adding_project_links)
@router.message(Command("skip"), CandidateRegistration.adding_project_links)
async def handle_project_links(message: Message, state: FSMContext):
    data = await state.get_data()
    links = {}
    if message.text and not message.text.startswith('/skip'):
        links = {"main_link": message.text}

    new_project = {
        "title": data.get("current_project_title"),
        "description": data.get("current_project_description"),
        "links": links
    }

    projects_list = data.get("projects", [])
    projects_list.append(new_project)
    await state.update_data(projects=projects_list)
    await state.update_data(current_project_title=None, current_project_description=None)

    await message.answer(
        Messages.CandidateRegistration.PROJECT_ADDED.format(title=new_project['title']),
        reply_markup=get_confirmation_keyboard(step="add_project")
    )
    await state.set_state(CandidateRegistration.confirm_add_another_project)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_project"), CandidateRegistration.confirm_add_another_project)
async def handle_confirm_add_project(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_PROJECT_TITLE)
        await state.set_state(CandidateRegistration.adding_project_title)
    else:
        await callback.message.delete()
        await _ask_for_location(callback.message, state)
    await callback.answer()

# --- ШАГ 6-7: Локация и формат работы ---
@router.message(CandidateRegistration.entering_location)
async def handle_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text.capitalize())
    await state.update_data(work_modes=[])
    await message.answer(
        "<b>Шаг 7/11:</b> Выберите желаемые форматы работы: 🏠\n"
        "Текущий выбор: пусто",
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
        "<b>Шаг 7/11:</b> Выберите желаемые форматы работы: 🏠\n"
        f"Текущий выбор: {', '.join(selected_modes) if selected_modes else 'пусто'}",
        reply_markup=get_work_modes_keyboard(selected=selected_modes)
    )
    await callback.answer()

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateRegistration.entering_work_modes)
async def handle_work_mode_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_modes = data.get("work_modes", [])
    if not selected_modes:
        await callback.message.edit_text(Messages.Common.INVALID_INPUT)
        await callback.message.edit_reply_markup(reply_markup=get_work_modes_keyboard(selected=set(selected_modes)))
        await callback.answer()
        return
    await callback.message.edit_text(
        f"<b>Шаг 7/11:</b> Форматы работы выбраны: {', '.join(selected_modes) if selected_modes else 'не выбрано'} ✅",
        reply_markup=None
    )
    await _ask_for_contacts(callback.message, state)
    await callback.answer()

# --- ШАГ 8: Контакты ---
@router.message(CandidateRegistration.entering_contacts)
@router.message(Command("skip"), CandidateRegistration.entering_contacts)
async def handle_contacts(message: Message, state: FSMContext):
    contacts = {}
    if message.text and not message.text.startswith('/skip'):
        pairs = message.text.split(',')
        for pair in pairs:
            try:
                key, value = pair.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "email" and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                    await message.answer(Messages.CandidateRegistration.CONTACTS_EMAIL_ERROR)
                    return
                if key == "phone" and not value.startswith('+'):
                    await message.answer(Messages.CandidateRegistration.CONTACTS_PHONE_WARNING)
                contacts[key] = value
            except ValueError:
                await message.answer(Messages.CandidateRegistration.CONTACTS_FORMAT_ERROR)
                return
    await state.update_data(contacts=contacts)
    await _ask_for_visibility(message, state)

# --- ШАГ 9: Видимость контактов ---
@router.callback_query(ContactsVisibilityCallback.filter(), CandidateRegistration.choosing_contacts_visibility)
async def handle_contacts_visibility(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext):
    await state.update_data(contacts_visibility=callback_data.visibility)
    await callback.message.edit_text(f"✅ Видимость контактов установлена: {callback_data.visibility.capitalize()}")
    await _ask_for_resume(callback.message, state)
    await callback.answer()

# --- ШАГ 10: Резюме ---
@router.message(F.document, CandidateRegistration.uploading_resume)
async def handle_resume_upload(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.RESUME_UPLOADING)
    file_info = await message.bot.get_file(message.document.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    file_response = await file_api_client.upload_file(
        filename=message.document.file_name, file_data=file_data.read(), content_type=message.document.mime_type,
        owner_id=message.from_user.id, file_type='resume'
    )
    if not file_response:
        await message.answer(Messages.CandidateRegistration.RESUME_ERROR)
        return

    await state.update_data(resume_file_id=file_response['id'])
    await message.answer(Messages.CandidateRegistration.RESUME_SUCCESS)
    await _ask_for_avatar(message, state)

@router.message(Command("skip"), CandidateRegistration.uploading_resume)
async def handle_skip_resume(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.RESUME_SKIPPED)
    await _ask_for_avatar(message, state)

# --- ШАГ 11: Аватар и ЗАВЕРШЕНИЕ ---
@router.message(F.photo, CandidateRegistration.uploading_avatar)
async def handle_avatar_upload(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.AVATAR_PROCESSING)
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    file_response = await file_api_client.upload_file(
        filename=f"{photo.file_unique_id}.jpg", file_data=file_data.read(), content_type="image/jpeg",
        owner_id=message.from_user.id, file_type='avatar'
    )
    if file_response:
        await state.update_data(avatar_file_id=file_response['id'])
        await message.answer(Messages.CandidateRegistration.AVATAR_SUCCESS)
    else:
        await message.answer(Messages.CandidateRegistration.AVATAR_ERROR)

    await _finish_registration(message, state)

@router.message(Command("skip"), CandidateRegistration.uploading_avatar)
async def handle_skip_avatar(message: Message, state: FSMContext):
    await message.answer(Messages.CandidateRegistration.AVATAR_SKIPPED)
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