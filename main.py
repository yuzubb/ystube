from fastapi import FastAPI, Request, Response, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import starlette.status as status
import asyncio
import httpx

# インポートエラー対策
try:
    from youtubesearchpython import Search
except ImportError:
    from youtubesearchpython.search import Search

app = FastAPI()
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE_NAME = "ys_auth"
AUTH_SECRET_VALUE = "authenticated_user"

def is_authenticated(request: Request):
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_SECRET_VALUE

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
        response.set_cookie(key=AUTH_COOKIE_NAME, value=AUTH_SECRET_VALUE, httponly=True, samesite="lax")
        return response
    return RedirectResponse(url="/ys", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    if not is_authenticated(request):
        return RedirectResponse(url="/ys")
    if not q:
        return RedirectResponse(url="/")

    # 初回検索
    search_provider = Search(q, limit=20)
    search_results = search_provider.result()
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": search_results.get('result', [])
    })

@app.get("/watch", response_class=HTMLResponse)
async def watch_page(request: Request, v: str = ""):
    if not is_authenticated(request):
        return RedirectResponse(url="/ys")
    return templates.TemplateResponse("watch.html", {"request": request, "video_id": v})
    
# --- API ---
@app.get("/api/search/more")
async def search_more(q: str, offset: int = 1):
    # offsetの分だけ next() を呼び出して次のページへ進む
    search_provider = Search(q, limit=20)
    for _ in range(offset):
        search_provider.next()
    return search_provider.result()

@app.get("/api/stream/{video_id}")
async def stream_video(video_id: str):
    target_url = f"https://yudlp.vercel.app/stream/{video_id}"
    
    async def generate_stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", target_url) as resp:
                if resp.status_code != 200:
                    yield b"Error: Unable to fetch stream"
                    return
                
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(generate_stream(), media_type="video/mp4")


@app.exception_handler(404)
async def handler_404(request: Request, _):
    return HTMLResponse("<body style='background:#05070a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><h2>404 | NOT FOUND</h2></body>", status_code=404)
