import os
import logging
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram import Update
from openai import OpenAI

# ── Настройки из переменных окружения ──────────────────────────────────────────
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AUTO_MODE = os.getenv("AUTO_MODE", "off")  # off | group

# ── Логирование ───────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("lior-bot")

# ── Клиент OpenAI ─────────────────────────────────────────────────────────────
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты — Lior Bot, бережный медиатор. В группе отвечаешь только по команде. "
    "Избегай ярлыков и обвинений. Формат: Наблюдение → Риск → Мягкий шаг. Коротко, уважительно."
)

def _window(ctx: ContextTypes.DEFAULT_TYPE, n: int = 10):
    hist = ctx.chat_data.get("history", [])
    return "\n".join(hist[-n:]) if hist else ""

async def cmd_start(update, ctx):
    await update.message.reply_text("Lior Bot включён. Команды: /tone, /suggest, /pause, /coach_on, /coach_off")

async def cmd_coach_on(update, ctx):
    ctx.chat_data["coach_on"] = True
    await update.message.reply_text("Режим коуча: ВКЛ (отвечаю только по командам).")

async def cmd_coach_off(update, ctx):
    ctx.chat_data["coach_on"] = False
    await update.message.reply_text("Режим коуча: ВЫКЛ.")

async def _ask_gpt(prompt: str) -> str:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role":"system","content":SYSTEM_PROMPT},
                  {"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content.strip()

async def cmd_tone(update, ctx):
    text = _window(ctx, 12) or (update.message.text or "")
    prompt = (
        "Проанализируй эмоциональный тон последних сообщений ниже. "
        "Дай 3 пункта: 1) Наблюдение (факты: короткие ответы, обобщения и т.п.); "
        "2) Риск (что может ухудшить контакт); "
        "3) Мягкий шаг (1 я‑сообщение + 1 открытый вопрос без «почему»).\n\n"
        f"Сообщения:\n{text}"
    )
    await update.message.reply_text(await _ask_gpt(prompt))

async def cmd_suggest(update, ctx):
    base = ("Дай 3 варианта продолжения диалога: 1) тёплый, 2) нейтральный, 3) твёрдо‑бережный. "
            "Каждый — 1–2 предложения, без обвинений и без слова «почему».")
    await update.message.reply_text(await _ask_gpt(base))

async def cmd_pause(update, ctx):
    await update.message.reply_text(
        "Пауза 30–60 сек. Я‑сообщение: «Я сейчас чувствую… и хочу понять тебя лучше». "
        "Один уточняющий вопрос без «почему»."
    )

async def on_message(update, ctx):
    txt = update.message.text or ""
    if not txt:
        return
    hist = ctx.chat_data.get("history", [])
    name = (update.effective_user.first_name or "User").strip()
    hist.append(f"{name}: {txt}")
    ctx.chat_data["history"] = hist[-40:]

    # ЩАДЯЩИЙ авто‑режим (по желанию)
    if AUTO_MODE == "group" and ctx.chat_data.get("coach_on"):
        if len(ctx.chat_data["history"]) % 12 == 0:  # редко, чтобы не раздражать
            text = _window(ctx, 10)
            prompt = ("Коротко подсвети динамику в 1–2 предложениях. "
                      "Без ярлыков и обвинений. Один мягкий шаг.\n\n"
                      f"Сообщения:\n{text}")
            try:
                await update.message.reply_text(await _ask_gpt(prompt))
            except Exception as e:
                logging.warning(f"auto mode error: {e}")

if __name__ == "__main__":
    app = Application.builder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("coach_on", cmd_coach_on))
    app.add_handler(CommandHandler("coach_off", cmd_coach_off))
    app.add_handler(CommandHandler("tone", cmd_tone))
    app.add_handler(CommandHandler("suggest", cmd_suggest))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    logging.info("Lior Bot started.")
    app.run_polling()
