from pathlib import Path
import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from collections import deque
from urllib.parse import unquote
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .flow_analyzer import analyze
from .java_parser import parse_project, endpoints
from .project_discovery import discover_projects, swagger_info
from .analyzer.semantic.catalog import semantic_catalog, semantic_rules_catalog, responsibilities_catalog
from .analyzer.semantic.endpoint_intent import INTENT_MAPPINGS
from .analyzer.semantic.operation_classifier import OPERATION_MAPPINGS
from .analyzer.maturity_catalog import maturity_dimensions_catalog
from .analyzer.maturity_evaluator import consolidate, evaluate_dimension
from .analyzer.maturity_cache import MaturityCache
from .analyzer.capacity import CapacityInput, analyze_capacity
from .spoon_bridge import engine_status
from .microservice_xray import analyze_microservice
from .architecture_detector import detect_architecture
from .maturity_report import build_maturity_report
from .project_upload import MAX_ARCHIVE_BYTES, extract_project_zip, extract_project_zip_file


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
app = FastAPI(title="EXPERT CODE FLOW", version="0.1.0")
maturity_cache = MaturityCache(ROOT / ".cache" / "maturity")
project_upload_root = ROOT / ".uploads" / "projects"

# Autenticação simples para o MVP. A senha permanece somente no backend.
AUTH_USERNAME = "admin"
AUTH_PASSWORD = ""
AUTH_COOKIE = "codeflow_session"
PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/health"}
auth_sessions: dict[str, dict[str, float]] = {}
uploaded_projects_by_session: dict[str, dict] = {}
chunk_uploads: dict[str, dict] = {}
chunk_upload_root = ROOT / ".uploads" / "chunks"
MAX_CHUNK_BYTES = 10 * 1024 * 1024
ENDPOINT_ANALYSIS_TIMEOUT_SECONDS = 120
SWAGGER_ENABLED = False
active_endpoint_scans: dict[str, asyncio.subprocess.Process] = {}
cancelled_endpoint_scans: set[str] = set()
processing_events = deque(maxlen=80)
api_events = deque(maxlen=120)
last_endpoint_processing: dict | None = None

log_root = ROOT / "logs"
log_root.mkdir(parents=True, exist_ok=True)
api_logger = logging.getLogger("expert_code_flow.api")
if not api_logger.handlers:
    api_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_root / "api.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    api_logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    api_logger.addHandler(stream_handler)
api_logger.propagate = False


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(AUTH_COOKIE, "")
    return bool(token and token in auth_sessions)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _remember_api_event(event: dict) -> None:
    api_events.appendleft({"timestamp": _utc_now_iso(), **event})


def _remember_processing_event(event: dict) -> None:
    processing_events.appendleft({"timestamp": _utc_now_iso(), **event})


@app.middleware("http")
async def log_api_requests(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    api_logger.info(
        "api.start id=%s method=%s path=%s query=%s client=%s",
        request_id, request.method, request.url.path, request.url.query or "-",
        request.client.host if request.client else "-",
    )
    try:
        response = await call_next(request)
    except Exception:
        api_logger.exception(
            "api.error id=%s method=%s path=%s elapsed_ms=%.0f",
            request_id, request.method, request.url.path, (time.perf_counter() - started) * 1000,
        )
        _remember_api_event({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "error": "Erro interno na API",
        })
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.0f}"
    api_logger.info(
        "api.end id=%s method=%s path=%s status=%s elapsed_ms=%.0f",
        request_id, request.method, request.url.path, response.status_code, elapsed_ms,
    )
    _remember_api_event({
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "elapsed_ms": round(elapsed_ms),
    })
    return response

