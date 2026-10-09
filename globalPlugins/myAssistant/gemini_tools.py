# -*- coding: UTF-8 -*-
"""Five advanced Gemini tools. They use your Google Gemini API key (NVDA settings, My assistant).

1. Gemini web search with sources (Google Search grounding)
2. Gemini image and screen describer (image file, clipboard picture or a screenshot)
3. Gemini document and PDF reader
4. Gemini audio and video transcriber
5. Gemini web page and YouTube summarizer
"""
import base64
import io
import json
import mimetypes
import os
import re
import threading
import time
import urllib.error
import urllib.request
import wx
import gui
import addonHandler
from . import providers
from .common import ask_form, run_async, speak
from .data import LANGUAGES
from .gemini_tts import gemini_key, NO_KEY
from .common import show_text

addonHandler.initTranslation()

API = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-2.5-flash"]
MAX_FILE = 14 * 1024 * 1024  # inline requests are limited to about 20 MB after base64 encoding
SYSTEM = ("You are a helpful assistant inside a screen reader add-on. The user is blind and uses NVDA. "
	"Reply in plain text only. Never use markdown symbols such as asterisks, hash signs, backticks or "
	"tables. Organize the answer with short paragraphs or numbered lines so it is easy to read aloud.")


# ------------------------------------------------------------------ core request
def _models():
	out = []
	try:
		mine = (providers.load().get("models", {}).get("gemini") or "").strip()
	except Exception:
		mine = ""
	for m in [mine] + FALLBACK_MODELS:
		if m and m not in out:
			out.append(m)
	return out


def _clean(text):
	"""Remove markdown marks so NVDA does not read them aloud."""
	text = re.sub(r"```[a-zA-Z]*\n?", "", text)
	text = text.replace("**", "").replace("__", "").replace("`", "")
	text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
	text = re.sub(r"(?m)^(\s*)[*•]\s+", r"\1- ", text)
	return text.strip()


def generate(parts, tools=None, system=SYSTEM):
	"""Send parts to Gemini. Returns (text, sources). Raises RuntimeError with a readable message."""
	key = gemini_key()
	if not key:
		raise RuntimeError(NO_KEY)
	payload = {"contents": [{"role": "user", "parts": parts}], "systemInstruction": {"parts": [{"text": system}]}}
	if tools:
		payload["tools"] = tools
	body = json.dumps(payload).encode("utf-8")
	last = ""
	for model in _models():
		req = urllib.request.Request(API % model, data=body, method="POST", headers={
			"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": "NVDA-MyAssistant/1.1"})
		try:
			with urllib.request.urlopen(req, timeout=180) as r:
				data = json.loads(r.read().decode("utf-8"))
		except urllib.error.HTTPError as e:
			try:
				msg = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
			except Exception:
				msg = ""
			last = msg or "HTTP %d" % e.code
			if e.code == 404:
				continue  # this model is not available: try the next one
			if e.code in (400, 401, 403) and "api key" in msg.lower():
				raise RuntimeError(_("Gemini did not accept the API key. Check the key in NVDA settings, "
					"My assistant. %s") % msg)
			if e.code == 429:
				raise RuntimeError(_("Gemini says the limit was reached. Wait a minute and try again. %s") % msg)
			raise RuntimeError(_("Gemini error (HTTP %d). %s") % (e.code, msg))
		except urllib.error.URLError as e:
			raise RuntimeError(_("Connection failed: %s") % e.reason)
		block = (data.get("promptFeedback") or {}).get("blockReason")
		if block:
			raise RuntimeError(_("Gemini did not answer because the request was blocked (%s).") % block)
		cands = data.get("candidates") or []
		if not cands:
			raise RuntimeError(_("Gemini returned no answer."))
		cand = cands[0]
		text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
		sources, seen = [], set()
		for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks", []):
			w = ch.get("web") or {}
			if w.get("uri") and w["uri"] not in seen:
				seen.add(w["uri"])
				sources.append((w.get("title") or w["uri"], w["uri"]))
		if not text.strip():
			raise RuntimeError(_("Gemini returned an empty answer. Try again with a different request."))
		return _clean(text), sources
	raise RuntimeError(_("No Gemini model could be used with this API key. %s") % last)


def _inline(data, mime):
	return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}


def _read_file(path):
	size = os.path.getsize(path)
	if size > MAX_FILE:
		raise RuntimeError(_("This file is %.1f MB. The limit is about 14 MB. Use a smaller file or cut it into parts.")
			% (size / 1048576.0))
	with open(path, "rb") as f:
		return f.read()


