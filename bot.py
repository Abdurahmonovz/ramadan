import asyncio
from datetime import datetime, timedelta, date as dt_date
import pytz

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from db import DB
from prayers import get_today
from keyboards import main_menu, stop_menu, reminder_inline, city_inline
from texts import WELCOME, DUA_OCHISH, DUA_YOPISH, GROUP_HELP

cfg = load_config()
db = DB()
router = Router()

# chat_id -> asyncio.Task (jonli countdown)  ✅ group/DM uchun mos
LIVE_TASKS: dict[int, asyncio.Task] = {}
# user_id -> temp reminder minutes
TEMP_REM: dict[int, int] = {}

def now_tz() -> datetime:
    return datetime.now(pytz.timezone(cfg.tz))

def parse_hhmm(s: str) -> datetime:
    hhmm = (s or "").strip()[:5]
    return datetime.strptime(hhmm, "%H:%M")

def build_targets(times: dict) -> tuple[datetime, datetime]:
    tz = pytz.timezone(cfg.tz)
    d = now_tz().date()
    imsak_dt = tz.localize(datetime.combine(d, parse_hhmm(times["imsak"]).time()))
    magh_dt = tz.localize(datetime.combine(d, parse_hhmm(times["maghrib"]).time()))
    return imsak_dt, magh_dt

def fmt_countdown(delta: timedelta) -> str:
    sec = int(delta.total_seconds())
    if sec < 0:
        sec = 0
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

async def stop_live(chat_id: int) -> None:
    task = LIVE_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except Exception:
            pass

async def live_message_loop(bot: Bot, chat_id: int, user_id: int, mode: str, msg_id: int):
    """
    mode: 'imsak' or 'maghrib'
    1 ta xabarni sekundiga edit qilib countdown qiladi.
    chat_id: group/DM
    user_id: kim ishga tushirgan bo‘lsa shahar/sozlama shundan olinadi
    """
    while True:
        user = await db.get(user_id)
        if not user:
            return

        try:
            times = await get_today(user["city"], cfg.country)
            imsak_dt, magh_dt = build_targets(times)
        except Exception:
            await asyncio.sleep(2)
            continue

        now = now_tz()

        if mode == "imsak":
            target = imsak_dt
            title = "🌙 Og‘iz yopishga oz qoldi"
            target_txt = f"Imsak: {times['imsak']}"
        else:
            target = magh_dt
            title = "🍽 Og‘iz ochishga oz qoldi"
            target_txt = f"Maghrib: {times['maghrib']}"

        diff = target - now
        text = (
            f"{title}\n"
            f"📍 {user['city']}\n"
            f"🕰 {target_txt}\n"
            f"⏳ {fmt_countdown(diff)}\n\n"
            f"🛑 To‘xtatish bossangiz eslatma to‘xtaydi."
        )

        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id)
        except Exception:
            return

        if diff.total_seconds() <= 0:
            await bot.send_message(chat_id, "✅ Vaqt bo‘ldi!")
            return

        await asyncio.sleep(1)

async def start_live(bot: Bot, chat_id: int, user_id: int, mode: str):
    # bir chatda bitta countdown
    if chat_id in LIVE_TASKS:
        return
    msg = await bot.send_message(chat_id, "⏳ Eslatma boshlandi…", reply_markup=stop_menu())
    task = asyncio.create_task(live_message_loop(bot, chat_id, user_id, mode, msg.message_id))
    LIVE_TASKS[chat_id] = task

def choose_mode(imsak_dt: datetime, magh_dt: datetime, now: datetime) -> str:
    if now < imsak_dt:
        return "imsak"
    if now < magh_dt:
        return "maghrib"
    # bugun o‘tib ketgan bo‘lsa, ertaga imsakga sanaydi (soddaroq)
    return "imsak"

# ===== Commands =====

