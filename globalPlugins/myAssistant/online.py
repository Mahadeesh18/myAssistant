# -*- coding: UTF-8 -*-
"""20 internet tools. Every result is shown in a dialog."""
import datetime
import random
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import quote
import addonHandler
from . import providers
from .common import (speak, http_text, http_json, run_async, ask_text, choose, show_text, _clip,
	geocode, get_location, WX, ask_form, ask_city)
from .data import COUNTRIES, COUNTRY_NAMES, COUNTRY_CODE, CURRENCIES

addonHandler.initTranslation()


def _12h(hhmm):
	try:
		h, m = [int(x) for x in re.match(r"(\d{1,2}):(\d{2})", hhmm).groups()]
		return "%d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")
	except Exception:
		return hhmm


def _city(title):
	return ask_city(title)


# 1 ---------------------------------------------------------------- 7-day forecast
def tool_forecast():
	city = _city(_("7-day forecast"))
	if city is None:
		return

	def work():
		lat, lon, place, _cc = geocode(city)
		w = http_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=7"
			"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max"
			% (lat, lon))
		d = w["daily"]
		out = [_("7-day forecast for %s") % place, ""]
		for i, day in enumerate(d["time"]):
			dt = datetime.date.fromisoformat(day)
			out.append("%s: %s, %s to %s°C, rain chance %s%%, wind up to %s km/h" % (
				dt.strftime("%A %d %B"), WX.get(d["weather_code"][i], "unknown").capitalize(),
				d["temperature_2m_min"][i], d["temperature_2m_max"][i],
				d["precipitation_probability_max"][i], d["wind_speed_10m_max"][i]))
		return "\n".join(out)
	run_async(work, _("7-day forecast"))


