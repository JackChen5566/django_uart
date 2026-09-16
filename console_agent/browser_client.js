(function (global) {
  "use strict";

  const DEFAULT_AGENT_URL = "http://127.0.0.1:9001";

  function normalizeAgentUrl(agentUrl) {
    const url = new URL(agentUrl || global.CONSOLE_AGENT_URL || DEFAULT_AGENT_URL);
    url.pathname = url.pathname.replace(/\/+$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  }

  function apiUrl(baseUrl, path, params) {
    const url = new URL(path, `${baseUrl}/`);
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
    return url;
  }

  function websocketUrl(baseUrl, path, params) {
    const url = apiUrl(baseUrl, path, params);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  }

  async function jsonFetch(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || data.message || response.statusText);
    }
    return data;
  }

  class LocalConsoleAgent {
    constructor(options) {
      this.baseUrl = normalizeAgentUrl(options && options.agentUrl);
    }

    status() {
      return jsonFetch(apiUrl(this.baseUrl, "/api/status"));
    }

    ports() {
      return jsonFetch(apiUrl(this.baseUrl, "/api/ports"));
    }

    commands(profile) {
      return jsonFetch(apiUrl(this.baseUrl, "/api/commands", { profile }));
    }

    validate(settings) {
      return jsonFetch(apiUrl(this.baseUrl, "/api/connect"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
    }

    openConsole(settings, handlers) {
      const callbacks = handlers || {};
      const ws = new WebSocket(websocketUrl(this.baseUrl, "/ws/console", settings));

      ws.addEventListener("open", (event) => {
        if (callbacks.open) callbacks.open(event);
      });

      ws.addEventListener("message", (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "serial" && callbacks.serial) callbacks.serial(message.data, message);
        if (message.type === "connected" && callbacks.connected) callbacks.connected(message);
        if (message.type === "error" && callbacks.error) callbacks.error(new Error(message.message), message);
        if (callbacks.message) callbacks.message(message);
      });

      ws.addEventListener("close", (event) => {
        if (callbacks.close) callbacks.close(event);
      });

      ws.addEventListener("error", (event) => {
        if (callbacks.error) callbacks.error(event);
      });

      return ws;
    }

    sendCommand(ws, command) {
      ws.send(JSON.stringify({ type: "command", data: command }));
    }

    sendQuickCommand(ws, name) {
      ws.send(JSON.stringify({ type: "quick_command", name }));
    }
  }

  global.LocalConsoleAgent = LocalConsoleAgent;
})(window);