def _pick_file(title, wildcard):
	dlg = wx.FileDialog(gui.mainFrame, title, wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
	gui.mainFrame.prePopup()
	try:
		return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None
	finally:
		dlg.Destroy()
		gui.mainFrame.postPopup()


def _with_sources(text, sources):
	if not sources:
		return text
	lines = ["%d. %s - %s" % (i, t, u) for i, (t, u) in enumerate(sources, 1)]
	return text + "\n\n" + _("Sources:") + "\n" + "\n".join(lines)


def _need_key(title):
	if gemini_key():
		return True
	show_text(title, NO_KEY)
	return False


def _lang_field():
	return {"key": "lang", "label": _("Answer &language:"), "type": "combo",
		"choices": ["Same language as the content"] + list(LANGUAGES), "default": "Same language as the content"}


def _lang_line(lang):
	return "" if lang.startswith("Same language") else " Write your answer in %s." % lang


# ------------------------------------------------------------------ 1. web search with sources
def tool_gemini_search():
	title = _("AI: Gemini web search with sources")
	if not _need_key(title):
		return
	r = ask_form(title, [
		{"key": "q", "label": _("Your &question (Gemini searches Google for the latest information):"),
			"type": "multiline", "required": True},
		{"key": "style", "label": _("Answer &style:"), "type": "combo",
			"choices": ["Short answer", "Detailed answer", "Step by step", "Latest news and developments"]},
		_lang_field(),
	])
	if not r:
		return
	prompt = "%s\n\nQuestion: %s\n%s" % (
		{"Short answer": "Give a short, direct answer.", "Detailed answer": "Give a detailed answer.",
		"Step by step": "Explain step by step.",
		"Latest news and developments": "Give the latest news and developments with dates."}[r["style"]],
		r["q"], _lang_line(r["lang"]))

	def work():
		text, sources = generate([{"text": prompt}], tools=[{"google_search": {}}])
		return _with_sources(text, sources)
	run_async(work, title)


# ------------------------------------------------------------------ 2. image and screen describer
IMAGE_TASKS = {
	"Describe in detail": "Describe this image in detail for a blind person: the scene, objects, people, colors, "
		"text and layout.",
	"Read all the text (OCR)": "Read all the text in this image exactly as written, in reading order. If there is "
		"no text, say so.",
	"Describe a screen or app window": "This is a screenshot. Describe the window for a blind keyboard user: the "
		"application, the main content, the buttons, links, fields and menus, and how to reach them with the keyboard.",
	"Explain a chart or graph": "Explain this chart or graph: its type, axes, trends, highest and lowest values and "
		"the main message.",
	"Describe the people and emotions": "Describe the people in this image: how many, what they wear, what they do "
		"and their expressions and mood. Do not name anyone.",
	"Identify objects and colors": "List every object you can see with its color and position.",
	"Answer my own question": "",
}
IMAGE_SOURCES = ["Screenshot of my screen", "Image file", "Picture from the clipboard"]
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
	".heic": "image/heic", ".heif": "image/heif"}


def _clipboard_image():
	"""PNG bytes of a picture on the clipboard, or None. Runs on the main thread."""
	if not wx.TheClipboard.Open():
		return None
	try:
		obj = wx.BitmapDataObject()
		if not wx.TheClipboard.GetData(obj):
			return None
		img = obj.GetBitmap().ConvertToImage()
		stream = io.BytesIO()
		img.SaveFile(stream, wx.BITMAP_TYPE_PNG)
		return stream.getvalue()
	except Exception:
		return None
	finally:
		wx.TheClipboard.Close()


