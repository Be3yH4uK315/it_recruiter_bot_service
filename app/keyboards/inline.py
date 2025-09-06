from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class RoleCallback(CallbackData, prefix="role"):
    role_name: str


class SearchResultAction(CallbackData, prefix="search_res"):
    action: str
    candidate_id: str


def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="👤 Я кандидат",
                callback_data=RoleCallback(role_name="candidate").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🏢 Я работодатель",
                callback_data=RoleCallback(role_name="employer").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_search_results_keyboard(candidate_id: str, is_last: bool) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text="📞 Показать контакты",
            callback_data=SearchResultAction(action="contact", candidate_id=candidate_id).pack()
        )
    ]
    if not is_last:
        buttons.append(
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=SearchResultAction(action="next", candidate_id="0").pack()
            )
        )

    keyboard = [buttons]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