@router.message(CommandStart())
async def start(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer(WELCOME, reply_markup=main_menu())
    if m.chat.type != "private":
        await m.answer(GROUP_HELP)

@router.message(Command("ramadan"))
async def ramadan_cmd(m: Message):
    # group/kanalda ishlaydi: shu chatga vaqt + countdown chiqaradi
    await db.ensure(m.from_user.id)
    user = await db.get(m.from_user.id)

    t = await get_today(user["city"], cfg.country)
    imsak_dt, magh_dt = build_targets(t)
    now = now_tz()
    mode = choose_mode(imsak_dt, magh_dt, now)

    await stop_live(m.chat.id)
    await m.answer(
        f"📍 {user['city']}\n"
        f"🌙 Og‘iz yopish (Imsak): {t['imsak']}\n"
        f"🍽 Og‘iz ochish (Maghrib): {t['maghrib']}\n\n"
        f"⏳ Countdown boshlanmoqda…",
        reply_markup=stop_menu()
    )

    # oxirgi yuborgan xabarga countdown bog‘laymiz
    # (eng yaxshisi: yangi xabar yuborib, o‘shani edit qilamiz)
    msg = await m.answer("⏳ ...", reply_markup=stop_menu())
    await start_live(m.bot, m.chat.id, m.from_user.id, mode)

# ===== Menu actions =====

@router.message(F.text == "🍽 Og‘iz ochish duosi")
async def dua_ochish(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer(DUA_OCHISH, reply_markup=main_menu())

@router.message(F.text == "🌙 Og‘iz yopish duosi")
async def dua_yopish(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer(DUA_YOPISH, reply_markup=main_menu())

@router.message(F.text == "📍 Shahar")
async def city(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer("Shaharni tanlang:", reply_markup=city_inline())

@router.callback_query(F.data.startswith("city:"))
async def city_cb(c: CallbackQuery):
    await db.ensure(c.from_user.id)
    val = c.data.split(":", 1)[1]

    if val == "custom":
        await c.message.answer("✍️ Shahar nomini yozing (masalan: Tashkent yoki Samarkand).")
        await c.answer()
        return

    await db.set_city(c.from_user.id, val)
    await c.message.answer(f"✅ Shahar saqlandi: {val}", reply_markup=main_menu())
    await c.answer("OK")

@router.message(F.text.regexp(r"^[A-Za-zА-Яа-я‘’'` \-]{3,40}$"))
async def custom_city_text(m: Message):
    await db.ensure(m.from_user.id)
    city = m.text.strip()

    try:
        _ = await get_today(city, cfg.country)
    except Exception:
        return

    await db.set_city(m.from_user.id, city)
    await m.answer(f"✅ Shahar saqlandi: {city}", reply_markup=main_menu())

@router.message(F.text == "⏳ Bugungi vaqtlar")
async def today_times(m: Message):
    await db.ensure(m.from_user.id)
    user = await db.get(m.from_user.id)
    t = await get_today(user["city"], cfg.country)

    await m.answer(
        f"📍 {user['city']}\n\n"
        f"🌙 Og‘iz yopish (Imsak): {t['imsak']}\n"
        f"🍽 Og‘iz ochish (Maghrib): {t['maghrib']}\n\n"
        f"Bot sahar/iftordan oldin avtomatik countdownni yoqadi.",
        reply_markup=main_menu()
    )

@router.message(F.text == "🔔 Eslatma sozlash")
async def remind(m: Message):
    await db.ensure(m.from_user.id)
    user = await db.get(m.from_user.id)
    TEMP_REM[m.from_user.id] = int(user["remind_before"])
    await m.answer("Necha minut oldin eslatsin? (Default: 10)", reply_markup=reminder_inline(TEMP_REM[m.from_user.id]))

@router.callback_query(F.data.startswith("rem:"))
async def rem_cb(c: CallbackQuery):
    await db.ensure(c.from_user.id)
    cur = TEMP_REM.get(c.from_user.id, 10)
    act = c.data.split(":", 1)[1]

    if act == "+5":
        cur = min(120, cur + 5)
    elif act == "-5":
        cur = max(1, cur - 5)
    elif act == "save":
        await db.set_remind_before(c.from_user.id, cur)
        await c.message.answer(f"✅ Saqlandi: {cur} minut oldin eslatadi.", reply_markup=main_menu())
        await c.answer("Saved")
        return

    TEMP_REM[c.from_user.id] = cur
    await c.message.edit_reply_markup(reply_markup=reminder_inline(cur))
    await c.answer()

@router.message(F.text == "🛑 To‘xtatish")
async def stop_btn(m: Message):
    await stop_live(m.chat.id)
    await m.answer("🛑 To‘xtatildi.", reply_markup=main_menu())

# ===== Auto reminders (DM only) =====
async def reminder_tick(bot: Bot):
    """
    Avtomatik reminder: faqat user DM (private chat) uchun ishlaydi.
    Group/kanal uchun /ramadan bilan start qiling.
    """
    users = await db.list_enabled()
    now = now_tz()
    today_str = dt_date.today().isoformat()

    for u in users:
        uid = u["user_id"]

        # DM chat_id = uid bo‘ladi (private)
        chat_id = uid

        # DM’da allaqachon countdown ketayotgan bo‘lsa
        if chat_id in LIVE_TASKS:
            continue

        try:
            t = await get_today(u["city"], cfg.country)
            imsak_dt, magh_dt = build_targets(t)
        except Exception:
            continue

        before = int(u["remind_before"])

        imsak_remind = imsak_dt - timedelta(minutes=before)
        if imsak_remind <= now < imsak_remind + timedelta(seconds=30):
            if (u.get("last_imsak_date") or "") != today_str:
                try:
                    await start_live(bot, chat_id, uid, "imsak")
                    await db.mark_sent(uid, "imsak", today_str)
                except Exception:
                    pass
            continue

        mag_remind = magh_dt - timedelta(minutes=before)
        if mag_remind <= now < mag_remind + timedelta(seconds=30):
            if (u.get("last_maghrib_date") or "") != today_str:
                try:
                    await start_live(bot, chat_id, uid, "maghrib")
                    await db.mark_sent(uid, "maghrib", today_str)
                except Exception:
                    pass

async def main():
    await db.init()
    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=cfg.tz)
    scheduler.add_job(reminder_tick, "interval", seconds=30, args=[bot])
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
