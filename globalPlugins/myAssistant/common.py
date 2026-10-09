# -*- coding: UTF-8 -*-
"""Shared helpers: dialogs, background work, HTTP, location."""
import json
import threading
import urllib.request
import wx
import gui
import ui
import api
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from . import sounds

UA = {"User-Agent": "Mozilla/5.0 (compatible; NVDA-MyAssistant/1.1)"}


def speak(text):
	ui.message(text)


def http_text(url, timeout=20, headers=None, limit=3000000):
	req = urllib.request.Request(url, headers=dict(UA, **(headers or {})))
	with urllib.request.urlopen(req, timeout=timeout) as r:
		raw = r.read(limit)
		charset = r.headers.get_content_charset() or "utf-8"
	return raw.decode(charset, "replace")


def http_json(url, timeout=15, headers=None):
	return json.loads(http_text(url, timeout, headers))


def bg(fn, cb):
	def w():
		try:
			r = fn()
		except Exception as e:
			r = _("Error: %s") % e
		wx.CallAfter(cb, r)
	threading.Thread(target=w, daemon=True).start()


def run_async(work, title, speak_only=False):
	"""Run work() in a thread and show the result in a dialog (speak_only is kept for compatibility)."""
	speak(_("Please wait"))
	sounds.play("working")

	def done(r):
		failed = isinstance(r, str) and r.startswith(_("Error: %s").split("%")[0])
		sounds.play("error" if failed else "success")
		show_text(title, r)
	bg(work, done)


def _finish(dlg, inner):
	main = wx.BoxSizer(wx.VERTICAL)
	main.Add(inner, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL | wx.EXPAND)
	main.Fit(dlg)
	dlg.SetSizer(main)
	dlg.CentreOnScreen()


def _modal(dlg, getter=None):
	gui.mainFrame.prePopup()
	try:
		code = dlg.ShowModal()
		return getter(dlg, code) if getter else code
	finally:
		dlg.Destroy()
		gui.mainFrame.postPopup()


def ask_text(prompt, title, default="", multiline=False):
	style = wx.OK | wx.CANCEL | wx.CENTRE | (wx.TE_MULTILINE if multiline else 0)
	dlg = wx.TextEntryDialog(gui.mainFrame, prompt, title, default, style=style)
	return _modal(dlg, lambda d, c: d.GetValue().strip() if c == wx.ID_OK else None)


