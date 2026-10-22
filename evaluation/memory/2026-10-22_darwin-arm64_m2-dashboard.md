# Memory check: one model loaded with the app running

- Run at (UTC): 2026-10-22 18:38:46
- Machine: {'os': 'Darwin', 'os_version': '26.6.2', 'arch': 'arm64', 'python': '3.13.17', 'chip': 'Apple M3', 'memory_gb': 16.0}
- App health: {'status': 'ok', 'app_version': '0.1.0', 'ollama': {'reachable': True, 'version': '0.40.8'}}
- Model: `qwen3:4b-instruct-2507-q4_K_M` at num_ctx 8192, 5 requests

| Measure | Baseline (no model loaded) | After requests |
|---|---|---|
| macOS memory pressure | normal | normal |
| System free % | 84 | 58 |
| Swap used (MB) | 2314.31 | 2266.25 |

Models loaded after the requests:

- `qwen3:4b-instruct-2507-q4_K_M`: 3.88 GB, 100% GPU, context 8192

Generation speed across requests: 27.3–28.5 tokens/s.

Largest memory users after the requests (summed per app):

- Ollama.app: 5402 MB
- Google Chrome.app: 2013 MB
- Claude.app: 1751 MB
- Dropbox.app: 461 MB
- claude.app: 339 MB
- python: 291 MB

Note: on Apple Silicon, GPU memory is shared with the system, so the model's memory may not appear fully in per-app figures. The loaded size above is Ollama's own figure.
