from typing import Dict, Any, List, Optional, TypedDict
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateFSM
from app.services.api_client import candidate_api_client, file_api_client
from app.keyboards.inline import (
    ProfileAction, EditFieldCallback, WorkModeCallback, SkillKindCallback,
    SkillLevelCallback, ConfirmationCallback, ContactsVisibilityCallback,
    get_profile_edit_keyboard, get_work_modes_keyboard, get_skill_kind_keyboard,
    get_skill_level_keyboard, get_confirmation_keyboard, get_contacts_visibility_keyboard,
    get_profile_actions_keyboard,
)
from app.core.messages import Messages
from app.utils.validators import (
    validate_list_length, validate_name,
    validate_headline_role, validate_location,
)
from app.utils.formatters import format_candidate_profile
from app.handlers.candidate_processors import (
    process_add_experience_responsibilities, process_confirm_add_experience,
    process_skill_level, process_confirm_add_skill,
    process_project_links, process_confirm_add_project,
    process_contacts, process_contacts_visibility,
    process_resume_upload, process_avatar_upload,
)
import logging

router = Router()
logger = logging.getLogger(__name__)

class CandidateData(TypedDict, total=False):
    mode: str
    field_to_edit: Optional[str]
    current_field: Optional[str]
    block_type: Optional[str]
    current_step: Optional[str]
    option_type: Optional[str]
    action_type: Optional[str]
    file_type: Optional[str]
    display_name: Optional[str]
    headline_role: Optional[str]
    location: Optional[str]
    work_modes: List[str]
    contacts: Optional[Dict[str, Any]]
    contacts_visibility: Optional[str]
    experiences: List[Dict[str, Any]]
    new_experiences: List[Dict[str, Any]]
    skills: List[Dict[str, Any]]
    new_skills: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    new_projects: List[Dict[str, Any]]
    current_exp_company: Optional[str]
    current_exp_position: Optional[str]
    current_exp_start_date: Optional[str]
    current_exp_end_date: Optional[str]
    current_skill_name: Optional[str]
    current_skill_kind: Optional[str]
    current_project_title: Optional[str]
    current_project_description: Optional[str]
    profile_cache: Optional[Dict[str, Any]]

