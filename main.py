import httpx
import asyncio
from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

# インポートの冗長性を排除し、Searchモジュールを整理
try:
    from youtubesearchpython import Search
except ImportError:
    from youtubesearchpython.search import Search

app = FastAPI(title="YStube API")
templates = Jinja2Templates(directory="templates")

# --- Configuration & Auth ---
AUTH_COOKIE = "ys_auth"
AUTH_VALUE = "authenticated_user"
STREAM_API_BASE = "https://yudlp.vercel.app/stream"

def is_auth(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == AUTH_VALUE

# --- Middlewares / Helpers ---
def auth_required(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=303, headers={"Location": "/ys"})

# --- View Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_auth(request):
        return RedirectResponse("/ys")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ys", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_auth(request):
        return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request}) # ログインもテンプレート化を推奨

@app.post("/ys")
async def login_verify(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE, value=AUTH_VALUE, httponly=True, samesite="lax")
        return response
    return RedirectResponse("/ys", status_code=HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def search_view(request: Request, q: str = ""):
    auth_required(request)
    if not q:
        return RedirectResponse("/")
    
    # 検索実行
    results = Search(q, limit=20).result()
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": results.get('result', [])
    })

@app.get("/watch", response_class=HTMLResponse)
async def watch_view(request: Request, v: str = ""):
    auth_required(request)
    if not v:
        return RedirectResponse("/")
    return templates.TemplateResponse("watch.html", {"request": request, "video_id": v})

# --- API Endpoints ---

@app.get("/api/search/more")
async def api_search_more(q: str, offset: int = 1):
    """追加読み込み用: 指定したoffset分までnext()を回して結果を返す"""
    search = Search(q, limit=20)
    for _ in range(offset):
        search.next()
    return search.result()

@app.get("/api/stream/{video_id}")
async def api_stream_proxy(video_id: str):
    """外部APIのJSONレスポンスをそのまま中継するプロキシ"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            target = f"{STREAM_API_BASE}/{video_id}"
            response = await client.get(target)
            response.raise_for_status() # 200番台以外は例外を飛ばす
            return response.json()
        except Exception as e:
            return JSONResponse(
                status_code=502,
                content={"error": "Upstream API Error", "detail": str(e)}
            )

# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(url=exc.headers.get("Location"))
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)

@app.exception_handler(404)
async def not_found_handler(request: Request, _):
    return HTMLResponse("<h1>404 | NOT FOUND</h1>", status_code=404)
