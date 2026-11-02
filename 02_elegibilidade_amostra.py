# ======================================================================
# BLOCO 02 - Elegibilidade das 14 TIs com BRIF -> amostra final da letter
# Depende do bloco 00 e dos rasters do bloco 01 (07_exports/fogo_mes).
# ======================================================================
#
# Ficam na amostra final as TIs que tiverem, ao mesmo tempo:
#   (a) IMAGENS: em cada ano, maior intervalo entre datas Landsat 8/9 com
#       cena <= MAX_CLOUD_L % de nuvem, em jun-out, <= MAX_GAP_DIAS; e
#       >= MIN_ANOS_IMG anos assim em 2014-2024. Sentinel-2 nao entra (sem
#       cobertura regular em 2014-2016).
#   (b) ENCONTROS: queimadas do restante da seca (cada mes de ago-out, pixels
#       conectados) encostando, a ate CONTACT_TOL_M, em cicatriz do inicio da
#       seca do mesmo ano, com >= MIN_CONTATO_M de borda em contato, em anos
#       com imagem adequada; >= MIN_ENCONTROS por TI.
#         ordem "clara"      : >= 2 meses de diferenca (ex.: jun x ago)
#         ordem "a verificar": meses vizinhos (jul x ago)
#
# Encontros calculados nos rasters de 30 m do bloco 01:
#   borda da queimada = pixels dela com vizinho (8 direcoes) fora dela
#   contato           = pixels de borda a ate 2 pixels de uma cicatriz inicial
#   contato (m)       = n de pixels de contato x 30 m
#
# Limitacoes (declarar no texto): nuvem = da CENA (CLOUD_COVER), nao da TI;
# encontros do MapBiomas mensal, antes da conferencia nas imagens (bloco 10).
#
# Output:
#   03_tables/amostra_final_tis.csv  (as 14, com elegivel e motivo de exclusao)
#   04_stats/elegibilidade_encontros_ti_ano.csv
#   02_cache/encontros_candidatos_<...>.gpkg (1 ponto por encontro)
#   06_logs/amostra_final.json
#   05_figures/02_elegibilidade.png
# ======================================================================

check_version()

import rasterio
from scipy import ndimage

# ============================================================
# 1. CRITERIOS
# ============================================================

IMG_MONTHS     = (6, 10)
MAX_CLOUD_L    = 30
MAX_GAP_DIAS   = 32          # = 2 revisitas do Landsat
MIN_ANOS_IMG   = 6           # de 11 anos
CONTACT_TOL_M  = 45          # 1,5 pixel
MIN_CONTATO_M  = 300
MIN_ENCONTROS  = 20

ANALYSIS_YEARS = list(YEARS)
FIRE_DIR = DIRS["exports"] / "fogo_mes"
CONN8 = np.ones((3, 3), int)
TOL_PX = int(np.ceil(CONTACT_TOL_M / PIX_M))

# ============================================================
# 2. (a) IMAGENS: datas limpas por TI e ano (so metadados)
# ============================================================

def clean_dates(ti_geom):
    d0, d1 = f"{ANALYSIS_YEARS[0]}-01-01", f"{ANALYSIS_YEARS[-1] + 1}-01-01"
    mm = ee.Filter.calendarRange(IMG_MONTHS[0], IMG_MONTHS[1], "month")
    out = {}
    for cid in ["LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"]:
        col = (ee.ImageCollection(cid).filterBounds(ti_geom).filterDate(d0, d1)
               .filter(mm).filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD_L)))
        out[cid.split("/")[1]] = col.aggregate_array("system:time_start").getInfo()
    return out

def max_gap(days, year):
    start = pd.Timestamp(year, IMG_MONTHS[0], 1)
    end = pd.Timestamp(year, IMG_MONTHS[1], 1) + pd.offsets.MonthEnd(0)
    pts = sorted({start, end, *[d for d in days if start <= d <= end]})
    return int(max((b - a).days for a, b in zip(pts[:-1], pts[1:])))