# 2 ---------------------------------------------------------------- air quality
def _aqi_label(v):
	for limit, name in ((50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
			(200, "Unhealthy"), (300, "Very unhealthy")):
		if v <= limit:
			return name
	return "Hazardous"


def tool_airquality():
	city = _city(_("Air quality"))
	if city is None:
		return

	def work():
		lat, lon, place, _cc = geocode(city)
		d = http_json("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=%s&longitude=%s"
			"&current=us_aqi,pm10,pm2_5,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide" % (lat, lon))["current"]
		aqi = d.get("us_aqi")
		return ("Air quality in %s\nUS AQI: %s (%s)\nPM2.5: %s µg/m³\nPM10: %s µg/m³\nOzone: %s µg/m³\n"
			"Nitrogen dioxide: %s µg/m³\nSulphur dioxide: %s µg/m³\nCarbon monoxide: %s µg/m³") % (
			place, aqi, _aqi_label(aqi) if aqi is not None else "unknown", d.get("pm2_5"), d.get("pm10"),
			d.get("ozone"), d.get("nitrogen_dioxide"), d.get("sulphur_dioxide"), d.get("carbon_monoxide"))
	run_async(work, _("Air quality"))


# 3 ---------------------------------------------------------------- prayer times
PRAYER_METHODS = [(1, "University of Islamic Sciences, Karachi"), (2, "Islamic Society of North America"),
	(3, "Muslim World League"), (4, "Umm al-Qura, Makkah"), (5, "Egyptian General Authority of Survey"),
	(13, "Diyanet, Turkey"), (11, "Majlis Ugama Islam Singapura")]


def tool_prayer():
	city = _city(_("Prayer times"))
	if city is None:
		return
	i = choose(_("Calculation method:"), _("Prayer times"), [n for _m, n in PRAYER_METHODS])
	if i < 0:
		return
	method = PRAYER_METHODS[i][0]

	def work():
		lat, lon, place, _cc = geocode(city)
		today = datetime.date.today()
		d = http_json("https://api.aladhan.com/v1/timings/%s?latitude=%s&longitude=%s&method=%d" % (
			today.strftime("%d-%m-%Y"), lat, lon, method))["data"]
		t, hj = d["timings"], d["date"]["hijri"]
		out = ["Prayer times for %s, %s" % (place, today.strftime("%A %d %B %Y")),
			"Hijri date: %s %s %s" % (hj["day"], hj["month"]["en"], hj["year"]), "Method: " + PRAYER_METHODS[i][1], ""]
		for name in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"):
			out.append("%s: %s" % (name, _12h(t[name])))
		return "\n".join(out)
	run_async(work, _("Prayer times"))


# 4 ---------------------------------------------------------------- joke
def tool_joke():
	def work():
		try:
			j = http_json("https://official-joke-api.appspot.com/random_joke")
			return "%s\n\n%s" % (j["setup"], j["punchline"])
		except Exception:
			return http_json("https://icanhazdadjoke.com/", headers={"Accept": "application/json"})["joke"]
	run_async(work, _("Random joke"))


# 5 ---------------------------------------------------------------- fact
def tool_fact():
	run_async(lambda: http_json("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en")["text"],
		_("Random fact"))


# 6 ---------------------------------------------------------------- quote
def tool_quote():
	def work():
		try:
			q = http_json("https://zenquotes.io/api/random")[0]
			return "%s\n\n- %s" % (q["q"], q["a"])
		except Exception:
			q = http_json("https://dummyjson.com/quotes/random")
			return "%s\n\n- %s" % (q["quote"], q["author"])
	run_async(work, _("Quote"))


# 7 ---------------------------------------------------------------- country info
def tool_country():
	r = ask_form(_("Country information"), [{"key": "c", "label": _("&Country (choose or type a name):"),
		"type": "editable", "choices": COUNTRY_NAMES, "default": "Pakistan", "required": True}])
	if not r:
		return
	q = r["c"]

	def work():
		try:
			r = http_json("https://restcountries.com/v3.1/name/%s?fields=name,capital,region,subregion,population,"
				"area,languages,currencies,timezones,cca2" % quote(q))
		except Exception:
			return _("Country not found.")
		c = r[0]
		cur = ", ".join("%s (%s)" % (v.get("name"), k) for k, v in (c.get("currencies") or {}).items())
		return ("%s (%s)\nCapital: %s\nRegion: %s, %s\nPopulation: {:,}\nArea: {:,.0f} km²\nLanguages: %s\n"
			"Currencies: %s\nTime zones: %s").format(c.get("population", 0), c.get("area", 0)) % (
			c["name"]["common"], c.get("cca2", ""), ", ".join(c.get("capital") or ["none"]), c.get("region"),
			c.get("subregion"), ", ".join((c.get("languages") or {}).values()), cur, ", ".join(c.get("timezones", [])))
	run_async(work, _("Country information"))


# 8 ---------------------------------------------------------------- public holidays
def tool_holidays():
	here = _("My location (automatic)")
	r = ask_form(_("Public holidays"), [{"key": "c", "label": _("&Country:"), "type": "combo",
		"choices": [here] + COUNTRY_NAMES, "default": here}])
	if not r:
		return
	code = "" if r["c"] == here else COUNTRY_CODE.get(r["c"], "")

	def work():
		cc = code.upper() or (get_location().get("cc") or "US")
		today = datetime.date.today()
		rows = []
		for y in (today.year, today.year + 1):
			try:
				rows += http_json("https://date.nager.at/api/v3/PublicHolidays/%d/%s" % (y, cc))
			except Exception:
				if y == today.year:
					return _("No holiday data for country code %s.") % cc
		up = [h for h in rows if h["date"] >= today.isoformat()][:12]
		out = ["Upcoming public holidays in %s" % cc, ""]
		for h in up:
			dt = datetime.date.fromisoformat(h["date"])
			name = h["name"] if h["name"] == h["localName"] else "%s (%s)" % (h["name"], h["localName"])
			out.append("%s: %s" % (dt.strftime("%A %d %B %Y"), name))
		return "\n".join(out)
	run_async(work, _("Public holidays"))


# 9 ---------------------------------------------------------------- IP / domain lookup
def tool_iplookup():
	q = ask_text(_("IP address or domain name (leave empty for your own):"), _("IP address lookup"))
	if q is None:
		return

	def work():
		d = http_json("http://ip-api.com/json/%s?fields=status,message,country,regionName,city,zip,lat,lon,"
			"timezone,isp,org,as,query" % quote(q))
		if d.get("status") != "success":
			return _("Lookup failed: %s") % d.get("message", "unknown error")
		return ("IP address: %s\nCity: %s\nRegion: %s\nCountry: %s\nPostal code: %s\nCoordinates: %s, %s\n"
			"Time zone: %s\nProvider: %s\nOrganization: %s\nNetwork: %s") % (
			d["query"], d["city"], d["regionName"], d["country"], d["zip"], d["lat"], d["lon"],
			d["timezone"], d["isp"], d["org"], d["as"])
	run_async(work, _("IP address lookup"))


# 10 --------------------------------------------------------------- synonyms, antonyms, rhymes
WORD_MODES = [("Synonyms", "rel_syn"), ("Antonyms", "rel_ant"), ("Rhymes", "rel_rhy"),
	("Words that sound like", "sl"), ("Words with a similar meaning", "ml")]


def tool_words():
	i = choose(_("Find:"), _("Word finder"), [_(n) for n, _p in WORD_MODES])
	if i < 0:
		return
	w = ask_text(_("English word:"), _("Word finder"))
	if not w:
		return

	def work():
		r = http_json("https://api.datamuse.com/words?%s=%s&max=40" % (WORD_MODES[i][1], quote(w)))
		if not r:
			return _("No words found.")
		return "%s for %s:\n\n%s" % (WORD_MODES[i][0], w, ", ".join(x["word"] for x in r))
	run_async(work, _("Word finder"))


# 11 --------------------------------------------------------------- crypto prices
CRYPTO_COINS = [("Popular coins (Bitcoin, Ethereum, Solana, BNB, XRP)", "bitcoin,ethereum,solana,binancecoin,ripple"),
	("Bitcoin", "bitcoin"), ("Ethereum", "ethereum"), ("Solana", "solana"), ("BNB", "binancecoin"), ("XRP", "ripple"),
	("Dogecoin", "dogecoin"), ("Cardano", "cardano"), ("Litecoin", "litecoin"), ("Tether", "tether"),
	("Toncoin", "the-open-network"), ("Tron", "tron"), ("Polkadot", "polkadot"), ("Chainlink", "chainlink")]
CRYPTO_FIAT = ["USD", "EUR", "GBP", "INR", "PKR", "AED", "SAR", "CAD", "AUD", "JPY", "CNY", "TRY", "BDT", "EGP"]


def tool_crypto():
	r = ask_form(_("Cryptocurrency prices"), [
		{"key": "coin", "label": _("&Coin:"), "type": "combo", "choices": [n for n, _i in CRYPTO_COINS]},
		{"key": "cur", "label": _("Show price &in:"), "type": "combo", "choices": CRYPTO_FIAT, "default": "USD"},
	])
	if not r:
		return
	ids = CRYPTO_COINS[r["coin_index"]][1]
	cur = r["cur"].lower()

	def work():
		d = http_json("https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=%s&include_24hr_change=true"
			% (quote(ids), quote(cur)))
		if not d:
			return _("No matching coins. Use full names such as bitcoin or ethereum.")
		out = []
		for k, v in d.items():
			ch = v.get(cur + "_24h_change")
			out.append("%s: %s %s%s" % (k.capitalize(), "{:,}".format(v.get(cur)), cur.upper(),
				(", 24 hour change %+.2f%%" % ch) if ch is not None else ""))
		return "\n".join(out)
	run_async(work, _("Cryptocurrency prices"))


# 12 --------------------------------------------------------------- news headlines (BBC RSS)
NEWS = [("Top stories", "news"), ("World", "news/world"), ("Technology", "news/technology"),
	("Business", "news/business"), ("Science and environment", "news/science_and_environment"),
	("Health", "news/health"), ("Entertainment and arts", "news/entertainment_and_arts"), ("Sport", "sport")]


def tool_news():
	i = choose(_("News category:"), _("News headlines"), [_(n) for n, _u in NEWS])
	if i < 0:
		return

	def work():
		root = ET.fromstring(http_text("https://feeds.bbci.co.uk/%s/rss.xml" % NEWS[i][1]).encode("utf-8"))
		out = ["BBC News: %s" % NEWS[i][0], ""]
		for n, it in enumerate(root.iter("item"), 1):
			if n > 12:
				break
			out.append("%d. %s. %s" % (n, (it.findtext("title") or "").strip(), (it.findtext("description") or "").strip()))
		return "\n".join(out)
	run_async(work, _("News headlines"))


# 13 --------------------------------------------------------------- Hacker News
def tool_hackernews():
	def work():
		ids = http_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:12]
		with ThreadPoolExecutor(6) as ex:
			items = list(ex.map(lambda i: http_json("https://hacker-news.firebaseio.com/v0/item/%d.json" % i), ids))
		out = ["Top Hacker News stories", ""]
		for n, it in enumerate(items, 1):
			out.append("%d. %s (%s points, %s comments)\n   %s" % (n, it.get("title"), it.get("score"),
				it.get("descendants", 0), it.get("url", "https://news.ycombinator.com/item?id=%s" % it.get("id"))))
		return "\n".join(out)
	run_async(work, _("Hacker News"))


