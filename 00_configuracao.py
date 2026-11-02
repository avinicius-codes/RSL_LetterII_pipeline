# ##########################################################################
# RSL LETTER II - Does early-season burn configuration constrain subsequent
# fires in Cerrado Indigenous Lands?  (Remote Sensing Letters)
# Dias, Alcantara & Rodrigues - codigo de analise (Google Colab + Earth Engine)
#
# BLOCO 00 - Configuracao: Google Drive + Earth Engine + 14 TIs com BRIF + funcoes comuns
# Roda em TODA sessao, antes de qualquer outro bloco.
#
# SEQUENCIA DOS BLOCOS (rode nesta ordem; cada um grava checkpoints e pode ser
# rodado de novo sem refazer o que ja existe):
#   00 configuracao                      09 configuracao pelo modelo nulo (SES)
#   01 cicatrizes MapBiomas Fogo         10 encontros nas bordas (segmentos)
#   02 elegibilidade -> amostra final    11 detectabilidade (NBR x MODIS)
#   03 rasters de 30 m por TI            12 modelos referencia x configuracao
#   04 ERA5-Land diario                  13 inferencia para poucas TIs
#   05 focos MODIS (MOD14A1 + MYD14A1)   14 robustez
#   06 estacao seca (artigo 1 + local)   15 sintese em texto (PT e EN)
#   07 tipologia das cicatrizes iniciais 16 figuras e tabela da letter
#   08 quantidade x configuracao (celula)17 figuras de sensoriamento remoto
#
# Periodo: so pos-BRIF (2014-2024); 2013 = transicao (nunca analisado);
# 2012-2013 so como historico de fogo (defasagens t-1 e t-2).
# Resultado = evidencia observacional: nada e atribuido as BRIFs e nenhuma
# queimada e chamada de prescrita sem documentacao independente.
# ##########################################################################

!pip -q install geemap geopandas pyogrio shapely tqdm rich pyarrow rasterio statsmodels scipy matplotlib pyfixest scikit-learn joblib wildboottest python-docx

import io
import os
import json
import time
import glob
import warnings
from pathlib import Path
from datetime import datetime

import ee
import geemap
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from tqdm.auto import tqdm
from rich.console import Console
from rich.table import Table
from google.colab import drive, auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

warnings.filterwarnings("ignore")
import logging
logging.getLogger("google_auth_httplib2").setLevel(logging.ERROR)
console = Console()
BLOCKS_VERSION = "2026-10-17-final"   # todos os blocos conferem esta versao

# ============================================================
# 1. USER CONFIGURATION
# ============================================================

PROJECT_NAME = "RSL_LETTER_II"          # pasta no Drive: MyDrive/RSL_LETTER_II (exportacoes do EE: MyDrive/RSL_LETTER_II_exports)
PROJECT_ROOT = Path(f"/content/drive/MyDrive/{PROJECT_NAME}")

FORCE_REPROCESS = False

# --- Periodo -------------------------------------------------------------
START_YEAR      = 2002
PRE_PERIOD      = (2002, 2012)   # pre-BRIF (so referencia ao artigo 1)
TRANSITION_YEAR = 2013           # ACT Funai-Ibama assinado em 2013; brigadas comecam em 2014
POST_PERIOD     = (2014, 2025)   # pos-BRIF (definicao da dissertacao)
END_YEAR        = 2024           # a letter analisa 2014-2024
YEARS = list(range(POST_PERIOD[0], END_YEAR + 1))
N_LAGS = 2                       # cicatrizes de 2012-2013 so como defasagem de 2014-2015

# --- Estacao seca: recorte do ARTIGO 1 (principal) ------------------------
#   inicio da seca  = mai-jul -> cicatrizes anteriores
#   restante da seca = ago-out -> queimadas posteriores
# Sensibilidade (bloco 06): seca local por TI (CHIRPS), mesma divisao.
DRY_MONTHS = (5, 6, 7, 8, 9, 10)
EARLY      = (5, 6, 7)
LATE       = (8, 9, 10)
SEASON_MAIN = "artigo1"
ELNINO     = [2015, 2023]

# --- Escalas espaciais ----------------------------------------------------
PIX_M      = 30
CELL_SIZES = [2490, 4980, 9990]    # ~2,5 / 5 / 10 km (sensibilidade); principal = 4980

# --- Earth Engine ---------------------------------------------------------
EE_PROJECT       = "smart-firmament-481617-n0"
EE_ASSET_PROJECT = "smart-firmament-481617-n0"
EE_ASSET_TIS     = f"projects/{EE_ASSET_PROJECT}/assets/tis_poligonais"
EE_ASSET_BIOME   = f"projects/{EE_ASSET_PROJECT}/assets/biome_border"
CLIPPED_ASSET_ID = f"projects/{EE_ASSET_PROJECT}/assets/RSL2_tis_poligonais_cerrado"   # ativo novo (rodada do zero)

