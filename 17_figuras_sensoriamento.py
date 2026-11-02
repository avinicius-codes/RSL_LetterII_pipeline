# ======================================================================
# BLOCO 17 - Figuras de sensoriamento remoto 600 dpi (TIFF LZW + PDF vetorial + PNG), em ingles
# Rode DEPOIS do bloco 16 e do bloco 11 na MESMA sessao (usa o estilo e as funcoes deles:
# salvar, moldura, grade_tis, mapa_localizacao, W, JNBR, CTX, core_counts).
# Depende tambem dos blocos 02, 05 (MODIS), 09 (SES) e 10 (segmentos).
# ======================================================================

check_version()
for _f in ["salvar", "moldura", "grade_tis", "mapa_localizacao", "rotulo_painel", "W", "CTX", "ORDER8"]:
    if _f not in globals():
        raise RuntimeError(f"'{_f}' nao definido - rode o bloco 16 nesta sessao antes do bloco 17.")

# ============================================================
# Figuras (todas com mapa; numeros escritos no proprio dado):
#   FigR1  Area e amostra: (a) localizacao no Brasil/Cerrado com grade lat/long,
#          14 TIs (8 analisadas, 6 excluidas com o motivo) | (b) triagem TI x ano:
#          maior intervalo entre imagens Landsat limpas e encontros candidatos
#   FigR2  O encontro visto do satelite (30 m, janela de 12 km do bloco 16):
#          (a) Landsat 8/9 falsa-cor SWIR2-NIR-red, fim do inicio da seca |
#          (b) idem, fim da seca | (c) dNBR + cicatrizes iniciais (MapBiomas),
#          pegadas dos pixels MODIS do restante e bordas interrompidas/atravessadas
#   FigR3  Teste independente do NBR: (a) mapa dos nucleos de cicatriz e do
#          combustivel nao queimado com os focos MODIS do restante | (b) razao
#          de taxas por TI (mapa) | (c) razao agregada com IC por bootstrap de TIs
#   FigR4  Configuracao pelo modelo nulo: SES medio da fragmentacao por celula
#          de 5 km em cada TI (azul = cicatrizes dividem o combustivel mais que o acaso)
# ============================================================

from pyproj import Transformer
from matplotlib.colors import TwoSlopeNorm
import matplotlib.patches as mpatches

TAG_SEG    = globals().get("TAG_SEG", f"{TAG_YEARS}_md")
FOCOS_NAME = globals().get("FOCOS_NAME", f"modis_focos_v1_{TAG_YEARS}")
_to_ll = Transformer.from_crs(AREA_CRS, "EPSG:4326", always_xy=True)
_to_xy = Transformer.from_crs("EPSG:4326", AREA_CRS, always_xy=True)
GRAT = "#b9b8b0"

# ------------------------------------------------------------
# Grade de coordenadas (lat/long) desenhada sobre mapas em EPSG:5880
# ------------------------------------------------------------
def graticule(ax, ext, step=None, labels=True, fs=5.4):
    x0, y0, x1, y1 = ext
    lons, lats = _to_ll.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    if step is None:
        span = max(lo1 - lo0, la1 - la0)
        step = next(s for s in [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10] if span / s <= 5)
    fmt = (lambda v, ew: f"{abs(v):.{0 if step >= 1 else (1 if step >= 0.1 else 2)}f}°{ew}")
    for lo in np.arange(np.ceil(lo0 / step) * step, lo1, step):
        la = np.linspace(la0 - 1, la1 + 1, 200)
        xs, ys = _to_xy.transform(np.full_like(la, lo), la)
        ax.plot(xs, ys, color=GRAT, lw=0.3, zorder=1.5, clip_on=True)
        if labels:
            xb, _ = _to_xy.transform(lo, la0)
            if x0 < xb < x1:
                ax.text(xb, y0 + 0.01 * (y1 - y0), fmt(lo, "W" if lo < 0 else "E"), fontsize=tam(fs), color=TINTA2,
                        ha="center", va="bottom", path_effects=HALO, zorder=9)
    for la in np.arange(np.ceil(la0 / step) * step, la1, step):
        lo = np.linspace(lo0 - 1, lo1 + 1, 200)
        xs, ys = _to_xy.transform(lo, np.full_like(lo, la))
        ax.plot(xs, ys, color=GRAT, lw=0.3, zorder=1.5, clip_on=True)
        if labels:
            _, yb = _to_xy.transform(lo0, la)
            if y0 < yb < y1:
                ax.text(x0 + 0.01 * (x1 - x0), yb, fmt(la, "S" if la < 0 else "N"), fontsize=tam(fs), color=TINTA2,
                        ha="left", va="center", path_effects=HALO, zorder=9)