# 14 --------------------------------------------------------------- on this day
def tool_onthisday():
	def work():
		t = datetime.date.today()
		ev = http_json("https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/%02d/%02d" % (t.month, t.day))["events"]
		pick = sorted(random.sample(ev, min(8, len(ev))), key=lambda e: e.get("year", 0))
		return "On this day, %s\n\n%s" % (t.strftime("%d %B"), "\n\n".join("%s: %s" % (e.get("year"), e.get("text")) for e in pick))
	run_async(work, _("On this day in history"))


# 15 --------------------------------------------------------------- book search
def tool_books():
	q = ask_text(_("Book title, author or subject:"), _("Book search"))
	if not q:
		return

	def work():
		d = http_json("https://openlibrary.org/search.json?limit=8&fields=title,author_name,first_publish_year,"
			"number_of_pages_median&q=" + quote(q))["docs"]
		if not d:
			return _("No books found.")
		out = []
		for n, b in enumerate(d, 1):
			line = "%d. %s by %s" % (n, b.get("title"), ", ".join(b.get("author_name", ["unknown author"])[:3]))
			if b.get("first_publish_year"):
				line += ", first published %s" % b["first_publish_year"]
			if b.get("number_of_pages_median"):
				line += ", about %s pages" % b["number_of_pages_median"]
			out.append(line)
		return "\n".join(out)
	run_async(work, _("Book search"))


