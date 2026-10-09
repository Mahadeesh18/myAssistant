# -*- coding: UTF-8 -*-
import threading
import wx
import ui
import addonHandler
from gui import guiHelper, settingsDialogs
from . import providers, sounds
from .about import show_about, version, AUTHOR

addonHandler.initTranslation()


class MyAssistantSettingsPanel(settingsDialogs.SettingsPanel):
	title = _("My assistant")

	def makeSettings(self, settingsSizer):
		self._outer = settingsSizer
		h = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		cfg = providers.load()
		self.work = {k: dict(cfg.get(k, {})) for k in ("keys", "models", "urls")}
		self.fetched = {}
		ids = [p["id"] for p in providers.PROVIDERS]
		names = [p["name"] for p in providers.PROVIDERS]
		# First control in the panel: press Tab from the category list to reach it.
		self.providerChoice = h.addLabeledControl(_("AI &provider:"), wx.Choice, choices=names)
		cur = cfg.get("provider", "openai")
		self._cur = ids.index(cur) if cur in ids else 0
		self.providerChoice.SetSelection(self._cur)
		# The API key is hidden (password field) until "Show API key" is checked. Two rows share one value:
		# only one of them is visible at a time, so the label shortcut and the Tab order stay correct.
		self.keyEdit = h.addLabeledControl(_("&API key:"), wx.TextCtrl, style=wx.TE_PASSWORD)
		self.keyPlain = h.addLabeledControl(_("&API key:"), wx.TextCtrl)
		self.showKeyCheck = wx.CheckBox(self, label=_("&Show API key"))
		h.addItem(self.showKeyCheck)
		self.showKeyCheck.SetValue(False)
		self.showKeyCheck.Bind(wx.EVT_CHECKBOX, self.onShowKey)
		# Editable combo box: pick a suggested model or type any model name.
		self.modelCombo = h.addLabeledControl(_("AI &model:"), wx.ComboBox, choices=[], style=wx.CB_DROPDOWN)
		self.urlEdit = h.addLabeledControl(_("&Base URL:"), wx.TextCtrl)
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.refreshBtn = bh.addButton(self, label=_("&Refresh model list"))
		self.testBtn = bh.addButton(self, label=_("&Test AI connection"))
		h.addItem(bh)
		self.soundCheck = wx.CheckBox(self, label=_("Play &sound effects"))
		h.addItem(self.soundCheck)
		self.soundCheck.SetValue(sounds.is_enabled())
		# About section: author name and tutorials.
		h.addItem(wx.StaticText(self, label=_("My assistant version %s. Developers: %s.") % (version(), AUTHOR)))
		ah = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.aboutBtn = ah.addButton(self, label=_("&About and tutorials..."))
		h.addItem(ah)
		self.aboutBtn.Bind(wx.EVT_BUTTON, lambda e: show_about(self))
		self._load(self._cur)
		self._applyKeyVisibility()
		self.providerChoice.Bind(wx.EVT_CHOICE, self.onProvider)
		self.refreshBtn.Bind(wx.EVT_BUTTON, self.onRefresh)
		self.testBtn.Bind(wx.EVT_BUTTON, self.onTest)

	def _getKey(self):
		box = self.keyPlain if self.showKeyCheck.GetValue() else self.keyEdit
		return box.GetValue().strip()

	def _setKey(self, value):
		self.keyEdit.SetValue(value)
		self.keyPlain.SetValue(value)

	def _applyKeyVisibility(self):
		show = self.showKeyCheck.GetValue()
		for ctrl, visible in ((self.keyEdit, not show), (self.keyPlain, show)):
			try:
				self._outer.Show(ctrl.GetContainingSizer(), visible, recursive=True)
			except Exception:
				ctrl.Show(visible)
		try:
			self._outer.Layout()
			self.Layout()
		except Exception:
			pass

	def onShowKey(self, evt):
		show = self.showKeyCheck.GetValue()
		# Copy the text from the field that was visible, so edits are never lost.
		src = self.keyEdit if show else self.keyPlain
		self._setKey(src.GetValue())
		self._applyKeyVisibility()
		ui.message(_("API key shown") if show else _("API key hidden"))

	def _pid(self, idx):
		return providers.PROVIDERS[idx]["id"]

	def _store(self, idx):
		pid = self._pid(idx)
		self.work["keys"][pid] = self._getKey()
		self.work["models"][pid] = self.modelCombo.GetValue().strip()
		self.work["urls"][pid] = self.urlEdit.GetValue().strip()

	def _fill_models(self, pid, selected):
		choices = providers.model_choices(pid, self.fetched.get(pid))
		if selected and selected not in choices:
			choices.insert(0, selected)
		self.modelCombo.Set(choices)
		self.modelCombo.SetValue(selected)

	def _load(self, idx):
		p = providers.PROVIDERS[idx]
		pid = p["id"]
		self._setKey(self.work["keys"].get(pid, ""))
		self.urlEdit.SetValue(self.work["urls"].get(pid) or p["url"])
		self._fill_models(pid, self.work["models"].get(pid) or p["model"])

	def onProvider(self, evt):
		self._store(self._cur)
		self._cur = self.providerChoice.GetSelection()
		self._load(self._cur)

	def _fields(self):
		return {
			"provider": self._pid(self.providerChoice.GetSelection()),
			"key": self._getKey(),
			"model": self.modelCombo.GetValue().strip(),
			"url": self.urlEdit.GetValue().strip(),
		}

	def _alive(self):
		try:
			self.IsShown()
			return True
		except RuntimeError:
			return False

	def onRefresh(self, evt):
		cfg = self._fields()
		ui.message(_("Downloading model list"))
		self.refreshBtn.Disable()

		def work():
			try:
				ids = providers.list_models(cfg)
				err = None
			except Exception as e:
				ids, err = None, str(e)
			wx.CallAfter(done, ids, err)

		def done(ids, err):
			if not self._alive():
				return
			self.refreshBtn.Enable()
			if err:
				wx.MessageBox(_("Could not download the model list: %s") % err, _("My assistant"),
					wx.OK | wx.ICON_ERROR, self)
				return
			pid = cfg["provider"]
			self.fetched[pid] = ids
			if self._pid(self.providerChoice.GetSelection()) == pid:
				self._fill_models(pid, self.modelCombo.GetValue().strip() or cfg["model"])
			wx.MessageBox(_("%d models found. Open the AI model combo box to choose one.") % len(ids),
				_("My assistant"), wx.OK | wx.ICON_INFORMATION, self)
		threading.Thread(target=work, daemon=True).start()

	def onTest(self, evt):
		cfg = self._fields()
		ui.message(_("Testing AI connection"))
		self.testBtn.Disable()

		def work():
			try:
				reply = providers.ask([{"role": "user", "content": "Reply with the single word OK."}], override=cfg)
				ok, msg = True, reply
			except Exception as e:
				ok, msg = False, str(e)
			wx.CallAfter(done, ok, msg)

		def done(ok, msg):
			if not self._alive():
				return
			self.testBtn.Enable()
			name = providers.BY_ID[cfg["provider"]]["name"]
			if ok:
				text = _("Connection successful.\nProvider: %s\nModel: %s\nAI replied: %s") % (
					name, cfg["model"], msg[:200])
				wx.MessageBox(text, _("Test AI connection"), wx.OK | wx.ICON_INFORMATION, self)
			else:
				text = _("Connection failed.\nProvider: %s\nModel: %s\nReason: %s") % (name, cfg["model"], msg)
				wx.MessageBox(text, _("Test AI connection"), wx.OK | wx.ICON_ERROR, self)
		threading.Thread(target=work, daemon=True).start()

	def onSave(self):
		self._store(self._cur)
		cfg = {"provider": self._pid(self.providerChoice.GetSelection())}
		cfg.update(self.work)
		providers.save(cfg)
		sounds.set_enabled(self.soundCheck.GetValue())