def ask_form(title, fields, intro=None, validate=None):
	"""One dialog with several labelled controls, so nothing has to be typed when a list will do.

	Each field is a dict: key, label, type, choices, default, required.
	type: "combo" (list only), "editable" (list, or type your own), "text", "multiline",
	"number" (validated before the dialog closes) or "check".
	Returns a dict of values (combo fields also give key + "_index"), or None if cancelled.
	"""
	dlg = wx.Dialog(gui.mainFrame, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
	s = wx.BoxSizer(wx.VERTICAL)
	h = guiHelper.BoxSizerHelper(dlg, sizer=s)
	if intro:
		h.addItem(wx.StaticText(dlg, label=intro))
	ctrls = {}
	first = None
	for f in fields:
		t = f.get("type", "text")
		default = f.get("default")
		if t in ("combo", "editable"):
			choices = [str(c) for c in f["choices"]]
			c = h.addLabeledControl(f["label"], wx.ComboBox, choices=choices,
				style=wx.CB_READONLY if t == "combo" else wx.CB_DROPDOWN)
			if default is not None and str(default) in choices:
				c.SetSelection(choices.index(str(default)))
			elif t == "editable" and default:
				c.SetValue(str(default))
			elif choices and t == "combo":
				c.SetSelection(0)
		elif t == "multiline":
			c = h.addLabeledControl(f["label"], wx.TextCtrl, value=str(default or ""),
				style=wx.TE_MULTILINE, size=(520, 150))
		elif t == "check":
			c = wx.CheckBox(dlg, label=f["label"])
			c.SetValue(bool(default))
			h.addItem(c)
		else:
			c = h.addLabeledControl(f["label"], wx.TextCtrl, value=str(default if default is not None else ""))
		ctrls[f["key"]] = (f, c)
		first = first or c
	h.addDialogDismissButtons(dlg.CreateButtonSizer(wx.OK | wx.CANCEL))
	values = {}

	def collect():
		out, err, bad = {}, None, None
		for k, (f, c) in ctrls.items():
			t = f.get("type", "text")
			if t == "check":
				out[k] = c.GetValue()
				continue
			v = c.GetValue().strip()
			if t in ("combo", "editable"):
				out[k + "_index"] = c.GetSelection()
			if f.get("required") and not v and not err:
				err, bad = _("Please fill in: %s") % f["label"].replace("&", "").rstrip(":"), c
			if t == "number":
				if v:
					try:
						v = float(v.replace(",", ""))
					except ValueError:
						if not err:
							err, bad = _("Invalid number: %s") % f["label"].replace("&", "").rstrip(":"), c
				elif not err:
					err, bad = _("Please fill in: %s") % f["label"].replace("&", "").rstrip(":"), c
			out[k] = v
		if not err and validate:
			err = validate(out)
		return out, err, bad

	def onOk(evt):
		out, err, bad = collect()
		if err:
			speak(err)
			wx.MessageBox(err, title, wx.OK | wx.ICON_WARNING, dlg)
			(bad or first).SetFocus()
			return
		values.update(out)
		evt.Skip()

	dlg.Bind(wx.EVT_BUTTON, onOk, id=wx.ID_OK)
	_finish(dlg, s)
	if first:
		first.SetFocus()
	return _modal(dlg, lambda d, c: dict(values) if c == wx.ID_OK else None)


def ask_combo(prompt, title, choices, default=None, editable=False):
	"""A single combo box. Returns the chosen text, or None if cancelled."""
	r = ask_form(title, [{"key": "v", "label": prompt, "type": "editable" if editable else "combo",
		"choices": choices, "default": default, "required": editable}])
	return r["v"] if r else None


def ask_number(prompt, title, default=""):
	"""Returns a float, or None if cancelled. Invalid input is refused before the dialog closes."""
	r = ask_form(title, [{"key": "n", "label": prompt, "type": "number", "default": default}])
	return r["n"] if r else None


def choose(prompt, title, options):
	"""Pick one item from a combo box. Returns its index, or -1 if cancelled."""
	r = ask_form(title, [{"key": "c", "label": prompt, "type": "combo", "choices": options}])
	return r["c_index"] if r else -1


def ask_date_combo(title, prompt, default=None, min_year=1900, max_year=2100, names=None, days=31):
	"""Year, month and day combo boxes. Returns datetime.date, or None if cancelled.
	names/days let the Hijri converter reuse it; then the result is a (year, month, day) tuple."""
	import datetime
	import calendar
	from .data import MONTHS
	hijri = names is not None
	d = default or datetime.date.today()
	yy, mm, dd = (d if hijri else (d.year, d.month, d.day))
	months = names or MONTHS
	fields = [
		{"key": "y", "label": _("&Year:"), "type": "combo", "choices": list(range(min_year, max_year + 1)), "default": yy},
		{"key": "m", "label": _("&Month:"), "type": "combo", "choices": months, "default": months[mm - 1]},
		{"key": "d", "label": _("&Day:"), "type": "combo", "choices": list(range(1, days + 1)), "default": dd},
	]

	def check(v):
		if hijri:
			return None
		try:
			datetime.date(int(v["y"]), v["m_index"] + 1, int(v["d"]))
		except ValueError:
			return _("That day does not exist in the chosen month. Please choose another day.")
	r = ask_form(title, fields, intro=prompt, validate=check)
	if not r:
		return None
	y, m, day = int(r["y"]), r["m_index"] + 1, int(r["d"])
	return (y, m, day) if hijri else datetime.date(y, m, day)


def ask_city(title):
	"""City combo box. Returns None if cancelled, "" for the current location, or a city name."""
	from .data import CITIES
	here = _("Current location (automatic)")
	r = ask_form(title, [{"key": "c", "label": _("&City (choose from the list or type any city):"), "type": "editable",
		"choices": [here] + CITIES, "default": here}])
	if not r:
		return None
	return "" if r["c"] in ("", here) else r["c"]


def confirm(msg, title):
	return wx.MessageBox(msg, title, wx.YES_NO | wx.ICON_QUESTION, gui.mainFrame) == wx.YES


def show_text(title, text):
	"""Every tool shows its result here: a read-only text box with Copy and Close buttons."""
	text = str(text)
	dlg = wx.Dialog(gui.mainFrame, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
	s = wx.BoxSizer(wx.VERTICAL)
	h = guiHelper.BoxSizerHelper(dlg, sizer=s)
	short = len(text) < 200 and text.count("\n") < 3
	tc = h.addLabeledControl(_("Result:"), wx.TextCtrl, value=text,
		style=wx.TE_MULTILINE | wx.TE_READONLY, size=(560, 110 if short else 320))
	bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
	cp = bh.addButton(dlg, label=_("&Copy"))
	cl = bh.addButton(dlg, id=wx.ID_CLOSE, label=_("C&lose"))
	cp.Bind(wx.EVT_BUTTON, lambda e: (api.copyToClip(text), sounds.play("copy"), speak(_("Copied"))))
	cl.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))
	dlg.SetEscapeId(wx.ID_CLOSE)
	h.addItem(bh)
	_finish(dlg, s)
	tc.SetFocus()
	sounds.play("open")
	_modal(dlg)
	sounds.play("close")


def _clip():
	try:
		t = api.getClipData()
	except Exception:
		t = ""
	if not t:
		speak(_("The clipboard has no text"))
	return t


def get_location():
	try:
		d = http_json("https://ipapi.co/json/")
		if d.get("latitude") is not None:
			return {"ip": d.get("ip"), "city": d.get("city"), "region": d.get("region"),
				"country": d.get("country_name"), "cc": d.get("country_code"),
				"lat": d["latitude"], "lon": d["longitude"],
				"tz": d.get("timezone"), "isp": d.get("org")}
	except Exception:
		pass
	d = http_json("http://ip-api.com/json/")
	return {"ip": d.get("query"), "city": d.get("city"), "region": d.get("regionName"),
		"country": d.get("country"), "cc": d.get("countryCode"), "lat": d["lat"], "lon": d["lon"],
		"tz": d.get("timezone"), "isp": d.get("isp")}


def geocode(city):
	"""Returns (lat, lon, place name, country code). Empty city means the current location."""
	if city:
		from urllib.parse import quote
		g = http_json("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + quote(city))
		if not g.get("results"):
			raise RuntimeError(_("City not found."))
		r = g["results"][0]
		return r["latitude"], r["longitude"], "%s, %s" % (r["name"], r.get("country", "")), r.get("country_code", "")
	loc = get_location()
	return loc["lat"], loc["lon"], "%s, %s" % (loc["city"], loc["country"]), loc.get("cc") or ""


WX = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
	51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
	66: "freezing rain", 67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
	77: "snow grains", 80: "rain showers", 81: "heavy rain showers", 82: "violent rain showers",
	85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with hail",
	99: "severe thunderstorm with hail"}
