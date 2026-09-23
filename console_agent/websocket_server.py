from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from aiohttp import WSMsgType, web

from .command_manager import CommandManager
from .config import AgentConfig, load_config_or_default
from .serial_manager import SerialManager, SerialSession, SerialSettings


LOGGER = logging.getLogger("console-agent")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Serial Console Agent</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111318;
      --panel: #1b1f29;
      --panel-2: #151923;
      --line: #343b4d;
      --text: #eef2f8;
      --muted: #9ba7ba;
      --accent: #5cc8ff;
      --danger: #ff6b6b;
      --ok: #74d99f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 20px 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .status {
      color: var(--muted);
      min-width: 160px;
      text-align: right;
    }
    .status.connected { color: var(--ok); }
    .status.error { color: var(--danger); }
    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 16px;
      align-items: stretch;
    }
    aside, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    aside { padding: 16px; }
    label {
      display: block;
      margin: 14px 0 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    select, input {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }
    button {
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #252b38;
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      cursor: pointer;
    }
    button.primary {
      border-color: #2a84aa;
      background: #116487;
    }
    button.danger {
      border-color: #8c3434;
      background: #6f2525;
    }
    button:disabled, select:disabled, input:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 16px;
    }
    .quick {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 8px;
    }
    .terminal-wrap {
      display: grid;
      grid-template-rows: 1fr auto;
      min-height: calc(100vh - 110px);
    }
    #terminal {
      min-height: 420px;
      max-height: calc(100vh - 210px);
      overflow: auto;
      margin: 0;
      padding: 14px;
      background: #07090d;
      border-radius: 8px 8px 0 0;
      color: #d8f7dd;
      font: 13px/1.45 Consolas, "Cascadia Mono", "Courier New", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .command-row {
      display: grid;
      grid-template-columns: 1fr 92px;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--line);
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      margin-top: 10px;
    }
    .inline-row {
      display: grid;
      grid-template-columns: 1fr 88px;
      gap: 8px;
      align-items: center;
    }
    .config-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 8px;
    }
    .file-input {
      display: none;
    }
    .download-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 38px;
      border: 1px solid #2a84aa;
      border-radius: 6px;
      background: #116487;
      color: var(--text);
      text-decoration: none;
      margin-bottom: 12px;
    }
    @media (max-width: 820px) {
      .layout { grid-template-columns: 1fr; }
      .terminal-wrap { min-height: 560px; }
      #terminal { max-height: 520px; }
      header { align-items: flex-start; flex-direction: column; }
      .status { text-align: left; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Serial Console Agent</h1>
      <div id="status" class="status">Loading...</div>
    </header>
    <div class="layout">
      <aside>
        <a class="download-link" href="/downloads/console-agent-windows-installer.zip" download>Download Windows installer</a>
        <button id="refreshPorts" type="button">Refresh ports</button>

        <label for="agentUrl">Local agent URL</label>
        <div class="inline-row">
          <input id="agentUrl" type="text" value="http://127.0.0.1:9001">
          <button id="applyAgentUrl" type="button">Apply</button>
        </div>

        <label for="port">Serial port</label>
        <select id="port"></select>

        <label for="baudrate">Baudrate</label>
        <select id="baudrate"></select>

        <div class="actions">
          <button id="connect" class="primary" type="button">Connect</button>
          <button id="disconnect" class="danger" type="button" disabled>Disconnect</button>
        </div>

        <label>Quick command</label>
        <div id="quick" class="quick"></div>
        <div class="hint">After connecting, port settings are locked until Disconnect.</div>

        <label>RU manager config</label>
        <input id="ruConfigFile" class="file-input" type="file" accept="application/json,.json">
        <div class="config-row">
          <button id="loadRuConfig" type="button">Load JSON</button>
          <button id="applyRuConfig" class="primary" type="button" disabled>Apply settings</button>
        </div>
        <div id="ruConfigSummary" class="hint">No JSON loaded.</div>
      </aside>

      <section class="terminal-wrap">
        <pre id="terminal"></pre>
        <div class="command-row">
          <input id="command" type="text" placeholder="Type command and press Enter" disabled>
          <button id="send" type="button" disabled>Send</button>
        </div>
      </section>
    </div>
  </main>

  <script>
    const LOCAL_AGENT_CANDIDATES = ["http://127.0.0.1:9001", "http://localhost:9001"];
    const DEFAULT_BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600];
    const state = {
      ws: null,
      commands: {},
      connected: false,
      localAgentOnline: false,
      localAgentUrl: LOCAL_AGENT_CANDIDATES[0],
      ansiStyle: {},
      ruConfig: null,
      ruConfigName: "",
    };
    const $ = (id) => document.getElementById(id);
    const agentUrlInput = $("agentUrl");
    const portSelect = $("port");
    const baudrateSelect = $("baudrate");
    const terminal = $("terminal");
    const statusEl = $("status");
    const commandInput = $("command");
    const ruConfigFileInput = $("ruConfigFile");
    const ESC = String.fromCharCode(27);
    const BEL = String.fromCharCode(7);
    const ANSI_COLORS = {
      30: "#2f343f", 31: "#ff6b6b", 32: "#74d99f", 33: "#ffd166",
      34: "#5cc8ff", 35: "#d98cff", 36: "#67e8f9", 37: "#eef2f8",
      90: "#8b95a7", 91: "#ff8f8f", 92: "#9af0ba", 93: "#ffe08a",
      94: "#8edaff", 95: "#e8b0ff", 96: "#9bf2ff", 97: "#ffffff",
    };
    const ANSI_BACKGROUNDS = {
      40: "#2f343f", 41: "#8c3434", 42: "#23603d", 43: "#7a5a16",
      44: "#1c5770", 45: "#5f3b75", 46: "#23616a", 47: "#eef2f8",
      100: "#5b6473", 101: "#a94444", 102: "#2f7d50", 103: "#9f7720",
      104: "#2a84aa", 105: "#7d4f98", 106: "#2f8894", 107: "#ffffff",
    };

    function setStatus(text, cls = "") {
      statusEl.textContent = text;
      statusEl.className = `status ${cls}`.trim();
    }

    function errorText(error) {
      return error && error.message ? error.message : String(error);
    }

    function normalizeAgentUrl(value) {
      const url = new URL(value);
      url.pathname = "";
      url.search = "";
      url.hash = "";
      return url.toString().replace(/\/$/, "");
    }

    function apiUrl(baseUrl, path, params = {}) {
      const url = new URL(path, `${baseUrl}/`);
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, value);
        }
      }
      return url;
    }

    async function fetchJson(baseUrl, path, options = {}) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const response = await fetch(apiUrl(baseUrl, path), {
        cache: "no-store",
        ...options,
        signal: controller.signal,
      }).finally(() => clearTimeout(timeout));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.message || response.statusText);
      return data;
    }

    async function fetchPageJson(path, options) {
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.message || response.statusText);
      return data;
    }

    async function detectLocalAgent(preferredUrl) {
      const candidates = [];
      if (preferredUrl) candidates.push(preferredUrl);
      for (const url of LOCAL_AGENT_CANDIDATES) {
        if (!candidates.includes(url)) candidates.push(url);
      }

      const failures = [];
      for (const candidate of candidates) {
        try {
          const baseUrl = normalizeAgentUrl(candidate);
          const status = await fetchJson(baseUrl, "/api/status");
          state.localAgentUrl = baseUrl;
          agentUrlInput.value = baseUrl;
          return status;
        } catch (error) {
          failures.push(`${candidate}: ${errorText(error)}`);
        }
      }
      throw new Error(failures.join("; "));
    }

    function xterm256Color(index) {
      if (index < 0 || index > 255) return null;
      const base = [
        "#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
        "#7f7f7f", "#ff0000", "#00ff00", "#ffff00", "#5c5cff", "#ff00ff", "#00ffff", "#ffffff",
      ];
      if (index < 16) return base[index];
      if (index >= 232) {
        const level = 8 + (index - 232) * 10;
        return `rgb(${level}, ${level}, ${level})`;
      }
      const value = [0, 95, 135, 175, 215, 255];
      const offset = index - 16;
      const red = value[Math.floor(offset / 36) % 6];
      const green = value[Math.floor(offset / 6) % 6];
      const blue = value[offset % 6];
      return `rgb(${red}, ${green}, ${blue})`;
    }

    function applySgr(params) {
      if (!params.length) params = [0];
      for (let i = 0; i < params.length; i += 1) {
        const code = params[i];
        if (code === 0) state.ansiStyle = {};
        else if (code === 1) state.ansiStyle.bold = true;
        else if (code === 2) state.ansiStyle.dim = true;
        else if (code === 4) state.ansiStyle.underline = true;
        else if (code === 7) state.ansiStyle.inverse = true;
        else if (code === 22) {
          delete state.ansiStyle.bold;
          delete state.ansiStyle.dim;
        } else if (code === 24) delete state.ansiStyle.underline;
        else if (code === 27) delete state.ansiStyle.inverse;
        else if (code === 39) delete state.ansiStyle.color;
        else if (code === 49) delete state.ansiStyle.backgroundColor;
        else if (ANSI_COLORS[code]) state.ansiStyle.color = ANSI_COLORS[code];
        else if (ANSI_BACKGROUNDS[code]) state.ansiStyle.backgroundColor = ANSI_BACKGROUNDS[code];
        else if ((code === 38 || code === 48) && params[i + 1] === 5) {
          const color = xterm256Color(params[i + 2]);
          if (color && code === 38) state.ansiStyle.color = color;
          if (color && code === 48) state.ansiStyle.backgroundColor = color;
          i += 2;
        } else if ((code === 38 || code === 48) && params[i + 1] === 2) {
          const red = params[i + 2];
          const green = params[i + 3];
          const blue = params[i + 4];
          if ([red, green, blue].every((value) => Number.isFinite(value) && value >= 0 && value <= 255)) {
            const color = `rgb(${red}, ${green}, ${blue})`;
            if (code === 38) state.ansiStyle.color = color;
            if (code === 48) state.ansiStyle.backgroundColor = color;
          }
          i += 4;
        }
      }
    }

    function appendStyledText(text) {
      if (!text) return;
      const style = state.ansiStyle;
      const foreground = style.inverse ? style.backgroundColor : style.color;
      const background = style.inverse ? style.color : style.backgroundColor;
      const hasStyle = foreground || background || style.bold || style.dim || style.underline;

      if (!hasStyle) {
        terminal.appendChild(document.createTextNode(text));
        return;
      }

      const span = document.createElement("span");
      if (foreground) span.style.color = foreground;
      if (background) span.style.backgroundColor = background;
      if (style.bold) span.style.fontWeight = "700";
      if (style.dim) span.style.opacity = "0.72";
      if (style.underline) span.style.textDecoration = "underline";
      span.textContent = text;
      terminal.appendChild(span);
    }

    function trimTerminal() {
      while (terminal.childNodes.length > 5000) {
        terminal.removeChild(terminal.firstChild);
      }
    }

    function append(text) {
      const oscPattern = new RegExp(`${ESC}\\][\\s\\S]*?(?:${BEL}|${ESC}\\\\)`, "g");
      const singleEscapePattern = new RegExp(`${ESC}[@-Z\\\\-_]`, "g");
      const csiPattern = new RegExp(`${ESC}\\[([0-?]*)([ -/]*)([@-~])`, "g");
      const stripped = text
        .replace(oscPattern, "")
        .replace(singleEscapePattern, "");
      let cursor = 0;
      let match;

      while ((match = csiPattern.exec(stripped)) !== null) {
        appendStyledText(stripped.slice(cursor, match.index));
        cursor = csiPattern.lastIndex;

        if (match[3] === "m") {
          const params = match[1]
            ? match[1].split(";").map((value) => (value === "" ? 0 : Number(value)))
            : [0];
          applySgr(params.filter((value) => Number.isFinite(value)));
        }
      }

      appendStyledText(stripped.slice(cursor));
      trimTerminal();
      terminal.scrollTop = terminal.scrollHeight;
    }

    function setLocked(locked) {
      state.connected = locked;
      portSelect.disabled = locked;
      baudrateSelect.disabled = locked;
      $("refreshPorts").disabled = locked;
      $("connect").disabled = locked;
      $("disconnect").disabled = !locked;
      commandInput.disabled = !locked;
      $("send").disabled = !locked;
      for (const button of document.querySelectorAll("[data-command]")) {
        button.disabled = !locked;
      }
      updateRuConfigButton();
    }

    function updateRuConfigButton() {
      $("applyRuConfig").disabled = !state.connected || !state.ruConfig;
    }

    function loadDefaultBaudrates(defaultBaudrate = 115200, baudrates = DEFAULT_BAUDRATES) {
      baudrateSelect.innerHTML = "";
      for (const rate of baudrates) {
        const option = new Option(rate, rate);
        if (rate === defaultBaudrate) option.selected = true;
        baudrateSelect.add(option);
      }
    }

    async function loadStatus() {
      const data = await detectLocalAgent(agentUrlInput.value);
      loadDefaultBaudrates(data.default_baudrate, data.baudrates);
      state.localAgentOnline = true;
      setStatus(`${data.name} online via ${state.localAgentUrl}`);
    }

    async function loadPorts() {
      const ports = await fetchJson(state.localAgentUrl, "/api/ports");
      portSelect.innerHTML = "";

      if (!ports.length) {
        portSelect.add(new Option("No serial ports found", ""));
        setStatus("No serial ports found", "error");
        return;
      }

      for (const port of ports) {
        const label = port.description ? `${port.device} - ${port.description}` : port.device;
        portSelect.add(new Option(label, port.device));
      }
      setStatus(`${ports.length} port(s) found`);
    }

    async function loadLocalAgent() {
      portSelect.innerHTML = "";
      portSelect.add(new Option("Loading local ports...", ""));
      loadDefaultBaudrates();
      $("connect").disabled = true;

      try {
        await loadStatus();
        await loadPorts();
        $("connect").disabled = !portSelect.value;
      } catch (error) {
        state.localAgentOnline = false;
        portSelect.innerHTML = "";
        portSelect.add(new Option("Local agent not available", ""));
        $("connect").disabled = true;
        setStatus(`Local agent unavailable: ${errorText(error)}`, "error");
      }
    }

    async function loadCommands() {
      const data = await fetchPageJson("/api/commands");
      state.commands = data.commands || {};
      const quick = $("quick");
      quick.innerHTML = "";

      for (const name of Object.keys(state.commands)) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = name;
        button.dataset.command = name;
        button.disabled = !state.connected;
        button.addEventListener("click", () => sendQuick(name));
        quick.appendChild(button);
      }
    }

    function wsUrl() {
      const agent = new URL(state.localAgentUrl);
      const scheme = agent.protocol === "https:" ? "wss" : "ws";
      const params = new URLSearchParams({
        port: portSelect.value,
        baudrate: baudrateSelect.value,
      });
      return `${scheme}://${agent.host}/ws/console?${params}`;
    }

    function connect() {
      if (!state.localAgentOnline) {
        setStatus("Start the local agent on this PC, then refresh ports", "error");
        return;
      }
      if (!portSelect.value) {
        setStatus("Select a serial port first", "error");
        return;
      }

      const ws = new WebSocket(wsUrl());
      state.ws = ws;
      setStatus("Connecting...");

      ws.onopen = () => {
        setLocked(true);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "serial") append(message.data);
        if (message.type === "connected") {
          setStatus(`${message.port} connected`, "connected");
          append(`\\n[connected ${message.port} @ ${message.baudrate}]\\n`);
        }
        if (message.type === "error") {
          append(`\\n[error] ${message.message}\\n`);
          setStatus(message.message, "error");
        }
      };

      ws.onclose = () => {
        setLocked(false);
        setStatus("Disconnected");
        append("\\n[disconnected]\\n");
        state.ws = null;
      };

      ws.onerror = () => {
        setStatus("WebSocket error", "error");
      };
    }

    function disconnect() {
      if (state.ws) state.ws.close();
    }

    function sendCommand() {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
      const value = commandInput.value;
      if (!value) return;
      state.ws.send(JSON.stringify({ type: "command", data: `${value}\\n` }));
      commandInput.value = "";
      setStatus("Command sent", "connected");
    }

    function sendQuick(name) {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
      const command = state.commands[name];
      if (command === undefined) {
        setStatus(`Unknown quick command: ${name}`, "error");
        return;
      }
      const data = command.endsWith("\\n") ? command : `${command}\\n`;
      state.ws.send(JSON.stringify({ type: "command", data }));
      setStatus(`${name} sent`, "connected");
    }

    function isPlainObject(value) {
      return value !== null && typeof value === "object" && !Array.isArray(value);
    }

    function configValue(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "string") return value.replace(/\r\n?/g, "\n").replace(/\n/g, "\\n");
      if (typeof value === "number" || typeof value === "boolean") return String(value);
      return JSON.stringify(value);
    }

    function buildRuManagerConfig(data) {
      if (!isPlainObject(data)) throw new Error("JSON root must be an object");

      const lines = [];
      for (const [key, value] of Object.entries(data)) {
        if (!key) throw new Error("JSON contains an empty key");
        if (/[\r\n]/.test(key)) throw new Error(`JSON key contains a line break: ${key}`);
        lines.push(`${key}=${configValue(value)}`);
      }

      if (!lines.length) throw new Error("JSON object has no key/value pairs");
      return `${lines.join("\n")}\n`;
    }

    function hereDocDelimiter(content) {
      let delimiter = "RUMANAGER_CONF_EOF";
      let index = 1;
      while (content.includes(delimiter)) {
        delimiter = `RUMANAGER_CONF_EOF_${index}`;
        index += 1;
      }
      return delimiter;
    }

    function buildRuManagerCommand(data) {
      const content = buildRuManagerConfig(data);
      const delimiter = hereDocDelimiter(content);
      return [
        'tmp="/tmp/rumanager.conf.$$"',
        `cat > "$tmp" <<'${delimiter}'`,
        content.trimEnd(),
        delimiter,
        'if [ "$(id -u 2>/dev/null)" = "0" ]; then',
        '  cp "$tmp" /etc/rumanager.conf',
        "else",
        '  sudo cp "$tmp" /etc/rumanager.conf',
        "fi",
        'rm -f "$tmp"',
        "sync",
        'echo "[rumanager.conf updated]"',
        "",
      ].join("\n");
    }

    async function loadRuConfigFile(file) {
      const text = await file.text();
      const data = JSON.parse(text);
      if (!isPlainObject(data)) throw new Error("JSON root must be an object");
      buildRuManagerConfig(data);

      state.ruConfig = data;
      state.ruConfigName = file.name;
      $("ruConfigSummary").textContent = `${file.name}: ${Object.keys(data).length} key/value pair(s) loaded.`;
      updateRuConfigButton();
      setStatus(`Loaded ${file.name}`);
    }

    function applyRuConfig() {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        setStatus("Connect to the UART shell before applying settings", "error");
        return;
      }
      if (!state.ruConfig) {
        setStatus("Load a JSON config first", "error");
        return;
      }
      if (!confirm("Overwrite /etc/rumanager.conf on the connected Linux system?")) return;

      const command = buildRuManagerCommand(state.ruConfig);
      state.ws.send(JSON.stringify({ type: "command", data: command }));
      append(`\n[applying ${state.ruConfigName || "JSON"} to /etc/rumanager.conf]\n`);
      setStatus("rumanager.conf apply command sent", "connected");
    }

    $("refreshPorts").addEventListener("click", loadLocalAgent);
    $("applyAgentUrl").addEventListener("click", loadLocalAgent);
    $("connect").addEventListener("click", connect);
    $("disconnect").addEventListener("click", disconnect);
    $("send").addEventListener("click", sendCommand);
    $("loadRuConfig").addEventListener("click", () => ruConfigFileInput.click());
    $("applyRuConfig").addEventListener("click", applyRuConfig);
    ruConfigFileInput.addEventListener("change", () => {
      const file = ruConfigFileInput.files && ruConfigFileInput.files[0];
      if (!file) return;
      loadRuConfigFile(file).catch((error) => {
        state.ruConfig = null;
        state.ruConfigName = "";
        $("ruConfigSummary").textContent = `JSON load failed: ${errorText(error)}`;
        updateRuConfigButton();
        setStatus(`JSON load failed: ${errorText(error)}`, "error");
      });
    });
    commandInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") sendCommand();
    });

    loadDefaultBaudrates();
    loadCommands().catch((error) => {
      setStatus(`Quick commands unavailable: ${errorText(error)}`, "error");
    });
    loadLocalAgent();
  </script>
