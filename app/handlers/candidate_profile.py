from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

from app.keyboards.inline import get_profile_actions_keyboard, ProfileAction, get_profile_edit_keyboard, \
    EditFieldCallback, get_work_modes_keyboard, WorkModeCallback, get_skill_kind_keyboard, SkillKindCallback, \
    get_skill_level_keyboard, SkillLevelCallback, get_confirmation_keyboard, ConfirmationCallback, \
    get_contacts_visibility_keyboard
from app.services.api_client import candidate_api_client, file_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateProfileEdit
from app.handlers.employer_search import format_candidate_profile
from app.core.messages import Messages

router = Router()

# --- ОТОБРАЖЕНИЕ ПРОФИЛЯ ---
async def _show_profile(message: Message | CallbackQuery, state: FSMContext):
    await state.clear()

    target_message = message.message if isinstance(message, CallbackQuery) else message
    user_id = message.from_user.id

    profile = await candidate_api_client.get_candidate_by_telegram_id(user_id)
    if not profile:
        await target_message.answer(Messages.CandidateProfile.NOT_FOUND)
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
        await callback.message.edit_text(Messages.CandidateProfile.CHOOSE_FIELD, reply_markup=get_profile_edit_keyboard())
    elif callback_data.action == "upload_resume":
        await state.set_state(CandidateProfileEdit.uploading_resume)
        await callback.message.delete()
        await callback.message.answer(Messages.CandidateProfile.UPLOAD_RESUME)
    elif callback_data.action == "upload_avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.delete()
        await callback.message.answer(Messages.CandidateProfile.UPLOAD_AVATAR)
    elif callback_data.action == "delete_avatar":
        success = await candidate_api_client.delete_avatar(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.CandidateProfile.DELETE_AVATAR_OK)
        else:
            await callback.message.answer(Messages.CandidateProfile.DELETE_AVATAR_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    elif callback_data.action == "delete_resume":
        success = await candidate_api_client.delete_resume(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.CandidateProfile.DELETE_RESUME_OK)
        else:
            await callback.message.answer(Messages.CandidateProfile.DELETE_RESUME_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    await callback.answer()


@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateProfileEdit.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext):
    field = callback_data.field_name
    await state.update_data(field_to_edit=field)

    prompts = {
        "display_name": Messages.CandidateProfile.ENTER_NAME,
        "headline_role": Messages.CandidateProfile.ENTER_ROLE,
        "location": Messages.CandidateProfile.ENTER_LOCATION,
    }

    if field in prompts:
        await state.set_state(CandidateProfileEdit.editing_field)
        await callback.message.edit_text(prompts[field])

    elif field == "contacts":
        await state.set_state(CandidateProfileEdit.editing_contacts)
        await callback.message.answer(Messages.CandidateProfile.ENTER_CONTACTS)

    elif field == "experiences":
        await state.update_data(new_experiences=[])
        await state.set_state(CandidateProfileEdit.editing_exp_company)
        await callback.message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_COMPANY)

    elif field == "skills":
        await state.update_data(new_skills=[])
        await state.set_state(CandidateProfileEdit.editing_skill_name)
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_SKILL_NAME)

    elif field == "projects":
        await state.update_data(new_projects=[])
        await state.set_state(CandidateProfileEdit.editing_project_title)
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_PROJECT_TITLE)

    elif field == "work_modes":
        await state.update_data(work_modes=[])
        await state.set_state(CandidateProfileEdit.editing_work_modes)
        await callback.message.edit_text(Messages.CandidateProfile.WORK_MODE_SELECT,
            reply_markup=get_work_modes_keyboard()
        )

    elif field == "avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.edit_text(Messages.CandidateProfile.UPLOAD_AVATAR)

    await callback.answer()

# ====== EXPERIENCES ======

@router.callback_query(EditFieldCallback.filter(F.field_name == "experiences"), CandidateProfileEdit.choosing_field)
async def handle_edit_experiences(callback: CallbackQuery, state: FSMContext):
    await state.update_data(new_experiences=[])
    await state.set_state(CandidateProfileEdit.editing_exp_company)
    await callback.message.edit_text(Messages.CandidateProfile.ENTER_EXPERIENCE_COMPANY)
    await callback.answer()