async def _show_profile(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Показать профиль кандидата."""
    user_id: int = target.from_user.id if isinstance(target, Message) else target.from_user.id
    logger.info(f"User {user_id} requesting profile display")

    data: CandidateData = await state.get_data()
    profile: Optional[Dict[str, Any]] = data.get('profile_cache')
    if not profile:
        try:
            profile = await candidate_api_client.get_candidate_by_telegram_id(user_id)
            if not profile:
                if isinstance(target, Message):
                    await target.answer(Messages.Profile.NOT_FOUND)
                else:
                    await target.message.answer(Messages.Profile.NOT_FOUND)
                return
            await state.update_data(profile_cache=profile)
        except Exception as e:
            logger.error(f"Error fetching profile for user {user_id}: {str(e)}", exc_info=True)
            if isinstance(target, Message):
                await target.answer(Messages.Profile.NOT_FOUND)
            else:
                await target.message.answer(Messages.Profile.NOT_FOUND)
            return

    avatar_url: Optional[str] = None
    if profile.get("avatar_file_id"):
        try:
            avatar_url = await file_api_client.get_download_url_by_file_id(profile["avatar_file_id"])
        except Exception as e:
            logger.warning(f"Error getting avatar URL for user {user_id}: {str(e)}")

    caption = format_candidate_profile(profile)
    has_avatar = bool(profile.get("avatar_file_id"))
    has_resume = bool(profile.get("resumes"))
    keyboard = get_profile_actions_keyboard(has_avatar=has_avatar, has_resume=has_resume)

    target_message = target if isinstance(target, Message) else target.message
    is_callback = isinstance(target, CallbackQuery)
    is_photo_in_callback = bool(target_message.photo) if is_callback else False

    try:
        if avatar_url:
            if is_callback:
                if is_photo_in_callback:
                    await target_message.edit_media(media=InputMediaPhoto(media=avatar_url, caption=caption), reply_markup=keyboard)
                else:
                    await target_message.delete()
                    await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
            else:
                await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
        else:
            if is_callback:
                if is_photo_in_callback:
                    await target_message.delete()
                    await target_message.answer(text=caption, reply_markup=keyboard)
                else:
                    await target_message.edit_text(text=caption, reply_markup=keyboard)
            else:
                await target_message.answer(text=caption, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error displaying profile for user {user_id}: {str(e)}", exc_info=True)
        await target_message.answer(text=caption, reply_markup=keyboard)

    if is_callback:
        await target.answer()
    await state.set_state(CandidateFSM.showing_profile)

async def _ask_for_experience(message: Message, state: FSMContext) -> None:
    """Запросить добавление опыта работы."""
    await state.update_data(experiences=[])
    await message.answer(Messages.Profile.ENTER_EXPERIENCE, reply_markup=get_confirmation_keyboard(step="start_exp"))
    await state.update_data(action_type='start_adding_experience')
    await state.set_state(CandidateFSM.confirm_action)

async def _ask_for_skills(message: Message, state: FSMContext) -> None:
    """Запросить добавление навыков."""
    await state.update_data(skills=[])
    await message.answer(Messages.Profile.ENTER_SKILL_NAME)
    await state.update_data(block_type='skill', current_step='name')
    await state.set_state(CandidateFSM.block_entry)

async def _ask_for_projects(message: Message, state: FSMContext) -> None:
    """Запросить добавление проектов."""
    await state.update_data(projects=[])
    await message.answer(Messages.Profile.ENTER_PROJECT, reply_markup=get_confirmation_keyboard(step="start_project"))
    await state.update_data(action_type='start_adding_project')
    await state.set_state(CandidateFSM.confirm_action)

async def _ask_for_location(message: Message, state: FSMContext) -> None:
    """Запросить ввод местоположения."""
    await message.answer(Messages.Profile.ENTER_LOCATION)
    await state.update_data(current_field='location')
    await state.set_state(CandidateFSM.entering_basic_info)

async def _ask_for_contacts(message: Message, state: FSMContext) -> None:
    """Запросить ввод контактов."""
    await message.answer(Messages.Profile.ENTER_CONTACTS)
    await state.set_state(CandidateFSM.editing_contacts)

async def _ask_for_visibility(message: Message, state: FSMContext) -> None:
    """Запросить выбор видимости контактов."""
    data: CandidateData = await state.get_data()
    if not data.get("contacts"):
        await state.update_data(contacts_visibility="hidden")
        await _ask_for_resume(message, state)
        return
    await message.answer(Messages.Profile.CONTACTS_VISIBILITY_SELECT, reply_markup=get_contacts_visibility_keyboard())
    await state.update_data(option_type='contacts_visibility')
    await state.set_state(CandidateFSM.selecting_options)

async def _ask_for_resume(message: Message, state: FSMContext) -> None:
    """Запросить загрузку резюме."""
    await message.answer(Messages.Profile.UPLOAD_RESUME)
    await state.update_data(file_type='resume')
    await state.set_state(CandidateFSM.uploading_file)

async def _ask_for_avatar(message: Message, state: FSMContext) -> None:
    """Запросить загрузку аватара."""
    await message.answer(Messages.Profile.UPLOAD_AVATAR)
    await state.update_data(file_type='avatar')
    await state.set_state(CandidateFSM.uploading_file)

async def _finish_registration_or_edit(message: Message, state: FSMContext) -> None:
    """Завершить регистрацию или редактирование профиля."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    telegram_id: int = message.from_user.id
    logger.info(f"User {telegram_id} finishing, mode={mode}")

    try:
        if mode == 'register':
            if not data.get('display_name') or not data.get('headline_role'):
                raise ValueError(Messages.Profile.FINISH_ERROR)

            if data.get("contacts") and not data.get("contacts_visibility"):
                data["contacts_visibility"] = "on_request"

        keys = ['experiences', 'skills', 'projects'] if mode == 'register' else ['new_experiences', 'new_skills', 'new_projects']
        max_lengths = [10, 20, 10]
        item_types = ["опытов работы", "навыков", "проектов"]
        for key, max_len, item_type in zip(keys, max_lengths, item_types):
            if key in data:
                validate_list_length(data[key], max_length=max_len, item_type=item_type)

        payload = data.copy()
        if mode == 'edit':
            payload = {data.get('field_to_edit'): payload.get(data.get('field_to_edit'))} if data.get('field_to_edit') else {}
            if 'new_experiences' in data:
                payload['experiences'] = data['new_experiences']
            if 'new_skills' in data:
                payload['skills'] = data['new_skills']
            if 'new_projects' in data:
                payload['projects'] = data['new_projects']

        success = await candidate_api_client.update_candidate_profile(telegram_id, payload)
        msg = Messages.Profile.FINISH_OK if mode == 'register' else Messages.Profile.FIELD_UPDATED
        await message.answer(msg if success else Messages.Profile.FINISH_ERROR)
    except ValueError as e:
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Error finishing for user {telegram_id}: {str(e)}", exc_info=True)
        await message.answer(Messages.Profile.FINISH_ERROR)
    finally:
        await state.clear()
        await _show_profile(message, state)

@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    """Обработка команды /profile."""
    logger.info(f"User {message.from_user.id} started /profile")
    await state.update_data(mode='edit')
    await _show_profile(message, state)

@router.callback_query(ProfileAction.filter())
async def handle_profile_action(callback: CallbackQuery, callback_data: ProfileAction, state: FSMContext) -> None:
    """Обработка действий с профилем."""
    logger.info(f"User {callback.from_user.id} selected action: {callback_data.action}")
    await state.update_data(mode='edit')
    if callback_data.action == "edit":
        await state.set_state(CandidateFSM.choosing_field)
        await callback.message.edit_text(Messages.Profile.CHOOSE_FIELD, reply_markup=get_profile_edit_keyboard())
    elif callback_data.action == "upload_resume":
        await state.update_data(file_type='resume')
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_RESUME)
    elif callback_data.action == "upload_avatar":
        await state.update_data(file_type='avatar')
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_AVATAR)
    elif callback_data.action == "delete_avatar":
        success = await candidate_api_client.delete_avatar(callback.from_user.id)
        msg = Messages.Profile.DELETE_AVATAR_OK if success else Messages.Profile.DELETE_AVATAR_ERROR
        await callback.message.answer(msg)
        await callback.message.delete()
        await state.update_data(profile_cache=None)
        await _show_profile(callback, state)
    elif callback_data.action == "delete_resume":
        success = await candidate_api_client.delete_resume(callback.from_user.id)
        msg = Messages.Profile.DELETE_RESUME_OK if success else Messages.Profile.DELETE_RESUME_ERROR
        await callback.message.answer(msg)
        await callback.message.delete()
        await state.update_data(profile_cache=None)
        await _show_profile(callback, state)
    await callback.answer()