# --- As 14 TIs com BRIF documentada no artigo submetido -----------------
# Tabela 1 de Dias et al. (2026). Selecao SEMPRE pelo codigo FUNAI.
COHORT_14 = {
    4602:  ("Ava-Canoeiro",        31382.34),
    2401:  ("Apinaye",             142342.10),
    5201:  ("Bakairi",             62123.55),
    7702:  ("Cachoeirinha",        24428.54),   # 7701 = poligono duplicado
    13601: ("Governador",          34003.31),
    20001: ("Kadiweu",             172119.93),
    20701: ("Kanela",              125575.79),
    23301: ("Kraolandia",          306030.23),
    25701: ("Limao Verde",         5209.87),
    33401: ("Paresi",              562192.89),
    33501: ("Parque do Araguaia",  1359314.28),
    36601: ("Porquinhos",          79406.80),
    50301: ("Xerente",             171257.31),
    49901: ("Xacriaba",            23223.94),
}
AREA_TOL_PCT    = 5.0
CERRADO_MIN_PCT = 10.0
EXPECTED_N_TIS  = 14
POSSIBLE_NAME_FIELDS = ["terrai_nom", "terrai_nome", "nome", "Nome", "NOME", "nome_ti", "NOME_TI",
                        "name", "Name", "NAME"]
POSSIBLE_CODE_FIELDS = ["terrai_cod", "cod_funai", "codigo_funai", "COD_FUNAI", "terrai_codi", "codigo"]

EE_EXPORT_FOLDER = f"{PROJECT_NAME}_exports"
MONITOR_INTERVAL = 60
MONITOR_TIMEOUT  = 18000

AREA_CRS = "EPSG:5880"     # SIRGAS 2000 / Brazil Polyconic
CELL_M   = 4980

FIG_DPI = 600              # todas as figuras (Remote Sensing Letters)
CAT_ORDER = ["Inicial pequena e fraca", "Inicial pequena e intensa",
             "Inicial grande", "Restante da seca"]
CAT_COLORS = {"Inicial pequena e fraca": "#1b7837", "Inicial pequena e intensa": "#7fbf7b",
              "Inicial grande": "#c2a5cf", "Restante da seca": "#b2182b"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "figure.dpi": 150,
    "savefig.dpi": FIG_DPI,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# ============================================================
# 2. SAFE GOOGLE DRIVE MOUNT
# ============================================================

if Path("/content/drive/MyDrive").exists():
    console.print("[green]OK Google Drive already mounted.[/green]")
else:
    drive.mount("/content/drive")
    console.print("[green]OK Google Drive mounted.[/green]")

# ============================================================
# 3. FOLDER STRUCTURE
# ============================================================

DIRS = {
    "raw":        PROJECT_ROOT / "00_raw",
    "boundaries": PROJECT_ROOT / "01_boundaries",
    "cache":      PROJECT_ROOT / "02_cache",
    "tables":     PROJECT_ROOT / "03_tables",
    "stats":      PROJECT_ROOT / "04_stats",
    "figures":    PROJECT_ROOT / "05_figures",
    "logs":       PROJECT_ROOT / "06_logs",
    "exports":    PROJECT_ROOT / "07_exports",
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)
console.print(f"[green]OK Project folders ready:[/green] {PROJECT_ROOT}")

# ============================================================
# 4. EARTH ENGINE INITIALIZATION
# ============================================================

EE_FORCE_AUTH = False

def _ee_init() -> str:
    try:
        ee.Initialize(project=EE_PROJECT)
        return "ok"
    except Exception as e:
        return str(e)

if EE_FORCE_AUTH:
    ee.Authenticate(force=True)
msg = _ee_init()
if msg != "ok":
    if "required permission" in msg or "USER_PROJECT_DENIED" in msg:
        console.print(f"[yellow]A conta logada nao tem permissao no projeto {EE_PROJECT}. "
                      "Refazendo o login: escolha a conta DONA do projeto.[/yellow]")
    ee.Authenticate(force=True)
    msg = _ee_init()
if msg != "ok":
    raise RuntimeError(
        f"Earth Engine nao inicializou no projeto {EE_PROJECT}:\n{msg}\n\n"
        "Saidas possiveis:\n"
        "  1) Rode de novo e, no login, escolha a conta dona do projeto.\n"
        "  2) Ou, logado como dono, de a sua outra conta o papel 'Service Usage Consumer' em\n"
        f"     https://console.cloud.google.com/iam-admin/iam?project={EE_PROJECT}\n"
        "  3) Ou troque EE_PROJECT/EE_ASSET_PROJECT por um projeto em que esta conta tenha acesso.")
console.print(f"[green]OK Earth Engine initialized: {EE_PROJECT}[/green]")

PROJ = ee.Projection(AREA_CRS)

# ============================================================
# 4b. ANOS DISPONIVEIS NOS DADOS
# ============================================================

FIRE_ASSET = ("projects/mapbiomas-public/assets/brazil/fire/collection4/"
              "mapbiomas_fire_collection4_monthly_burned_v1")
FIRE_BAND  = lambda y: f"burned_monthly_{y}"
LULC_ASSET         = "projects/mapbiomas-public/assets/brazil/lulc/v1"
LULC_COLLECTION_ID = 10.0
LULC_VERSION       = "v1"

fire_last = max(int(b.rsplit("_", 1)[1]) for b in ee.Image(FIRE_ASSET).bandNames().getInfo()
                if b.startswith("burned_monthly_"))
lulc_last = int(ee.ImageCollection(LULC_ASSET)
                .filter(ee.Filter.eq("collection_id", LULC_COLLECTION_ID))
                .filter(ee.Filter.eq("version", LULC_VERSION))
                .aggregate_max("year").getInfo())
last_ok = min(END_YEAR, fire_last, lulc_last)
if last_ok < END_YEAR:
    console.print(f"[yellow]WARNING MapBiomas Fogo vai ate {fire_last} e a Cobertura ate {lulc_last}. "
                  f"Analise rodando {POST_PERIOD[0]}-{last_ok}.[/yellow]")
YEARS = [y for y in YEARS if y <= last_ok]
SCAR_YEARS = list(range(YEARS[0] - N_LAGS, YEARS[-1] + 1))
assert TRANSITION_YEAR not in YEARS and all(POST_PERIOD[0] <= y <= POST_PERIOD[1] for y in YEARS)
console.print(f"[cyan]Anos analisados (pos-BRIF):[/cyan] {YEARS[0]}-{YEARS[-1]} | "
              f"[cyan]so defasagem do fogo:[/cyan] {SCAR_YEARS[0]}-{YEARS[0] - 1} | "
              f"[cyan]transicao (nunca analisada):[/cyan] {TRANSITION_YEAR}")

# ============================================================
# 5. CACHE / TABLE UTILITIES
# ============================================================

def cache_path(name, ext="parquet"):
    return DIRS["cache"] / f"{name}.{ext}"

def table_path(name, ext="csv"):
    return DIRS["tables"] / f"{name}.{ext}"

def stats_path(name, ext="csv"):
    return DIRS["stats"] / f"{name}.{ext}"

def fig_path(name, ext="png"):
    return DIRS["figures"] / f"{name}.{ext}"

def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)