@app.middleware("http")
async def require_authentication(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    if _is_authenticated(request):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Autenticação necessária"}, status_code=401)
    return RedirectResponse(url="/login", status_code=303)


@app.middleware("http")
async def disable_local_ui_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


class FlowRequest(BaseModel):
    project_path: str
    http_method: str | None = None
    endpoint: str
    diagram_type: str = "INTERNAL"
    detail_level: str = "ARCHITECTURAL"
    analysis_engine: str = "python-legacy"


class MaturityDimensionRequest(BaseModel):
    project_path: str
    dimension_id: str


class MaturityConsolidationRequest(BaseModel):
    results: list[dict]


class MaturityCacheRequest(BaseModel):
    report: dict


class MaturityReportRequest(BaseModel):
    report: dict


class LoginRequest(BaseModel):
    username: str
    password: str


class UploadInitRequest(BaseModel):
    filename: str
    size: int


class UploadFinishRequest(BaseModel):
    upload_id: str


@app.get("/login")
def login_page(request: Request):
    if _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return FileResponse(FRONTEND / "login.html")


@app.post("/api/auth/login")
def login(request: LoginRequest, http_request: Request):
    valid_user = hmac.compare_digest(request.username, AUTH_USERNAME)
    valid_password = hmac.compare_digest(request.password, AUTH_PASSWORD)
    if not (valid_user and valid_password):
        raise HTTPException(401, "Usuário ou senha inválidos")
    token = secrets.token_urlsafe(32)
    auth_sessions[token] = {"authenticated": True}
    response = JSONResponse({"authenticated": True, "username": AUTH_USERNAME})
    is_https = (
        http_request.url.scheme == "https"
        or http_request.headers.get("x-forwarded-proto", "").lower() == "https"
    )
    response.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/auth/logout")
def logout(request: Request):
    token = request.cookies.get(AUTH_COOKIE, "")
    if token:
        auth_sessions.pop(token, None)
        uploaded_projects_by_session.pop(token, None)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(AUTH_COOKIE, path="/")
    return response


@app.get("/api/health")
def health(): return {"status": "ok", "version": "0.1.0"}


@app.get("/api/status")
def system_status():
    spoon = engine_status()
    recent_errors = [event for event in api_events if int(event.get("status", 0)) >= 400]
    active_uploads = len(chunk_uploads)
    components = [
        {"id": "api", "name": "API FastAPI", "status": "ok", "detail": "Respondendo em memoria", "metric": f"{len(api_events)} req. recentes"},
        {"id": "auth", "name": "Sessoes", "status": "ok", "detail": "Autenticacao local ativa", "metric": f"{len(auth_sessions)} sessao(oes)"},
        {"id": "endpoint-worker", "name": "Worker de endpoints", "status": "busy" if active_endpoint_scans else "ok", "detail": "Processamento isolado por subprocesso", "metric": f"{len(active_endpoint_scans)} ativo(s)"},
        {"id": "uploads", "name": "Upload em blocos", "status": "busy" if active_uploads else "ok", "detail": "Estado temporario somente em memoria", "metric": f"{active_uploads} upload(s) ativo(s)"},
        {"id": "spoon", "name": "Spoon + SootUp", "status": "ok" if spoon.get("available") else "warning", "detail": spoon.get("detail") or spoon.get("label") or "Motor estrutural", "metric": "disponivel" if spoon.get("available") else "indisponivel"},
        {"id": "errors", "name": "Erros recentes", "status": "warning" if recent_errors else "ok", "detail": "Requisicoes HTTP com falha no buffer atual", "metric": str(len(recent_errors))},
    ]
    return {
        "generated_at": _utc_now_iso(),
        "version": app.version,
        "storage": "memory-only",
        "components": components,
        "active_endpoint_scans": list(active_endpoint_scans.keys()),
        "last_processing": last_endpoint_processing,
        "processing_events": list(processing_events)[:30],
        "api_events": list(api_events)[:40],
    }


@app.get("/api/analysis/engines")
def analysis_engines():
    return {"default": "python-legacy", "selection": "per-request", "engines": [
        {"id": "python-legacy", "enabled": True, "available": True, "mode": "authoritative"},
        engine_status(),
    ]}


@app.get("/api/projects")
def projects(root: str = Query(...)):
    try: return {"root": str(Path(root).resolve()), "projects": discover_projects(root)}
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.post("/api/projects/upload")
async def upload_projects(request: Request):
    filename = unquote(request.headers.get("x-filename", "projeto.zip"))
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_ARCHIVE_BYTES:
        raise HTTPException(413, "O pacote ZIP excede o limite de 300 MB")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise HTTPException(413, "O pacote ZIP excede o limite de 300 MB")
    try:
        root = extract_project_zip(bytes(data), filename, project_upload_root)
        found = discover_projects(str(root))
        if not found:
            shutil.rmtree(root, ignore_errors=True)
            raise ValueError("Nenhum projeto Spring Boot foi encontrado no pacote ZIP")
        result = {"source": "upload", "filename": filename, "root": str(root), "projects": found}
        uploaded_projects_by_session[request.cookies[AUTH_COOKIE]] = result
        return result
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/projects/upload/init")
def init_chunk_upload(payload: UploadInitRequest):
    filename = Path(payload.filename).name
    if not filename.lower().endswith(".zip"):
        raise HTTPException(400, "Selecione um arquivo com extensão .zip")
    if payload.size <= 0 or payload.size > MAX_ARCHIVE_BYTES:
        raise HTTPException(413, "O pacote ZIP excede o limite de 300 MB")
    chunk_upload_root.mkdir(parents=True, exist_ok=True)
    upload_id = uuid.uuid4().hex
    archive_path = chunk_upload_root / f"{upload_id}.zip"
    archive_path.touch(exist_ok=False)
    chunk_uploads[upload_id] = {
        "filename": filename,
        "size": payload.size,
        "received": 0,
        "next_index": 0,
        "path": archive_path,
        "created_at": time.time(),
    }
    return {"upload_id": upload_id, "chunk_size": 8 * 1024 * 1024}


@app.post("/api/projects/upload/chunk")
async def upload_project_chunk(request: Request, upload_id: str = Query(...), index: int = Query(...)):
    state = chunk_uploads.get(upload_id)
    if not state:
        raise HTTPException(404, "Upload não encontrado ou expirado")
    if index != state["next_index"]:
        raise HTTPException(409, "Bloco recebido fora de ordem")
    chunk = bytearray()
    async for part in request.stream():
        chunk.extend(part)
        if len(chunk) > MAX_CHUNK_BYTES:
            raise HTTPException(413, "Bloco de upload acima do limite permitido")
    if not chunk or state["received"] + len(chunk) > state["size"]:
        raise HTTPException(400, "Tamanho de upload inconsistente")
    with state["path"].open("ab") as target:
        target.write(chunk)
    state["received"] += len(chunk)
    state["next_index"] += 1
    return {"received": state["received"], "size": state["size"]}


@app.post("/api/projects/upload/finish")
def finish_chunk_upload(payload: UploadFinishRequest, request: Request):
    state = chunk_uploads.pop(payload.upload_id, None)
    if not state:
        raise HTTPException(404, "Upload não encontrado ou expirado")
    archive_path: Path = state["path"]
    try:
        if state["received"] != state["size"]:
            raise ValueError("O upload não foi concluído integralmente")
        root = extract_project_zip_file(archive_path, state["filename"], project_upload_root)
        found = discover_projects(str(root))
        if not found:
            shutil.rmtree(root, ignore_errors=True)
            raise ValueError("Nenhum projeto Spring Boot foi encontrado no pacote ZIP")
        result = {"source": "upload", "filename": state["filename"], "root": str(root), "projects": found}
        uploaded_projects_by_session[request.cookies[AUTH_COOKIE]] = result
        return result
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        archive_path.unlink(missing_ok=True)


@app.get("/api/projects/upload/current")
def current_uploaded_project(request: Request):
    token = request.cookies.get(AUTH_COOKIE, "")
    context = uploaded_projects_by_session.get(token)
    if not context:
        return {"available": False}
    if not Path(context["root"]).is_dir():
        uploaded_projects_by_session.pop(token, None)
        return {"available": False}
    return {"available": True, **context}


async def _scan_endpoints_in_worker(project: Path, analysis_id: str) -> dict:
    global last_endpoint_processing
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    started_at = _utc_now_iso()
    processing_record = {
        "analysis_id": analysis_id,
        "type": "endpoint-scan",
        "project": str(project),
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "duration_ms": None,
        "pid": None,
        "endpoints": None,
        "worker_log": "",
        "error": "",
    }
    last_endpoint_processing = processing_record
    _remember_processing_event({"analysis_id": analysis_id, "level": "info", "message": "Iniciando varredura de endpoints", "project": str(project)})
    started_perf = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "backend.endpoint_worker", str(project),
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=creationflags,
    )
    processing_record["pid"] = process.pid
    active_endpoint_scans[analysis_id] = process
    api_logger.info("endpoint.scan.start id=%s pid=%s project=%s timeout_s=%s", analysis_id, process.pid, project, ENDPOINT_ANALYSIS_TIMEOUT_SECONDS)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=ENDPOINT_ANALYSIS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        api_logger.error("endpoint.scan.timeout id=%s pid=%s project=%s", analysis_id, process.pid, project)
        processing_record.update({"status": "timeout", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "error": f"Timeout apos {ENDPOINT_ANALYSIS_TIMEOUT_SECONDS} segundos"})
        _remember_processing_event({"analysis_id": analysis_id, "level": "error", "message": processing_record["error"], "project": str(project)})
        raise HTTPException(504, f"A análise excedeu {ENDPOINT_ANALYSIS_TIMEOUT_SECONDS} segundos e foi encerrada. Consulte logs/api.log.") from exc
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
            await process.communicate()
        api_logger.warning("endpoint.scan.disconnected id=%s pid=%s project=%s", analysis_id, process.pid, project)
        processing_record.update({"status": "cancelled", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "error": "Cliente desconectado durante a analise"})
        _remember_processing_event({"analysis_id": analysis_id, "level": "warning", "message": processing_record["error"], "project": str(project)})
        raise
    finally:
        if active_endpoint_scans.get(analysis_id) is process:
            active_endpoint_scans.pop(analysis_id, None)
    worker_log = stderr.decode("utf-8", errors="replace").strip()
    if worker_log:
        api_logger.info("endpoint.scan.worker id=%s %s", analysis_id, worker_log.replace("\n", " | "))
        processing_record["worker_log"] = worker_log
        _remember_processing_event({"analysis_id": analysis_id, "level": "info", "message": worker_log, "project": str(project)})
    if analysis_id in cancelled_endpoint_scans:
        cancelled_endpoint_scans.discard(analysis_id)
        api_logger.warning("endpoint.scan.cancel-confirmed id=%s pid=%s", analysis_id, process.pid)
        processing_record.update({"status": "cancelled", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "error": "Analise cancelada pelo usuario"})
        _remember_processing_event({"analysis_id": analysis_id, "level": "warning", "message": processing_record["error"], "project": str(project)})
        raise HTTPException(409, "Análise cancelada pelo usuário")
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        api_logger.error("endpoint.scan.invalid-output id=%s stdout=%r", analysis_id, stdout[-1000:])
        processing_record.update({"status": "error", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "error": "O worker retornou uma resposta invalida", "worker_log": worker_log})
        _remember_processing_event({"analysis_id": analysis_id, "level": "error", "message": processing_record["error"], "project": str(project)})
        raise HTTPException(500, "O analisador retornou uma resposta inválida. Consulte logs/api.log.") from exc
    if process.returncode != 0:
        processing_record.update({"status": "error", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "error": payload.get("error") or "Falha ao analisar os endpoints", "worker_log": worker_log})
        _remember_processing_event({"analysis_id": analysis_id, "level": "error", "message": processing_record["error"], "project": str(project)})
        raise HTTPException(400, payload.get("error") or "Falha ao analisar os endpoints")
    api_logger.info("endpoint.scan.end id=%s pid=%s project=%s endpoints=%s", analysis_id, process.pid, project, len(payload.get("endpoints", [])))
    processing_record.update({"status": "ok", "finished_at": _utc_now_iso(), "duration_ms": round((time.perf_counter() - started_perf) * 1000), "endpoints": len(payload.get("endpoints", []))})
    _remember_processing_event({"analysis_id": analysis_id, "level": "info", "message": f"Varredura concluida com {processing_record['endpoints']} endpoint(s)", "project": str(project)})
    return payload


