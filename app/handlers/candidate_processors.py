from typing import Dict, Any, List, Optional, Callable
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateFSM
from app.keyboards.inline import ConfirmationCallback, ContactsVisibilityCallback, SkillLevelCallback, get_confirmation_keyboard, get_contacts_visibility_keyboard, get_skill_kind_keyboard
from app.core.messages import Messages
from app.utils.validators import (
    parse_experience_text, parse_skill_text, parse_project_text, parse_contacts_text,
    ValidationError, validate_list_length
)
from app.services.api_client import file_api_client, candidate_api_client
import logging

logger = logging.getLogger(__name__)

async def process_add_experience_responsibilities(message: Message, state: FSMContext, mode: str = 'register') -> None:
    """Процесс добавления обязанностей к опыту работы."""
    data: Dict[str, Any] = await state.get_data()
    responsibilities: Optional[str] = message.text if message.text and not message.text.startswith('/skip') else None
    company: Optional[str] = data.get('current_exp_company')
    position: Optional[str] = data.get('current_exp_position')
    start_date: Optional[str] = data.get('current_exp_start_date')
    end_date: Optional[str] = data.get('current_exp_end_date')
    try:
        if not all([company, position, start_date]):
            raise ValueError("Missing experience data")
        exp_text = f"company: {company}\nposition: {position}\nstart_date: {start_date}\nend_date: {end_date}\nresponsibilities: {responsibilities or ''}"
        new_experience = parse_experience_text(exp_text)
        key = "experiences" if mode == 'register' else "new_experiences"
        experiences: List[Dict[str, Any]] = data.get(key, [])
        experiences.append(new_experience.model_dump())
        validate_list_length(experiences, max_length=10, item_type="опытов работы")
        await state.update_data(**{key: experiences})
        await state.update_data(current_exp_company=None, current_exp_position=None, current_exp_start_date=None, current_exp_end_date=None)
        added_msg = Messages.Profile.EXPERIENCE_UPDATED if mode == 'edit' else Messages.Profile.EXPERIENCE_ADDED
        await message.answer(added_msg.format(name=new_experience.company), reply_markup=get_confirmation_keyboard(step="exp" if mode == 'edit' else "add_exp"))
        await state.update_data(action_type='add_another_exp')
        await state.set_state(CandidateFSM.confirm_action)
    except (ValueError, ValidationError) as e:
        await message.answer(Messages.Profile.EXPERIENCE_INVALID.format(error=str(e)))
        await state.update_data(current_step='company')
        await state.set_state(CandidateFSM.block_entry)
    except Exception as e:
        logger.error(f"Error in process_add_experience_responsibilities: {str(e)}", exc_info=True)
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_experience(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, mode: str = 'register', next_func: Optional[Callable] = None, show_profile_func: Optional[Callable] = None) -> None:
    """Процесс подтверждения добавления опыта работы."""
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
            await state.update_data(current_step='company')
            await state.set_state(CandidateFSM.block_entry)
        else:
            await callback.message.delete()
            if mode == 'edit':
                data: Dict[str, Any] = await state.get_data()
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
    except Exception as e:
        logger.error(f"Error in process_confirm_add_experience: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.CANCELLED)
    await callback.answer()

async def process_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext, mode: str = 'register') -> None:
    """Процесс выбора уровня навыка."""
    data: Dict[str, Any] = await state.get_data()
    name: Optional[str] = data.get('current_skill_name')
    kind: Optional[str] = data.get('current_skill_kind')
    try:
        if not name or not kind:
            raise ValueError("Missing skill data")
        skill_text = f"name: {name}, kind: {kind}, level: {callback_data.level}"
        new_skill = parse_skill_text(skill_text)
        key = "skills" if mode == 'register' else "new_skills"
        skills: List[Dict[str, Any]] = data.get(key, [])
        skills.append(new_skill.model_dump())
        validate_list_length(skills, max_length=20, item_type="навыков")
        await state.update_data(**{key: skills})
        await state.update_data(current_skill_name=None, current_skill_kind=None)
        added_msg = Messages.Profile.SKILLS_UPDATED if mode == 'edit' else Messages.Profile.SKILL_ADDED
        await callback.message.edit_text(added_msg.format(name=new_skill.skill), reply_markup=get_confirmation_keyboard(step="skill" if mode == 'edit' else "add_skill"))
        await state.update_data(action_type='add_another_skill')
        await state.set_state(CandidateFSM.confirm_action)
    except (ValueError, ValidationError) as e:
        await callback.message.answer(Messages.Profile.SKILL_INVALID.format(error=str(e)))
        await state.update_data(current_step='name')
        await state.set_state(CandidateFSM.block_entry)
    except Exception as e:
        logger.error(f"Error in process_skill_level: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_skill(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, mode: str = 'register', next_func: Optional[Callable] = None, show_profile_func: Optional[Callable] = None) -> None:
    """Процесс подтверждения добавления навыка."""
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_SKILL_NAME)
            await state.update_data(current_step='name')
            await state.set_state(CandidateFSM.block_entry)
        else:
            await callback.message.delete()
            if mode == 'edit':
                data: Dict[str, Any] = await state.get_data()
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
    except Exception as e:
        logger.error(f"Error in process_confirm_add_skill: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.CANCELLED)
    await callback.answer()

async def process_project_links(message: Message, state: FSMContext, mode: str = 'register') -> None:
    """Процесс добавления ссылок к проекту."""
    data: Dict[str, Any] = await state.get_data()
    links_text: Optional[str] = message.text if message.text and not message.text.startswith('/skip') else None
    title: Optional[str] = data.get('current_project_title')
    description: Optional[str] = data.get('current_project_description')
    try:
        if not title:
            raise ValueError("Missing project title")
        new_project = parse_project_text(title=title, description=description, links_text=links_text)
        key = "projects" if mode == 'register' else "new_projects"
        projects: List[Dict[str, Any]] = data.get(key, [])
        projects.append(new_project.model_dump())
        validate_list_length(projects, max_length=10, item_type="проектов")
        await state.update_data(**{key: projects})
        await state.update_data(current_project_title=None, current_project_description=None)
        added_msg = Messages.Profile.PROJECTS_UPDATED if mode == 'edit' else Messages.Profile.PROJECT_ADDED
        await message.answer(added_msg.format(title=new_project.title), reply_markup=get_confirmation_keyboard(step="project" if mode == 'edit' else "add_project"))
        await state.update_data(action_type='add_another_project')
        await state.set_state(CandidateFSM.confirm_action)
    except (ValueError, ValidationError) as e:
        await message.answer(Messages.Profile.PROJECT_INVALID.format(error=str(e)))
        await state.update_data(current_step='title')
        await state.set_state(CandidateFSM.block_entry)
    except Exception as e:
        logger.error(f"Error in process_project_links: {str(e)}", exc_info=True)
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_confirm_add_project(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext, mode: str = 'register', next_func: Optional[Callable] = None, show_profile_func: Optional[Callable] = None) -> None:
    """Процесс подтверждения добавления проекта."""
    try:
        if callback_data.action == "yes":
            await callback.message.edit_text(Messages.Profile.ENTER_PROJECT_TITLE)
            await state.update_data(current_step='title')
            await state.set_state(CandidateFSM.block_entry)
        else:
            await callback.message.delete()
            if mode == 'edit':
                data: Dict[str, Any] = await state.get_data()
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
    except Exception as e:
        logger.error(f"Error in process_confirm_add_project: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.CANCELLED)
    await callback.answer()

async def process_contacts(message: Message, state: FSMContext, mode: str = 'register', next_func: Optional[Callable] = None, show_profile_func: Optional[Callable] = None) -> None:
    """Процесс обработки контактов."""
    try:
        contacts_text: Optional[str] = message.text if message.text and not message.text.startswith('/skip') else None
        if contacts_text:
            new_contacts = parse_contacts_text(contacts_text)
            key = "contacts" if mode == 'register' else "new_contacts"
            await state.update_data(**{key: new_contacts.model_dump()})
            await message.answer(Messages.Profile.CONTACTS_VISIBILITY_SELECT, reply_markup=get_contacts_visibility_keyboard())
            await state.update_data(option_type='contacts_visibility')
            await state.set_state(CandidateFSM.selecting_options)
        else:
            await state.update_data(contacts=None, contacts_visibility="hidden")
            if mode == 'edit':
                data: Dict[str, Any] = await state.get_data()
                update_payload = {"contacts": data.get("new_contacts", {}), "contacts_visibility": "hidden"}
                success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)
                msg = Messages.Profile.CONTACTS_UPDATED if success else Messages.Profile.CONTACTS_UPDATE_ERROR
                await message.answer(msg)
                await state.clear()
                if show_profile_func:
                    await show_profile_func(message, state)
            else:
                if next_func:
                    await next_func(message, state)
    except (ValueError, ValidationError) as e:
        await message.answer(Messages.Profile.CONTACTS_INVALID.format(error=str(e)))
        await state.set_state(CandidateFSM.editing_contacts)
    except Exception as e:
        logger.error(f"Error in process_contacts: {str(e)}", exc_info=True)
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_contacts_visibility(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext, mode: str = 'register', next_func: Optional[Callable] = None, show_profile_func: Optional[Callable] = None) -> None:
    """Процесс обработки видимости контактов."""
    try:
        await state.update_data(contacts_visibility=callback_data.visibility)
        await callback.message.edit_text(f"✅ Видимость контактов: {callback_data.visibility.capitalize()}")
        if mode == 'edit':
            data: Dict[str, Any] = await state.get_data()
            update_payload = {"contacts": data.get("new_contacts", {}), "contacts_visibility": callback_data.visibility}
            success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
            msg = Messages.Profile.CONTACTS_UPDATED if success else Messages.Profile.CONTACTS_UPDATE_ERROR
            await callback.message.answer(msg)
            await state.clear()
            if show_profile_func:
                await show_profile_func(callback, state)
        else:
            if next_func:
                await next_func(callback.message, state)
    except Exception as e:
        logger.error(f"Error in process_contacts_visibility: {str(e)}", exc_info=True)
        await callback.message.answer(Messages.Common.CANCELLED)
    await callback.answer()

async def process_resume_upload(message: Message, state: FSMContext, telegram_id: int) -> bool:
    """Процесс загрузки резюме с валидацией."""
    try:
        await message.answer(Messages.Profile.RESUME_PROCESSING)
        document = message.document
        if document.mime_type not in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            await message.answer(Messages.Profile.RESUME_WRONG_TYPE)
            return False
        if document.file_size > 10 * 1024 * 1024:
            await message.answer(Messages.Profile.RESUME_TOO_BIG)
            return False
        file_info = await message.bot.get_file(document.file_id)
        file_data = await message.bot.download_file(file_info.file_path)
        candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(telegram_id)
        old_file_id = candidate_profile.get("resumes")[0]["file_id"] if candidate_profile and candidate_profile.get("resumes") else None
        extension = document.file_name.split('.')[-1].lower()
        content_type = 'application/pdf' if extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        file_response = await file_api_client.upload_file(
            filename=document.file_name,
            file_data=file_data.read(),
            content_type=content_type,
            owner_id=telegram_id,
            file_type='resume'
        )
        if not file_response:
            await message.answer(Messages.Profile.RESUME_UPDATE_ERROR)
            return False
        success = await candidate_api_client.replace_resume(telegram_id, file_response['id'])
        if success and old_file_id:
            await file_api_client.delete_file(old_file_id, owner_telegram_id=telegram_id)
        await message.answer(Messages.Profile.RESUME_UPDATED if success else Messages.Profile.RESUME_UPDATE_ERROR)
        return success
    except Exception as e:
        logger.error(f"Error in process_resume_upload: {str(e)}", exc_info=True)
        await message.answer(Messages.Profile.RESUME_UPDATE_ERROR)
        return False

async def process_avatar_upload(message: Message, state: FSMContext, telegram_id: int) -> bool:
    """Процесс загрузки аватара с валидацией."""
    try:
        await message.answer(Messages.Profile.AVATAR_PROCESSING)
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        file_data = await message.bot.download_file(file_info.file_path)
        candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(telegram_id)
        old_file_id = candidate_profile.get("avatars")[0]["file_id"] if candidate_profile and candidate_profile.get("avatars") else None
        extension = file_info.file_path.split('.')[-1].lower()
        content_type = 'image/jpeg' if extension in ['jpg', 'jpeg'] else 'image/png'
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
        success = await candidate_api_client.replace_avatar(telegram_id, file_response['id'])
        if success and old_file_id:
            await file_api_client.delete_file(old_file_id, owner_telegram_id=telegram_id)
        await message.answer(Messages.Profile.AVATAR_UPDATED if success else Messages.Profile.AVATAR_UPDATE_ERROR)
        return success
    except Exception as e:
        logger.error(f"Error in process_avatar_upload: {str(e)}", exc_info=True)
        await message.answer(Messages.Profile.AVATAR_UPDATE_ERROR)
        return False