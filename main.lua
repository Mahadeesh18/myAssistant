require "import"
import "android.widget.*"
import "android.view.*"
import "android.app.*"
import "android.graphics.Typeface"
import "android.graphics.Color"
import "android.os.Build"
import "android.os.Looper"
import "android.os.Handler"
import "android.media.ToneGenerator"
import "android.media.AudioManager"
import "android.content.Context"
import "android.os.Vibrator"
import "android.net.Uri"
import "android.content.Intent"
import "android.text.InputType"
import "android.content.DialogInterface"
import "java.net.URLEncoder"
import "com.androlua.Http"

local updater = nil
pcall(function()
  updater = require "updater"
end)

local context = service or activity or this
local mainHandler = Handler(Looper.getMainLooper())

-- Accessibility Screen Reader Helper
local function speakText(text)
  pcall(function()
    if service then
      service.speak(text)
    elseif activity then
      activity.getAccessibilityManager().announceForAccessibility(text)
    end
  end)
end

-- Persistent Preferences Setup
local preferences = context.getSharedPreferences("AppSettings", Context.MODE_PRIVATE)
local editor = preferences.edit()

-- Global Settings Flags (Loaded from SharedPreferences)
local isToneEnabled = preferences.getBoolean("ToneGeneratorState", true)
local isVibrationEnabled = preferences.getBoolean("VibrationState", true)

-- Helpers for Audio and Vibration
local toneGenerator = nil
pcall(function()
  toneGenerator = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
end)

local function playBeep()
  if isToneEnabled and toneGenerator then
    pcall(function()
      toneGenerator.startTone(ToneGenerator.TONE_PROP_BEEP, 150)
    end)
  end
end

local function triggerVibration()
  if isVibrationEnabled then
    pcall(function()
      local vibrator = context.getSystemService(Context.VIBRATOR_SERVICE)
      if vibrator and vibrator.hasVibrator() then
        if Build.VERSION.SDK_INT >= 26 then
          import "android.os.VibrationEffect"
          vibrator.vibrate(VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE))
        else
          vibrator.vibrate(50)
        end
      end
    end)
  end
end

-- ============================================
-- FEEDBACK DIALOG & MODULE
-- ============================================

local function showSuccessDialog(parentDlg)
  local layout = LinearLayout(context)
  layout.setOrientation(LinearLayout.VERTICAL)
  layout.setPadding(60, 60, 60, 60)
  layout.setGravity(Gravity.CENTER)
  layout.setBackgroundColor(Color.parseColor("#121212"))
  
  local msgText = TextView(context)
  msgText.setText("Feedback sent successfully!")
  msgText.setTextSize(18)
  msgText.setTextColor(Color.parseColor("#4CAF50"))
  msgText.setGravity(Gravity.CENTER)
  msgText.setPadding(0, 0, 0, 40)
  layout.addView(msgText)
  
  local btnOk = Button(context)
  btnOk.setText("OK")
  btnOk.setBackgroundColor(Color.parseColor("#2196F3"))
  btnOk.setTextColor(Color.WHITE)
  local pOk = LinearLayout.LayoutParams(-1, -2)
  btnOk.setLayoutParams(pOk)
  layout.addView(btnOk)
  
  local successDlg = LuaDialog(context)
  successDlg.View = layout
  
  btnOk.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      successDlg.dismiss()
      if parentDlg then parentDlg.dismiss() end
    end
  })
  
  successDlg.show()
end

local function openFeedbackDialog()
  local dlg = nil
  local layout = {
    LinearLayout,
    orientation = "vertical",
    layout_width = "fill",
    layout_height = "fill",
    backgroundColor = Color.parseColor("#121212"),
    padding = "16dp",
    {
      ScrollView,
      layout_width = "fill",
      layout_height = "fill",
      fillViewport = true,
      {
        LinearLayout,
        id = "container",
        orientation = "vertical",
        layout_width = "fill",
        layout_height = "wrap",
      }
    }
  }

  dlg = LuaDialog(context)
  dlg.View = loadlayout(layout)

  -- 1. Title
  local tTitle = TextView(context)
  tTitle.setText("Sent feedback to developer")
  tTitle.setTextSize(20)
  tTitle.setTextColor(Color.WHITE)
  tTitle.setPadding(10, 10, 10, 10)
  container.addView(tTitle)

  -- 2. Project Name Label & Locked EditText
  local tProj = TextView(context)
  tProj.setText("Enter the project name required")
  tProj.setTextColor(Color.WHITE)
  container.addView(tProj)

  local editProject = EditText(context)
  editProject.setText("Computer Shortcuts")
  editProject.setFocusable(false)
  editProject.setClickable(false)
  editProject.setEnabled(false)
  editProject.setTextColor(Color.parseColor("#757575"))
  container.addView(editProject)

  -- 3. Name Label & EditText
  local tName = TextView(context)
  tName.setText("Enter your name required")
  tName.setTextColor(Color.WHITE)
  container.addView(tName)

  local editName = EditText(context)
  editName.setTextColor(Color.WHITE)
  container.addView(editName)

  -- 4. WhatsApp Label & EditText
  local tWa = TextView(context)
  tWa.setText("Enter your WhatsApp number optional")
  tWa.setTextColor(Color.WHITE)
  container.addView(tWa)

  local editWa = EditText(context)
  editWa.setInputType(InputType.TYPE_CLASS_PHONE)
  editWa.setTextColor(Color.WHITE)
  container.addView(editWa)

  -- 5. Feedback Label & EditText
  local tMsg = TextView(context)
  tMsg.setText("Write your feedback message")
  tMsg.setTextColor(Color.WHITE)
  container.addView(tMsg)

  local editMsg = EditText(context)
  editMsg.setTextColor(Color.WHITE)
  container.addView(editMsg)

  -- 6. Cent (Send) Button
  local bCent = Button(context)
  bCent.setText("Cent")
  bCent.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()

      local projectName = tostring(editProject.getText() or "Computer Shortcuts")
      local name = tostring(editName.getText() or "")
      local wa = tostring(editWa.getText() or "")
      local msg = tostring(editMsg.getText() or "")

      if name:match("^%s*$") then
        speakText("Please enter your name")
        return
      end

      if msg:match("^%s*$") then
        speakText("Please enter feedback message")
        return
      end

      if #msg > 5000 then
        speakText("Feedback message exceeds 5000 characters limit")
        return
      end

      local pd = ProgressDialog(context)
      pd.setMessage("Sending please wait...")
      pd.setCancelable(false)
      local pdWindow = pd.getWindow()
      if pdWindow then
        pdWindow.setType(2032)
      end
      pd.show()
      speakText("Sending please wait")

      local BOT_TOKEN = "8801600206:AAGhOLhnkWD-QFTS_-gKgnOGTmQ29bW7434"
      local CHAT_ID = "8254707942"
      local VERCEL_URL = "https://send-feedback-dusky.vercel.app/api"

      local fullText = "New Feedback Received:\nProject: " .. projectName .. "\nName: " .. name
      if wa ~= "" then
        fullText = fullText .. "\nWhatsApp: " .. wa
      end
      fullText = fullText .. "\nFeedback: " .. msg

      local encodedToken = URLEncoder.encode(BOT_TOKEN, "UTF-8")
      local encodedChatId = URLEncoder.encode(CHAT_ID, "UTF-8")
      local encodedText = URLEncoder.encode(fullText, "UTF-8")

      local postData = "bot_token=" .. encodedToken .. "&chat_id=" .. encodedChatId .. "&text=" .. encodedText

      Http.post(VERCEL_URL, postData, function(code, content)
        pcall(function() pd.dismiss() end)
        if tonumber(code) == 200 then
          speakText("Feedback sent successfully")
          editMsg.setText("")
          showSuccessDialog(dlg)
        else
          local errCode = tostring(code or "Unknown")
          speakText("Failed to send. Error code " .. errCode)
          Toast.makeText(context, "Error (" .. errCode .. "): " .. tostring(content), Toast.LENGTH_LONG).show()
        end
      end)
    end
  })
  container.addView(bCent)

  dlg.setOnKeyListener(DialogInterface.OnKeyListener{
    onKey = function(dialog, keyCode, event)
      if keyCode == KeyEvent.KEYCODE_BACK and event.getAction() == KeyEvent.ACTION_UP then
        dlg.dismiss()
        return true
      end
      return false
    end
  })

  dlg.show()
