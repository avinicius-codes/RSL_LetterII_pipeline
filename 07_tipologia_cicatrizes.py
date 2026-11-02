# ======================================================================
# BLOCO 07 - Tipologia DESCRITIVA das cicatrizes do inicio da seca (focos MODIS 1 km)
# Depende dos blocos 00, 01 (cicatrizes), 02 (amostra), 04 (ERA5), 05 (MODIS) e 06.
# ======================================================================

check_version()

# ============================================================
# BLOCK 6 - Descriptive typology of early-season burns
#
# MUDANCA (2026-10-17): focos MODIS C6.1 (MOD14A1 + MYD14A1, FireMask >= 8),
#   como no artigo 1. Cada foco vai para a cicatriz mais proxima a ate
#   FOCO_LINK_M = 1000 m (pixel de ~1 km). FRP = MaxFRP diario do pixel.
#   Foco noturno = algoritmo noturno do MODIS (QA bit 2 = 0; passagens
#   ~22h30 Terra e ~01h30 Aqua).
#   Checkpoint com sufixo "_md" (o de VIIRS fica intacto).
#
# Descreve as cicatrizes ANTERIORES (inicio da seca). So descricao:
#   - nenhuma queimada e chamada de "manejo" ou "prescrita";
#   - nada e atribuido as BRIFs.
#
# Tipos (recorte principal do artigo 1):
#   "Inicial pequena e fraca"  : inicio + area < mediana do restante da mesma TI
#                                + (sem foco ou FRP max < p25 do restante)
#   "Inicial pequena e intensa": inicio + pequena, mas FRP alto
#   "Inicial grande"           : inicio, area >= mediana
#   "Restante da seca"         : cicatrizes do restante (referencia)
#   "Fragmento < 1 ha"         : abaixo de MIN_SCAR_HA (fora dos limiares e dos focos)
#
# Descricoes: D1 tempo no dia do 1o foco (percentil ERA5); D2 foco noturno
#   (controlando a area); D3 tipologia por TI x FRRI do artigo 1.
#
# Output:
#   02_cache/cicatrizes_tipologia_<tag>_md.gpkg
#   04_stats/B06_tipologia_resumo.csv, D1_tempo.csv, D2_foco_noturno*.csv, D3_tipologia_por_TI.csv
#   05_figures/D1_tempo.png
# ============================================================

import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from scipy.spatial import cKDTree

# ============================================================
# 1. PARAMETERS
# ============================================================

FOCOS_NAME   = globals().get("FOCOS_NAME", f"modis_focos_v1_{TAG_YEARS}")
TAG_SEG      = globals().get("TAG_SEG", f"{TAG_YEARS}_md")
FOCO_LINK_M  = 1000      # foco -> cicatriz mais proxima ate 1 km (pixel MODIS)
MIN_SCAR_HA  = 1.0
N_BOOT_D1    = 999
SEED         = 42
SEASONS      = load_seasons()
AMOSTRA      = load_sample_ids()

# ============================================================
# 2. LOAD
# ============================================================

if "scars_raw" not in globals():
    scars_raw = read_table(cache_path(SCARS_NAME, "gpkg"))
if "focos_raw" not in globals():
    focos_raw = read_table(cache_path(FOCOS_NAME, "parquet"))
if "era5_daily" not in globals():
    era5_daily = read_table(cache_path(f"era5_diario_v2_{TAG_YEARS}", "parquet"))

scars = scars_raw[scars_raw["year"].isin(YEARS) & scars_raw["ti_id"].isin(AMOSTRA)].to_crs(AREA_CRS).copy()
scars["area_ha"] = scars.geometry.area / 1e4
scars["scar_id"] = np.arange(len(scars))

focos = focos_raw.copy()
focos["confidence"] = focos["confidence"].astype(str).str.lower().str[0]
focos = focos[focos["confidence"] != "l"].copy()                 # FireMask >= 8
focos["acq_date"] = pd.to_datetime(focos["acq_date"])
focos["det_id"] = np.arange(len(focos))
focos = gpd.GeoDataFrame(focos.drop(columns=["ti_id"], errors="ignore"),
                         geometry=gpd.points_from_xy(focos["longitude"], focos["latitude"]),
                         crs="EPSG:4326").to_crs(AREA_CRS)
era5 = era5_daily.copy()
era5["date"] = pd.to_datetime(era5["date"])
console.print(f"[cyan]{len(scars):,} cicatrizes ({len(AMOSTRA)} TIs da amostra) | {len(focos):,} focos MODIS[/cyan]")

# ============================================================
# 3. FOCOS MODIS -> CICATRIZES
# ============================================================