# ============================================================
# FIG R1 - AREA DE ESTUDO E TRIAGEM DA AMOSTRA
# ============================================================
def figR1():
    am_p = table_path("amostra_final_tis")
    am = pd.read_csv(am_p)
    ty_p = stats_path("elegibilidade_encontros_ti_ano")
    ty = pd.read_csv(ty_p)
    fig = plt.figure(figsize=(LARG, 15.5 * CM), layout="constrained")
    sf_a, sf_b = fig.subfigures(2, 1, height_ratios=[1.35, 1], hspace=0.03)
    ax = sf_a.subplots()
    ext = mapa_localizacao(ax, rotulos=True)
    excl = am[~am["elegivel"].astype(bool)]
    for _, r in excl.iterrows():
        g = tis[tis["ti_id"].astype(int) == int(r["ti_id"])]
        if len(g):
            p = g.geometry.iloc[0].representative_point()
            cod = "I" if "imagens" in str(r["motivo_exclusao"]) else "E"
            ax.annotate(cod, (p.x, p.y), xytext=(4, -6), textcoords="offset points", fontsize=tam(5.6),
                        color=TINTA2, fontstyle="italic", path_effects=HALO, zorder=6)
    graticule(ax, ext, step=5)
    moldura(ax, ext, barra_m=500000, seta=True, fs=5.6)
    # inset: America do Sul / Brasil
    axi = ax.inset_axes([0.70, 0.66, 0.30, 0.34])
    if "brasil" in CTX:
        CTX["brasil"].plot(ax=axi, facecolor=FUNDO, edgecolor="#9a9992", lw=0.3)
    if "cerrado" in CTX:
        CTX["cerrado"].plot(ax=axi, facecolor=CERRADO, edgecolor=CERRADO_BORDA, lw=0.3)
    axi.add_patch(mpatches.Rectangle(ext[:2], ext[2] - ext[0], ext[3] - ext[1], fill=False, ec=TINTA, lw=0.5))
    axi.set_aspect("equal"); axi.set_axis_off()
    sf_a.legend(handles=[mpatches.Patch(fc=LARANJA, ec=TINTA, lw=0.35, label="Analysed IL (numbers as in Table 1)"),
                         mpatches.Patch(fc="white", ec=TINTA2, lw=0.5, label="Excluded IL: I = imagery, E = encounters"),
                         mpatches.Patch(fc=CERRADO, ec=CERRADO_BORDA, lw=0.45, label="Cerrado biome")],
                loc="outside lower center", ncol=3, fontsize=tam(5.6), handlelength=1.1, columnspacing=1.0)
    rotulo_painel(ax, "a")

    axb = sf_b.subplots()
    order = am.sort_values(["elegivel", "ti_name"], ascending=[False, True])["ti_id"].astype(int).tolist()
    gap = ty.pivot_table(index="ti_id", columns="year", values="max_gap_dias").reindex(order)
    enc = ty.pivot_table(index="ti_id", columns="year", values="n_encontros", fill_value=0).reindex(order)
    cm_gap = LinearSegmentedColormap.from_list("gap", ["#1f5fc8", "#a9c8ee", "#fbe3c4", "#e0532b", "#7a1f3d"])
    im = axb.imshow(gap.values, cmap=cm_gap, norm=mpl.colors.Normalize(8, 96), aspect="auto", interpolation="nearest")
    for i in range(gap.shape[0]):
        for j in range(gap.shape[1]):
            v = int(enc.values[i, j])
            if v:
                axb.text(j, i, f"{v}" if v < 1000 else f"{v / 1000:.1f}k", ha="center", va="center",
                         fontsize=tam(4.6), color="white" if gap.values[i, j] < 20 or gap.values[i, j] > 70 else TINTA)
    axb.set_xticks(range(gap.shape[1])); axb.set_xticklabels(gap.columns, fontsize=tam(5.4))
    axb.set_yticks(range(gap.shape[0]))
    nm = tis.set_index("ti_id")["ti_name"]
    axb.set_yticklabels([f"{NUM.get(t, '–')} {nm[t]}" for t in order], fontsize=tam(5.4))
    n_ok = int(am["elegivel"].sum())
    axb.axhline(n_ok - 0.5, color=TINTA, lw=0.8)
    axb.grid(False); axb.tick_params(length=0)
    cb = sf_b.colorbar(im, ax=axb, fraction=0.03, pad=0.01, extend="max")
    cb.set_label("Longest gap between clear\nLandsat 8/9 dates, Jun–Oct (days)", fontsize=tam(5.6))
    cb.ax.tick_params(labelsize=tam(5.2)); cb.outline.set_linewidth(0.4)
    axb.set_title("numbers: candidate encounters (late fire touching early scar); line: analysed above, excluded below",
                  fontsize=tam(5.6), color=MUDO, loc="left", pad=2)
    rotulo_painel(axb, "b")
    salvar(fig, "FigR1_study_area_sample")

