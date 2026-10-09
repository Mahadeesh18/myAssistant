# -*- coding: UTF-8 -*-
"""About dialog with the developer names and step-by-step tutorials."""
import wx
import gui
import api
import addonHandler
from gui import guiHelper
from .common import speak, _finish, _modal

addonHandler.initTranslation()

AUTHOR = "Rithishwaran and Mahadeesh"


def version():
	try:
		return str(addonHandler.getCodeAddon().manifest["version"])
	except Exception:
		return "1.0"


def about_text():
	return _(
		"My assistant, version %s\n"
		"Developers: %s\n\n"
		"My assistant puts more than 153 tools in one NVDA add-on: an AI chat with 26 providers, "
		"more than 50 advanced AI tools for writing, learning, code, analysis and daily life, "
		"an alarm manager, timer, stopwatch, world clock, currency converter, weather, prayer times, "
		"news and many offline calculators.\n\n"
		"Everything is designed for keyboard and screen reader use. Wherever a choice is needed, "
		"a combo box gives you a ready-made list, so you do not have to type and cannot make typing mistakes. "
		"Every result opens in a read-only box that you can read with the arrow keys and copy.\n\n"
		"Thank you for using My assistant. Feedback and ideas are always welcome."
	) % (version(), AUTHOR)


def tutorials():
	return [
		(_("Getting started"), _(
			"1. Press NVDA+Shift+A anywhere to open the My assistant tools list.\n"
			"2. The cursor starts in the Search box. Type part of a tool name, for example weather or alarm; "
			"small spelling mistakes are fine. Press the down arrow to move to the results, or Enter to run the first one.\n"
			"3. Or press Tab to the Category combo box and choose a group of tools, for example "
			"AI: writing and email, Internet tools or Offline tools. Choose All tools to see everything.\n"
			"4. Press Tab to the Tools list, use the up and down arrows to choose a tool, then press Enter.\n"
			"5. Every result opens in a box named Result. Press Copy to copy it or Close (Escape) to go back. "
			"You return to the tools list, so you can run another tool. Press Escape in the tools list, or choose Close, to leave.\n\n"
			"You can also open the tools list from the NVDA menu: Tools, My assistant.")),
		(_("Set up an AI provider and API key"), _(
			"The AI tools need an API key from an AI provider. Some providers have a free plan.\n"
			"1. Open NVDA settings with NVDA+Control+G.\n"
			"2. Choose the My assistant category.\n"
			"3. In the AI provider combo box choose your provider, for example OpenAI, Google Gemini or Groq.\n"
			"4. Type your API key in the API key edit box.\n"
			"5. Press Refresh model list, then open the AI model combo box and choose a model. "
			"You can also type any model name.\n"
			"6. Press Test AI connection. A message tells you if it works.\n"
			"7. Press OK to save.\n\n"
			"Ollama and LM Studio run on your own computer and need no key.")),
		(_("Using the combo boxes"), _(
			"A combo box is a list that you open with Alt+Down arrow, or simply move through with the up and "
			"down arrow keys. You can also type the first letters of an item to jump to it, for example type "
			"P-K-R to reach the Pakistani Rupee.\n\n"
			"Some combo boxes are list-only, so no wrong value can be entered. Others, such as the city "
			"combo box, let you choose from the list or type any name that is not in it.\n\n"
			"If something is missing or invalid, My assistant tells you and keeps the window open so you "
			"can correct it.")),
		(_("Using the AI tools"), _(
			"The AI tools are grouped in the categories that start with AI.\n"
			"1. Copy some text first (Control+C) if the tool works on text. The Your text box is filled "
			"with the clipboard automatically. You can also edit it or type your own.\n"
			"2. Choose options such as the language, tone or length from the combo boxes.\n"
			"3. Press OK. You hear Please wait, then the answer opens in the Result box.\n\n"
			"Tips: give clear details for better answers. If you see an error about an API key, follow the "
			"tutorial Set up an AI provider and API key.")),
		(_("Gemini voices and Live Assistant"), _(
			"Both tools use your Google Gemini API key. Open NVDA settings, My assistant, choose Google Gemini as the AI provider and enter the key. "
			"The tools work even if you later choose another provider for the AI chat.\n\n"
			"AI: Gemini voices text to speech\n"
			"1. Open the tool and type or paste your text in the Enter your text box.\n"
			"2. Press Tab and choose a voice in the Choose your voice combo box.\n"
			"3. Press Tab and press Generate Audio. You hear Please wait, then the audio plays.\n"
			"4. In the result box, press Save Audio, choose a folder and a name, and the audio is saved as a WAV file. "
			"Press Play again to hear it once more.\n\n"
			"AI: Gemini Live Assistant\n"
			"1. Use headphones, so that Gemini does not hear its own voice.\n"
			"2. Open the tool and press Start Conversation. NVDA says Gemini is live. Now simply talk. Gemini answers with its voice, "
			"and the Conversation box keeps a written copy.\n"
			"3. Press Share Screen to let Gemini see your screen, then ask for example What is on my screen? or Read the window. "
			"Pictures of your screen are sent to Google Gemini while sharing is on. Press the same button again to stop sharing.\n"
			"4. Press Stop Conversation, or Close, when you are finished.")),
		(_("Five advanced Gemini tools"), _(
			"These tools use your Google Gemini API key (NVDA settings, My assistant). Open the tools list, choose the category AI: chat, or type Gemini in the Search box.\n\n"
			"AI: Gemini web search with sources\n"
			"Type a question. Gemini searches Google and answers with the latest information, then lists the sources.\n\n"
			"AI: Gemini image and screen describer\n"
			"Choose the source: a screenshot of your screen, an image file or a picture from the clipboard. For a screenshot choose how many seconds to wait, press OK, "
			"then switch to the window you want described. Choose a task such as Describe in detail, Read all the text, Describe a screen or app window, or Answer my own question.\n\n"
			"AI: Gemini document and PDF reader\n"
			"Choose a PDF or text file, then choose Summarize, Key points, Read tables and numbers, or ask your own question about the file.\n\n"
			"AI: Gemini audio and video transcriber\n"
			"Choose an audio or video file up to about 14 MB. Gemini transcribes it, writes it with speakers and timestamps, summarizes it or writes meeting minutes.\n\n"
			"AI: Gemini web page and YouTube summarizer\n"
			"Paste a web page or public YouTube link (a link in the clipboard is filled in for you) and choose to summarize it, get key points or ask a question.\n\n"
			"Files, screenshots and links are sent to Google Gemini. Do not use private files unless you accept that.")),
		(_("Searching for tools"), _(
			"The Search box at the top of the tools list finds tools while you type, even when a word is spelled wrongly. "
			"For example calclator finds Calculator, wether finds Weather, and timzone finds World clock.\n"
			"Related words work too: calendar lists date tools, reminder lists Alarm manager and Timer.\n"
			"After a short pause NVDA tells you how many tools were found and says the best match. "
			"Press the down arrow to go into the results, or Enter to run the first one. Clear the box to see the category again.")),
		(_("Internet tools"), _(
			"Open the tools list and choose the category Internet tools. It holds 44 tools that need no account or key, for example: "
			"Website inspector, Translator with 40 languages, Food product lookup (nutrition, ingredients and allergens), Postal code lookup, "
			"Anime and manga search, NASA Space picture of the day, Password breach checker, Domain registration lookup, Podcast finder, "
			"Web page archiver, Web page analyzer for SEO and accessibility, International Space Station, Trivia quiz, Number and date facts, "
			"Random advice, Random Wikipedia article, TV show search, Recipe finder, Upcoming rocket launches, GitHub lookup, "
			"Software package info, Website status check, DNS lookup, Internet speed test, URL shortener and the RSS feed reader.\n\n"
			"Choose a tool, fill in the combo boxes or edit boxes, press OK, and the result opens in the Result box. "
			"The Internet speed test takes about 20 seconds. The URL shortener copies the short address to the clipboard. "
			"In the Trivia quiz the answers are at the end of the result, so scroll down only when you are ready.")),
		(_("Website inspector"), _(
			"The Website inspector is the most advanced internet tool. It checks one website or domain like a security and performance auditor "
			"and explains every finding in plain words. Open the tools list, type inspector in the Search box and press Enter.\n\n"
			"1. Choose what to check in the combo box: Full inspection, Security headers and cookies, Certificate and encryption, Redirect trace, "
			"Speed and timing breakdown, Email domain security, or DNS records overview.\n"
			"2. Type the web address or just the domain, for example example.com, and press OK. A full inspection takes about 10 to 30 seconds.\n"
			"3. The result starts with a score from 0 to 100 with a letter grade, then a Fix first list that puts the most serious problems at the top. "
			"The details follow. Every line begins with Good, Warning or Problem so you can jump through it quickly.\n\n"
			"What it checks: every redirect and whether plain HTTP moves to HTTPS; the TLS version, cipher, HTTP/2 support and the certificate owner, "
			"issuer, names and days until it expires; security headers such as HSTS, Content-Security-Policy, clickjacking and MIME protection, "
			"Referrer-Policy and Permissions-Policy; cookie flags Secure, HttpOnly and SameSite; software details a server gives away; "
			"timings for DNS, connection, TLS, server wait and download, page size, compression and caching; CDN and hosting clues; "
			"DNS records with DNSSEC and CAA; email protection with SPF, DKIM, DMARC, MX and MTA-STS; and security.txt and robots.txt.\n\n"
			"The tool only reads public information, the same as a browser does. It never logs in, changes or attacks a site. "
			"Scores are an estimate based on common best practice, not a guarantee. The DKIM check tries common selector names, "
			"so a missing result does not always mean DKIM is missing.")),
		(_("Sound effects"), _(
			"Sound effects tell you what is happening without extra speech: a rising sound (enter) when you open the tools list, "
			"a falling sound (exit) when you close it, a soft tick as you move through the list, a sound when a result opens, "
			"a falling sound when it closes, a pulse while a tool is working, a chime on success, a buzz on errors, "
			"a click when you copy, and a beeping alarm.\n"
			"To turn them off or on: NVDA settings, My assistant category, Play sound effects check box. "
			"You can also open the tools list, choose Everyday utilities, then Sound effects settings and preview, "
			"pick a sound in the combo box and press OK to hear it.\n"
			"To use your own sounds, copy files named enter.wav, exit.wav or move.wav into the folder myAssistantSounds "
			"inside your NVDA configuration folder (create it if it is missing). They replace the built-in ones.")),
		(_("Alarm manager"), _(
			"1. Open the tools list and choose Alarm manager.\n"
			"2. Press Add. Choose the hour and the minute from the combo boxes (24 hour clock).\n"
			"3. Optionally type a label.\n"
			"4. In the Choose your sound combo box pick one of 100 sounds. Each sound is numbered, so you can type a number to jump to it. "
			"You hear a preview as you move through the list, or press Preview sound.\n"
			"5. In the Ring for combo box choose how many minutes the alarm rings: 1, 2, 3, 5, 10, 15, 30 or 60.\n"
			"6. Optionally check Repeat every day, then press OK. The alarm keeps working while NVDA is running.\n\n"
			"When the alarm rings a window opens with the Stop button ready. Press Enter or Escape to stop, "
			"or Tab to Snooze for 5 minutes. To remove an alarm, select it in the list and press Delete.")),
		(_("Timer and stopwatch"), _(
			"Timer: choose the hours, minutes and seconds from the three combo boxes, add an optional label, "
			"then press OK. You hear beeps and a spoken message when time is up.\n"
			"Stopwatch: choose Start, Stop, Report elapsed time or Reset from the combo box.")),
		(_("Currency converter and world clock"), _(
			"Currency converter: type the amount, then choose the From and To currencies from the combo boxes. "
			"Type the first letters of a code, such as EUR, to jump to it. Rates are downloaded live.\n"
			"World clock: choose a time zone from the combo box to hear the current time there.")),
		(_("Keyboard shortcuts"), _(
			"NVDA+Shift+A opens the tools list.\n"
			"Other commands, such as the AI chat, battery status and date and time, have no shortcut by "
			"default. To give them one, open NVDA menu, Preferences, Input gestures, then find the "
			"My assistant category.")),
		(_("Troubleshooting"), _(
			"Error: No API key set. Enter a key in NVDA settings, My assistant.\n"
			"Error: HTTP 401 or 403. The key is wrong or has no access to the chosen model.\n"
			"Error: HTTP 429. You reached the provider limit. Wait a little or choose another model.\n"
			"Connection failed. Check your internet connection with the Internet connection check tool.\n"
			"An internet tool returns nothing. The free online service may be busy. Try again later.")),
		(_("About the developers"), _(
			"My assistant was created by %s.\n"
			"The aim is to give NVDA users one accessible place for everyday tools and AI help, "
			"designed so that it is easy and safe to use with a keyboard and a screen reader.") % AUTHOR),
	]


