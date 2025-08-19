from workers import WorkerEntrypoint, Response
import json, importlib
from urllib.parse import urlparse

def _cors_headers(env):
    origin = getattr(env, "ALLOWED_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "authorization, content-type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

# Lazy import so openpyxl only loads on first real request
_placer = None
def _get_placer():
    global _placer
    if _placer is None:
        _placer = importlib.import_module("placer")
    return _placer

class Default(WorkerEntrypoint):
    async def fetch(self, request):  # NOTE: signature must be (self, request)
        env = self.env
        # ctx = self.ctx  # available if you need it

        # CORS preflight
        if request.method == "OPTIONS":
            return Response("", status=204, headers=_cors_headers(env))

        # Optional health / warmup
        u = urlparse(request.url)
        if request.method == "GET" and u.path == "/health":
            return Response("ok", status=200, headers=_cors_headers(env))
        if request.method in ("GET", "POST") and u.path == "/warmup":
            _get_placer()  # primes the import cache
            return Response("warmed", status=200, headers=_cors_headers(env))

        # Main endpoint (expects multipart/form-data)
        if request.method != "POST":
            return Response("Use POST", status=405, headers=_cors_headers(env))

        try:
            form = await request.formData()
            tiles_file = form.get("tiles")
            reqs_file  = form.get("reqs")
            grids = int((form.get("grids") or "10"))
            rows  = int((form.get("rows")  or "24"))
            seed  = int((form.get("seed")  or "42"))

            if not tiles_file or not reqs_file:
                return Response("Missing files 'tiles' and/or 'reqs'", status=400, headers=_cors_headers(env))

            tiles_bytes = bytes(await tiles_file.arrayBuffer())
            reqs_bytes  = bytes(await reqs_file.arrayBuffer())

            placer = _get_placer()
            xlsx_bytes = placer.place_and_export(tiles_bytes, reqs_bytes, grids, rows, seed)

            headers = {
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Content-Disposition": 'attachment; filename="grids_export.xlsx"',
                **_cors_headers(env),
            }
            return Response(xlsx_bytes, status=200, headers=headers)
        except Exception as exc:
            payload = {"error": str(exc)}
            return Response(json.dumps(payload), status=400,
                            headers={"Content-Type": "application/json", **_cors_headers(env)})