# ============================================================
# FIG R2 - O ENCONTRO VISTO PELO LANDSAT E PELO MODIS (30 m)
# ============================================================
def landsat_rgb(win, d0, d1, px=30):
    """Mediana Landsat 8/9 SR (SWIR2, NIR, red) sem nuvem na janela, grade EPSG:5880 de 30 m alinhada."""
    x0, y0, x1, y1 = win
    n_c, n_r = int(round((x1 - x0) / px)), int(round((y1 - y0) / px))
    rect = ee.Geometry.Rectangle([x0, y0, x1, y1], PROJ, False)
    def prep(i):
        i = ee.Image(i)
        clear = i.select("QA_PIXEL").bitwiseAnd(0b11111).eq(0)
        return i.select(["SR_B7", "SR_B5", "SR_B4"]).multiply(0.0000275).add(-0.2).updateMask(clear)
    col = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
           .filterBounds(rect).filterDate(d0, d1))
    n_img = col.size().getInfo()
    img = col.map(prep).median().unmask(-1).toFloat()
    arr = ee.data.computePixels({"expression": img, "fileFormat": "NUMPY_NDARRAY",
                                 "grid": {"dimensions": {"width": n_c, "height": n_r},
                                          "affineTransform": {"scaleX": px, "shearX": 0, "translateX": x0,
                                                              "shearY": 0, "scaleY": -px, "translateY": y1},
                                          "crsCode": AREA_CRS}})
    rgb = np.dstack([arr[b] for b in ["SR_B7", "SR_B5", "SR_B4"]]).astype(float)
    rgb[rgb < 0] = np.nan
    return rgb, n_img

def stretch(rgb, lo=2, hi=98, ref=None):
    ref = rgb if ref is None else ref
    out = np.empty_like(rgb)
    for k in range(3):
        a, b = np.nanpercentile(ref[..., k], [lo, hi])
        out[..., k] = np.clip((rgb[..., k] - a) / (b - a), 0, 1)
    return np.nan_to_num(out ** 0.9, nan=0.9)

