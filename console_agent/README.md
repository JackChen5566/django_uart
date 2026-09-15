# Console Agent

This agent runs on each Windows or Linux PC that owns serial ports. Django should only handle login, permissions, PC/device setup, and page rendering. Console data flows directly:

```text
RU/device -> COMx or /dev/ttyUSBx -> local console-agent -> browser WebSocket
```

## Install

Windows PowerShell:

```powershell
cd C:\path\to\django_uart
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\console_agent\requirements.txt
Copy-Item .\console_agent\config.example.json .\console_agent\config.json
```

Linux:

```bash
cd /path/to/django_uart
python3 -m venv .venv
. .venv/bin/activate
pip install -r ./console_agent/requirements.txt
cp ./console_agent/config.example.json ./console_agent/config.json
```

## Configure

Edit `console_agent/config.json`.

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

## Run

Windows:

```powershell
.\.venv\Scripts\python.exe -m console_agent.agent --config .\console_agent\config.json
```

Linux:

```bash
.venv/bin/python -m console_agent.agent --config ./console_agent/config.json
```

The default service address is `http://PC-IP:9001`.

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
GET /api/commands?profile=O-RU
```

## WebSocket

Connect the browser directly to the PC agent:

```javascript
const ws = new WebSocket("ws://192.168.1.101:9001/ws/console?port=COM3&baudrate=115200&profile=O-RU");

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
new WebSocket("ws://192.168.1.101:9001/ws/console?port=/dev/ttyUSB3&baudrate=115200");
```

## HTTPS Django Pages

Browsers usually block `ws://` from an `https://` page. In production, configure TLS on the agent and use `wss://`.

Set these in `config.json`:

```json
{
  "certfile": "certs/agent.crt",
  "keyfile": "certs/agent.key"
}
```

Then connect with:

```javascript
new WebSocket("wss://192.168.1.101:9001/ws/console?port=COM3&baudrate=115200");
```

## Notes For Django Integration

Django should return PC metadata only, for example:

```json
{
  "name": "SQA-PC-01",
  "agent_url": "https://192.168.1.101:9001",
  "devices": [
    { "name": "RU-01", "port": "COM3", "baudrate": 115200, "profile": "O-RU" }
  ]
}
```

The browser then calls the selected PC agent directly. Serial logs and command traffic never pass through Django.

