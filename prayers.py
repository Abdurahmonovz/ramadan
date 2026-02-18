import aiohttp
from datetime import date

BASE = "https://api.aladhan.com/v1"

async def get_today(city: str, country: str, method: int = 2, school: int = 1):
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
