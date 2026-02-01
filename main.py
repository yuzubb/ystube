import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER
import pytchat

try:
    from youtubesearchpython import Search
except ImportError:
    from youtubesearchpython.search import Search

app = FastAPI()
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE = "ys_auth"
AUTH_VALUE = "authenticated_user"
DETAILS_API_BASE = "https://siawaseok.duckdns.org/api/video2"
STREAM_API_BASE = "https://yudlp.vercel.app/stream"

def is_auth(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == AUTH_VALUE

def require_auth(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=303, headers={"Location": "/ys"})

@app.get("/", response_class=HTMLResponse)
async def view_index(request: Request):
    if not is_auth(request):
        return RedirectResponse("/ys")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ys", response_class=HTMLResponse)
async def view_login(request: Request):
    if is_auth(request):
        return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/ys")
async def action_login(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE, value=AUTH_VALUE, httponly=True, samesite="lax")
        return response
    return RedirectResponse("/ys", status_code=HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def view_search(request: Request, q: str = ""):
    require_auth(request)
    if not q:
        return RedirectResponse("/")
    search_provider = Search(q, limit=20)
    results = search_provider.result()
    return templates.TemplateResponse("search.html", {"request": request, "query": q, "results": results.get('result', [])})

@app.get("/watch", response_class=HTMLResponse)
async def view_watch(request: Request, v: str = ""):
    require_auth(request)
    if not v:
        return RedirectResponse("/")
    return templates.TemplateResponse("watch.html", {"request": request, "video_id": v})

@app.get("/api/details/{video_id}")
async def api_video_details(video_id: str):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.get(f"{DETAILS_API_BASE}/{video_id}?depth=1")
            data = res.json()
            try:
                chat = pytchat.create(video_id=video_id)
                comments_list = []
                if chat.is_alive():
                    for c in chat.get().sync_items():
                        comments_list.append({
                            "authorName": c.author.name,
                            "authorThumbnail": c.author.imageUrl,
                            "text": c.message,
                            "publishedTime": c.datetime
                        })
                data['comments'] = comments_list
            except:
                data['comments'] = []
            return data
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": str(e)})

@app.get("/api/stream/{video_id}")
async def api_proxy_stream_json(video_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            target_url = f"{STREAM_API_BASE}/{video_id}"
            response = await client.get(target_url)
            return response.json()
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": str(e)})

@app.exception_handler(404)
async def error_404(request: Request, _):
    return HTMLResponse("<body style='background:#05070a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><h2>404 | NOT FOUND</h2></body>", status_code=404)