def figR2():
    ti, yr, win = W
    pre, n_pre = landsat_rgb(win, f"{yr}-06-15", f"{yr}-08-01")
    post, n_post = landsat_rgb(win, f"{yr}-09-15", f"{yr}-11-01")
    both = np.concatenate([pre, post], axis=0)                     # mesmo estiramento nas duas datas
    pre_s, post_s = stretch(pre, ref=both), stretch(post, ref=both)
    ext_i = (win[0], win[2], win[1], win[3])
    early = np.isin(JNBR["month"], EARLY).astype(float) if JNBR is not None else None
    fo = read_table(cache_path(FOCOS_NAME, "parquet"))
    fo = fo[(fo["confidence"].astype(str).str[0] != "l")]
    fo["acq_date"] = pd.to_datetime(fo["acq_date"])
    fo = fo[(fo["acq_date"].dt.year == yr) & fo["acq_date"].dt.month.isin(LATE)]
    fx, fy = _to_xy.transform(fo["longitude"].to_numpy(), fo["latitude"].to_numpy())
    inw = (fx > win[0]) & (fx < win[2]) & (fy > win[1]) & (fy < win[3])
    fx, fy = fx[inw], fy[inw]
    sg = pd.read_parquet(cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[FUEL_MAIN]}_{TAG_SEG}", "parquet"),
                         columns=["ti_id", "year", "tipo_seg", "resultado", "x", "y"])
    sg = sg[(sg["ti_id"] == ti) & (sg["year"] == yr) & (sg["tipo_seg"] == "cicatriz") &
            sg["x"].between(win[0], win[2]) & sg["y"].between(win[1], win[3])]

    fig = plt.figure(figsize=(LARG, 7.6 * CM), layout="constrained")
    axs = fig.subplots(1, 3)
    titles = [f"Landsat 8/9, 15 Jun–31 Jul {yr} (n = {n_pre})", f"Landsat 8/9, 15 Sep–31 Oct {yr} (n = {n_post})",
              "dNBR, scars, MODIS and edges"]
    axs[0].imshow(pre_s, extent=ext_i, interpolation="nearest", rasterized=True, zorder=1)
    axs[1].imshow(post_s, extent=ext_i, interpolation="nearest", rasterized=True, zorder=1)
    if JNBR is not None:
        dn = np.ma.masked_less(JNBR["pre"], -100) / 100.0 - np.ma.masked_less(JNBR["post"], -100) / 100.0
        e = JNBR["ext"]
        axs[2].add_patch(mpatches.Rectangle(win[:2], win[2] - win[0], win[3] - win[1], color=SEM_DADO, zorder=0))
        im = axs[2].imshow(np.ma.clip(dn, -0.1, 0.8), extent=(e[0], e[1], e[2], e[3]), cmap=CMAP_DNBR,
                           norm=mpl.colors.Normalize(0, 0.6), interpolation="nearest", rasterized=True, zorder=1)
    for ax in axs:
        if early is not None and early.any():
            ax.contour(np.flipud(early), levels=[0.5], colors=["#5fd3ff" if ax is not axs[2] else C_INI],
                       linewidths=0.45, extent=ext_i, zorder=3)
    for x, y in zip(fx, fy):                                         # pegada nominal do pixel MODIS (~926 m)
        axs[2].add_patch(mpatches.Rectangle((x - 463, y - 463), 926, 926, fill=False, ec="#7a1f3d", lw=0.5, zorder=4))
    ok = sg[sg["resultado"] == "interrupcao"]; ct = sg[sg["resultado"] == "continuidade"]
    axs[2].scatter(ok["x"], ok["y"], s=2.5, color="#163f73", lw=0, zorder=5)
    axs[2].scatter(ct["x"], ct["y"], s=9, color=C_PASSOU, edgecolor="white", lw=0.4, zorder=6)
    for k, ax in enumerate(axs):
        ti_geom(ti).boundary.plot(ax=ax, color="white" if k < 2 else TINTA, lw=0.5, zorder=4)
        graticule(ax, win, labels=(k == 0))
        moldura(ax, win, barra_m=2000 if k == 0 else None, seta=(k == 2), fs=5)
        ax.set_title(titles[k], fontsize=tam(5.8), pad=2)
        rotulo_painel(ax, "abc"[k])
    if JNBR is not None:
        colorbar_fina(fig, im, axs[2], "dNBR (July − min Aug–Oct)", ticks=[0, 0.2, 0.4, 0.6], extend="max")
    fig.legend(handles=[Line2D([], [], color=C_INI, lw=0.9, label="Early scar, May–Jul (MapBiomas)"),
                        mpatches.Patch(fill=False, ec="#7a1f3d", lw=0.6, label="MODIS fire pixel, Aug–Oct"),
                        Line2D([], [], marker="o", ls="", ms=2, color="#163f73", label="Edge: fire interrupted"),
                        Line2D([], [], marker="o", ls="", ms=3.4, mfc=C_PASSOU, mec="white", label="Edge: fire crossed")],
               loc="outside lower center", ncol=4, fontsize=tam(5.4), handlelength=1.0, columnspacing=0.9)
    salvar(fig, "FigR2_encounter_landsat_modis")