@app.get("/api/endpoints")
async def list_endpoints(project: str = Query(...), analysis_id: str | None = Query(None)):
    resolved = Path(project).resolve()
    if not resolved.is_dir():
        raise HTTPException(400, "Diretório do microsserviço não encontrado")
    operation_id = analysis_id or uuid.uuid4().hex
    return await _scan_endpoints_in_worker(resolved, operation_id)



@app.post("/api/analysis/cancel")
async def cancel_analysis(analysis_id: str = Query(...)):
    process = active_endpoint_scans.get(analysis_id)
    if not process or process.returncode is not None:
        return {"analysis_id": analysis_id, "cancelled": False, "detail": "Análise não está ativa"}
    process.kill()
    await process.wait()
    cancelled_endpoint_scans.add(analysis_id)
    active_endpoint_scans.pop(analysis_id, None)
    api_logger.warning("endpoint.scan.cancelled id=%s pid=%s", analysis_id, process.pid)
    _remember_processing_event({"analysis_id": analysis_id, "level": "warning", "message": "Cancelamento solicitado pelo usuario"})
    return {"analysis_id": analysis_id, "cancelled": True}


@app.get("/api/project-profile")
def project_profile(project: str = Query(...)):
    try:
        types = parse_project(Path(project).resolve())
        return {"project": project, "architecture": detect_architecture(types), "java_types": len(types), "endpoints": len(endpoints(types))}
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/api/swagger-info")
def get_swagger_info(project: str = Query(...)):
    if not SWAGGER_ENABLED:
        raise HTTPException(503, "Swagger temporariamente desativado")
    try: return swagger_info(project)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc

