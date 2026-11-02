# ======================================================================
# BLOCO 03 - Pilhas de 30 m por TI (fogo, cobertura, Landsat NBR, relevo, barreiras)
# Depende dos blocos 00 e 02 (amostra final).
# ======================================================================
#
# Tudo o que vem depois (sequencia, configuracao, encontros, modelos) e
# calculado sobre estas pilhas, para qualquer recorte sazonal e escala.
#
# 1) Por TI e por ano (2012-2024; 2012-2013 so como historico):
#      month : mes da queima no MapBiomas Fogo Col. 4 (0 = nao queimou)
#      cover : MapBiomas Cobertura Col. 10 em 4 grupos (1 natural, 2 pastagem/
#              mosaico, 3 agricultura/silvicultura, 4 nao combustivel, 0 sem dado)
#      nbrMM : NBR MINIMO do mes MM (abr-nov), Landsat 8/9 C2 L2 (x100), so
#              observacoes limpas (QA_PIXEL sem nuvem, sombra, cirro); calculado
#              ate 500 m de onde houve fogo no ano (fora: -128 = sem dado)
#      cntMM : n de observacoes limpas do Landsat no mes MM
# 2) Camadas fixas por TI:
#      ti, elev (SRTM), slope10 (graus x 10),
#      barrier : agua / nao vegetado / urbano / mineracao em >= 80% dos anos
#                + rios HydroSHEDS (ordem <= 7) [+ estradas, se ROADS_ASSET]
#      river   : so os rios
#
# Download direto do Earth Engine (ee.data.computePixels, endereco de alto
# volume), em blocos de ate 1024 x 1024 pixels em paralelo, sem tarefas no
# painel e sem passar pelo Drive de exportacao. Bloco pesado demais e dividido
# em 4; recusa por excesso de pedidos -> espera e tenta de novo; arquivo ja
# existente -> pula (se o Colab cair, rode de novo).
#
# Projecao EPSG:5880, grade de 30 m alinhada; recorte = retangulo da TI + 2 km.
# Output: 07_exports/rasters/l9_<tag>_v3_yr_ti<id>_<ano>.tif e ..._static_ti<id>.tif
# ======================================================================

check_version()

import concurrent.futures as cf
import shutil
import rasterio
from rasterio.transform import Affine

# ============================================================
# 1. PARAMETERS
# ============================================================

BARRIER_CLASSES   = [22, 23, 24, 25, 30, 31, 33]
BARRIER_MIN_SHARE = 0.8
RIVER_MAX_ORD     = 7
RIVER_BUFFER_M    = 30
ROADS_ASSET       = ""          # opcional: ativo de linhas de estradas
ROADS_BUFFER_M    = 15
NODATA8           = -128
NEAR_BURN_M       = 500
N_WORKERS         = 10
TILE_PX           = 1024
MIN_TILE          = 128
MAX_TRIES         = 6

RASTER_DIR.mkdir(parents=True, exist_ok=True)
ti_ids = load_sample_ids()
console.print(f"[cyan]TIs com raster:[/cyan] " + ", ".join(tis.set_index("ti_id").loc[ti_ids, "ti_name"])
              + f" | anos: {SCAR_YEARS[0]}-{SCAR_YEARS[-1]}")

# ============================================================
# 2. IMAGENS
# ============================================================

lulc_ic = (ee.ImageCollection(LULC_ASSET)
           .filter(ee.Filter.eq("collection_id", LULC_COLLECTION_ID))
           .filter(ee.Filter.eq("version", LULC_VERSION)))

def lulc(y):
    return lulc_ic.filter(ee.Filter.eq("year", y)).first().select("classification")

def landsat_nbr(img):
    img = ee.Image(img)
    clear = img.select("QA_PIXEL").bitwiseAnd(0b11111).eq(0)   # fill, nuvem dilatada, cirro, nuvem, sombra
    sr = img.select(["SR_B5", "SR_B7"]).multiply(0.0000275).add(-0.2)
    return (sr.normalizedDifference(["SR_B5", "SR_B7"]).toFloat().rename("nbr")
              .updateMask(clear).copyProperties(img, ["system:time_start"]))

L89 = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").select(["SR_B5", "SR_B7", "QA_PIXEL"])
       .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").select(["SR_B5", "SR_B7", "QA_PIXEL"])))
_EMPTY = ee.Image.constant(0).toFloat().rename("nbr").updateMask(ee.Image.constant(0))
_MIN_COUNT = ee.Reducer.min().combine(ee.Reducer.count(), sharedInputs=True)

