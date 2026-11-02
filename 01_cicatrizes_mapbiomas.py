# ======================================================================
# BLOCO 01 - Cicatrizes do MapBiomas Fogo (Colecao 4, mensal, 30 m)
# Depende do bloco 00.
# ======================================================================
#
# Cicatriz = pixels queimados no MESMO mes e ano, contiguos (vizinhanca de 8),
# dentro de cada TI. O valor do pixel no MapBiomas Fogo Col. 4 mensal e o
# proprio MES da queima (1-12), banda "burned_monthly_{ano}".
#
#   1) Earth Engine: exporta o raster do mes da queima - uma imagem por TI,
#      uma banda por ano (2012-2024) + mascara da TI. EPSG:5880, 30 m, mesma
#      grade dos rasters do bloco 03.
#   2) Colab: transforma em poligonos (mesmo mes, vizinhanca de 8), com bordas
#      exatamente nos pixels de 30 m (sem simplificar).
#
# Output:
#   07_exports/fogo_mes/l9_<tag>_firemonth_ti<id>.tif   (um por TI)
#   02_cache/cicatrizes_<anos>_<tag>.gpkg  (campos: ti_id, year, month, area_ha)
# ======================================================================

check_version()

import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

FIRE_DIR    = DIRS["exports"] / "fogo_mes"
TASK_PREFIX = f"l9_{RUN_TAG}_firemonth"

def fire_name(ti_id):
    return f"{TASK_PREFIX}_ti{int(ti_id)}"

# ============================================================
# 1. EXPORTACAO DO RASTER (uma imagem por TI, uma banda por ano)
# ============================================================

def fire_image(ti_id):
    fire = ee.Image(FIRE_ASSET)
    bands = [ti_img.eq(int(ti_id)).rename("ti")]
    bands += [fire.select(FIRE_BAND(y)).unmask(0).rename(f"m{y}") for y in SCAR_YEARS]
    return ee.Image.cat(bands).toUint8()

def run_fire_rasters():
    specs = {}
    for t in tis["ti_id"].astype(int):
        region, transform, _ = ti_frame(t)
        specs[fire_name(t)] = (lambda t=t: fire_image(t), region, transform)
    return run_image_exports(specs, FIRE_DIR)

# ============================================================
# 2. POLIGONOS (mesmo mes, vizinhanca de 8, sem simplificar)
# ============================================================

def vectorize_ti(ti_id):
    with rasterio.open(FIRE_DIR / f"{fire_name(ti_id)}.tif") as src:
        arr = src.read()
        tr = src.transform
    inside = arr[0] == 1
    rows = []
    for k, y in enumerate(SCAR_YEARS, start=1):
        month = arr[k].astype(np.int16)
        mask = inside & (month > 0)
        if not mask.any():
            continue
        for geom, val in shapes(month, mask=mask, connectivity=8, transform=tr):
            rows.append({"ti_id": int(ti_id), "year": int(y), "month": int(val), "geometry": shape(geom)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=AREA_CRS)

def run_scars_pipeline() -> gpd.GeoDataFrame:
    missing = run_fire_rasters()
    if missing:
        raise RuntimeError(f"Faltam rasters: {missing} - rode o bloco 01 de novo quando as tarefas terminarem.")
    parts = []
    for t in tqdm(tis["ti_id"].astype(int), desc="Vetorizando TIs"):
        g = vectorize_ti(t)
        console.print(f"  [dim]TI {t}: {len(g):,} cicatrizes[/dim]")
        parts.append(g)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=AREA_CRS)
    g["area_ha"] = g.geometry.area / 1e4
    return g[["ti_id", "year", "month", "area_ha", "geometry"]]

scars_raw = checkpoint_load_or_run(SCARS_NAME, run_scars_pipeline, ext="gpkg")

# ============================================================
# 3. CONFERENCIA
# ============================================================

chk = (scars_raw.assign(periodo=np.select([scars_raw["month"].isin(EARLY), scars_raw["month"].isin(LATE)],
                                          ["mai-jul", "ago-out"], "outro"))
                .groupby(["year", "periodo"])["area_ha"].sum().unstack(fill_value=0).round(0))
display(chk)
chk.to_csv(stats_path("cicatrizes_area_por_ano_periodo"))

console.print(f"[bold green]OK BLOCO 01 completo: {len(scars_raw):,} cicatrizes.[/bold green]")
