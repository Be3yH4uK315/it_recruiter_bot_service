from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

from app.keyboards.inline import get_profile_actions_keyboard, ProfileAction, get_profile_edit_keyboard, \
    EditFieldCallback, get_work_modes_keyboard, WorkModeCallback, get_skill_kind_keyboard, SkillKindCallback, \
    get_skill_level_keyboard, SkillLevelCallback, ConfirmationCallback, \
    ContactsVisibilityCallback
from app.services.api_client import candidate_api_client, file_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateProfileEdit
from app.handlers.employer_search import format_candidate_profile
from app.core.messages import Messages

from app.handlers.common_blocks import (
    process_add_experience_responsibilities, process_confirm_add_experience,
    process_skill_level, process_confirm_add_skill,
    process_project_links, process_confirm_add_project,
    process_contacts, process_contacts_visibility,
    process_resume_upload, process_avatar_upload
)

router = Router()

# --- ОТОБРАЖЕНИЕ ПРОФИЛЯ ---
async def _show_profile(message: Message | CallbackQuery, state: FSMContext):
    await state.clear()

    target_message = message.message if isinstance(message, CallbackQuery) else message
    user_id = message.from_user.id

    profile = await candidate_api_client.get_candidate_by_telegram_id(user_id)
    if not profile:
        await target_message.answer(Messages.Profile.NOT_FOUND)
        return

    avatar_url = None
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
        await target_message.answer(text=caption, reply_markup=keyboard)

    if is_callback:
        await message.answer()


# --- ГЛАВНАЯ КОМАНДА ПРОФИЛЯ ---
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    await _show_profile(message, state)

# --- ОБРАБОТЧИКИ ДЕЙСТВИЙ ---
@router.callback_query(ProfileAction.filter())
async def handle_profile_action(callback: CallbackQuery, callback_data: ProfileAction, state: FSMContext):
    if callback_data.action == "edit":
        await state.set_state(CandidateProfileEdit.choosing_field)
        await callback.message.edit_text(Messages.Profile.CHOOSE_FIELD, reply_markup=get_profile_edit_keyboard())
    elif callback_data.action == "upload_resume":
        await state.set_state(CandidateProfileEdit.uploading_resume)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_RESUME)
    elif callback_data.action == "upload_avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_AVATAR)
    elif callback_data.action == "delete_avatar":
        success = await candidate_api_client.delete_avatar(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.Profile.DELETE_AVATAR_OK)
        else:
            await callback.message.answer(Messages.Profile.DELETE_AVATAR_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    elif callback_data.action == "delete_resume":
        success = await candidate_api_client.delete_resume(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.Profile.DELETE_RESUME_OK)
        else:
            await callback.message.answer(Messages.Profile.DELETE_RESUME_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    await callback.answer()


@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateProfileEdit.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext):
    field = callback_data.field_name
    await state.update_data(field_to_edit=field)

    prompts = {
        "display_name": Messages.Profile.ENTER_NAME,
        "headline_role": Messages.Profile.ENTER_ROLE,
        "location": Messages.Profile.ENTER_LOCATION,
    }

    if field in prompts:
        await state.set_state(CandidateProfileEdit.editing_field)
        await callback.message.edit_text(prompts[field])

    elif field == "contacts":
        await state.set_state(CandidateProfileEdit.editing_contacts)
        await callback.message.answer(Messages.Profile.ENTER_CONTACTS)

    elif field == "experiences":
        await state.update_data(new_experiences=[])
        await state.set_state(CandidateProfileEdit.editing_exp_company)
        await callback.message.answer(Messages.Profile.ENTER_EXPERIENCE_COMPANY)

    elif field == "skills":
        await state.update_data(new_skills=[])
        await state.set_state(CandidateProfileEdit.editing_skill_name)
        await callback.message.edit_text(Messages.Profile.ENTER_SKILL_NAME)

    elif field == "projects":
        await state.update_data(new_projects=[])
        await state.set_state(CandidateProfileEdit.editing_project_title)
        await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)

    elif field == "work_modes":
        await state.update_data(work_modes=[])
        await state.set_state(CandidateProfileEdit.editing_work_modes)
        await callback.message.edit_text(Messages.Profile.WORK_MODE_SELECT,
            reply_markup=get_work_modes_keyboard()
        )

    elif field == "avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.edit_text(Messages.Profile.UPLOAD_AVATAR)

    await callback.answer()

# ====== EXPERIENCES ======
@router.callback_query(EditFieldCallback.filter(F.field_name == "experiences"), CandidateProfileEdit.choosing_field)
async def handle_edit_experiences(callback: CallbackQuery, state: FSMContext):
    await state.update_data(new_experiences=[])
    await state.set_state(CandidateProfileEdit.editing_exp_company)
    await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
    await callback.answer()


@router.message(CandidateProfileEdit.editing_exp_company)
async def handle_edit_exp_company(message: Message, state: FSMContext):
    await state.update_data(current_exp_company=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_POSITION)
    await state.set_state(CandidateProfileEdit.editing_exp_position)


@router.message(CandidateProfileEdit.editing_exp_position)
async def handle_edit_exp_position(message: Message, state: FSMContext):
    await state.update_data(current_exp_position=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_START)
    await state.set_state(CandidateProfileEdit.editing_exp_start_date)


@router.message(CandidateProfileEdit.editing_exp_start_date)
async def handle_edit_exp_start_date(message: Message, state: FSMContext):
    await state.update_data(current_exp_start_date=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_END)
    await state.set_state(CandidateProfileEdit.editing_exp_end_date)


