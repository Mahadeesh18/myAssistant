# -*- coding: UTF-8 -*-
"""15 more advanced internet tools (no account or API key needed) and the sound effects tool."""
import datetime
import os
import random
import re
import socket
import ssl
import time
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlparse
import wx
import api
import addonHandler
from .common import (speak, http_text, http_json, run_async, ask_text, choose, show_text, _clip,
	ask_form, UA)
from .data import LANGUAGES, COUNTRY_NAMES, COUNTRY_CODE
from . import sounds
from .inspector import tool_inspector

addonHandler.initTranslation()


def _strip_html(s):
	return unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").strip()


def _copy_later(text):
	wx.CallAfter(api.copyToClip, text)


# 1 ---------------------------------------------------------------- ISS and people in space
def tool_iss():
	def work():
		d = http_json("https://api.wheretheiss.at/v1/satellites/25544")
		out = [_("International Space Station right now"), "",
			"Latitude: %.3f" % d["latitude"], "Longitude: %.3f" % d["longitude"],
			"Altitude: %.0f km" % d["altitude"], "Speed: {:,.0f} km/h".format(d["velocity"]),
			"Sunlight: %s" % d.get("visibility", "unknown")]
		try:
			p = http_json("http://api.open-notify.org/astros.json", timeout=10)
			out += ["", "People in space now: %d" % p["number"]]
			out += ["%s (%s)" % (x["name"], x["craft"]) for x in p["people"]]
		except Exception:
			pass
		return "\n".join(out)
	run_async(work, _("International Space Station"))


# 2 ---------------------------------------------------------------- trivia quiz
TRIVIA_CATS = [("Any category", ""), ("General knowledge", "9"), ("Science and nature", "17"),
	("Computers", "18"), ("Mathematics", "19"), ("History", "23"), ("Geography", "22"), ("Sports", "21"),
	("Animals", "27"), ("Film", "11"), ("Music", "12"), ("Video games", "15"), ("Politics", "24")]


def tool_trivia():
	r = ask_form(_("Trivia quiz"), [
		{"key": "cat", "label": _("&Category:"), "type": "combo", "choices": [_(n) for n, _i in TRIVIA_CATS]},
		{"key": "diff", "label": _("&Difficulty:"), "type": "combo",
			"choices": [_("Any"), _("Easy"), _("Medium"), _("Hard")]},
		{"key": "n", "label": _("&Number of questions:"), "type": "combo", "choices": [1, 3, 5, 10], "default": 5},
	])
	if not r:
		return
	cat = TRIVIA_CATS[r["cat_index"]][1]
	diff = ["", "easy", "medium", "hard"][r["diff_index"]]
	n = int(r["n"])

	def work():
		url = "https://opentdb.com/api.php?type=multiple&encode=url3986&amount=%d" % n
		if cat:
			url += "&category=" + cat
		if diff:
			url += "&difficulty=" + diff
		res = http_json(url).get("results") or []
		if not res:
			return _("No questions found. Try another category or difficulty.")
		qs, ans = [], []
		for i, q in enumerate(res, 1):
			opts = [unquote(x) for x in q["incorrect_answers"]] + [unquote(q["correct_answer"])]
			random.shuffle(opts)
			letters = "ABCD"
			qs.append("%d. %s\n%s" % (i, unquote(q["question"]),
				"\n".join("   %s) %s" % (letters[k], o) for k, o in enumerate(opts))))
			ans.append("%d. %s) %s" % (i, letters[opts.index(unquote(q["correct_answer"]))], unquote(q["correct_answer"])))
		return "\n\n".join(qs) + "\n\n" + "-" * 30 + "\n" + _("Answers (scroll down after you have tried)") + "\n" + "\n".join(ans)
	run_async(work, _("Trivia quiz"))


# 3 ---------------------------------------------------------------- number and date facts
def tool_number():
	r = ask_form(_("Number and date facts"), [
		{"key": "kind", "label": _("&Kind of fact:"), "type": "combo",
			"choices": [_("Trivia about a number"), _("Math fact about a number"), _("Year fact"), _("Today in the calendar")]},
		{"key": "num", "label": _("&Number (leave empty for a random one):"), "type": "text"},
	])
	if not r:
		return
	kind, num = r["kind_index"], r["num"].strip()
	if num and not re.match(r"^-?\d+$", num):
		speak(_("Please type a whole number"))
		return

	def work():
		if kind == 3:
			t = datetime.date.today()
			url = "http://numbersapi.com/%d/%d/date?json" % (t.month, t.day)
		else:
			url = "http://numbersapi.com/%s/%s?json" % (num or "random", ["trivia", "math", "year"][kind])
		return http_json(url)["text"]
	run_async(work, _("Number and date facts"))


# 4 ---------------------------------------------------------------- advice
def tool_advice():
	run_async(lambda: http_json("https://api.adviceslip.com/advice?t=%d" % time.time())["slip"]["advice"],
		_("Random advice"))


# 5 ---------------------------------------------------------------- random Wikipedia article
def tool_wikirandom():
	def work():
		d = http_json("https://en.wikipedia.org/api/rest_v1/page/random/summary")
		link = (d.get("content_urls") or {}).get("desktop", {}).get("page", "")
		return "%s\n%s\n\n%s\n\n%s" % (d.get("title"), d.get("description", ""), d.get("extract", ""), link)
	run_async(work, _("Random Wikipedia article"))