def tool_gemini_image():
	title = _("AI: Gemini image and screen describer")
	if not _need_key(title):
		return
	r = ask_form(title, [
		{"key": "src", "label": _("Picture &source:"), "type": "combo", "choices": IMAGE_SOURCES},
		{"key": "task", "label": _("What should Gemini &do:"), "type": "combo", "choices": list(IMAGE_TASKS)},
		{"key": "q", "label": _("Your &question or extra details (needed for Answer my own question):"), "type": "text"},
		{"key": "wait", "label": _("For a screenshot, &wait before capturing (switch to the window you want):"),
			"type": "combo", "choices": ["3 seconds", "5 seconds", "10 seconds", "15 seconds"], "default": "5 seconds"},
		_lang_field(),
	], validate=lambda v: _("Please type your question.") if v["task"] == "Answer my own question" and not v["q"] else None)
	if not r:
		return
	data, mime, seconds = None, "image/png", 0
	if r["src"] == IMAGE_SOURCES[1]:
		path = _pick_file(_("Choose an image"), "Images (*.png;*.jpg;*.jpeg;*.webp;*.heic;*.heif)|"
			"*.png;*.jpg;*.jpeg;*.webp;*.heic;*.heif")
		if not path:
			return
		mime = IMAGE_MIME.get(os.path.splitext(path)[1].lower(), "image/png")
		try:
			data = _read_file(path)
		except Exception as e:
			show_text(title, _("Error: %s") % e)
			return
	elif r["src"] == IMAGE_SOURCES[2]:
		data = _clipboard_image()
		if not data:
			show_text(title, _("The clipboard has no picture. Copy a picture first, for example with Alt+Print Screen."))
			return
	else:
		seconds = int(r["wait"].split()[0])
	instr = IMAGE_TASKS[r["task"]]
	if r["q"]:
		instr = (instr + " " if instr else "") + "User request: " + r["q"]
	instr += _lang_line(r["lang"])

	def work():
		img, m = data, mime
		if img is None:
			wx.CallAfter(speak, _("Capturing your screen in %d seconds. Switch to the window now.") % seconds)
			time.sleep(seconds)
			from .gemini_live import capture_screen_jpeg
			img, m = capture_screen_jpeg(), "image/jpeg"
			wx.CallAfter(speak, _("Screen captured. Please wait."))
		text, _s = generate([_inline(img, m), {"text": instr}])
		return text
	run_async(work, title)


# ------------------------------------------------------------------ 3. document and PDF reader
DOC_TASKS = {
	"Summarize": "Summarize this document clearly.",
	"Key points": "List the most important points as numbered lines.",
	"Explain in simple words": "Explain this document in very simple words for a beginner.",
	"Extract action items and deadlines": "List every task, who is responsible and any deadline.",
	"Read tables and numbers": "Read out all tables and important numbers in this document in a clear, linear way "
		"suitable for a screen reader.",
	"Make study questions": "Write 10 study questions with answers based on this document.",
	"Answer my own question": "",
}
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".html", ".htm", ".xml", ".json", ".py", ".js", ".css", ".log", ".ini", ".rtf"}


def tool_gemini_document():
	title = _("AI: Gemini document and PDF reader")
	if not _need_key(title):
		return
	path = _pick_file(_("Choose a PDF or text file"), "Documents (*.pdf;*.txt;*.md;*.csv;*.html;*.xml;*.json;*.rtf;*.py;*.js)|"
		"*.pdf;*.txt;*.md;*.csv;*.tsv;*.html;*.htm;*.xml;*.json;*.rtf;*.py;*.js;*.css;*.log;*.ini")
	if not path:
		return
	r = ask_form(title, [
		{"key": "task", "label": _("What should Gemini &do:"), "type": "combo", "choices": list(DOC_TASKS)},
		{"key": "q", "label": _("Your &question or extra details (needed for Answer my own question):"), "type": "text"},
		_lang_field(),
	], intro=_("File: %s") % os.path.basename(path),
		validate=lambda v: _("Please type your question.") if v["task"] == "Answer my own question" and not v["q"] else None)
	if not r:
		return
	instr = DOC_TASKS[r["task"]]
	if r["q"]:
		instr = (instr + " " if instr else "") + "User request: " + r["q"]
	instr += _lang_line(r["lang"])
	ext = os.path.splitext(path)[1].lower()

	def work():
		raw = _read_file(path)
		if ext == ".pdf":
			parts = [_inline(raw, "application/pdf"), {"text": instr}]
		elif ext in TEXT_EXT or ext == ".tsv":
			parts = [{"text": "Document (%s):\n\n%s\n\n---\n%s" % (
				os.path.basename(path), raw.decode("utf-8", "replace")[:400000], instr)}]
		else:
			raise RuntimeError(_("This file type is not supported. Use a PDF or a text file."))
		text, _s = generate(parts)
		return text
	run_async(work, title)


# ------------------------------------------------------------------ 4. audio and video transcriber
AV_MIME = {".wav": "audio/wav", ".mp3": "audio/mp3", ".aiff": "audio/aiff", ".aif": "audio/aiff", ".aac": "audio/aac",
	".ogg": "audio/ogg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".mp4": "video/mp4", ".mov": "video/mov",
	".webm": "video/webm", ".mpeg": "video/mpeg", ".mpg": "video/mpg", ".avi": "video/avi"}
