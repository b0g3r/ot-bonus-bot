import asyncio
import logging
from typing import Dict, Tuple

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.redis import RedisStorage
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config

logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()
bot = Bot(token=config.API_TOKEN, loop=loop)

storage = RedisStorage()
dp = Dispatcher(bot, storage=storage)


async def check_voting_end():
    """
    Проверяет что голосование закончено, и если оно закончено -- рассылает уведомление.
    Админу -- общий результат
    """
    admin_state = dp.current_state(chat=config.ADMIN_ID, user=config.ADMIN_ID)
    participants = {}
    names = {}
    total_bonus_amount = 0
    for participant_id, (name, bonus) in (await admin_state.get_data())['participants'].items():
        names[participant_id] = name
        total_bonus_amount += bonus
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        participant_data = await participant_state.get_data()
        participants[participant_id] = participant_data

    for participant_id, participant_data in participants.items():
        if not participant_data['completed']:
            return

    poll_result = {p_id: 0 for p_id in participants}
    for participant_id, participant_data in participants.items():
        # перебираем всех участников и сохраняем результаты голосования и наполняем сумму бонусов
        candidates = participant_data['candidates']
        for id, (_, point) in candidates.items():
            poll_result[id] += point

    point_parts = {p_id: 0 for p_id in participants}
    for participant_id, points in poll_result.items():
        participant_data = participants[participant_id]
        point_parts[participant_id] = points*participant_data['bonus']

    total_point_amount = sum(point_parts.values())

    bonus_parts = {
        p_id: points and int((points/total_point_amount)*total_bonus_amount)
        for p_id, points in point_parts.items()
    }

    for participant_id, calc_bonus in bonus_parts.items():
        # перебираем кандидатов и вычисляем бонус
        old_bonus = participants[participant_id]['bonus']
        await bot.send_message(participant_id, 'Твоя премия: {0}. У тебя было {1}'.format(
            calc_bonus,
            old_bonus
        ))
    await bot.send_message(
        config.ADMIN_ID,
        '\n'.join(
            '{0}: {1}'.format(names[p_id], bonus) for p_id, bonus in bonus_parts.items()
        )
    )


async def send_vote_status(state: FSMContext):
    """
    Отправляет участнику голосования текущий статус его голосования
    """
    data = await state.get_data()
    message_parts = [
        'Короче, голосование',
        "Кликай, пока не надоест"
    ]
    inline_keyboard = InlineKeyboardMarkup(row_width=1)
    for id, (name, point) in data['candidates'].items():
        inline_keyboard.add(InlineKeyboardButton(f"{name}: {point}", callback_data=id))
    inline_keyboard.add(InlineKeyboardButton('Завершить голосование', callback_data='check'))
    message_id = data.get('vote_message_id')
    if message_id:
        await bot.edit_message_reply_markup(
            state.user,
            message_id,
            reply_markup=inline_keyboard
        )
    else:
        message_id = (await bot.send_message(
            state.user,
            "\n".join(message_parts),
          reply_markup=inline_keyboard
        ))['message_id']

    await state.update_data({'vote_message_id': message_id})
    await state.set_state('voting')