@router.message(CandidateProfileEdit.editing_exp_company)
async def handle_edit_exp_company(message: Message, state: FSMContext):
    await state.update_data(current_exp_company=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_POSITION)
    await state.set_state(CandidateProfileEdit.editing_exp_position)


@router.message(CandidateProfileEdit.editing_exp_position)
async def handle_edit_exp_position(message: Message, state: FSMContext):
    await state.update_data(current_exp_position=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_START)
    await state.set_state(CandidateProfileEdit.editing_exp_start_date)


@router.message(CandidateProfileEdit.editing_exp_start_date)
async def handle_edit_exp_start_date(message: Message, state: FSMContext):
    try:
        start_date = date.fromisoformat(message.text)
    except ValueError:
        await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_START_ERROR)
        return
    await state.update_data(current_exp_start_date=start_date.isoformat())
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_END)
    await state.set_state(CandidateProfileEdit.editing_exp_end_date)


@router.message(CandidateProfileEdit.editing_exp_end_date)
async def handle_edit_exp_end_date(message: Message, state: FSMContext):
    if message.text.lower() == "настоящее время":
        end_date = None
    else:
        try:
            end_date = date.fromisoformat(message.text).isoformat()
        except ValueError:
            await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_END_ERROR)
            return

    await state.update_data(current_exp_end_date=end_date)
    await message.answer(Messages.CandidateProfile.ENTER_EXPERIENCE_RESP)
    await state.set_state(CandidateProfileEdit.editing_exp_responsibilities)


@router.message(CandidateProfileEdit.editing_exp_responsibilities)
async def handle_edit_exp_responsibilities(message: Message, state: FSMContext):
    data = await state.get_data()
    exp = {
        "company": data["current_exp_company"],
        "position": data["current_exp_position"],
        "start_date": data["current_exp_start_date"],
        "end_date": data.get("current_exp_end_date"),
        "responsibilities": message.text,
    }

    new_experiences = data.get("new_experiences", [])
    new_experiences.append(exp)

    await state.update_data(new_experiences=new_experiences)

    await message.answer(
        Messages.CandidateProfile.EXPERIENCE_ADDED,
        reply_markup=get_confirmation_keyboard(step="edit_exp")
    )
    await state.set_state(CandidateProfileEdit.confirm_edit_another_experience)


@router.callback_query(ConfirmationCallback.filter(F.step == "edit_exp"), CandidateProfileEdit.confirm_edit_another_experience)
async def handle_confirm_edit_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_EXPERIENCE_COMPANY)
        await state.set_state(CandidateProfileEdit.editing_exp_company)
    else:
        data = await state.get_data()
        update_payload = {"experiences": data.get("new_experiences", [])}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        if success:
            await callback.message.answer(Messages.CandidateProfile.EXPERIENCE_UPDATED)
        else:
            await callback.message.answer(Messages.CandidateProfile.EXPERIENCE_UPDATE_ERROR)
        await state.clear()
        await _show_profile(callback, state)
    await callback.answer()

# ====== CONTACTS ======

@router.callback_query(EditFieldCallback.filter(F.field_name == "contacts"), CandidateProfileEdit.choosing_field)
async def handle_edit_contacts(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CandidateProfileEdit.editing_contacts)
    await callback.message.edit_text(Messages.CandidateProfile.ENTER_CONTACTS)
    await callback.answer()


@router.message(CandidateProfileEdit.editing_contacts)
async def handle_edit_contacts_input(message: Message, state: FSMContext):
    contacts_text = message.text
    contacts = {}
    try:
        for item in contacts_text.split(","):
            key, value = item.strip().split(":", 1)
            contacts[key.strip()] = value.strip()
    except Exception:
        await message.answer(Messages.CandidateProfile.ENTER_CONTACTS_ERROR)
        return

    await state.update_data(new_contacts=contacts)
    await message.answer(Messages.CandidateProfile.CONTACTS_VISIBILITY_SELECT, reply_markup=get_contacts_visibility_keyboard())
    await state.set_state(CandidateProfileEdit.editing_visibility)


