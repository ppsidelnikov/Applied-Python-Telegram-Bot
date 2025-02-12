from aiogram import BaseMiddleware
from aiogram.types import Message 

class LogginMiddleware(BaseMiddleware):
    async def __call__(sel, handler, event: Message, data: dict):
        print(f'Получено сообщение: {event.text}')
        return await handler(event, data)