def run_imagery():
    rows = []
    for r in tqdm(list(tis.itertuples()), desc="Imagens por TI"):
        geom = tis_fc.filter(ee.Filter.eq("ti_id", int(r.ti_id))).geometry()
        by_sensor = {k: pd.DatetimeIndex(pd.to_datetime(v, unit="ms").normalize().unique())
                     for k, v in clean_dates(geom).items()}
        all_d = pd.DatetimeIndex(sorted(set().union(*[set(d) for d in by_sensor.values()])))
        for y in ANALYSIS_YEARS:
            dy = all_d[all_d.year == y]
            row = {"ti_id": r.ti_id, "year": y}
            for k, d in by_sensor.items():
                row[f"n_datas_{k}"] = int((d.year == y).sum())
            row.update({"n_datas_limpas": len(dy), "max_gap_dias": max_gap(list(dy), y)})
            rows.append(row)
    return pd.DataFrame(rows)

img = checkpoint_load_or_run(f"B01b_imagens_landsat_{ANALYSIS_YEARS[0]}_{ANALYSIS_YEARS[-1]}_c{MAX_CLOUD_L}_{RUN_TAG}",
                             run_imagery, ext="parquet")
img["imagem_ok"] = img["max_gap_dias"] <= MAX_GAP_DIAS

# ============================================================
# 3. (b) ENCONTROS NO RASTER DE 30 m
# ============================================================

def encounters_ti(ti_id):
    with rasterio.open(FIRE_DIR / f"l9_{RUN_TAG}_firemonth_ti{int(ti_id)}.tif") as src:
        arr, tr = src.read(), src.transform
    inside = arr[0] == 1
    enc_rows, area_rows = [], []
    for y in ANALYSIS_YEARS:
        m = arr[1 + SCAR_YEARS.index(y)].astype(np.int16)
        E = inside & np.isin(m, EARLY)
        L_all = inside & np.isin(m, LATE)
        area_rows.append({"ti_id": ti_id, "year": y, "precoce": float(E.sum() * 0.09),
                          "tardia": float(L_all.sum() * 0.09)})
        if not E.any() or not L_all.any():
            continue
        e_near = ndimage.maximum_filter(np.where(E, m, 0), size=2 * TOL_PX + 1)
        for mo in LATE:
            Lm = inside & (m == mo)
            if not Lm.any():
                continue
            lab, n = ndimage.label(Lm, structure=CONN8)
            edge = Lm & ~ndimage.binary_erosion(Lm, structure=CONN8, border_value=0)
            contact = edge & (e_near > 0)
            if not contact.any():
                continue
            ids_c = lab[contact]
            n_contact = np.bincount(ids_c, minlength=n + 1)
            n_edge = np.bincount(lab[edge], minlength=n + 1)
            n_px = np.bincount(lab.ravel(), minlength=n + 1)
            emax = np.zeros(n + 1, np.int16)
            np.maximum.at(emax, ids_c, e_near[contact])
            hits = np.nonzero(n_contact * PIX_M >= MIN_CONTATO_M)[0]
            hits = hits[hits > 0]
            if len(hits) == 0:
                continue
            cents = ndimage.center_of_mass(Lm, lab, hits)
            for k, (r, c) in zip(hits, cents):
                gap = int(mo - emax[k])
                enc_rows.append({
                    "scar_id": f"{ti_id}_{y}_{mo}_{k}", "ti_id": ti_id, "year": y,
                    "month_late": int(mo), "month_early_max": int(emax[k]),
                    "contato_m": float(n_contact[k] * PIX_M), "perimetro_m": float(n_edge[k] * PIX_M),
                    "frac_borda_em_contato": float(n_contact[k] / max(n_edge[k], 1)),
                    "area_queimada_ha": float(n_px[k] * 0.09),
                    "ordem": "clara" if gap >= 2 else "a verificar",
                    "x": tr.c + (c + 0.5) * PIX_M, "y": tr.f - (r + 0.5) * PIX_M})
    del arr
    return enc_rows, area_rows

