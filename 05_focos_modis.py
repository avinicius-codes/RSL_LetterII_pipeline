# ======================================================================
# BLOCO 05 - Focos de calor MODIS C6.1 (Terra MOD14A1 + Aqua MYD14A1, 1 km) por pixel e dia
# Depende do bloco 00 (e do 01 para o mapa de conferencia). Mesma colecao do artigo 1.
# ======================================================================

check_version()

# ============================================================
# BLOCK 4 - MODIS C6.1 daily active fires (MOD14A1 + MYD14A1), Earth Engine
#
# Por que MODIS: continuidade com o artigo 1 (mesma colecao, mesmo limiar
# principal FireMask >= 8) e serie homogenea em todo o pos-BRIF (2014-2024).
#
# O que sai: UM PONTO POR PIXEL MODIS COM FOGO POR DIA E SATELITE, no centro
# do pixel da grade sinusoidal (~926 m). Colunas no MESMO formato que o bloco 07
# e o bloco 10 ja usavam (latitude, longitude, acq_date, frp, daynight,
# confidence), mais satellite e firemask:
#   confidence : FireMask 7 = "l" (baixa), 8 = "n" (nominal), 9 = "h" (alta)
#                -> bloco 07/bloco 10 descartam "l" = serie principal >= 8 do artigo 1
#   frp        : MaxFRP x 0,1 (MW) - FRP maximo do pixel no dia
#   daynight   : QA bit 2 (1 = algoritmo diurno "D", 0 = noturno "N")
#   acq_time   : nao existe no produto diario (fica vazio)
#
# Consequencias da resolucao de 1 km (declarar nos Metodos):
#   - chegada  : foco a ate FOCO_ARR_M = 1000 m da borda, do lado de fora
#   - entrada  : centro do pixel a >= FOCO_IN_M = 1000 m DENTRO da cicatriz
#                (o pixel inteiro fica dentro da cicatriz) -> so cicatrizes
#                largas (> ~2 km) podem ter entrada vista pelo MODIS; nas
#                demais a continuidade vem so do Landsat
#   - data     : a data do foco e o dia da chegada usado no tempo (ERA5)
#
# Output:
#   07_exports/modis_focos/modis_focos_<ano>_<tag>.csv  (1 por ano, do EE)
#   02_cache/modis_focos_v1_<anos>_<tag>.parquet        (lido pelo bloco 07 e bloco 10)
#   04_stats/B04_modis_focos_ano_mes.csv
#   05_figures/B04_modis_focos_mapa.{tif,png,pdf}       (600 dpi)
# ============================================================

import json as _json

# ============================================================
# 1. PARAMETERS
# ============================================================

MODIS_COLS   = {"Terra": "MODIS/061/MOD14A1", "Aqua": "MODIS/061/MYD14A1"}
FOCO_MONTHS  = (3, 4, 5, 6, 7, 8, 9, 10, 11)   # mar-nov: cobre o recorte do artigo 1 e o local (bloco 06)
FOCO_MIN_FM  = 7                               # exporta >= 7; a analise usa >= 8 (descarta "l")
FOCO_BUFFER_M = 2000                           # TIs + 2 km (mesmo recorte dos rasters)
FOCO_ARR_M   = 1000                            # usado no bloco 10 (chegada)
FOCO_IN_M    = 1000                            # usado no bloco 10 (entrada) e no bloco 07 (ligacao foco-cicatriz)
FOCO_DIR     = DIRS["exports"] / "modis_focos"
FOCO_DIR.mkdir(parents=True, exist_ok=True)
FOCOS_NAME   = f"modis_focos_v1_{TAG_YEARS}"   # checkpoint lido pelo bloco 07 e bloco 10
TAG_SEG      = f"{TAG_YEARS}_md"               # sufixo dos checkpoints que usam focos (bloco 07, bloco 10...)
FIG_DPI_RSL  = 600

# ============================================================
# 2. REGIAO: as 14 TIs + 2 km (barato; o bloco 07/bloco 10 filtram a amostra)
# ============================================================