# 6 ---------------------------------------------------------------- TV show search
def tool_tvshows():
	q = ask_text(_("TV show name:"), _("TV show search"))
	if not q:
		return

	def work():
		res = http_json("https://api.tvmaze.com/search/shows?q=" + quote(q))[:6]
		if not res:
			return _("No shows found.")
		out = []
		for i, x in enumerate(res, 1):
			s = x["show"]
			net = (s.get("network") or s.get("webChannel") or {}).get("name", "unknown")
			year = (s.get("premiered") or "")[:4] or "unknown"
			rating = (s.get("rating") or {}).get("average")
			out.append("%d. %s (%s)\nStatus: %s. Network: %s. Genres: %s. Rating: %s\n%s" % (
				i, s["name"], year, s.get("status"), net, ", ".join(s.get("genres") or []) or "none",
				rating if rating else "none", _strip_html(s.get("summary"))[:500]))
		return "\n\n".join(out)
	run_async(work, _("TV show search"))


# 7 ---------------------------------------------------------------- recipes
def tool_recipes():
	r = ask_form(_("Recipe finder"), [
		{"key": "mode", "label": _("&What do you want?"), "type": "combo",
			"choices": [_("Search recipes by name"), _("Surprise me with a random recipe")]},
		{"key": "q", "label": _("&Dish name (for searching):"), "type": "text"},
	])
	if not r:
		return
	rand, q = r["mode_index"] == 1, r["q"].strip()
	if not rand and not q:
		speak(_("Please type a dish name"))
		return

	def work():
		url = "https://www.themealdb.com/api/json/v1/1/" + ("random.php" if rand else "search.php?s=" + quote(q))
		meals = http_json(url).get("meals") or []
		if not meals:
			return _("No recipes found.")
		out = []
		for m in meals[:3]:
			ing = []
			for k in range(1, 21):
				name = (m.get("strIngredient%d" % k) or "").strip()
				if name:
					ing.append("%s %s" % ((m.get("strMeasure%d" % k) or "").strip(), name))
			out.append("%s\nCategory: %s. Cuisine: %s.\n\nIngredients:\n%s\n\nInstructions:\n%s" % (
				m["strMeal"], m.get("strCategory"), m.get("strArea"), "\n".join(ing),
				(m.get("strInstructions") or "").replace("\r", "")))
		return ("\n\n" + "=" * 30 + "\n\n").join(out)
	run_async(work, _("Recipe finder"))


# 8 ---------------------------------------------------------------- rocket launches
def tool_launches():
	def work():
		d = http_json("https://ll.thedevs.com/2.2.0/launch/upcoming/?limit=8&mode=list")["results"]
		if not d:
			return _("No upcoming launches found.")
		out = [_("Upcoming rocket launches (times in UTC)"), ""]
		for i, x in enumerate(d, 1):
			net = (x.get("net") or "")[:16].replace("T", " ")
			status = (x.get("status") or {}).get("name", "unknown")
			out.append("%d. %s\n   %s UTC. Status: %s. Provider: %s." % (
				i, x.get("name"), net, status, x.get("lsp_name") or "unknown"))
		return "\n".join(out)
	run_async(work, _("Upcoming rocket launches"))


# 9 ---------------------------------------------------------------- GitHub lookup
def tool_github():
	r = ask_form(_("GitHub lookup"), [
		{"key": "mode", "label": _("&Look up:"), "type": "combo",
			"choices": [_("A user"), _("A repository (owner/name)"), _("Search repositories")]},
		{"key": "q", "label": _("&Name or search words:"), "type": "text", "required": True},
	])
	if not r:
		return
	mode, q = r["mode_index"], r["q"].strip()

	def work():
		base = "https://api.github.com"
		hdr = {"Accept": "application/vnd.github+json"}
		if mode == 0:
			u = http_json("%s/users/%s" % (base, quote(q)), headers=hdr)
			return ("%s (%s)\n%s\nLocation: %s\nCompany: %s\nPublic repositories: %s\nFollowers: %s\nFollowing: %s\n"
				"Joined: %s\nWebsite: %s\n%s") % (u.get("name") or u["login"], u["login"], u.get("bio") or "",
				u.get("location"), u.get("company"), u["public_repos"], u["followers"], u["following"],
				u["created_at"][:10], u.get("blog"), u["html_url"])
		if mode == 1:
			g = http_json("%s/repos/%s" % (base, quote(q, safe="/")), headers=hdr)
			return ("%s\n%s\nLanguage: %s\nStars: {:,}\nForks: {:,}\nOpen issues: %s\nLicense: %s\nCreated: %s\n"
				"Last push: %s\n%s").format(g["stargazers_count"], g["forks_count"]) % (
				g["full_name"], g.get("description") or "", g.get("language"), g["open_issues_count"],
				(g.get("license") or {}).get("name", "none"), g["created_at"][:10], g["pushed_at"][:10], g["html_url"])
		items = http_json("%s/search/repositories?per_page=8&sort=stars&q=%s" % (base, quote(q)), headers=hdr)["items"]
		if not items:
			return _("No repositories found.")
		return "\n\n".join("%d. %s, %s stars, %s\n%s\n%s" % (i, g["full_name"], "{:,}".format(g["stargazers_count"]),
			g.get("language") or "unknown language", g.get("description") or "", g["html_url"])
			for i, g in enumerate(items, 1))
	run_async(work, _("GitHub lookup"))


