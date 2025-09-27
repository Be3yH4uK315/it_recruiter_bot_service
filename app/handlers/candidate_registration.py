from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from typing import Dict, Any, List, Optional
from app.states.candidate import CandidateFSM
from app.services.api_client import candidate_api_client, file_api_client
from app.keyboards.inline import (
    get_profile_actions_keyboard, get_work_modes_keyboard, WorkModeCallback,
    get_skill_kind_keyboard, SkillKindCallback,
    get_skill_level_keyboard, SkillLevelCallback,
    get_confirmation_keyboard, ConfirmationCallback,
    get_contacts_visibility_keyboard, ContactsVisibilityCallback,
)
from app.core.messages import Messages
from app.utils.validators import (
    Experience, Project, Skill, validate_list_length, validate_name, validate_headline_role, validate_location
)
from app.handlers.common_blocks import (
    process_add_experience_responsibilities, process_confirm_add_experience,
    process_skill_level, process_confirm_add_skill,
    process_project_links, process_confirm_add_project,
    process_contacts, process_contacts_visibility,
    process_resume_upload, process_avatar_upload
)
from app.utils.formatters import format_candidate_profile
import logging

router = Router()
logger = logging.getLogger(__name__)

async def _show_profile(message: Message | CallbackQuery, state: FSMContext) -> None:
    """Отображение профиля кандидата."""
    await state.clear()
    target_message = message.message if isinstance(message, CallbackQuery) else message
    user_id: int = message.from_user.id
    logger.info(f"User {user_id} requesting profile display")

    profile: Optional[Dict[str, Any]] = await candidate_api_client.get_candidate_by_telegram_id(user_id)
    if not profile:
        await target_message.answer(Messages.Profile.NOT_FOUND)
        return

    avatar_url: Optional[str] = None
    if profile.get("avatar_file_id"):
        avatar_url = await file_api_client.get_download_url_by_file_id(profile["avatar_file_id"])

    caption = format_candidate_profile(profile)
    has_avatar = bool(profile.get("avatar_file_id"))
    has_resume = bool(profile.get("resumes"))
    keyboard = get_profile_actions_keyboard(has_avatar=has_avatar, has_resume=has_resume)

    is_callback = isinstance(message, CallbackQuery)
    is_photo_in_callback = bool(target_message.photo) if is_callback else False

    try:
        if is_callback:
            if avatar_url:
                if is_photo_in_callback:
                    await target_message.edit_media(media=InputMediaPhoto(media=avatar_url, caption=caption),
                                                    reply_markup=keyboard)
                else:
                    await target_message.delete()
                    await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
            else:
                if is_photo_in_callback:
                    await target_message.delete()
                    await target_message.answer(text=caption, reply_markup=keyboard)
                else:
                    await target_message.edit_text(text=caption, reply_markup=keyboard)
        else:
            if avatar_url:
                await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
            else:
                await target_message.answer(text=caption, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error displaying profile for user {user_id}: {str(e)}")
        await target_message.answer(text=caption, reply_markup=keyboard)

    if is_callback:
        await message.answer()
    await state.set_state(CandidateFSM.showing_profile)

async def _ask_for_experience(message: Message, state: FSMContext) -> None:
    """Запрос на добавление опыта работы."""
    await state.update_data(experiences=[])
    await message.answer(Messages.Profile.ENTER_EXPERIENCE, reply_markup=get_confirmation_keyboard(step="start_exp"))
    await state.update_data(action_type='start_adding_experience')
    await state.set_state(CandidateFSM.confirm_action)

async def _ask_for_skills(message: Message, state: FSMContext) -> None:
    """Запрос на добавление навыков."""
    await state.update_data(skills=[])
    await message.answer(Messages.Profile.ENTER_SKILL_NAME)
    await state.update_data(block_type='skill', current_step='name')
    await state.set_state(CandidateFSM.block_entry)

async def _ask_for_projects(message: Message, state: FSMContext) -> None:
    """Запрос на добавление проектов."""
    await state.update_data(projects=[])
    await message.answer(Messages.Profile.ENTER_PROJECT, reply_markup=get_confirmation_keyboard(step="start_project"))
    await state.update_data(action_type='start_adding_project')
    await state.set_state(CandidateFSM.confirm_action)

async def _ask_for_location(message: Message, state: FSMContext) -> None:
    """Запрос на ввод локации."""
    await message.answer(Messages.Profile.ENTER_LOCATION)
    await state.update_data(current_field='location')
    await state.set_state(CandidateFSM.entering_basic_info)

async def _ask_for_contacts(message: Message, state: FSMContext) -> None:
    """Запрос на ввод контактов."""
    await message.answer(Messages.Profile.ENTER_CONTACTS)
    await state.set_state(CandidateFSM.editing_contacts)

async def _ask_for_visibility(message: Message, state: FSMContext) -> None:
    """Запрос на видимость контактов."""
    data: Dict[str, Any] = await state.get_data()
    if not data.get("contacts"):
        await state.update_data(contacts_visibility="hidden")
        await _ask_for_resume(message, state)
        return
    await message.answer(Messages.Profile.CONTACTS_VISIBILITY_SELECT, reply_markup=get_contacts_visibility_keyboard())
    await state.update_data(option_type='contacts_visibility')
    await state.set_state(CandidateFSM.selecting_options)

async def _ask_for_resume(message: Message, state: FSMContext) -> None:
    """Запрос на загрузку резюме."""
    await message.answer(Messages.Profile.UPLOAD_RESUME)
    await state.update_data(file_type='resume')
    await state.set_state(CandidateFSM.uploading_file)

async def _ask_for_avatar(message: Message, state: FSMContext) -> None:
    """Запрос на загрузку аватара."""
    await message.answer(Messages.Profile.UPLOAD_AVATAR)
    await state.update_data(file_type='avatar')
    await state.set_state(CandidateFSM.uploading_file)

async def _finish_registration(message: Message, state: FSMContext) -> None:
    """Завершение регистрации или редактирования."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    telegram_id: int = message.from_user.id
    logger.info(f"User {telegram_id} finishing, mode={mode}")

    if mode == 'register':
        if not data.get('display_name') or not data.get('headline_role'):
            await message.answer(Messages.Profile.FINISH_ERROR)
            await state.clear()
            return

        if data.get("contacts") and not data.get("contacts_visibility"):
            data["contacts_visibility"] = "on_request"

        try:
            if 'experiences' in data:
                validate_list_length(data['experiences'], max_length=10, item_type="опытов работы")
            if 'skills' in data:
                validate_list_length(data['skills'], max_length=20, item_type="навыков")
            if 'projects' in data:
                validate_list_length(data['projects'], max_length=10, item_type="проектов")
        except ValueError as e:
            await message.answer(str(e))
            await state.clear()
            return

    profile_success = await candidate_api_client.update_candidate_profile(telegram_id, data)

    if profile_success:
        await message.answer(Messages.Profile.FINISH_OK if mode == 'register' else Messages.Profile.FIELD_UPDATED)
    else:
        await message.answer(Messages.Profile.FINISH_ERROR)

    await state.clear()
    await _show_profile(message, state)

@router.message(CandidateFSM.entering_basic_info)
async def handle_basic_input(message: Message, state: FSMContext) -> None:
    """Обработка базового ввода (имя, роль, локация)."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    current_field: Optional[str] = data.get('current_field')
    field_to_edit: Optional[str] = data.get('field_to_edit')
    input_text: str = message.text.strip()
    logger.info(f"User {message.from_user.id} in entering_basic_info, mode={mode}, current_field={current_field}, field_to_edit={field_to_edit}, input={message.text}")

    if current_field is None:
        logger.warning(f"No current_field for user {message.from_user.id}")
        await message.answer(Messages.Common.INVALID_INPUT)
        if mode == 'register':
            await message.answer(Messages.Profile.ENTER_NAME)
            await state.update_data(current_field='display_name')
        return

    if mode == 'edit' and field_to_edit:
        if field_to_edit != current_field:
            logger.warning(f"Mismatch field_to_edit {field_to_edit} and current_field {current_field} for user {message.from_user.id}")
            await message.answer(Messages.Common.INVALID_INPUT)
            return
        try:
            if field_to_edit == 'display_name' and not validate_name(input_text):
                await message.answer(Messages.Common.INVALID_INPUT)
                await message.answer(Messages.Profile.ENTER_NAME)
                return
            elif field_to_edit == 'headline_role' and not validate_headline_role(input_text):
                await message.answer(Messages.Common.INVALID_INPUT)
                await message.answer(Messages.Profile.ENTER_ROLE)
                return
            elif field_to_edit == 'location' and not validate_location(input_text):
                await message.answer(Messages.Common.INVALID_INPUT)
                await message.answer(Messages.Profile.ENTER_LOCATION)
                return

            update_payload = {field_to_edit: input_text}
            success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)
            msg = Messages.Profile.FIELD_UPDATED if success else Messages.Profile.FIELD_UPDATE_ERROR
            await message.answer(msg)
            await state.clear()
            await message.delete()
            await _show_profile(message, state)
        except Exception as e:
            logger.error(f"Error in edit mode for user {message.from_user.id}: {str(e)}")
            await message.answer(Messages.Common.INVALID_INPUT)
            if field_to_edit == 'display_name':
                await message.answer(Messages.Profile.ENTER_NAME)
            elif field_to_edit == 'headline_role':
                await message.answer(Messages.Profile.ENTER_ROLE)
            elif field_to_edit == 'location':
                await message.answer(Messages.Profile.ENTER_LOCATION)
            return
    elif mode == 'register':
        try:
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
            else:
                await message.answer(Messages.Common.INVALID_INPUT)
                await message.answer(Messages.Profile.ENTER_NAME)
                await state.update_data(current_field='display_name')
        except Exception as e:
            logger.error(f"Error in register mode for user {message.from_user.id}: {str(e)}")
            await message.answer(Messages.Common.INVALID_INPUT)
            if current_field == 'display_name':
                await message.answer(Messages.Profile.ENTER_NAME)
            elif current_field == 'headline_role':
                await message.answer(Messages.Profile.ENTER_ROLE)
            elif current_field == 'location':
                await message.answer(Messages.Profile.ENTER_LOCATION)
    else:
        logger.warning(f"Invalid mode {mode} for user {message.from_user.id}")
        await message.answer(Messages.Common.INVALID_INPUT)
        await message.answer(Messages.Profile.ENTER_NAME)
        await state.update_data(current_field='display_name')