# ============================================================
# FIG R3 - TESTE INDEPENDENTE DO NBR (FOCOS MODIS NOS NUCLEOS)
# ============================================================
def figR3():
    rr = pd.read_csv(stats_path("B08b_modis_razao_taxas"))
    pt = pd.read_csv(stats_path("B08b_modis_razao_taxas_por_TI"), index_col=0)
    nuc = pd.read_csv(stats_path("B08b_modis_nucleos_ti_ano"))
    fig = plt.figure(figsize=(LARG, 13.2 * CM), layout="constrained")
    sf_m, sf_g = fig.subfigures(2, 1, height_ratios=[1.25, 1], hspace=0.03)
    # (a) mapa do TI-ano com maior area de nucleo de cicatriz
    ex = nuc[nuc["core_m"] == nuc["core_m"].min()].sort_values("km2_cicatriz", ascending=False).iloc[0]
    _, M = core_counts(int(ex["ti_id"]), int(ex["year"]), int(ex["core_m"]), keep_masks=True)
    tr = M["tr"]; Hh, Ww = M["E"].shape
    e = (tr.c, tr.f - Hh * PIX_M, tr.c + Ww * PIX_M, tr.f)
    cls = np.zeros(M["E"].shape, np.uint8)
    cls[M["inside"]] = 1; cls[M["L"]] = 2; cls[M["E"]] = 3; cls[M["coreE"]] = 4; cls[M["coreU"]] = 5
    cmap = ListedColormap(["#ffffff", NEUTRO, "#f9c9a2", AZUL_CLARO, C_INI, "#cfe3c3"])
    ax = sf_m.subplots()
    f = int(np.ceil(max(cls.shape) / 1800))
    ax.imshow(np.ma.masked_equal(cls[::f, ::f], 0), cmap=cmap, vmin=0, vmax=5, extent=(e[0], e[2], e[1], e[3]),
              interpolation="nearest", rasterized=True, zorder=1)
    ax.scatter(*M["pts"], s=2.2, color=VINHO, lw=0, zorder=4)
    ti_geom(int(ex["ti_id"])).boundary.plot(ax=ax, color=TINTA, lw=0.5, zorder=5)
    bb = ti_geom(int(ex["ti_id"])).total_bounds
    h = max(bb[2] - bb[0], bb[3] - bb[1]) / 2 * 1.03; cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    ext = (cx - h, cy - h, cx + h, cy + h)
    graticule(ax, ext)
    moldura(ax, ext, barra_m=barra_redonda(2 * h), seta=True, fs=5.4)
    ax.set_title(f"{TI_NAME.get(int(ex['ti_id']))}, {int(ex['year'])}", fontsize=tam(6.2), loc="left")
    sf_m.legend(handles=[mpatches.Patch(color=AZUL_CLARO, label="Early scar (May–Jul)"),
                         mpatches.Patch(color=C_INI, label="Scar core, > 1 km from edge"),
                         mpatches.Patch(color="#cfe3c3", label="Unburned-fuel core, > 1 km"),
                         mpatches.Patch(color="#f9c9a2", label="Burned Aug–Oct"),
                         Line2D([], [], marker="o", ls="", ms=2.6, color=VINHO, label="MODIS fire pixel, Aug–Oct")],
                loc="outside right center", ncol=1, fontsize=tam(5.6), handlelength=1.0)
    rotulo_painel(ax, "a")
    # (b) razao de taxas por TI no mapa de localizacao
    axb, axc = sf_g.subplots(1, 2, width_ratios=[1.25, 1])
    vals = {int(k): float(v) for k, v in pt["razao_taxas"].items() if np.isfinite(v) and v > 0}
    norm = mpl.colors.LogNorm(max(min(vals.values()), 1e-3), 1) if vals else mpl.colors.LogNorm(1e-2, 1)
    cm_rr = LinearSegmentedColormap.from_list("rr", ["#163f73", "#2f78b4", "#9ec9e2", "#fbe3c4"])
    ext_l = mapa_localizacao(axb, cor_ti=vals, cmap=cm_rr, norm=norm)
    graticule(axb, ext_l, step=5, fs=5)
    moldura(axb, ext_l, barra_m=500000, seta=False, fs=5)
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cm_rr), ax=axb, fraction=0.04, pad=0.01)
    cb.set_label("MODIS rate ratio,\nscar / unburned core", fontsize=tam(5.6)); cb.ax.tick_params(labelsize=tam(5))
    rotulo_painel(axb, "b")
    # (c) razao agregada (log)
    lab = {"naoqueimado": "All unburned fuel", "naoqueimado_local": "Unburned ≤ 5 km of a scar"}
    y = 0
    for cm_ in sorted(rr["core_m"].unique()):
        for ref in ["naoqueimado", "naoqueimado_local"]:
            r = rr[(rr["core_m"] == cm_) & (rr["referencia"] == ref)]
            if not len(r):
                continue
            r = r.iloc[0]
            axc.plot([r["ic95_inf_boot_TI"], r["ic95_sup_boot_TI"]], [y, y], color=C_INI, lw=1.8, solid_capstyle="round")
            axc.scatter(r["razao_taxas_agregada"], y, s=26, color=C_INI, edgecolor="white", zorder=3)
            axc.text(r["ic95_sup_boot_TI"] * 1.15, y, f"{r['razao_taxas_agregada']:.2f}", va="center", fontsize=tam(5.6))
            axc.text(-0.02, y, f"{lab[ref]}\ncore > {cm_ / 1000:g} km", transform=mpl.transforms.blended_transform_factory(
                axc.transAxes, axc.transData), ha="right", va="center", fontsize=tam(5.4), linespacing=1.0)
            y += 1
    axc.axvline(1, color=TINTA2, lw=0.7, ls=(0, (3, 2)))
    axc.set_xscale("log"); axc.set_yticks([]); axc.set_ylim(-0.6, y - 0.4)
    axc.set_xlabel("Later-fire MODIS density, scar core / unburned core\n(95% CI, bootstrap over ILs)", fontsize=tam(5.8))
    axc.grid(axis="y", visible=False)
    rotulo_painel(axc, "c")
    salvar(fig, "FigR3_modis_independent_test")

