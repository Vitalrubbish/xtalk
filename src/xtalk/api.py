import json
import os
import sys
import hashlib
import importlib
import importlib.util
import uuid
from pathlib import Path
from typing import Callable, Type, Any, Union
from fastapi import (
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    status,
)
from langchain_core.tools import BaseTool

from .auth import JWTAuth, extract_bearer_token, resolve_auth_config
from .persistence import PersistenceStore
from .serving.service_manager import ServiceManager
from .pipelines import Pipeline
from .pipelines.default import DefaultPipeline
from .serving.session_limiter import SessionLimiter
from .serving.events import TextForEmbeddingReady
from .serving.service import Service, DefaultService


# ImportSpec can be a module path string, a file path string, "module:attr_chain",
# a Path object pointing to a .py file, or Path pointing to any file path.
ImportSpec = Union[str, Path]


class Xtalk:
    """Create Xtalk pipelines, services, and session entrypoints.

    Notes
    -----
    ``Xtalk`` is the main integration surface used by the sample applications.
    It builds pipelines from configuration, stores a prototype service, and
    accepts WebSocket sessions on demand.
    """

    # Slot -> ordered import specs
    MODEL_REGISTRY: dict[str, list[ImportSpec]] = {
        "asr": ["xtalk.speech.asr"],
        "llm_agent": ["xtalk.llm_agent"],
        "tts": ["xtalk.speech.tts"],
        "embeddings": ["xtalk.embeddings"],
        "speaker_encoder": ["xtalk.speech.speaker_encoder"],
        "captioner": ["xtalk.speech.captioner"],
        "caption_rewriter": ["xtalk.rewriter"],
        "thought_rewriter": ["xtalk.rewriter"],
        "vad": ["xtalk.speech.vad"],
        "speech_enhancer": ["xtalk.speech.speech_enhancer"],
        "speech_speed_controller": ["xtalk.speech.speech_speed_controller"],
        "turn_detector": ["xtalk.speech.turn_detector"],
    }

    # Cache for file-path modules to avoid re-importing the same file repeatedly
    _FILE_MODULE_CACHE: dict[str, Any] = {}

    def __init__(self, *, service_prototype: Service, max_sessions: int | None = None):
        """Initialize an ``Xtalk`` application wrapper.

        Parameters
        ----------
        service_prototype : Service
            Prototype service used to clone per-session service instances.
        max_sessions : int | None, optional
            Maximum number of concurrent sessions. If omitted, no session limit
            is enforced.
        """
        service_config = dict(service_prototype.service_config)
        data_dir = service_config.get("data_dir") or "data"
        auth_secret, auth_ttl_seconds = resolve_auth_config(service_config)

        self._persistence = PersistenceStore(
            Path(data_dir).expanduser().resolve() / "chat_history.sqlite3"
        )
        self._auth = JWTAuth(secret=auth_secret, ttl_seconds=auth_ttl_seconds)
        self._service_manager = ServiceManager(
            service_prototype=service_prototype,
            persistence_store=self._persistence,
        )
        self._pipeline = service_prototype.pipeline
        self._session_limiter = (
            SessionLimiter(max_sessions) if max_sessions is not None else None
        )

    # -------------------------
    # Public registry APIs
    # -------------------------
    @classmethod
    def register_model_search_spec(
        cls,
        *,
        slot: str,
        spec: ImportSpec,
        prepend: bool = True,
    ) -> None:
        """Register an additional model lookup location for a slot.

        Parameters
        ----------
        slot : str
            Registry slot name such as ``"llm_agent"`` or ``"tts"``.
        spec : ImportSpec
            Import target to try when loading that slot. Supported forms include
            module paths, ``"module:attribute"`` references, and Python file
            paths.
        prepend : bool, default=True
            Whether to try the new spec before existing registered specs.

        Notes
        -----
        Common ``spec`` forms include ``"my_pkg.custom_tts"``,
        ``"my_pkg.custom_tts:registry"``, ``"/abs/path/custom_tts.py"``, and
        ``Path("./custom_tts.py")``.

        Examples
        --------
        >>> Xtalk.register_model_search_spec(
        ...     slot="llm_agent",
        ...     spec="./echo_agent.py",
        ... )
        """
        if not slot:
            raise ValueError("slot must be non-empty")
        if not spec:
            raise ValueError("spec must be non-empty")

        paths = cls.MODEL_REGISTRY.get(slot)
        if paths is None:
            cls.MODEL_REGISTRY[slot] = [spec]
            return

        if spec in paths:
            return

        if prepend:
            paths.insert(0, spec)
        else:
            paths.append(spec)

    # -------------------------
    # Config / construction
    # -------------------------
    @staticmethod
    def _get_config_dict(path_or_dict: str | dict) -> dict:
        if isinstance(path_or_dict, str):
            with open(path_or_dict, "r") as f:
                config = json.load(f)
        else:
            config = path_or_dict
        return config

    @classmethod
    def from_config(cls, path_or_dict: str | dict) -> "Xtalk":
        """Build an ``Xtalk`` instance from configuration data.

        Parameters
        ----------
        path_or_dict : str | dict
            JSON file path or already loaded configuration dictionary.

        Returns
        -------
        Xtalk
            Configured application wrapper backed by a ``DefaultPipeline`` and
            ``DefaultService``.

        Examples
        --------
        >>> xtalk = Xtalk.from_config("server_config.json")
        """
        config = cls._get_config_dict(path_or_dict)
        pipeline = cls._load_pipeline(DefaultPipeline, config)
        service_prototype = DefaultService(
            pipeline=pipeline, service_config=cls._load_service_config(config)
        )
        max_sessions = cls._max_sessions(config)
        return cls(service_prototype=service_prototype, max_sessions=max_sessions)

    @classmethod
    def create_pipeline_from_config(
        cls,
        *,
        pipeline_cls: Type[Pipeline],
        config_path_or_dict: str | dict,
        additional_model_registry: dict[str, Any],
    ) -> Pipeline:
        """Instantiate a custom pipeline class from configuration.

        Parameters
        ----------
        pipeline_cls : Type[Pipeline]
            Concrete pipeline type to instantiate.
        config_path_or_dict : str | dict
            JSON file path or already loaded configuration dictionary.
        additional_model_registry : dict[str, Any]
            Extra slot-to-instance mapping merged on top of the default model
            registry before the pipeline is created.

        Returns
        -------
        Pipeline
            Pipeline instance created from the supplied configuration.

        Examples
        --------
        >>> pipeline = Xtalk.create_pipeline_from_config(
        ...     pipeline_cls=DefaultPipeline,
        ...     config_path_or_dict="server_config.json",
        ...     additional_model_registry={},
        ... )
        """
        config = cls._get_config_dict(config_path_or_dict)
        pipeline = cls._load_pipeline(pipeline_cls, config, additional_model_registry)
        return pipeline

    def set_session_limit(self, limit: int):
        """Set or replace the concurrent session limit.

        Parameters
        ----------
        limit : int
            Maximum number of active sessions allowed at the same time.
        """
        self._session_limiter = SessionLimiter(limit)

    async def embed_text(self, session_id: str, text: str, user_id: str | None = None):
        """Queue text for session-scoped embedding storage.

        Parameters
        ----------
        session_id : str
            Session identifier returned to the frontend.
        text : str
            Text content that should be embedded and persisted for retrieval.

        Raises
        ------
        ValueError
            Raised if the target session does not exist.
        """
        if user_id is not None and not self._persistence.user_owns_session(
            user_id, session_id
        ):
            raise ValueError(f"Session {session_id} not found for user {user_id}.")
        service = self._service_manager.get_service(session_id)
        if service is None:
            raise ValueError(f"Session {session_id} not found.")
        await service.event_bus.publish(
            TextForEmbeddingReady(session_id=session_id, text=text)
        )

    def add_agent_tools(
        self, tools_or_factories: list[BaseTool | Callable[[], BaseTool]]
    ):
        """Attach tools to the prototype agent before sessions are created.

        Parameters
        ----------
        tools_or_factories : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or zero-argument factories that produce tool
            instances.

        Raises
        ------
        RuntimeError
            Raised if at least one service session has already been created.
        """
        if self._service_manager.get_service_count() > 0:
            raise RuntimeError("Cannot add tools after services have been created.")
        self._pipeline.get_agent().add_tools(tools_or_factories)

    def _login(self) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        user = self._persistence.ensure_user(user_id)
        return {
            "access_token": self._auth.issue_token(sub=user_id),
            "user": user,
        }

    def _verify_access_token(self, token: str) -> str:
        user_id = self._auth.verify_token(token)
        self._persistence.ensure_user(user_id)
        return user_id

    def _list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        self._persistence.ensure_user(user_id)
        return self._persistence.list_sessions(user_id)

    def _get_session_detail(self, user_id: str, session_id: str) -> dict[str, Any]:
        self._persistence.ensure_user(user_id)
        return self._persistence.get_session_detail(user_id, session_id)

    def mount_routes(
        self,
        app: Any,
        *,
        login_path: str = "/api/auth/login",
        sessions_path: str = "/api/sessions",
        session_detail_path: str = "/api/sessions/{session_id}",
        upload_path: str = "/api/upload",
        ws_path: str = "/ws",
    ) -> None:
        """Mount the built-in auth, session, upload, and websocket routes."""

        def _require_http_user(request: Request) -> str:
            token = extract_bearer_token(request.headers.get("authorization"))
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing bearer token",
                )
            try:
                return self._verify_access_token(token)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(exc),
                ) from exc

        def _require_ws_user(websocket: WebSocket) -> str:
            token = websocket.query_params.get("access_token")
            if token is None:
                token = extract_bearer_token(websocket.headers.get("authorization"))
            if not token:
                raise ValueError("Missing access token")
            return self._verify_access_token(token)

        @app.post(login_path)
        async def _login_route() -> dict[str, Any]:
            return self._login()

        @app.get(sessions_path)
        async def _list_sessions_route(request: Request) -> dict[str, Any]:
            user_id = _require_http_user(request)
            return {"sessions": self._list_sessions(user_id)}

        @app.get(session_detail_path)
        async def _session_detail_route(
            request: Request, session_id: str
        ) -> dict[str, Any]:
            user_id = _require_http_user(request)
            try:
                return self._get_session_detail(user_id, session_id)
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
                ) from exc

        @app.post(upload_path)
        async def _upload_route(
            request: Request,
            session_id: str = Form(...),
            file: UploadFile = File(...),
        ) -> dict[str, str]:
            user_id = _require_http_user(request)
            content_type = (file.content_type or "").lower()
            is_text = content_type.startswith("text/") if content_type else False
            if content_type and not is_text:
                raise HTTPException(
                    status_code=400, detail="Only text files are supported."
                )
            text = (await file.read()).decode("utf-8", errors="ignore")
            try:
                await self.embed_text(session_id=session_id, text=text, user_id=user_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return {"status": "ok"}

        @app.websocket(ws_path)
        async def _websocket_route(websocket: WebSocket) -> None:
            try:
                user_id = _require_ws_user(websocket)
            except ValueError:
                await websocket.accept()
                await websocket.close(code=1008, reason="Unauthorized")
                return
            await self.connect(websocket, user_id=user_id)

    async def connect(self, websocket: WebSocket, user_id: str | None = None):
        """Accept a WebSocket session and hand it to the service manager.

        Parameters
        ----------
        websocket : WebSocket
            FastAPI WebSocket connection from the client.
        user_id : str | None, optional
            Authenticated user identifier. When omitted, the connection falls
            back to the legacy connection-scoped session behavior.

        Notes
        -----
        If a session limit is configured, the socket is first admitted through
        the session limiter queue.
        """
        if self._session_limiter:
            await websocket.accept()
            waiter = await self._session_limiter.acquire(websocket)
            if waiter is None:
                try:
                    await websocket.close(code=1000)
                except Exception:
                    pass
                return
            await self._service_manager.connect(
                websocket=websocket, already_accepted=True, user_id=user_id
            )
            await self._session_limiter.release(waiter)
            return

        await self._service_manager.connect(websocket=websocket, user_id=user_id)

    @staticmethod
    def _max_sessions(config: dict):
        if "max_connections" in config:
            try:
                return int(config["max_connections"])
            except Exception:
                pass
        return None

    @staticmethod
    def _load_service_config(config: dict):
        return config.get("service_config", {})

    @classmethod
    def _load_pipeline(
        cls,
        pipeline_cls: Type[Pipeline],
        config: dict,
        additional_model_registry: dict | None = None,
    ):
        model_map: dict[str, Any] = {}
        for slot, specs in cls.MODEL_REGISTRY.items():
            model_map[slot] = cls._init_model(
                model_config=config.get(slot, {}),
                import_specs=specs,
            )

        if additional_model_registry:
            model_map = model_map | additional_model_registry

        return pipeline_cls(**model_map)

    # -------------------------
    # Dynamic importing helpers
    # -------------------------
    @staticmethod
    def _normalize_import_spec(spec: ImportSpec) -> str:
        """
        Normalize ImportSpec into a string.

        - Path -> expanded, resolved, absolute filesystem path
        - str  -> returned as-is
        """
        if isinstance(spec, Path):
            return str(spec.expanduser().resolve())
        if isinstance(spec, str):
            return spec
        raise TypeError(f"Invalid ImportSpec type: {type(spec)}")

    @staticmethod
    def _looks_like_file_path(spec: ImportSpec) -> bool:
        """
        Heuristic: treat as file path if it ends with .py or contains a path separator
        or starts with '.' (relative) or is absolute.

        Notes:
          - A Path object is always treated as a file path.
        """
        if isinstance(spec, Path):
            return True

        if not isinstance(spec, str):
            return False

        if spec.endswith(".py"):
            return True
        if os.path.isabs(spec):
            return True
        if (
            spec.startswith("." + os.sep)
            or spec.startswith(".." + os.sep)
            or spec.startswith("./")
            or spec.startswith("../")
        ):
            return True
        if os.sep in spec or (os.altsep and os.altsep in spec):
            return True
        return False

    @classmethod
    def _import_from_file(cls, file_path: str):
        """
        Import a module from a Python file path.

        Notes:
          - Uses a deterministic synthetic module name based on the absolute path.
          - Caches the imported module to avoid repeated loads.
          - If you edit the file during runtime and want reload behavior, you can
            clear Xtalk._FILE_MODULE_CACHE[file_abs] manually.
        """
        file_abs = os.path.abspath(file_path)
        if not os.path.exists(file_abs):
            raise FileNotFoundError(f"Python file not found: {file_abs}")

        if file_abs in cls._FILE_MODULE_CACHE:
            return cls._FILE_MODULE_CACHE[file_abs]

        digest = hashlib.sha256(file_abs.encode("utf-8")).hexdigest()[:16]
        module_name = f"xtalk_userfile_{digest}"

        spec = importlib.util.spec_from_file_location(module_name, file_abs)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for file: {file_abs}")

        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules so relative imports inside that file can work (best-effort)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        cls._FILE_MODULE_CACHE[file_abs] = module
        return module

    @staticmethod
    def _resolve_attr_chain(obj: Any, chain: str) -> Any:
        """Resolve 'a.b.c' on an object/module."""
        cur = obj
        for part in chain.split("."):
            cur = getattr(cur, part)
        return cur

    @classmethod
    def _import_candidate(cls, spec: ImportSpec):
        """
        Import a candidate specified by:
          - module path: "my_pkg.mod"
          - module + attr chain: "my_pkg.mod:some.subobj"
          - file path: "/path/to/file.py"
          - file + attr chain: "/path/to/file.py:some.subobj"
          - Path("/path/to/file.py")
        Returns the resolved module/object.
        """
        spec_str = cls._normalize_import_spec(spec)

        if ":" in spec_str:
            base, attr_chain = spec_str.split(":", 1)
            base_obj = cls._import_candidate(base)
            return cls._resolve_attr_chain(base_obj, attr_chain)

        if cls._looks_like_file_path(spec):
            return cls._import_from_file(spec_str)

        # Fully-qualified module import
        return importlib.import_module(spec_str)

    # -------------------------
    # Model initialization
    # -------------------------
    @classmethod
    def _init_model(cls, model_config: dict | str, import_specs: list[ImportSpec]):
        if not model_config:
            return None

        if isinstance(model_config, dict) and "type" not in model_config:
            raise ValueError("Model config must contain 'type' field.")

        model_type = (
            model_config["type"] if isinstance(model_config, dict) else model_config
        )
        model_params = (
            model_config.get("params", {}) if isinstance(model_config, dict) else {}
        )

        errors: list[str] = []
        for spec in import_specs:
            try:
                container = cls._import_candidate(spec)
            except Exception as e:
                errors.append(f"{spec!r} import failed: {e!r}")
                continue

            # Convention: model classes are exported as attributes on the imported module/object
            model_class = getattr(container, model_type, None)
            if model_class is None:
                continue
            if not isinstance(model_class, type):
                errors.append(
                    f"{spec!r} has attribute {model_type!r} but it is not a class"
                )
                continue

            return model_class(**model_params)

        detail = "\n  - " + "\n  - ".join(errors) if errors else ""
        raise ValueError(
            f"Model class {model_type!r} not found. Tried specs: {import_specs}.{detail}"
        )