@router.message(CandidateFSM.block_entry)
async def handle_block_entry(message: Message, state: FSMContext) -> None:
    """Обработка ввода блоков (опыт, навыки, проекты)."""
    data: Dict[str, Any] = await state.get_data()
    block_type: Optional[str] = data.get('block_type')
    current_step: Optional[str] = data.get('current_step')
    mode: str = data.get('mode', 'register')
    if block_type is None or current_step is None:
        logger.warning(f"Missing block_type or current_step for user {message.from_user.id}")
        await message.answer(Messages.Common.INVALID_INPUT)
        return
    logger.info(f"User {message.from_user.id} in block_entry, block_type={block_type}, current_step={current_step}, mode={mode}")

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
    else:
        await message.answer(Messages.Common.INVALID_INPUT)

@router.callback_query(ConfirmationCallback.filter(), CandidateFSM.confirm_action)
async def handle_confirm(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext) -> None:
    """Обработка подтверждений."""
    data: Dict[str, Any] = await state.get_data()
    action_type: Optional[str] = data.get('action_type')
    mode: str = data.get('mode', 'register')
    if action_type is None:
        logger.warning(f"No action_type for user {callback.from_user.id}")
        await callback.answer(Messages.Common.INVALID_INPUT)
        return
    logger.info(f"User {callback.from_user.id} in confirm_action, action_type={action_type}, mode={mode}")
    if action_type == 'start_adding_experience':
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
            await state.update_data(block_type='experience', current_step='company')
            await state.set_state(CandidateFSM.block_entry)
        else:
            await callback.message.delete()
            await _ask_for_skills(callback.message, state)
    elif action_type == 'add_another_exp':
        await process_confirm_add_experience(
            callback, callback_data, state, mode=mode,
            next_func=_ask_for_skills, show_profile_func=_show_profile
        )
    elif action_type == 'start_adding_project':
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)
            await state.update_data(block_type='project', current_step='title')
            await state.set_state(CandidateFSM.block_entry)
        else:
            await callback.message.delete()
            await _ask_for_location(callback.message, state)
    elif action_type == 'add_another_project':
        await process_confirm_add_project(
            callback, callback_data, state, mode=mode,
            next_func=_ask_for_location, show_profile_func=_show_profile
        )
    elif action_type == 'add_another_skill':
        await process_confirm_add_skill(
            callback, callback_data, state, mode=mode,
            next_func=_ask_for_projects, show_profile_func=_show_profile
        )
    await callback.answer()

