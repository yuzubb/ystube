from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from youtubesearchpython import Search
import starlette.status as status

app = FastAPI()
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE_NAME = "ys_auth"
AUTH_SECRET_VALUE = "authenticated_user"

def is_authenticated(request: Request):
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_SECRET_VALUE

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ys", response_class=HTMLResponse)
async def ys_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/")
    return HTMLResponse("""
        <div style="background:#05070a; height:100vh; display:flex; justify-content:center; align-items:center; color:white; font-family:sans-serif;">
            <form method="post" style="text-align:center;">
                <input type="password" name="passcode" placeholder="Passcode" autofocus 
                       style="background:rgba(255,255,255,0.1); border:1px solid #00d4ff; padding:10px; color:white; border-radius:5px; outline:none;">
                <button type="submit" style="background:#00d4ff; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">Verify</button>
            </form>
        </div>
    """)

@app.post("/ys")
async def ys_verify(passcode: str = Form(...)):
    if passcode == "yes":
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key=AUTH_COOKIE_NAME, value=AUTH_SECRET_VALUE, httponly=True)
        return response
    raise HTTPException(status_code=401)

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    
    search_provider = Search(q, limit=20)
    search_results = search_provider.result()
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": search_results.get('result', [])
    })

# --- Error Handlers ---
@app.exception_handler(404)
async def handler_404(request: Request, _):
    return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)

@app.exception_handler(401)
async def handler_401(request: Request, _):
    return RedirectResponse(url="/ys")
