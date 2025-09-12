from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class RoleCallback(CallbackData, prefix="role"):
    role_name: str


class EditFieldCallback(CallbackData, prefix="edit_field"):
    field_name: str


class WorkModeCallback(CallbackData, prefix="work_mode"):
    mode: str


class ProfileAction(CallbackData, prefix="profile_action"):
    action: str


class SearchResultDecision(CallbackData, prefix="search_dec"):
    action: str
    candidate_id: str


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


def get_work_modes_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Удаленно", callback_data=WorkModeCallback(mode="remote").pack()),
            InlineKeyboardButton(text="Офис", callback_data=WorkModeCallback(mode="office").pack()),
            InlineKeyboardButton(text="Гибрид", callback_data=WorkModeCallback(mode="hybrid").pack()),
        ],
        [
            InlineKeyboardButton(text="Готово", callback_data=WorkModeCallback(mode="done").pack())
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_profile_actions_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data=ProfileAction(action="edit").pack())],
        [InlineKeyboardButton(text="📄 Загрузить/обновить резюме", callback_data=ProfileAction(action="upload_resume").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_initial_search_keyboard(candidate_id: str, has_resume: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="👍 Подходит",
                callback_data=SearchResultDecision(action="like", candidate_id=candidate_id).pack()
            ),
            InlineKeyboardButton(
                text="👎 Не подходит",
                callback_data=SearchResultDecision(action="dislike", candidate_id=candidate_id).pack()
            )
        ]
    ]

    if has_resume:
        keyboard.append([
            InlineKeyboardButton(
                text="📄 Скачать резюме",
                callback_data=SearchResultAction(action="get_resume", candidate_id=candidate_id).pack()
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➡️ Следующий (пропустить)",
            callback_data=SearchResultAction(action="next", candidate_id="0").pack()
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_liked_candidate_keyboard(candidate_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="📞 Показать контакты",
                callback_data=SearchResultAction(action="contact", candidate_id=candidate_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=SearchResultAction(action="next", candidate_id="0").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Должность", callback_data=EditFieldCallback(field_name="headline_role").pack()),
            InlineKeyboardButton(text="Опыт", callback_data=EditFieldCallback(field_name="experience_years").pack()),
        ],
        [
            InlineKeyboardButton(text="Навыки", callback_data=EditFieldCallback(field_name="skills").pack()),
            InlineKeyboardButton(text="Локация", callback_data=EditFieldCallback(field_name="location").pack()),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=EditFieldCallback(field_name="back").pack())
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