# 16 --------------------------------------------------------------- earthquakes
QUAKES = [("Magnitude 4.5 and above, past day", "4.5_day"), ("Magnitude 4.5 and above, past week", "4.5_week"),
	("Significant earthquakes, past month", "significant_month")]


def tool_earthquakes():
	i = choose(_("Show:"), _("Recent earthquakes"), [_(n) for n, _u in QUAKES])
	if i < 0:
		return

	def work():
		f = http_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/%s.geojson" % QUAKES[i][1])["features"]
		if not f:
			return _("No earthquakes found.")
		f.sort(key=lambda x: x["properties"]["time"], reverse=True)
		out = [QUAKES[i][0], ""]
		for x in f[:15]:
			p = x["properties"]
			when = datetime.datetime.fromtimestamp(p["time"] / 1000).strftime("%d %b %I:%M %p")
			out.append("Magnitude %s, %s, %s" % (p.get("mag"), p.get("place"), when))
		return "\n".join(out)
	run_async(work, _("Recent earthquakes"))


# 17 --------------------------------------------------------------- sunrise and sunset
def tool_suntimes():
	city = _city(_("Sunrise and sunset"))
	if city is None:
		return

	def work():
		lat, lon, place, _cc = geocode(city)
		d = http_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=1"
			"&daily=sunrise,sunset,daylight_duration" % (lat, lon))["daily"]
		sec = int(d["daylight_duration"][0])
		return "Sun times for %s\nSunrise: %s\nSunset: %s\nDaylight: %d hours %d minutes" % (
			place, _12h(d["sunrise"][0][11:]), _12h(d["sunset"][0][11:]), sec // 3600, sec % 3600 // 60)
	run_async(work, _("Sunrise and sunset"))


# 18 --------------------------------------------------------------- web page reader
class _Text(HTMLParser):
	SKIP = {"script", "style", "noscript", "svg", "head", "template", "iframe"}
	BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "ul", "ol", "table"}

	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.parts, self.skip, self.title, self._in_title = [], 0, "", False

	def handle_starttag(self, tag, attrs):
		if tag == "title":
			self._in_title = True
		if tag in self.SKIP:
			self.skip += 1
		elif tag in self.BLOCK:
			self.parts.append("\n")

	def handle_endtag(self, tag):
		if tag == "title":
			self._in_title = False
		if tag in self.SKIP and self.skip:
			self.skip -= 1
		elif tag in self.BLOCK:
			self.parts.append("\n")

	def handle_data(self, data):
		if self._in_title:
			self.title += data
		elif not self.skip:
			self.parts.append(data)


