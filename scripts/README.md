# Scripts - AgriAI

Utility scripts for development and deployment.

## Available Scripts

### Setup & Start

**setup.sh**
- Initialize project
- Create directories
- Setup environment

```bash
./scripts/setup.sh
```

**start.sh**
- Start all services
- Check health
- Display URLs

```bash
./scripts/start.sh
```

**stop.sh**
- Stop all services

```bash
./scripts/stop.sh
```

### Testing & Demo

**demo.sh**
- Run API demos
- Test endpoints
- Show examples

```bash
./scripts/demo.sh
```

**test_api.sh**
- Test all API endpoints
- Check responses
- Verify functionality

```bash
./scripts/test_api.sh
```

**check_system.sh**
- Check system health
- Verify dependencies
- Check ports
- Test services

```bash
./scripts/check_system.sh
```

### Database

### Public demo web (Cloudflare Pages + Quick Tunnel)

The public demo is served by `agriai-public-web` and exposed through
`agriai-quick-tunnel`. A Quick Tunnel URL is temporary, so
`update-pages-proxy.ps1` updates the Pages Worker whenever a new URL is
created.

```powershell
# Check/recover Docker, backend, tunnel and Pages health
powershell -ExecutionPolicy Bypass -File .\scripts\ensure-public-web.ps1

# Install recovery at Windows logon plus an hourly watchdog
powershell -ExecutionPolicy Bypass -File .\scripts\install-public-web-watchdog.ps1

# Open the demo; this launcher performs recovery before opening Chrome
.\Xem-Link-AgriAI.cmd
```

Logs are written to `.local\logs\pages-proxy-update.log`.