names_all = tis.set_index("ti_id")["ti_name"].to_dict()

def run_encounters():
    enc_rows, area_rows = [], []
    for t in tqdm(tis["ti_id"].astype(int).tolist(), desc="Encontros por TI"):
        e, a = encounters_ti(t)
        enc_rows += e
        area_rows += a
        console.print(f"  [dim]{names_all[t]}: {len(e):,} encontros[/dim]")
    enc = pd.DataFrame(enc_rows)
    g = gpd.GeoDataFrame(enc, geometry=gpd.points_from_xy(enc["x"], enc["y"]), crs=AREA_CRS) \
        if len(enc) else gpd.GeoDataFrame(columns=["ti_id", "year", "ordem", "contato_m", "geometry"],
                                          geometry="geometry", crs=AREA_CRS)
    write_table(pd.DataFrame(area_rows), cache_path(f"elegibilidade_areas_{RUN_TAG}", "parquet"))
    return g

enc = checkpoint_load_or_run(f"encontros_candidatos_{ANALYSIS_YEARS[0]}_{ANALYSIS_YEARS[-1]}"
                             f"_t{CONTACT_TOL_M}_m{MIN_CONTATO_M}_{RUN_TAG}", run_encounters, ext="gpkg")
areas = read_table(cache_path(f"elegibilidade_areas_{RUN_TAG}", "parquet"))

enc_ty = (pd.DataFrame(enc.drop(columns="geometry"))
          .groupby(["ti_id", "year"])
          .agg(n_encontros=("scar_id", "size"),
               n_ordem_clara=("ordem", lambda o: int((o == "clara").sum())),
               contato_km=("contato_m", lambda c: c.sum() / 1000))
          .reset_index())
ty = (img.merge(enc_ty, on=["ti_id", "year"], how="left")
         .merge(areas, on=["ti_id", "year"], how="left"))
for c in ["n_encontros", "n_ordem_clara", "contato_km", "precoce", "tardia"]:
    ty[c] = ty[c].fillna(0)
ty.to_csv(stats_path("elegibilidade_encontros_ti_ano"), index=False)

# ============================================================
# 4. ELEGIBILIDADE POR TI E MOTIVO DAS EXCLUSOES
# ============================================================

ok_years = ty[ty["imagem_ok"]]
per_ti = (tis[["ti_id", "terrai_cod", "ti_name", "area_ha"]]
          .merge(ty.groupby("ti_id").agg(anos_imagem_ok=("imagem_ok", "sum"),
                                          gap_mediano_dias=("max_gap_dias", "median")).reset_index(),
                 on="ti_id", how="left")
          .merge(ok_years.groupby("ti_id").agg(encontros=("n_encontros", "sum"),
                                                encontros_ordem_clara=("n_ordem_clara", "sum"),
                                                contato_km=("contato_km", "sum")).reset_index(),
                 on="ti_id", how="left")
          .fillna({"anos_imagem_ok": 0, "encontros": 0, "encontros_ordem_clara": 0, "contato_km": 0}))

def motivo(r):
    m = []
    if r["anos_imagem_ok"] < MIN_ANOS_IMG:
        m.append(f"imagens: {int(r['anos_imagem_ok'])} ano(s) com intervalo <= {MAX_GAP_DIAS} d "
                 f"(minimo {MIN_ANOS_IMG})")
    if r["encontros"] < MIN_ENCONTROS:
        m.append(f"encontros: {int(r['encontros'])} em anos com imagem adequada (minimo {MIN_ENCONTROS})")
    return "; ".join(m)