region = tis_fc.map(lambda f: ee.Feature(f).buffer(FOCO_BUFFER_M, 100)).union(100).geometry()

def modis_points_year(y: int) -> ee.FeatureCollection:
    fcs = []
    for sat, cid in MODIS_COLS.items():
        col = (ee.ImageCollection(cid)
               .filterDate(f"{y}-01-01", f"{y + 1}-01-01")
               .filter(ee.Filter.calendarRange(min(FOCO_MONTHS), max(FOCO_MONTHS), "month"))
               .filterBounds(region))

        def to_points(img, sat=sat):
            img = ee.Image(img)
            fm = img.select("FireMask")
            day = img.select("QA").bitwiseAnd(4).rightShift(2)            # bit 2: 1 = dia
            stack = (fm.rename("firemask")
                     .addBands(img.select("MaxFRP").multiply(0.1).rename("frp"))
                     .addBands(day.rename("day"))
                     .updateMask(fm.gte(FOCO_MIN_FM)))
            pts = stack.sample(region=region, projection=fm.projection(), geometries=True,
                               dropNulls=True, tileScale=4)            # centro do pixel nativo
            d = img.date().format("YYYY-MM-dd")
            return pts.map(lambda f: f.set({"acq_date": d, "satellite": sat}))
        fcs.append(col.map(to_points).flatten())
    return ee.FeatureCollection(fcs).flatten()

def foco_name(y):
    return f"modis_focos_{y}_{RUN_TAG}"

def make_task(y):
    return ee.batch.Export.table.toDrive(
        collection=modis_points_year(y), description=foco_name(y), folder=EE_EXPORT_FOLDER,
        fileNamePrefix=foco_name(y), fileFormat="CSV",
        selectors=["firemask", "frp", "day", "acq_date", "satellite", ".geo"])

# ============================================================
# 3. EXPORTAR (1 tarefa por ano) -> MONITORAR -> BAIXAR (funcoes do bloco 00)
# ============================================================

def run_modis_pipeline() -> pd.DataFrame:
    specs = {foco_name(y): (lambda y=y: make_task(y)) for y in YEARS}
    paths = run_ee_exports(specs, "csv", FOCO_DIR)
    if len(paths) < len(YEARS):
        raise RuntimeError("Faltam anos de focos MODIS - rode o bloco 05 de novo quando as tarefas terminarem.")
    parts = []
    for p in paths:
        d = pd.read_csv(p)
        if d.empty:
            continue
        xy = d[".geo"].map(lambda g: _json.loads(g)["coordinates"])
        d["longitude"] = xy.str[0]; d["latitude"] = xy.str[1]
        parts.append(d.drop(columns=".geo"))
    v = pd.concat(parts, ignore_index=True)
    v["acq_date"] = pd.to_datetime(v["acq_date"])
    v = v[v["acq_date"].dt.year.isin(YEARS) & v["acq_date"].dt.month.isin(FOCO_MONTHS)]
    v["firemask"] = v["firemask"].astype(int)
    v["confidence"] = v["firemask"].map({7: "l", 8: "n", 9: "h"})
    v["daynight"] = np.where(v["day"].astype(int) == 1, "D", "N")
    v["acq_time"] = np.nan
    v["sensor"] = "MODIS"
    v = v.drop_duplicates(["latitude", "longitude", "acq_date", "satellite"])

    tis_buf = tis.to_crs(AREA_CRS).copy()
    tis_buf["geometry"] = tis_buf.buffer(FOCO_BUFFER_M)
    g = gpd.GeoDataFrame(v, geometry=gpd.points_from_xy(v["longitude"], v["latitude"]), crs="EPSG:4326")
    g = gpd.sjoin(g, tis_buf.to_crs("EPSG:4326")[["ti_id", "geometry"]], predicate="within", how="inner")
    g = g.drop(columns=["index_right", "geometry", "day"])
    # TIs vizinhas com buffers sobrepostos: o foco fica na TI cujo limite esta mais perto
    g = g.drop_duplicates(["latitude", "longitude", "acq_date", "satellite"])
    cols = ["ti_id", "latitude", "longitude", "acq_date", "acq_time", "satellite", "sensor",
            "firemask", "confidence", "frp", "daynight"]
    return pd.DataFrame(g[cols]).reset_index(drop=True)

