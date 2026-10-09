local updater = {}

local Dialog = luajava.bindClass("android.app.Dialog")
local WindowManager = luajava.bindClass("android.view.WindowManager")
local Build = luajava.bindClass("android.os.Build")

local activeDialog = nil

local function dismissActiveDialog()
  if activeDialog then
    pcall(function() activeDialog.dismiss() end)
    activeDialog = nil
  end
end

local function setScreen(view)
  local ok = pcall(function()
    service.setContentView(view)
  end)
  if not ok then
    pcall(function()
      dismissActiveDialog()
      local dialog = Dialog(service)
      dialog.requestWindowFeature(1)
      dialog.setContentView(view)
      local window = dialog.getWindow()
      if window then
        if Build.VERSION.SDK_INT >= 26 then
          window.setType(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY)
        else
          window.setType(2003)
        end
        window.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT)
      end
      dialog.show()
      activeDialog = dialog
    end)
  end
end

local function closeExtension()
  dismissActiveDialog()
  pcall(function() service.finish() end)
end

local function enableBackKey(view, onBackFn)
  pcall(function()
    view.setFocusableInTouchMode(true)
    view.requestFocus()
    view.setOnKeyListener(luajava.createProxy("android.view.View$OnKeyListener", {
      onKey = function(v, keyCode, event)
        if event.getAction() == 0 and keyCode == 4 then
          if onBackFn then onBackFn() end
          return true
        end
        return false
      end
    }))
  end)
end

updater.config = {
  CURRENT_VERSION = "2026.10.08",
  VERSION_URL = "https://raw.githubusercontent.com/Mahadeesh18/ComputerShortcuts/main/virgin.txt",
  WHATSNEW_URL = "https://raw.githubusercontent.com/Mahadeesh18/ComputerShortcuts/main/what's%20new.txt",
  ZIP_URL = "https://github.com/Mahadeesh18/ComputerShortcuts/archive/refs/heads/main.zip",
   TARGET_PATH = "/storage/self/primary/解说/Plugins/Computer Shortcuts/",
  MAIN_FILE = "main.lua",
  UPDATER_FILE = "updater.lua",
  EXCLUDE_FILES = {
    ["virgin.txt"] = true,
    ["what's new.txt"] = true,
  }
}

local Handler = luajava.bindClass("android.os.Handler")
local Looper = luajava.bindClass("android.os.Looper")
local Toast = luajava.bindClass("android.widget.Toast")
local URL = luajava.bindClass("java.net.URL")
local BufferedReader = luajava.bindClass("java.io.BufferedReader")
local InputStreamReader = luajava.bindClass("java.io.InputStreamReader")
local File = luajava.bindClass("java.io.File")
local FileOutputStream = luajava.bindClass("java.io.FileOutputStream")
local FileInputStream = luajava.bindClass("java.io.FileInputStream")
local ZipInputStream = luajava.bindClass("java.util.zip.ZipInputStream")
local Executors = luajava.bindClass("java.util.concurrent.Executors")
local LinearLayout = luajava.bindClass("android.widget.LinearLayout")
local ScrollView = luajava.bindClass("android.widget.ScrollView")
local TextView = luajava.bindClass("android.widget.TextView")
local Button = luajava.bindClass("android.widget.Button")
local Color = luajava.bindClass("android.graphics.Color")
local View = luajava.bindClass("android.view.View")
local Byte = luajava.bindClass("java.lang.Byte")
local Thread = luajava.bindClass("java.lang.Thread")

local mainHandler = Handler(Looper.getMainLooper())
local executorService = Executors.newCachedThreadPool()

local function makeRunnable(fn)
  return luajava.createProxy("java.lang.Runnable", {
    run = function() fn() end
  })
end

local function makeOnClickListener(fn)
  return luajava.createProxy("android.view.View$OnClickListener", {
    onClick = function(v) fn(v) end
  })
end

local function runOnUI(fn)
  mainHandler.post(makeRunnable(function() fn() end))
end

local function runInBackground(fn)
  executorService.execute(makeRunnable(function() fn() end))
end

local function showToast(msg)
  runOnUI(function()
    Toast.makeText(service, msg, Toast.LENGTH_SHORT).show()
  end)
end