def attach_focos(scars, focos):
    """Cada foco vai para a cicatriz mais proxima (ate 1 km) do mesmo ano e do
    mesmo mes ou do mes seguinte (o MapBiomas data a cicatriz pela imagem)."""
    focos = focos.copy()
    focos["y"] = focos["acq_date"].dt.year
    focos["m"] = focos["acq_date"].dt.month
    matches = []
    for (yr, mo), s in scars.groupby(["year", "month"]):
        cand = focos[(focos["y"] == yr) & (focos["m"].isin([mo, mo - 1]))]
        if cand.empty:
            continue
        matches.append(gpd.sjoin_nearest(cand, s[["scar_id", "month", "geometry"]],
                                         max_distance=FOCO_LINK_M, distance_col="dist"))
    if not matches:
        m = pd.DataFrame(columns=["det_id", "scar_id", "daynight", "frp", "acq_date"])
    else:
        m = pd.concat(matches, ignore_index=True)
        m["same_month"] = (m["m"] == m["month"]).astype(int)
        m = (m.sort_values(["det_id", "same_month", "dist"], ascending=[True, False, True])
               .drop_duplicates("det_id"))
    agg = m.groupby("scar_id").agg(
        n_day=("daynight", lambda s: int((s == "D").sum())),
        n_night=("daynight", lambda s: int((s == "N").sum())),
        frp_max=("frp", "max"),
        first_date=("acq_date", "min"))
    out = scars.merge(agg, on="scar_id", how="left")
    out[["n_day", "n_night"]] = out[["n_day", "n_night"]].fillna(0).astype(int)
    out["n_det"] = out["n_day"] + out["n_night"]
    return out

FRAG = f"Fragmento < {MIN_SCAR_HA:g} ha"
_big = scars["area_ha"] >= MIN_SCAR_HA
s = gpd.GeoDataFrame(
    pd.concat([attach_focos(scars[_big], focos),
               scars[~_big].assign(n_day=0, n_night=0, n_det=0)], ignore_index=True),
    geometry="geometry", crs=AREA_CRS)
console.print(f"[cyan]Cicatrizes >= {MIN_SCAR_HA:g} ha:[/cyan] {_big.sum():,} "
              f"({scars.loc[_big, 'area_ha'].sum() / scars['area_ha'].sum():.1%} da area) | "
              f"[cyan]fragmentos:[/cyan] {(~_big).sum():,}")

# ============================================================
# 4. TIPOLOGIA
# ============================================================

def typology(s, scheme=SEASON_MAIN):
    s = s.copy()
    ini = s.apply(lambda r: r["month"] in SEASONS[scheme][int(r["ti_id"])][0], axis=1)
    res = s.apply(lambda r: r["month"] in SEASONS[scheme][int(r["ti_id"])][1], axis=1)
    s["periodo"] = np.select([ini, res], ["inicio", "restante"], "outro")
    big = s["area_ha"] >= MIN_SCAR_HA
    rest = s[(s["periodo"] == "restante") & big]
    med = rest.groupby("ti_id")["area_ha"].median()
    frp_p25 = rest.loc[rest["n_det"] > 0, "frp_max"].quantile(0.25)
    pequena = s["area_ha"] < s["ti_id"].map(med).fillna(rest["area_ha"].median())
    fraca = (s["n_det"] == 0) | (s["frp_max"] < frp_p25)
    s["tipo"] = np.select(
        [~big, ini & pequena & fraca, ini & pequena, ini, s["periodo"].eq("restante")],
        [FRAG] + CAT_ORDER, "Fora da seca (nov-abr)")
    lim = {"esquema": scheme, "sensor_focos": "MODIS MOD14A1+MYD14A1 (FireMask >= 8)",
           "area_minima_ha": MIN_SCAR_HA, "mediana_restante_por_TI_ha": med.round(1).to_dict(),
           "frp_p25_restante_MW": round(float(frp_p25), 2)}
    return s, lim

s, lim = typology(s)
save_json(lim, DIRS["logs"] / "B06_limiares_tipologia_md.json")
tipo_tab = s.groupby("tipo").agg(n=("scar_id", "size"), area_ha=("area_ha", "sum"),
                                 area_mediana_ha=("area_ha", "median"),
                                 com_foco=("n_det", lambda n: (n > 0).mean()))
tipo_tab.to_csv(stats_path("B06_tipologia_resumo"))
display(tipo_tab.round(2))

# ============================================================
# 5. D1 - TEMPO NO DIA DA QUEIMA (descricao)
# ============================================================

def weather_percentiles(s, era5):
    d = s[s["first_date"].notna() & s["tipo"].isin(CAT_ORDER)].copy()
    if d.empty:
        return d
    pts = era5.drop_duplicates("point_id")[["point_id", "lon", "lat"]].reset_index(drop=True)
    tree = cKDTree(pts[["lon", "lat"]].to_numpy())
    cent = d.geometry.centroid.to_crs("EPSG:4326")
    _, idx = tree.query(np.c_[cent.x, cent.y])
    d["point_id"] = pts.loc[idx, "point_id"].to_numpy()
    d["date"] = pd.to_datetime(d["first_date"]).dt.normalize()
    e = era5.copy()
    e["mo"] = e["date"].dt.month
    for var in ["vpd_max", "rh_min", "wind"]:
        e[f"P_{var}"] = e.groupby(["point_id", "mo"])[var].rank(method="max", pct=True)
    return d.merge(e[["point_id", "date", "P_vpd_max", "P_rh_min", "P_wind"]], on=["point_id", "date"], how="left")

