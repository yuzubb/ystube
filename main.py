from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import starlette.status as status
import os

# ライブラリのインポートエラーを物理的に回避する
try:
    from youtubesearchpython import Search
except ImportError:
    # 構造的にパスが通っていない場合、内部ディレクトリから直接取得を試みる
    try:
        from youtubesearchpython.search import Search
    except ImportError:
        # 最終手段（環境により異なるため）
        Search = None

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 認証設定
AUTH_COOKIE_NAME = "ys_auth"
AUTH_SECRET_VALUE = "authenticated_user"

def is_authenticated(request: Request):
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_SECRET_VALUE

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/ys")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ys", response_class=HTMLResponse)
async def ys_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/")
    return HTMLResponse("""
        <form method="post">
            <input type="password" name="passcode" placeholder="ACCESS CODE" autofocus>
            <button type="submit">UNLOCK</button>
        </form>
    """)

@app.post("/ys")
async def ys_verify(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        # samesite=Lax は開発環境・本番環境両方で安定します
        response.set_cookie(key=AUTH_COOKIE_NAME, value=AUTH_SECRET_VALUE, httponly=True, samesite="lax")
        return response
    return RedirectResponse(url="/ys", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    if not is_authenticated(request):
        return RedirectResponse(url="/ys")
    
    if not q:
        return RedirectResponse(url="/")

    if Search is None:
        return HTMLResponse("Search module not found. Check requirements.", status_code=500)

    try:
        # Search(q) は内部で同期通信を行うが、
        # httpx==0.24.1 を使っていれば proxies エラーは出ない
        search_provider = Search(q, limit=20)
        search_results = search_provider.result()
        
        return templates.TemplateResponse("search.html", {
            "request": request,
            "query": q,
            "results": search_results.get('result', [])
        })
    except Exception as e:
        return HTMLResponse(f"Search Error: {str(e)}", status_code=500)

# --- Error Handlers ---

@app.exception_handler(404)
async def handler_404(request: Request, _):
    return HTMLResponse("<body style='background:#05070a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><h2 style='font-weight:200;letter-spacing:5px;'>404 | NOT FOUND</h2></body>", status_code=404)