per_ti["motivo_exclusao"] = per_ti.apply(motivo, axis=1)
per_ti["elegivel"] = per_ti["motivo_exclusao"] == ""
per_ti = per_ti.sort_values(["elegivel", "encontros"], ascending=[False, False])
per_ti.to_csv(table_path("amostra_final_tis"), index=False)
save_json({"criterios": {"anos": [ANALYSIS_YEARS[0], ANALYSIS_YEARS[-1]], "IMG_MONTHS": IMG_MONTHS,
                         "sensores": "Landsat 8/9 C2 L2", "MAX_CLOUD_L": MAX_CLOUD_L,
                         "MAX_GAP_DIAS": MAX_GAP_DIAS, "MIN_ANOS_IMG": MIN_ANOS_IMG,
                         "CONTACT_TOL_M": CONTACT_TOL_M, "MIN_CONTATO_M": MIN_CONTATO_M,
                         "MIN_ENCONTROS": MIN_ENCONTROS},
           "elegiveis": per_ti.loc[per_ti["elegivel"], "ti_name"].tolist(),
           "excluidas": dict(zip(per_ti.loc[~per_ti["elegivel"], "ti_name"],
                                 per_ti.loc[~per_ti["elegivel"], "motivo_exclusao"]))},
          DIRS["logs"] / "amostra_final.json")

AMOSTRA_TI_IDS = per_ti.loc[per_ti["elegivel"], "ti_id"].astype(int).tolist()

t = Table(title=f"Amostra final: {len(AMOSTRA_TI_IDS)} de {len(per_ti)} TIs com BRIF")
for c in ["TI", "anos c/ imagem", "encontros", "ordem clara", "contato (km)", "situacao"]:
    t.add_column(c)
for _, r in per_ti.iterrows():
    t.add_row(str(r["ti_name"]), str(int(r["anos_imagem_ok"])), str(int(r["encontros"])),
              str(int(r["encontros_ordem_clara"])), f"{r['contato_km']:.1f}",
              "[green]entra[/green]" if r["elegivel"] else f"[red]sai[/red] - {r['motivo_exclusao']}")
console.print(t)

# ============================================================
# 5. FIGURA DE CONFERENCIA (a versao da revista e a FigR1 do bloco 17)
# ============================================================

names = per_ti.set_index("ti_id")["ti_name"]
order = per_ti["ti_id"].tolist()
mat = ty.pivot_table(index="ti_id", columns="year", values="n_encontros", fill_value=0).reindex(order)
okm = ty.pivot_table(index="ti_id", columns="year", values="imagem_ok", aggfunc="first").reindex(order)
fig, ax = plt.subplots(figsize=(1.2 + 0.55 * mat.shape[1], 0.9 + 0.38 * mat.shape[0]))
im = ax.imshow(mat.values, cmap="Blues", aspect="auto")
vmax = np.nanmax(mat.values) if mat.size else 0
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = int(mat.values[i, j]); ok_ = bool(okm.values[i, j])
        ax.text(j, i, "x" if not ok_ else (str(v) if v else ""), ha="center", va="center", fontsize=7,
                color="#b2182b" if not ok_ else ("white" if v > vmax / 2 else "black"))
ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(mat.columns, fontsize=8)
ax.set_yticks(range(mat.shape[0]))
ax.set_yticklabels([f"{names[i]}{'' if i in AMOSTRA_TI_IDS else '  (sai)'}" for i in mat.index], fontsize=8)
ax.grid(False)
ax.set_title("Encontros candidatos (ago-out encostando em mai-jul)\nx = ano sem imagem adequada", fontsize=10)
fig.colorbar(im, ax=ax, shrink=0.7, label="encontros")
fig.savefig(fig_path("02_elegibilidade"))
plt.show()

console.print(f"[bold green]OK BLOCO 02 completo: amostra final = {len(AMOSTRA_TI_IDS)} TIs "
              f"({', '.join(names[i] for i in AMOSTRA_TI_IDS)}).[/bold green]")