@router.callback_query(CandidateProfileEdit.editing_visibility)
async def handle_edit_visibility(callback: CallbackQuery, state: FSMContext):
    visibility = callback.data
    data = await state.get_data()
    update_payload = {
        "contacts": data.get("new_contacts", {}),
        "contacts_visibility": visibility,
    }

    success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
    if success:
        await callback.message.answer(Messages.CandidateProfile.CONTACTS_UPDATED)
    else:
        await callback.message.answer(Messages.CandidateProfile.CONTACTS_UPDATE_ERROR)
    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()

# --- TXT VALUE ---
@router.message(CandidateProfileEdit.editing_field)
async def handle_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field_to_edit")
    update_payload = {field: message.text}

    success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)

    if success:
        await message.answer(Messages.CandidateProfile.FIELD_UPDATED)
    else:
        await message.answer(Messages.CandidateProfile.FIELD_UPDATE_ERROR)

    await state.clear()
    await message.delete()
    await _show_profile(message, state)

# --- SKILLS ---
@router.message(CandidateProfileEdit.editing_skill_name)
async def handle_edit_skill_name(message: Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_SKILL_KIND, reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateProfileEdit.editing_skill_kind)
async def handle_edit_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(Messages.CandidateProfile.ENTER_SKILL_LEVEL, reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateProfileEdit.editing_skill_level)
async def handle_edit_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    data = await state.get_data()
    new_skill = {
        "skill": data.get("current_skill_name"),
        "kind": data.get("current_skill_kind"),
        "level": callback_data.level
    }
    skills_list = data.get("new_skills", [])
    skills_list.append(new_skill)
    await state.update_data(new_skills=skills_list)
    await callback.message.edit_text(Messages.CandidateProfile.SKILL_ADDED.format(name=new_skill['skill']),
        reply_markup=get_confirmation_keyboard(step="edit_skill")
    )
    await state.set_state(CandidateProfileEdit.confirm_edit_another_skill)
    await callback.answer()

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_skill"),
                       CandidateProfileEdit.confirm_edit_another_skill)
async def handle_confirm_edit_skill(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                    state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_SKILL_NAME)
        await state.set_state(CandidateProfileEdit.editing_skill_name)
    else:
        data = await state.get_data()
        update_payload = {"skills": data.get("new_skills", [])}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        if success:
            await callback.message.answer(Messages.CandidateProfile.SKILL_ADDED)
        else:
            await callback.message.answer(Messages.CandidateProfile.SKILLS_UPDATE_ERROR)

        await state.clear()
        await _show_profile(callback, state)
    await callback.answer()

# --- PROJECT ---
@router.message(CandidateProfileEdit.editing_project_title)
async def handle_edit_project_title(message: Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer(Messages.CandidateProfile.ENTER_PROJECT_DESCRIPTION)
    await state.set_state(CandidateProfileEdit.editing_project_description)

@router.message(CandidateProfileEdit.editing_project_description)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_description)
async def handle_edit_project_description(message: Message, state: FSMContext):
    description = message.text if message.text and not message.text.startswith('/skip') else None
    await state.update_data(current_project_description=description)
    await message.answer(Messages.CandidateProfile.ENTER_PROJECT_LINKS)
    await state.set_state(CandidateProfileEdit.editing_project_links)

@router.message(CandidateProfileEdit.editing_project_links)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_links)
async def handle_edit_project_links(message: Message, state: FSMContext):
    data = await state.get_data()
    links = {"main_link": message.text} if message.text and not message.text.startswith('/skip') else {}
    new_project = {
        "title": data.get("current_project_title"),
        "description": data.get("current_project_description"),
        "links": links
    }
    projects_list = data.get("new_projects", [])
    projects_list.append(new_project)
    await state.update_data(new_projects=projects_list)
    await message.answer(Messages.CandidateProfile.PROJECT_ADDED.format(name=new_project['title']),
        reply_markup=get_confirmation_keyboard(step="edit_project")
    )
    await state.set_state(CandidateProfileEdit.confirm_edit_another_project)

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_project"),
                       CandidateProfileEdit.confirm_edit_another_project)