# ============================================================
# FIG R4 - CONFIGURACAO PELO MODELO NULO, NO MAPA
# ============================================================
def figR4():
    cn = pd.read_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[FUEL_MAIN]}_{TAG_YEARS}_nulo", "parquet"))
    cn = cn[cn["q_inicio"] > 0].dropna(subset=["conf_split_ses"])
    g = cn.groupby(["ti_id", "x", "y"]).agg(ses=("conf_split_ses", "mean"), n=("year", "size")).reset_index()
    g = g[g["n"] >= 3]
    norm = TwoSlopeNorm(vmin=-3, vcenter=0, vmax=3)
    cm_ses = LinearSegmentedColormap.from_list("ses", ["#163f73", "#2f78b4", "#9ec9e2", "#f4f3ef", "#f9c9a2", "#e0532b", "#7a1f3d"])
    fig = plt.figure(figsize=(LARG, 9.8 * CM), layout="constrained")

    def desenhar(ax, ti):
        d_ = g[g["ti_id"] == ti]
        hh = CELL_M / 2
        if len(d_):
            gg = gpd.GeoDataFrame(d_[["ses"]], geometry=[_box(x - hh, y - hh, x + hh, y + hh) for x, y in zip(d_["x"], d_["y"])],
                                  crs=AREA_CRS)
            gg.plot(ax=ax, column="ses", cmap=cm_ses, norm=norm, edgecolor="white", linewidth=0.12, zorder=2)
    axs = grade_tis(fig, desenhar, info=lambda ti: (f"median SES {g.loc[g['ti_id'] == ti, 'ses'].median():.2f}"
                                                   if (g["ti_id"] == ti).any() else ""))
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cm_ses), ax=axs, location="bottom", shrink=0.45,
                      aspect=34, pad=0.02, extend="both")
    cb.set_label("Fuel-fragmentation SES vs null model (mean 2014–2024; blue: early scars split fuel more than chance)",
                 fontsize=tam(5.6))
    cb.ax.tick_params(labelsize=tam(5.2)); cb.outline.set_linewidth(0.4)
    rotulo_painel(axs[0, 0], "a")
    salvar(fig, "FigR4_null_model_configuration")

# ============================================================
# RODAR (cada figura isolada: se faltar um insumo, so ela e pulada)
# ============================================================
for fn in [figR1, figR2, figR3, figR4]:
    try:
        fn()
    except Exception as e:
        console.print(f"[yellow]{fn.__name__} pulada: {str(e)[:160]}[/yellow]")
console.print(f"[bold green]OK BLOCO 17 completo: figuras em {FIG_DIR} (600 dpi .tif/.pdf/.png).[/bold green]")