d1 = weather_percentiles(s, era5)
rng = np.random.default_rng(SEED)
rows = []
for cat in CAT_ORDER:
    x = d1[d1["tipo"] == cat]
    if len(x) < 5:
        continue
    for var in ["P_vpd_max", "P_rh_min", "P_wind"]:
        v = x[var].dropna()
        tis_x = x["ti_id"].unique()
        boots = [x.set_index("ti_id").loc[rng.choice(tis_x, len(tis_x))][var].mean() for _ in range(N_BOOT_D1)]
        rows.append({"tipo": cat, "variavel": var, "n": len(v), "media_percentil": v.mean(),
                     "ic95_inf": np.nanpercentile(boots, 2.5), "ic95_sup": np.nanpercentile(boots, 97.5)})
D1 = pd.DataFrame(rows)
D1.to_csv(stats_path("D1_tempo"), index=False)
console.print("\n[bold]D1 - percentil do VPD no dia do 1o foco MODIS (0,5 = dia tipico do mes)[/bold]")
display(D1[D1["variavel"] == "P_vpd_max"].round(3))

fig, ax = plt.subplots(figsize=(4.8, 4.0))
ax.plot([0, 1], [0, 1], color="black", lw=0.8, ls="--", label="Dia tipico")
for cat in CAT_ORDER:
    v = np.sort(d1.loc[d1["tipo"] == cat, "P_vpd_max"].dropna().to_numpy())
    if len(v) >= 5:
        ax.step(v, np.arange(1, len(v) + 1) / len(v), where="post", color=CAT_COLORS[cat], lw=1.6,
                label=f"{cat} (n={len(v)})")
ax.set_xlabel("Percentil do VPD no dia do 1o foco MODIS\n(0 = dia mais umido do mes; 1 = mais seco)")
ax.set_ylabel("Proporcao acumulada")
ax.legend(fontsize=7, frameon=False, loc="lower right")
fig.savefig(fig_path("D1_tempo"))
plt.show()

# ============================================================
# 6. D2 - FOCO NOTURNO (descricao, controlando a area)
# ============================================================

d2 = s[(s["n_det"] > 0) & s["tipo"].isin(CAT_ORDER)].copy()
d2["noturno"] = (d2["n_night"] > 0).astype(int)
d2["log_area"] = np.log(d2["area_ha"])
d2["cat"] = pd.Categorical(d2["tipo"], categories=[c for c in reversed(CAT_ORDER) if c in set(d2["tipo"])])
m2 = smf.glm("noturno ~ C(cat) + log_area", data=d2, family=sm.families.Binomial()).fit(
    cov_type="cluster", cov_kwds={"groups": d2["ti_id"]})
D2 = pd.DataFrame({"razao_chances": np.exp(m2.params), "ic95_inf": np.exp(m2.conf_int()[0]),
                   "ic95_sup": np.exp(m2.conf_int()[1]), "p": m2.pvalues})
D2.to_csv(stats_path("D2_foco_noturno"))
d2_taxa = d2.groupby("tipo")["noturno"].agg(["size", "mean"])
d2_taxa.to_csv(stats_path("D2_foco_noturno_taxa"))
console.print("\n[bold]D2 - chance de foco noturno MODIS (referencia = restante da seca)[/bold]")
display(d2_taxa.round(3))
display(D2.round(3))

# ============================================================
# 7. D3 - TIPOLOGIA POR TI x FRRI DO ARTIGO 1
# ============================================================

ini_area = s[s["periodo"] == "inicio"].groupby(["ti_id", "tipo"])["area_ha"].sum().unstack(fill_value=0)
D3 = ini_area.div(ini_area.sum(axis=1), axis=0).add_prefix("frac_").reset_index().merge(artigo1, on="ti_id", how="left")
D3.to_csv(stats_path("D3_tipologia_por_TI"), index=False)
display(D3.round(3))
ok = D3.dropna(subset=["frri"])
if len(ok) >= 4 and "frac_Inicial pequena e fraca" in ok:
    r, p = stats.spearmanr(ok["frac_Inicial pequena e fraca"], ok["frri"])
    console.print(f"Spearman (fracao 'pequena e fraca' x FRRI): rho = {r:.2f}, p = {p:.3f}, n = {len(ok)} "
                  "(descritivo; poucas TIs)")
    save_json({"rho": float(r), "p": float(p), "n": int(len(ok))}, DIRS["logs"] / "D3_spearman_frri.json")

# ============================================================
# 8. SAVE
# ============================================================

out = s.drop(columns=["first_date"]).assign(first_date=s["first_date"].astype(str))
write_table(out, cache_path(f"cicatrizes_tipologia_{TAG_SEG}", "gpkg"))
console.print("[bold green]OK BLOCO 07 completo.[/bold green]")