end

local function handleFeedback()
  openFeedbackDialog()
end

-- ============================================
-- HELPER: SAFE WINDOW TYPE RESOLVER
-- ============================================

local function getSafeWindowType()
  if Build.VERSION.SDK_INT >= 26 then
    return WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
  else
    return WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
  end
end

-- ============================================
-- 11 CATEGORIES DATABASE
-- ============================================

local categories = {
  {
    name = "NVDA Navigations",
    keys = {
      {key = "1. NVDA + N", desc = "Open NVDA main menu"},
      {key = "2. NVDA + Q", desc = "Exit NVDA"},
      {key = "3. NVDA + Control + F", desc = "Find text on screen"},
      {key = "4. NVDA + F3", desc = "Find next occurrence"},
      {key = "5. NVDA + Shift + F3", desc = "Find previous occurrence"},
      {key = "6. NVDA + Down Arrow", desc = "Start continuous reading"},
      {key = "7. NVDA + Up Arrow", desc = "Stop continuous reading"},
      {key = "8. NVDA + Tab", desc = "Announce focused control"},
      {key = "9. NVDA + T", desc = "Read active window title"},
      {key = "10. NVDA + Shift + B", desc = "Announce battery status"},
      {key = "11. NVDA + Shift + C", desc = "Read clipboard text"},
      {key = "12. NVDA + Control + S", desc = "Toggle speech mode"},
      {key = "13. NVDA + Space", desc = "Switch Focus/Browse mode"},
      {key = "14. NVDA + F12", desc = "Announce current time"},
      {key = "15. NVDA + F12 twice", desc = "Announce current date"},
      {key = "16. NVDA + Control + Down", desc = "Read status bar"},
      {key = "17. NVDA + End", desc = "Announce cursor position"},
      {key = "18. NVDA + Control + Z", desc = "Open Python Console"},
      {key = "19. NVDA + Control + G", desc = "Open General Settings"},
      {key = "20. NVDA + Control + V", desc = "Open Voice / Synthesizer Settings"},
      {key = "21. NVDA + Control + K", desc = "Open Keyboard Settings"},
      {key = "22. NVDA + Control + M", desc = "Open Mouse Settings"},
      {key = "23. NVDA + Control + O", desc = "Open Object Presentation Settings"},
      {key = "24. NVDA + Control + B", desc = "Open Browse Mode Settings"},
      {key = "25. NVDA + Control + F", desc = "Open Document Formatting Settings"},
      {key = "26. NVDA + Control + D", desc = "Open Dictionary Manager"},
      {key = "27. NVDA + Control + P", desc = "Open Punctuation and Symbol Settings"},
      {key = "28. NVDA + Control + A", desc = "Open Audio Ducking Settings"},
      {key = "29. NVDA + Control + C", desc = "Save Current Configuration"},
      {key = "30. NVDA + Control + R", desc = "Reset Configuration to Saved"}
    }
  },
  {
    name = "JAWS Navigations",
    keys = {
      {key = "1. Insert + J", desc = "Open JAWS main window"},
      {key = "2. Insert + F4", desc = "Exit JAWS"},
      {key = "3. Insert + Down", desc = "Say all / Read document"},
      {key = "4. Insert + Up", desc = "Stop reading"},
      {key = "5. Insert + Tab", desc = "Announce focused control"},
      {key = "6. Insert + T", desc = "Read active window title"},
      {key = "7. Insert + F7", desc = "Open Links List"},
      {key = "8. Insert + F6", desc = "Open Headings List"},
      {key = "9. Insert + F5", desc = "Open Form Fields List"},
      {key = "10. Insert + F12", desc = "Announce current time"},
      {key = "11. Insert + F12 twice", desc = "Announce current date"},
      {key = "12. Insert + 6 (Numpad)", desc = "Open Settings Center"},
      {key = "13. Insert + Shift + V", desc = "Open Quick Settings"},
      {key = "14. Insert + Control + S", desc = "Open Voice Synthesizer Settings"},
      {key = "15. Insert + Control + D", desc = "Open Dictionary Manager"},
      {key = "16. Insert + Control + K", desc = "Open Keyboard Manager"},
      {key = "17. Insert + Control + G", desc = "Open Graphic Labeler"},
      {key = "18. Insert + Control + B", desc = "Open Braille Settings"},
      {key = "19. Insert + V", desc = "Open Adjust JAWS Options"}
    }
  },
  {
    name = "Screen Readers - Reading Commands (NVDA & JAWS)",
    keys = {
      {key = "1. Numpad 2 (NVDA/JAWS)", desc = "Read current character under cursor"},
      {key = "2. Numpad 1 (NVDA/JAWS)", desc = "Move and read previous character"},
      {key = "3. Numpad 3 (NVDA/JAWS)", desc = "Move and read next character"},
      {key = "4. Numpad 2 twice", desc = "Spell current character phonetically"},
      {key = "5. Numpad 5 (NVDA/JAWS)", desc = "Read current word"},
      {key = "6. Numpad 4 (NVDA/JAWS)", desc = "Move and read previous word"},
      {key = "7. Numpad 6 (NVDA/JAWS)", desc = "Move and read next word"},
      {key = "8. Numpad 5 twice", desc = "Spell current word letter-by-letter"},
      {key = "9. Numpad 8 (NVDA/JAWS)", desc = "Read current line"},
      {key = "10. Numpad 7 (NVDA/JAWS)", desc = "Move and read previous line"},
      {key = "11. Numpad 9 (NVDA/JAWS)", desc = "Move and read next line"},
      {key = "12. NVDA + Alt + Up Arrow", desc = "Read current sentence (NVDA)"},
      {key = "13. NVDA + Alt + Down Arrow", desc = "Move and read next sentence"},
      {key = "14. NVDA + Alt + Left Arrow", desc = "Move and read previous sentence"},
      {key = "15. Alt + Numpad 5 (JAWS)", desc = "Read current sentence (JAWS)"},
      {key = "16. NVDA + Control + Up Arrow", desc = "Read current paragraph (NVDA)"},
      {key = "17. NVDA + Control + Down Arrow", desc = "Move and read next paragraph"},
      {key = "18. NVDA + Control + Left Arrow", desc = "Move and read previous paragraph"},
      {key = "19. Control + Numpad 5 (JAWS)", desc = "Read current paragraph (JAWS)"},
      {key = "20. NVDA + Down Arrow / Insert + Down", desc = "Say All - Read continuously"}
    }
  },
  {
    name = "Screen Readers - Selection Commands (NVDA & JAWS)",
    keys = {
      {key = "1. Shift + Right Arrow", desc = "Select next character"},
      {key = "2. Shift + Left Arrow", desc = "Select previous character"},
      {key = "3. Control + Shift + Right Arrow", desc = "Select next word"},
      {key = "4. Control + Shift + Left Arrow", desc = "Select previous word"},
      {key = "5. Shift + Down Arrow", desc = "Select current line down"},
      {key = "6. Shift + Up Arrow", desc = "Select current line up"},
      {key = "7. Shift + Home", desc = "Select text from cursor to start of line"},
      {key = "8. Shift + End", desc = "Select text from cursor to end of line"},
      {key = "9. Control + Shift + Home", desc = "Select from cursor to start of document"},
      {key = "10. Control + Shift + End", desc = "Select from cursor to end of document"},
      {key = "11. Control + Shift + Down Arrow", desc = "Select next paragraph"},
      {key = "12. Control + Shift + Up Arrow", desc = "Select previous paragraph"},
      {key = "13. Control + A", desc = "Select all text and items"},
      {key = "14. NVDA + F10", desc = "Set start point for selective text selection"},
      {key = "15. NVDA + F10 twice", desc = "Select text from start point to current position"}
    }
  },
  {
    name = "Windows Start Menu",
    keys = {
      {key = "1. Windows Key / Ctrl + Esc", desc = "Open or close Start Menu"},
      {key = "2. Type Text", desc = "Search immediately when Start Menu is open"},
      {key = "3. Tab", desc = "Navigate search sections, account, pinned apps"},
      {key = "4. Up / Down / Left / Right Arrow", desc = "Navigate pinned apps and all apps list"},
      {key = "5. Apps Key / Shift + F10", desc = "Open context menu for selected app"},
      {key = "6. Enter", desc = "Launch selected app"},
      {key = "7. Windows + X", desc = "Open Quick Link / Power User menu"},
      {key = "8. Esc", desc = "Close Start Menu"}
    }
  },
  {
    name = "Windows Taskbar",
    keys = {
      {key = "1. Windows + T", desc = "Set focus to Taskbar apps list"},
      {key = "2. Left / Right Arrow", desc = "Navigate open and pinned apps"},
      {key = "3. Up Arrow / Apps Key / Shift + F10", desc = "Open Jump List for selected app"},
      {key = "4. Enter / Space", desc = "Activate or switch to selected app"},
      {key = "5. Windows + [1-9]", desc = "Launch or switch to app at numerical position"},
      {key = "6. Windows + Shift + [1-9]", desc = "Launch new instance of app at position"},
      {key = "7. Windows + Ctrl + [1-9]", desc = "Switch to last active window of app at position"},
      {key = "8. Windows + Alt + [1-9]", desc = "Open Jump List for app at position"},
      {key = "9. Shift + Click on Taskbar Icon", desc = "Open another instance of app"},
      {key = "10. Ctrl + Shift + Click on Taskbar Icon", desc = "Open app as Administrator"}
    }
  },
  {
    name = "Windows Notification Area & System Tray",
    keys = {
      {key = "1. Windows + B", desc = "Set focus to Notification Area / System Tray"},
      {key = "2. Left / Right / Up / Down Arrow", desc = "Navigate between System Tray icons"},
      {key = "3. Enter / Space", desc = "Activate selected icon or expand overflow"},
      {key = "4. Apps Key / Shift + F10", desc = "Open context menu for selected icon"},
      {key = "5. Windows + N", desc = "Open Notification Center and Calendar"},
      {key = "6. Windows + A", desc = "Open Quick Settings"},
      {key = "7. Windows + Shift + V", desc = "Focus directly on Notification toasts"},
      {key = "8. NVDA + F12 / Insert + F12", desc = "Read time and date from System Tray clock"}
    }
  },
  {
    name = "Windows Desktop",
    keys = {
      {key = "1. Windows + D", desc = "Show Desktop / Minimize all"},
      {key = "2. Windows + M", desc = "Minimize all windows"},
      {key = "3. Windows + Shift + M", desc = "Restore minimized windows"},
      {key = "4. Windows + E", desc = "Open File Explorer"},
      {key = "5. Windows + R", desc = "Open Run dialog"},
      {key = "6. Windows + I", desc = "Open Windows Settings"},
      {key = "7. Windows + L", desc = "Lock PC"},
      {key = "8. Windows + S", desc = "Open Search"},
      {key = "9. Alt + Tab", desc = "Switch applications"},
      {key = "10. Alt + F4", desc = "Close window / Shutdown"},
      {key = "11. Control + Shift + Escape", desc = "Open Task Manager"},
      {key = "12. F2", desc = "Rename selected item"},
      {key = "13. Delete", desc = "Move to Recycle Bin"},
      {key = "14. Shift + Delete", desc = "Permanently delete"}
    }
  },
  {
    name = "Microsoft Word",
    keys = {
      {key = "1. Ctrl + N", desc = "New blank document"},
      {key = "2. Ctrl + O", desc = "Open document"},
      {key = "3. Ctrl + S", desc = "Save document"},
      {key = "4. F12", desc = "Save As dialog"},
      {key = "5. Ctrl + P", desc = "Print document"},
      {key = "6. Ctrl + B", desc = "Bold text"},
      {key = "7. Ctrl + I", desc = "Italic text"},
      {key = "8. Ctrl + U", desc = "Underline text"},
      {key = "9. Ctrl + E", desc = "Center align text"},
      {key = "10. Ctrl + L", desc = "Left align text"},
      {key = "11. Ctrl + R", desc = "Right align text"},
      {key = "12. Ctrl + J", desc = "Justify align text"},
      {key = "13. Ctrl + Z", desc = "Undo action"},
      {key = "14. Ctrl + Y", desc = "Redo action"},
      {key = "15. Ctrl + F", desc = "Find text"},
      {key = "16. Ctrl + H", desc = "Find and Replace text"},
      {key = "17. Ctrl + K", desc = "Insert hyperlink"},
      {key = "18. F7", desc = "Run spell and grammar check"}
    }
  },
  {
    name = "Microsoft Excel",
    keys = {
      {key = "1. Ctrl + N", desc = "New workbook"},
      {key = "2. Ctrl + O", desc = "Open workbook"},
      {key = "3. Ctrl + S", desc = "Save workbook"},
      {key = "4. F2", desc = "Edit active cell"},
      {key = "5. F4", desc = "Repeat last action or absolute reference"},
      {key = "6. Ctrl + Arrow Key", desc = "Jump to edge of data region"},
      {key = "7. Ctrl + Space", desc = "Select entire column"},
      {key = "8. Shift + Space", desc = "Select entire row"},
      {key = "9. Alt + =", desc = "Insert AutoSum formula"},
      {key = "10. Ctrl + Shift + L", desc = "Toggle filter on or off"},
      {key = "11. Ctrl + T", desc = "Create table from selection"},
      {key = "12. Ctrl + 1", desc = "Open Format Cells dialog"}
    }
  },
  {
    name = "Microsoft PowerPoint",
    keys = {
      {key = "1. Ctrl + N", desc = "Create new presentation"},
      {key = "2. Ctrl + M", desc = "Insert new slide"},
      {key = "3. Ctrl + D", desc = "Duplicate selected slide"},
      {key = "4. F5", desc = "Start slideshow from beginning"},
      {key = "5. Shift + F5", desc = "Start slideshow from current slide"},
      {key = "6. Esc", desc = "End slideshow"},
      {key = "7. B", desc = "Blackout screen during slideshow"},
      {key = "8. W", desc = "Whiteout screen during slideshow"},
      {key = "9. Ctrl + P", desc = "Change pointer to pen during presentation"},
      {key = "10. Ctrl + A", desc = "Change pointer to arrow during presentation"},
      {key = "11. Ctrl + E", desc = "Change pointer to eraser during presentation"},
      {key = "12. Ctrl + G", desc = "Group selected objects"},
      {key = "13. Ctrl + Shift + G", desc = "Ungroup selected objects"}
    }
  }
}