@app.get("/api/microservice-xray")
def microservice_xray(project: str = Query(...)):
    try: return analyze_microservice(project)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/api/semantic/catalog")
def get_semantic_catalog(): return semantic_catalog()


@app.get("/api/semantic/rules")
def get_semantic_rules(): return {"rules": semantic_rules_catalog()}


@app.get("/api/semantic/responsibilities")
def get_semantic_responsibilities(): return {"responsibilities": responsibilities_catalog()}


@app.get("/api/semantic/intent-mappings")
def get_intent_mappings(): return {"mappings": INTENT_MAPPINGS}


@app.get("/api/semantic/operation-mappings")
def get_operation_mappings(): return {"mappings": OPERATION_MAPPINGS}


@app.get("/api/maturity/dimensions")
def get_maturity_dimensions(): return maturity_dimensions_catalog()


@app.post("/api/maturity/evaluate-dimension")
def post_evaluate_maturity_dimension(request: MaturityDimensionRequest):
    try: return evaluate_dimension(request.project_path, request.dimension_id)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.post("/api/maturity/consolidate")
def post_consolidate_maturity(request: MaturityConsolidationRequest): return consolidate(request.results)


@app.post("/api/maturity/cache")
def cache_maturity_report(request: MaturityCacheRequest):
    try: return maturity_cache.save(request.report)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/api/maturity/cache/latest")
