# -*- coding: UTF-8 -*-
"""The tools of My assistant: everyday tools, internet tools, offline tools, 70 AI tools and 5 advanced Gemini tools."""
import ast
import ctypes
import datetime
import json
import math
import operator
import os
import platform
import random
import re
import secrets
import shutil
import socket
import string
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import wx
import gui
import ui
import api
import tones
import queueHandler
import addonHandler
import globalVars
import languageHandler
from gui import guiHelper
from . import providers
from .online import ONLINE_TOOLS
from .offline import OFFLINE_TOOLS

addonHandler.initTranslation()

CFG = globalVars.appArgs.configPath
UA = {"User-Agent": "NVDA-MyAssistant/1.0"}


# ---------------------------------------------------------------- helpers
from .common import (speak, http_json, bg, run_async, _finish, _modal, ask_text, ask_number, choose,
	confirm, show_text, _clip, get_location, WX as _WX, ask_form, ask_combo, ask_city)
from .data import CURRENCIES, CURRENCY_LABELS, currency_code, TIMEZONES, LANGUAGES
from .ai_tools import AI_CATEGORIES, AI_COUNT
from .about import show_about
from .search import filter_tools
from logHandler import log
from .newtools import tool_sounds
from .gemini_tts import tool_gemini_tts
from .gemini_live import tool_gemini_live
from .gemini_tools import GEMINI_TOOLS
from . import sounds
from .alarmsounds import ALARM_SOUNDS, DEFAULT_SOUND


def _run(cmd):
	subprocess.Popen(cmd, creationflags=0x08000000)


# ---------------------------------------------------------------- alarm / timer engine
_lock = threading.Lock()
_alarms = []
_timers = []
_stop = threading.Event()
_thread = None
ALARM_FILE = os.path.join(CFG, "myAssistantAlarms.json")
NOTES_FILE = os.path.join(CFG, "myAssistantNotes.json")


def _read(path):
	try:
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return []


def _write(path, data):
	with open(path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=1)


def start_engine():
	global _thread
	_alarms[:] = _read(ALARM_FILE)
	_stop.clear()
	_thread = threading.Thread(target=_loop, daemon=True)
	_thread.start()


def stop_engine():
	_stop.set()


def _loop():
	while not _stop.wait(1):
		now = datetime.datetime.now()
		hm, today = now.strftime("%H:%M"), now.date().isoformat()
		fire = []
		with _lock:
			changed = False
			for a in list(_alarms):
				if a["time"] == hm and a.get("last") != today:
					a["last"] = today
					fire.append((a.get("label") or a["time"], a.get("sound", DEFAULT_SOUND), a.get("minutes", 5)))
					changed = True
					if not a.get("daily"):
						_alarms.remove(a)
			if changed:
				_write(ALARM_FILE, _alarms)
			t = time.time()
			for tm in list(_timers):
				if tm[0] <= t:
					_timers.remove(tm)
					fire.append((tm[1], DEFAULT_SOUND, 1))
		for f in fire:
			threading.Thread(target=_alert, args=f, daemon=True).start()


RING_MINUTES = [1, 2, 3, 5, 10, 15, 30, 60]


def _sound_names():
	return ["%d. %s" % (i + 1, n) for i, (n, _f, _d) in enumerate(ALARM_SOUNDS)]


class RingDialog(wx.Dialog):
	"""Shown while an alarm rings. Stop is the default button, so Enter or Escape silences it."""

	def __init__(self, text, stop, sound, minutes):
		super().__init__(gui.mainFrame, title=_("Alarm"))
		self.stop, self.text, self.sound, self.minutes = stop, text, sound, minutes
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		h.addItem(wx.StaticText(self, label=_("Alarm: %s") % text))
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.stopBtn = bh.addButton(self, id=wx.ID_OK, label=_("&Stop"))
		self.snoozeBtn = bh.addButton(self, label=_("S&nooze for 5 minutes"))
		self.stopBtn.SetDefault()
		self.stopBtn.Bind(wx.EVT_BUTTON, self.onStop)
		self.snoozeBtn.Bind(wx.EVT_BUTTON, self.onSnooze)
		self.Bind(wx.EVT_CLOSE, self.onStop)
		self.SetEscapeId(wx.ID_OK)
		h.addItem(bh)
		_finish(self, s)
		self.stopBtn.SetFocus()

	def onStop(self, evt):
		self.stop.set()
		self.finish()

	def onSnooze(self, evt):
		self.stop.set()
		when = datetime.datetime.now() + datetime.timedelta(minutes=5)
		with _lock:
			_alarms.append({"time": when.strftime("%H:%M"), "label": self.text, "daily": False,
				"sound": self.sound, "minutes": self.minutes})
			_alarms.sort(key=lambda a: a["time"])
			_write(ALARM_FILE, _alarms)
		speak(_("Snoozed until %s") % when.strftime("%H:%M"))
		self.finish()

	def finish(self):
		if getattr(self, "_done", False):
			return
		self._done = True
		try:
			self.Destroy()
			gui.mainFrame.postPopup()
		except Exception:
			pass