AV_TASKS = {
	"Transcribe word for word": "Transcribe all speech word for word. Add paragraphs. Do not add comments.",
	"Transcribe with speakers and timestamps": "Transcribe the speech. Label each speaker (Speaker 1, Speaker 2) and "
		"put a timestamp in minutes and seconds at the start of each turn.",
	"Summarize": "Summarize what is said in a short paragraph, then list the key points.",
	"Meeting minutes": "Write meeting minutes: summary, decisions, action items with owners and deadlines, next steps.",
	"Describe sounds and music": "Describe everything you hear: speech, music, instruments, sounds and mood.",
	"Describe a video (what is shown)": "Describe what happens in this video scene by scene for a blind person, "
		"including any spoken words and on-screen text.",
}


def tool_gemini_audio():
	title = _("AI: Gemini audio and video transcriber")
	if not _need_key(title):
		return
	path = _pick_file(_("Choose an audio or video file (up to about 14 MB)"),
		"Audio and video (*.mp3;*.wav;*.m4a;*.aac;*.ogg;*.flac;*.aiff;*.mp4;*.mov;*.webm;*.mpeg)|"
		"*.mp3;*.wav;*.m4a;*.aac;*.ogg;*.flac;*.aiff;*.aif;*.mp4;*.mov;*.webm;*.mpeg;*.mpg;*.avi")
	if not path:
		return
	ext = os.path.splitext(path)[1].lower()
	mime = AV_MIME.get(ext) or mimetypes.guess_type(path)[0] or "audio/mp3"
	r = ask_form(title, [
		{"key": "task", "label": _("What should Gemini &do:"), "type": "combo", "choices": list(AV_TASKS)},
		_lang_field(),
	], intro=_("File: %s") % os.path.basename(path))
	if not r:
		return
	instr = AV_TASKS[r["task"]] + _lang_line(r["lang"])

	def work():
		text, _s = generate([_inline(_read_file(path), mime), {"text": instr}])
		return text
	run_async(work, title)


# ------------------------------------------------------------------ 5. web page and YouTube summarizer
WEB_TASKS = {
	"Summarize": "Summarize the content clearly in a short paragraph, then list the key points.",
	"Key points": "List the most important points as numbered lines.",
	"Explain in simple words": "Explain the content in very simple words for a beginner.",
	"Read the main article text": "Give the main article text without menus, ads and clutter, in reading order.",
	"Check if it is trustworthy": "Assess how trustworthy this content is: who published it, claims that need "
		"checking, bias and what to verify elsewhere.",
	"Answer my own question": "",
}
YT = re.compile(r"^(https?://)?(www\.|m\.)?(youtube\.com/(watch|shorts|live)|youtu\.be/)", re.I)


def tool_gemini_web():
	title = _("AI: Gemini web page and YouTube summarizer")
	if not _need_key(title):
		return
	r = ask_form(title, [
		{"key": "url", "label": _("&Web page or YouTube link (filled from the clipboard if it is a link):"),
			"type": "text", "required": True, "default": _clip_url()},
		{"key": "task", "label": _("What should Gemini &do:"), "type": "combo", "choices": list(WEB_TASKS)},
		{"key": "q", "label": _("Your &question or extra details (needed for Answer my own question):"), "type": "text"},
		_lang_field(),
	], validate=lambda v: _("Please type your question.") if v["task"] == "Answer my own question" and not v["q"] else None)
	if not r:
		return
	url = r["url"].strip()
	if not re.match(r"^https?://", url, re.I):
		url = "https://" + url
	instr = WEB_TASKS[r["task"]]
	if r["q"]:
		instr = (instr + " " if instr else "") + "User request: " + r["q"]
	instr += _lang_line(r["lang"])

	def work():
		if YT.match(url):
			# A public YouTube video: Gemini watches and listens to it.
			parts = [{"file_data": {"file_uri": url}}, {"text": instr}]
			text, _s = generate(parts)
			return text
		text, sources = generate([{"text": "Open this web page and do the following. %s\n\nPage: %s" % (instr, url)}],
			tools=[{"url_context": {}}])
		return text
	run_async(work, title)


def _clip_url():
	try:
		import api
		t = (api.getClipData() or "").strip()
		return t if re.match(r"^https?://\S+$", t) else ""
	except Exception:
		return ""


GEMINI_TOOLS = [
	(_("AI: Gemini web search with sources"), tool_gemini_search),
	(_("AI: Gemini image and screen describer"), tool_gemini_image),
	(_("AI: Gemini document and PDF reader"), tool_gemini_document),
	(_("AI: Gemini audio and video transcriber"), tool_gemini_audio),
	(_("AI: Gemini web page and YouTube summarizer"), tool_gemini_web),
]
