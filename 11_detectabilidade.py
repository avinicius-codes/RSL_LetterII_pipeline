# ======================================================================
# BLOCO 11 - Detectabilidade: a interrupcao nas bordas e real ou e o NBR que nao ve fogo sobre area queimada?
# Depende dos blocos 00, 03 (rasters), 05 (MODIS), 06 e 10 (segmentos).
# ======================================================================

check_version()

# ============================================================
# BLOCK 8b - Detectability checks
#
# O problema: no bloco 10 a CONTINUIDADE e uma nova queda de NBR na faixa interna.
#   Na REFERENCIA o interior e vegetacao (NBR ~0,4): qualquer fogo derruba o NBR.
#   Na CICATRIZ o interior ja queimou (NBR ~0) e tem pouco combustivel: uma
#   reentrada real mexe pouco no NBR. A interrupcao nas cicatrizes pode estar
#   inflada pelo DETECTOR, nao pelo fogo. Tres verificacoes:
#
# (A) CURVA DO LIMIAR: % de interrupcao (cicatriz x referencia) refeita com o
#     limiar da queda media de NBR na faixa interna variando de 0,02 a 0,20,
#     e com a queda RELATIVA ao estado anterior (dNBR / sqrt(|NBR antes|),
#     forma do RdNBR, Miller & Thode 2007; NBR antes com piso de 0,05).
#     Se o contraste so existe em limiares altos, ele e do detector.
#
# (B) SENSIBILIDADE DO LANDSAT COM ENTRADA CONFIRMADA PELO MODIS: nos segmentos
#     em que um pixel MODIS com fogo do restante esta >= 1 km DENTRO da
#     cicatriz (o fogo entrou de fato), em que fracao o Landsat tambem marcou
#     continuidade? Mesmo calculo na referencia. Diferenca = vies de deteccao.
#
# (C) TESTE INDEPENDENTE DO NBR (MODIS): densidade de pixels-dia MODIS com fogo
#     no restante da seca (FireMask >= 8) dentro dos NUCLEOS das cicatrizes do
#     inicio (pixels a > 1 km da borda: o pixel MODIS inteiro cabe dentro) x
#     nucleos de combustivel ainda nao queimado no fim do inicio da seca,
#     na mesma TI-ano. Versao "local": so o combustivel a ate 5 km de uma
#     cicatriz. Razao de taxas por Poisson com efeito fixo de TI-ano e IC por
#     bootstrap de TIs. Nao depende do NBR nem da regra de borda: se a razao
#     for << 1, as cicatrizes de fato barram o fogo posterior.
#
# Output:
#   04_stats/B08b_curva_limiar.csv, B08b_sensibilidade_landsat.csv,
#            B08b_modis_nucleos_ti_ano.csv, B08b_modis_razao_taxas.csv
#   05_figures/B08b_detectabilidade.{tif,png,pdf}   (600 dpi)
# ============================================================

from scipy import ndimage
import statsmodels.api as sm
import statsmodels.formula.api as smf

# ============================================================
# 1. PARAMETERS
# ============================================================

TAG_SEG    = globals().get("TAG_SEG", f"{TAG_YEARS}_md")
FOCOS_NAME = globals().get("FOCOS_NAME", f"modis_focos_v1_{TAG_YEARS}")
LIMIARES   = np.round(np.arange(0.02, 0.205, 0.01), 2)
PRE_PISO   = 0.05
OBS_MIN    = 0.5
CORE_M     = [1000, 1500]          # nucleo: > 1 km da borda (principal) e > 1,5 km (sensibilidade)
LOCAL_M    = 5000                  # versao local: combustivel a ate 5 km de uma cicatriz
N_BOOT     = 2000
SEASONS    = load_seasons()
AMOSTRA    = load_sample_ids()
rng        = np.random.default_rng(8)

segs = pd.read_parquet(cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[FUEL_MAIN]}_{TAG_SEG}", "parquet"))
if "drop_int_med" not in segs.columns:
    raise RuntimeError("Segmentos sem 'drop_int_med' - rode o bloco 10 novo (MODIS) antes do bloco 11.")

