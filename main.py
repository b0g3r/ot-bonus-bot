from aiogram.utils.executor import start_polling

from bot import loop, dp

if __name__ == '__main__':
    start_polling(dp, loop=loop, skip_updates=True)