-- ============================================
-- EXTRA SHORTCUTS FOR ALL CATEGORIES
-- ============================================

local extras = {}

extras["NVDA Navigations"] = {
  {key = "NVDA + Up Arrow", desc = "Read current line"},
  {key = "NVDA + Shift + Up Arrow", desc = "Read current selection"},
  {key = "NVDA + S", desc = "Cycle speech modes (talk, beeps, on-demand, off)"},
  {key = "NVDA + 1", desc = "Toggle Input Help mode"},
  {key = "NVDA + 2", desc = "Toggle speaking typed characters"},
  {key = "NVDA + 3", desc = "Toggle speaking typed words"},
  {key = "NVDA + P", desc = "Cycle punctuation level"},
  {key = "NVDA + F", desc = "Announce text formatting"},
  {key = "NVDA + B", desc = "Read entire foreground window"},
  {key = "NVDA + C", desc = "Read clipboard text"},
  {key = "NVDA + U", desc = "Cycle progress bar output"},
  {key = "NVDA + Shift + D", desc = "Cycle audio ducking mode"},
  {key = "NVDA + F2", desc = "Pass next key directly to the app"},
  {key = "NVDA + F7", desc = "Open Elements List (browse mode)"},
  {key = "NVDA + R", desc = "OCR: recognize content of current object"},
  {key = "Control", desc = "Stop speech"},
  {key = "Shift", desc = "Pause or resume speech"},
  {key = "NVDA + Numpad 8", desc = "Move navigator to parent object"},
  {key = "NVDA + Numpad 2", desc = "Move navigator to first child object"},
  {key = "NVDA + Numpad 4", desc = "Move navigator to previous object"},
  {key = "NVDA + Numpad 6", desc = "Move navigator to next object"},
  {key = "NVDA + Numpad Enter", desc = "Activate current navigator object"},
  {key = "NVDA + Numpad Minus", desc = "Move navigator object to focus"},
  {key = "NVDA + Numpad Slash", desc = "Left mouse click"},
  {key = "NVDA + Numpad Star", desc = "Right mouse click"},
  {key = "H / Shift + H", desc = "Next / previous heading (browse mode)"},
  {key = "K / Shift + K", desc = "Next / previous link (browse mode)"},
  {key = "D / Shift + D", desc = "Next / previous landmark (browse mode)"},
  {key = "F / Shift + F", desc = "Next / previous form field (browse mode)"},
  {key = "B / Shift + B", desc = "Next / previous button (browse mode)"},
  {key = "T / Shift + T", desc = "Next / previous table (browse mode)"},
  {key = "E / Shift + E", desc = "Next / previous edit field (browse mode)"},
  {key = "L / Shift + L", desc = "Next / previous list (browse mode)"},
  {key = "1 to 6", desc = "Jump to next heading of that level (browse mode)"}
}

