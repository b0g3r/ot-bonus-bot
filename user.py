import logging

from aiogram import types

from common import check_voting_end, bot, dp, send_vote_status

logger = logging.getLogger(__name__)

STEPS = [0, 1, 3]


@dp.callback_query_handler(func=lambda q: q.data == 'check', state='voting')
async def voting(callback_query: types.CallbackQuery):
    """
    Обрабатывает нажатие на клавишу "готово" в сообщении голосовании
    """
    with dp.current_state(chat=callback_query.from_user.id, user=callback_query.from_user.id) as \
            state:
        data = await state.get_data()
        await state.update_data({'completed': True})
        logger.info(f"{state.user} закончил")
        await bot.edit_message_text(
            'Голосование закончено, ожидаем оставшихся',
            callback_query.from_user.id,
            data['vote_message_id'],
        )
        await check_voting_end()
        await state.set_state('end')
        await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(state='voting')
async def voting(callback_query: types.CallbackQuery):
    """
    Обрабатывает нажатие на клавиши выбора и меняет сообщение на приглашение к вводу
    """
    with dp.current_state(chat=callback_query.from_user.id, user=callback_query.from_user.id) as \
            state:
        data = await state.get_data()
        info = data['candidates'][callback_query.data]
        data['candidates'][callback_query.data] = info[0], next_step(info[1])
        await state.update_data({'candidates': data['candidates']})
        await bot.answer_callback_query(callback_query.id)
        await send_vote_status(state)


def next_step(step: int):
    count = len(STEPS)
    index = STEPS.index(step)
    return STEPS[(index+1)%count]