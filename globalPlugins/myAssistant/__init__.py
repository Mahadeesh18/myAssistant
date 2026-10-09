# -*- coding: UTF-8 -*-
"""My assistant - more than 120 tools, 70 AI tools and an AI chat with 26 providers for NVDA. Developers: Rithishwaran and Mahadeesh."""
import wx
import gui
import globalPluginHandler
import scriptHandler
import addonHandler
from gui import settingsDialogs
from .settings import MyAssistantSettingsPanel
from . import tools
from .about import show_about

addonHandler.initTranslation()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("My assistant")

	def __init__(self):
		super().__init__()
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(MyAssistantSettingsPanel)
		tray = gui.mainFrame.sysTrayIcon
		self.menuItem = tray.toolsMenu.Append(wx.ID_ANY, _("My assistant..."))
		tray.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(tools.open_tools), self.menuItem)
		self.aboutItem = tray.toolsMenu.Append(wx.ID_ANY, _("About My assistant..."))
		tray.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(show_about), self.aboutItem)
		tools.start_engine()

	def terminate(self):
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(MyAssistantSettingsPanel)
		except ValueError:
			pass
		try:
			gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self.menuItem)
		except Exception:
			pass
		try:
			gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self.aboutItem)
		except Exception:
			pass
		tools.stop_engine()

	@scriptHandler.script(description=_("Open the My assistant tools list"), gesture="kb:NVDA+shift+a")
	def script_openTools(self, gesture):
		wx.CallAfter(tools.open_tools)

	@scriptHandler.script(description=_("Open About My assistant with the developer names and tutorials"))
	def script_about(self, gesture):
		wx.CallAfter(show_about)

	@scriptHandler.script(description=_("Open the My assistant AI chat"))
	def script_chat(self, gesture):
		wx.CallAfter(tools.tool_chat)

	@scriptHandler.script(description=_("Announce battery status"))
	def script_battery(self, gesture):
		wx.CallAfter(tools.tool_battery)

	@scriptHandler.script(description=_("Announce current date and time"))
	def script_datetime(self, gesture):
		wx.CallAfter(tools.tool_datetime)