extras["JAWS Navigations"] = {
  {key = "Insert + F1", desc = "Screen-sensitive help"},
  {key = "Insert + 1", desc = "Toggle Keyboard Help mode"},
  {key = "Insert + Z", desc = "Toggle Virtual Cursor on or off"},
  {key = "Insert + F", desc = "Announce font and formatting"},
  {key = "Insert + Escape", desc = "Refresh screen"},
  {key = "Insert + F11", desc = "Move focus to System Tray"},
  {key = "Insert + F2", desc = "Run JAWS Manager (script and feature list)"},
  {key = "Insert + B", desc = "Read entire active window"},
  {key = "Insert + End", desc = "Read status bar"},
  {key = "Insert + Up Arrow", desc = "Read current line"},
  {key = "Insert + C", desc = "Read Windows clipboard text"},
  {key = "Control", desc = "Stop speech"},
  {key = "H / Shift + H", desc = "Next / previous heading (web)"},
  {key = "K / Shift + K", desc = "Next / previous link (web)"},
  {key = "F / Shift + F", desc = "Next / previous form field (web)"},
  {key = "T / Shift + T", desc = "Next / previous table (web)"},
  {key = "R / Shift + R", desc = "Next / previous region or landmark (web)"},
  {key = "B / Shift + B", desc = "Next / previous button (web)"},
  {key = "Insert + Space, then Z", desc = "Layered keys for JAWS commands"}
}