def read_table(path):
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix in (".gpkg", ".geojson"):
        return gpd.read_file(path)
    raise ValueError(f"Unsupported format: {path}")

def write_table(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix == ".gpkg":
        df.to_file(path, driver="GPKG")
    else:
        raise ValueError(f"Unsupported format: {path}")

def checkpoint_load_or_run(name, func, ext="parquet", force=FORCE_REPROCESS):
    """Carrega o checkpoint se existir; senao roda func() e salva."""
    path = cache_path(name, ext)
    if path.exists() and not force:
        console.print(f"[cyan]OK Loading checkpoint:[/cyan] {path.name}")
        return read_table(path)
    console.print(f"[yellow]-> Processing:[/yellow] {name}")
    df = func()
    write_table(df, path)
    console.print(f"[green]OK Checkpoint saved:[/green] {path}")
    return df

# ============================================================
# 6. EARTH ENGINE EXPORT -> MONITOR -> DRIVE DOWNLOAD
# ============================================================

def get_active_tasks() -> dict:
    try:
        return {t["description"]: t["id"] for t in ee.data.getTaskList()
                if t.get("state") in ("RUNNING", "READY")}
    except Exception:
        return {}

def ee_monitor(ids_by_name: dict) -> dict:
    """Acompanha as tarefas PELO ID. Devolve {nome: estado}."""
    pending = dict(ids_by_name)
    done, t0 = {}, time.time()
    if not pending:
        return done
    console.print(f"[cyan]Monitoring {len(pending)} tasks...[/cyan]")
    while pending:
        try:
            for st in ee.data.getTaskStatus(list(pending.values())):
                name = next((n for n, i in pending.items() if i == st.get("id")), None)
                if name is None:
                    continue
                state = st.get("state", "")
                if state == "COMPLETED":
                    done[name] = state; pending.pop(name)
                    console.print(f"  [green]OK {name}: COMPLETED[/green]")
                elif state in ("FAILED", "CANCELLED"):
                    done[name] = state; pending.pop(name)
                    console.print(f"  [red]X {name}: {state} - {st.get('error_message', '')}[/red]")
        except Exception as e:
            console.print(f"[yellow]WARNING checking status: {e}[/yellow]")
        if not pending:
            break
        if time.time() - t0 > MONITOR_TIMEOUT:
            for n in pending:
                done[n] = "TIMEOUT"
            console.print(f"[red]WARNING timeout. Pending: {sorted(pending)}[/red]")
            break
        console.print(f"  [dim]{len(done)}/{len(done) + len(pending)} | {len(pending)} pending | "
                      f"{MONITOR_INTERVAL}s...[/dim]")
        time.sleep(MONITOR_INTERVAL)
    bad = [n for n, s in done.items() if s != "COMPLETED"]
    if bad:
        save_json({"failed": bad, "at": datetime.now()}, DIRS["logs"] / f"failed_tasks_{int(time.time())}.json")
    return done

def launch_or_attach(names: list, make_task) -> dict:
    active = get_active_tasks()
    ids = {}
    for n in names:
        if n in active:
            ids[n] = active[n]
            console.print(f"[cyan]OK Task already active: {n}[/cyan]")
            continue
        task = make_task(n)
        task.start()
        ids[n] = task.id
        console.print(f"[yellow]-> Task launched: {n}[/yellow]")
        time.sleep(0.5)
    return ids

def _drive_call_with_retry(request_fn, max_retries=6):
    from googleapiclient.errors import HttpError
    for attempt in range(max_retries):
        try:
            return request_fn()
        except HttpError as e:
            if e.resp.status == 403 and "rateLimitExceeded" in str(e) and attempt < max_retries - 1:
                wait = min(2 ** attempt * 2, 60)
                console.print(f"  [yellow]Rate limit hit, waiting {wait}s...[/yellow]")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Drive API retries exhausted.")

def _export_folder_id(svc):
    """id da pasta EE_EXPORT_FOLDER no Drive (None se ainda nao existe). A busca de arquivos
    exportados fica restrita a ela: arquivos de rodadas antigas em outras pastas nunca sao usados."""
    res = _drive_call_with_retry(lambda: svc.files().list(
        q=f"name='{EE_EXPORT_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces="drive", fields="files(id, name)").execute())
    f = res.get("files", [])
    return f[0]["id"] if f else None

def drive_download(filenames: list, dest_dir: Path, quiet: bool = False) -> list:
    auth.authenticate_user()
    svc = build("drive", "v3", cache_discovery=False)
    folder = _export_folder_id(svc)
    got = []
    for fn in filenames:
        dest = Path(dest_dir) / fn
        if dest.exists():
            got.append(dest)
            continue
        if folder is None:                      # pasta de exportacao ainda nao existe: nada a baixar
            continue
        res = _drive_call_with_retry(lambda: svc.files().list(
            q=f"name='{fn}' and '{folder}' in parents and trashed=false", spaces="drive",
            orderBy="createdTime desc", fields="files(id, name)").execute())
        time.sleep(1.5)
        files = res.get("files", [])
        if not files:
            if not quiet:
                console.print(f"  [yellow]WARNING not found on Drive: {fn}[/yellow]")
            continue
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, svc.files().get_media(fileId=files[0]["id"]))
        finished = False
        while not finished:
            _, finished = _drive_call_with_retry(lambda: downloader.next_chunk())
        dest.write_bytes(buf.getvalue())
        got.append(dest)
        console.print(f"  [green]OK {fn}[/green]")
        time.sleep(1.5)
    return got

def run_ee_exports(specs: dict, ext: str, dest_dir: Path) -> list:
    """specs = {descricao: funcao_sem_argumentos -> ee.batch.Task (nao iniciada)}."""
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    need = [d for d in specs if not (dest_dir / f"{d}.{ext}").exists()]
    console.print(f"  Ja baixados: {len(specs) - len(need)} | A processar: {len(need)}")
    if need:
        drive_download([f"{d}.{ext}" for d in need], dest_dir, quiet=True)
        need = [d for d in need if not (dest_dir / f"{d}.{ext}").exists()]
    if need:
        ids = launch_or_attach(need, lambda d: specs[d]())
        status = ee_monitor(ids)
        drive_download([f"{d}.{ext}" for d in need if status.get(d) == "COMPLETED"], dest_dir)
    paths = [dest_dir / f"{d}.{ext}" for d in specs if (dest_dir / f"{d}.{ext}").exists()]
    if len(paths) < len(specs):
        console.print(f"[red]WARNING {len(specs) - len(paths)} arquivo(s) faltando - "
                      "rode o bloco de novo mais tarde.[/red]")
    return paths

# ============================================================
# 7. AS 14 TIs COM BRIF - pelo CODIGO FUNAI
#    tis_poligonais -> 14 codigos -> recorte no Cerrado (biome_border) -> >= 10%
#    Poligonos sem simplificar; areas em EPSG:5880, margem de erro de 1 m.
# ============================================================

EXACT = ee.ErrorMargin(1)

def _as_number(v):
    return ee.Number(ee.Algorithms.If(ee.Algorithms.ObjectType(v).equals("String"),
                                      ee.Number.parse(v), v))

def _check_fields():
    props = ee.Feature(ee.FeatureCollection(EE_ASSET_TIS).first()).propertyNames().getInfo()
    code_field = next((c for c in POSSIBLE_CODE_FIELDS if c in props), None)
    name_field = next((c for c in POSSIBLE_NAME_FIELDS if c in props), None)
    if code_field is None:
        raise RuntimeError(f"Nao achei o campo de codigo FUNAI em {EE_ASSET_TIS}. Campos: {props}.")
    console.print(f"[dim]Campos usados: codigo='{code_field}', nome='{name_field}'[/dim]")
    return code_field, name_field

def build_tis_server(code_field, name_field, codes):
    raw_fc = ee.FeatureCollection(EE_ASSET_TIS).filter(ee.Filter.Or(
        ee.Filter.inList(code_field, codes),
        ee.Filter.inList(code_field, [str(c) for c in codes])))
    biome_geom = ee.FeatureCollection(EE_ASSET_BIOME).geometry(EXACT)

    def _clip(f):
        f = ee.Feature(f)
        geom = f.geometry()
        inter = geom.intersection(biome_geom, EXACT, PROJ)
        return ee.Feature(inter, {
            "terrai_cod":      _as_number(f.get(code_field)),
            "nome_ativo":      f.get(name_field) if name_field else "",
            "area_total_ha":   geom.area(EXACT, PROJ).divide(1e4),
            "area_cerrado_ha": inter.area(EXACT, PROJ).divide(1e4),
        })
    return raw_fc.map(_clip)

def prepare_tis_asset() -> ee.FeatureCollection:
    code_field, name_field = _check_fields()
    codes = list(COHORT_14)
    clipped = build_tis_server(code_field, name_field, codes)

    info = clipped.map(lambda f: ee.Feature(None, ee.Feature(f).toDictionary())).getInfo()
    df = pd.DataFrame([x["properties"] for x in info["features"]])
    if df.empty:
        raise RuntimeError(f"Nenhum dos 14 codigos encontrado em {EE_ASSET_TIS}.")
    df["terrai_cod"] = df["terrai_cod"].astype(int)
    df = df.groupby("terrai_cod", as_index=False).agg(
        nome_ativo=("nome_ativo", "first"), n_poligonos=("nome_ativo", "size"),
        area_total_ha=("area_total_ha", "sum"), area_cerrado_ha=("area_cerrado_ha", "sum"))

    faltam = [f"{c} ({COHORT_14[c][0]})" for c in codes if c not in set(df["terrai_cod"])]
    if faltam:
        raise RuntimeError(f"Codigo(s) FUNAI nao encontrado(s) em {EE_ASSET_TIS}: {', '.join(faltam)}.")
    df["ti_name"] = df["terrai_cod"].map(lambda c: COHORT_14[c][0])
    df["area_artigo_ha"] = df["terrai_cod"].map(lambda c: COHORT_14[c][1])
    df["pct_cerrado"] = 100 * df["area_cerrado_ha"] / df["area_total_ha"]
    df["dif_area_vs_artigo_%"] = 100 * (df["area_cerrado_ha"] / df["area_artigo_ha"] - 1)
    df.to_csv(DIRS["stats"] / "tis_conferencia_codigo_nome_area.csv", index=False)
    console.print("[bold]Conferencia das 14 TIs (codigo FUNAI -> nome no ativo, area no Cerrado x Tabela 1)[/bold]")
    display(df[["terrai_cod", "ti_name", "nome_ativo", "n_poligonos", "area_cerrado_ha",
                "area_artigo_ha", "dif_area_vs_artigo_%", "pct_cerrado"]].round(2))
    off = df[df["dif_area_vs_artigo_%"].abs() > AREA_TOL_PCT]
    if len(off):
        console.print(f"[yellow]WARNING area difere > {AREA_TOL_PCT}% da Tabela 1 em: "
                      f"{', '.join(off['ti_name'])}.[/yellow]")

    kept = df[df["pct_cerrado"] >= CERRADO_MIN_PCT].sort_values("terrai_cod").reset_index(drop=True)
    kept["ti_id"] = np.arange(1, len(kept) + 1)
    if len(kept) != EXPECTED_N_TIS:
        console.print(f"[red]WARNING ficaram {len(kept)} TIs (esperado {EXPECTED_N_TIS}).[/red]")
    kept.to_csv(DIRS["stats"] / "tis_cerrado_overlap_pct.csv", index=False)

    try:
        cur = ee.FeatureCollection(CLIPPED_ASSET_ID).aggregate_array("terrai_cod").getInfo()
        if sorted(int(c) for c in cur) == sorted(kept["terrai_cod"].tolist()):
            console.print(f"[green]OK {CLIPPED_ASSET_ID} ja existe com as {len(kept)} TIs - reaproveitando.[/green]")
            return ee.FeatureCollection(CLIPPED_ASSET_ID)
    except Exception:
        pass

    id_map = ee.Dictionary({str(c): int(i) for c, i in zip(kept["terrai_cod"], kept["ti_id"])})
    nm_map = ee.Dictionary({str(c): n for c, n in zip(kept["terrai_cod"], kept["ti_name"])})
    keep_codes = kept["terrai_cod"].tolist()

    def _props(f):
        f = ee.Feature(f)
        key = ee.Number(f.get("terrai_cod")).format("%d")
        return f.set({"ti_id": id_map.get(key), "ti_name": nm_map.get(key),
                      "area_ha": f.get("area_cerrado_ha"),
                      "area_km2": ee.Number(f.get("area_cerrado_ha")).divide(100)})
    out = clipped.filter(ee.Filter.inList("terrai_cod", keep_codes)).map(_props)

    try:
        ee.data.deleteAsset(CLIPPED_ASSET_ID)
    except Exception:
        pass
    task = ee.batch.Export.table.toAsset(collection=out, description="RSL2_tis_poligonais_cerrado",
                                         assetId=CLIPPED_ASSET_ID)
    task.start()
    console.print(f"[yellow]-> Criando o ativo {CLIPPED_ASSET_ID}...[/yellow]")
    while True:
        st = task.status()
        if st["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(20)
    if st["state"] != "COMPLETED":
        raise RuntimeError(f"Falha ao criar {CLIPPED_ASSET_ID}: {st}")
    return ee.FeatureCollection(CLIPPED_ASSET_ID)

tis_fc = prepare_tis_asset()
tis = geemap.ee_to_gdf(tis_fc)
tis = (tis.set_crs("EPSG:4326") if tis.crs is None else tis).to_crs(AREA_CRS)
tis["ti_id"] = tis["ti_id"].astype(int)
tis["terrai_cod"] = pd.to_numeric(tis["terrai_cod"]).astype(int)
tis = (tis.dissolve(by="ti_id", as_index=False, aggfunc={"terrai_cod": "first", "ti_name": "first",
                                                         "area_ha": "sum", "area_km2": "sum"})
          .sort_values("ti_id").reset_index(drop=True))
tis.to_file(DIRS["boundaries"] / "tis_brif_cerrado.gpkg", driver="GPKG")

ti_img = ee.Image(0).int().paint(tis_fc, "ti_id")

# Etiquetas dos checkpoints (nunca reaproveitar arquivos de outro conjunto de TIs/anos)
# "r2" = rodada do zero na pasta RSL_LETTER_II: nomes de tarefas e arquivos NOVOS, que nunca
# coincidem com os de rodadas antigas (v4_...) -> nada antigo e reaproveitado
RUN_TAG    = f"r2_{len(tis)}tp"
TAG_YEARS  = f"{YEARS[0]}_{YEARS[-1]}_{RUN_TAG}"
SCARS_NAME = f"cicatrizes_{SCAR_YEARS[0]}_{YEARS[-1]}_{RUN_TAG}"
FOCOS_NAME = f"modis_focos_v1_{TAG_YEARS}"     # focos MODIS (bloco 05)
TAG_SEG    = f"{TAG_YEARS}_md"                  # tudo o que usa focos MODIS (blocos 07, 10-17)

# ============================================================
# 8. TABELA DO PRIMEIRO ARTIGO: classe e FRRI de cada TI
#    Preencha 00_raw/artigo1_tis.csv (terrai_cod, classe, frri).
# ============================================================

def load_artigo1() -> pd.DataFrame:
    manual = DIRS["raw"] / "artigo1_tis.csv"
    base = tis[["ti_id", "terrai_cod", "ti_name"]].rename(columns={"ti_name": "nome"})
    if not manual.exists():
        modelo = DIRS["raw"] / "artigo1_tis_MODELO.csv"
        base.assign(classe="", frri="").to_csv(modelo, index=False)
        console.print(f"[yellow]WARNING sem {manual.name}: comparacoes com o FRRI ficam em branco. "
                      f"Preencha o modelo {modelo} e salve como {manual.name}.[/yellow]")
        return base.assign(classe=np.nan, frri=np.nan)
    a = pd.read_csv(manual)
    key = "terrai_cod" if "terrai_cod" in a.columns else "ti_id"
    a = base.merge(a[[key, "classe", "frri"]], on=key, how="left")
    a["frri"] = pd.to_numeric(a["frri"], errors="coerce")
    return a[["ti_id", "terrai_cod", "nome", "classe", "frri"]]

artigo1 = load_artigo1()
artigo1.to_csv(table_path("artigo1_tis"), index=False)

# ============================================================
# 8b. FUNCOES COMUNS DOS BLOCOS 02-17
# ============================================================

def load_sample_ids() -> list:
    """ti_id das TIs elegiveis (bloco 02). Sem a triagem, PARA (nao roda as 14 por engano)."""
    p = table_path("amostra_final_tis")
    if not p.exists():
        raise RuntimeError(f"Amostra final nao encontrada ({p.name}) - rode o bloco 02.")
    a = pd.read_csv(p)
    ids = a.loc[a["elegivel"].astype(bool), "ti_id"].astype(int).tolist()
    console.print(f"[dim]Amostra final: {len(ids)} TIs[/dim]")
    return ids

def load_seasons() -> dict:
    """{esquema: {ti_id: (meses_iniciais, meses_restantes)}}. 'artigo1' sempre; 'local' do bloco 06."""
    s = {"artigo1": {int(t): (tuple(EARLY), tuple(LATE)) for t in tis["ti_id"]}}
    p = table_path("estacoes_por_ti", "json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        for sch, d in raw.items():
            s[sch] = {int(k): (tuple(v["inicio"]), tuple(v["restante"])) for k, v in d.items()}
    return s

# --- Rasters de 30 m por TI (bloco 03) ------------------------------------
RASTER_DIR   = DIRS["exports"] / "rasters"
LS_MONTHS    = list(range(4, 12))     # abr-nov
NODATA       = -32768
YEAR_BANDS   = (["month", "cover"] + [f"nbr{m:02d}" for m in LS_MONTHS]
                + [f"cnt{m:02d}" for m in LS_MONTHS])
STATIC_BANDS = ["ti", "elev", "slope10", "barrier", "river"]

# --- Uso do solo -> combustivel (MapBiomas Col. 10)
#   1 natural | 2 pastagem e mosaico | 3 agricultura e silvicultura | 4 NAO combustivel | 0 sem dado
COVER_CLASSES = {
    1: [3, 4, 5, 6, 11, 12, 13, 29, 32, 49, 50],
    2: [15, 21],
    3: [9, 18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48, 62],
    4: [22, 23, 24, 25, 30, 31, 33],
}
FUEL_MODES = {"todos_vegetados": (1, 2, 3), "nativa+pastagem": (1, 2), "nativa": (1,)}
FUEL_MAIN  = "todos_vegetados"
FUEL_RUNS  = ["todos_vegetados", "nativa+pastagem"]
FUEL_TAG   = {"todos_vegetados": "tv", "nativa+pastagem": "np", "nativa": "n"}

def fuel_from_cover(cover, mode=FUEL_MAIN):
    return np.isin(cover, FUEL_MODES[mode])

def raster_name(ti_id, year=None):
    return (f"l9_{RUN_TAG}_v3_static_ti{int(ti_id)}" if year is None
            else f"l9_{RUN_TAG}_v3_yr_ti{int(ti_id)}_{int(year)}")

RASTER_BUFFER_M = 2000

def read_raster(ti_id, year=None) -> dict:
    """Le um raster do bloco 03 -> {banda: array, '_transform', '_shape', '_crs'}, na grade da TI."""
    import rasterio
    from rasterio.windows import Window
    from rasterio.transform import Affine
    p = RASTER_DIR / f"{raster_name(ti_id, year)}.tif"
    if not p.exists():
        raise FileNotFoundError(f"{p.name} nao existe - rode o bloco 03.")
    names = STATIC_BANDS if year is None else YEAR_BANDS
    minx, miny, maxx, maxy = tis.set_index("ti_id").loc[ti_id].geometry.bounds
    x0 = float(np.floor((minx - RASTER_BUFFER_M) / PIX_M) * PIX_M)
    y0 = float(np.floor((miny - RASTER_BUFFER_M) / PIX_M) * PIX_M)
    x1 = float(np.ceil((maxx + RASTER_BUFFER_M) / PIX_M) * PIX_M)
    y1 = float(np.ceil((maxy + RASTER_BUFFER_M) / PIX_M) * PIX_M)
    W, H = int(round((x1 - x0) / PIX_M)), int(round((y1 - y0) / PIX_M))
    with rasterio.open(p) as src:
        col = int(round((x0 - src.transform.c) / PIX_M))
        row = int(round((src.transform.f - y1) / PIX_M))
        win, crs = Window(col, row, W, H), src.crs
        out = {}
        for i, n in enumerate(names):
            fill = -128 if n.startswith("nbr") else 0
            out[n] = src.read(i + 1, window=win, boundless=True, fill_value=fill)
    out["_transform"], out["_shape"], out["_crs"] = Affine(PIX_M, 0, x0, 0, -PIX_M, y1), (H, W), crs
    return out

def ti_frame(ti_id):
    """Recorte de cada TI: retangulo da TI + 2 km, grade de 30 m alinhada em EPSG:5880."""
    minx, miny, maxx, maxy = tis.set_index("ti_id").loc[ti_id].geometry.bounds
    x0 = float(np.floor((minx - RASTER_BUFFER_M) / PIX_M) * PIX_M)
    y0 = float(np.floor((miny - RASTER_BUFFER_M) / PIX_M) * PIX_M)
    x1 = float(np.ceil((maxx + RASTER_BUFFER_M) / PIX_M) * PIX_M)
    y1 = float(np.ceil((maxy + RASTER_BUFFER_M) / PIX_M) * PIX_M)
    region = ee.Geometry.Rectangle([x0, y0, x1, y1], PROJ, False)
    transform = [float(PIX_M), 0.0, x0, 0.0, -float(PIX_M), y1]
    n_px = int((x1 - x0) / PIX_M * (y1 - y0) / PIX_M)
    return region, transform, n_px

def export_image_task(img, name, region, transform):
    return ee.batch.Export.image.toDrive(
        image=img, description=name, folder=EE_EXPORT_FOLDER, fileNamePrefix=name,
        region=region, crs=AREA_CRS, crsTransform=transform, maxPixels=1e13, fileFormat="GeoTIFF")

def drive_download_tif(name, dest_dir, quiet=False):
    """Baixa um GeoTIFF exportado pelo EE; se veio em pedacos, junta num arquivo so."""
    import rasterio
    from rasterio.merge import merge as rio_merge
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}.tif"
    if dest.exists():
        return dest
    auth.authenticate_user()
    svc = build("drive", "v3", cache_discovery=False)
    folder = _export_folder_id(svc)
    if folder is None:
        return None
    res = _drive_call_with_retry(lambda: svc.files().list(
        q=f"name contains '{name}' and '{folder}' in parents and trashed=false", spaces="drive",
        orderBy="createdTime desc", fields="files(id, name)").execute())
    files = [f for f in res.get("files", [])
             if f["name"] == f"{name}.tif" or (f["name"].startswith(f"{name}-") and f["name"].endswith(".tif"))]
    # o mesmo arquivo exportado mais de uma vez fica com nomes repetidos no Drive: usa so o
    # mais recente de cada nome (a lista ja vem do mais novo para o mais antigo)
    _vistos = set()
    files = [f for f in files if not (f["name"] in _vistos or _vistos.add(f["name"]))]
    inteiro = [f for f in files if f["name"] == f"{name}.tif"]
    if inteiro:                                   # arquivo inteiro tem prioridade sobre pedacos
        files = inteiro
    if not files:
        if not quiet:
            console.print(f"  [yellow]WARNING nao achei {name} no Drive[/yellow]")
        return None
    parts = []
    for f in files:
        p = dest_dir / f["name"]
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=f["id"]))
        done = False
        while not done:
            _, done = _drive_call_with_retry(lambda: dl.next_chunk())
        p.write_bytes(buf.getvalue())
        parts.append(p)
        time.sleep(1.0)
    if len(parts) > 1:
        srcs = [rasterio.open(p) for p in parts]
        mosaic, tr = rio_merge(srcs)
        meta = srcs[0].meta.copy()
        meta.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=tr, compress="deflate")
        for s in srcs:
            s.close()
        with rasterio.open(dest, "w", **meta) as dst:
            dst.write(mosaic)
        for p in parts:
            p.unlink(missing_ok=True)
    else:
        parts[0].rename(dest)
    console.print(f"  [green]OK {dest.name}[/green]")
    return dest