def _show_ring(box, text, stop, sound, minutes):
	try:
		gui.mainFrame.prePopup()
		dlg = RingDialog(text, stop, sound, minutes)
		box.append(dlg)
		dlg.Show()
		dlg.Raise()
	except Exception:
		pass


def _alert(text, sound=DEFAULT_SOUND, minutes=5):
	"""Ring with the chosen sound until it is stopped or the chosen number of minutes has passed."""
	if not 0 <= sound < len(ALARM_SOUNDS):
		sound = DEFAULT_SOUND
	_name, fname, length = ALARM_SOUNDS[sound]
	path = sounds.alarm_path(fname)
	stop = threading.Event()
	box = []
	wx.CallAfter(_show_ring, box, text, stop, sound, minutes)
	end = time.time() + max(1, int(minutes)) * 60
	next_speech = 0
	while not stop.is_set() and not _stop.is_set() and time.time() < end:
		if time.time() >= next_speech:
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Alarm: %s") % text)
			next_speech = time.time() + 20
		sounds.play_path(path)
		stop.wait(length + 0.6)
	stop.set()
	for d in box:
		wx.CallAfter(d.finish)


def parse_time(s):
	m = re.match(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*([ap]m)?\s*$", s, re.I)
	if not m:
		return None
	h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
	if ap == "pm" and h < 12:
		h += 12
	if ap == "am" and h == 12:
		h = 0
	if h > 23 or mi > 59:
		return None
	return "%02d:%02d" % (h, mi)


class _ListDialog(wx.Dialog):
	title_ = ""
	can_view = False

	def __init__(self):
		super().__init__(gui.mainFrame, title=self.title_)
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		self.lst = h.addLabeledControl(_("Items:"), wx.ListBox, choices=self.labels(), size=(450, 200))
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		bh.addButton(self, label=_("&Add...")).Bind(wx.EVT_BUTTON, lambda e: self.add())
		if self.can_view:
			bh.addButton(self, label=_("&View")).Bind(wx.EVT_BUTTON, lambda e: self.view())
		bh.addButton(self, label=_("&Delete")).Bind(wx.EVT_BUTTON, lambda e: self.delete())
		bh.addButton(self, id=wx.ID_CLOSE, label=_("C&lose")).Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		self.SetEscapeId(wx.ID_CLOSE)
		h.addItem(bh)
		_finish(self, s)
		self.lst.SetFocus()

	def refresh(self):
		self.lst.Set(self.labels())
		if self.lst.GetCount():
			self.lst.SetSelection(0)

	def view(self):
		pass


class AlarmAddDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Add alarm"))
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		now = datetime.datetime.now()
		self.hour = h.addLabeledControl(_("&Hour (00 to 23):"), wx.ComboBox,
			choices=["%02d" % i for i in range(24)], style=wx.CB_READONLY)
		self.minute = h.addLabeledControl(_("&Minute:"), wx.ComboBox,
			choices=["%02d" % i for i in range(60)], style=wx.CB_READONLY)
		self.hour.SetSelection(now.hour)
		self.minute.SetSelection(now.minute)
		self.label = h.addLabeledControl(_("&Label (optional):"), wx.TextCtrl)
		self.sound = h.addLabeledControl(_("Choose your &sound (100 sounds):"), wx.ComboBox,
			choices=_sound_names(), style=wx.CB_READONLY)
		self.sound.SetSelection(DEFAULT_SOUND)
		pv = wx.Button(self, label=_("&Preview sound"))
		h.addItem(pv)
		pv.Bind(wx.EVT_BUTTON, self.onPreview)
		self.sound.Bind(wx.EVT_COMBOBOX, self.onPreview)
		self.minutes = h.addLabeledControl(_("&Ring for:"), wx.ComboBox,
			choices=[(_("%d minute") if m == 1 else _("%d minutes")) % m for m in RING_MINUTES], style=wx.CB_READONLY)
		self.minutes.SetSelection(RING_MINUTES.index(5))
		self.daily = wx.CheckBox(self, label=_("&Repeat every day"))
		h.addItem(self.daily)
		h.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		_finish(self, s)
		self.hour.SetFocus()

	def onPreview(self, evt):
		i = self.sound.GetSelection()
		if i >= 0:
			sounds.play_path(sounds.alarm_path(ALARM_SOUNDS[i][1]))


class AlarmDialog(_ListDialog):
	title_ = _("Alarm manager")

	def labels(self):
		with _lock:
			return [("%s - %s (%s, %s, %s)" % (a["time"], a.get("label") or _("Alarm"),
				_("daily") if a.get("daily") else _("once"),
				ALARM_SOUNDS[min(a.get("sound", DEFAULT_SOUND), len(ALARM_SOUNDS) - 1)][0],
				_("rings %d min") % a.get("minutes", 5))) for a in _alarms]

	def add(self):
		res = _modal(AlarmAddDialog(self), lambda d, c: (
			"%02d:%02d" % (d.hour.GetSelection(), d.minute.GetSelection()),
			d.label.GetValue().strip(), d.daily.GetValue(), max(0, d.sound.GetSelection()),
			RING_MINUTES[max(0, d.minutes.GetSelection())]) if c == wx.ID_OK else None)
		if not res:
			return
		hm, label, daily, sound, minutes = res
		with _lock:
			_alarms.append({"time": hm, "label": label, "daily": daily, "sound": sound, "minutes": minutes})
			_alarms.sort(key=lambda a: a["time"])
			_write(ALARM_FILE, _alarms)
		self.refresh()
		speak(_("Alarm set for %s, sound %s, rings for %d minutes") % (hm, ALARM_SOUNDS[sound][0], minutes))

	def delete(self):
		i = self.lst.GetSelection()
		if i < 0:
			return
		with _lock:
			del _alarms[i]
			_write(ALARM_FILE, _alarms)
		self.refresh()
		speak(_("Deleted"))


class NotesDialog(_ListDialog):
	title_ = _("Notes manager")
	can_view = True

	def __init__(self):
		self.notes = _read(NOTES_FILE)
		super().__init__()

	def labels(self):
		return [(n.splitlines() or [""])[0][:80] for n in self.notes]

	def add(self):
		t = ask_text(_("Note text:"), _("Add note"), multiline=True)
		if t:
			self.notes.append(t)
			_write(NOTES_FILE, self.notes)
			self.refresh()

	def view(self):
		i = self.lst.GetSelection()
		if i >= 0:
			show_text(_("Note"), self.notes[i])

	def delete(self):
		i = self.lst.GetSelection()
		if i >= 0:
			del self.notes[i]
			_write(NOTES_FILE, self.notes)
			self.refresh()
			speak(_("Deleted"))


CHAT_STYLES = [
	(_("Normal"), None),
	(_("Short answers"), "Answer briefly, in one to three sentences."),
	(_("Detailed answers"), "Give thorough, well organized answers."),
	(_("Teacher: explain step by step"), "Act as a patient teacher. Explain step by step with simple examples."),
	(_("Friendly conversation partner"), "Chat in a warm, friendly and natural way."),
	(_("Professional expert"), "Answer like a professional expert: precise, formal and well reasoned."),
]
CHAT_BASE = ("Reply in plain text only, without markdown symbols, so a screen reader reads it cleanly. ")


class ChatDialog(wx.Dialog):
	def __init__(self):
		super().__init__(gui.mainFrame, title=_("AI chat - %s") % providers.current_name(),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.msgs = []
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		self.history = h.addLabeledControl(_("Conversation:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(620, 300))
		self.style = h.addLabeledControl(_("Assistant &style:"), wx.ComboBox,
			choices=[n for n, _p in CHAT_STYLES], style=wx.CB_READONLY)
		self.style.SetSelection(0)
		self.input = h.addLabeledControl(_("Your &message (Enter to send):"), wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER)
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.sendBtn = bh.addButton(self, label=_("&Send"))
		clr = bh.addButton(self, label=_("Clea&r"))
		cl = bh.addButton(self, id=wx.ID_CLOSE, label=_("C&lose"))
		self.sendBtn.Bind(wx.EVT_BUTTON, self.onSend)
		self.input.Bind(wx.EVT_TEXT_ENTER, self.onSend)
		clr.Bind(wx.EVT_BUTTON, self.onClear)
		cl.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		self.SetEscapeId(wx.ID_CLOSE)
		h.addItem(bh)
		_finish(self, s)
		self.input.SetFocus()

	def onClear(self, e):
		self.msgs = []
		self.history.SetValue("")
		self.input.SetFocus()
		speak(_("Conversation cleared"))

	def onSend(self, e):
		text = self.input.GetValue().strip()
		if not text or not self.sendBtn.IsEnabled():
			return
		self.input.SetValue("")
		self.msgs.append({"role": "user", "content": text})
		self.history.AppendText(_("You: %s") % text + "\n\n")
		self.sendBtn.Disable()
		speak(_("Thinking"))
		msgs = list(self.msgs)
		system = CHAT_BASE + (CHAT_STYLES[max(0, self.style.GetSelection())][1] or "")

		def work():
			try:
				return providers.ask(msgs, system=system)
			except Exception as ex:
				return _("Error: %s") % ex

		def done(reply):
			try:
				self.history.AppendText(_("AI: %s") % reply + "\n\n")
				if not reply.startswith(_("Error:")):
					self.msgs.append({"role": "assistant", "content": reply})
				else:
					self.msgs.pop()
				self.sendBtn.Enable()
			except RuntimeError:
				return
			speak(reply)
		bg(work, done)


# ---------------------------------------------------------------- tools
def tool_chat():
	_modal(ChatDialog())


def tool_alarm():
	_modal(AlarmDialog())


def tool_timer():
	r = ask_form(_("Timer"), [
		{"key": "h", "label": _("&Hours:"), "type": "combo", "choices": list(range(0, 24)), "default": 0},
		{"key": "m", "label": _("&Minutes:"), "type": "combo", "choices": list(range(0, 60)), "default": 5},
		{"key": "s", "label": _("&Seconds:"), "type": "combo", "choices": list(range(0, 60)), "default": 0},
		{"key": "label", "label": _("&Label (optional):"), "type": "text"},
	], validate=lambda v: _("Please choose a time longer than zero.") if not (int(v["h"]) or int(v["m"]) or int(v["s"])) else None)
	if not r:
		return
	secs = int(r["h"]) * 3600 + int(r["m"]) * 60 + int(r["s"])
	label = r["label"] or _("Timer finished")
	with _lock:
		_timers.append((time.time() + secs, label))
	show_text(_("Timer"), _("Timer started for %s. Label: %s") % (_fmt(secs), label))


_sw = {"start": None, "elapsed": 0.0}


def _sw_now():
	return _sw["elapsed"] + ((time.time() - _sw["start"]) if _sw["start"] else 0)


def _fmt(sec):
	sec = int(sec)
	return "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)


def tool_stopwatch():
	i = choose(_("Stopwatch:"), _("Stopwatch"), [_("Start"), _("Stop"), _("Report elapsed time"), _("Reset")])
	if i == 0 and not _sw["start"]:
		_sw["start"] = time.time()
		show_text(_("Stopwatch"), _("Stopwatch started"))
	elif i == 1 and _sw["start"]:
		_sw["elapsed"] = _sw_now()
		_sw["start"] = None
		show_text(_("Stopwatch"), _("Stopped at %s") % _fmt(_sw["elapsed"]))
	elif i == 2:
		show_text(_("Stopwatch"), _("Elapsed %s") % _fmt(_sw_now()))
	elif i == 3:
		_sw["start"], _sw["elapsed"] = None, 0.0
		show_text(_("Stopwatch"), _("Stopwatch reset"))


def tool_power():
	opts = [_("Shut down now"), _("Restart now"), _("Sleep"), _("Hibernate"), _("Lock computer"),
		_("Sign out"), _("Shut down after a delay"), _("Restart after a delay"), _("Cancel scheduled shutdown")]
	i = choose(_("Choose a power action:"), _("Power manager"), opts)
	if i < 0:
		return
	if i in (0, 1, 2, 3, 5) and not confirm(_("Are you sure: %s?") % opts[i], _("Power manager")):
		return
	if i == 0:
		_run(["shutdown", "/s", "/t", "0"])
	elif i == 1:
		_run(["shutdown", "/r", "/t", "0"])
	elif i == 2:
		_run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
	elif i == 3:
		_run(["shutdown", "/h"])
	elif i == 4:
		ctypes.windll.user32.LockWorkStation()
	elif i == 5:
		_run(["shutdown", "/l"])
	elif i in (6, 7):
		v = ask_combo(_("Delay in minutes:"), opts[i], ["1", "5", "10", "15", "20", "30", "45", "60", "90", "120", "180"], "30")
		if not v:
			return
		secs = int(v) * 60
		_run(["shutdown", "/s" if i == 6 else "/r", "/t", str(secs)])
		show_text(_("Power manager"), _("Scheduled in %s minutes") % v)
	elif i == 8:
		_run(["shutdown", "/a"])
		show_text(_("Power manager"), _("Cancel requested"))


def tool_volume():
	i = choose(_("Volume:"), _("Volume control"), [_("Volume up"), _("Volume down"), _("Mute or unmute")])
	if i < 0:
		return
	vk, n = [(0xAF, 5), (0xAE, 5), (0xAD, 1)][i]
	for _i in range(n):
		ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
		ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
	show_text(_("Volume control"), _("Done: %s") % [_("Volume up"), _("Volume down"), _("Mute or unmute")][i])


WIKI_LANGS = [(_("Automatic (NVDA language)"), ""), ("English", "en"), ("Arabic", "ar"), ("Urdu", "ur"), ("Hindi", "hi"),
	("Tamil", "ta"), ("Bengali", "bn"), ("Persian", "fa"), ("Turkish", "tr"), ("French", "fr"), ("Spanish", "es"),
	("German", "de"), ("Portuguese", "pt"), ("Russian", "ru"), ("Chinese", "zh"), ("Japanese", "ja")]


def tool_wikipedia():
	r = ask_form(_("Wikipedia"), [
		{"key": "q", "label": _("Search Wikipedia &for:"), "type": "text", "required": True},
		{"key": "lang", "label": _("&Language:"), "type": "combo", "choices": [n for n, _c in WIKI_LANGS]},
	])
	if not r:
		return
	q = r["q"]
	lang = WIKI_LANGS[r["lang_index"]][1] or (languageHandler.getLanguage() or "en").split("_")[0] or "en"

	def work():
		def go(lg):
			s = http_json("https://%s.wikipedia.org/w/api.php?action=opensearch&limit=1&format=json&search=%s"
				% (lg, urllib.parse.quote(q)))
			if not s[1]:
				return None
			t = s[1][0]
			d = http_json("https://%s.wikipedia.org/api/rest_v1/page/summary/%s"
				% (lg, urllib.parse.quote(t.replace(" ", "_"), safe="")))
			return "%s\n\n%s\n\n%s" % (d.get("title", t), d.get("extract", ""),
				d.get("content_urls", {}).get("desktop", {}).get("page", ""))
		try:
			r = go(lang)
		except Exception:
			r = None
		return r or go("en") or _("No results found.")
	run_async(work, _("Wikipedia"))


def tool_weather():
	city = ask_city(_("Weather checker"))
	if city is None:
		return

	def work():
		if city:
			g = http_json("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(city))
			if not g.get("results"):
				return _("City not found.")
			r = g["results"][0]
			lat, lon, place = r["latitude"], r["longitude"], "%s, %s" % (r["name"], r.get("country", ""))
		else:
			loc = get_location()
			lat, lon, place = loc["lat"], loc["lon"], "%s, %s" % (loc["city"], loc["country"])
		w = http_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=1"
			"&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
			"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max" % (lat, lon))
		c, d = w["current"], w["daily"]
		return ("Weather in %s\n%s, %s°C (feels like %s°C)\nHumidity %s%%, wind %s km/h\n"
			"Today: high %s°C, low %s°C, chance of rain %s%%") % (
			place, _WX.get(c["weather_code"], "unknown conditions").capitalize(), c["temperature_2m"],
			c["apparent_temperature"], c["relative_humidity_2m"], c["wind_speed_10m"],
			d["temperature_2m_max"][0], d["temperature_2m_min"][0], d["precipitation_probability_max"][0])
	run_async(work, _("Weather"))


def tool_dictionary():
	w = ask_text(_("English word to define:"), _("Dictionary"))
	if not w:
		return

	def work():
		try:
			d = http_json("https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(w))
		except Exception:
			return _("Word not found.")
		out = []
		for m in d[0].get("meanings", []):
			out.append(m.get("partOfSpeech", "").capitalize())
			for i, df in enumerate(m.get("definitions", [])[:3], 1):
				out.append("%d. %s" % (i, df["definition"]))
			out.append("")
		return "\n".join(out).strip() or _("No definition found.")
	run_async(work, _("Dictionary"))


def tool_currency():
	r = ask_form(_("Currency converter"), [
		{"key": "amt", "label": _("&Amount:"), "type": "number", "default": "1"},
		{"key": "a", "label": _("&From currency:"), "type": "combo", "choices": CURRENCY_LABELS, "default": "USD - US Dollar"},
		{"key": "b", "label": _("&To currency:"), "type": "combo", "choices": CURRENCY_LABELS, "default": "EUR - Euro"},
	])
	if not r:
		return
	amt, a, b = r["amt"], currency_code(r["a"]), currency_code(r["b"])

	def work():
		rates = http_json("https://open.er-api.com/v6/latest/USD")["rates"]
		if a not in rates or b not in rates:
			return _("Exchange rate not available for this currency.")
		res = amt / rates[a] * rates[b]
		one = 1 / rates[a] * rates[b]
		return "{:,.2f} {} = {:,.2f} {}\n1 {} = {:,.4f} {}".format(amt, a, res, b, a, one, b)
	run_async(work, _("Currency"))


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
	ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
	ast.USub: operator.neg, ast.UAdd: operator.pos}
_FN = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log10,
	"ln": math.log, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil}
_CONST = {"pi": math.pi, "e": math.e}


def _ev(n):
	if isinstance(n, ast.Expression):
		return _ev(n.body)
	if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
		return n.value
	if isinstance(n, ast.Name) and n.id in _CONST:
		return _CONST[n.id]
	if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
		l, r = _ev(n.left), _ev(n.right)
		if isinstance(n.op, ast.Pow) and abs(r) > 1000:
			raise ValueError("exponent too large")
		return _OPS[type(n.op)](l, r)
	if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
		return _OPS[type(n.op)](_ev(n.operand))
	if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FN:
		return _FN[n.func.id](*[_ev(a) for a in n.args])
	raise ValueError("unsupported")


def tool_calculator():
	e = ask_text(_("Expression (for example 12*(3+4)/5 or sqrt(2)):"), _("Calculator"))
	if not e:
		return
	try:
		r = _ev(ast.parse(e.replace("^", "**").replace("×", "*").replace("÷", "/"), mode="eval"))
		show_text(_("Calculator"), "%s = %s" % (e, round(r, 10) if isinstance(r, float) else r))
	except ZeroDivisionError:
		show_text(_("Calculator"), _("Cannot divide by zero"))
	except Exception:
		show_text(_("Calculator"), _("Invalid expression"))


class _SPS(ctypes.Structure):
	_fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
		("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
		("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def tool_battery():
	s = _SPS()
	if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
		show_text(_("Battery checker"), _("Could not read battery status"))
		return
	if s.BatteryFlag == 128:
		show_text(_("Battery checker"), _("No battery detected. Running on AC power."))
		return
	parts = [_("Battery %d percent") % s.BatteryLifePercent if s.BatteryLifePercent != 255 else _("Battery level unknown")]
	parts.append(_("charging") if s.BatteryFlag & 8 else (_("plugged in") if s.ACLineStatus == 1 else _("on battery")))
	if s.BatteryLifeTime != 0xFFFFFFFF and s.ACLineStatus != 1:
		parts.append(_("%d hours %d minutes remaining") % (s.BatteryLifeTime // 3600, s.BatteryLifeTime % 3600 // 60))
	if s.SystemStatusFlag == 1:
		parts.append(_("battery saver on"))
	show_text(_("Battery checker"), ", ".join(parts))


def tool_location():
	def work():
		l = get_location()
		try:
			api.copyToClip("%s, %s" % (l["lat"], l["lon"]))
		except Exception:
			pass
		return ("Approximate location (based on your IP address, not GPS)\nCity: %s\nRegion: %s\nCountry: %s\n"
			"Coordinates: %s, %s (copied to clipboard)\nTime zone: %s\nIP address: %s\nProvider: %s\n"
			"Map: https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=12/%s/%s") % (
			l["city"], l["region"], l["country"], l["lat"], l["lon"], l["tz"], l["ip"], l["isp"],
			l["lat"], l["lon"], l["lat"], l["lon"])
	run_async(work, _("Location tracker"))


class _MEM(ctypes.Structure):
	_fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
		("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
		("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
		("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
		("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def tool_sysinfo():
	m = _MEM()
	m.dwLength = ctypes.sizeof(m)
	ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
	ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
	up = ctypes.windll.kernel32.GetTickCount64() // 1000
	du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
	g = 1024 ** 3
	show_text(_("System info"), "Computer: %s\nWindows: %s %s\nProcessor cores: %s\n"
		"Memory: %.1f GB used of %.1f GB (%d%%)\nSystem drive: %.1f GB free of %.1f GB\nUptime: %dd %dh %dm" % (
		platform.node(), platform.system(), platform.version(), os.cpu_count(),
		(m.ullTotalPhys - m.ullAvailPhys) / g, m.ullTotalPhys / g, m.dwMemoryLoad,
		du.free / g, du.total / g, up // 86400, up % 86400 // 3600, up % 3600 // 60))


def tool_network():
	def work():
		out = ["Computer name: " + socket.gethostname()]
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("8.8.8.8", 80))
			out.append("Local IP: " + s.getsockname()[0])
			s.close()
		except OSError:
			out.append("Local IP: not connected")
		try:
			r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True,
				creationflags=0x08000000, timeout=8).stdout
			ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", r, re.M)
			sig = re.search(r"^\s*Signal\s*:\s*(.+)$", r, re.M)
			if ssid:
				out.append("Wi-Fi: %s, signal %s" % (ssid.group(1).strip(), sig.group(1).strip() if sig else "?"))
			else:
				out.append("Wi-Fi: not connected")
		except Exception:
			pass
		try:
			out.append("Public IP: %s" % get_location()["ip"])
		except Exception:
			out.append("Public IP: unavailable")
		return "\n".join(out)
	run_async(work, _("Network info"))


def tool_internet():
	def work():
		t = time.time()
		try:
			socket.create_connection(("1.1.1.1", 443), 4).close()
		except OSError as e:
			return _("No internet connection: %s") % e
		return _("Internet is working. Response time %d milliseconds.") % ((time.time() - t) * 1000)
	run_async(work, _("Internet check"))


def tool_datetime():
	show_text(_("Current date and time"), datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p"))


def tool_worldclock():
	names = [n for n, _o in TIMEZONES]
	r = ask_form(_("World clock"), [
		{"key": "z", "label": _("&Place (time zone):"), "type": "combo", "choices": names, "default": "UTC"},
	])
	if not r:
		return
	name = r["z"]
	now = datetime.datetime.now(datetime.timezone.utc)
	try:
		from zoneinfo import ZoneInfo
		t = now.astimezone(ZoneInfo(name))
	except Exception:
		off = dict(TIMEZONES)[name]
		t = now.astimezone(datetime.timezone(datetime.timedelta(minutes=off)))
	show_text(_("World clock"), _("%s: %s") % (name.replace("_", " "), t.strftime("%A %d %B %Y, %I:%M %p")))


def tool_notes():
	_modal(NotesDialog())


def tool_clipboard():
	t = _clip()
	if t:
		show_text(_("Clipboard"), t)


def tool_window():
	try:
		if _open["dlg"] is not None:
			title = _open["title"]  # the tools list itself is the foreground window now
		else:
			title = api.getForegroundObject().name
		show_text(_("Active window title"), title or _("Untitled window"))
	except Exception:
		show_text(_("Active window title"), _("Unavailable"))


def tool_password():
	r = ask_form(_("Password generator"), [
		{"key": "n", "label": _("Password &length:"), "type": "combo", "choices": list(range(8, 65)), "default": 16},
		{"key": "sym", "label": _("Include &symbols"), "type": "check", "default": True},
		{"key": "digits", "label": _("Include &numbers"), "type": "check", "default": True},
	])
	if not r:
		return
	chars = string.ascii_letters + (string.digits if r["digits"] else "") + ("!@#$%^&*-_=+?" if r["sym"] else "")
	pw = "".join(secrets.choice(chars) for _i in range(int(r["n"])))
	api.copyToClip(pw)
	show_text(_("Password generator"), pw + "\n\n" + _("Copied to clipboard."))


def tool_random():
	i = choose(_("Choose:"), _("Random"), [_("Flip a coin"), _("Roll a die"), _("Random number 1 to 100")])
	if i == 0:
		show_text(_("Random"), random.choice([_("Heads"), _("Tails")]))
	elif i == 1:
		show_text(_("Random"), str(random.randint(1, 6)))
	elif i == 2:
		show_text(_("Random"), str(random.randint(1, 100)))


def tool_about():
	show_about()


CAT_ALL = _("All tools")
CAT_TIME = _("Time, alarms and reminders")
CAT_SYSTEM = _("Computer and system")
CAT_UTIL = _("Everyday utilities")
CAT_NET = _("Internet tools")
CAT_OFF = _("Offline calculators and converters")
CAT_AI = _("AI: chat")

_TIME = [(_("Alarm manager"), tool_alarm), (_("Timer"), tool_timer), (_("Stopwatch"), tool_stopwatch),
	(_("World clock"), tool_worldclock), (_("Current date and time"), tool_datetime)]
_SYSTEM = [(_("Power manager"), tool_power), (_("Volume control"), tool_volume), (_("Battery checker"), tool_battery),
	(_("System information"), tool_sysinfo), (_("Network and Wi-Fi information"), tool_network),
	(_("Internet connection check"), tool_internet), (_("Active window title"), tool_window),
	(_("Location tracker"), tool_location)]
_UTIL = [(_("Calculator"), tool_calculator), (_("Currency converter"), tool_currency), (_("Notes manager"), tool_notes),
	(_("Read clipboard"), tool_clipboard), (_("Password generator"), tool_password),
	(_("Coin, dice and random number"), tool_random), (_("Wikipedia search"), tool_wikipedia),
	(_("Weather checker"), tool_weather), (_("Dictionary"), tool_dictionary),
	(_("Sound effects settings and preview"), tool_sounds),
	(_("About My assistant and tutorials"), tool_about)]
_AI_CHAT = [(_("AI chat box"), tool_chat), (_("AI: Gemini voices text to speech"), tool_gemini_tts),
	(_("AI: Gemini Live Assistant"), tool_gemini_live)] + list(GEMINI_TOOLS)
_DROP = {_("AI: improve or explain clipboard text"), _("AI: ask a quick question")}
_ONLINE = [t for t in ONLINE_TOOLS if t[0] not in _DROP]

CATEGORIES = [(CAT_AI, _AI_CHAT)] + list(AI_CATEGORIES) + [(CAT_TIME, _TIME), (CAT_UTIL, _UTIL),
	(CAT_NET, _ONLINE), (CAT_OFF, list(OFFLINE_TOOLS)), (CAT_SYSTEM, _SYSTEM)]
TOOLS = [t for _c, items in CATEGORIES for t in items]
CATEGORIES.insert(0, (CAT_ALL, TOOLS))


_CAT_OF = {}
for _cn, _items in CATEGORIES[1:]:
	for _t in _items:
		_CAT_OF.setdefault(id(_t), _cn)


def _category_of(item):
	return _CAT_OF.get(id(item), "")


class ToolsDialog(wx.Dialog):
	"""The tools list. It stays open while a tool runs: when a result or dialog is closed you are back in the list."""

	def __init__(self):
		super().__init__(gui.mainFrame, title=_("My assistant"))
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		# Search box: type any part of a tool name; small spelling mistakes are fine.
		self.search = h.addLabeledControl(_("&Search tools (spelling mistakes are fine):"), wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER)
		self.cat = h.addLabeledControl(_("&Category:"), wx.ComboBox,
			choices=["%s (%d)" % (n, len(items)) for n, items in CATEGORIES], style=wx.CB_READONLY)
		self.cat.SetSelection(0)
		self.items = TOOLS
		self.lst = h.addLabeledControl(_("&Tools:"), wx.ListBox, choices=[n for n, _f in self.items], size=(460, 320))
		self.lst.SetSelection(0)
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		run = bh.addButton(self, id=wx.ID_OK, label=_("&Run"))
		cl = bh.addButton(self, id=wx.ID_CANCEL, label=_("&Close"))
		run.SetDefault()
		run.Bind(wx.EVT_BUTTON, self.onRun)
		self.cat.Bind(wx.EVT_COMBOBOX, self.onCategory)
		self.lst.Bind(wx.EVT_LISTBOX, self.onMove)
		self.lst.Bind(wx.EVT_LISTBOX_DCLICK, self.onRun)
		self.search.Bind(wx.EVT_TEXT, self.onSearchText)
		self.search.Bind(wx.EVT_TEXT_ENTER, self.onRun)
		self.search.Bind(wx.EVT_KEY_DOWN, self.onSearchKey)
		self.Bind(wx.EVT_ACTIVATE, self.onActivate)
		cl.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
		self.SetEscapeId(wx.ID_CANCEL)
		h.addItem(bh)
		_finish(self, s)
		self._timer = None
		self._ready = False
		self.search.SetFocus()

	# -- showing the right tools
	def _show(self, items, keep=None):
		self.items = items
		self.lst.Set([n for n, _f in items])
		if items:
			sel = 0
			if keep is not None:
				for k, it in enumerate(items):
					if it[1] is keep:
						sel = k
						break
			self.lst.SetSelection(sel)

	def onCategory(self, evt):
		sounds.play("move")
		self.search.ChangeValue("")
		i = self.cat.GetSelection()
		if i >= 0:
			self._show(CATEGORIES[i][1])

	def onSearchText(self, evt):
		# Wait a moment after the last key so NVDA is not interrupted on every letter.
		if self._timer:
			self._timer.Stop()
		self._timer = wx.CallLater(350, self._doSearch)

	def _doSearch(self):
		try:
			q = self.search.GetValue()
		except RuntimeError:
			return
		if not q.strip():
			i = self.cat.GetSelection()
			self._show(CATEGORIES[i if i >= 0 else 0][1])
			return
		found = filter_tools(q, TOOLS, _category_of)
		self._show(found)
		if found:
			speak(_("%d tools found. %s") % (len(found), found[0][0]))
		else:
			speak(_("No tools found"))

	def onSearchKey(self, evt):
		k = evt.GetKeyCode()
		if k == wx.WXK_DOWN and self.items:
			if self._timer:
				self._timer.Stop()
				self._doSearch()
			self.lst.SetFocus()
			return
		evt.Skip()

	# -- sounds and focus
	def onMove(self, evt):
		sounds.play("move")
		evt.Skip()

	def onActivate(self, evt):
		# After a result or another dialog closes, put the focus back in the tools list.
		if evt.GetActive() and self._ready and self.items:
			wx.CallAfter(self._focusList)
		evt.Skip()

	def _focusList(self):
		try:
			if self.lst.GetSelection() < 0 and self.items:
				self.lst.SetSelection(0)
			self.lst.SetFocus()
		except RuntimeError:
			pass

	# -- running a tool (the menu does not close)
	def onRun(self, e):
		if self._timer and self._timer.IsRunning():
			self._timer.Stop()
			self._doSearch()
		i = self.lst.GetSelection()
		if i < 0 or i >= len(self.items):
			return
		fn = self.items[i][1]
		self._ready = True
		wx.CallAfter(self._call, fn)

	def _call(self, fn):
		try:
			fn()
		except Exception:
			log.error("My assistant: a tool failed", exc_info=True)
			sounds.play("error")
			speak(_("This tool could not run. See the NVDA log for details."))


_open = {"dlg": None, "title": None}


def open_tools():
	"""Open the tools list. It plays the enter sound when it opens and the exit sound when you close it."""
	cur = _open["dlg"]
	if cur is not None:
		try:
			cur.Raise()
			cur.search.SetFocus()
			return
		except RuntimeError:
			_open["dlg"] = None
	try:
		# The window you were in before the list opened, for the Active window title tool.
		_open["title"] = api.getForegroundObject().name
	except Exception:
		_open["title"] = None
	dlg = ToolsDialog()
	_open["dlg"] = dlg
	sounds.play("enter")
	try:
		_modal(dlg)
	finally:
		_open["dlg"] = None
		sounds.play("exit")