extras["Screen Readers - Reading Commands (NVDA & JAWS)"] = {
  {key = "Control + Right Arrow", desc = "Move to and read next word"},
  {key = "Control + Left Arrow", desc = "Move to and read previous word"},
  {key = "Control + Down Arrow", desc = "Move to next paragraph"},
  {key = "Control + Up Arrow", desc = "Move to previous paragraph"},
  {key = "Home", desc = "Move to start of line"},
  {key = "End", desc = "Move to end of line"},
  {key = "Control + Home", desc = "Move to start of document"},
  {key = "Control + End", desc = "Move to end of document"},
  {key = "Page Up / Page Down", desc = "Move up or down one page"},
  {key = "NVDA + Up Arrow / Insert + Up Arrow", desc = "Read current line"},
  {key = "NVDA + Shift + Up Arrow", desc = "Read current selection (NVDA)"},
  {key = "NVDA + F", desc = "Announce formatting at cursor (NVDA)"},
  {key = "Insert + F", desc = "Announce formatting at cursor (JAWS)"},
  {key = "NVDA + Numpad Plus", desc = "Say all from review cursor (NVDA)"},
  {key = "Numpad 0 twice", desc = "Toggle Numpad Insert behavior when needed"}
}

extras["Screen Readers - Selection Commands (NVDA & JAWS)"] = {
  {key = "Shift + Page Down", desc = "Select one page down"},
  {key = "Shift + Page Up", desc = "Select one page up"},
  {key = "Control + C", desc = "Copy selection"},
  {key = "Control + X", desc = "Cut selection"},
  {key = "Control + V", desc = "Paste"},
  {key = "Control + Z", desc = "Undo last action"},
  {key = "NVDA + Shift + Up Arrow", desc = "Announce current selection (NVDA)"},
  {key = "Insert + Shift + Down Arrow", desc = "Announce selected text (JAWS)"},
  {key = "F8", desc = "Turn on extend-selection mode (Word)"},
  {key = "F8 twice / three times", desc = "Extend to word / sentence (Word)"},
  {key = "Escape", desc = "Cancel selection mode"},
  {key = "Shift + Control + Space", desc = "Select current item in some lists"}
}

extras["Windows Start Menu"] = {
  {key = "Windows + Q", desc = "Open search"},
  {key = "Control + Shift + Enter", desc = "Run selected app as Administrator"},
  {key = "Windows + X, then U, then U", desc = "Shut down"},
  {key = "Windows + X, then U, then R", desc = "Restart"},
  {key = "Windows + X, then U, then S", desc = "Sleep"},
  {key = "Windows + X, then U, then I", desc = "Sign out"},
  {key = "Home / End", desc = "Jump to first or last item in a list"},
  {key = "Alt + Enter", desc = "Open properties of selected search result"},
  {key = "Windows + Q, then Right Arrow", desc = "Open actions for selected result"}
}

extras["Windows Taskbar"] = {
  {key = "Windows + Shift + T", desc = "Cycle Taskbar apps backward"},
  {key = "Windows + Control + Shift + [1-9]", desc = "Open app at position as Administrator"},
  {key = "Alt + Esc", desc = "Cycle through open windows in order"},
  {key = "Windows + Tab", desc = "Open Task View"},
  {key = "Windows + Home", desc = "Minimize all except the active window"},
  {key = "Windows + Comma", desc = "Peek at the desktop"},
  {key = "Middle Click on Taskbar icon", desc = "Open new instance of the app"},
  {key = "Delete on a Jump List item", desc = "Remove from recent items"},
  {key = "Windows + W", desc = "Open Widgets (Windows 11)"}
}

extras["Windows Notification Area & System Tray"] = {
  {key = "Escape", desc = "Close Notification Center or Quick Settings"},
  {key = "Windows + A, then Tab", desc = "Move between Quick Settings tiles"},
  {key = "Windows + K", desc = "Open Cast / connect to display"},
  {key = "Windows + P", desc = "Choose display projection mode"},
  {key = "Windows + Control + Shift + B", desc = "Wake screen if it is black"},
  {key = "Windows + Control + V", desc = "Open sound output picker (newer Windows 11)"},
  {key = "Windows + Alt + B", desc = "Toggle HDR"},
  {key = "Delete in Notification Center", desc = "Dismiss selected notification"}
}

extras["Windows Desktop"] = {
  {key = "Windows + Tab", desc = "Open Task View"},
  {key = "Windows + Control + D", desc = "Create new virtual desktop"},
  {key = "Windows + Control + Left / Right", desc = "Switch virtual desktop"},
  {key = "Windows + Control + F4", desc = "Close current virtual desktop"},
  {key = "Windows + Arrow Keys", desc = "Snap or maximize / restore window"},
  {key = "Windows + Shift + Left / Right", desc = "Move window to another monitor"},
  {key = "Windows + Shift + S", desc = "Take screenshot (Snipping tool)"},
  {key = "Windows + PrtSc", desc = "Save full screenshot to Pictures"},
  {key = "Windows + V", desc = "Open clipboard history"},
  {key = "Windows + Period", desc = "Open emoji and symbols panel"},
  {key = "Windows + H", desc = "Start voice typing"},
  {key = "Windows + P", desc = "Choose display projection mode"},
  {key = "Windows + U", desc = "Open Accessibility settings"},
  {key = "Windows + Control + Enter", desc = "Toggle Narrator"},
  {key = "Windows + Plus / Minus", desc = "Open Magnifier / zoom in and out"},
  {key = "Windows + Pause", desc = "Open system About page"},
  {key = "Windows + G", desc = "Open Xbox Game Bar"},
  {key = "Windows + Home", desc = "Minimize all except active window"},
  {key = "Control + Alt + Delete", desc = "Security screen"},
  {key = "Control + C / X / V", desc = "Copy / cut / paste"},
  {key = "Control + Z / Y", desc = "Undo / redo"},
  {key = "Control + A", desc = "Select all"},
  {key = "Control + Shift + N", desc = "Create new folder"},
  {key = "Alt + Enter", desc = "Open Properties of selected item"},
  {key = "Alt + Left / Right", desc = "Back / forward in File Explorer"},
  {key = "Alt + Up", desc = "Go up one folder level"},
  {key = "F5", desc = "Refresh"}
}