def run_image_exports(specs: dict, dest_dir) -> list:
    """specs = {nome: (funcao -> ee.Image, region, transform)}. Devolve os nomes que ainda faltam."""
    dest_dir = Path(dest_dir)
    need = [n for n in specs if not (dest_dir / f"{n}.tif").exists()]
    console.print(f"  Ja baixados: {len(specs) - len(need)} | A processar: {len(need)}")
    for n in need:
        drive_download_tif(n, dest_dir, quiet=True)
    need = [n for n in need if not (dest_dir / f"{n}.tif").exists()]
    if need:
        def _make(n):
            make, region, transform = specs[n]
            return export_image_task(make(), n, region, transform)
        ids = launch_or_attach(need, _make)
        status = ee_monitor(ids)
        for n in need:
            if status.get(n) == "COMPLETED":
                drive_download_tif(n, dest_dir)
    return [n for n in specs if not (dest_dir / f"{n}.tif").exists()]

_STATIC = {}

def static_of(ti_id):
    if ti_id not in _STATIC:
        _STATIC[ti_id] = read_raster(ti_id)
    return _STATIC[ti_id]

RES_METODO = "curva_q_v2"

def residualize_conf(df, conf_vars, q="q_inicio", nbins=50):
    """conf_*_res = configuracao MENOS o que a quantidade explica (curva por faixas de q).
    Usado so como sensibilidade; a medida principal e o SES do modelo nulo (bloco 09)."""
    df = df.copy()
    qv = df[q].to_numpy(float)
    pos = qv > 0
    edges = np.unique(np.quantile(qv[pos], np.linspace(0, 1, nbins + 1))) if pos.sum() > nbins else None
    for v in conf_vars:
        if v not in df.columns:
            continue
        y = df[v].to_numpy(float)
        pred = np.full(len(df), np.nan)
        z = ~pos & ~np.isnan(y)
        if z.any():
            pred[~pos] = np.nanmean(y[z])
        okp = pos & ~np.isnan(y)
        if edges is not None and okp.sum() > nbins:
            b = np.clip(np.searchsorted(edges, qv[okp], side="right") - 1, 0, len(edges) - 2)
            qm = pd.Series(qv[okp]).groupby(b).mean()
            ym = pd.Series(y[okp]).groupby(b).mean()
            pred[pos] = np.interp(qv[pos], qm.to_numpy(), ym.to_numpy())
        df[f"{v}_res"] = y - pred
    df["res_metodo"] = RES_METODO
    return df

