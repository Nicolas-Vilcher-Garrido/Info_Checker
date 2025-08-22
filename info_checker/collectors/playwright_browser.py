from __future__ import annotations

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except Exception:
    sync_playwright = None

import os
import re
import glob
import csv
from pathlib import Path
from urllib.parse import quote
from typing import Optional

from dotenv import load_dotenv

from info_checker.core.interfaces import Collector
from info_checker.core.models import CollectRequest, CollectResponse

# pandas opcional (para Excel)
try:
    import pandas as pd
except ImportError:
    pd = None

# ---------------------- helpers de parsing ----------------------
_MONTH_RE = re.compile(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}$", re.I)

def _is_month_token(s: str) -> bool:
    return bool(_MONTH_RE.match(s.strip()))

def _norm(s: str) -> str:
    return (s or "").strip()

# =======================================================================

class PlaywrightCollector(Collector):
    """
    Coletor Playwright para extrair dados de relatórios Power BI EMBED.
    - Login robusto (ASP.NET WebForms, com fallbacks: clique, submit e __doPostBack)
    - Localiza iframe do Power BI
    - Extrai tabela/tab visível (grid/table) e exporta CSV
    - Junta CSVs em Excel (se pandas estiver instalado)
    """

    def __init__(self, headless: bool = True, default_timeout_ms: int = 30000):
        self.headless = headless
        self.default_timeout_ms = default_timeout_ms
        load_dotenv()
        self.export_dir = Path("exports") / "powerbi"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir = self.export_dir / "debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------- utilidades ----------------------
    def _save_html(self, page, name: str):
        try:
            path_html = self.debug_dir / f"{name}.html"
            path_png  = self.debug_dir / f"{name}.png"
            with open(path_html, "w", encoding="utf-8") as f:
                f.write(page.content())
            page.screenshot(path=str(path_png), full_page=True)
            print(f"[DEBUG] HTML: {path_html.resolve()}")
            print(f"[DEBUG] PNG : {path_png.resolve()}")
        except Exception:
            pass

    def _try_fill(self, ctx, selector: str, value: str) -> bool:
        try:
            loc = ctx.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(value)
                return True
        except Exception:
            pass
        return False

    # ---------------------- LOGIN ----------------------
    def _fill_username(self, ctx, username: str) -> bool:
        print("[DEBUG] Tentando preencher o nome de usuário...")
        # seletor exato ASP.NET
        if self._try_fill(ctx, '#lgnCredencial_UserName', username):
            print("[DEBUG] Usuário preenchido com sucesso.")
            return True

        # genéricos (fallback)
        for fn in (
            lambda: ctx.get_by_placeholder("Login").fill(username),
            lambda: ctx.get_by_label("Login", exact=False).fill(username),
            lambda: ctx.get_by_placeholder("Usuário").fill(username),
            lambda: ctx.get_by_label("Usuário", exact=False).fill(username),
            lambda: ctx.get_by_placeholder("E-mail").fill(username),
            lambda: ctx.get_by_label("E-mail", exact=False).fill(username),
        ):
            try:
                fn(); return True
            except Exception:
                pass

        # ASP.NET WebForms: ids terminando com UserName
        for sel in ['input[id$="UserName"]','input[name$="UserName"]']:
            if self._try_fill(ctx, sel, username): return True

        # genéricos
        for sel in [
            'input[name="username"]','input[id="username"]',
            'input[type="email"]','input[type="text"]:not([hidden])',
            'input[name*="user" i]','input[id*="user" i]',
            'input[name*="login" i]','input[id*="login" i]',
            'input:not([type]):not([hidden])',
        ]:
            if self._try_fill(ctx, sel, username): return True

        return False

    def _fill_password(self, ctx, password: str) -> bool:
        print("[DEBUG] Tentando preencher a senha...")
        # seletor exato ASP.NET
        if self._try_fill(ctx, '#lgnCredencial_Password', password):
            print("[DEBUG] Senha preenchida com sucesso.")
            return True

        # fallbacks
        for fn in (
            lambda: ctx.get_by_placeholder("Senha").fill(password),
            lambda: ctx.get_by_label("Senha", exact=False).fill(password),
        ):
            try:
                fn(); return True
            except Exception:
                pass

        for sel in ['input[id$="Password"]','input[name$="Password"]']:
            if self._try_fill(ctx, sel, password): return True

        for sel in [
            'input[name="password"]','input[id="password"]','input[type="password"]',
            'input[name*="senha" i]','input[id*="senha" i]',
            'input[name*="pass" i]','input[id*="pass" i]',
        ]:
            if self._try_fill(ctx, sel, password): return True

        return False

    def _click_or_submit_login(self, page_or_frame) -> bool:
        """
        1) Tenta clicar no botão padrão (#lgnCredencial_LoginButton).
        2) Se não rolar, tenta submeter o form pai do campo senha.
        3) Se for WebForms com __doPostBack, dispara ele manualmente.
        """
        ctx = page_or_frame
        print("[DEBUG] Tentando acionar o login...")

        # 1) botão clássico
        try:
            btn = ctx.locator('#lgnCredencial_LoginButton')
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=6000)
                print("[DEBUG] Clique no botão de login (id) OK")
                return True
        except Exception:
            pass

        # 1b) botões alternativos
        for sel in [
            'input[type="submit"]','input[type="image"]','button[type="submit"]',
            'button:has-text("Entrar")','a:has-text("Entrar")',
            'button:has-text("Acessar")','a:has-text("Acessar")',
            '[id$="LoginButton"]','[name$="LoginButton"]',
        ]:
            try:
                el = ctx.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.click(timeout=6000)
                    print(f"[DEBUG] Clique no seletor de login {sel} OK")
                    return True
            except Exception:
                pass

        # 2) submit do form (se existir)
        try:
            pwd = ctx.locator('#lgnCredencial_Password').first
            if pwd.count() == 0:
                pwd = ctx.locator('input[type="password"]').first
            if pwd.count() > 0:
                ctx.evaluate(
                    """(el)=>{
                        const f = el.form || el.closest('form');
                        if (f) f.submit();
                    }""",
                    pwd
                )
                print("[DEBUG] Form.submit() disparado")
                return True
        except Exception:
            pass

        # 3) __doPostBack (ASP.NET)
        try:
            has_postback = ctx.evaluate("() => typeof window.__doPostBack === 'function'")
            if has_postback:
                # tenta com o target do login comum
                ctx.evaluate("""() => { try { __doPostBack('lgnCredencial$LoginButton',''); } catch(e){} }""")
                print("[DEBUG] __doPostBack('lgnCredencial$LoginButton','')")
                return True
        except Exception:
            pass

        # 4) Enter no campo senha
        try:
            pwd = ctx.locator('input[type="password"]').first
            if pwd.count() > 0:
                pwd.focus()
                ctx.keyboard.press("Enter")
                print("[DEBUG] Enter no campo de senha")
                return True
        except Exception:
            pass

        return False

    def _perform_login(self, page, login_url: str, username: str, password: str):
        print("[DEBUG] Ir para login:", login_url)
        page.goto(login_url, wait_until="domcontentloaded")
        self._save_html(page, "login_page")

        def try_ctx(ctx) -> bool:
            ok_user = self._fill_username(ctx, username)
            ok_pass = self._fill_password(ctx, password)
            if ok_user and ok_pass:
                page.wait_for_timeout(250)
                if self._click_or_submit_login(ctx):
                    return True
            return False

        # tenta na página
        done = try_ctx(page)
        # se não deu, tenta em iframes
        if not done:
            for f in page.frames:
                if f == page.main_frame:
                    continue
                try:
                    if try_ctx(f):
                        done = True
                        break
                except Exception:
                    continue

        # aguarda pós-login
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        print("[DEBUG] URL após tentativa de login:", page.url)
        # registra mensagem de erro se houver
        try:
            msg = page.locator('#lgnCredencial_FailureText, .validation-summary-errors, [id*="FailureText"]').first
            if msg.count() > 0 and msg.is_visible():
                print("[WARN] Mensagem de erro de login:", _norm(msg.inner_text()))
        except Exception:
            pass

    # ---------------------- POWER BI FRAME ----------------------
    def _find_pbi_frame(self, page):
        targets = ("app.powerbi.com/reportembed", "powerbi", "report", "relatorio.aspx", "reportid=")
        # 1) varre frames por URL
        for f in page.frames:
            try:
                u = (f.url or "").lower()
                if any(t in u for t in targets):
                    return f
            except Exception:
                continue
        # 2) tenta pelos iframes DOM
        try:
            iframes = page.locator("iframe")
            n = min(iframes.count(), 50)
            for i in range(n):
                el = iframes.nth(i)
                try:
                    src = (el.get_attribute("src") or "").lower()
                    tit = (el.get_attribute("title") or "").lower()
                    if any(t in src for t in targets) or any(t in tit for t in targets):
                        cf = el.content_frame()
                        if cf: 
                            return cf
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ---------------------- EXTRAÇÃO TABELA ----------------------
    def _extract_table_like(self, ctx) -> tuple[list[str], list[list[str]]]:
        """
        Tenta montar header + rows a partir de grids do Power BI.
        """
        headers: list[str] = []
        rows: list[list[str]] = []

        # 1) tenta 'role' semântico
        table = ctx.locator('[role="table"], [role="grid"]').first
        if table.count() > 0 and table.is_visible():
            # headers
            try:
                hdr = table.locator('[role="columnheader"], thead th')
                for t in hdr.all_text_contents():
                    t = _norm(t)
                    if t:
                        headers.append(t)
            except Exception:
                pass
            # rows
            try:
                row_loc = table.locator('[role="row"]')
                rcount = row_loc.count()
                for ri in range(rcount):
                    row_el = row_loc.nth(ri)
                    cells = []
                    cell_loc = row_el.locator('[role="gridcell"], td')
                    for txt in cell_loc.all_text_contents():
                        v = _norm(txt)
                        if v:
                            cells.append(v)
                    if cells:
                        rows.append(cells)
            except Exception:
                pass
            if headers or rows:
                return headers, rows

        # 2) fallback: varre visual container
        try:
            visual = ctx.locator('[data-automationid="visualContainer"], [data-automation-id="visualContainer"]').first
            if visual.count() > 0:
                texts = []
                nodes = visual.locator("*, svg text")
                n = min(nodes.count(), 2000)
                for i in range(n):
                    try:
                        t = _norm(nodes.nth(i).inner_text())
                        if t:
                            texts.append(t)
                    except Exception:
                        pass
                # heurística simples: tente separar por linhas quando encontrar mês
                row: list[str] = []
                for t in texts:
                    if _is_month_token(t):
                        if row:
                            rows.append(row)
                        row = [t]
                    else:
                        if t:
                            row.append(t)
                if row:
                    rows.append(row)
        except Exception:
            pass

        return headers, rows

    def _extract_table_to_csv(self, ctx, out_csv: Path, tab_name: str) -> bool:
        try:
            # aguarda algo "table-like" aparecer
            ctx.wait_for_selector('[role="grid"], [role="table"], [data-automationid="visualContainer"]',
                                  timeout=30000)
            headers, rows = self._extract_table_like(ctx)
            if not rows and not headers:
                print(f"[WARN] Nada tabular visível para '{tab_name}'.")
                return False

            out_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(out_csv, "w", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                if headers:
                    writer.writerow(headers)
                writer.writerows(rows)

            print(f"[OK] CSV gerado para '{tab_name}': {out_csv.resolve()}")
            return True

        except PWTimeoutError:
            print(f"[ERRO] Timeout aguardando tabela/visual para '{tab_name}'.")
            return False
        except Exception as e:
            print(f"[ERRO] Falha na extração para '{tab_name}': {e}")
            return False

    # ---------------------- MERGE CSV -> EXCEL ----------------------
    def merge_exports_to_xlsx(self, out_xlsx: str) -> str:
        if pd is None:
            raise RuntimeError("Pandas não encontrado. Instale: pip install pandas openpyxl")
        csv_paths = glob.glob(str(self.export_dir / "*.csv"))
        if not csv_paths:
            raise RuntimeError(f"Nenhum CSV encontrado em: {self.export_dir.resolve()}")
        tmp = out_xlsx + ".tmp"
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as writer:
            for path in csv_paths:
                sheet = Path(path).stem[:31]
                try:
                    df = pd.read_csv(path, encoding="utf-8")
                    df.to_excel(writer, index=False, sheet_name=sheet)
                except Exception as e:
                    print(f"[WARN] falha ao escrever '{sheet}': {e}")
        if os.path.exists(out_xlsx):
            try: os.remove(out_xlsx)
            except Exception: pass
        os.replace(tmp, out_xlsx)
        print(f"[EXPORT] Excel gerado: {Path(out_xlsx).resolve()}")
        return out_xlsx

    # ---------------------- COLLECT ----------------------
    def collect(self, req: CollectRequest) -> CollectResponse:
        if sync_playwright is None:
            raise RuntimeError("Playwright não está instalado no ambiente.")
        extra = req.extra or {}
        username = extra.get("username") or os.getenv("USERNAME")
        password = extra.get("password") or os.getenv("PASSWORD")
        if not username or not password:
            raise RuntimeError("Credenciais ausentes.")

        login_url_base = extra.get("login_url", "https://patrezeseguros.metainfo.com.br/login")
        use_return_url = bool(extra.get("use_return_url", False))
        wait_until = extra.get("wait_until", "domcontentloaded")
        wait_ms = int(extra.get("wait_ms", 6000))
        nav_timeout_ms = int(extra.get("nav_timeout_ms", 60000))
        merge_to_excel = bool(extra.get("merge_to_excel", True))
        excel_name = extra.get("excel_name") or "powerbi_export.xlsx"
        tabs_to_extract = extra.get("tabs_to_extract", [])
        out_xlsx_path = str(Path("exports") / excel_name)

        login_url = login_url_base
        if use_return_url:
            sep = "&" if "?" in login_url_base else "?"
            login_url = f"{login_url_base}{sep}returnUrl={quote(req.source, safe='')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=120 if not self.headless else 0)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(max(self.default_timeout_ms, 15000))

            # 1) login
            self._perform_login(page, login_url=login_url, username=username, password=password)

            # não saia cedo; alguns ambientes mantêm a URL igual, mas setam cookie
            # então tente ir ao relatório de qualquer forma
            print("[DEBUG] tentando abrir relatório:", req.source)
            try:
                page.goto(req.source, wait_until=wait_until, timeout=nav_timeout_ms)
            except Exception as e:
                print(f"[ERRO] Falha ao acessar relatório: {e}")
                self._save_html(page, "erro_navegacao_relatorio")

            # 2) iframe do Power BI
            pbi_frame = self._find_pbi_frame(page)
            if not pbi_frame:
                print("[WARN] Não foi possível localizar o iframe do Power BI.")
                self._save_html(page, "erro_frame")
                html = page.content()
                context.close(); browser.close()
                return CollectResponse(raw=html, extracted=None,
                    meta={"engine": "playwright", "excel_path": None, "frame": "not_found"})

            # 3) extração
            # se nenhuma aba foi informada, tenta extrair a tabela visível atual
            if not tabs_to_extract:
                self._extract_table_to_csv(pbi_frame, self.export_dir / "PaginaAtual.csv", "PaginaAtual")
            else:
                for tab in tabs_to_extract:
                    print(f"[INFO] Processando aba: '{tab}'")
                    try:
                        # tenta achar o botão/aba por vários atributos/rotulos
                        loc = pbi_frame.locator(
                            f'[aria-label="{tab}"], [title="{tab}"], [data-tooltip-content="{tab}"]'
                        )
                        if loc.count() == 0:
                            loc = pbi_frame.locator(f'text="{tab}"').first
                        loc.wait_for(state="visible", timeout=15000)
                        loc.click(timeout=10000)
                        # aguarda render
                        try: pbi_frame.wait_for_load_state("domcontentloaded", timeout=8000)
                        except Exception: pass

                        out_csv = self.export_dir / f"{tab.replace(' ', '_')}.csv"
                        self._extract_table_to_csv(pbi_frame, out_csv, tab)
                    except PWTimeoutError:
                        print(f"[ERRO] Timeout no botão/aba '{tab}'.")
                        self._save_html(page, f"erro_{tab}")
                    except Exception as e:
                        print(f"[ERRO] Falha ao processar a aba '{tab}': {e}")
                        self._save_html(page, f"erro_{tab}")

            excel_path = None
            if merge_to_excel:
                try:
                    excel_path = self.merge_exports_to_xlsx(out_xlsx=out_xlsx_path)
                except Exception as e:
                    print("[WARN] merge_to_excel falhou:", e)

            if wait_ms:
                page.wait_for_timeout(wait_ms)

            html = page.content()
            context.close(); browser.close()

        return CollectResponse(
            raw=html,
            extracted=None,
            meta={
                "engine": "playwright",
                "used_return_url": use_return_url,
                "export_dir": str(self.export_dir.resolve()),
                "excel_path": excel_path,
            },
        )