extras["Microsoft Word"] = {
  {key = "Ctrl + A", desc = "Select all"},
  {key = "Ctrl + C / X / V", desc = "Copy / cut / paste"},
  {key = "Ctrl + Shift + C", desc = "Copy formatting"},
  {key = "Ctrl + Shift + V", desc = "Paste formatting"},
  {key = "Ctrl + Home / End", desc = "Go to start / end of document"},
  {key = "Ctrl + G or F5", desc = "Go To page, line, or heading"},
  {key = "Ctrl + Enter", desc = "Insert page break"},
  {key = "Ctrl + Shift + Enter", desc = "Insert column break"},
  {key = "Ctrl + Alt + 1 / 2 / 3", desc = "Apply Heading 1 / 2 / 3"},
  {key = "Ctrl + Shift + N", desc = "Apply Normal style"},
  {key = "Ctrl + Alt + M", desc = "Insert comment"},
  {key = "Ctrl + Shift + E", desc = "Turn Track Changes on or off"},
  {key = "Ctrl + 1 / 2 / 5", desc = "Single / double / 1.5 line spacing"},
  {key = "Ctrl + Shift + > / <", desc = "Increase / decrease font size"},
  {key = "Ctrl + ] / [", desc = "Increase / decrease font size by 1 pt"},
  {key = "Ctrl + Shift + L", desc = "Apply bullet list"},
  {key = "Ctrl + M / Ctrl + Shift + M", desc = "Increase / decrease indent"},
  {key = "Ctrl + T", desc = "Create hanging indent"},
  {key = "Ctrl + Alt + F", desc = "Insert footnote"},
  {key = "Ctrl + Alt + D", desc = "Insert endnote"},
  {key = "Alt + Shift + D", desc = "Insert current date"},
  {key = "Alt + Shift + T", desc = "Insert current time"},
  {key = "Shift + F3", desc = "Cycle text case (lower, UPPER, Title)"},
  {key = "Ctrl + Shift + A", desc = "Format as all capitals"},
  {key = "Ctrl + D", desc = "Open Font dialog"},
  {key = "Ctrl + Q", desc = "Remove paragraph formatting"},
  {key = "Ctrl + Space", desc = "Clear character formatting"},
  {key = "Ctrl + =", desc = "Subscript"},
  {key = "Ctrl + Shift + =", desc = "Superscript"},
  {key = "Ctrl + Backspace / Delete", desc = "Delete previous / next word"},
  {key = "Alt + Shift + Up / Down", desc = "Move paragraph up or down"},
  {key = "Ctrl + W", desc = "Close document"},
  {key = "Ctrl + F6", desc = "Switch to next open document"},
  {key = "Alt + Q", desc = "Search commands (Tell Me / Search)"},
  {key = "F6", desc = "Move between document, ribbon, and status bar"},
  {key = "Alt", desc = "Show ribbon key tips"}
}

extras["Microsoft Excel"] = {
  {key = "Ctrl + C / X / V", desc = "Copy / cut / paste"},
  {key = "Ctrl + Z / Y", desc = "Undo / redo"},
  {key = "Ctrl + A", desc = "Select all cells or current data region"},
  {key = "Ctrl + Home / End", desc = "Go to A1 / last used cell"},
  {key = "Ctrl + Shift + Arrow Key", desc = "Select to edge of data region"},
  {key = "Ctrl + Page Up / Page Down", desc = "Previous / next worksheet"},
  {key = "Ctrl + G or F5", desc = "Go To cell or range"},
  {key = "Ctrl + F / Ctrl + H", desc = "Find / Find and Replace"},
  {key = "F11", desc = "Create chart on new sheet"},
  {key = "Alt + F1", desc = "Create embedded chart"},
  {key = "Shift + F11", desc = "Insert new worksheet"},
  {key = "Ctrl + ;", desc = "Insert current date"},
  {key = "Ctrl + Shift + ;", desc = "Insert current time"},
  {key = "Alt + Enter", desc = "New line inside a cell"},
  {key = "Ctrl + Enter", desc = "Fill selected cells with entry"},
  {key = "Ctrl + D / Ctrl + R", desc = "Fill down / fill right"},
  {key = "Ctrl + E", desc = "Flash Fill"},
  {key = "Ctrl + Shift + $", desc = "Apply currency format"},
  {key = "Ctrl + Shift + %", desc = "Apply percentage format"},
  {key = "Ctrl + Shift + ~", desc = "Apply General format"},
  {key = "Ctrl + 9 / Ctrl + 0", desc = "Hide selected rows / columns"},
  {key = "Ctrl + Shift + 9 / 0", desc = "Unhide rows / columns"},
  {key = "Ctrl + Minus", desc = "Delete selected cells, rows, or columns"},
  {key = "Ctrl + Shift + Plus", desc = "Insert cells, rows, or columns"},
  {key = "F9", desc = "Recalculate workbook"},
  {key = "Ctrl + `", desc = "Show formulas / show values"},
  {key = "Shift + F2", desc = "Insert or edit note"},
  {key = "Alt + Down Arrow", desc = "Open drop-down list or filter menu"},
  {key = "F12", desc = "Save As"},
  {key = "Ctrl + W", desc = "Close workbook"},
  {key = "Ctrl + Shift + U", desc = "Expand or collapse formula bar"},
  {key = "Ctrl + P", desc = "Print"}
}

