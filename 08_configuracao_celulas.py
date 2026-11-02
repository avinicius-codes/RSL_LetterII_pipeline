# ======================================================================
# BLOCO 08 - Quantidade x configuracao das cicatrizes iniciais, por celula
# Depende dos blocos 00, 03 (rasters), 04 (ERA5) e 06 (estacoes).
# ======================================================================
#
# Objetivo especifico 2. Para cada celula (principal 4980 m), ano e recorte,
# sobre o COMBUSTIVEL (cobertura vegetada; fora: nao vegetado, mineracao,
# aquicultura e agua):
#   QUANTIDADE   q_inicio (fracao queimada no inicio), q_inicio_viz (8 vizinhas),
#                q_ant1/q_ant2 (t-1, t-2)
#   CONFIGURACAO do combustivel restante no fim do inicio da seca:
#                conf_split  = log(m_eff depois / antes) (Jaeger 2000)
#                conf_lpi    = maior mancha / area queimavel
#                conf_borda  = borda cicatriz-combustivel (m/ha)
#                conf_npatch = manchas de combustivel por km2
#                (a versao independente da quantidade e o SES do bloco 09)
#   DESFECHO     y_resto = fracao queimada no restante; y_cont = maior mancha
#                queimada no restante / area queimavel
#   CONTROLES    nativa, pastagem, agricultura, declividade, barreira, rios,
#                VPD do restante e chuva da seca (ERA5), centroide
# Manchas cortadas na borda da celula contam so pela parte dentro (cutting-out).
#
# Output: 02_cache/celulas_<esquema>_<tamanho>_<comb>_<tag>.parquet
#         04_stats/B07_correlacao_quantidade_configuracao.csv
# ======================================================================

check_version()

from scipy import ndimage
from scipy.spatial import cKDTree
from pyproj import Transformer

MIN_QUEIMAVEL = 0.25
CONN8 = np.ones((3, 3), int)
SEASONS = load_seasons()
AMOSTRA = load_sample_ids()

if "era5_daily" not in globals():
    era5_daily = read_table(cache_path(f"era5_diario_v2_{TAG_YEARS}", "parquet"))
era5_daily["date"] = pd.to_datetime(era5_daily["date"])
era5_m = (era5_daily.assign(year=era5_daily["date"].dt.year, mes=era5_daily["date"].dt.month)
          .groupby(["point_id", "year", "mes"])
          .agg(vpd=("vpd_max", "mean"), chuva=("precip_mm", "sum")).reset_index())
era5_pts = era5_daily.drop_duplicates("point_id")[["point_id", "lon", "lat"]].reset_index(drop=True)
era5_tree = cKDTree(era5_pts[["lon", "lat"]].to_numpy())
era5_m_idx = era5_m.set_index(["point_id", "year", "mes"])
_to_ll = Transformer.from_crs(AREA_CRS, "EPSG:4326", always_xy=True)

def weather_for(xs, ys, year, ini, res):
    lon, lat = _to_ll.transform(np.asarray(xs), np.asarray(ys))
    _, idx = era5_tree.query(np.c_[lon, lat])
    pid = era5_pts.loc[idx, "point_id"].to_numpy()
    vpd, chuva = [], []
    for p in pid:
        try:
            g = era5_m_idx.loc[(p, year)]
            vpd.append(g.loc[g.index.isin(res), "vpd"].mean())
            chuva.append(g.loc[g.index.isin(list(ini) + list(res)), "chuva"].sum())
        except KeyError:
            vpd.append(np.nan); chuva.append(np.nan)
    return np.array(vpd), np.array(chuva), pid

def _edge(scar, fuel):
    nb = np.zeros_like(fuel)
    nb[1:, :] |= fuel[:-1, :]; nb[:-1, :] |= fuel[1:, :]
    nb[:, 1:] |= fuel[:, :-1]; nb[:, :-1] |= fuel[:, 1:]
    return float((scar & nb).sum()) * PIX_M

