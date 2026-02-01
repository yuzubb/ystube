import json
import httpx
import urllib.parse
import datetime
import concurrent.futures
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

# --- Configuration & Constants ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE = "ys_auth"
AUTH_VALUE = "authenticated_user"

# API Base URLs
DETAILS_API_BASE = "https://siawaseok.duckdns.org/api/video2"
STREAM_API_BASE = "https://yudlp.vercel.app/stream"

# 参考コードに基づいたコメント用インスタンスリスト
COMMENT_API_INSTANCES = [
    'https://invidious.lunivers.trade/',
    'https://invidious.ducks.party/',
    'https://super8.absturztau.be/',
    'https://invidious.nikkosphere.com/',
    'https://yt.omada.cafe/',
    'https://iv.melmac.space/',
    'https://iv.duti.dev/',
]

# --- Helpers ---

def is_auth(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == AUTH_VALUE

async def verify_auth(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=303, headers={"Location": "/ys"})

async def fetch_json(url: str, timeout: float = 10.0):
    """共通のGETリクエスト用ヘルパー"""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36'}
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
    return None

async def request_invidious_parallel(path: str, instances: list):
    """複数インスタンスに並列リクエストを送り、最初に成功したものを返す"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36'}
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # すべてのインスタンスに対してタスクを作成
        tasks = [client.get(f"{api}api/v1{path}", headers=headers) for api in instances]
        
        # 最初に完了した成功レスポンスを待つ
        for future in asyncio.as_completed(tasks):
            try:
                response = await future
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue
    return None

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def view_index(request: Request):
    if not is_auth(request): return RedirectResponse("/ys")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ys", response_class=HTMLResponse)
async def view_login(request: Request):
    if is_auth(request): return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/ys")
async def action_login(passcode: str = Form(...)):
    if passcode == "yuzu": # 参考コードのコード「yuzu」に合わせました
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE, value=AUTH_VALUE, httponly=True)
        return response
    return RedirectResponse("/ys", status_code=HTTP_303_SEE_OTHER)

@app.get("/watch", response_class=HTMLResponse)
async def view_watch(request: Request, v: str, _=Depends(verify_auth)):
    return templates.TemplateResponse("watch.html", {"request": request, "video_id": v})

# --- API Endpoints ---

@app.get("/api/details/{video_id}")
async def api_video_details(video_id: str):
    data = await fetch_json(f"{DETAILS_API_BASE}/{video_id}?depth=1")
    return data if data else JSONResponse(status_code=502, content={"error": "Failed to fetch details"})

@app.get("/api/comments/{video_id}")
async def api_get_comments(video_id: str):
    """
    参考コードのロジックを非同期並列リクエストで再現
    """
    path = f"/comments/{urllib.parse.quote(video_id)}"
    data = await request_invidious_parallel(path, COMMENT_API_INSTANCES)
    
    if not data or "comments" not in data:
        return JSONResponse(status_code=502, content={"error": "All Invidious instances failed"})

    # 参考コードの整形ロジックをそのまま適用
    try:
        return [
            {
                "author": i["author"],
                "authoricon": i["authorThumbnails"][-1]["url"] if i.get("authorThumbnails") else "",
                "authorid": i["authorId"],
                "body": i["contentHtml"].replace("\n", "<br>")
            } 
            for i in data["comments"]
        ]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Data formatting failed"})

@app.get("/api/stream/{video_id}")
async def api_proxy_stream_json(video_id: str):
    data = await fetch_json(f"{STREAM_API_BASE}/{video_id}")
    return data if data else JSONResponse(status_code=502, content={"error": "Failed to fetch stream"})

# --- サーバー起動用 ---
import asyncio
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