# ============================================================
# 4. RUN
# ============================================================

focos_raw = checkpoint_load_or_run(FOCOS_NAME, run_modis_pipeline, ext="parquet")
focos_raw["acq_date"] = pd.to_datetime(focos_raw["acq_date"])

# ============================================================
# 5. CONFERENCIAS
# ============================================================

chk = (focos_raw[focos_raw["confidence"] != "l"]
       .assign(ano=lambda d: d["acq_date"].dt.year, mes=lambda d: d["acq_date"].dt.month)
       .pivot_table(index="ano", columns="mes", values="frp", aggfunc="size", fill_value=0))
chk.to_csv(stats_path("B04_modis_focos_ano_mes"))
display(chk)
fm = focos_raw["firemask"].value_counts(normalize=True).sort_index()
console.print(f"[cyan]FireMask 7/8/9:[/cyan] " + " | ".join(f"{k}: {v:.1%}" for k, v in fm.items())
              + f" | [cyan]noturnos (>= 8):[/cyan] "
              f"{(focos_raw.loc[focos_raw['confidence'] != 'l', 'daynight'] == 'N').mean():.1%}"
              + f" | [cyan]Terra/Aqua:[/cyan] {focos_raw['satellite'].value_counts().to_dict()}")

# Mapa de conferencia (espacial): uma TI media, um ano - focos sobre as cicatrizes do MapBiomas
try:
    if "scars_raw" not in globals():
        scars_raw = read_table(cache_path(SCARS_NAME, "gpkg"))
    t0 = int(tis.sort_values("area_ha").iloc[len(tis) // 2]["ti_id"])
    yr_show = int(focos_raw.loc[focos_raw["ti_id"] == t0, "acq_date"].dt.year.mode().iat[0])
    s = scars_raw[(scars_raw["ti_id"] == t0) & (scars_raw["year"] == yr_show)]
    f = focos_raw[(focos_raw["ti_id"] == t0) & (focos_raw["acq_date"].dt.year == yr_show) &
                  (focos_raw["confidence"] != "l")]
    fg = gpd.GeoDataFrame(f, geometry=gpd.points_from_xy(f["longitude"], f["latitude"]),
                          crs="EPSG:4326").to_crs(AREA_CRS)
    fig, ax = plt.subplots(figsize=(14 / 2.54, 14 / 2.54))
    tis[tis["ti_id"] == t0].boundary.plot(ax=ax, color="black", lw=0.6)
    s[s["month"].isin(EARLY)].plot(ax=ax, color="#1f5fc8", lw=0)
    s[s["month"].isin(LATE)].plot(ax=ax, color="#f28322", lw=0)
    # quadrado de ~1 km = pegada nominal do pixel MODIS
    fg.assign(geometry=fg.buffer(463, cap_style=3)).boundary.plot(
        ax=ax, color=np.where(fg["acq_date"].dt.month.isin(EARLY), "#0b2a66", "#7a1f3d"), lw=0.4)
    ax.set_title(f"{tis.set_index('ti_id').loc[t0, 'ti_name']} {yr_show}: MapBiomas mai-jul (azul) e "
                 f"ago-out (laranja); quadrados = pixels MODIS com fogo (>= 8)", fontsize=8)
    ax.set_axis_off()
    for ext, kw in [("tif", {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", {}), ("pdf", {})]:
        fig.savefig(fig_path("B04_modis_focos_mapa", ext), dpi=FIG_DPI_RSL, facecolor="white", **kw)
    plt.show()
except Exception as e:
    console.print(f"[dim]mapa de conferencia pulado: {str(e)[:100]}[/dim]")

console.print(f"[bold green]OK BLOCO 05 completo: {len(focos_raw):,} pixels-dia com fogo "
              f"({(focos_raw['confidence'] != 'l').sum():,} com FireMask >= 8).[/bold green]")
