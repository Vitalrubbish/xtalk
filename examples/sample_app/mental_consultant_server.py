import argparse
import json
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from xtalk import Xtalk
from xtalk.log_utils import mute_other_logging

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

mute_other_logging()

parser = argparse.ArgumentParser(description="Mental Consultant Xtalk Server")
parser.add_argument("--config", type=str, help="Path to the server configuration file")
parser.add_argument("--port", type=int, help="Port number for the server to listen on")
args = parser.parse_args()

app = FastAPI(title="Mental Consultant Xtalk Server")
Xtalk.register_model_search_spec(
    slot="llm_agent",
    spec=Path(__file__).parent / "mental_consultant_agent.py",
)


def build_mental_consultant_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a config copy that swaps in the mental consultant agent."""

    llm_agent_config = config.get("llm_agent")
    if not isinstance(llm_agent_config, dict):
        raise RuntimeError("Configured llm_agent must be an object.")
    llm_agent_params = llm_agent_config.get("params", {})
    if not isinstance(llm_agent_params, dict):
        raise RuntimeError("Configured llm_agent.params must be an object.")

    updated_config = dict(config)
    updated_config["llm_agent"] = {
        **llm_agent_config,
        "type": "MentalConsultantAgent",
        "params": dict(llm_agent_params),
    }
    return updated_config

# Instantiate Xtalk from config
## Read config from json
with open(args.config, "r", encoding="utf-8") as f:
    config = json.load(f)
xtalk_instance = Xtalk.from_config(build_mental_consultant_config(config))
xtalk_instance.mount_routes(app)


# Serve static files
example_server_path = Path(__file__).parent
templates = Jinja2Templates(directory=str(example_server_path / "templates"))
static_root = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_root)), name="static")
try:
    app.mount(
        "/xtalk",
        StaticFiles(
            directory=str(Path(__file__).parent.parent.parent / "frontend" / "dist")
        ),
        name="xtalk",
    )
except Exception:
    print("No local X-Talk frontend library found. You may use the library from CDN.")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port or 11995)