extras["Microsoft PowerPoint"] = {
  {key = "Ctrl + S / O / P", desc = "Save / open / print"},
  {key = "F12", desc = "Save As"},
  {key = "Ctrl + C / X / V", desc = "Copy / cut / paste"},
  {key = "Ctrl + Z / Y", desc = "Undo / redo"},
  {key = "Ctrl + B / I / U", desc = "Bold / italic / underline"},
  {key = "Ctrl + F / Ctrl + H", desc = "Find / Replace"},
  {key = "Ctrl + K", desc = "Insert hyperlink"},
  {key = "F7", desc = "Spell check"},
  {key = "F4", desc = "Repeat last action"},
  {key = "Ctrl + Shift + > / <", desc = "Increase / decrease font size"},
  {key = "Ctrl + T", desc = "Open Font dialog"},
  {key = "Ctrl + Shift + Up / Down", desc = "Move selected slide up / down"},
  {key = "Ctrl + Shift + Home / End", desc = "Move slide to start / end"},
  {key = "Ctrl + Alt + M", desc = "Insert comment"},
  {key = "Alt + F5", desc = "Start Presenter View"},
  {key = "N / Enter / Space / Right Arrow", desc = "Next slide or animation (slideshow)"},
  {key = "P / Backspace / Left Arrow", desc = "Previous slide or animation (slideshow)"},
  {key = "Number + Enter", desc = "Go to that slide number (slideshow)"},
  {key = "Ctrl + L", desc = "Change pointer to laser pointer (slideshow)"},
  {key = "Ctrl + H", desc = "Hide pointer and navigation (slideshow)"},
  {key = "E", desc = "Erase on-screen annotations (slideshow)"},
  {key = "S", desc = "Stop or restart automatic slideshow"},
  {key = "Ctrl + W", desc = "Close presentation"},
  {key = "Alt + Q", desc = "Search commands (Tell Me / Search)"},
  {key = "F6", desc = "Move between panes and ribbon"}
}

-- AUTO-MERGE EXTRAS
for _, cat in ipairs(categories) do
  local more = extras[cat.name]
  if more then
    for _, item in ipairs(more) do
      local n = #cat.keys + 1
      table.insert(cat.keys, {
        key = n .. ". " .. item.key,
        desc = item.desc
      })
    end
  end
end

-- ============================================
-- SETTINGS WINDOW
-- ============================================

local function openSettingsWindow()
  local setView = LinearLayout(context)
  setView.setOrientation(LinearLayout.VERTICAL)
  setView.setPadding(25, 25, 25, 25)

  local txtTitle = TextView(context)
  txtTitle.setText("SETTINGS")
  txtTitle.setTextSize(16)
  txtTitle.setGravity(Gravity.CENTER)
  txtTitle.setTextColor(Color.parseColor("#FF6B35"))
  txtTitle.setTypeface(Typeface.DEFAULT_BOLD)
  txtTitle.setPadding(0, 0, 0, 20)
  setView.addView(txtTitle)

  local tempToneState = isToneEnabled
  local tempVibState = isVibrationEnabled

  local switchTone = Switch(context)
  switchTone.setText("Tone Generator Sound")
  switchTone.setChecked(tempToneState)
  switchTone.setPadding(0, 10, 0, 10)
  switchTone.setOnCheckedChangeListener(CompoundButton.OnCheckedChangeListener{
    onCheckedChanged = function(buttonView, isChecked)
      tempToneState = isChecked
    end
  })
  setView.addView(switchTone)

  local switchVib = Switch(context)
  switchVib.setText("Vibration Effect")
  switchVib.setChecked(tempVibState)
  switchVib.setPadding(0, 10, 0, 20)
  switchVib.setOnCheckedChangeListener(CompoundButton.OnCheckedChangeListener{
    onCheckedChanged = function(buttonView, isChecked)
      tempVibState = isChecked
    end
  })
  setView.addView(switchVib)

  local setDl = AlertDialog.Builder(context)
  setDl.setView(setView)
  local setDialog = setDl.create()

  local bottomLayout = LinearLayout(context)
  bottomLayout.setOrientation(LinearLayout.HORIZONTAL)
  bottomLayout.setGravity(Gravity.RIGHT)
  bottomLayout.setPadding(0, 10, 0, 0)

  local btnCancel = Button(context)
  btnCancel.setText("Cancel")
  btnCancel.setTextSize(12)
  btnCancel.setLayoutParams(LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.WRAP_CONTENT,
    LinearLayout.LayoutParams.WRAP_CONTENT
  ))
  btnCancel.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      speakText("Settings cancelled successfully")
      setDialog.dismiss()
    end
  })
  bottomLayout.addView(btnCancel)

  local btnSave = Button(context)
  btnSave.setText("Save")
  btnSave.setTextSize(12)
  local saveParams = LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.WRAP_CONTENT,
    LinearLayout.LayoutParams.WRAP_CONTENT
  )
  saveParams.setMargins(15, 0, 0, 0)
  btnSave.setLayoutParams(saveParams)
  btnSave.setOnClickListener(View.OnClickListener{
    onClick = function()
      isToneEnabled = tempToneState
      isVibrationEnabled = tempVibState
      editor.putBoolean("ToneGeneratorState", isToneEnabled)
      editor.putBoolean("VibrationState", isVibrationEnabled)
      editor.commit()

      playBeep()
      triggerVibration()
      speakText("Settings saved successfully")
      setDialog.dismiss()
    end
  })
  bottomLayout.addView(btnSave)

  setView.addView(bottomLayout)

  setDialog.getWindow().setType(getSafeWindowType())
  setDialog.show()
end

-- ============================================
-- EXPLORE WINDOW
-- ============================================

local function openExploreWindow()
  local expView = LinearLayout(context)
  expView.setOrientation(LinearLayout.VERTICAL)
  expView.setPadding(25, 25, 25, 25)

  local txtTitle = TextView(context)
  txtTitle.setText("EXPLORE")
  txtTitle.setTextSize(16)
  txtTitle.setGravity(Gravity.CENTER)
  txtTitle.setTextColor(Color.parseColor("#FF6B35"))
  txtTitle.setTypeface(Typeface.DEFAULT_BOLD)
  txtTitle.setPadding(0, 0, 0, 20)
  expView.addView(txtTitle)

  local btnSettings = Button(context)
  btnSettings.setText("Settings")
  btnSettings.setTextSize(12)
  btnSettings.setLayoutParams(LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.MATCH_PARENT,
    LinearLayout.LayoutParams.WRAP_CONTENT
  ))
  btnSettings.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      openSettingsWindow()
    end
  })
  expView.addView(btnSettings)

  local btnFeedback = Button(context)
  btnFeedback.setText("Send Feedback to Developer")
  btnFeedback.setTextSize(12)
  btnFeedback.setLayoutParams(LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.MATCH_PARENT,
    LinearLayout.LayoutParams.WRAP_CONTENT
  ))
  btnFeedback.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      handleFeedback()
    end
  })
  expView.addView(btnFeedback)

  local expDl = AlertDialog.Builder(context)
  expDl.setView(expView)
  local expDialog = expDl.create()

  local bottomLayout = LinearLayout(context)
  bottomLayout.setOrientation(LinearLayout.HORIZONTAL)
  bottomLayout.setGravity(Gravity.RIGHT)
  bottomLayout.setPadding(0, 10, 0, 0)

  local btnBack = Button(context)
  btnBack.setText("Back")
  btnBack.setTextSize(12)
  btnBack.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      expDialog.dismiss()
    end
  })
  bottomLayout.addView(btnBack)
  expView.addView(bottomLayout)

  expDialog.getWindow().setType(getSafeWindowType())
  expDialog.show()
