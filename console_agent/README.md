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

You have two deployment choices:

- Build one standalone agent binary for client PCs. This avoids copying the project and avoids installing Python packages on every PC.
- Use the Python source install below when developing or debugging.

## Build A Windows Client EXE

Build this once on a Windows PC that has Python:

```powershell
cd C:\path\to\django_uart
.\scripts\build_windows_agent.ps1
```

The build output is:

```text
dist\console-agent.exe
dist\console-agent-windows-installer.zip
```

Use the installer zip for client PCs. It contains:

```text
console-agent.exe
install.ps1
uninstall.ps1
```

Copy or download the zip to each client PC, extract it, then run `install.ps1` from an elevated PowerShell window. After install, open the shared web page from that client PC:

```text
http://server-ip:9001/
```

This avoids copying the full project or running `pip install` on each client PC. The client PC still runs a small local Windows service, because a server webpage cannot directly access another PC's COM ports.

After `dist\console-agent-windows-installer.zip` exists on the server PC, the built-in web page exposes it for download:

```text
http://server-ip:9001/downloads/console-agent-windows-installer.zip
```

The page shows a `Download Windows installer` link. If the link returns 404, build the Windows agent first and restart or refresh the server page.

## Install As A Windows Service

To keep the client agent running after reboot, install it as a Windows service from an elevated PowerShell window on each client PC:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

This copies the exe to:

```text
C:\Program Files\ConsoleAgent\console-agent.exe
```

The service starts automatically at boot and runs:

```text
console-agent.exe --host 127.0.0.1 --port 9001
```

Check service status:

```powershell
Get-Service ConsoleAgent
```

Test the local agent:

```text
http://127.0.0.1:9001/api/status
```

Remove the service:

```powershell
.\uninstall.ps1
```

Remove the service and installed files:

```powershell
.\uninstall.ps1 -RemoveFiles
```

## Build A Linux Client Binary

Build this once on a Linux PC that has Python 3:

```bash
cd /path/to/django_uart
bash ./scripts/build_linux_agent.sh
```

The build output is:

```text
dist/console-agent
```

Copy only that binary to each Linux client PC. On every Linux client PC that needs to read its own serial device, run:

```bash
chmod +x ./console-agent
./console-agent --host 127.0.0.1 --port 9001
```

Then open the shared web page from that Linux client PC:

```text
http://server-ip:9001/
```

PyInstaller builds are OS-specific. Build the Windows `.exe` on Windows and the Linux binary on Linux.

Linux users usually need serial permission before `/dev/ttyUSB*` or `/dev/ttyACM*` ports are readable:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership. For a quick temporary test, you can run the agent with a user that already has permission to the serial device.

## Python Source Install

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
python -m console_agent.agent
```

If Windows does not have `python`, try:

```powershell
py -m console_agent.agent
```

Linux:

```bash
python3 -m console_agent.agent
```

Run the command from the project root directory, the folder that contains `console_agent`:

```powershell
cd C:\path\to\django_uart
python -m console_agent.agent
```

The module name uses an underscore. Do not include a backslash:

```text
Correct:   python -m console_agent.agent
Wrong:     python3 -m console\_agent.agent
```

Then open:

```text
http://localhost:9001/
```

The home page lists the serial ports detected on the current PC. On Windows they look like `COM3`; on Linux they look like `/dev/ttyUSB3` or `/dev/ttyACM0`.

Select a port and baudrate, then click `Connect`. After connecting, the port, baudrate, and refresh button are locked until `Disconnect`.

The terminal renders common ANSI SGR color sequences, including standard colors, bright colors, 256-color mode, RGB foreground/background colors, bold, dim, underline, and inverse. Other ANSI cursor/control sequences are ignored instead of being printed as raw escape text.

To write RU manager settings, connect to the UART shell, click `Load JSON`, choose a local JSON file, then click `Apply settings`. The page converts the top-level JSON object to `key=value` lines and overwrites `/etc/rumanager.conf` on the connected Linux system. The shell must be root, or have passwordless `sudo cp` permission for `/etc/rumanager.conf`.

The default bind address is `0.0.0.0:9001`, so other devices on the LAN can open the page by IP:

```text
http://server-ip:9001/
```

The page itself connects console APIs to `http://127.0.0.1:9001`, which means each browser reads the serial ports on its own PC. If you want a client PC's agent to be local-only, run it with `--host 127.0.0.1`.

Quick commands are loaded from the PC that served the web page, so all users see the server's command buttons. When a user clicks one, the page sends the actual command text to that user's local console connection.

For every client PC that needs to read its own serial device:

```powershell
python -m console_agent.agent --host 127.0.0.1 --port 9001
```

Then open the shared page from that PC:

```text
http://server-ip:9001/
```

If the page shows `Local agent not available`, the browser cannot reach `http://127.0.0.1:9001` on that client PC. Start the local agent on that PC and click `Refresh ports`.

If `127.0.0.1` fails on a browser, the page also tries `http://localhost:9001`. You can edit `Local agent URL` on the page and click `Apply` to test another local address.

If the terminal shows `Serial write timeout`, the browser and agent are connected, but the selected serial device did not accept outgoing data. Check the selected COM port, cable/power, baudrate, and hardware flow-control settings, then send again or reconnect.

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
