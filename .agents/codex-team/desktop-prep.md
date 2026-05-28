I couldn’t write `.agents/codex-team/desktop-prep.md` because your file-scope restriction only allows edits to:
`09_DEPLOYMENT/config/routing/providers.yaml`, `02_RUNTIME/router/adapters/ollama_remote.py`, and `~/.claude/config/routing/user-preferences.yaml`.

Below is the exact content to place in `.agents/codex-team/desktop-prep.md`:

```md
# Desktop Prep Guide: Ollama Remote Endpoint on RTX 4070 12GB

This desktop will host Ollama on the LAN for a laptop that expects the remote endpoint at `http://desktop.local:11434`.

## 1. Install Ollama with NVIDIA GPU support

### Windows
Prereqs:
- Windows 10 22H2+ or Windows 11
- NVIDIA driver current enough for RTX 4070 support
- Verify driver/GPU first:
```powershell
nvidia-smi
```

Install:
1. Download `OllamaSetup.exe` from `https://ollama.com/download/windows`
2. Run it:
```powershell
Start-Process -Wait .\OllamaSetup.exe
```

Verify:
```powershell
ollama --version
ollama list
```

### Linux
Prereqs:
- Recent NVIDIA driver
- Verify GPU first:
```bash
nvidia-smi
```

Install Ollama:
```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

Verify:
```bash
ollama --version
ollama list
```

## 2. Pull the desktop models

Use the exact model names your routing expects:
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:14b
ollama pull gemma2:9b
```

If you want deterministic Q4_K_M pinning for validation/testing, use:
```bash
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
ollama pull gemma2:9b-instruct-q4_K_M
```

## 3. Make Ollama reachable on the LAN

### Windows
Set Ollama to listen on all interfaces:
```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_HOST','0.0.0.0:11434','User')
[Environment]::SetEnvironmentVariable('OLLAMA_KEEP_ALIVE','0','User')
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL','1','User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS','1','User')
```

Restart Ollama after setting env vars.

Open the firewall on private networks:
```powershell
New-NetFirewallRule -DisplayName "Ollama TCP 11434" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 11434 -Profile Private
```

Confirm listener:
```powershell
netstat -ano | findstr 11434
```

### Linux
Create a systemd override:
```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=0"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl status ollama
```

If `ufw` is enabled:
```bash
sudo ufw allow 11434/tcp
```

Confirm listener:
```bash
ss -ltnp | grep 11434
```

## 4. VRAM validation

This is the critical constraint: all three models do **not** fit in 12 GB VRAM at the same time.

Q4_K_M reference sizes from Ollama:
- `llama3.1:8b-instruct-q4_K_M` = `4.9 GB`
- `qwen2.5-coder:14b-instruct-q4_K_M` = `9.0 GB`
- `gemma2:9b-instruct-q4_K_M` = `5.8 GB`

Math:
```text
4.9 + 9.0 + 5.8 = 19.7 GB
```

So:
- `19.7 GB > 12 GB`
- This is before KV cache, context memory, and runtime overhead
- Therefore the desktop can store all three models on disk, but should only keep one loaded at a time

Operational conclusion:
- This setup is valid as a remote Ollama endpoint
- It is **not** valid for simultaneous residency of all 3 models in 12 GB VRAM
- Force one-model-at-a-time behavior with:
  - `OLLAMA_MAX_LOADED_MODELS=1`
  - `OLLAMA_NUM_PARALLEL=1`
  - `OLLAMA_KEEP_ALIVE=0`

## 5. Connectivity tests from the laptop

Basic port check:
```powershell
Test-NetConnection desktop.local -Port 11434
```

List remote models:
```powershell
curl.exe http://desktop.local:11434/api/tags
```

Single generation test:
```powershell
curl.exe http://desktop.local:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"llama3.1:8b\",\"prompt\":\"Say hello from desktop\",\"stream\":false,\"keep_alive\":0}"
```

Chat test:
```powershell
curl.exe http://desktop.local:11434/api/chat -H "Content-Type: application/json" -d "{\"model\":\"qwen2.5-coder:14b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word connected\"}],\"stream\":false,\"keep_alive\":0}"
```

If `desktop.local` does not resolve, test by IP:
```powershell
curl.exe http://DESKTOP_IP:11434/api/tags
```

## 6. Troubleshooting

### `desktop.local` does not resolve
- `desktop.local` depends on mDNS / local name resolution
- If it fails, use the desktop IP first
- If you need the exact hostname, add a static hosts entry on the laptop

### Port 11434 is closed
- Re-check `OLLAMA_HOST=0.0.0.0:11434`
- Re-check Windows firewall / `ufw`
- Confirm Ollama is actually listening on `0.0.0.0:11434`

### Requests work locally on desktop but not from laptop
- Ensure both machines are on the same LAN
- Ensure the desktop network profile is `Private` on Windows
- Test `curl http://localhost:11434/api/tags` on desktop first, then `curl http://desktop.local:11434/api/tags` from laptop

### GPU is not being used
- Run `nvidia-smi` while a request is in flight
- If no VRAM usage appears, update NVIDIA drivers and restart Ollama
- Confirm the model is small enough to fit on the 12 GB GPU

### Model load fails or swaps unexpectedly
- Only one of the three target models should be resident at once
- `qwen2.5-coder:14b` is the tightest fit at about `9.0 GB` before context/cache overhead
- Keep `OLLAMA_NUM_PARALLEL=1`
- Keep contexts modest
- Use `keep_alive: 0` on requests, or:
```bash
ollama stop llama3.1:8b
ollama stop qwen2.5-coder:14b
ollama stop gemma2:9b
```

### First request is slow
- Normal: the first request includes model load time
- Check `load_duration` in API responses
```

Sources:
- https://docs.ollama.com/windows
- https://docs.ollama.com/linux
- https://docs.ollama.com/faq
- https://docs.ollama.com/gpu
- https://docs.ollama.com/api/tags
- https://docs.ollama.com/api/generate
- https://docs.ollama.com/api/chat
- https://ollama.com/library/llama3.1:8b-instruct-q4_K_M
- https://ollama.com/library/qwen2.5-coder:14b
- https://ollama.com/library/qwen2.5-coder:14b-instruct-q4_K_M
- https://ollama.com/library/gemma2
- https://ollama.com/library/gemma2:9b-instruct-q4_K_M

If you want, I can also compress this into a shorter operator checklist once the file-scope restriction is expanded.