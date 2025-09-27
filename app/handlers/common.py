from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from app.keyboards.inline import get_role_selection_keyboard, RoleCallback
from app.services.api_client import candidate_api_client
from app.states.candidate import CandidateFSM
from app.states.employer import EmployerSearch
from app.core.messages import Messages
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start."""
    await state.clear()
    logger.info(f"User {message.from_user.id} started /start")
    await message.answer(Messages.Common.START, reply_markup=get_role_selection_keyboard())

@router.callback_query(RoleCallback.filter(F.role_name == "candidate"))
async def cq_select_candidate(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор роли кандидата."""
    await callback.answer()
    user = callback.from_user
    logger.info(f"User {user.id} selected candidate role")
    await candidate_api_client.create_candidate(telegram_id=user.id, telegram_name=user.username or user.full_name)
    await state.update_data(mode='register', current_field='display_name')
    await callback.message.edit_text(Messages.Profile.ENTER_NAME)
    await state.set_state(CandidateFSM.entering_basic_info)

@router.callback_query(RoleCallback.filter(F.role_name == "employer"))
async def cq_select_employer(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор роли работодателя."""
    await callback.answer()
    logger.info(f"User {callback.from_user.id} selected employer role")
    await state.update_data(filter_step='role')
    await state.set_state(EmployerSearch.entering_filters)
    await callback.message.edit_text(Messages.EmployerSearch.STEP_1)

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Обработка команды /search."""
    logger.info(f"User {message.from_user.id} started /search")
    await state.update_data(filter_step='role')
    await state.set_state(EmployerSearch.entering_filters)
    await message.answer(Messages.EmployerSearch.STEP_1)