# ============================================================
# 2. (A) CURVA DO LIMIAR
# ============================================================

d = segs[segs["resultado"].isin(["interrupcao", "continuidade"]) & (segs["frac_int_obs"] >= OBS_MIN)
         & (segs["viirs_dentro"] == 0)].copy()                   # so o Landsat decide
d["drop_rel"] = d["drop_int_med"] / np.sqrt(np.maximum(np.abs(d["nbr_pre_int"]), PRE_PISO))
rows = []
for t in LIMIARES:
    for tipo, g in d.groupby("tipo_seg"):
        rows.append({"limiar": t, "tipo_seg": tipo, "n": len(g),
                     "interrupcao_abs_%": 100 * (g["drop_int_med"] < t).mean(),
                     "interrupcao_rel_%": 100 * (g["drop_rel"] < t / np.sqrt(0.4)).mean()})
curva = pd.DataFrame(rows)
curva.to_csv(stats_path("B08b_curva_limiar"), index=False)
estado = d.groupby("tipo_seg")[["nbr_pre_int", "drop_int_med", "drop_rel"]].describe().T
estado.to_csv(stats_path("B08b_estado_faixa_interna"))
console.print("[bold](A) Estado da faixa interna antes do fogo posterior (NBR) e queda observada[/bold]")
display(estado.round(3))
console.print("[bold](A) % de interrupcao pelo limiar de queda media de NBR[/bold]")
display(curva.pivot_table(index="limiar", columns="tipo_seg", values=["interrupcao_abs_%", "interrupcao_rel_%"]).round(1))

# ============================================================
# 3. (B) SENSIBILIDADE DO LANDSAT DADA ENTRADA CONFIRMADA PELO MODIS
# ============================================================

c = segs[segs["chegada"] & (segs["viirs_dentro"] > 0) & (segs["frac_int_obs"] >= OBS_MIN)].copy()
c["landsat_viu"] = c["frac_int_nova"] >= ENC_DEFAULT["cont_min"] if "ENC_DEFAULT" in globals() else c["frac_int_nova"] >= 0.2
sens = c.groupby("tipo_seg").agg(n_segmentos=("seg_uid", "size"), landsat_viu_entrada=("landsat_viu", "mean"),
                                 queda_mediana=("drop_int_med", "median"), nbr_antes_mediano=("nbr_pre_int", "median"))
sens.to_csv(stats_path("B08b_sensibilidade_landsat"))
console.print("[bold](B) Entrada confirmada pelo MODIS: em que fracao o Landsat tambem viu?[/bold]")
display(sens.round(3))

# ============================================================
# 4. (C) MODIS NOS NUCLEOS: CICATRIZ x COMBUSTIVEL NAO QUEIMADO
# ============================================================

if "focos_raw" not in globals():
    focos_raw = read_table(cache_path(FOCOS_NAME, "parquet"))
fo = focos_raw[focos_raw["confidence"].astype(str).str[0] != "l"].copy()
fo["acq_date"] = pd.to_datetime(fo["acq_date"])
fo = fo.drop_duplicates(["latitude", "longitude", "acq_date"])   # pixel-dia (Terra e Aqua no mesmo dia = 1)
_g = gpd.GeoSeries(gpd.points_from_xy(fo["longitude"], fo["latitude"]), crs="EPSG:4326").to_crs(AREA_CRS)
fo["x"], fo["y"] = _g.x.to_numpy(), _g.y.to_numpy()
fo["year"], fo["mes"] = fo["acq_date"].dt.year, fo["acq_date"].dt.month