end

-- ============================================
-- CATEGORY DETAIL WINDOW
-- ============================================

local function openCategoryWindow(catData)
  local subLayoutView = LinearLayout(context)
  subLayoutView.setOrientation(LinearLayout.VERTICAL)
  subLayoutView.setPadding(25, 25, 25, 25)

  local txtTitle = TextView(context)
  txtTitle.setText(catData.name)
  txtTitle.setTextSize(16)
  txtTitle.setGravity(Gravity.CENTER)
  txtTitle.setTextColor(Color.parseColor("#FF6B35"))
  txtTitle.setTypeface(Typeface.DEFAULT_BOLD)
  txtTitle.setPadding(0, 0, 0, 15)
  subLayoutView.addView(txtTitle)

  local scroll = ScrollView(context)
  local listContainer = LinearLayout(context)
  listContainer.setOrientation(LinearLayout.VERTICAL)
  scroll.addView(listContainer)

  local scrollParams = LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.MATCH_PARENT, 0, 1
  )
  scroll.setLayoutParams(scrollParams)
  subLayoutView.addView(scroll)

  if catData.keys then
    for i, item in ipairs(catData.keys) do
      local txtKey = TextView(context)
      txtKey.setText(item.key)
      txtKey.setTextSize(16)
      txtKey.setTextColor(Color.parseColor("#0000CC"))
      txtKey.setTypeface(Typeface.DEFAULT_BOLD)
      txtKey.setPadding(0, 15, 0, 2)
      listContainer.addView(txtKey)

      local txtDesc = TextView(context)
      txtDesc.setText(item.desc)
      txtDesc.setTextSize(14)
      txtDesc.setTextColor(Color.parseColor("#333333"))
      txtDesc.setPadding(0, 0, 0, 15)
      listContainer.addView(txtDesc)
    end
  end

  local subDl = AlertDialog.Builder(context)
  subDl.setView(subLayoutView)
  local subDialog = subDl.create()

  local bottomLayout = LinearLayout(context)
  bottomLayout.setOrientation(LinearLayout.HORIZONTAL)
  bottomLayout.setGravity(Gravity.RIGHT)
  bottomLayout.setPadding(0, 10, 0, 0)

  local btnBack = Button(context)
  btnBack.setText("Back")
  btnBack.setTextSize(12)
  btnBack.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      subDialog.dismiss()
    end
  })
  bottomLayout.addView(btnBack)
  subLayoutView.addView(bottomLayout)

  subDialog.getWindow().setType(getSafeWindowType())
  subDialog.show()
end

-- ============================================
-- MAIN MENU WINDOW
-- ============================================

local function showMainMenu()
  local mainLayoutView = LinearLayout(context)
  mainLayoutView.setOrientation(LinearLayout.VERTICAL)
  mainLayoutView.setPadding(20, 20, 20, 20)

  local mainTitle = TextView(context)
  mainTitle.setText("COMPUTER SHORTCUTS")
  mainTitle.setTextSize(16)
  mainTitle.setGravity(Gravity.CENTER)
  mainTitle.setTextColor(Color.parseColor("#FF6B35"))
  mainTitle.setTypeface(Typeface.DEFAULT_BOLD)
  mainLayoutView.addView(mainTitle)

  local subTitle = TextView(context)
  subTitle.setText("Created By Mahadeesh")
  subTitle.setTextSize(12)
  subTitle.setGravity(Gravity.CENTER)
  subTitle.setTextColor(Color.parseColor("#008800"))
  subTitle.setPadding(0, 0, 0, 15)
  mainLayoutView.addView(subTitle)

  local scrollMain = ScrollView(context)
  local buttonContainer = LinearLayout(context)
  buttonContainer.setOrientation(LinearLayout.VERTICAL)
  scrollMain.addView(buttonContainer)

  local scrollParams = LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.MATCH_PARENT, 0, 1
  )
  scrollMain.setLayoutParams(scrollParams)
  mainLayoutView.addView(scrollMain)

  local btnExplore = Button(context)
  btnExplore.setText("Explore")
  btnExplore.setTextSize(12)
  btnExplore.setLayoutParams(LinearLayout.LayoutParams(
    LinearLayout.LayoutParams.MATCH_PARENT,
    LinearLayout.LayoutParams.WRAP_CONTENT
  ))
  btnExplore.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      openExploreWindow()
    end
  })
  buttonContainer.addView(btnExplore)

  for i, cat in ipairs(categories) do
    local btn = Button(context)
    btn.setText(cat.name)
    btn.setTextSize(12)
    btn.setLayoutParams(LinearLayout.LayoutParams(
      LinearLayout.LayoutParams.MATCH_PARENT,
      LinearLayout.LayoutParams.WRAP_CONTENT
    ))
    btn.setOnClickListener(View.OnClickListener{
      onClick = function()
        playBeep()
        triggerVibration()
        openCategoryWindow(cat)
      end
    })
    buttonContainer.addView(btn)
  end

  local mainDl = AlertDialog.Builder(context)
  mainDl.setView(mainLayoutView)
  local mainDialog = mainDl.create()

  local bottomLayout = LinearLayout(context)
  bottomLayout.setOrientation(LinearLayout.HORIZONTAL)
  bottomLayout.setGravity(Gravity.RIGHT)
  bottomLayout.setPadding(0, 10, 0, 0)

  local btnExit = Button(context)
  btnExit.setText("Exit")
  btnExit.setTextSize(12)
  btnExit.setOnClickListener(View.OnClickListener{
    onClick = function()
      playBeep()
      triggerVibration()
      speakText("Thank you for using Computer Shortcuts App. Goodbye!")
      
      mainHandler.postDelayed(Runnable{
        run = function()
          mainDialog.dismiss()
        end
      }, 1000)
    end
  })
  bottomLayout.addView(btnExit)
  mainLayoutView.addView(bottomLayout)

  mainDialog.getWindow().setType(getSafeWindowType())
  mainDialog.show()
end

-- 안전한 அப்டேட் செக் / மெயின் மெனு அழைப்பு
if type(updater) == "table" and updater.checkUpdate then
  pcall(function()
    updater.checkUpdate(function()
      showMainMenu()
    end)
  end)
else
  showMainMenu()
end