from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateRegistration, CandidateProfileEdit
from app.keyboards.inline import (
    get_confirmation_keyboard, ConfirmationCallback,
    SkillLevelCallback, get_contacts_visibility_keyboard, 
    ContactsVisibilityCallback,
)
from app.core.messages import Messages
from app.utils.validators import (
    parse_experience_text, parse_skill_text, parse_project_text, parse_contacts_text,
    validate_list_length, ValidationError
)
from app.services.api_client import file_api_client, candidate_api_client
import logging

logger = logging.getLogger(__name__)

# --- Общая функция для блока опыта (добавление/редактирование) ---
async def process_add_experience_responsibilities(message: Message, state: FSMContext, is_edit_mode: bool = False):
    try:
        data = await state.get_data()
        responsibilities = message.text if message.text and not message.text.startswith('/skip') else None
        exp_text = f"company: {data.get('current_exp_company')}\nposition: {data.get('current_exp_position')}\nstart_date: {data.get('current_exp_start_date')}\nend_date: {data.get('current_exp_end_date')}\nresponsibilities: {responsibilities or ''}"
        new_experience = parse_experience_text(exp_text)
        key = "new_experiences" if is_edit_mode else "experiences"
        experiences = data.get(key, [])
        experiences.append(new_experience.dict())
        validate_list_length(experiences, max_length=10, item_type="опытов работы")
        await state.update_data(**{key: experiences})
        await state.update_data(current_exp_company=None, current_exp_position=None, current_exp_start_date=None, current_exp_end_date=None)
        added_msg = Messages.Profile.EXPERIENCE_UPDATED if is_edit_mode else Messages.Profile.EXPERIENCE_ADDED
        await message.answer(
            added_msg.format(name=new_experience.company),
            reply_markup=get_confirmation_keyboard(step="edit_exp" if is_edit_mode else "add_exp")
        )
        next_state = CandidateProfileEdit.confirm_edit_another_experience if is_edit_mode else CandidateRegistration.confirm_add_another_experience
        await state.set_state(next_state)
    except (ValueError, ValidationError) as e:
        error_msg = Messages.Profile.EXPERIENCE_INVALID.format(error=str(e))
        await message.answer(error_msg)
        prev_state = CandidateProfileEdit.editing_exp_company if is_edit_mode else CandidateRegistration.adding_exp_company
        await state.set_state(prev_state)
    except Exception as e:
        logger.error(f"Unexpected error in process_add_experience_responsibilities: {e}")
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, is_edit_mode: bool = False, next_func=None, show_profile_func=None):
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
            next_state = CandidateProfileEdit.editing_exp_company if is_edit_mode else CandidateRegistration.adding_exp_company
            await state.set_state(next_state)
        else:
            await callback.message.delete()
            if is_edit_mode:
                data = await state.get_data()
                update_payload = {"experiences": data.get("new_experiences", [])}
                success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
                msg = Messages.Profile.EXPERIENCE_UPDATED if success else Messages.Profile.EXPERIENCE_UPDATE_ERROR
                await callback.message.answer(msg)
                await state.clear()
                if show_profile_func:
                    await show_profile_func(callback, state)
            else:
                if next_func:
                    await next_func(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error in process_confirm_add_experience: {e}")
        await callback.message.answer(Messages.Common.CANCELLED)

# --- Общая функция для блока навыков ---
async def process_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext, is_edit_mode: bool = False):
    try:
        data = await state.get_data()
        skill_text = f"name: {data.get('current_skill_name')}, kind: {data.get('current_skill_kind')}, level: {callback_data.level}"
        new_skill = parse_skill_text(skill_text)
        key = "new_skills" if is_edit_mode else "skills"
        skills_list = data.get(key, [])
        skills_list.append(new_skill.dict())
        validate_list_length(skills_list, max_length=20, item_type="навыков")
        await state.update_data(**{key: skills_list})
        await state.update_data(current_skill_name=None, current_skill_kind=None)
        added_msg = Messages.Profile.SKILLS_UPDATED if is_edit_mode else Messages.Profile.SKILL_ADDED
        await callback.message.edit_text(
            added_msg.format(name=new_skill.skill),
            reply_markup=get_confirmation_keyboard(step="edit_skill" if is_edit_mode else "add_skill")
        )
        next_state = CandidateProfileEdit.confirm_edit_another_skill if is_edit_mode else CandidateRegistration.confirm_add_another_skill
        await state.set_state(next_state)
    except (ValueError, ValidationError) as e:
        error_msg = Messages.Profile.SKILL_INVALID.format(error=str(e))
        await callback.message.answer(error_msg)
        prev_state = CandidateProfileEdit.editing_skill_name if is_edit_mode else CandidateRegistration.adding_skill_name
        await state.set_state(prev_state)
    except Exception as e:
        logger.error(f"Unexpected error in process_skill_level: {e}")
        await callback.message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_skill(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, is_edit_mode: bool = False, next_func=None, show_profile_func=None):
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_SKILL_NAME)
            next_state = CandidateProfileEdit.editing_skill_name if is_edit_mode else CandidateRegistration.adding_skill_name
            await state.set_state(next_state)
        else:
            await callback.message.delete()
            if is_edit_mode:
                data = await state.get_data()
                update_payload = {"skills": data.get("new_skills", [])}
                success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
                msg = Messages.Profile.SKILLS_UPDATED if success else Messages.Profile.SKILLS_UPDATE_ERROR
                await callback.message.answer(msg)
                await state.clear()
                if show_profile_func:
                    await show_profile_func(callback, state)
            else:
                if next_func:
                    await next_func(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error in process_confirm_add_skill: {e}")
        await callback.message.answer(Messages.Common.CANCELLED)

# --- Общая функция для блока проектов ---
async def process_project_links(message: Message, state: FSMContext, is_edit_mode: bool = False):
    try:
        data = await state.get_data()
        links_text = message.text if message.text and not message.text.startswith('/skip') else None
        new_project = parse_project_text(
            title=data.get("current_project_title"),
            description=data.get("current_project_description"),
            links_text=links_text
        )
        key = "new_projects" if is_edit_mode else "projects"
        projects_list = data.get(key, [])
        projects_list.append(new_project.dict())
        validate_list_length(projects_list, max_length=10, item_type="проектов")
        await state.update_data(**{key: projects_list})
        await state.update_data(current_project_title=None, current_project_description=None)
        added_msg = Messages.Profile.PROJECTS_UPDATED if is_edit_mode else Messages.Profile.PROJECT_ADDED
        await message.answer(
            added_msg.format(title=new_project.title),
            reply_markup=get_confirmation_keyboard(step="edit_project" if is_edit_mode else "add_project")
        )
        next_state = CandidateProfileEdit.confirm_edit_another_project if is_edit_mode else CandidateRegistration.confirm_add_another_project
        await state.set_state(next_state)
    except (ValueError, ValidationError) as e:
        error_msg = Messages.Profile.PROJECT_INVALID.format(error=str(e))
        await message.answer(error_msg)
        prev_state = CandidateProfileEdit.editing_project_title if is_edit_mode else CandidateRegistration.adding_project_title
        await state.set_state(prev_state)
    except Exception as e:
        logger.error(f"Unexpected error in process_project_links: {e}")
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_project(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, is_edit_mode: bool = False, next_func=None, show_profile_func=None):
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)
            next_state = CandidateProfileEdit.editing_project_title if is_edit_mode else CandidateRegistration.adding_project_title
            await state.set_state(next_state)
        else:
            await callback.message.delete()
            if is_edit_mode:
                data = await state.get_data()
                update_payload = {"projects": data.get("new_projects", [])}
                success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
                msg = Messages.Profile.PROJECTS_UPDATED if success else Messages.Profile.PROJECTS_UPDATE_ERROR
                await callback.message.answer(msg)
                await state.clear()
                if show_profile_func:
                    await show_profile_func(callback, state)
            else:
                if next_func:
                    await next_func(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error in process_confirm_add_project: {e}")
        await callback.message.answer(Messages.Common.CANCELLED)

# --- Общая функция для контактов ---
async def process_contacts(message: Message, state: FSMContext, is_edit_mode: bool = False, next_func=None):
    try:
        if message.text and not message.text.startswith('/skip'):
            contacts = parse_contacts_text(message.text)
            key = "new_contacts" if is_edit_mode else "contacts"
            await state.update_data(**{key: contacts.dict(exclude_none=True)})
            logger.info("Контакты введены, отправляем сообщение видимости")
            await message.answer(Messages.Profile.CONTACTS_VISIBILITY_SELECT, reply_markup=get_contacts_visibility_keyboard())
            next_state = CandidateProfileEdit.editing_visibility if is_edit_mode else CandidateRegistration.choosing_contacts_visibility
            await state.set_state(next_state)
            if is_edit_mode:
                pass
        else:
            key = "new_contacts" if is_edit_mode else "contacts"
            await state.update_data(**{key: {}})
            logger.info("Контакты пропущены (/skip), вызываем next_func")
            if next_func:
                await next_func(message, state)
    except (ValueError, ValidationError) as e:
        error_msg = Messages.Profile.CONTACTS_INVALID.format(error=str(e))
        await message.answer(error_msg)
    except Exception as e:
        logger.error(f"Unexpected error in process_contacts: {e}")
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_contacts_visibility(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext, is_edit_mode: bool = False, next_func=None, show_profile_func=None):
    try:
        await state.update_data(contacts_visibility=callback_data.visibility)
        await callback.message.edit_text(f"✅ Видимость контактов: {callback_data.visibility.capitalize()}")
        if is_edit_mode:
            data = await state.get_data()
            update_payload = {
                "contacts": data.get("new_contacts", {}),
                "contacts_visibility": callback_data.visibility,
            }
            success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
            msg = Messages.Profile.CONTACTS_UPDATED if success else Messages.Profile.CONTACTS_UPDATE_ERROR
            await callback.message.answer(msg)
            await state.clear()
            if show_profile_func:
                await show_profile_func(callback, state)
        else:
            if next_func:
                await next_func(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error in process_contacts_visibility: {e}")
        await callback.message.answer(Messages.Common.CANCELLED)

# --- Общая функция для загрузки resume ---
async def process_resume_upload(message: Message, state: FSMContext, telegram_id: int):
    try:
        await message.answer(Messages.Profile.RESUME_PROCESSING)
        document = message.document
        if document.mime_type not in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            await message.answer(Messages.Profile.RESUME_WRONG_TYPE)
            return False
        if document.file_size > 10 * 1024 * 1024:  # 10MB limit
            await message.answer(Messages.Profile.RESUME_TOO_BIG)
            return False

        file_info = await message.bot.get_file(document.file_id)
        file_data = await message.bot.download_file(file_info.file_path)

        old_file_id_to_delete = None
        candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(telegram_id)
        if candidate_profile and candidate_profile.get("resumes"):
            old_file_id_to_delete = candidate_profile["resumes"][0]["file_id"]

        extension = document.file_name.split('.')[-1].lower()
        content_type = 'application/pdf' if extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if extension == 'docx' else 'application/pdf'
        filename = document.file_name

        file_response = await file_api_client.upload_file(
            filename=filename,
            file_data=file_data.read(),
            content_type=content_type,
            owner_id=telegram_id,
            file_type='resume'
        )

        if not file_response:
            await message.answer(Messages.Profile.RESUME_UPDATE_ERROR)
            return False

        new_file_id = file_response['id']
        success = await candidate_api_client.replace_resume(
            telegram_id=telegram_id,
            file_id=new_file_id
        )

        if success:
            await message.answer(Messages.Profile.RESUME_UPDATED)
            if old_file_id_to_delete:
                await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=telegram_id)
        else:
            await message.answer(Messages.Profile.RESUME_UPDATE_ERROR)
        return success
    except Exception as e:
        logger.error(f"Unexpected error in process_resume_upload: {e}")
        await message.answer(Messages.Profile.RESUME_UPDATE_ERROR)
        return False

# --- Общая функция для загрузки avatar ---
async def process_avatar_upload(message: Message, state: FSMContext, telegram_id: int):
    try:
        await message.answer(Messages.Profile.AVATAR_PROCESSING)
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        file_data = await message.bot.download_file(file_info.file_path)

        old_file_id_to_delete = None
        candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(telegram_id)
        if candidate_profile and candidate_profile.get("avatars"):
            old_file_id_to_delete = candidate_profile["avatars"][0]["file_id"]

        extension = file_info.file_path.split('.')[-1].lower()
        content_type = 'image/jpeg' if extension in ['jpg', 'jpeg'] else 'image/png' if extension == 'png' else 'image/jpeg'
        filename = f"{photo.file_unique_id}.{extension}"

        file_response = await file_api_client.upload_file(
            filename=filename,
            file_data=file_data.read(),
            content_type=content_type,
            owner_id=telegram_id,
            file_type='avatar'
        )

        if not file_response:
            await message.answer(Messages.Profile.AVATAR_UPDATE_ERROR)
            return False

        new_file_id = file_response['id']
        success = await candidate_api_client.replace_avatar(
            telegram_id=telegram_id,
            file_id=new_file_id
        )

        if success:
            await message.answer(Messages.Profile.AVATAR_UPDATED)
            if old_file_id_to_delete:
                await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=telegram_id)
        else:
            await message.answer(Messages.Profile.AVATAR_UPDATE_ERROR)
        return success
    except Exception as e:
        logger.error(f"Unexpected error in process_avatar_upload: {e}")
        await message.answer(Messages.Profile.AVATAR_UPDATE_ERROR)
        return False