# Console Agent

This agent runs on each Windows or Linux PC that owns serial ports. Django should only handle login, permissions, PC/device setup, and page rendering. Console data flows from each user's browser to the agent on that same PC:

```text
RU/device -> COMx or /dev/ttyUSBx -> local console-agent -> browser WebSocket
```

For a shared site, one PC can expose the web page by IP, but every client PC must also run its own local agent. The web page may come from the server IP; console traffic still goes to `127.0.0.1:9001` in each browser:

```text
PC-A browser -> http://server-ip:9001 page -> http://127.0.0.1:9001 -> PC-A COM ports
PC-B browser -> http://server-ip:9001 page -> http://127.0.0.1:9001 -> PC-B COM ports
server PC -> serves the page, but does not proxy console traffic
```

## Install

Windows PowerShell:

```powershell
cd C:\path\to\django_uart
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\console_agent\requirements.txt
```

Linux:

```bash
cd /path/to/django_uart
python3 -m venv .venv
. .venv/bin/activate
pip install -r ./console_agent/requirements.txt
```

## Run With The Built-In UI

Config is optional. The simplest run command is:

Windows:

```powershell
python.exe -m console_agent.agent
```

Linux:

```bash
python3 -m console_agent.agent
```

Then open:

```text
http://localhost:9001/
```

The home page lists the serial ports detected on the current PC. On Windows they look like `COM3`; on Linux they look like `/dev/ttyUSB3` or `/dev/ttyACM0`.

Select a port and baudrate, then click `Connect`. After connecting, the port, baudrate, and refresh button are locked until `Disconnect`.

The default bind address is `0.0.0.0:9001`, so other devices on the LAN can open the page by IP:

```text
http://server-ip:9001/
```

The page itself connects console APIs to `http://127.0.0.1:9001`, which means each browser reads the serial ports on its own PC. If you want a client PC's agent to be local-only, run it with `--host 127.0.0.1`.

Quick commands are loaded from the PC that served the web page, so all users see the server's command buttons. When a user clicks one, the page sends the actual command text to that user's local console connection.

## Optional Config

You only need a config file if you want fixed PC names, TLS, custom quick commands, or predefined device metadata.

Copy the example first:

Windows:

```powershell
Copy-Item .\console_agent\config.example.json .\console_agent\config.json
```

Linux:

```bash
cp ./console_agent/config.example.json ./console_agent/config.json
```

Then edit `console_agent/config.json`.

Windows ports look like:

```json
{ "name": "RU-01", "port": "COM3", "baudrate": 115200, "profile": "O-RU" }
```

Linux ports look like:

```json
{ "name": "RU-01", "port": "/dev/ttyUSB3", "baudrate": 115200, "profile": "O-RU" }
```

On Linux, the user running the agent usually needs serial permission:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership.

Run with config:

Windows:

```powershell
.\.venv\Scripts\python.exe -m console_agent.agent --config .\console_agent\config.json
```

Linux:

```bash
.venv/bin/python -m console_agent.agent --config ./console_agent/config.json
```

The default page address is `http://PC-IP:9001`. Console API calls from the browser use `http://127.0.0.1:9001`. Quick command definitions come from `http://PC-IP:9001/api/commands`.

## HTTP API

Status:

```http
GET /api/status
```

List local serial ports:

```http
GET /api/ports
```

Validate a connection and return the WebSocket URL:

```http
POST /api/connect
Content-Type: application/json

{
  "port": "COM3",
  "baudrate": 115200
}
```

List quick commands:

```http
GET /api/commands
```

## WebSocket

Connect the browser directly to the agent running on the same PC:

```javascript
const ws = new WebSocket("ws://127.0.0.1:9001/ws/console?port=COM3&baudrate=115200");

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "serial") {
    terminal.write(message.data);
  }
};

ws.send(JSON.stringify({ type: "command", data: "cat /etc/version\n" }));
ws.send(JSON.stringify({ type: "quick_command", name: "version" }));
```

For Linux, use the tty path:

```javascript
new WebSocket("ws://127.0.0.1:9001/ws/console?port=/dev/ttyUSB3&baudrate=115200");
```

## Django Integration

In the Django page, talk to the local agent from browser JavaScript. Do not route console traffic through a Django view, because that would access the Django server PC's serial ports.

You can serve your own copy of `browser_client.js`, or load it from the local agent while it is running:

```html
<script src="http://127.0.0.1:9001/client.js"></script>
<script>
  (async () => {
    const terminal = document.querySelector("#terminal");
    const agent = new LocalConsoleAgent({ agentUrl: "http://127.0.0.1:9001" });

    const ports = await agent.ports();
    const ws = agent.openConsole(
      { port: ports[0].device, baudrate: 115200 },
      {
        serial: (text) => terminal.textContent += text,
        error: (error) => console.error(error),
      },
    );

    agent.sendCommand(ws, "cat /etc/version\n");
  })();
</script>
```

The browser resolves `127.0.0.1` on the user's PC, not on the Django server. That is the key point that lets each PC read its own local console.

## HTTPS Django Pages

If your browser blocks `ws://127.0.0.1` from an `https://` Django page, configure TLS on the agent and use `https://127.0.0.1:9001` plus `wss://127.0.0.1:9001`.

Set these in `config.json`:

```json
{
  "certfile": "certs/agent.crt",
  "keyfile": "certs/agent.key"
}
```

Then connect with:

```javascript
new WebSocket("wss://127.0.0.1:9001/ws/console?port=COM3&baudrate=115200");
```

## PC Metadata

Django can still return PC metadata for display or default choices, for example:

```json
{
  "name": "SQA-PC-01",
  "agent_url": "http://127.0.0.1:9001",
  "devices": [
    { "name": "RU-01", "port": "COM3", "baudrate": 115200, "profile": "O-RU" }
  ]
}
```

The browser then calls its local agent directly. Serial logs and command traffic never pass through Django.
