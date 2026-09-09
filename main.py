import os
import random
import string
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Form, Request, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client

app = FastAPI(title="智信 SmartTiTu 客户开通申请系统")

# 静态文件挂载与模板配置
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
app.mount("/static", StaticFiles(directory=templates_dir), name="static")
templates = Jinja2Templates(directory="templates")

# ================= 0. Session 密钥与多账号权限配置 =================
SECRET_KEY = os.getenv("SECRET_KEY", "smarttitu_secure_key_2026")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

UIC_USER = os.getenv("UIC_USER", "uic_user")
UIC_PASSWORD = os.getenv("UIC_PASSWORD", "citic1616%UIC798")

ACTIVATE_USER = os.getenv("ACTIVATE_USER", "act_user")
ACTIVATE_PASSWORD = os.getenv("ACTIVATE_PASSWORD", "citic1616%ACT798")

ADMIN_USER = os.getenv("ADMIN_USER", "citic_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "citic1616#ADMIN")

# ================= Supabase 客户端初始化 =================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[警告] 未检测到 SUPABASE_URL 或 SUPABASE_KEY 环境变量，请在平台配置。")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


# ================= 辅助函数 =================
def render_template(template_name: str, request: Request, context: dict = None):
    if context is None:
        context = {}
    context["request"] = request
    try:
        return templates.TemplateResponse(request=request, name=template_name, context=context)
    except TypeError:
        return templates.TemplateResponse(name=template_name, context=context)


def check_uic_auth(request: Request):
    role = request.session.get("role")
    if role not in ["uic", "admin"]:
        return RedirectResponse(url="/login?next=/uic", status_code=303)
    return None


def check_activate_auth(request: Request):
    role = request.session.get("role")
    if role not in ["activate", "admin"]:
        return RedirectResponse(url="/login?next=/activate", status_code=303)
    return None


def generate_unique_apply_id() -> str:
    """从 Supabase 查询已有 ID 并生成唯一 ID"""
    existing_ids = set()
    if supabase:
        try:
            res = supabase.table("TituCustomers").select("apply_id").execute()
            for r in res.data:
                if r.get("apply_id"):
                    existing_ids.add(r["apply_id"].strip())
        except Exception as e:
            print(f"[generate_unique_apply_id 错误] {e}")

    while True:
        new_id = f"TiTu{''.join(random.choices(string.digits, k=6))}"
        if new_id not in existing_ids:
            return new_id


def load_options():
    """从 Supabase 的 options 表加载配置数据，回退提供默认选项"""
    default_opts = {
        "teams": [
            "中国业务部",
            "网联业务部",
            "企业业务部",
            "环球业务部",
            "信科产品部",
            "中企华北",
            "中企华南",
            "中企华东"
        ],
        "industries": [
            "金融/银行/证券",
            "保险",
            "电信/运营商",
            "互联网/科技",
            "零售/电商",
            "制造业",
            "医疗健康",
            "教育",
            "政府/公共事业",
            "能源/公用事业",
            "物流/运输",
            "汽车",
            "地产/建筑",
            "媒体/娱乐",
            "旅游/酒店",
            "专业服务/咨询",
            "农业",
            "其他"
        ],
        "app_types": [
            "SmartTiTu",
            "代销"
        ],
        "poc_stages": [
            "PoC",
            "正式上线"
        ],
        "contracts": [
            "已签署",
            "待签署",
            "未启动",
            "PoC阶段暂不适用"
        ],
        "models": [
            "doubao-seed-2-0-pro-260215",
            "doubao-seed-2-0-lite-260428",
            "doubao-seed-2-0-lite-260215",
            "doubao-seed-2-0-mini-260428",
            "doubao-seed-2-0-mini-260215",
            "doubao-seed-2-0-code-preview-260215",
            "doubao-seed-code-preview-251028",
            "deepseek-v4-pro-260425",
            "deepseek-v4-flash-260425",
            "deepseek-v4-flash-ga-260731",
            "deepseek-v4-pro-ga-260813",
            "doubao-seed-character-251128",
            "doubao-seed-translation-250915",
            "doubao-seedance-2-0-260128",
            "doubao-seedance-2-0-fast-260128",
            "doubao-seedance-2-0-mini-260615",
            "doubao-seedream-5-0-pro-260628",
            "doubao-seedream-4-5-251128",
            "doubao-seedream-4-0-250828",
            "doubao-seedream-5-0-260128",
            "doubao-seed-evolving",
            "doubao-seed-2-1-pro-260628",
            "doubao-seed-2-1-turbo-260628",
            "glm-5-2-260617",
            "kimi-k3",
            "deepseek-v4-pro-0813",
            "Deepseek-v4-flash-0731",
            "qwen3.8-max",
            "qwen3.7-plus",
            "qwen3.7-max",
            "moonshotai/Kimi-K2.7-Code",
            "zai-org/GLM-5.2",
            "Pro/moonshotai/Kimi-K2.6",
            "Pro/zai-org/GLM-5.1"
        ],
        "poc_statuses": [
            "待开通",
            "已开通",
            "测试中",
            "已完成",
            "已转正式",
            "已关闭"
        ]
    }
    if not supabase:
        return default_opts

    try:
        res = supabase.table("options").select("*").execute()
        if not res.data:
            return default_opts

        opts = {
            "teams": [], "industries": [], "app_types": [],
            "poc_stages": [], "contracts": [], "models": [], "poc_statuses": []
        }
        for item in res.data:
            cat = item.get("category")
            val = item.get("value")
            if cat in opts and val:
                opts[cat].append(val)
        return opts
    except Exception as e:
        print(f"[load_options 错误] {e}")
        return default_opts


def save_to_supabase(data: dict):
    if not supabase:
        print("[错误] Supabase 客户端未初始化，无法保存数据")
        return
    try:
        supabase.table("TituCustomers").insert(data).execute()
    except Exception as e:
        print(f"[save_to_supabase 错误] {e}")


def get_TituCustomers(page: int = 1, limit: int = 6):
    if not supabase:
        return [], 1, page

    try:
        start = (page - 1) * limit
        end = start + limit - 1

        # 查询总数与分页数据
        res = supabase.table("TituCustomers").select("*", count="exact").order("id", desc=True).range(start,
                                                                                                     end).execute()
        total_items = res.count or 0
        total_pages = max(1, (total_items + limit - 1) // limit)

        items = []
        for r in res.data:
            raw_models = r.get("models") or ""
            models_list = [m.strip() for m in raw_models.split(",") if m.strip()]
            items.append({
                "row": r.get("id"),
                "apply_id": r.get("apply_id") or "",
                "team": r.get("team") or "",
                "client_name": r.get("client_name") or "",
                "app_type": r.get("app_type") or "",
                "poc_stage": r.get("poc_stage") or "",
                "models": raw_models,
                "models_list": models_list,
                "open_date": r.get("open_date") or "",
                "status": r.get("status") or "待开通",
                "quota": r.get("quota") or "",
                "client_id_info": r.get("client_id_info") or "",
                "update_date": r.get("update_date") or "",
                "pdf_url": r.get("pdf_url") or ""
            })

        return items, total_pages, page
    except Exception as e:
        print(f"[get_TituCustomers 错误] {e}")
        return [], 1, page


# ================= 路由与逻辑 =================
@app.get("/")
async def root(request: Request):
    role = request.session.get("role")
    if role == "activate":
        return RedirectResponse(url="/activate", status_code=303)
    elif role in ["uic", "admin"]:
        return RedirectResponse(url="/uic", status_code=303)
    return RedirectResponse(url="/login?next=/uic", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/uic"):
    return render_template("login.html", request, {"error": None, "next_url": next})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        next_url: str = Form("/uic")
):
    role = None
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        role = "admin"
    elif username == UIC_USER and password == UIC_PASSWORD:
        role = "uic"
    elif username == ACTIVATE_USER and password == ACTIVATE_PASSWORD:
        role = "activate"

    if role:
        request.session["role"] = role
        request.session["username"] = username
        target = next_url if next_url and not next_url.startswith("/login") else "/uic"
        return RedirectResponse(url=target, status_code=303)

    return render_template("login.html", request, {
        "error": "用户名或密码错误，请确认你的账号权限！",
        "next_url": next_url
    })


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/uic", response_class=HTMLResponse)
async def get_form(request: Request):
    auth_redirect = check_uic_auth(request)
    if auth_redirect: return auth_redirect

    options = load_options()
    today_str = datetime.today().strftime('%Y-%m-%d')
    apply_id = generate_unique_apply_id()
    return render_template("index.html", request, {
        "options": options,
        "today_str": today_str,
        "apply_id": apply_id
    })


@app.post("/submit")
async def submit_form(
        request: Request,
        apply_id: str = Form(...),
        apply_date: str = Form(...), team: str = Form(...), sales_name: str = Form(...),
        industry: str = Form(...), client_name: str = Form(...), company_desc: str = Form(""),
        contact_info: str = Form(...), internal_contact: str = Form(""), app_type: str = Form(...),
        poc_stage: str = Form(...), requirement_desc: str = Form(""), contract_status: str = Form(...),
        models: List[str] = Form([]),
        pdf_file: Optional[UploadFile] = File(None)
):
    auth_redirect = check_uic_auth(request)
    if auth_redirect: return auth_redirect

    pdf_url = ""
    if pdf_file and supabase:
        try:
            pdf_filename = f"智信SmartTiTu客户开通{apply_id}.pdf"
            content = await pdf_file.read()

            # 将 PDF 上传到 Supabase Storage 的 pdf-records 存储桶
            supabase.storage.from_("pdf-records").upload(
                path=pdf_filename,
                file=content,
                file_options={"content-type": "application/pdf"}
            )
            # 获取访问公开外链
            pdf_url = supabase.storage.from_("pdf-records").get_public_url(pdf_filename)
        except Exception as e:
            print(f"[Supabase Storage 上传错误] {e}")

    form_data = {
        "apply_id": apply_id, "apply_date": apply_date, "team": team, "sales_name": sales_name,
        "industry": industry, "client_name": client_name, "company_desc": company_desc,
        "contact_info": contact_info, "internal_contact": internal_contact, "app_type": app_type,
        "poc_stage": poc_stage, "requirement_desc": requirement_desc, "contract_status": contract_status,
        "models": ", ".join(models), "status": "待开通", "pdf_url": pdf_url
    }
    save_to_supabase(form_data)
    return RedirectResponse(url=f"/success?client_name={client_name}", status_code=303)


@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request, client_name: str = "客户"):
    auth_redirect = check_uic_auth(request)
    if auth_redirect: return auth_redirect
    return render_template("success.html", request, {"client_name": client_name})


@app.get("/activate", response_class=HTMLResponse)
async def activate_page(request: Request, page: int = 1):
    auth_redirect = check_activate_auth(request)
    if auth_redirect: return auth_redirect

    items, total_pages, current_page = get_TituCustomers(page=page, limit=6)
    options = load_options()
    return render_template("activate.html", request, {
        "items": items,
        "total_pages": total_pages,
        "current_page": current_page,
        "poc_statuses": options["poc_statuses"]
    })


@app.post("/activate/save")
async def save_activate(
        request: Request,
        page: int = Form(...),
        row_ids: List[int] = Form(...),
        open_dates: List[str] = Form(default=[]),
        statuses: List[str] = Form(default=[]),
        quotas: List[str] = Form(default=[]),
        client_id_infos: List[str] = Form(default=[])
):
    auth_redirect = check_activate_auth(request)
    if auth_redirect: return auth_redirect

    if supabase:
        today_str = datetime.today().strftime('%Y-%m-%d')
        for i, row_id in enumerate(row_ids):
            update_payload = {
                "open_date": open_dates[i] if i < len(open_dates) else "",
                "status": statuses[i] if i < len(statuses) else "待开通",
                "quota": quotas[i] if i < len(quotas) else "",
                "client_id_info": client_id_infos[i] if i < len(client_id_infos) else "",
                "update_date": today_str
            }
            try:
                supabase.table("TituCustomers").update(update_payload).eq("id", row_id).execute()
            except Exception as e:
                print(f"[Supabase 更新错误] {e}")

    return RedirectResponse(url=f"/activate?page={page}", status_code=303)