def cells_ti_year(ti, year, scheme, cell_m, fuel_mode=FUEL_MAIN):
    st = static_of(ti)
    yr, l1, l2 = read_raster(ti, year), read_raster(ti, year - 1), read_raster(ti, year - 2)
    inside = st["ti"] == ti
    queim = inside & fuel_from_cover(yr["cover"], fuel_mode) & (st["barrier"] == 0)
    sm = season_masks(yr["month"], ti, scheme, SEASONS)
    E = sm["inicio"] & queim
    L = sm["resto"] & queim
    fuel0 = queim & ~sm["antes"]
    fuel1 = fuel0 & ~E
    P1 = (l1["month"] > 0) & queim
    P2 = (l2["month"] > 0) & queim
    slope = st["slope10"] / 10.0
    cp = int(round(cell_m / PIX_M))
    H, W = queim.shape
    tr = st["_transform"]
    rows = []
    for i in range(H // cp):
        for j in range(W // cp):
            sl = (slice(i * cp, (i + 1) * cp), slice(j * cp, (j + 1) * cp))
            A = int(queim[sl].sum())
            if A < MIN_QUEIMAVEL * cp * cp:
                continue
            e, l, f0, f1 = E[sl], L[sl], fuel0[sl], fuel1[sl]
            s0, _, _ = _meff(f0)
            s1, mx1, n1 = _meff(f1)
            _, mxL, _ = _meff(l)
            _, _, ne = _meff(e)
            ins = inside[sl]
            rows.append({
                "ti_id": ti, "year": year, "row": i, "col": j,
                "x": tr.c + (j + 0.5) * cp * PIX_M, "y": tr.f - (i + 0.5) * cp * PIX_M,
                "area_queimavel_ha": A * 0.09,
                "q_inicio": e.sum() / A, "q_ant1": P1[sl].sum() / A, "q_ant2": P2[sl].sum() / A,
                "conf_split": np.log(s1 / s0) if (s0 > 0 and s1 > 0) else np.nan,
                "conf_lpi": mx1 / A,
                "conf_borda": _edge(e, f1) / (A * 0.09),
                "conf_npatch": n1 / (A * 0.09 / 100),
                "n_cicatrizes": ne,
                "y_resto": l.sum() / A,
                "y_cont": mxL / A,
                "nativa": float((yr["cover"][sl][ins] == 1).mean()) if ins.any() else np.nan,
                "pastagem": float((yr["cover"][sl][ins] == 2).mean()) if ins.any() else np.nan,
                "agricultura": float((yr["cover"][sl][ins] == 3).mean()) if ins.any() else np.nan,
                "declividade": float(slope[sl][ins].mean()) if ins.any() else np.nan,
                "barreira": float(st["barrier"][sl][ins].mean()) if ins.any() else np.nan,
                "rios": float(st["river"][sl][ins].mean()) if ins.any() else np.nan,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    ini, res = SEASONS[scheme][int(ti)]
    df["vpd_resto"], df["chuva_seca"], df["era5_point"] = weather_for(df["x"], df["y"], year, ini, res)
    key = df.set_index(["row", "col"])["q_inicio"]
    viz = []
    for r, c in zip(df["row"], df["col"]):
        vals = [key.get((r + dr, c + dc)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
        vals = [v for v in vals if v is not None and not np.isnan(v)]
        viz.append(np.mean(vals) if vals else np.nan)
    df["q_inicio_viz"] = viz
    return df

CONF_VARS = ["conf_split", "conf_lpi", "conf_borda", "conf_npatch"]

def build_cells(scheme=SEASON_MAIN, cell_m=CELL_M, force=False, fuel_mode=FUEL_MAIN) -> pd.DataFrame:
    p = cache_path(f"celulas_{scheme}_{cell_m}_{FUEL_TAG[fuel_mode]}_{TAG_YEARS}", "parquet")
    if p.exists() and not (force or FORCE_REPROCESS):
        df = pd.read_parquet(p)
        if df.get("res_metodo", pd.Series([""])).iloc[0] != RES_METODO:
            df = residualize_conf(df, CONF_VARS)
            df.to_parquet(p, index=False)
        return df
    parts = []
    for ti in tqdm(AMOSTRA, desc=f"Celulas {scheme} {cell_m} m"):
        for y in YEARS:
            parts.append(cells_ti_year(ti, y, scheme, cell_m, fuel_mode))
    df = pd.concat([d for d in parts if len(d)], ignore_index=True)
    df["cell_id"] = df["ti_id"].astype(str) + "_" + df["row"].astype(str) + "_" + df["col"].astype(str)
    df = residualize_conf(df, CONF_VARS)
    df["esquema"], df["cell_m"], df["combustivel"] = scheme, cell_m, fuel_mode
    df.to_parquet(p, index=False)
    return df

cells_by_fuel = {}
for fm in FUEL_RUNS:
    cells_by_fuel[fm] = build_cells(fuel_mode=fm)
    c_ = cells_by_fuel[fm]
    console.print(f"[green]OK [{fm}] {c_['cell_id'].nunique():,} celulas x {c_['year'].nunique()} anos = {len(c_):,} linhas[/green]")
cells = cells_by_fuel[FUEL_MAIN]

cols_q = ["q_inicio", "q_ant1"] + CONF_VARS + [f"{v}_res" for v in CONF_VARS]
corr = pd.concat([c_[cols_q].corr(method="spearman").loc[["q_inicio"], CONF_VARS + [f"{v}_res" for v in CONF_VARS]]
                  .assign(combustivel=fm) for fm, c_ in cells_by_fuel.items()]).set_index("combustivel")
corr.to_csv(stats_path("B07_correlacao_quantidade_configuracao"))
console.print("[bold]Spearman: quantidade (q_inicio) x configuracao bruta e residual[/bold]")
display(corr.round(2))
console.print("[bold green]OK BLOCO 08 completo.[/bold green]")
