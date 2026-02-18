import asyncio
from datetime import datetime, timedelta, date as dt_date
import pytz

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from db import DB
from prayers import get_today, get_calendar_by_city
from keyboards import (
    main_menu,
    stop_menu,
    reminder_inline,
    city_inline,
    calendar_city_inline,
)
from texts import WELCOME, DUA_OCHISH, DUA_YOPISH, GROUP_HELP
from calendar_image import render_ramadan_calendar_png

cfg = load_config()
db = DB()
router = Router()

# chat_id -> asyncio.Task (DM ham chat)
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


def choose_mode(imsak_dt: datetime, magh_dt: datetime, now: datetime) -> str:
    if now < imsak_dt:
        return "imsak"
    if now < magh_dt:
        return "maghrib"
    return "imsak"


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
    1 ta xabarni sekundiga edit qilib countdown qiladi.
    chat_id: DM yoki group
    user_id: shahar/sozlama kimniki bo‘lsa shu
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
    if chat_id in LIVE_TASKS:
        return
    msg = await bot.send_message(chat_id, "⏳ Eslatma boshlandi…", reply_markup=stop_menu())
    task = asyncio.create_task(live_message_loop(bot, chat_id, user_id, mode, msg.message_id))
    LIVE_TASKS[chat_id] = task


# ===== Commands =====

@router.message(CommandStart())
async def start(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer(WELCOME, reply_markup=main_menu())
    if m.chat.type != "private":
        await m.answer(GROUP_HELP)


@router.message(Command("ramadan"))
async def ramadan_cmd(m: Message):
    """
    group/kanalda /ramadan yozilsa — shu chatda vaqtlar + countdown.
    """
    await db.ensure(m.from_user.id)
    user = await db.get(m.from_user.id)

    t = await get_today(user["city"], cfg.country)
    imsak_dt, magh_dt = build_targets(t)
    mode = choose_mode(imsak_dt, magh_dt, now_tz())

    await stop_live(m.chat.id)

    await m.answer(
        f"📍 {user['city']}\n"
        f"🌙 Og‘iz yopish (Imsak): {t['imsak']}\n"
        f"🍽 Og‘iz ochish (Maghrib): {t['maghrib']}\n\n"
        f"⏳ Countdown boshlanmoqda…",
        reply_markup=stop_menu()
    )
    await start_live(m.bot, m.chat.id, m.from_user.id, mode)


# ===== Menu =====

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
        f"🍽 Og‘iz ochish (Maghrib): {t['maghrib']}\n",
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


# ===== Ramadan calendar as PNG =====

@router.message(F.text == "📆 Ramazon taqvimi")
async def ramadan_calendar_menu(m: Message):
    await db.ensure(m.from_user.id)
    await m.answer("Qaysi viloyat/shahar uchun Ramazon taqvimi kerak?", reply_markup=calendar_city_inline())


@router.callback_query(F.data.startswith("cal:"))
async def cal_cb(c: CallbackQuery):
    city = c.data.split(":", 1)[1]
    await c.answer()

    now = now_tz()
    years_to_try = [now.year, now.year + 1]
    rows = []  # (greg_date, imsak, maghrib)

    for year in years_to_try:
        for month in range(1, 13):
            try:
                days = await get_calendar_by_city(month, year, city, cfg.country)
            except Exception:
                continue

            for d in days:
                hijri = d["date"]["hijri"]
                if hijri["month"]["number"] == 9:  # Ramadan
                    g_date = d["date"]["gregorian"]["date"]  # dd-mm-yyyy
                    t = d["timings"]
                    imsak = (t.get("Imsak") or "")[:5]
                    magh = (t.get("Maghrib") or "")[:5]
                    rows.append((g_date, imsak, magh))

        if rows:
            break

    if not rows:
        await c.message.answer("Ramazon taqvimi topilmadi. Keyinroq urinib ko‘ring.", reply_markup=main_menu())
        return

    title = f"{city} — Ramazon taqvimi"
    png_io = render_ramadan_calendar_png(title=title, rows=rows)

    file = BufferedInputFile(png_io.getvalue(), filename="ramazon_taqvim.png")
    await c.message.answer_photo(
        photo=file,
        caption=f"📍 {city}\n✅ Ramazon taqvimi",
        reply_markup=main_menu()
    )


# ===== Auto reminders (DM only) =====

async def reminder_tick(bot: Bot):
    """
    Avtomatik reminder faqat private (DM) chatda ishlaydi.
    Group/kanalda /ramadan ishlating.
    """
    users = await db.list_enabled()
    now = now_tz()
    today_str = dt_date.today().isoformat()

    for u in users:
        uid = u["user_id"]
        chat_id = uid  # DM chat_id = user_id

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
