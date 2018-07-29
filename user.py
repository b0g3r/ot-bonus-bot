import logging

from aiogram import types

from common import check_voting_end, bot, dp, calculate_rest, send_vote_status

logger = logging.getLogger(__name__)


@dp.callback_query_handler(func=lambda q: q.data == 'check', state='voting')
async def voting(callback_query: types.CallbackQuery):
    """
    Обрабатывает нажатие на клавишу "готово" в сообщении голосовании
    """
    with dp.current_state(chat=callback_query.from_user.id, user=callback_query.from_user.id) as \
            state:
        data = await state.get_data()
        if calculate_rest(data['bonus'], data['candidates']) != 0:
            await bot.answer_callback_query(callback_query.id, 'Остаток не равен 0')
        else:
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
        await bot.edit_message_text(
            f"Голосуй за {data['candidates'][callback_query.data][0]}. Вводи сколько готов отдать.",
            callback_query.from_user.id,
            data['vote_message_id'],
        )
        await state.update_data({'candidate': callback_query.data})
        await state.set_state('bonus_input')
        await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state='bonus_input')
async def bonus_input(message: types.Message):
    """
    Обрабатывает ввод пользователя и присваивает голос выбранному кандидату
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        data = await state.get_data()
        try:
            bonus = int(message.text)
        except ValueError:
            await message.reply('Это не число даже')
            return
        if bonus < 0:
            await message.reply('Соси жопу, нельзя в минус')
            return

        candidate = data['candidate']
        candidates = data['candidates']
        candidates[candidate] = candidates[candidate][0], bonus
        await state.update_data({'candidates': candidates})
        await send_vote_status(state)

