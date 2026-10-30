import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from mistralai import Mistral

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
MY_TELEGRAM_ID = int(os.getenv("MY_TELEGRAM_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
mistral_client = Mistral(api_key=MISTRAL_KEY)

PROMPT_TEMPLATE = """Ты — редактор иронично-позитивного новостного дайджеста.

**Игнорируй (ответ строго `IGNORE`):**
- Рекламу и самопиар.
- Пустую политику, формальные заявления, назначения и подписание законов без интересных практических последствий.
- Бессодержательный кликбейт и информационный шум.
- Новости, из которых совершенно невозможно извлечь интересную сторону.

**Не игнорируй негативные новости!** Рост цен, кризисы, аварии, задержки, дефицит и прочие неприятности — основной материал для юмора.

**Если новость подходит:**
Перепиши её суть в один короткий абзац, иронично и позитивно. Ищи забавные последствия, неожиданные преимущества и абсурдно-позитивные стороны происходящего. Допускается сарказм и лёгкая гипербола, но не выдумывай факты. Не шути над жертвами трагедий.

Без заголовков, вводных фраз и объяснений. Сразу переходи к пересказу.

**Формат:** либо один короткий юмористический абзац, либо строго `IGNORE`.

Текст новости для анализа:
{news_text}"""

async def handle_webhook_news(request):
    try:
        data = await request.json()
    except Exception:
        return web.Response(text="Invalid JSON", status=400)
        
    raw_news = data.get("text", "")
    if not raw_news:
        return web.Response(text="No text provided", status=400)

    try:
        response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(news_text=raw_news)}],
            temperature=0.2,
            max_tokens=300
        )
    except Exception as e:
        return web.Response(text=f"API Error: {str(e)}", status=500)
    
    result_text = response.choices.message.content.strip()

    clean_text = re.sub(r'[^\w\s]', '', result_text).strip().upper()
    if clean_text.startswith("IGNORE"):
        return web.Response(text="Ignored by LLM", status=200)

    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🚀 Опубликовать в канал", callback_data="approve"))

    await bot.send_message(
        chat_id=MY_TELEGRAM_ID,
        text=result_text,
        reply_markup=builder.as_markup()
    )
    return web.Response(text="OK", status=200)

@dp.callback_query(lambda c: c.data == "approve")
async def process_approve(callback_query: types.CallbackQuery):
    approved_text = callback_query.message.text
    await bot.send_message(chat_id=CHANNEL_ID, text=approved_text)
    await bot.edit_message_text(
        text=f"✅ **Опубликовано:**\n\n{approved_text}",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id
    )
    await callback_query.answer("Успешно опубликовано!")

app = web.Application()
app.router.add_post('/webhook/news', handle_webhook_news)

if __name__ == '__main__':
    from aiogram.webhook.aiohttp_impl import SimpleRequestHandler
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook/tg")
    web.run_app(app, host="0.0.0.0", port=8080)
