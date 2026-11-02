# ======================================================================
# BLOCO 04 - ERA5-Land diario (abr-nov) nas TIs com BRIF
# Depende do bloco 00.
# ======================================================================
#
# Usos: tempo no dia em que o fogo chegou a cada borda (bloco 10); VPD e chuva
# da estacao por celula (bloco 08); tempo no dia das queimadas iniciais (07).
#   vpd_max   : deficit de pressao de vapor no horario mais quente (kPa), da
#               temperatura maxima e do ponto de orvalho medio
#   rh_min    : umidade relativa minima aproximada (%)
#   wind      : vento a 10 m (m/s), das componentes u/v medias
#   precip_mm : chuva do dia (mm)
# Pontos = centros dos pixels do ERA5-Land (~9 km) sobre as TIs + 10 km.
#
# Output: 07_exports/era5/l9_<tag>_era5v2_AAAA.csv | 02_cache/era5_diario_v2_<anos>.parquet
# ======================================================================

check_version()

ERA5_DAILY    = "ECMWF/ERA5_LAND/DAILY_AGGR"
ERA5_BUFFER_M = 10000
TASK_ERA5     = f"l9_{RUN_TAG}_era5v2"
ERA5_DIR      = DIRS["exports"] / "era5"

era5_ic   = ee.ImageCollection(ERA5_DAILY)
era5_proj = era5_ic.first().projection()
era5_area = tis_fc.map(lambda f: ee.Feature(f).buffer(ERA5_BUFFER_M, 500)).geometry()

def _pt_props(f):
    f = ee.Feature(f)
    lon = ee.Number(f.get("longitude"))
    lat = ee.Number(f.get("latitude"))
    return f.set({"lon": lon, "lat": lat,
                  "point_id": lon.format("%.3f").cat("_").cat(lat.format("%.3f"))})

era5_points = (ee.Image.pixelLonLat().reproject(era5_proj)
               .sample(region=era5_area, projection=era5_proj, geometries=True)
               .map(_pt_props))
console.print(f"[cyan]Pontos ERA5 dentro da area:[/cyan] {era5_points.size().getInfo()}")

def _sat_vp(t_c):
    return t_c.expression("0.6108*exp(17.27*T/(T+237.3))", {"T": t_c})

def daily_vars(img):
    img = ee.Image(img)
    t  = img.select("temperature_2m_max").subtract(273.15)
    td = img.select("dewpoint_temperature_2m").subtract(273.15)
    es, ea = _sat_vp(t), _sat_vp(td)
    u = img.select("u_component_of_wind_10m")
    v = img.select("v_component_of_wind_10m")
    return (es.subtract(ea).rename("vpd_max")
              .addBands(ea.divide(es).multiply(100).rename("rh_min"))
              .addBands(u.hypot(v).rename("wind"))
              .addBands(img.select("total_precipitation_sum").multiply(1000).rename("precip_mm"))
              .set("date", img.date().format("YYYY-MM-dd")))

def era5_task(y):
    def _make():
        col = era5_ic.filterDate(f"{y}-04-01", f"{y}-12-01").map(daily_vars)

        def _per_day(img):
            img = ee.Image(img)
            return (img.reduceRegions(collection=era5_points, reducer=ee.Reducer.first(), scale=11132)
                       .map(lambda f: ee.Feature(f).set("date", img.get("date")).setGeometry(None)))
        table = col.map(_per_day).flatten()
        return ee.batch.Export.table.toDrive(
            collection=table, description=f"{TASK_ERA5}_{y}", folder=EE_EXPORT_FOLDER,
            fileNamePrefix=f"{TASK_ERA5}_{y}", fileFormat="CSV",
            selectors=["point_id", "lon", "lat", "date", "vpd_max", "rh_min", "wind", "precip_mm"])
    return _make

def run_era5_pipeline() -> pd.DataFrame:
    paths = run_ee_exports({f"{TASK_ERA5}_{y}": era5_task(y) for y in YEARS}, "csv", ERA5_DIR)
    if len(paths) < len(YEARS):
        raise RuntimeError("Faltam anos do ERA5 - rode o bloco 04 de novo mais tarde.")
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["vpd_max"])

era5_daily = checkpoint_load_or_run(f"era5_diario_v2_{TAG_YEARS}", run_era5_pipeline, ext="parquet")
era5_daily["date"] = pd.to_datetime(era5_daily["date"])

chk = era5_daily.groupby(era5_daily["date"].dt.month)[["vpd_max", "rh_min", "wind"]].mean().round(2)
chk.index.name = "mes"
display(chk)
if chk["vpd_max"].idxmax() not in (8, 9, 10):
    console.print("[red]WARNING pico de VPD fora de ago-out - confira as bandas do ERA5.[/red]")
console.print(f"[bold green]OK BLOCO 04 completo: {era5_daily['point_id'].nunique()} pontos x "
              f"{era5_daily['date'].nunique()} dias.[/bold green]")