def year_image(y, region):
    month = ee.Image(FIRE_ASSET).select(FIRE_BAND(y)).unmask(0).toInt8().rename("month")
    frm = [c for g in COVER_CLASSES for c in COVER_CLASSES[g]]
    to = [g for g in COVER_CLASSES for _ in COVER_CLASSES[g]]
    cover = lulc(y).remap(frm, to, 0).unmask(0).toInt8().rename("cover")
    nbrs, cnts = [], []
    if y < YEARS[0]:          # 2012-2013: so historico de fogo, sem Landsat
        for m in LS_MONTHS:
            nbrs.append(ee.Image.constant(NODATA8).toInt8().rename(f"nbr{m:02d}"))
            cnts.append(ee.Image.constant(0).toInt8().rename(f"cnt{m:02d}"))
        return ee.Image.cat([month, cover] + nbrs + cnts)
    near = month.gt(0).focalMax(radius=NEAR_BURN_M, kernelType="circle", units="meters")
    col = (L89.filterBounds(region).filterDate(f"{y}-01-01", f"{y + 1}-01-01")
              .map(landsat_nbr).map(lambda i: ee.Image(i).updateMask(near)))
    for m in LS_MONTHS:
        cm = col.filter(ee.Filter.calendarRange(m, m, "month")).merge(ee.ImageCollection([_EMPTY]))
        red = cm.reduce(_MIN_COUNT)
        nbrs.append(red.select("nbr_min").multiply(100).round().unmask(NODATA8).toInt8().rename(f"nbr{m:02d}"))
        cnts.append(red.select("nbr_count").unmask(0).toInt8().rename(f"cnt{m:02d}"))
    return ee.Image.cat([month, cover] + nbrs + cnts)

def static_image():
    elev = ee.Image("USGS/SRTMGL1_003").select("elevation")
    slope10 = ee.Terrain.slope(elev).multiply(10).round()
    share = ee.Image.cat([lulc(y).remap(BARRIER_CLASSES, [1] * len(BARRIER_CLASSES), 0).unmask(0)
                          for y in YEARS]).reduce(ee.Reducer.mean())
    perm = share.gte(BARRIER_MIN_SHARE)
    rivers = (ee.FeatureCollection("WWF/HydroSHEDS/v1/FreeFlowingRivers")
              .filter(ee.Filter.lte("RIV_ORD", RIVER_MAX_ORD))
              .map(lambda f: ee.Feature(f).buffer(RIVER_BUFFER_M)))
    river = ee.Image(0).paint(rivers, 1)
    barrier = perm.Or(river)
    if ROADS_ASSET:
        roads = ee.FeatureCollection(ROADS_ASSET).map(lambda f: ee.Feature(f).buffer(ROADS_BUFFER_M))
        barrier = barrier.Or(ee.Image(0).paint(roads, 1))
    return ee.Image.cat([ti_img.rename("ti"), elev.rename("elev"), slope10.rename("slope10"),
                         barrier.rename("barrier"), river.rename("river")]).unmask(0).toInt16()

# ============================================================
# 3. DOWNLOAD DIRETO EM BLOCOS
# ============================================================

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
ee.Initialize(project=EE_PROJECT, opt_url="https://earthengine-highvolume.googleapis.com")

def _fetch(img, bands, x0, y1, w, h):
    req = {"expression": img, "fileFormat": "NUMPY_NDARRAY",
           "grid": {"dimensions": {"width": int(w), "height": int(h)},
                    "affineTransform": {"scaleX": float(PIX_M), "shearX": 0.0, "translateX": float(x0),
                                        "shearY": 0.0, "scaleY": -float(PIX_M), "translateY": float(y1)},
                    "crsCode": AREA_CRS}}
    arr = ee.data.computePixels(req)
    return np.stack([arr[b] for b in bands])

def fetch_tile(img, bands, x0, y1, w, h):
    for k in range(MAX_TRIES):
        try:
            return _fetch(img, bands, x0, y1, w, h)
        except Exception as e:
            msg = str(e).lower()
            heavy = any(s in msg for s in ["timed out", "memory", "too large", "payload", "deadline"])
            if heavy and max(w, h) > MIN_TILE:
                hw, hh = (w + 1) // 2, (h + 1) // 2
                out = None
                for dx, dy, pw, ph in [(0, 0, hw, hh), (hw, 0, w - hw, hh), (0, hh, hw, h - hh), (hw, hh, w - hw, h - hh)]:
                    if pw <= 0 or ph <= 0:
                        continue
                    a = fetch_tile(img, bands, x0 + dx * PIX_M, y1 - dy * PIX_M, pw, ph)
                    if out is None:
                        out = np.zeros((a.shape[0], h, w), a.dtype)
                    out[:, dy:dy + ph, dx:dx + pw] = a
                return out
            time.sleep(min(2 ** k * 3, 60))
    raise RuntimeError(f"Bloco ({x0:.0f}, {y1:.0f}, {w}x{h}) falhou {MAX_TRIES} vezes.")

