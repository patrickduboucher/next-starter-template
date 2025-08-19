from workers import WorkerEntrypoint, Response
import io
import json
import importlib

# Lazy-load placer (and thus openpyxl) on first request
_placer = None
def _get_placer():
    global _placer
    if _placer is None:
        _placer = importlib.import_module("placer")
    return _placer

def _cors_headers(env):
    # Adjust CORS to your Squarespace site. For dev, you can return "*".
    origin = getattr(env, "ALLOWED_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "authorization, content-type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

class Default(WorkerEntrypoint):
    async def fetch(self, request, env, ctx):
        # Preflight
        if request.method == "OPTIONS":
            return Response("", status=204, headers=_cors_headers(env))

        if request.method != "POST":
            return Response("Use POST", status=405, headers=_cors_headers(env))

        # Optional bearer check (uncomment if you want to enforce a token)
        # token_hdr = request.headers.get("authorization") or ""
        # expected = getattr(env, "TOKEN", None)
        # if expected and token_hdr != f"Bearer {expected}":
        #     return Response("Unauthorized", status=401, headers=_cors_headers(env))

        try:
            form = await request.formData()  # same API as the web Fetch standard
            tiles_file = form.get("tiles")
            reqs_file  = form.get("reqs")
            grids = int((form.get("grids") or "10"))
            rows  = int((form.get("rows")  or "24"))
            seed  = int((form.get("seed")  or "42"))

            if not tiles_file or not reqs_file:
                return Response("Missing files 'tiles' and/or 'reqs'", status=400, headers=_cors_headers(env))

            tiles_bytes = bytes(await tiles_file.arrayBuffer())
            reqs_bytes  = bytes(await reqs_file.arrayBuffer())

            # Run placement and build Excel entirely in memory
            #xlsx_bytes = place_and_export(tiles_bytes, reqs_bytes, grids, rows, seed)
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