async def handle_confirm_edit_project(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                      state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text(Messages.CandidateProfile.ENTER_PROJECT_TITLE)
        await state.set_state(CandidateProfileEdit.editing_project_title)
    else:
        data = await state.get_data()
        update_payload = {"projects": data.get("new_projects", [])}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        if success:
            await callback.message.answer(Messages.CandidateProfile.PROJECTS_UPDATED)
        else:
            await callback.message.answer(Messages.CandidateProfile.PROJECTS_UPDATE_ERROR)

        await state.clear()
        await _show_profile(callback, state)
    await callback.answer()

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
        await callback.message.answer(Messages.CandidateProfile.WORK_MODE_UPDATED)
    else:
        await callback.message.answer(Messages.CandidateProfile.WORK_MODE_UPDATE_ERROR)

    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()

# --- RESUME ---
@router.message(F.document, CandidateProfileEdit.uploading_resume)
async def handle_resume_upload(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id

    await message.answer(Messages.CandidateProfile.RESUME_PROCESSING)

    document = message.document
    if document.mime_type not in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        await message.answer(Messages.CandidateProfile.RESUME_WRONG_TYPE)
        return
    if document.file_size > 10 * 1024 * 1024:  # 10MB limit
        await message.answer(Messages.CandidateProfile.RESUME_TOO_BIG)
        return

    file_info = await message.bot.get_file(document.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    old_file_id_to_delete = None
    candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(user_telegram_id)
    if candidate_profile and candidate_profile.get("resumes"):
        old_file_id_to_delete = candidate_profile["resumes"][0]["file_id"]

    extension = document.file_name.split('.')[-1].lower()
    content_type = 'application/pdf' if extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if extension == 'docx' else 'application/pdf'
    filename = document.file_name

    file_response = await file_api_client.upload_file(
        filename=filename,
        file_data=file_data.read(),
        content_type=content_type,
        owner_id=user_telegram_id,
        file_type='resume'
    )

    if not file_response:
        await message.answer(Messages.CandidateProfile.RESUME_UPDATE_ERROR)
        return

    new_file_id = file_response['id']
    success = await candidate_api_client.replace_resume(
        telegram_id=user_telegram_id,
        file_id=new_file_id
    )

    if success:
        await message.answer(Messages.CandidateProfile.RESUME_UPDATED)
        if old_file_id_to_delete:
            await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=user_telegram_id)
    else:
        await message.answer(Messages.CandidateProfile.RESUME_UPDATE_ERROR)

    await state.clear()
    await message.delete()
    await _show_profile(message, state)

# --- AVATAR ---
@router.message(F.photo, CandidateProfileEdit.uploading_avatar)
async def handle_avatar_upload(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id

    await message.answer(Messages.CandidateProfile.AVATAR_PROCESSING)

    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    old_file_id_to_delete = None
    candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(user_telegram_id)
    if candidate_profile and candidate_profile.get("avatars"):
        old_file_id_to_delete = candidate_profile["avatars"][0]["file_id"]

    extension = file_info.file_path.split('.')[-1].lower()
    content_type = 'image/jpeg' if extension in ['jpg', 'jpeg'] else 'image/png' if extension == 'png' else 'image/jpeg'
    filename = f"{photo.file_unique_id}.{extension}"

    file_response = await file_api_client.upload_file(
        filename=filename,
        file_data=file_data.read(),
        content_type=content_type,
        owner_id=user_telegram_id,
        file_type='avatar'
    )

    if not file_response:
        await message.answer(Messages.CandidateProfile.AVATAR_UPDATE_ERROR)
        return

    new_file_id = file_response['id']
    success = await candidate_api_client.replace_avatar(
        telegram_id=user_telegram_id,
        file_id=new_file_id
    )

    if success:
        await message.answer(Messages.CandidateProfile.AVATAR_UPDATED)
        if old_file_id_to_delete:
            await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=user_telegram_id)
    else:
        await message.answer(Messages.CandidateProfile.AVATAR_UPDATE_ERROR)

    await state.clear()
    await message.delete()
    await _show_profile(message, state)

# --- BACK ---
@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateProfileEdit.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()