@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateFSM.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext) -> None:
    """Обработка выбора поля для редактирования."""
    field: str = callback_data.field_name
    logger.info(f"User {callback.from_user.id} chose field: {field}")
    prompts: Dict[str, str] = {
        "display_name": Messages.Profile.ENTER_NAME,
        "headline_role": Messages.Profile.ENTER_ROLE,
        "location": Messages.Profile.ENTER_LOCATION,
    }
    if field in prompts:
        await state.update_data(field_to_edit=field, current_field=field)
        await state.set_state(CandidateFSM.entering_basic_info)
        await callback.message.edit_text(prompts[field])
    elif field == "contacts":
        await state.set_state(CandidateFSM.editing_contacts)
        await callback.message.answer(Messages.Profile.ENTER_CONTACTS)
    elif field == "experiences":
        await state.update_data(block_type='experience', current_step='company', new_experiences=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
    elif field == "skills":
        await state.update_data(block_type='skill', current_step='name', new_skills=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_SKILL_NAME)
    elif field == "projects":
        await state.update_data(block_type='project', current_step='title', new_projects=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_PROJECT_TITLE)
    elif field == "work_modes":
        await state.update_data(option_type='work_modes', work_modes=[])
        await state.set_state(CandidateFSM.selecting_options)
        await callback.message.answer(Messages.Profile.WORK_MODE_SELECT, reply_markup=get_work_modes_keyboard(selected=set()))
    await callback.answer()

@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateFSM.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка возврата к просмотру профиля."""
    logger.info(f"User {callback.from_user.id} back to profile")
    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()

@router.message(CandidateFSM.entering_basic_info)
async def handle_basic_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода базовой информации (ФИО, роль, локация)."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    current_field: Optional[str] = data.get('current_field')
    field_to_edit: Optional[str] = data.get('field_to_edit')
    input_text: str = message.text.strip()
    logger.info(f"User {message.from_user.id} in entering_basic_info, mode={mode}, current_field={current_field}, input={input_text}")
    
    prompts = {
    'display_name': Messages.Profile.ENTER_NAME,
    'headline_role': Messages.Profile.ENTER_ROLE,
    'location': Messages.Profile.ENTER_LOCATION,
    }

    try:
        if mode == 'edit' and field_to_edit:
            validators = {
                'display_name': validate_name,
                'headline_role': validate_headline_role,
                'location': validate_location,
            }
            if field_to_edit in validators and not validators[field_to_edit](input_text):
                await message.answer(Messages.Common.INVALID_INPUT)
                await message.answer(prompts[field_to_edit])
                return
            update_payload = {field_to_edit: input_text if field_to_edit != 'location' else input_text.capitalize()}
            success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)
            msg = Messages.Profile.FIELD_UPDATED if success else Messages.Profile.FIELD_UPDATE_ERROR
            await message.answer(msg)
            await state.clear()
            await state.update_data(profile_cache=None)
            await _show_profile(message, state)
        elif mode == 'register':
            if current_field == 'display_name':
                if not validate_name(input_text):
                    await message.answer(Messages.Common.INVALID_INPUT)
                    await message.answer(Messages.Profile.ENTER_NAME)
                    return
                await state.update_data(display_name=input_text)
                await message.answer(Messages.Profile.ENTER_ROLE)
                await state.update_data(current_field='headline_role')
            elif current_field == 'headline_role':
                if not validate_headline_role(input_text):
                    await message.answer(Messages.Common.INVALID_INPUT)
                    await message.answer(Messages.Profile.ENTER_ROLE)
                    return
                await state.update_data(headline_role=input_text)
                await _ask_for_experience(message, state)
            elif current_field == 'location':
                if not validate_location(input_text):
                    await message.answer(Messages.Common.INVALID_INPUT)
                    await message.answer(Messages.Profile.ENTER_LOCATION)
                    return
                await state.update_data(location=input_text.capitalize())
                await state.update_data(work_modes=[])
                await message.answer(Messages.Profile.WORK_MODE_SELECT, reply_markup=get_work_modes_keyboard(selected=set()))
                await state.update_data(option_type='work_modes')
                await state.set_state(CandidateFSM.selecting_options)
    except Exception as e:
        logger.error(f"Error in handle_basic_input for user {message.from_user.id}: {str(e)}", exc_info=True)
        await message.answer(Messages.Common.INVALID_INPUT)

@router.message(CandidateFSM.block_entry)
async def handle_block_entry(message: Message, state: FSMContext) -> None:
    """Обработка ввода блоков (опыт, навык, проект)."""
    data: CandidateData = await state.get_data()
    block_type: Optional[str] = data.get('block_type')
    current_step: Optional[str] = data.get('current_step')
    mode: str = data.get('mode', 'register')
    logger.info(f"User {message.from_user.id} in block_entry, block_type={block_type}, current_step={current_step}")

    try:
        if block_type == 'experience':
            if current_step == 'company':
                await state.update_data(current_exp_company=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_POSITION)
                await state.update_data(current_step='position')
            elif current_step == 'position':
                await state.update_data(current_exp_position=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_START)
                await state.update_data(current_step='start_date')
            elif current_step == 'start_date':
                await state.update_data(current_exp_start_date=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_END)
                await state.update_data(current_step='end_date')
            elif current_step == 'end_date':
                await state.update_data(current_exp_end_date=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_RESP)
                await state.update_data(current_step='responsibilities')
            elif current_step == 'responsibilities':
                await process_add_experience_responsibilities(message, state, mode=mode)
        elif block_type == 'skill':
            if current_step == 'name':
                await state.update_data(current_skill_name=message.text)
                await message.answer(Messages.Profile.ENTER_SKILL_KIND, reply_markup=get_skill_kind_keyboard())
                await state.update_data(option_type='skill_kind')
                await state.set_state(CandidateFSM.selecting_options)
        elif block_type == 'project':
            if current_step == 'title':
                await state.update_data(current_project_title=message.text)
                await message.answer(Messages.Profile.ENTER_PROJECT_DESCRIPTION)
                await state.update_data(current_step='description')
            elif current_step == 'description':
                description = message.text if message.text and not message.text.startswith('/skip') else None
                await state.update_data(current_project_description=description)
                await message.answer(Messages.Profile.ENTER_PROJECT_LINKS)
                await state.update_data(current_step='links')
            elif current_step == 'links':
                await process_project_links(message, state, mode=mode)
    except Exception as e:
        logger.error(f"Error in handle_block_entry for user {message.from_user.id}: {str(e)}", exc_info=True)
        await message.answer(Messages.Common.INVALID_INPUT)

@router.callback_query(ConfirmationCallback.filter(), CandidateFSM.confirm_action)
async def handle_confirm(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext) -> None:
    """Обработка подтверждений действий."""
    data: CandidateData = await state.get_data()
    action_type: Optional[str] = data.get('action_type')
    mode: str = data.get('mode', 'register')
    logger.info(f"User {callback.from_user.id} in confirm_action, action_type={action_type}")

    try:
        if action_type == 'start_adding_experience':
            if callback_data.action == "yes":
                await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
                await state.update_data(block_type='experience', current_step='company')
                await state.set_state(CandidateFSM.block_entry)
            else:
                await callback.message.delete()
                await _ask_for_skills(callback.message, state)
        elif action_type == 'add_another_exp':
            await process_confirm_add_experience(callback, callback_data, state, mode=mode, next_func=_ask_for_skills, show_profile_func=_show_profile)
        elif action_type == 'start_adding_project':
            if callback_data.action == "yes":
                await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)
                await state.update_data(block_type='project', current_step='title')
                await state.set_state(CandidateFSM.block_entry)
            else:
                await callback.message.delete()
                await _ask_for_location(callback.message, state)
        elif action_type == 'add_another_project':
            await process_confirm_add_project(callback, callback_data, state, mode=mode, next_func=_ask_for_location, show_profile_func=_show_profile)
        elif action_type == 'add_another_skill':
            await process_confirm_add_skill(callback, callback_data, state, mode=mode, next_func=_ask_for_projects, show_profile_func=_show_profile)
    except Exception as e:
        logger.error(f"Error in handle_confirm for user {callback.from_user.id}: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.INVALID_INPUT)
    await callback.answer()

@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateFSM.selecting_options)
async def handle_work_mode_selection(callback: CallbackQuery, callback_data: WorkModeCallback, state: FSMContext) -> None:
    """Обработка выбора форматов работы."""
    data: CandidateData = await state.get_data()
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

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateFSM.selecting_options)
async def handle_work_mode_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка завершения выбора форматов работы."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    selected_modes: List[str] = data.get("work_modes", [])
    logger.info(f"User {callback.from_user.id} finished work mode selection: {selected_modes}")
    if not selected_modes:
        await callback.message.edit_text(Messages.Common.INVALID_INPUT)
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Форматы работы выбраны: {', '.join(selected_modes)} ✅",
        reply_markup=None
    )
    if mode == 'edit':
        update_payload = {"work_modes": selected_modes}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        msg = Messages.Profile.WORK_MODE_UPDATED if success else Messages.Profile.WORK_MODE_UPDATE_ERROR
        await callback.message.answer(msg)
        await state.clear()
        await state.update_data(profile_cache=None)
        await _show_profile(callback, state)
    else:
        await _ask_for_contacts(callback.message, state)
    await callback.answer()

@router.callback_query(SkillKindCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext) -> None:
    """Обработка выбора типа навыка."""
    logger.info(f"User {callback.from_user.id} selected skill kind: {callback_data.kind}")
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(
        Messages.Profile.ENTER_SKILL_LEVEL,
        reply_markup=get_skill_level_keyboard()
    )
    await state.update_data(option_type='skill_level')
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext) -> None:
    """Обработка выбора уровня навыка."""
    logger.info(f"User {callback.from_user.id} selected skill level: {callback_data.level}")
    await state.update_data(current_skill_level=callback_data.level)
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    await process_skill_level(callback, callback_data, state, mode=mode)

@router.message(CandidateFSM.editing_contacts)
@router.message(Command("skip"), CandidateFSM.editing_contacts)
async def handle_contacts_edit(message: Message, state: FSMContext) -> None:
    """Обработка ввода контактов."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    await process_contacts(message, state, mode=mode, next_func=_ask_for_visibility, show_profile_func=_show_profile)

@router.callback_query(ContactsVisibilityCallback.filter(), CandidateFSM.selecting_options)
async def handle_contacts_visibility_edit(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext) -> None:
    """Обработка выбора видимости контактов."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    await process_contacts_visibility(callback, callback_data, state, mode=mode, next_func=_ask_for_resume, show_profile_func=_show_profile)

@router.message(F.document, CandidateFSM.uploading_file)
async def handle_resume_upload_edit(message: Message, state: FSMContext) -> None:
    """Обработка загрузки резюме."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    success = await process_resume_upload(message, state, message.from_user.id)
    if success:
        await state.update_data(profile_cache=None)
        if mode == 'edit':
            await state.clear()
            await message.delete()
            await _show_profile(message, state)
        else:
            await _ask_for_avatar(message, state)

@router.message(F.photo, CandidateFSM.uploading_file)
async def handle_avatar_upload_edit(message: Message, state: FSMContext) -> None:
    """Обработка загрузки аватара."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    success = await process_avatar_upload(message, state, message.from_user.id)
    if success:
        await state.update_data(profile_cache=None)
        if mode == 'edit':
            await state.clear()
            await message.delete()
            await _show_profile(message, state)
        else:
            await _finish_registration_or_edit(message, state)

@router.message(Command("skip"), CandidateFSM.uploading_file)
async def handle_skip_uploading(message: Message, state: FSMContext) -> None:
    """Обработка пропуска загрузки файла."""
    data: CandidateData = await state.get_data()
    mode: str = data.get('mode', 'register')
    file_type: Optional[str] = data.get('file_type')
    logger.info(f"User {message.from_user.id} skipped uploading {file_type}")
    await message.answer(Messages.Common.CANCELLED)
    if mode == 'edit':
        await state.clear()
        await _show_profile(message, state)
    else:
        if file_type == 'resume':
            await _ask_for_avatar(message, state)
        elif file_type == 'avatar':
            await _finish_registration_or_edit(message, state)

@router.message(Command("cancel"), StateFilter(CandidateFSM))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """Обработка команды /cancel для отмены текущего действия."""
    logger.info(f"User {message.from_user.id} cancelled FSM")
    await state.clear()
    await message.answer(Messages.Common.CANCELLED)

@router.message(StateFilter(CandidateFSM))
async def invalid_input(message: Message, state: FSMContext) -> None:
    """Fallback для неверного ввода в FSM."""
    current_state: Optional[str] = await state.get_state()
    data: Dict[str, Any] = await state.get_data()
    current_field: Optional[str] = data.get('current_field')
    block_type: Optional[str] = data.get('block_type')
    current_step: Optional[str] = data.get('current_step')
    logger.warning(f"Invalid input from user {message.from_user.id} in state {current_state}: {message.text}")

    await message.answer(Messages.Common.INVALID_INPUT)
    if current_state == CandidateFSM.entering_basic_info:
        if current_field == 'display_name':
            await message.answer(Messages.Profile.ENTER_NAME)
        elif current_field == 'headline_role':
            await message.answer(Messages.Profile.ENTER_ROLE)
        elif current_field == 'location':
            await message.answer(Messages.Profile.ENTER_LOCATION)
        else:
            await message.answer(Messages.Profile.ENTER_NAME)
            await state.update_data(current_field='display_name')
    elif current_state == CandidateFSM.block_entry:
        if block_type == 'experience':
            if current_step == 'company':
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
            elif current_step == 'position':
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_POSITION)
            elif current_step == 'start_date':
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_START)
            elif current_step == 'end_date':
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_END)
            elif current_step == 'responsibilities':
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_RESP)
        elif block_type == 'skill' and current_step == 'name':
            await message.answer(Messages.Profile.ENTER_SKILL_NAME)
        elif block_type == 'project':
            if current_step == 'title':
                await message.answer(Messages.Profile.ENTER_PROJECT_TITLE)
            elif current_step == 'description':
                await message.answer(Messages.Profile.ENTER_PROJECT_DESCRIPTION)
            elif current_step == 'links':
                await message.answer(Messages.Profile.ENTER_PROJECT_LINKS)
    elif current_state == CandidateFSM.editing_contacts:
        await message.answer(Messages.Profile.ENTER_CONTACTS)