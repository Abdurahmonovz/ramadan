import aiohttp
from datetime import date

BASE = "https://api.aladhan.com/v1"


async def get_today(city: str, country: str, method: int = 2, school: int = 1):
    """
    Returns today's timings (Imsak, Maghrib) by city/country.
    """
    d = date.today().strftime("%d-%m-%Y")
    url = f"{BASE}/timingsByCity/{d}"
    params = {"city": city, "country": country, "method": method, "school": school}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=20) as r:
            data = await r.json()

    if data.get("code") != 200:
        raise RuntimeError(str(data))

    t = data["data"]["timings"]
    return {
        "imsak": t.get("Imsak"),
        "maghrib": t.get("Maghrib"),
    }


async def get_calendar_by_city(
    month: int,
    year: int,
    city: str,
    country: str,
    method: int = 2,
    school: int = 1,
):
    """
    Gregorian month calendar for a city.
    Returns list of day objects (contains timings + hijri date).
    """
    url = f"{BASE}/calendarByCity/{year}/{month}"
    params = {"city": city, "country": country, "method": method, "school": school}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=30) as r:
            data = await r.json()

    if data.get("code") != 200:
        raise RuntimeError(str(data))

    return data["data"]
