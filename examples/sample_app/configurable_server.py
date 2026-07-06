import argparse
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import json
import mimetypes

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")

from xtalk import Xtalk
from xtalk.log_utils import mute_other_logging

mute_other_logging()

parser = argparse.ArgumentParser(description="Xtalk Dev Server")
parser.add_argument("--config", type=str, help="Path to the server configuration file")
parser.add_argument("--port", type=int, help="Port number for the server to listen on")
args = parser.parse_args()

app = FastAPI(title="Xtalk Dev Server")

xtalk_instance = Xtalk.from_config(args.config)
xtalk_instance.mount_routes(app)


logs_path = Path(__file__).parent
templates = Jinja2Templates(directory=str(logs_path / "templates"))
app.mount("/static", StaticFiles(directory=str(logs_path / "static")), name="static")
try:
    app.mount(
        "/xtalk",
        StaticFiles(
            directory=str(Path(__file__).parent.parent.parent / "frontend" / "dist")
        ),
        name="xtalk",
    )
except Exception:
    print("No local Xtalk frontend library found.")
@app.get("/api/voices")
async def get_reference_audios():
    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)
        try:
            voices = config["tts"]["params"]["voices"]
        except:
            voices = []
    return JSONResponse(content={"audios": voices})


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Use the modern Starlette TemplateResponse(request, name, context) signature.
    # The old "TemplateResponse(name, context)" form puts ``request`` into the
    # context dict, and jinja2 tries to hash the cache key as ``(name, context)``
    # which fails because ``request`` is an unhashable mapping. See issue #62.
    return templates.TemplateResponse(request, "index.html", {})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port or 11995)
