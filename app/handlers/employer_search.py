from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional, List
from app.states.employer import EmployerSearch
from app.services.api_client import employer_api_client, search_api_client, candidate_api_client, file_api_client
from app.keyboards.inline import get_liked_candidate_keyboard, get_initial_search_keyboard, SearchResultAction, SearchResultDecision
from app.utils.formatters import format_candidate_profile
from app.core.messages import Messages
import logging

router = Router()
logger = logging.getLogger(__name__)

async def show_candidate_profile(message: Message | CallbackQuery, state: FSMContext) -> None:
    """Отображение профиля кандидата в поиске."""
    data: Dict[str, Any] = await state.get_data()
    idx: int = data.get('current_index', 0)
    found_profiles: List[Dict[str, Any]] = data.get('found_profiles', [])
    session_id: Optional[str] = data.get('session_id')
    target_message = message.message if isinstance(message, CallbackQuery) else message

    if not found_profiles or idx >= len(found_profiles):
        await target_message.answer(Messages.EmployerSearch.NO_MORE)
        if isinstance(message, CallbackQuery): await message.answer()
        await state.clear()
        return

    profile = found_profiles[idx]
    candidate_id = profile['id']

    avatar_url: Optional[str] = None
    if profile.get("avatar_file_id"):
        avatar_url = await file_api_client.get_download_url_by_file_id(profile["avatar_file_id"])

    caption = format_candidate_profile(profile)
    has_resume = profile.get("has_resume", False)
    keyboard = get_initial_search_keyboard(candidate_id, has_resume)

    current_message_is_photo = bool(target_message.photo)

    try:
        if avatar_url:
            if current_message_is_photo:
                await target_message.edit_media(media=InputMediaPhoto(media=avatar_url, caption=caption),
                                                reply_markup=keyboard)
            else:
                await target_message.delete()
                await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
        else:
            if current_message_is_photo:
                await target_message.delete()
                await target_message.answer(text=caption, reply_markup=keyboard)
            else:
                await target_message.edit_text(text=caption, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error showing candidate profile for user {message.from_user.id}: {str(e)}")
        await target_message.answer(text=caption, reply_markup=keyboard)

    if isinstance(message, CallbackQuery):
        await message.answer()

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Обработка команды /search."""
    await state.clear()
    logger.info(f"User {message.from_user.id} started search")
    await state.update_data(filter_step='role')
    await state.set_state(EmployerSearch.entering_filters)
    await message.answer(Messages.EmployerSearch.STEP_1)

@router.message(EmployerSearch.entering_filters)
async def handle_filter_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода фильтров."""
    data: Dict[str, Any] = await state.get_data()
    filter_step: Optional[str] = data.get("filter_step")
    if filter_step is None:
        logger.warning(f"No filter_step for user {message.from_user.id}")
        await message.answer(Messages.Common.INVALID_INPUT)
        return
    logger.info(f"User {message.from_user.id} entering filter: {filter_step}, input={message.text}")
    try:
        if filter_step == "role":
            await state.update_data(role=message.text)
            await message.answer(Messages.EmployerSearch.STEP_2)
            await state.update_data(filter_step="must_skills")
        elif filter_step == "must_skills":
            skills = [s.strip().lower() for s in message.text.split(",")]
            await state.update_data(must_skills=skills)
            await message.answer(Messages.EmployerSearch.STEP_3)
            await state.update_data(filter_step="nice_skills")
        elif filter_step == "nice_skills":
            if message.text != "/skip":
                skills = [s.strip().lower() for s in message.text.split(",")]
                await state.update_data(nice_skills=skills)
            await message.answer(Messages.EmployerSearch.STEP_4)
            await state.update_data(filter_step="experience")
        elif filter_step == "experience":
            parts = message.text.replace(",", ".").split("-")
            exp_min = float(parts[0].strip())
            exp_max = float(parts[1].strip()) if len(parts) > 1 else None
            await state.update_data(experience_min=exp_min, experience_max=exp_max)
            await message.answer(Messages.EmployerSearch.STEP_5)
            await state.update_data(filter_step="location_and_work_modes")
        elif filter_step == "location_and_work_modes":
            if message.text != "/skip":
                await state.update_data(location_query=message.text)
            await message.answer(Messages.EmployerSearch.SAVING, reply_markup=ReplyKeyboardRemove())
            filters = await state.get_data()
            employer_profile = await employer_api_client.get_or_create_employer(
                message.from_user.id, message.from_user.username
            )
            if not employer_profile:
                await message.answer(Messages.EmployerSearch.EMPLOYER_ERROR)
                await state.clear()
                return
            await state.update_data(employer_profile=employer_profile)
            search_session = await employer_api_client.create_search_session(employer_profile["id"], filters)
            if not search_session:
                await message.answer(Messages.EmployerSearch.SEARCH_ERROR)
                await state.clear()
                return
            await state.update_data(session_id=search_session["id"])
            filters["page"] = 1
            filters["size"] = 5
            search_response = await search_api_client.search_candidates(filters)
            if not search_response or not search_response.get("results"):
                await message.answer(Messages.EmployerSearch.NO_RESULTS)
                await state.clear()
                return
            found_profiles = []
            for res in search_response["results"]:
                candidate_id = res["candidate_id"]
                profile = await candidate_api_client.get_candidate(candidate_id)
                if profile:
                    found_profiles.append(profile)
            if not found_profiles:
                await message.answer(Messages.EmployerSearch.NO_RESULTS)
                await state.clear()
                return
            total_found = search_response.get("total", len(found_profiles))
            await state.update_data(found_profiles=found_profiles, current_index=0)
            await state.set_state(EmployerSearch.showing_results)
            await message.answer(Messages.EmployerSearch.FOUND.format(total=total_found))
            await show_candidate_profile(message, state)

    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid filter input from user {message.from_user.id}: {str(e)}")
        await message.answer(Messages.Common.INVALID_INPUT)

async def process_next_candidate(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход к следующему кандидату."""
    data: Dict[str, Any] = await state.get_data()
    new_index = data.get('current_index', 0) + 1
    await state.update_data(current_index=new_index)
    await show_candidate_profile(callback, state)

@router.callback_query(SearchResultDecision.filter(), EmployerSearch.showing_results)
async def handle_decision(callback: CallbackQuery, callback_data: SearchResultDecision, state: FSMContext) -> None:
    """Обработка решения по кандидату (like/next)."""
    data: Dict[str, Any] = await state.get_data()
    session_id: Optional[str] = data.get("session_id")
    if not session_id:
        await callback.answer(Messages.EmployerSearch.SESSION_EXPIRED, show_alert=True)
        return
    success = await employer_api_client.save_decision(
        session_id=session_id,
        candidate_id=callback_data.candidate_id,
        decision=callback_data.action
    )
    if not success:
        await callback.answer(Messages.EmployerSearch.DECISION_ERROR, show_alert=True)
        return
    if callback_data.action == "like":
        await callback.answer(Messages.EmployerSearch.DECISION_LIKE)
        new_keyboard = get_liked_candidate_keyboard(callback_data.candidate_id)
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await callback.answer("Выбор сохранен.")
        await process_next_candidate(callback, state)

@router.callback_query(SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results)
async def handle_next_candidate(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход к следующему кандидату."""
    await process_next_candidate(callback, state)

@router.callback_query(SearchResultAction.filter(F.action == "contact"), EmployerSearch.showing_results)
async def handle_show_contact(callback: CallbackQuery, callback_data: SearchResultAction, state: FSMContext) -> None:
    """Запрос контактов кандидата."""
    data: Dict[str, Any] = await state.get_data()
    employer_profile = data.get('employer_profile')
    if not employer_profile:
        await callback.answer(Messages.EmployerSearch.SESSION_EXPIRED, show_alert=True)
        return
    await callback.answer(Messages.EmployerSearch.CONTACTS_REQUEST, show_alert=False)
    response = await employer_api_client.request_contacts(
        employer_id=employer_profile['id'],
        candidate_id=callback_data.candidate_id
    )
    if not response:
        await callback.message.answer(Messages.EmployerSearch.CONTACTS_ERROR)
        return
    if response.get("granted") and response.get("contacts"):
        contacts = response["contacts"]
        contact_text = "\n".join([f"<b>{key.capitalize()}:</b> {value}" for key, value in contacts.items()])
        await callback.message.answer(Messages.EmployerSearch.CONTACTS_GRANTED.format(contacts=contact_text))
    else:
        await callback.message.answer(Messages.EmployerSearch.CONTACTS_DENIED)

@router.callback_query(SearchResultAction.filter(F.action == "get_resume"), EmployerSearch.showing_results)
async def handle_get_resume(callback: CallbackQuery, callback_data: SearchResultAction, state: FSMContext) -> None:
    """Получение резюме кандидата."""
    await callback.answer("Запрашиваю профиль...")
    profile = await candidate_api_client.get_candidate(callback_data.candidate_id)
    if not profile or not profile.get("resumes"):
        await callback.message.answer(Messages.EmployerSearch.RESUME_NONE)
        return
    file_id = profile["resumes"][0]["file_id"]
    await callback.answer("Запрашиваю ссылку на файл...")
    link = await file_api_client.get_download_url_by_file_id(file_id)
    if link:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать файл", url=link)]
        ])
        await callback.message.answer(
            Messages.EmployerSearch.RESUME_LINK,
            reply_markup=keyboard
        )
    else:
        await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)