from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from youtubesearchpython import AsyncSearch
import starlette.status as status

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
    # ログイン画面のデザイン（簡易版）
    return HTMLResponse("""
        <style>
            body { background: #05070a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: sans-serif; margin: 0; }
            form { text-align: center; background: rgba(255,255,255,0.05); padding: 40px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); }
            input { background: transparent; border: 1px solid #00d4ff; padding: 12px; color: white; border-radius: 8px; outline: none; width: 200px; margin-bottom: 20px; display: block; }
            button { background: #00d4ff; border: none; padding: 10px 30px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s; }
            button:hover { opacity: 0.8; box-shadow: 0 0 15px #00d4ff; }
        </style>
        <form method="post">
            <h2 style="font-weight:200; letter-spacing:5px;">YSTUBE</h2>
            <input type="password" name="passcode" placeholder="Passcode" autofocus>
            <button type="submit">ENTER</button>
        </form>
    """)

@app.post("/ys")
async def ys_verify(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE_NAME, value=AUTH_SECRET_VALUE, httponly=True, samesite="lax")
        return response
    return RedirectResponse(url="/ys", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    if not is_authenticated(request):
        return RedirectResponse(url="/ys")
    
    if not q:
        return RedirectResponse(url="/")

    # AsyncSearchを使用（httpxの引数エラーを回避しやすい）
    search_provider = AsyncSearch(q, limit=20)
    search_results = await search_provider.result()
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": search_results.get('result', [])
    })

# --- Error Handlers ---

@app.exception_handler(404)
async def handler_404(request: Request, _):
    return HTMLResponse("<body style='background:#05070a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;'><h1>404 | Not Found</h1></body>", status_code=404)

# 定義されていないすべてのルートを404へ
@app.api_route("/{path_name:path}", methods=["GET", "POST"])
async def catch_all(request: Request, path_name: str):
    raise HTTPException(status_code=404)