@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateFSM.selecting_options)
async def handle_work_mode_selection(callback: CallbackQuery, callback_data: WorkModeCallback, state: FSMContext) -> None:
    """Выбор формата работы."""
    data: Dict[str, Any] = await state.get_data()
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
    """Завершение выбора формата работы."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    selected_modes: List[str] = data.get("work_modes", [])
    logger.info(f"User {callback.from_user.id} finished work mode selection: {selected_modes}, mode={mode}")
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
        await _show_profile(callback, state)
    else:
        await _ask_for_contacts(callback.message, state)
    await callback.answer()

@router.callback_query(SkillKindCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext) -> None:
    """Выбор типа навыка."""
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(
        Messages.Profile.ENTER_SKILL_LEVEL,
        reply_markup=get_skill_level_keyboard()
    )
    await state.update_data(option_type='skill_level')
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext) -> None:
    """Выбор уровня навыка."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    await process_skill_level(callback, callback_data, state, mode=mode)

@router.message(CandidateFSM.editing_contacts)
@router.message(Command("skip"), CandidateFSM.editing_contacts)
async def handle_contacts(message: Message, state: FSMContext) -> None:
    """Обработка ввода контактов."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    logger.info(f"User {message.from_user.id} entered contacts, mode={mode}")
    await process_contacts(message, state, mode=mode, next_func=_ask_for_visibility, show_profile_func=_show_profile)

@router.callback_query(ContactsVisibilityCallback.filter(), CandidateFSM.selecting_options)
async def handle_contacts_visibility(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext) -> None:
    """Выбор видимости контактов."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    logger.info(f"User {callback.from_user.id} selected contacts visibility: {callback_data.visibility}, mode={mode}")
    await process_contacts_visibility(
        callback, callback_data, state, mode=mode,
        next_func=_ask_for_resume, show_profile_func=_show_profile
    )