def core_counts(ti, y, core_m, scheme=SEASON_MAIN, fuel_mode=FUEL_MAIN, keep_masks=False):
    st, yr = static_of(ti), read_raster(ti, y)
    ini, res = SEASONS[scheme][int(ti)]
    inside = st["ti"] == ti
    queim = inside & fuel_from_cover(yr["cover"], fuel_mode) & (st["barrier"] == 0)
    sm_ = season_masks(yr["month"], ti, scheme, SEASONS)
    E = sm_["inicio"] & queim
    U = queim & ~sm_["antes"] & ~E
    k = core_m / PIX_M
    coreE = ndimage.distance_transform_edt(E) > k
    coreU = ndimage.distance_transform_edt(U) > k
    nearE = ndimage.distance_transform_edt(~E) <= LOCAL_M / PIX_M if E.any() else np.zeros_like(E)
    tr = st["_transform"]
    p = fo[(fo["ti_id"] == ti) & (fo["year"] == y) & fo["mes"].isin(res)]
    c_ = np.floor((p["x"].to_numpy() - tr.c) / PIX_M).astype(int)
    r_ = np.floor((tr.f - p["y"].to_numpy()) / PIX_M).astype(int)
    ok = (r_ >= 0) & (r_ < E.shape[0]) & (c_ >= 0) & (c_ < E.shape[1])
    r_, c_ = r_[ok], c_[ok]
    out = {"ti_id": ti, "year": y, "core_m": core_m,
           "n_cicatriz": int(coreE[r_, c_].sum()), "km2_cicatriz": coreE.sum() * 9e-4,
           "n_naoqueimado": int(coreU[r_, c_].sum()), "km2_naoqueimado": coreU.sum() * 9e-4,
           "n_naoqueimado_local": int((coreU & nearE)[r_, c_].sum()),
           "km2_naoqueimado_local": (coreU & nearE).sum() * 9e-4}
    if keep_masks:
        return out, dict(coreE=coreE, coreU=coreU, E=E, L=sm_["resto"] & inside, inside=inside, tr=tr,
                         pts=(p["x"].to_numpy()[ok], p["y"].to_numpy()[ok]))
    return out

rows = [core_counts(ti, y, cm) for cm in CORE_M for ti in tqdm(AMOSTRA, desc=f"Nucleos MODIS") for y in YEARS]
nuc = pd.DataFrame(rows)
nuc.to_csv(stats_path("B08b_modis_nucleos_ti_ano"), index=False)

def rate_ratio(df, ref="naoqueimado"):
    """Razao de taxas cicatriz / referencia: Poisson com efeito fixo de TI-ano + bootstrap de TIs."""
    dd = df[(df["km2_cicatriz"] > 0) & (df[f"km2_{ref}"] > 0)]
    long = pd.concat([pd.DataFrame({"ti_id": dd["ti_id"], "ty": dd["ti_id"].astype(str) + "_" + dd["year"].astype(str),
                                    "cic": 1, "n": dd["n_cicatriz"], "km2": dd["km2_cicatriz"]}),
                      pd.DataFrame({"ti_id": dd["ti_id"], "ty": dd["ti_id"].astype(str) + "_" + dd["year"].astype(str),
                                    "cic": 0, "n": dd[f"n_{ref}"], "km2": dd[f"km2_{ref}"]})])
    pooled = (dd["n_cicatriz"].sum() / dd["km2_cicatriz"].sum()) / (dd[f"n_{ref}"].sum() / dd[f"km2_{ref}"].sum())
    try:
        m = smf.glm("n ~ cic + C(ty)", data=long, family=sm.families.Poisson(),
                    offset=np.log(long["km2"])).fit(cov_type="cluster", cov_kwds={"groups": long["ti_id"]})
        rr_glm = float(np.exp(m.params["cic"]))
    except Exception:
        rr_glm = np.nan
    ids = dd["ti_id"].unique()
    boots = []
    for _ in range(N_BOOT):
        b = pd.concat([dd[dd["ti_id"] == t] for t in rng.choice(ids, len(ids))])
        den = b[f"n_{ref}"].sum() / b[f"km2_{ref}"].sum()
        if den > 0:
            boots.append((b["n_cicatriz"].sum() / b["km2_cicatriz"].sum()) / den)
    lo, hi = (np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan))
    return {"referencia": ref, "ti_anos": len(dd), "focos_cicatriz": int(dd["n_cicatriz"].sum()),
            "km2_cicatriz": dd["km2_cicatriz"].sum(), "focos_ref": int(dd[f"n_{ref}"].sum()),
            "km2_ref": dd[f"km2_{ref}"].sum(), "razao_taxas_agregada": pooled, "razao_taxas_poisson_FE": rr_glm,
            "ic95_inf_boot_TI": lo, "ic95_sup_boot_TI": hi}

