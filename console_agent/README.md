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

To bind another host or port without a config file:

```powershell
python.exe -m console_agent.agent --host 0.0.0.0 --port 9001
```

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
GET /api/commands
```

## WebSocket

Connect the browser directly to the PC agent:

```javascript
const ws = new WebSocket("ws://192.168.1.101:9001/ws/console?port=COM3&baudrate=115200");

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