def page_text(html):
	p = _Text()
	p.feed(html)
	body = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
	body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
	return p.title.strip(), body


def tool_webpage():
	url = ask_text(_("Web page address:"), _("Web page reader"))
	if not url:
		return
	if not re.match(r"^https?://", url, re.I):
		url = "https://" + url

	def work():
		title, body = page_text(http_text(url, timeout=25))
		if not body:
			return _("The page has no readable text.")
		return "%s\n%s\n\n%s" % (title or url, url, body[:40000])
	run_async(work, _("Web page reader"))


# 19 --------------------------------------------------------------- AI: rewrite clipboard
REWRITES = [("Proofread and fix mistakes", "Proofread the following text. Fix spelling, grammar and punctuation without changing the meaning. Reply with the corrected text only:"),
	("Make it more formal", "Rewrite the following text in a more formal, professional tone. Reply with the rewritten text only:"),
	("Make it simpler", "Rewrite the following text in simple, plain language. Reply with the rewritten text only:"),
	("Make it shorter", "Rewrite the following text to be much shorter while keeping the key points. Reply with the rewritten text only:"),
	("Explain it", "Explain the following text clearly and simply:")]


def tool_ai_rewrite():
	t = _clip()
	if not t:
		return
	i = choose(_("What should the AI do with the clipboard text?"), _("AI: improve clipboard text"),
		[_(n) for n, _p in REWRITES])
	if i < 0:
		return
	run_async(lambda: providers.ask([{"role": "user", "content": REWRITES[i][1] + "\n\n" + t}]),
		_("AI: improve clipboard text"))


# 20 --------------------------------------------------------------- AI: quick question
def tool_ai_ask():
	q = ask_text(_("Your question:"), _("AI: quick question"), multiline=True)
	if q:
		run_async(lambda: providers.ask([{"role": "user", "content": q}]), _("AI: quick question"))


ONLINE_TOOLS = [
	(_("Weather: 7-day forecast"), tool_forecast),
	(_("Air quality"), tool_airquality),
	(_("Prayer times"), tool_prayer),
	(_("Sunrise and sunset times"), tool_suntimes),
	(_("News headlines"), tool_news),
	(_("Hacker News top stories"), tool_hackernews),
	(_("Recent earthquakes"), tool_earthquakes),
	(_("Cryptocurrency prices"), tool_crypto),
	(_("Country information"), tool_country),
	(_("Public holidays"), tool_holidays),
	(_("On this day in history"), tool_onthisday),
	(_("Book search"), tool_books),
	(_("Word finder: synonyms, antonyms, rhymes"), tool_words),
	(_("IP address or domain lookup"), tool_iplookup),
	(_("Web page reader"), tool_webpage),
	(_("Random joke"), tool_joke),
	(_("Random fact"), tool_fact),
	(_("Inspirational quote"), tool_quote),
	(_("AI: improve or explain clipboard text"), tool_ai_rewrite),
	(_("AI: ask a quick question"), tool_ai_ask),
]


from .newtools import NEW_ONLINE_TOOLS  # noqa: E402

ONLINE_TOOLS[18:18] = NEW_ONLINE_TOOLS