rr = pd.DataFrame([dict(core_m=cm, **rate_ratio(nuc[nuc["core_m"] == cm], ref))
                   for cm in CORE_M for ref in ["naoqueimado", "naoqueimado_local"]])
per_ti = (nuc[nuc["core_m"] == CORE_M[0]].groupby("ti_id")
          [["n_cicatriz", "km2_cicatriz", "n_naoqueimado", "km2_naoqueimado"]].sum())
per_ti["razao_taxas"] = (per_ti["n_cicatriz"] / per_ti["km2_cicatriz"]) / (per_ti["n_naoqueimado"] / per_ti["km2_naoqueimado"])
per_ti["TI"] = per_ti.index.map(tis.set_index("ti_id")["ti_name"])
rr.to_csv(stats_path("B08b_modis_razao_taxas"), index=False)
per_ti.to_csv(stats_path("B08b_modis_razao_taxas_por_TI"))
console.print("[bold](C) Focos MODIS do restante da seca: nucleo de cicatriz / nucleo nao queimado[/bold]")
display(rr.round(3)); display(per_ti.round(3))

# ============================================================
# 5. FIGURA (600 dpi): mapa de um TI-ano + as tres verificacoes
# ============================================================

try:
    ex = nuc[nuc["core_m"] == CORE_M[0]].assign(t=lambda x: x["n_cicatriz"] + x["n_naoqueimado"]) \
            .sort_values(["km2_cicatriz", "t"], ascending=False).iloc[0]
    _, M = core_counts(int(ex["ti_id"]), int(ex["year"]), CORE_M[0], keep_masks=True)
    from matplotlib.colors import ListedColormap
    tr = M["tr"]; Hh, Ww = M["E"].shape
    ext = (tr.c, tr.c + Ww * PIX_M, tr.f - Hh * PIX_M, tr.f)
    cls = np.zeros(M["E"].shape, np.uint8)
    cls[M["inside"]] = 1; cls[M["L"]] = 2; cls[M["E"]] = 3; cls[M["coreE"]] = 4; cls[M["coreU"] & ~M["L"]] = 5
    cls[M["coreU"] & M["L"]] = 6
    cmap = ListedColormap(["white", "#efeee9", "#f7c79a", "#9ec2ee", "#1f5fc8", "#cfe3c3", "#e98b4a"])
    fig = plt.figure(figsize=(17 / 2.54, 12.5 / 2.54), layout="constrained")
    gs = fig.add_gridspec(2, 3, height_ratios=[1.35, 1])
    ax = fig.add_subplot(gs[0, :])
    f = int(np.ceil(max(cls.shape) / 1600))
    ax.imshow(cls[::f, ::f], cmap=cmap, vmin=0, vmax=6, extent=ext, interpolation="nearest", rasterized=True)
    ax.scatter(*M["pts"], s=3, color="#7a1f3d", lw=0, zorder=3)
    tis[tis["ti_id"] == int(ex["ti_id"])].boundary.plot(ax=ax, color="black", lw=0.5)
    ax.set_aspect("equal"); ax.set_axis_off()
    x0 = ext[0] + 0.04 * (ext[1] - ext[0]); y0 = ext[2] + 0.05 * (ext[3] - ext[2])
    ax.add_patch(plt.Rectangle((x0, y0), 10000, (ext[3] - ext[2]) * 0.012, color="black"))
    ax.text(x0 + 5000, y0 + (ext[3] - ext[2]) * 0.02, "10 km", ha="center", va="bottom", fontsize=7)
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(color="#9ec2ee", label="Early scar (May–Jul)"),
                       mp.Patch(color="#1f5fc8", label="Early-scar core (> 1 km from edge)"),
                       mp.Patch(color="#cfe3c3", label="Unburned fuel core"),
                       mp.Patch(color="#f7c79a", label="Burned Aug–Oct (MapBiomas)"),
                       plt.Line2D([], [], marker="o", ls="", ms=3, color="#7a1f3d", label="MODIS fire pixel, Aug–Oct")],
              loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=6.5, frameon=False)
    ax.set_title(f"(a) {tis.set_index('ti_id').loc[int(ex['ti_id']), 'ti_name']} {int(ex['year'])}: "
                 f"MODIS later-fire pixels in scar cores vs unburned cores", fontsize=8, loc="left")
    ax1 = fig.add_subplot(gs[1, 0])
    for tipo, cor in [("cicatriz", "#1f5fc8"), ("referencia", "#8f8e88")]:
        g = curva[curva["tipo_seg"] == tipo]
        ax1.plot(g["limiar"], g["interrupcao_abs_%"], color=cor, lw=1.5, label={"cicatriz": "Scar", "referencia": "Reference"}[tipo])
        ax1.plot(g["limiar"], g["interrupcao_rel_%"], color=cor, lw=1.0, ls="--")
    ax1.axvline(0.10, color="black", lw=0.5, ls=":")
    ax1.set_xlabel("NBR-drop threshold"); ax1.set_ylabel("Interrupted (%)")
    ax1.set_title("(b) threshold (dashed: relative)", fontsize=8, loc="left"); ax1.legend(fontsize=6.5, frameon=False)
    ax2 = fig.add_subplot(gs[1, 1])
    if len(sens):
        ax2.bar(range(len(sens)), 100 * sens["landsat_viu_entrada"], color=["#1f5fc8", "#8f8e88"][:len(sens)])
        ax2.set_xticks(range(len(sens))); ax2.set_xticklabels([{"cicatriz": "Scar", "referencia": "Ref."}.get(i, i) for i in sens.index])
        for k_, v in enumerate(sens["n_segmentos"]):
            ax2.text(k_, 2, f"n={v:,}", ha="center", fontsize=6, color="white")
    ax2.set_ylim(0, 100); ax2.set_ylabel("Landsat flagged entry (%)")
    ax2.set_title("(c) entry confirmed by MODIS", fontsize=8, loc="left")
    ax3 = fig.add_subplot(gs[1, 2])
    r0 = rr[rr["core_m"] == CORE_M[0]].set_index("referencia")
    for k_, ref in enumerate(["naoqueimado", "naoqueimado_local"]):
        if ref in r0.index:
            v = r0.loc[ref]
            ax3.errorbar(k_, v["razao_taxas_agregada"], yerr=[[v["razao_taxas_agregada"] - v["ic95_inf_boot_TI"]],
                         [v["ic95_sup_boot_TI"] - v["razao_taxas_agregada"]]], fmt="o", color="#1f5fc8", capsize=3)
    ax3.axhline(1, color="black", lw=0.6, ls="--")
    ax3.set_xticks([0, 1]); ax3.set_xticklabels(["all unburned", "≤ 5 km of scar"], fontsize=7)
    ax3.set_yscale("log"); ax3.set_ylabel("MODIS rate ratio, scar / unburned")
    ax3.set_title("(d) NBR-independent test", fontsize=8, loc="left")
    for ext_, kw in [("tif", {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", {}), ("pdf", {})]:
        fig.savefig(fig_path("B08b_detectabilidade", ext_), dpi=600, facecolor="white", **kw)
    plt.show(); plt.close(fig)
except Exception as e_:
    console.print(f"[yellow]figura pulada: {str(e_)[:150]}[/yellow]")

console.print("[bold green]OK BLOCO 11 completo.[/bold green]")
