# -*- coding: UTF-8 -*-
"""AI provider registry, config storage and chat requests (stdlib only)."""
import json
import os
import urllib.request
import urllib.error
import globalVars


def _p(pid, name, url, model, kind="openai", needs_key=True):
	return {"id": pid, "name": name, "url": url, "model": model, "kind": kind, "needs_key": needs_key}


PROVIDERS = [
	_p("openai", "OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
	_p("anthropic", "Anthropic (Claude)", "https://api.anthropic.com/v1", "claude-haiku-4-5-20251001", "anthropic"),
	_p("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash"),
	_p("mistral", "Mistral AI", "https://api.mistral.ai/v1", "mistral-small-latest"),
	_p("groq", "Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
	_p("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
	_p("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
	_p("xai", "xAI (Grok)", "https://api.x.ai/v1", "grok-3-mini"),
	_p("together", "Together AI", "https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
	_p("perplexity", "Perplexity", "https://api.perplexity.ai", "sonar"),
	_p("cohere", "Cohere", "https://api.cohere.ai/compatibility/v1", "command-a-03-2025"),
	_p("fireworks", "Fireworks AI", "https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct"),
	_p("cerebras", "Cerebras", "https://api.cerebras.ai/v1", "llama-3.3-70b"),
	_p("sambanova", "SambaNova", "https://api.sambanova.ai/v1", "Meta-Llama-3.3-70B-Instruct"),
	_p("nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct"),
	_p("huggingface", "Hugging Face", "https://router.huggingface.co/v1", "meta-llama/Llama-3.3-70B-Instruct"),
	_p("moonshot", "Moonshot (Kimi)", "https://api.moonshot.ai/v1", "moonshot-v1-8k"),
	_p("zhipu", "Zhipu AI (GLM)", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
	_p("qwen", "Alibaba Qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
	_p("github", "GitHub Models", "https://models.inference.ai.azure.com", "gpt-4o-mini"),
	_p("hyperbolic", "Hyperbolic", "https://api.hyperbolic.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct"),
	_p("deepinfra", "DeepInfra", "https://api.deepinfra.com/v1/openai", "meta-llama/Llama-3.3-70B-Instruct"),
	_p("novita", "Novita AI", "https://api.novita.ai/v3/openai", "meta-llama/llama-3.3-70b-instruct"),
	_p("ollama", "Ollama (local, no key)", "http://localhost:11434/v1", "llama3.2", needs_key=False),
	_p("lmstudio", "LM Studio (local, no key)", "http://localhost:1234/v1", "local-model", needs_key=False),
	_p("custom", "Custom OpenAI-compatible", "", "", needs_key=False),
]
BY_ID = {p["id"]: p for p in PROVIDERS}

# Suggested models shown in the settings combo box. The box is editable, and
# "Refresh model list" in settings downloads the live list from the provider.
MODELS = {
	"openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "gpt-5", "gpt-5-mini"],
	"anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-sonnet-5-5", "claude-opus-5-5"],
	# Every Gemini model that can chat, newest first (checked against Google's model list, September 2026).
	# "Refresh model list" in settings downloads the full live list from Google, including image, speech and embedding models.
	"gemini": ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
		"gemini-3.1-pro-preview", "gemini-3.1-flash-lite", "gemini-3-flash-preview",
		"gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"],
	"mistral": ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest", "open-mistral-nemo", "codestral-latest"],
	"groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
	"openrouter": ["openai/gpt-4o-mini", "google/gemini-2.5-flash", "deepseek/deepseek-chat",
		"meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.3-70b-instruct:free"],
	"deepseek": ["deepseek-chat", "deepseek-reasoner"],
	"xai": ["grok-3-mini", "grok-3", "grok-4"],
	"together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct-Turbo"],
	"perplexity": ["sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro"],
	"cohere": ["command-a-03-2025", "command-r-plus-08-2024", "command-r-08-2024", "command-r7b-12-2024"],
	"ollama": ["llama3.2", "llama3.1", "qwen2.5", "mistral", "gemma2", "phi3"],
}


def model_choices(pid, extra=None):
	"""Default model first, then the suggestions, then anything extra (fetched or typed)."""
	out = []
	for m in [BY_ID[pid]["model"]] + MODELS.get(pid, []) + list(extra or []):
		if m and m not in out:
			out.append(m)
	return out
CONFIG_FILE = os.path.join(globalVars.appArgs.configPath, "myAssistant.json")


def load():
	try:
		with open(CONFIG_FILE, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {}


def save(cfg):
	with open(CONFIG_FILE, "w", encoding="utf-8") as f:
		json.dump(cfg, f, indent=1)


def current():
	c = load()
	pid = c.get("provider", "openai")
	if pid not in BY_ID:
		pid = "openai"
	p = BY_ID[pid]
	return {
		"provider": pid,
		"key": c.get("keys", {}).get(pid, "").strip(),
		"model": c.get("models", {}).get(pid, "").strip() or p["model"],
		"url": c.get("urls", {}).get(pid, "").strip() or p["url"],
	}


def current_name():
	return BY_ID[current()["provider"]]["name"]


def _post(url, headers, payload):
	headers = dict(headers)
	headers["Content-Type"] = "application/json"
	headers["User-Agent"] = "NVDA-MyAssistant/1.1"
	req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
	try:
		with urllib.request.urlopen(req, timeout=90) as r:
			return json.loads(r.read().decode("utf-8"))
	except urllib.error.HTTPError as e:
		try:
			body = e.read().decode("utf-8", "replace")[:400]
		except Exception:
			body = ""
		raise RuntimeError("HTTP %s. %s" % (e.code, body))
	except urllib.error.URLError as e:
		raise RuntimeError("Connection failed: %s" % e.reason)


def ask(messages, system=None, override=None):
	"""messages: list of {"role": "user"|"assistant", "content": str}. Returns reply text."""
	cfg = override or current()
	p = BY_ID[cfg["provider"]]
	key, model, base = cfg["key"], cfg["model"], cfg["url"].rstrip("/")
	if p["needs_key"] and not key:
		raise RuntimeError("No API key set for %s. Open NVDA settings, My assistant, and enter it." % p["name"])
	if not base or not model:
		raise RuntimeError("Base URL and model are required for this provider (NVDA settings, My assistant).")
	if p["kind"] == "anthropic":
		payload = {"model": model, "max_tokens": 1500, "messages": messages}
		if system:
			payload["system"] = system
		data = _post(base + "/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, payload)
		return "".join(b.get("text", "") for b in data.get("content", [])).strip() or "(empty reply)"
	msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
	headers = {"Authorization": "Bearer " + key} if key else {}
	data = _post(base + "/chat/completions", headers, {"model": model, "messages": msgs})
	try:
		return (data["choices"][0]["message"]["content"] or "").strip() or "(empty reply)"
	except (KeyError, IndexError, TypeError):
		raise RuntimeError("Unexpected reply: %s" % str(data)[:300])


def list_models(cfg):
	"""Download the model ids offered by the provider in cfg. Raises RuntimeError on failure."""
	p = BY_ID[cfg["provider"]]
	key, base = cfg["key"], cfg["url"].rstrip("/")
	if p["needs_key"] and not key:
		raise RuntimeError("No API key set for %s." % p["name"])
	if not base:
		raise RuntimeError("Base URL is required.")
	if p["kind"] == "anthropic":
		headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
	else:
		headers = {"Authorization": "Bearer " + key} if key else {}
	headers["User-Agent"] = "NVDA-MyAssistant/1.1"
	req = urllib.request.Request(base + "/models?limit=200" if p["kind"] == "anthropic" else base + "/models",
		headers=headers)
	try:
		with urllib.request.urlopen(req, timeout=30) as r:
			data = json.loads(r.read().decode("utf-8"))
	except urllib.error.HTTPError as e:
		raise RuntimeError("HTTP %s" % e.code)
	except urllib.error.URLError as e:
		raise RuntimeError("Connection failed: %s" % e.reason)
	items = data.get("data") if isinstance(data, dict) else data
	ids = []
	for it in items or []:
		mid = it.get("id") if isinstance(it, dict) else str(it)
		if mid:
			ids.append(mid[len("models/"):] if mid.startswith("models/") else mid)
	if not ids:
		raise RuntimeError("The provider returned no models.")
	return sorted(set(ids))
