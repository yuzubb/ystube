import json
import httpx
import urllib.parse
import datetime
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Constants ---
AUTH_COOKIE = "ys_auth"
AUTH_VALUE = "authenticated_user"
DETAILS_API_BASE = "https://siawaseok.duckdns.org/api/video2"
STREAM_API_BASE = "https://yudlp.vercel.app/stream"
PLAYLIST_API_BASE = "https://yudlp.vercel.app/playlist"

# 提供されたファイルに基づいたインスタンスリスト
SEARCH_API_INSTANCES = [
    'https://api-five-zeta-55.vercel.app/',
]
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

async def request_invidious_parallel(path: str, instances: list):
    """並列でリクエストを送り、最初に成功したJSONを返す"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36'}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        tasks = [client.get(f"{api}api/v1{path}", headers=headers) for api in instances]
        for future in asyncio.as_completed(tasks):
            try:
                response = await future
                if response.status_code == 200:
                    return response.json()
            except:
                continue
    return None

def format_search_item(i):
    """提供されたコードの formatSearchData ロジックを適用"""
    t = i.get("type")
    if t == "video":
        return {
            "type": "video",
            "title": i.get("title"),
            "id": i.get("videoId"),
            "author": i.get("author"),
            "published": i.get("publishedText"),
            "length": str(datetime.timedelta(seconds=i.get("lengthSeconds", 0))),
            "view_count_text": i.get("viewCountText")
        }
    elif t == "playlist":
        return {
            "type": "playlist",
            "title": i.get("title"),
            "id": i.get("playlistId"),
            "thumbnail": i.get("playlistThumbnail"),
            "count": i.get("videoCount")
        }
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
    if passcode == "yuzu":
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE, value=AUTH_VALUE, httponly=True)
        return response
    return RedirectResponse("/ys", status_code=HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def view_search(request: Request, q: str, page: int = 1, _=Depends(verify_auth)):
    path = f"/search?q={urllib.parse.quote(q)}&page={page}&hl=jp"
    data = await request_invidious_parallel(path, SEARCH_API_INSTANCES + COMMENT_API_INSTANCES)
    
    results = []
    if data:
        results = [format_search_item(i) for i in data if format_search_item(i)]

    return templates.TemplateResponse("search.html", {
        "request": request,
        "results": results,
        "word": q,
        "next": f"/search?q={q}&page={page + 1}"
    })

@app.get("/watch", response_class=HTMLResponse)
async def view_watch(request: Request, v: str, _=Depends(verify_auth)):
    return templates.TemplateResponse("watch.html", {"request": request, "video_id": v})

# --- API Endpoints ---

@app.get("/api/playlist/watch")
async def api_get_playlist_mix(v: str, list: str):
    """
    Mixリスト用: /api/playlist/watch?v={videoid}&list={playlistid}
    yudlp側の /playlist/{playlistid}?v={videoid} を叩いて結果を返す
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # 内部で yudlp.vercel.app のエンドポイントへ転送
            backend_url = f"{PLAYLIST_API_BASE}/{list}?v={v}"
            res = await client.get(backend_url)
            return res.json()
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": "playlist api failed", "details": str(e)})

@app.get("/api/details/{video_id}")
async def api_video_details(video_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(f"{DETAILS_API_BASE}/{video_id}?depth=1")
            return res.json()
        except:
            return JSONResponse(status_code=502, content={"error": "details failed"})

@app.get("/api/comments/{video_id}")
async def api_get_comments(video_id: str):
    path = f"/comments/{urllib.parse.quote(video_id)}"
    data = await request_invidious_parallel(path, COMMENT_API_INSTANCES)
    if not data: return JSONResponse(status_code=502, content={"error": "comments failed"})
    
    return [
        {
            "author": i["author"],
            "authoricon": i["authorThumbnails"][-1]["url"] if i.get("authorThumbnails") else "",
            "authorid": i["authorId"],
            "body": i["contentHtml"].replace("\n", "<br>")
        } for i in data.get("comments", [])
    ]

@app.get("/api/stream/{video_id}")
async def api_proxy_stream_json(video_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(f"{STREAM_API_BASE}/{video_id}")
            return res.json()
        except:
            return JSONResponse(status_code=502, content={"error": "stream failed"})