# 10 --------------------------------------------------------------- software packages
def tool_package():
	r = ask_form(_("Software package info"), [
		{"key": "src", "label": _("&Package manager:"), "type": "combo", "choices": ["PyPI (Python)", "npm (JavaScript)"]},
		{"key": "name", "label": _("&Package name:"), "type": "text", "required": True},
	])
	if not r:
		return
	src, name = r["src_index"], r["name"].strip()

	def work():
		if src == 0:
			i = http_json("https://pypi.org/pypi/%s/json" % quote(name))["info"]
			return ("%s %s\n%s\nAuthor: %s\nLicense: %s\nRequires Python: %s\nInstall: pip install %s\n%s") % (
				i["name"], i["version"], i.get("summary") or "", i.get("author") or "unknown",
				(i.get("license") or "unknown")[:80], i.get("requires_python") or "any", i["name"],
				i.get("package_url") or "")
		d = http_json("https://registry.npmjs.org/%s/latest" % quote(name, safe="@/"))
		auth = d.get("author")
		auth = auth.get("name") if isinstance(auth, dict) else auth
		return ("%s %s\n%s\nAuthor: %s\nLicense: %s\nInstall: npm install %s\nHomepage: %s") % (
			d["name"], d["version"], d.get("description") or "", auth or "unknown", d.get("license") or "unknown",
			d["name"], d.get("homepage") or "none")
	run_async(work, _("Software package info"))