</body>
</html>
"""


@web.middleware
async def cors_middleware(request: web.Request, handler: web.RequestHandler) -> web.StreamResponse:
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)

    config: AgentConfig = request.app["config"]
    origin = request.headers.get("Origin")
    if "*" in config.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in config.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    if request.headers.get("Access-Control-Request-Private-Network") == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


def create_app(config: AgentConfig) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config
    app["commands"] = CommandManager(config.commands)
    app["active_ports"] = set()
    app.router.add_get("/", index)
    app.router.add_get("/client.js", client_js)
    app.router.add_get("/downloads/console-agent.exe", windows_agent_download)
    app.router.add_get("/downloads/console-agent-windows-installer.zip", windows_installer_download)
    app.router.add_get("/api/status", status)
    app.router.add_get("/api/ports", ports)
    app.router.add_post("/api/connect", connect)
    app.router.add_get("/api/commands", commands)
    app.router.add_get("/ws/console", console_ws)
    return app


async def index(request: web.Request) -> web.Response:
    return web.Response(text=INDEX_HTML, content_type="text/html")


async def client_js(request: web.Request) -> web.Response:
    path = Path(__file__).with_name("browser_client.js")
    return web.FileResponse(path, headers={"Cache-Control": "no-store"})


async def windows_agent_download(request: web.Request) -> web.StreamResponse:
    path = Path(__file__).resolve().parent.parent / "dist" / "console-agent.exe"
    if not path.exists():
        return web.Response(
            status=404,
            text="console-agent.exe is not built yet. Run scripts/build_windows_agent.ps1 first.",
        )
    return web.FileResponse(
        path,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="console-agent.exe"',
        },
    )


async def windows_installer_download(request: web.Request) -> web.StreamResponse:
    path = Path(__file__).resolve().parent.parent / "dist" / "console-agent-windows-installer.zip"
    if not path.exists():
        return web.Response(
            status=404,
            text="console-agent-windows-installer.zip is not built yet. Run scripts/build_windows_agent.ps1 first.",
        )
    return web.FileResponse(
        path,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="console-agent-windows-installer.zip"',
        },
    )


async def status(request: web.Request) -> web.Response:
    config: AgentConfig = request.app["config"]
    return web.json_response(
        {
            "name": config.pc_name,
            "status": "online",
            "port": config.port,
            "tls": config.tls_enabled,
            "default_baudrate": config.default_baudrate,
            "devices": [
                {
                    "name": device.name,
                    "port": device.port,
                    "baudrate": device.baudrate,
                    "profile": device.profile,
                }
                for device in config.devices
            ],
            "baudrates": config.baudrates,
        }
    )


async def ports(request: web.Request) -> web.Response:
    return web.json_response(SerialManager.list_ports())


async def connect(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        settings = settings_from_payload(payload, request.app["config"])
        await asyncio.to_thread(SerialManager.validate, settings)
    except Exception as exc:
        LOGGER.exception("Serial validation failed")
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    scheme = "wss" if request.app["config"].tls_enabled else "ws"
    host = request.host
    query = urlencode({"port": settings.port, "baudrate": settings.baudrate})
    return web.json_response({"ok": True, "websocket_url": f"{scheme}://{host}/ws/console?{query}"})


async def commands(request: web.Request) -> web.Response:
    manager: CommandManager = request.app["commands"]
    profile = request.query.get("profile", "default")
    return web.json_response({"profile": profile, "commands": manager.list_commands(profile)})


async def console_ws(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    try:
        settings = settings_from_payload(request.query, request.app["config"])
    except Exception as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return ws

    profile = request.query.get("profile", "default")
    manager: CommandManager = request.app["commands"]
    active_ports: set[str] = request.app["active_ports"]

    if settings.port in active_ports:
        await ws.send_json({"type": "error", "message": f"{settings.port} is already connected"})
        await ws.close()
        return ws

    try:
        active_ports.add(settings.port)
        async with SerialSession(settings) as session:
            await ws.send_json(
                {
                    "type": "connected",
                    "port": settings.port,
                    "baudrate": settings.baudrate,
                }
            )
            reader = asyncio.create_task(serial_to_websocket(session, ws))
            writer = asyncio.create_task(websocket_to_serial(ws, session, manager, profile))
            done, pending = await asyncio.wait({reader, writer}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.exception("Console session failed")
        if not ws.closed:
            await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        active_ports.discard(settings.port)
        if not ws.closed:
            await ws.close()

    return ws


async def serial_to_websocket(session: SerialSession, ws: web.WebSocketResponse) -> None:
    while not ws.closed:
        text = await session.read_text()
        if text:
            await ws.send_json({"type": "serial", "data": text})


async def websocket_to_serial(
    ws: web.WebSocketResponse,
    session: SerialSession,
    manager: CommandManager,
    profile: str,
) -> None:
    async for message in ws:
        try:
            if message.type == WSMsgType.TEXT:
                await handle_ws_text(message.data, session, manager, profile)
            elif message.type == WSMsgType.BINARY:
                await session.write_bytes(message.data)
            elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR}:
                break
        except Exception as exc:
            LOGGER.warning("Serial write failed: %s", exc)
            if not ws.closed:
                await ws.send_json({"type": "error", "message": str(exc)})


async def handle_ws_text(
    text: str,
    session: SerialSession,
    manager: CommandManager,
    profile: str,
) -> None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        await session.write_text(text)
        return

    message_type = payload.get("type")
    if message_type == "command":
        await session.write_text(str(payload.get("data", "")))
    elif message_type == "quick_command":
        command_name = str(payload.get("name", ""))
        command = manager.resolve(command_name, profile)
        if command is None:
            raise ValueError(f"Unknown quick command: {command_name}")
        await session.write_text(command)
    elif message_type == "bytes_base64":
        await session.write_base64(str(payload.get("data", "")))
    else:
        raise ValueError(f"Unsupported WebSocket message type: {message_type}")


def settings_from_payload(payload: Any, config: AgentConfig) -> SerialSettings:
    port = str(payload.get("port", "")).strip()
    if not port:
        device_name = str(payload.get("device", "")).strip()
        match = next((device for device in config.devices if device.name == device_name), None)
        if match is None:
            raise ValueError("Missing serial port")
        port = match.port
        baudrate = match.baudrate
    else:
        baudrate = int(payload.get("baudrate", config.default_baudrate))

    return SerialSettings(
        port=port,
        baudrate=baudrate,
        bytesize=int(payload.get("bytesize", 8)),
        parity=str(payload.get("parity", "N")).upper(),
        stopbits=float(payload.get("stopbits", 1)),
        timeout=float(payload.get("timeout", 0.1)),
        write_timeout=float(payload.get("write_timeout", 5)),
    )


def ssl_context(config: AgentConfig) -> ssl.SSLContext | None:
    if not config.tls_enabled:
        return None
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(config.certfile, config.keyfile)
    return context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local serial console agent.")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to agent config JSON.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind when no config file is used.")
    parser.add_argument("--port", default=9001, type=int, help="Port to bind when no config file is used.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    config = load_config_or_default(args.config, host=args.host, port=args.port)
    protocol = "wss" if config.tls_enabled else "ws"
    LOGGER.info("Starting %s on %s:%s (%s)", config.pc_name, config.host, config.port, protocol)
    web.run_app(create_app(config), host=config.host, port=config.port, ssl_context=ssl_context(config))


if __name__ == "__main__":
    main()