@router.message(F.document, CandidateFSM.uploading_file)
async def handle_resume_upload(message: Message, state: FSMContext) -> None:
    """Загрузка резюме."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    logger.info(f"User {message.from_user.id} uploading resume, mode={mode}")
    success = await process_resume_upload(message, state, message.from_user.id)
    if success:
        if mode == 'edit':
            await state.clear()
            await message.delete()
            await _show_profile(message, state)
        else:
            await _ask_for_avatar(message, state)

@router.message(Command("skip"), CandidateFSM.uploading_file)
async def handle_skip_resume(message: Message, state: FSMContext) -> None:
    """Пропуск загрузки резюме."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    file_type: Optional[str] = data.get('file_type')
    logger.info(f"User {message.from_user.id} skipped uploading {file_type}, mode={mode}")
    if file_type == 'resume':
        await message.answer(Messages.Common.CANCELLED)
        if mode == 'edit':
            await state.clear()
            await _show_profile(message, state)
        else:
            await _ask_for_avatar(message, state)
    elif file_type == 'avatar':
        await message.answer(Messages.Common.CANCELLED)
        if mode == 'edit':
            await state.clear()
            await _show_profile(message, state)
        else:
            await _finish_registration(message, state)

@router.message(F.photo, CandidateFSM.uploading_file)
async def handle_avatar_upload(message: Message, state: FSMContext) -> None:
    """Загрузка аватара."""
    data: Dict[str, Any] = await state.get_data()
    mode: str = data.get('mode', 'register')
    logger.info(f"User {message.from_user.id} uploading avatar, mode={mode}")
    success = await process_avatar_upload(message, state, message.from_user.id)
    if success:
        if mode == 'edit':
            await state.clear()
            await message.delete()
            await _show_profile(message, state)
        else:
            await _finish_registration(message, state)

@router.message(Command("cancel"), StateFilter(CandidateFSM))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """Отмена FSM."""
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