local function cleanHtmlContent(rawHtml)
  if not rawHtml then return nil end
  if not (rawHtml:find("<html") or rawHtml:find("<!DOCTYPE")) then
    return rawHtml
  end
  local extractedLines = {}
  for rawLinesMatch in rawHtml:gmatch('"rawLines":%s*%[(.-)%]') do
    for str in rawLinesMatch:gmatch('"([^"]-)"') do
      table.insert(extractedLines, str)
    end
  end
  if #extractedLines > 0 then
    return table.concat(extractedLines, "\n")
  end
  for codeLine in rawHtml:gmatch('class="[^"]*blob%-code[^"]*"[^>]*>(.-)</td>') do
    local cleanLine = codeLine:gsub("<[^>]+>", "")
    table.insert(extractedLines, cleanLine)
  end
  if #extractedLines > 0 then
    return table.concat(extractedLines, "\n")
  end
  return rawHtml:gsub("<script.-</script>", ""):gsub("<style.-</style>", ""):gsub("<[^>]+>", "")
end

local function fetchUrlText(urlString)
  local currentUrl = urlString
  pcall(function() math.randomseed(os.time() + math.floor(os.clock() * 1000)) end)
  local cacheBuster = "cb=" .. tostring(os.time()) .. "_" .. tostring(math.random(100000, 999999))
  if not currentUrl:find("%?") then
    currentUrl = currentUrl .. "?" .. cacheBuster
  else
    currentUrl = currentUrl .. "&" .. cacheBuster
  end
  local lastErr = "Unknown connection error"
  for i = 1, 5 do
    local conn
    local success, res = pcall(function()
      local url = URL(currentUrl)
      conn = url.openConnection()
      conn.setRequestMethod("GET")
      conn.setConnectTimeout(30000)
      conn.setReadTimeout(30000)
      conn.setInstanceFollowRedirects(true)
      conn.setUseCaches(false)
      pcall(function() conn.setDefaultUseCaches(false) end)
      conn.setRequestProperty("User-Agent", "Mozilla/5.0")
      conn.setRequestProperty("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
      conn.setRequestProperty("Pragma", "no-cache")
      conn.setRequestProperty("Expires", "0")
      local code = conn.getResponseCode()
      if code == 301 or code == 302 or code == 303 or code == 307 or code == 308 then
        local loc = conn.getHeaderField("Location")
        conn.disconnect()
        if loc then
          currentUrl = loc
          return "REDIRECT"
        end
        return nil
      end
      if code ~= 200 then return nil end
      local reader = BufferedReader(InputStreamReader(conn.getInputStream(), "UTF-8"))
      local lines = {}
      local line = reader.readLine()
      while line ~= nil do
        table.insert(lines, line)
        line = reader.readLine()
      end
      reader.close()
      return table.concat(lines, "\n")
    end)
    if conn then pcall(function() conn.disconnect() end) end
    if success then
      if res ~= "REDIRECT" and res then
        return cleanHtmlContent(res)
      end
    else
      lastErr = tostring(res)
    end
  end
  return nil, lastErr
end

local function downloadFile(urlString, destFile)
  local currentUrl = urlString
  pcall(function() math.randomseed(os.time() + math.floor(os.clock() * 1000)) end)
  local cacheBuster = "cb=" .. tostring(os.time()) .. "_" .. tostring(math.random(100000, 999999))
  if not currentUrl:find("%?") then
    currentUrl = currentUrl .. "?" .. cacheBuster
  else
    currentUrl = currentUrl .. "&" .. cacheBuster
  end
  for i = 1, 5 do
    local conn
    local success, res = pcall(function()
      local url = URL(currentUrl)
      conn = url.openConnection()
      conn.setRequestMethod("GET")
      conn.setConnectTimeout(15000)
      conn.setReadTimeout(15000)
      conn.setInstanceFollowRedirects(true)
      conn.setUseCaches(false)
      pcall(function() conn.setDefaultUseCaches(false) end)
      local code = conn.getResponseCode()
      if code == 301 or code == 302 or code == 303 or code == 307 or code == 308 then
        local loc = conn.getHeaderField("Location")
        conn.disconnect()
        if loc then
          currentUrl = loc
          return "REDIRECT"
        end
        return false
      end
      if code ~= 200 then return false end
      local input = conn.getInputStream()
      local output = FileOutputStream(destFile)
      local buffer = luajava.newArray(Byte.TYPE, 4096)
      local bytesRead = input.read(buffer)
      while bytesRead ~= -1 do
        output.write(buffer, 0, bytesRead)
        bytesRead = input.read(buffer)
      end
      output.close()
      input.close()
      return true
    end)
    if conn then pcall(function() conn.disconnect() end) end
    if success then
      if res ~= "REDIRECT" then
        return res == true
      end
    else
      return false
    end
  end
  return false
end

local function deleteDirectoryContents(dir)
  if not dir or not dir.exists() then return end
  local files = dir.listFiles()
  if files ~= nil then
    for i = 0, #files - 1 do
      local f = files[i]
      if f ~= nil then
        if f.isDirectory() then
          deleteDirectoryContents(f)
          f.delete()
        else
          f.delete()
        end
      end
    end
  end
end

local function extractZipExcluding(zipFile, destDir, excludeMap)
  local fis = FileInputStream(zipFile)
  local zis = ZipInputStream(fis)
  local entry = zis.getNextEntry()
  
  while entry ~= nil do
    local entryName = entry.getName()
    local slashIdx = entryName:find("/")
    if slashIdx then
      local relativePath = entryName:sub(slashIdx + 1)
      if relativePath ~= "" then
        local filename = relativePath:match("^.+/(.+)$") or relativePath
        local isExcluded = excludeMap[filename:lower()]
        local outFile = File(destDir, relativePath)
        
        if entry.isDirectory() then
          outFile.mkdirs()
        else
          if not isExcluded then
            local parent = outFile.getParentFile()
            if parent and not parent.exists() then
              parent.mkdirs()
            end
            local fos = FileOutputStream(outFile)
            local buf = luajava.newArray(Byte.TYPE, 4096)
            local len = zis.read(buf)
            while len > 0 do
              fos.write(buf, 0, len)
              len = zis.read(buf)
            end
            fos.close()
          end
        end
      end
    end
    zis.closeEntry()
    entry = zis.getNextEntry()
  end
  zis.close()
  fis.close()
end

local function updateVersionInFile(newVersion)
  updater.config.CURRENT_VERSION = newVersion
  local filePath = updater.config.TARGET_PATH .. updater.config.UPDATER_FILE
  local rf = io.open(filePath, "r")
  if rf then
    local content = rf:read("*a")
    rf:close()
    if content then
      local updatedContent = content:gsub('CURRENT_VERSION%s*=%s*["\']([^"\']+)["\']', 'CURRENT_VERSION = "' .. newVersion .. '"')
      local wf = io.open(filePath, "w")
      if wf then
        wf:write(updatedContent)
        wf:flush()
        wf:close()
      end
    end
  end
end

function updater.showLoadingDialog(msg)
  local rootLayout = LinearLayout(service)
  rootLayout.setOrientation(LinearLayout.VERTICAL)
  rootLayout.setBackgroundColor(Color.BLACK)

  local layoutInner = LinearLayout(service)
  layoutInner.setOrientation(LinearLayout.VERTICAL)
  layoutInner.setPadding(20, 20, 20, 20)

  local tvMsg = TextView(service)
  tvMsg.setText(msg or "Checking for update...")
  tvMsg.setTextSize(18)
  tvMsg.setTextColor(Color.WHITE)
  tvMsg.setPadding(0, 20, 0, 20)
  layoutInner.addView(tvMsg)

  rootLayout.addView(layoutInner)

  enableBackKey(rootLayout, function() end)

  setScreen(rootLayout)
end

function updater.showNoUpdateDialog(onDismiss)
  local rootLayout = LinearLayout(service)
  rootLayout.setOrientation(LinearLayout.VERTICAL)
  rootLayout.setBackgroundColor(Color.BLACK)

  local layoutInner = LinearLayout(service)
  layoutInner.setOrientation(LinearLayout.VERTICAL)
  layoutInner.setPadding(20, 20, 20, 20)

  local tvMsg = TextView(service)
  tvMsg.setText("No updates available")
  tvMsg.setTextSize(18)
  tvMsg.setTextColor(Color.GREEN)
  tvMsg.setPadding(0, 20, 0, 20)
  layoutInner.addView(tvMsg)

  rootLayout.addView(layoutInner)

  enableBackKey(rootLayout, function() end)

  setScreen(rootLayout)

  mainHandler.postDelayed(makeRunnable(function()
    dismissActiveDialog()
    if onDismiss then onDismiss() end
  end), 1000)
end

function updater.showErrorDialog(msg, onDismiss)
  local rootLayout = LinearLayout(service)
  rootLayout.setOrientation(LinearLayout.VERTICAL)
  rootLayout.setBackgroundColor(Color.BLACK)

  local scrollLayout = ScrollView(service)
  local layoutInner = LinearLayout(service)
  layoutInner.setOrientation(LinearLayout.VERTICAL)
  layoutInner.setPadding(20, 20, 20, 20)

  local tvMsg = TextView(service)
  tvMsg.setText("Error Checking Update!\n\nDetails:\n" .. tostring(msg) .. "\n\nLocal Version: " .. tostring(updater.config.CURRENT_VERSION))
  tvMsg.setTextSize(18)
  tvMsg.setTextColor(Color.RED)
  tvMsg.setPadding(0, 20, 0, 20)
  layoutInner.addView(tvMsg)

  local btnClose = Button(service)
  btnClose.setText("Close")
  btnClose.setOnClickListener(makeOnClickListener(function()
    dismissActiveDialog()
    if onDismiss then onDismiss() end
  end))
  layoutInner.addView(btnClose)

  scrollLayout.addView(layoutInner)
  rootLayout.addView(scrollLayout)

  enableBackKey(rootLayout, function()
    dismissActiveDialog()
    if onDismiss then onDismiss() end
  end)
  setScreen(rootLayout)
end

function updater.showUpdateDialog(onlineVersion, whatsNewText, onDismiss)
  local rootLayout = LinearLayout(service)
  rootLayout.setOrientation(LinearLayout.VERTICAL)
  rootLayout.setBackgroundColor(Color.BLACK)

  local isDownloading = false

  enableBackKey(rootLayout, function()
    if isDownloading then
      Toast.makeText(service, "Downloading in progress...", Toast.LENGTH_SHORT).show()
    else
      dismissActiveDialog()
      if onDismiss then onDismiss() end
    end
  end)

  local scrollLayout = ScrollView(service)
  local layoutInner = LinearLayout(service)
  layoutInner.setOrientation(LinearLayout.VERTICAL)
  layoutInner.setPadding(20, 20, 20, 20)

  local btnDismiss = Button(service)
  btnDismiss.setText("Dismiss Update Dialog")
  btnDismiss.setOnClickListener(makeOnClickListener(function()
    if not isDownloading then
      dismissActiveDialog()
      if onDismiss then onDismiss() end
    end
  end))
  layoutInner.addView(btnDismiss)

  local titleView = TextView(service)
  titleView.setText("Update Available: v" .. onlineVersion)
  titleView.setTextSize(20)
  titleView.setTextColor(Color.GREEN)
  titleView.setPadding(0, 10, 0, 10)
  layoutInner.addView(titleView)

  local headerWhatsNew = TextView(service)
  headerWhatsNew.setText("What's New:")
  headerWhatsNew.setTextSize(18)
  headerWhatsNew.setTextColor(Color.YELLOW)
  headerWhatsNew.setPadding(0, 10, 0, 10)
  layoutInner.addView(headerWhatsNew)

  if whatsNewText and whatsNewText ~= "" then
    for line in whatsNewText:gmatch("[^\r\n]+") do
      local lineView = TextView(service)
      lineView.setText(line)
      lineView.setTextSize(16)
      lineView.setTextColor(Color.WHITE)
      lineView.setPadding(0, 5, 0, 5)
      layoutInner.addView(lineView)
    end
  else
    local lineView = TextView(service)
    lineView.setText("No details provided.")
    lineView.setTextSize(16)
    lineView.setTextColor(Color.WHITE)
    layoutInner.addView(lineView)
  end

  local btnUpdate = Button(service)
  btnUpdate.setText("Update Now")

  local btnCancel = Button(service)
  btnCancel.setText("Cancel")
  btnCancel.setVisibility(View.GONE)

  btnUpdate.setOnClickListener(makeOnClickListener(function()
    if isDownloading then return end
    isDownloading = true
    btnDismiss.setEnabled(false)
    btnUpdate.setText("Downloading...")
    btnUpdate.setEnabled(false)
    btnCancel.setVisibility(View.VISIBLE)

    runInBackground(function()
      local tempZip = File(service.getCacheDir(), "update_temp.zip")
      local success = downloadFile(updater.config.ZIP_URL, tempZip)
      
      if not success then
        isDownloading = false
        runOnUI(function()
          btnDismiss.setEnabled(true)
          btnUpdate.setText("Update Now")
          btnUpdate.setEnabled(true)
          btnCancel.setVisibility(View.GONE)
          Toast.makeText(service, "Download failed! Try again.", Toast.LENGTH_SHORT).show()
        end)
        return
      end

      local destDir = File(updater.config.TARGET_PATH)
      deleteDirectoryContents(destDir)
      
      pcall(function()
        extractZipExcluding(tempZip, destDir, updater.config.EXCLUDE_FILES)
      end)
      
      if tempZip.exists() then tempZip.delete() end

      updateVersionInFile(onlineVersion)

      runOnUI(function()
        updater.showRestartDialog()
      end)
    end)
  end))

  btnCancel.setOnClickListener(makeOnClickListener(function()
    if isDownloading then
      isDownloading = false
      btnDismiss.setEnabled(true)
      btnUpdate.setText("Update Now")
      btnUpdate.setEnabled(true)
      btnCancel.setVisibility(View.GONE)
      Toast.makeText(service, "Update canceled.", Toast.LENGTH_SHORT).show()
    end
  end))

  layoutInner.addView(btnUpdate)
  layoutInner.addView(btnCancel)

  scrollLayout.addView(layoutInner)
  rootLayout.addView(scrollLayout)
  setScreen(rootLayout)
end

function updater.showRestartDialog()
  local rootLayout = LinearLayout(service)
  rootLayout.setOrientation(LinearLayout.VERTICAL)
  rootLayout.setBackgroundColor(Color.BLACK)

  local scrollLayout = ScrollView(service)
  local layoutInner = LinearLayout(service)
  layoutInner.setOrientation(LinearLayout.VERTICAL)
  layoutInner.setPadding(20, 20, 20, 20)

  local tvMsg = TextView(service)
  tvMsg.setText("Update completed successfully! Please restart the extension.")
  tvMsg.setTextSize(18)
  tvMsg.setTextColor(Color.GREEN)
  tvMsg.setPadding(0, 20, 0, 20)
  layoutInner.addView(tvMsg)

  local btnRestart = Button(service)
  btnRestart.setText("Restart Extension")
  btnRestart.setOnClickListener(makeOnClickListener(function()
    for k, _ in pairs(package.loaded) do
      if k ~= "string" and k ~= "table" and k ~= "math" and k ~= "coroutine" and k ~= "package" and k ~= "io" and k ~= "os" and k ~= "debug" and k ~= "luajava" then
        package.loaded[k] = nil
      end
    end
    pcall(function() closeExtension() end)
    mainHandler.postDelayed(makeRunnable(function()
      pcall(function()
        dofile(updater.config.TARGET_PATH .. updater.config.MAIN_FILE)
      end)
    end), 300)
  end))
  layoutInner.addView(btnRestart)

  scrollLayout.addView(layoutInner)
  rootLayout.addView(scrollLayout)

  enableBackKey(rootLayout, function()
    pcall(function() closeExtension() end)
  end)

  setScreen(rootLayout)
end

function updater.checkUpdate(onFinished)
  local startTime = os.time()
  runOnUI(function()
    updater.showLoadingDialog("Checking for update...")
  end)
  
  runInBackground(function()
    local onlineVersionRaw, errDetail = fetchUrlText(updater.config.VERSION_URL)
    
    local elapsedTime = os.time() - startTime
    if elapsedTime < 1 then
      pcall(function() Thread.sleep(1000) end)
    end

    if not onlineVersionRaw then
      runOnUI(function()
        dismissActiveDialog()
        showToast("Connection error")
        if onFinished then onFinished() end
      end)
      return
    end

    local onlineVersion = onlineVersionRaw:match("^%s*(.-)%s*$")
    
    if onlineVersion == updater.config.CURRENT_VERSION then
      runOnUI(function()
        dismissActiveDialog()
        updater.showNoUpdateDialog(onFinished)
      end)
    else
      local whatsNewText = fetchUrlText(updater.config.WHATSNEW_URL) or ""
      runOnUI(function()
        dismissActiveDialog()
        updater.showUpdateDialog(onlineVersion, whatsNewText, onFinished)
      end)
    end
  end)
end

return updater