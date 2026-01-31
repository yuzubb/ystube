from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from youtubesearchpython import VideosSearch
import starlette.status as status

app = FastAPI()
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE_NAME = "ys_auth"
AUTH_SECRET_VALUE = "authenticated_user"

# --- 認証チェック用関数 ---
def is_authenticated(request: Request):
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_SECRET_VALUE

# --- ルート設定 ---

# 検索画面
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return templates.TemplateResponse("index.html", {"request": request})

# 認証用ルート
@app.get("/ys", response_class=HTMLResponse)
async def ys_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/")
    return HTMLResponse("""
        <form method="post">
            <input type="text" name="passcode" placeholder="Enter code..." autofocus>
            <button type="submit">Verify</button>
        </form>
    """)

@app.post("/ys")
async def ys_verify(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE_NAME, value=AUTH_SECRET_VALUE, httponly=True)
        return response
    else:
        raise HTTPException(status_code=401, detail="Invalid code")

# 検索処理ルート
@app.get("/search")
async def search(request: Request, q: str = ""):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    
    videos_search = VideosSearch(q, limit=10)
    results = videos_search.result()
    
    return {"query": q, "results": results['result']}

# --- エラーハンドリング ---

@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return HTMLResponse("<h1>404 - Page Not Found</h1>", status_code=404)

@app.exception_handler(401)
async def custom_401_handler(request: Request, __):
    return HTMLResponse("<h1>401 - Unauthorized</h1><p>Access Denied. Please verify at /ys</p>", status_code=401)