def write_stack(name, img, bands, dtype, ti_id):
    dest = RASTER_DIR / f"{name}.tif"
    if dest.exists():
        return "ja existe"
    _, transform, _ = ti_frame(ti_id)
    x0, y1 = transform[2], transform[5]
    reg = tis.set_index("ti_id").loc[ti_id].geometry.bounds
    W = int(round((float(np.ceil((reg[2] + RASTER_BUFFER_M) / PIX_M) * PIX_M) - x0) / PIX_M))
    H = int(round((y1 - float(np.floor((reg[1] - RASTER_BUFFER_M) / PIX_M) * PIX_M)) / PIX_M))
    out = np.zeros((len(bands), H, W), dtype)
    jobs = [(c, r, min(TILE_PX, W - c), min(TILE_PX, H - r))
            for r in range(0, H, TILE_PX) for c in range(0, W, TILE_PX)]
    with cf.ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futs = {ex.submit(fetch_tile, img, bands, x0 + c * PIX_M, y1 - r * PIX_M, w, h): (c, r, w, h)
                for c, r, w, h in jobs}
        for f in cf.as_completed(futs):
            c, r, w, h = futs[f]
            out[:, r:r + h, c:c + w] = f.result().astype(dtype)
    tmp = Path("/content") / f"{name}.tif"
    prof = dict(driver="GTiff", height=H, width=W, count=len(bands), dtype=np.dtype(dtype).name,
                crs=AREA_CRS, transform=Affine(PIX_M, 0, x0, 0, -PIX_M, y1),
                compress="deflate", tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(out)
    shutil.copy(tmp, dest)
    tmp.unlink()
    return f"{W}x{H} px, {len(jobs)} bloco(s)"

def run_rasters():
    todo = []
    for t in ti_ids:
        todo.append((raster_name(t), lambda: static_image(), STATIC_BANDS, np.int16, t))
        for y in SCAR_YEARS:
            todo.append((raster_name(t, y), (lambda y=y, t=t: year_image(y, ti_frame(t)[0])),
                         YEAR_BANDS, np.int8, t))
    falta = [j for j in todo if not (RASTER_DIR / f"{j[0]}.tif").exists()]
    console.print(f"  Ja prontos: {len(todo) - len(falta)} | A baixar: {len(falta)}")
    erros = []
    for name, make, bands, dtype, t in tqdm(falta, desc="Rasters"):
        t0 = time.time()
        try:
            info = write_stack(name, make(), bands, dtype, t)
            console.print(f"  [green]OK {name}[/green] [dim]{info}, {time.time() - t0:.0f} s[/dim]")
        except Exception as e:
            erros.append(name)
            console.print(f"  [red]X {name}: {str(e)[:200]}[/red]")
    return erros

missing_rasters = run_rasters()
ee.Initialize(project=EE_PROJECT)          # volta ao endereco normal

# ============================================================
# 4. CONFERENCIA
# ============================================================

if not missing_rasters:
    t0, y0 = ti_ids[0], YEARS[-1]
    st, yr = read_raster(t0), read_raster(t0, y0)
    inside = st["ti"] == t0
    obs = {m: float((yr[f"cnt{m:02d}"][inside & (yr["month"] > 0)] > 0).mean()) for m in LS_MONTHS}
    console.print(f"[cyan]TI {t0}, {y0}:[/cyan] queimado {float((yr['month'][inside] > 0).mean()):.1%} | "
                  f"nativa {float((yr['cover'][inside] == 1).mean()):.1%} | barreira {float(st['barrier'][inside].mean()):.1%}")
    console.print("[cyan]Areas queimadas com observacao Landsat limpa, por mes:[/cyan] "
                  + " | ".join(f"{m:02d}: {v:.0%}" for m, v in obs.items()))
    console.print("[bold green]OK BLOCO 03 completo.[/bold green]")
else:
    console.print(f"[red]{len(missing_rasters)} raster(s) com erro - rode o bloco 03 de novo: {missing_rasters[:5]}[/red]")