def latest_maturity_report(project_path: str | None = Query(None)):
    report = maturity_cache.latest(project_path)
    if not report: raise HTTPException(404, "Nenhuma avaliação de maturidade armazenada no cache")
    return report


@app.post("/api/maturity/report-pdf")
def maturity_report_pdf(request: MaturityReportRequest):
    context = request.report.get("context") or {}
    project_path = context.get("project_path")
    if not project_path:
        raise HTTPException(400, "O relatorio de maturidade nao possui o caminho do microservico")
    try:
        xray = analyze_microservice(project_path)
        target = build_maturity_report(request.report, xray, ROOT / "output" / "pdf")
        return FileResponse(target, media_type="application/pdf", filename=target.name)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/flow")
def flow(project: str = Query(...), endpoint: str = Query(...), analysis_engine: str = Query("python-legacy")):
    try: return analyze(project, endpoint, analysis_engine)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.post("/api/capacity/analyze")
def post_capacity_analysis(request: CapacityInput):
    try: return analyze_capacity(request)
    except (ValueError, OSError) as exc: raise HTTPException(400, str(exc)) from exc


@app.post("/api/flow")
def create_flow(request: FlowRequest):
    if request.diagram_type not in {"INTERNAL", "SERVICE"}:
        raise HTTPException(400, "diagram_type deve ser INTERNAL ou SERVICE")
    if request.detail_level not in {"ARCHITECTURAL", "TECHNICAL"}:
        raise HTTPException(400, "detail_level deve ser ARCHITECTURAL ou TECHNICAL")
    try:
        result = analyze(request.project_path, request.endpoint, request.analysis_engine)
        result["diagram_type"] = request.diagram_type
        result["detail_level"] = request.detail_level
        result["mermaid"] = (result["technical_mermaid"] if request.detail_level == "TECHNICAL"
                             else result["architectural_mermaid"])
        return result
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/")
def index(): return FileResponse(FRONTEND / "index.html")


@app.get("/fluxos")
def flow_models_page(): return FileResponse(FRONTEND / "fluxos.html")


@app.get("/camada-semantica")
def semantic_layer_page(): return FileResponse(FRONTEND / "camada-semantica.html")


@app.get("/avaliacao-maturidade")
def maturity_assessment_page(): return FileResponse(FRONTEND / "avaliacao-maturidade.html")


@app.get("/dimensoes-analise")
def maturity_dimensions_page(): return FileResponse(FRONTEND / "dimensoes-analise.html")


@app.get("/auditoria-maturidade")
def maturity_audit_page(): return FileResponse(FRONTEND / "auditoria-maturidade.html")


@app.get("/avaliacao-capacity")
def capacity_assessment_page(): return FileResponse(FRONTEND / "avaliacao-capacity.html")


@app.get("/performance")
def performance_page(): return FileResponse(FRONTEND / "performance.html")


@app.get("/status")
def status_page(): return FileResponse(FRONTEND / "status.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