@router.message(CandidateProfileEdit.editing_exp_end_date)
async def handle_edit_exp_end_date(message: Message, state: FSMContext):
    await state.update_data(current_exp_end_date=message.text)
    await message.answer(Messages.Profile.ENTER_EXPERIENCE_RESP)
    await state.set_state(CandidateProfileEdit.editing_exp_responsibilities)


@router.message(CandidateProfileEdit.editing_exp_responsibilities)
async def handle_edit_exp_responsibilities(message: Message, state: FSMContext):
    await process_add_experience_responsibilities(message, state, is_edit_mode=True)

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_exp"), CandidateProfileEdit.confirm_edit_another_experience)
async def handle_confirm_edit_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    await process_confirm_add_experience(callback, callback_data, state, is_edit_mode=True, show_profile_func=_show_profile)

# ====== CONTACTS ======
@router.callback_query(EditFieldCallback.filter(F.field_name == "contacts"), CandidateProfileEdit.choosing_field)
async def handle_edit_contacts(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CandidateProfileEdit.editing_contacts)
    await callback.message.edit_text(Messages.Profile.ENTER_CONTACTS)
    await callback.answer()


@router.message(CandidateProfileEdit.editing_contacts)
async def handle_edit_contacts_input(message: Message, state: FSMContext):
    await process_contacts(message, state, is_edit_mode=True)

@router.callback_query(ContactsVisibilityCallback.filter(), CandidateProfileEdit.editing_visibility)
async def handle_edit_visibility(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext):
    await process_contacts_visibility(callback, callback_data, state, is_edit_mode=True, show_profile_func=_show_profile)

# --- TXT VALUE ---
@router.message(CandidateProfileEdit.editing_field)
async def handle_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field_to_edit")
    update_payload = {field: message.text}

    success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)

    if success:
        await message.answer(Messages.Profile.FIELD_UPDATED)
    else:
        await message.answer(Messages.Profile.FIELD_UPDATE_ERROR)

    await state.clear()
    await message.delete()
    await _show_profile(message, state)

# --- SKILLS ---
@router.message(CandidateProfileEdit.editing_skill_name)
async def handle_edit_skill_name(message: Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer(Messages.Profile.ENTER_SKILL_KIND, reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateProfileEdit.editing_skill_kind)
async def handle_edit_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(Messages.Profile.ENTER_SKILL_LEVEL, reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateProfileEdit.editing_skill_level)
async def handle_edit_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    await process_skill_level(callback, callback_data, state, is_edit_mode=True)

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_skill"),
                       CandidateProfileEdit.confirm_edit_another_skill)
async def handle_confirm_edit_skill(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                    state: FSMContext):
    await process_confirm_add_skill(callback, callback_data, state, is_edit_mode=True, show_profile_func=_show_profile)

# --- PROJECT ---
@router.message(CandidateProfileEdit.editing_project_title)
async def handle_edit_project_title(message: Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer(Messages.Profile.ENTER_PROJECT_DESCRIPTION)
    await state.set_state(CandidateProfileEdit.editing_project_description)

@router.message(CandidateProfileEdit.editing_project_description)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_description)
async def handle_edit_project_description(message: Message, state: FSMContext):
    description = message.text if message.text and not message.text.startswith('/skip') else None
    await state.update_data(current_project_description=description)
    await message.answer(Messages.Profile.ENTER_PROJECT_LINKS)
    await state.set_state(CandidateProfileEdit.editing_project_links)

@router.message(CandidateProfileEdit.editing_project_links)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_links)
async def handle_edit_project_links(message: Message, state: FSMContext):
    await process_project_links(message, state, is_edit_mode=True)

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_project"),
                       CandidateProfileEdit.confirm_edit_another_project)
async def handle_confirm_edit_project(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                      state: FSMContext):
    await process_confirm_add_project(callback, callback_data, state, is_edit_mode=True, show_profile_func=_show_profile)

# --- WORK MODE ---
@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateProfileEdit.editing_work_modes)
async def handle_edit_work_mode_selection(callback: CallbackQuery, callback_data: WorkModeCallback,
                                          state: FSMContext):
    data = await state.get_data()
    selected_modes = data.get("work_modes", [])
    if callback_data.mode not in selected_modes:
        selected_modes.append(callback_data.mode)
    else:
        selected_modes.remove(callback_data.mode)
    await state.update_data(work_modes=selected_modes)
    await callback.answer(f"Выбрано: {', '.join(selected_modes) if selected_modes else 'пусто'}")

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateProfileEdit.editing_work_modes)
async def handle_edit_work_mode_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    update_payload = {"work_modes": data.get("work_modes", [])}
    success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
    if success:
        await callback.message.answer(Messages.Profile.WORK_MODE_UPDATED)
    else:
        await callback.message.answer(Messages.Profile.WORK_MODE_UPDATE_ERROR)

    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()

# --- RESUME ---
@router.message(F.document, CandidateProfileEdit.uploading_resume)
async def handle_resume_upload(message: Message, state: FSMContext):
    success = await process_resume_upload(message, state, message.from_user.id)
    if success:
        await state.clear()
        await message.delete()
        await _show_profile(message, state)

# --- AVATAR ---
@router.message(F.photo, CandidateProfileEdit.uploading_avatar)
async def handle_avatar_upload(message: Message, state: FSMContext):
    success = await process_avatar_upload(message, state, message.from_user.id)
    await state.clear()
    await message.delete()
    await _show_profile(message, state)

# --- BACK ---
@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateProfileEdit.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()