class AboutDialog(wx.Dialog):
	def __init__(self, parent=None):
		super().__init__(parent or gui.mainFrame, title=_("About My assistant"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.items = [(_("About My assistant"), about_text())] + tutorials()
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		self.combo = h.addLabeledControl(_("&Topic:"), wx.ComboBox, choices=[t for t, _b in self.items],
			style=wx.CB_READONLY)
		self.combo.SetSelection(0)
		self.text = h.addLabeledControl(_("&Details:"), wx.TextCtrl, value=self.items[0][1],
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(620, 320))
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		cp = bh.addButton(self, label=_("&Copy"))
		cl = bh.addButton(self, id=wx.ID_CLOSE, label=_("C&lose"))
		self.combo.Bind(wx.EVT_COMBOBOX, self.onTopic)
		cp.Bind(wx.EVT_BUTTON, lambda e: (api.copyToClip(self.text.GetValue()), speak(_("Copied"))))
		cl.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		self.SetEscapeId(wx.ID_CLOSE)
		h.addItem(bh)
		_finish(self, s)
		self.combo.SetFocus()

	def onTopic(self, evt):
		i = self.combo.GetSelection()
		if i >= 0:
			self.text.SetValue(self.items[i][1])


def show_about(parent=None):
	"""parent is given when opened from NVDA settings, which is itself a modal dialog."""
	if parent is not None:
		dlg = AboutDialog(parent)
		try:
			dlg.ShowModal()
		finally:
			dlg.Destroy()
	else:
		_modal(AboutDialog())