# 11 --------------------------------------------------------------- website status check
def tool_sitecheck():
	url = ask_text(_("Website address:"), _("Website status check"))
	if not url:
		return
	if not re.match(r"^https?://", url, re.I):
		url = "https://" + url

	def work():
		req = urllib.request.Request(url, headers=UA)
		t0 = time.time()
		try:
			resp = urllib.request.urlopen(req, timeout=20)
			code, hdr, final = resp.status, resp.headers, resp.geturl()
		except HTTPError as e:
			resp, code, hdr, final = e, e.code, e.headers, e.geturl()
		first = (time.time() - t0) * 1000
		size = len(resp.read(2000000))
		total = (time.time() - t0) * 1000
		out = [url, "Status: %s" % code, "Time to first response: %.0f ms" % first, "Total time: %.0f ms" % total,
			"Downloaded: {:,} bytes".format(size), "Final address: %s" % final,
			"Server: %s" % (hdr.get("Server") or "unknown"), "Content type: %s" % (hdr.get("Content-Type") or "unknown")]
		out.append("Verdict: " + (_("The site is up.") if code < 400 else _("The site answered with an error.")))
		p = urlparse(final)
		if p.scheme == "https":
			try:
				with socket.create_connection((p.hostname, p.port or 443), timeout=10) as s:
					with ssl.create_default_context().wrap_socket(s, server_hostname=p.hostname) as ss:
						end = ssl.cert_time_to_seconds(ss.getpeercert()["notAfter"])
				out.append("Security certificate valid for another %d days" % int((end - time.time()) // 86400))
			except Exception as e:
				out.append("Security certificate problem: %s" % e)
		return "\n".join(out)
	run_async(work, _("Website status check"))


# 12 --------------------------------------------------------------- DNS lookup
DNS_TYPES = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]


def tool_dns():
	r = ask_form(_("DNS lookup"), [
		{"key": "d", "label": _("&Domain name:"), "type": "text", "required": True},
		{"key": "t", "label": _("Record &type:"), "type": "combo", "choices": DNS_TYPES},
	])
	if not r:
		return
	dom, typ = r["d"].strip(), r["t"]
	dom = re.sub(r"^https?://", "", dom, flags=re.I).split("/")[0]

	def work():
		d = http_json("https://dns.google/resolve?name=%s&type=%s" % (quote(dom), typ))
		ans = d.get("Answer") or []
		if not ans:
			return _("No %s records found for %s.") % (typ, dom)
		return "%s records for %s\n\n%s" % (typ, dom, "\n".join("%s (time to live %s seconds)" % (a["data"], a["TTL"]) for a in ans))
	run_async(work, _("DNS lookup"))


# 13 --------------------------------------------------------------- internet speed test
def tool_speedtest():
	sounds.play("sweep")

	def work():
		t = time.time()
		http_text("https://speed.cloudflare.com/__down?bytes=0", timeout=10)
		latency = (time.time() - t) * 1000
		req = urllib.request.Request("https://speed.cloudflare.com/__down?bytes=20000000", headers=UA)
		n, t = 0, time.time()
		with urllib.request.urlopen(req, timeout=30) as r:
			while time.time() - t < 12:
				b = r.read(65536)
				if not b:
					break
				n += len(b)
		down = n * 8 / max(time.time() - t, 0.001) / 1e6
		up = None
		try:
			data = bytes(4000000)
			req = urllib.request.Request("https://speed.cloudflare.com/__up", data=data,
				headers=dict(UA, **{"Content-Type": "text/plain"}), method="POST")
			t = time.time()
			urllib.request.urlopen(req, timeout=30).read()
			up = len(data) * 8 / max(time.time() - t, 0.001) / 1e6
		except Exception:
			pass
		return "Internet speed test\nDelay (ping): %.0f ms\nDownload speed: %.1f Mbps\nUpload speed: %s" % (
			latency, down, ("%.1f Mbps" % up) if up else "could not be measured")
	run_async(work, _("Internet speed test"))


# 14 --------------------------------------------------------------- URL shortener
def tool_shorten():
	clip = ""
	try:
		clip = api.getClipData() or ""
	except Exception:
		pass
	q = ask_text(_("Long web address to shorten:"), _("URL shortener"), clip if clip.lower().startswith("http") else "")
	if not q:
		return
	if not re.match(r"^https?://", q, re.I):
		q = "https://" + q

	def work():
		d = http_json("https://is.gd/create.php?format=json&url=" + quote(q, safe=""))
		if "shorturl" not in d:
			return _("Could not shorten: %s") % d.get("errormessage", "unknown error")
		_copy_later(d["shorturl"])
		return "%s\n\n%s" % (d["shorturl"], _("The short address was copied to the clipboard."))
	run_async(work, _("URL shortener"))


# 15 --------------------------------------------------------------- RSS and Atom feed reader
FEEDS = [("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
	("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
	("NPR News", "https://feeds.npr.org/1001/rss.xml"),
	("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
	("The Verge", "https://www.theverge.com/rss/index.xml"),
	("NASA breaking news", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
	("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml")]


def tool_rss():
	r = ask_form(_("Feed reader"), [{"key": "f", "label": _("&Feed (choose one, or type a feed address):"),
		"type": "editable", "choices": [n for n, _u in FEEDS], "default": FEEDS[0][0], "required": True}])
	if not r:
		return
	pick = r["f"]
	url = dict(FEEDS).get(pick) or (pick if re.match(r"^https?://", pick, re.I) else "https://" + pick)

	def work():
		root = ET.fromstring(http_text(url, timeout=25).encode("utf-8"))
		atom = "{http://www.w3.org/2005/Atom}"
		title = root.findtext("channel/title") or root.findtext(atom + "title") or url
		rows = []
		for it in root.iter("item"):
			rows.append(((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(),
				_strip_html(it.findtext("description"))[:300]))
		if not rows:
			for it in root.iter(atom + "entry"):
				ln = it.find(atom + "link")
				rows.append(((it.findtext(atom + "title") or "").strip(), ln.get("href") if ln is not None else "",
					_strip_html(it.findtext(atom + "summary"))[:300]))
		if not rows:
			return _("No articles found in this feed.")
		out = [title, ""]
		for i, (t, l, s) in enumerate(rows[:15], 1):
			out.append("%d. %s\n%s\n%s\n" % (i, t, s, l))
		return "\n".join(out)
	run_async(work, _("Feed reader"))


# 16 --------------------------------------------------------------- password breach checker
def tool_pwned():
	import hashlib
	import gui
	from .common import _modal
	dlg = wx.PasswordEntryDialog(gui.mainFrame, _("Password to check (it is never sent anywhere; only part of its fingerprint is):"),
		_("Password breach checker"))
	pw = _modal(dlg, lambda d, c: d.GetValue() if c == wx.ID_OK else None)
	if not pw:
		return

	def work():
		h = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()
		prefix, suffix = h[:5], h[5:]
		text = http_text("https://api.pwnedpasswords.com/range/" + prefix, timeout=20, headers={"Add-Padding": "true"})
		count = 0
		for line in text.splitlines():
			a, _sep, b = line.partition(":")
			if a.strip() == suffix:
				count = int(b.strip() or 0)
				break
		note = _("Only the first 5 characters of the password's SHA-1 fingerprint were sent. The password itself never left your computer.")
		if count > 0:
			return (_("This password appeared in %s known data breaches. Do not use it anywhere. Choose a new, unique password.") %
				"{:,}".format(count)) + "\n\n" + note
		return _("This password was not found in the known breach list. That is good, but it does not prove it is strong.") + "\n\n" + note
	run_async(work, _("Password breach checker"))


# 17 --------------------------------------------------------------- whois (RDAP)
def tool_whois():
	q = ask_text(_("Domain name, for example example.com:"), _("Domain registration lookup"))
	if not q:
		return
	dom = re.sub(r"^https?://", "", q.strip(), flags=re.I).split("/")[0].lower()
	if dom.startswith("www."):
		dom = dom[4:]

	def work():
		try:
			d = http_json("https://rdap.org/domain/" + quote(dom), timeout=25)
		except HTTPError as e:
			if e.code == 404:
				return _("%s was not found. It may be available to register, or its registry does not publish this data.") % dom
			raise
		ev = {e.get("eventAction"): (e.get("eventDate") or "")[:10] for e in d.get("events", [])}
		registrar = ""
		for ent in d.get("entities", []):
			if "registrar" in ent.get("roles", []):
				for item in (ent.get("vcardArray") or [None, []])[1]:
					if item[0] == "fn":
						registrar = item[3]
		out = ["Domain: %s" % (d.get("ldhName") or dom).lower(), "Registrar: %s" % (registrar or "not published"),
			"Registered: %s" % (ev.get("registration") or "unknown"), "Last changed: %s" % (ev.get("last changed") or "unknown"),
			"Expires: %s" % (ev.get("expiration") or "unknown")]
		try:
			days = (datetime.date.fromisoformat(ev["expiration"]) - datetime.date.today()).days
			out.append("Days until it expires: %d" % days)
		except Exception:
			pass
		out.append("Status: %s" % (", ".join(d.get("status", [])) or "unknown"))
		ns = [n.get("ldhName", "").lower() for n in d.get("nameservers", [])]
		out.append("Name servers: %s" % (", ".join(ns) or "none listed"))
		return "\n".join(out)
	run_async(work, _("Domain registration lookup"))


# 18 --------------------------------------------------------------- podcast finder
def tool_podcasts():
	q = ask_text(_("Podcast name or topic:"), _("Podcast finder"))
	if not q:
		return

	def work():
		res = http_json("https://itunes.apple.com/search?media=podcast&limit=8&term=" + quote(q)).get("results", [])
		if not res:
			return _("No podcasts found.")
		out = []
		for i, p in enumerate(res, 1):
			out.append("%d. %s by %s\nGenre: %s. Episodes: %s. Latest episode: %s.\nFeed address (usable in the feed reader): %s" % (
				i, p.get("collectionName"), p.get("artistName"), p.get("primaryGenreName"), p.get("trackCount", "unknown"),
				(p.get("releaseDate") or "unknown")[:10], p.get("feedUrl") or "not published"))
		return "\n\n".join(out)
	run_async(work, _("Podcast finder"))


# 19 --------------------------------------------------------------- web page archiver (Wayback Machine)
def tool_archive():
	r = ask_form(_("Web page archiver"), [
		{"key": "mode", "label": _("&What do you want to do?"), "type": "combo",
			"choices": [_("Find the newest saved copy of a page"), _("Save a new copy of a page now")]},
		{"key": "url", "label": _("&Web page address:"), "type": "text", "required": True},
	])
	if not r:
		return
	mode, url = r["mode_index"], r["url"].strip()
	if not re.match(r"^https?://", url, re.I):
		url = "https://" + url

	def work():
		if mode == 0:
			snap = http_json("https://archive.org/wayback/available?url=" + quote(url, safe="")).get("archived_snapshots", {}).get("closest")
			if not snap:
				return _("No saved copy of this page was found. Use Save a new copy of a page now.")
			ts = snap["timestamp"]
			return "Newest saved copy of %s\nSaved on: %s-%s-%s at %s:%s UTC\nAddress: %s" % (
				url, ts[0:4], ts[4:6], ts[6:8], ts[8:10], ts[10:12], snap["url"])
		req = urllib.request.Request("https://web.archive.org/save/" + url, headers=UA)
		with urllib.request.urlopen(req, timeout=90) as resp:
			loc = resp.headers.get("Content-Location")
			final = ("https://web.archive.org" + loc) if loc else resp.geturl()
		return "The page was saved to the Internet Archive.\nAddress of the saved copy: %s" % final
	run_async(work, _("Web page archiver"))


# 20 --------------------------------------------------------------- page analyzer (SEO and accessibility)
class _Scan(HTMLParser):
	SKIP = {"script", "style", "noscript", "svg", "template"}

	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.title, self._in_title, self.lang, self.meta, self.canonical = "", False, "", {}, ""
		self.headings, self.links, self.imgs, self.noalt = [], [], 0, 0
		self.words, self.skip, self._h, self._a, self._btn = 0, 0, None, None, None
		self.buttons_bad, self.inputs, self.label_for, self._labels, self.forms = 0, [], set(), 0, 0

	def handle_starttag(self, tag, attrs):
		a = {k: (v or "") for k, v in attrs}
		if tag in self.SKIP:
			self.skip += 1
		if tag == "html":
			self.lang = a.get("lang", "")
		elif tag == "title":
			self._in_title = True
		elif tag == "meta":
			self.meta[(a.get("name") or a.get("property") or "").lower()] = a.get("content", "")
		elif tag == "link" and "canonical" in a.get("rel", "").lower():
			self.canonical = a.get("href", "")
		elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
			self._h = [int(tag[1]), ""]
		elif tag == "a" and a.get("href"):
			self._a = [a["href"], a.get("aria-label", "") or a.get("title", "")]
		elif tag == "img":
			self.imgs += 1
			if "alt" not in a and not a.get("aria-label"):
				self.noalt += 1
		elif tag == "button":
			self._btn = a.get("aria-label", "") or a.get("title", "")
		elif tag == "label":
			self._labels += 1
			if a.get("for"):
				self.label_for.add(a["for"])
		elif tag == "form":
			self.forms += 1
		elif tag in ("input", "select", "textarea"):
			if a.get("type", "text").lower() not in ("hidden", "submit", "button", "image", "reset"):
				labelled = bool(a.get("aria-label") or a.get("aria-labelledby") or a.get("title") or self._labels)
				self.inputs.append((a.get("id", ""), labelled))

	def handle_endtag(self, tag):
		if tag in self.SKIP and self.skip:
			self.skip -= 1
		if tag == "title":
			self._in_title = False
		elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._h:
			self.headings.append(tuple(self._h))
			self._h = None
		elif tag == "a" and self._a:
			self.links.append(tuple(self._a))
			self._a = None
		elif tag == "button" and self._btn is not None:
			if not self._btn.strip():
				self.buttons_bad += 1
			self._btn = None
		elif tag == "label" and self._labels:
			self._labels -= 1

	def handle_data(self, data):
		if self._in_title:
			self.title += data
		if self.skip:
			return
		self.words += len(data.split())
		if self._h:
			self._h[1] += data
		if self._a:
			self._a[1] += data
		if self._btn is not None:
			self._btn += data


def tool_pageanalyzer():
	url = ask_text(_("Web page address:"), _("Web page analyzer: SEO and accessibility"))
	if not url:
		return
	if not re.match(r"^https?://", url, re.I):
		url = "https://" + url

	def work():
		html = http_text(url, timeout=25)
		p = _Scan()
		p.feed(html)
		host = urlparse(url).hostname or ""
		ext = sum(1 for h, _t in p.links if h.startswith("http") and (urlparse(h).hostname or "") != host)
		empty_links = sum(1 for _h, t in p.links if not t.strip())
		unlabelled = sum(1 for i, ok in p.inputs if not ok and i not in p.label_for)
		h1 = sum(1 for lv, _t in p.headings if lv == 1)
		skipped, prev = 0, 0
		for lv, _t in p.headings:
			if prev and lv > prev + 1:
				skipped += 1
			prev = lv
		desc = p.meta.get("description", "").strip()
		base = "%s://%s" % (urlparse(url).scheme, urlparse(url).netloc)

		def exists(path):
			try:
				http_text(base + path, timeout=10, limit=2000)
				return True
			except Exception:
				return False
		out = ["Page: %s" % url, "", "SEO", "Title: %s (%d characters)" % (p.title.strip() or "missing", len(p.title.strip())),
			"Description: %s" % (("%d characters" % len(desc)) if desc else "missing"),
			"Canonical address: %s" % (p.canonical or "none"), "Main headings (H1): %d" % h1,
			"Words on the page: {:,}".format(p.words), "Links: %d, of which %d go to other sites" % (len(p.links), ext),
			"robots.txt: %s" % ("found" if exists("/robots.txt") else "not found"),
			"sitemap.xml: %s" % ("found" if exists("/sitemap.xml") else "not found"), "",
			"Accessibility", "Page language declared: %s" % (p.lang or "no"),
			"Images: %d, without alternative text: %d" % (p.imgs, p.noalt), "Links with no readable text: %d" % empty_links,
			"Buttons with no readable name: %d" % p.buttons_bad, "Form fields without a label: %d" % unlabelled,
			"Heading levels skipped: %d" % skipped, "", "Problems found:"]
		probs = []
		if not p.title.strip():
			probs.append("The page has no title.")
		if h1 != 1:
			probs.append("The page should have exactly one main heading (H1); it has %d." % h1)
		if not desc:
			probs.append("There is no meta description.")
		if not p.lang:
			probs.append("The page language is not declared, so a screen reader may use the wrong voice.")
		if p.noalt:
			probs.append("%d images have no alt attribute." % p.noalt)
		if empty_links:
			probs.append("%d links have no text, so a screen reader cannot say where they go." % empty_links)
		if p.buttons_bad:
			probs.append("%d buttons have no name." % p.buttons_bad)
		if unlabelled:
			probs.append("%d form fields have no label." % unlabelled)
		if skipped:
			probs.append("Heading levels are skipped %d times." % skipped)
		out += probs or ["None of the checked problems were found."]
		if p.headings:
			out += ["", "Heading outline:"] + ["%s%s %s" % ("  " * (lv - 1), "H%d" % lv, " ".join(t.split())[:100]) for lv, t in p.headings[:25]]
		return "\n".join(out)
	run_async(work, _("Web page analyzer: SEO and accessibility"))


# 21 --------------------------------------------------------------- translator
LANG_CODES = {"English": "en", "Arabic": "ar", "Urdu": "ur", "Hindi": "hi", "Tamil": "ta", "Telugu": "te",
	"Malayalam": "ml", "Kannada": "kn", "Bengali": "bn", "Punjabi": "pa", "Gujarati": "gu", "Marathi": "mr",
	"Sinhala": "si", "Nepali": "ne", "Persian": "fa", "Turkish": "tr", "French": "fr", "Spanish": "es",
	"Portuguese": "pt", "German": "de", "Italian": "it", "Dutch": "nl", "Russian": "ru", "Ukrainian": "uk",
	"Polish": "pl", "Swedish": "sv", "Greek": "el", "Hebrew": "he", "Chinese (Simplified)": "zh-CN",
	"Chinese (Traditional)": "zh-TW", "Japanese": "ja", "Korean": "ko", "Indonesian": "id", "Malay": "ms",
	"Thai": "th", "Vietnamese": "vi", "Filipino": "tl", "Swahili": "sw", "Hausa": "ha", "Amharic": "am",
	"Pashto": "ps"}


def _chunks(text, size=450):
	"""Split text into pieces the free translation service accepts, at sentence ends or spaces."""
	text = text.strip()
	out = []
	while len(text) > size:
		cut = max(text.rfind(". ", 0, size), text.rfind("\n", 0, size), text.rfind("? ", 0, size), text.rfind("! ", 0, size))
		if cut < size // 3:
			cut = text.rfind(" ", 0, size)
		if cut < size // 3:
			cut = size - 1
		out.append(text[:cut + 1].strip())
		text = text[cut + 1:].strip()
	if text:
		out.append(text)
	return out


def tool_translator():
	clip = ""
	try:
		clip = (api.getClipData() or "")[:2000]
	except Exception:
		pass
	r = ask_form(_("Translator"), [
		{"key": "src", "label": _("&Translate from:"), "type": "combo", "choices": LANGUAGES, "default": "English"},
		{"key": "dst", "label": _("Translate &into:"), "type": "combo", "choices": LANGUAGES, "default": "Hindi"},
		{"key": "text", "label": _("&Text to translate:"), "type": "multiline", "default": clip, "required": True},
	], intro=_("Free translation, no account or AI key needed. Text on the clipboard is filled in for you."),
		validate=lambda v: _("Please choose two different languages.") if v["src"] == v["dst"] else None)
	if not r:
		return
	pair = "%s|%s" % (LANG_CODES.get(r["src"], "en"), LANG_CODES.get(r["dst"], "en"))
	text, dst = r["text"], r["dst"]

	def work():
		out = []
		for part in _chunks(text, 450 if text.isascii() else 150):  # the free service accepts about 500 bytes at a time
			d = http_json("https://api.mymemory.translated.net/get?q=%s&langpair=%s" % (quote(part), quote(pair)))
			if str(d.get("responseStatus")) != "200":
				raise RuntimeError(str(d.get("responseDetails") or d.get("responseStatus")))
			out.append(_strip_html(d["responseData"]["translatedText"]))
		return "%s\n\n(%s)" % ("\n".join(out), _("Translated into %s") % dst)
	run_async(work, _("Translator"))


# 22 --------------------------------------------------------------- food products (Open Food Facts)
NUTRI = [("energy-kcal_100g", "Energy", "kcal"), ("fat_100g", "Fat", "g"), ("saturated-fat_100g", "Saturated fat", "g"),
	("carbohydrates_100g", "Carbohydrates", "g"), ("sugars_100g", "Sugars", "g"), ("fiber_100g", "Fibre", "g"),
	("proteins_100g", "Protein", "g"), ("salt_100g", "Salt", "g")]


def _food_text(p):
	name = p.get("product_name") or "Unnamed product"
	out = ["%s%s" % (name, (", " + p["brands"]) if p.get("brands") else "")]
	if p.get("quantity"):
		out.append("Size: %s" % p["quantity"])
	if p.get("code"):
		out.append("Barcode: %s" % p["code"])
	if p.get("nutriscore_grade"):
		out.append("Nutri-Score: %s (A is best, E is worst)" % str(p["nutriscore_grade"]).upper())
	if p.get("nova_group"):
		out.append("Processing level (NOVA, 1 to 4): %s" % p["nova_group"])
	nut = p.get("nutriments") or {}
	rows = ["%s %s %s" % (label, round(float(nut[k]), 1), unit) for k, label, unit in NUTRI if nut.get(k) not in (None, "")]
	if rows:
		out.append("Per 100 g: " + ", ".join(rows))
	allergens = [a.split(":")[-1].replace("-", " ") for a in (p.get("allergens_tags") or [])]
	if allergens:
		out.append("Allergens: " + ", ".join(allergens))
	if p.get("ingredients_text"):
		out.append("Ingredients: " + p["ingredients_text"][:600])
	return "\n".join(out)


def tool_food():
	r = ask_form(_("Food product lookup"), [
		{"key": "mode", "label": _("&Look up by:"), "type": "combo",
			"choices": [_("Product name"), _("Barcode number")]},
		{"key": "q", "label": _("&Product name or barcode:"), "type": "text", "required": True},
	], intro=_("Nutrition, ingredients and allergens from Open Food Facts."))
	if not r:
		return
	mode, q = r["mode_index"], r["q"].strip()
	fields = "code,product_name,brands,quantity,nutriscore_grade,nova_group,nutriments,allergens_tags,ingredients_text"

	def work():
		base = "https://world.openfoodfacts.org"
		if mode == 1:
			code = re.sub(r"\D", "", q)
			if not code:
				return _("A barcode contains only digits.")
			d = http_json("%s/api/v2/product/%s.json?fields=%s" % (base, code, fields))
			if d.get("status") != 1:
				return _("No product with this barcode was found.")
			d["product"].setdefault("code", code)
			return _food_text(d["product"])
		d = http_json("%s/cgi/search.pl?search_simple=1&action=process&json=1&page_size=5&fields=%s&search_terms=%s" % (
			base, fields, quote(q)))
		prods = [p for p in d.get("products", []) if p.get("product_name")]
		if not prods:
			return _("No products found.")
		return "\n\n".join("%d. %s" % (n, _food_text(p)) for n, p in enumerate(prods, 1))
	run_async(work, _("Food product lookup"))


# 23 --------------------------------------------------------------- postal codes
def tool_postal():
	r = ask_form(_("Postal code lookup"), [
		{"key": "c", "label": _("&Country:"), "type": "combo", "choices": COUNTRY_NAMES, "default": "India"},
		{"key": "z", "label": _("&Postal code, PIN or ZIP code:"), "type": "text", "required": True},
	], intro=_("Finds the town, state and map position of a postal code. About 60 countries are supported."))
	if not r:
		return
	cc = COUNTRY_CODE.get(r["c"], "").lower()
	z = r["z"].strip()

	def work():
		code = z.replace(" ", "") if cc not in ("gb",) else (z.split()[0] if " " in z else z[:-3] if len(z) > 4 else z)
		if cc == "ca":
			code = code[:3]
		try:
			d = http_json("https://api.zippopotam.us/%s/%s" % (quote(cc), quote(code)))
		except HTTPError as e:
			if e.code == 404:
				return _("Nothing found. Check the code and the country. Not every country is supported.")
			raise
		out = ["%s, postal code %s" % (d.get("country"), d.get("post code"))]
		for p in d.get("places", [])[:15]:
			out.append("%s, %s (%s). Latitude %s, longitude %s" % (p.get("place name"), p.get("state"),
				p.get("state abbreviation"), p.get("latitude"), p.get("longitude")))
		return "\n".join(out)
	run_async(work, _("Postal code lookup"))


# 24 --------------------------------------------------------------- anime and manga
def tool_anime():
	r = ask_form(_("Anime and manga search"), [
		{"key": "kind", "label": _("&Search for:"), "type": "combo", "choices": [_("Anime"), _("Manga")]},
		{"key": "q", "label": _("&Title or words:"), "type": "text", "required": True},
	])
	if not r:
		return
	kind, q = "manga" if r["kind_index"] == 1 else "anime", r["q"].strip()

	def work():
		d = http_json("https://api.jikan.moe/v4/%s?limit=5&sfw=true&q=%s" % (kind, quote(q)), timeout=25).get("data", [])
		if not d:
			return _("Nothing found.")
		out = []
		for n, a in enumerate(d, 1):
			title = a.get("title_english") or a.get("title")
			line = ["%d. %s%s" % (n, title, (" (%s)" % a["title"]) if a.get("title_english") and a["title_english"] != a.get("title") else "")]
			bits = [a.get("type"), a.get("status"), "Score %s" % a["score"] if a.get("score") else None]
			if kind == "anime" and a.get("episodes"):
				bits.append("%s episodes" % a["episodes"])
			if kind == "manga":
				if a.get("chapters"):
					bits.append("%s chapters" % a["chapters"])
				if a.get("volumes"):
					bits.append("%s volumes" % a["volumes"])
			year = a.get("year") or ((a.get("published") or a.get("aired") or {}).get("string"))
			if year:
				bits.append(str(year))
			line.append(", ".join(str(b) for b in bits if b))
			g = ", ".join(x["name"] for x in a.get("genres", []))
			if g:
				line.append("Genres: " + g)
			if a.get("synopsis"):
				line.append(a["synopsis"].replace("\r", "").strip()[:350])
			out.append("\n".join(line))
		return "\n\n".join(out)
	run_async(work, _("Anime and manga search"))


# 25 --------------------------------------------------------------- NASA picture of the day
def tool_apod():
	i = choose(_("Show:"), _("Space picture of the day"), [_("Today's picture"), _("A random picture from the archive")])
	if i < 0:
		return

	def work():
		url = "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY" + ("&count=1" if i == 1 else "")
		try:
			d = http_json(url, timeout=25)
		except HTTPError as e:
			if e.code == 429:
				return _("NASA's free shared key has reached its hourly limit. Please try again later.")
			raise
		if isinstance(d, list):
			d = d[0]
		out = [d.get("title", ""), "Date: %s" % d.get("date", "")]
		if d.get("copyright"):
			out.append("Photographer: %s" % str(d["copyright"]).replace("\n", " ").strip())
		out += ["", d.get("explanation", ""), "", "%s: %s" % ("Video" if d.get("media_type") == "video" else "Image",
			d.get("hdurl") or d.get("url", ""))]
		return "\n".join(out)
	run_async(work, _("Space picture of the day"))


# ---------------------------------------------------------------- sound effects tool
def tool_sounds():
	r = ask_form(_("Sound effects"), [
		{"key": "on", "label": _("Play sound effects in My assistant"), "type": "check", "default": sounds.is_enabled()},
		{"key": "s", "label": _("&Preview this sound:"), "type": "combo", "choices": [n for n, _f in sounds.SOUNDS]},
	], intro=_("Sound effects play when a window opens or closes, while a tool is working, and when it succeeds or fails."))
	if not r:
		return
	sounds.set_enabled(r["on"])
	sounds.play(sounds.SOUNDS[r["s_index"]][1], force=True)
	speak(_("Sound effects on") if r["on"] else _("Sound effects off"))


NEW_ONLINE_TOOLS = [
	(_("International Space Station and people in space"), tool_iss),
	(_("Trivia quiz"), tool_trivia),
	(_("Number and date facts"), tool_number),
	(_("Random advice"), tool_advice),
	(_("Random Wikipedia article"), tool_wikirandom),
	(_("TV show search"), tool_tvshows),
	(_("Recipe finder"), tool_recipes),
	(_("Upcoming rocket launches"), tool_launches),
	(_("GitHub lookup: users and repositories"), tool_github),
	(_("Software package info: PyPI and npm"), tool_package),
	(_("Website status check"), tool_sitecheck),
	(_("DNS lookup"), tool_dns),
	(_("Internet speed test"), tool_speedtest),
	(_("URL shortener"), tool_shorten),
	(_("News and blog feed reader (RSS)"), tool_rss),
	(_("Password breach checker"), tool_pwned),
	(_("Domain registration lookup (whois)"), tool_whois),
	(_("Podcast finder"), tool_podcasts),
	(_("Web page archiver (Wayback Machine)"), tool_archive),
	(_("Web page analyzer: SEO and accessibility"), tool_pageanalyzer),
	(_("Translator (free, 40 languages)"), tool_translator),
	(_("Food product lookup: nutrition and allergens"), tool_food),
	(_("Postal code lookup"), tool_postal),
	(_("Anime and manga search"), tool_anime),
	(_("Space picture of the day (NASA)"), tool_apod),
	(_("Website inspector: security, certificate, speed, DNS and email (advanced)"), tool_inspector),
]
