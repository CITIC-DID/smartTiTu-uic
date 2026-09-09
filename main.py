import os
import random
import string
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Form, Request, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import openpyxl
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="智信 SmartTiTu 客户开通申请系统")

# 静态文件挂载
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
app.mount("/static", StaticFiles(directory=templates_dir), name="static")
templates = Jinja2Templates(directory="templates")

# ================= 0. Session 密钥与多账号权限配置 =================
SECRET_KEY = os.getenv("SECRET_KEY", "smarttitu_secure_key_2026")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 1. 申请采集页 账号密码
UIC_USER = os.getenv("UIC_USER", "uic_user")
UIC_PASSWORD = os.getenv("UIC_PASSWORD", "citic1616%UIC798")

# 2. 开通管理页 账号密码
ACTIVATE_USER = os.getenv("ACTIVATE_USER", "act_user")
ACTIVATE_PASSWORD = os.getenv("ACTIVATE_PASSWORD", "citic1616%ACT798")

# 3. 超级管理员 账号密码（可访问所有页面）
ADMIN_USER = os.getenv("ADMIN_USER", "citic_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "citic1616#ADMIN")

# ================= 路径配置（已修改为 data 文件夹下） =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 1. 主 Excel 文件路径: data/智信SmartTiTu客户开通申请登记表.xlsx
EXCEL_FILE = os.path.join(DATA_DIR, "智信SmartTiTu客户开通申请登记表.xlsx")

# 2. PDF 保存文件夹路径: data/historyExcel/
HISTORY_DIR = os.path.join(DATA_DIR, "historyApplyRecord")


# ================= 辅助：渲染模板兼容函数 =================
def render_template(template_name: str, request: Request, context: dict = None):
    """
    兼容 FastAPI 新旧版本的 TemplateResponse 函数
    """
    if context is None:
        context = {}
    context["request"] = request
    try:
        return templates.TemplateResponse(request=request, name=template_name, context=context)
    except TypeError:
        return templates.TemplateResponse(name=template_name, context=context)


# ================= 权限校验与ID辅助函数 =================

def check_uic_auth(request: Request):
    """检查是否有申请页面的访问权限"""
    role = request.session.get("role")
    if role not in ["uic", "admin"]:
        return RedirectResponse(url="/login?next=/uic", status_code=303)
    return None


def check_activate_auth(request: Request):
    """检查是否有开通管理页面的访问权限"""
    role = request.session.get("role")
    if role not in ["activate", "admin"]:
        return RedirectResponse(url="/login?next=/activate", status_code=303)
    return None


def generate_unique_apply_id() -> str:
    """读取 Excel B列已有申请ID，随机生成一个不重复的申请ID"""
    existing_ids = set()
    if os.path.exists(EXCEL_FILE):
        try:
            wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
            if '申请登记表' in wb.sheetnames:
                sheet = wb['申请登记表']
                for r in range(3, sheet.max_row + 1):
                    val = sheet.cell(row=r, column=2).value
                    if val:
                        existing_ids.add(str(val).strip())
            wb.close()
        except Exception as e:
            print(f"[generate_unique_apply_id 错误] {e}")

    while True:
        new_id = f"TiTu{''.join(random.choices(string.digits, k=6))}"
        if new_id not in existing_ids:
            return new_id


def load_options():
    default_opts = {
        "teams": [], "industries": [], "app_types": [],
        "poc_stages": [], "contracts": [], "models": [], "poc_statuses": []
    }
    if not os.path.exists(EXCEL_FILE):
        return default_opts

    try:
        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
        if '选项参考' not in wb.sheetnames:
            wb.close()
            return default_opts

        ref_sheet = wb['选项参考']
        teams, industries, app_types, poc_stages, contracts, models, poc_statuses = [], [], [], [], [], [], []
        for r in range(2, ref_sheet.max_row + 1):
            cat = ref_sheet.cell(row=r, column=1).value
            opt = ref_sheet.cell(row=r, column=2).value
            if cat == '团队' and opt:
                teams.append(opt)
            elif cat == '客户行业' and opt:
                industries.append(opt)
            elif cat == '申请类型' and opt:
                app_types.append(opt)
            elif cat == 'PoC/正式上线' and opt:
                poc_stages.append(opt)
            elif cat == '合约' and opt:
                contracts.append(opt)
            elif cat == 'POC状态' and opt:
                poc_statuses.append(opt)

        for r in range(3, ref_sheet.max_row + 1):
            m_id = ref_sheet.cell(row=r, column=6).value
            if m_id and m_id not in models: models.append(m_id)

        wb.close()
        return {
            "teams": teams, "industries": industries, "app_types": app_types,
            "poc_stages": poc_stages, "contracts": contracts, "models": models,
            "poc_statuses": poc_statuses
        }
    except Exception as e:
        print(f"[load_options 错误] {e}")
        return default_opts


def save_to_excel(data: dict):
    if not os.path.exists(EXCEL_FILE):
        return
    try:
        wb = openpyxl.load_workbook(EXCEL_FILE)
        sheet = wb['申请登记表']
        target_row = 3
        while True:
            vals = [sheet.cell(row=target_row, column=c).value for c in range(1, 20)]
            if all(v is None or str(v).strip() == "" for v in vals): break
            target_row += 1

        sheet.cell(row=target_row, column=1, value=data['apply_date'])
        sheet.cell(row=target_row, column=2, value=data['apply_id'])
        sheet.cell(row=target_row, column=3, value=data['team'])
        sheet.cell(row=target_row, column=4, value=data['sales_name'])
        sheet.cell(row=target_row, column=5, value=data['industry'])
        sheet.cell(row=target_row, column=6, value=data['client_name'])
        sheet.cell(row=target_row, column=7, value=data['company_desc'])
        sheet.cell(row=target_row, column=8, value=data['contact_info'])
        sheet.cell(row=target_row, column=9, value=data['internal_contact'])
        sheet.cell(row=target_row, column=10, value=data['app_type'])
        sheet.cell(row=target_row, column=11, value=data['poc_stage'])
        sheet.cell(row=target_row, column=12, value=data['requirement_desc'])
        sheet.cell(row=target_row, column=13, value=data['contract_status'])
        sheet.cell(row=target_row, column=14, value=", ".join(data['models']))
        sheet.cell(row=target_row, column=16, value="待开通")
        wb.save(EXCEL_FILE)
        wb.close()
    except Exception as e:
        print(f"[save_to_excel 错误] {e}")


def get_applications(page: int = 1, limit: int = 6):
    if not os.path.exists(EXCEL_FILE):
        return [], 1, page

    try:
        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
        if '申请登记表' not in wb.sheetnames:
            wb.close()
            return [], 1, page

        sheet = wb['申请登记表']
        data = []
        for r in range(3, sheet.max_row + 1):
            client_name = sheet.cell(row=r, column=6).value
            if not client_name: continue

            raw_models = sheet.cell(row=r, column=14).value or ""
            models_list = [m.strip() for m in str(raw_models).split(",") if m.strip()]

            data.append({
                "row": r,
                "apply_id": sheet.cell(row=r, column=2).value or "",
                "team": sheet.cell(row=r, column=3).value or "",
                "client_name": client_name,
                "app_type": sheet.cell(row=r, column=10).value or "",
                "poc_stage": sheet.cell(row=r, column=11).value or "",
                "models": raw_models,
                "models_list": models_list,
                "open_date": sheet.cell(row=r, column=15).value or "",
                "status": sheet.cell(row=r, column=16).value or "待开通",
                "quota": sheet.cell(row=r, column=17).value or "",
                "client_id_info": sheet.cell(row=r, column=18).value or "",
                "update_date": sheet.cell(row=r, column=19).value or ""
            })
        wb.close()

        data.reverse()
        total_items = len(data)
        total_pages = max(1, (total_items + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit
        page_data = data[start:end]

        return page_data, total_pages, page
    except Exception as e:
        print(f"[get_applications 错误] {e}")
        return [], 1, page


# ================= 路由与登录认证 =================

@app.get("/")
async def root(request: Request):
    role = request.session.get("role")
    if role == "activate":
        return RedirectResponse(url="/activate", status_code=303)
    elif role in ["uic", "admin"]:
        return RedirectResponse(url="/uic", status_code=303)
    return RedirectResponse(url="/login?next=/uic", status_code=303)


# 登录页面
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/uic"):
    return render_template("login.html", request, {"error": None, "next_url": next})


# 登录提交处理
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

        if role == "uic":
            target = next_url if next_url.startswith("/uic") or next_url.startswith("/success") else "/uic"
        elif role == "activate":
            target = next_url if next_url.startswith("/activate") else "/activate"
        else:
            target = next_url if next_url else "/uic"

        return RedirectResponse(url=target, status_code=303)

    return render_template("login.html", request, {
        "error": "用户名或密码错误，请确认你的账号权限！",
        "next_url": next_url
    })


# 退出登录
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# 1. 申请采集页面 /uic
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
        pdf_file: Optional[UploadFile] = File(None)  # 接收前端上传的 PDF 文件
):
    auth_redirect = check_uic_auth(request)
    if auth_redirect: return auth_redirect

    # 保存 PDF 到 data/historyExcel 文件夹中
    if pdf_file:
        try:
            if not os.path.exists(HISTORY_DIR):
                os.makedirs(HISTORY_DIR, exist_ok=True)

            # 使用指定格式命名保存
            pdf_filename = f"智信SmartTiTu客户开通{apply_id}.pdf"
            save_path = os.path.join(HISTORY_DIR, pdf_filename)

            content = await pdf_file.read()
            with open(save_path, "wb") as f:
                f.write(content)
        except Exception as e:
            print(f"[保存 PDF 错误] {e}")

    form_data = {
        "apply_id": apply_id, "apply_date": apply_date, "team": team, "sales_name": sales_name,
        "industry": industry, "client_name": client_name, "company_desc": company_desc,
        "contact_info": contact_info, "internal_contact": internal_contact, "app_type": app_type,
        "poc_stage": poc_stage, "requirement_desc": requirement_desc, "contract_status": contract_status,
        "models": models
    }
    save_to_excel(form_data)
    return RedirectResponse(url=f"/success?client_name={client_name}", status_code=303)


@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request, client_name: str = "客户"):
    auth_redirect = check_uic_auth(request)
    if auth_redirect: return auth_redirect
    return render_template("success.html", request, {"client_name": client_name})


# 2. 开通信息页面 /activate
@app.get("/activate", response_class=HTMLResponse)
async def activate_page(request: Request, page: int = 1):
    auth_redirect = check_activate_auth(request)
    if auth_redirect: return auth_redirect

    items, total_pages, current_page = get_applications(page=page, limit=6)
    options = load_options()
    return render_template("activate.html", request, {
        "items": items,
        "total_pages": total_pages,
        "current_page": current_page,
        "poc_statuses": options["poc_statuses"]
    })


# 保存接口 /activate/save
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

    if os.path.exists(EXCEL_FILE):
        try:
            wb = openpyxl.load_workbook(EXCEL_FILE)
            sheet = wb['申请登记表']
            today_str = datetime.today().strftime('%Y-%m-%d')

            for i, row in enumerate(row_ids):
                sheet.cell(row=row, column=15, value=open_dates[i] if i < len(open_dates) else "")
                sheet.cell(row=row, column=16, value=statuses[i] if i < len(statuses) else "待开通")
                sheet.cell(row=row, column=17, value=quotas[i] if i < len(quotas) else "")
                sheet.cell(row=row, column=18, value=client_id_infos[i] if i < len(client_id_infos) else "")
                sheet.cell(row=row, column=19, value=today_str)

            wb.save(EXCEL_FILE)
            wb.close()
        except Exception as e:
            print(f"[save_activate 错误] {e}")

    return RedirectResponse(url=f"/activate?page={page}", status_code=303)