def _meff(mask):
    """Manchas (vizinhanca de 8) -> (soma das areas^2, maior area, n de manchas), em pixels.
    m_eff (Jaeger 2000) = soma(a_i^2) / area de referencia."""
    from scipy import ndimage
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), int))
    if n == 0:
        return 0.0, 0.0, 0
    a = np.bincount(lab.ravel())[1:].astype(float)
    return float((a ** 2).sum()), float(a.max()), int(n)

def season_masks(month, ti_id, scheme, seasons):
    """antes = queimado antes do inicio da seca | inicio = cicatrizes iniciais | resto = restante."""
    ini, res = seasons[scheme][int(ti_id)]
    return {"antes": (month > 0) & (month < min(ini)),
            "inicio": np.isin(month, ini),
            "resto": np.isin(month, res)}

def check_version():
    if globals().get("BLOCKS_VERSION") != "2026-10-17-final":
        raise RuntimeError("Rode o bloco 00 (configuracao) desta versao antes deste bloco.")

# ============================================================
# 9. SUMMARY
# ============================================================

summary = Table(title="RSL - TIs com BRIF (Cerrado)")
summary.add_column("ti_id"); summary.add_column("TI"); summary.add_column("area (ha)")
summary.add_column("classe"); summary.add_column("FRRI")
for _, r in tis.merge(artigo1.drop(columns=["terrai_cod"]), on="ti_id", how="left").iterrows():
    summary.add_row(str(r["ti_id"]), str(r["ti_name"]), f"{r.get('area_ha', np.nan):,.0f}",
                    str(r.get("classe", "")), f"{r.get('frri', np.nan):.3f}")
console.print(summary)

save_json({"project": PROJECT_NAME, "created_at": datetime.now(), "ee_project": EE_PROJECT,
           "tis_asset": CLIPPED_ASSET_ID, "transition_year": TRANSITION_YEAR,
           "post_period": POST_PERIOD, "years": YEARS, "scar_years": SCAR_YEARS,
           "early": EARLY, "late": LATE, "cell_m": CELL_M, "focos": "MODIS MOD14A1+MYD14A1 C6.1",
           "ti_names": tis["ti_name"].tolist()}, DIRS["logs"] / "project_metadata.json")
console.print(f"[bold green]OK BLOCO 00 completo (versao {BLOCKS_VERSION}).[/bold green]")
