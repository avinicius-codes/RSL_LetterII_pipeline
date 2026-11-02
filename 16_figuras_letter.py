# ======================================================================
# BLOCO 16 - Figuras e Tabela 1 da letter (Remote Sensing Letters, em ingles)
# Depende do bloco 00 e dos resultados ja salvos (01, 03, 07, 08, 10, 12, 14).
# Nao recalcula analises. 600 dpi: TIFF (LZW) + PDF vetorial + PNG.
# ======================================================================
#
# RSL: pagina de coluna unica; figuras na largura da mancha de texto
# (LARGURA_CM). Times New Roman (Liberation Serif no Colab), paleta azul/laranja
# segura para daltonismo, numeros escritos junto do dado, mapas com escala e norte.
#   Fig. 1  Premissa: (a) estacao dominante da queima por pixel nas TIs |
#           (b) area queimada anual, inicio x restante | (c) NBR mensal por classe
#   Fig. 2  O teste: (a) dNBR + cicatrizes + bordas atravessadas por TI |
#           (b) interrupcao cicatriz x referencia | (c) por TI
#   Fig. 3  Configuracao: (a) cicatrizes pela area | (b, c) % parado por area e
#           largura | (d) razoes de chances alem da quantidade
#   Fig. 4  Generalizacao: (a) % parado por celula de 5 km | (b) distribuicao por
#           TI | (c) robustez
#   Fig. S2 tipologia | Fig. S3 janela de 12 km a 30 m | Tabela 1
# JANELA = None escolhe a janela de 12 km sozinha; ou fixe JANELA = (ti_id, ano).
# ======================================================================

check_version()

JANELA = None
LARGURA_CM = 14.0
ESCALA_FONTE = 1.2

import sys, shutil
import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
from matplotlib.ticker import FixedLocator, NullLocator, FormatStrFormatter, MaxNLocator
import rasterio
from shapely.geometry import shape, box as _box
import docx
from docx.shared import Pt, Cm as DocxCm

if "google.colab" in sys.modules:
    os.system("apt-get -qq install -y fonts-liberation > /dev/null 2>&1")
    font_manager.fontManager = font_manager._load_fontmanager(try_read_cache=False)

FIG_DIR = DIRS["figures"] / "letter"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR = PROJECT_ROOT / "08_textos"
TXT_DIR.mkdir(exist_ok=True)
FIRE_DIR = DIRS["exports"] / "fogo_mes"
SEQ_DIR = DIRS["exports"] / "sequencia_md"

# ============================================================
# ESTILO
# ============================================================
CM = 1 / 2.54
LARG = LARGURA_CM * CM
TINTA, TINTA2, MUDO = "#0b0b0b", "#52514e", "#898781"
GRADE, EIXO, NEUTRO, FUNDO = "#e1e0d9", "#c3c2b7", "#f0efec", "#f4f3ef"
AZUL, LARANJA = "#2a78d6", "#eb6834"
AZUL_CLARO, ROXO, VINHO = "#a9c8ee", "#9b8ac4", "#7a1f3d"
CERRADO, CERRADO_BORDA = "#e2ead8", "#8aa36d"

def tam(pt):
    return round(pt * ESCALA_FONTE, 2)

mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": tam(7.5), "axes.labelsize": tam(7.5), "axes.titlesize": tam(7.5),
    "xtick.labelsize": tam(7), "ytick.labelsize": tam(7), "legend.fontsize": tam(6.8),
    "text.color": TINTA, "axes.labelcolor": TINTA, "axes.titlecolor": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.edgecolor": EIXO, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.minor.size": 1.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "legend.frameon": False, "legend.handlelength": 1.6,
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.dpi": 600, "figure.dpi": 150,
})
HALO = [pe.withStroke(linewidth=1.8, foreground="white")]
_PAINEIS = []

def _raiz(ax):
    f = ax.figure
    while getattr(f, "figure", f) is not f and hasattr(f, "figure"):
        f = f.figure
    return f

def rotulo_painel(ax, letra, **_):
    """(a), (b)... posicionados no salvar(), depois do layout."""
    _PAINEIS.append((ax, letra))

def _colocar_rotulos(fig):
    meus = [p for p in _PAINEIS if _raiz(p[0]) is fig]
    if meus and fig.get_layout_engine() is not None:
        topo = 0.65 / (fig.get_figheight() * 2.54)
        fig.get_layout_engine().set(rect=(0, 0.25 * topo, 1, 1 - 1.25 * topo))
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    inv = fig.transFigure.inverted()
    fixos = []
    for ax, letra in meus:
        bb = ax.get_tightbbox(r).transformed(inv)
        fixos.append((max(bb.x0, 0.0), bb.y1 + 0.004, letra))
    fig.set_layout_engine("none")
    for x, y, letra in fixos:
        fig.text(x, y, f"({letra})", fontweight="bold", fontsize=tam(8), ha="left", va="bottom")
    _PAINEIS[:] = [p for p in _PAINEIS if _raiz(p[0]) is not fig]

def salvar(fig, nome):
    _colocar_rotulos(fig)
    for ext, extra in [("pdf", {}), ("tif", {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", {})]:
        fig.savefig(FIG_DIR / f"{nome}.{ext}", dpi=600, facecolor="white", **extra)
    plt.show()
    plt.close(fig)
    console.print(f"[green]  {nome}: .pdf / .tif / .png (600 dpi)[/green]")

def moldura(ax, ext, barra_m=None, seta=True, fs=6, canto_barra="lower left", canto_seta="lower right"):
    """Mapa sem eixos, barra de escala preta/branca e seta de norte."""
    fs = tam(fs)
    ax.set_xlim(ext[0], ext[2]); ax.set_ylim(ext[1], ext[3])
    ax.set_aspect("equal"); ax.set_axis_off()
    w, h = ext[2] - ext[0], ext[3] - ext[1]
    if barra_m:
        x0 = ext[0] + 0.06 * w if "left" in canto_barra else ext[2] - 0.06 * w - barra_m
        y0 = ext[1] + 0.06 * h if "lower" in canto_barra else ext[3] - 0.08 * h
        th = 0.022 * h
        ax.add_patch(mpatches.Rectangle((x0, y0), barra_m / 2, th, fc=TINTA, ec=TINTA, lw=0.4, zorder=8))
        ax.add_patch(mpatches.Rectangle((x0 + barra_m / 2, y0), barra_m / 2, th, fc="white", ec=TINTA, lw=0.4, zorder=8))
        rot = f"{barra_m / 1000:g} km" if barra_m >= 1000 else f"{barra_m:g} m"
        ax.text(x0 + barra_m / 2, y0 - 0.012 * h, rot, fontsize=fs, ha="center", va="top", color=TINTA2,
                path_effects=HALO, zorder=8)
    if seta:
        xs = ext[0] + (0.90 if "right" in canto_seta else 0.10) * w
        ys = ext[1] + (0.10 if "lower" in canto_seta else 0.78) * h
        ax.annotate("", xy=(xs, ys + 0.09 * h), xytext=(xs, ys),
                    arrowprops=dict(arrowstyle="-|>", lw=0.7, color=TINTA, mutation_scale=7), zorder=8)
        ax.text(xs, ys - 0.01 * h, "N", ha="center", va="top", fontsize=fs + 1, fontweight="bold",
                path_effects=HALO, zorder=8)

def barra_redonda(largura_m, frac=0.25):
    alvo = frac * largura_m
    return max([k for k in [250, 500, 1000, 2000, 5000, 10000, 20000, 25000, 50000, 100000, 200000, 500000]
                if k <= alvo] or [250])

def dot_labels(ax, xs, ys, labels, dx, ha="left", fs=5.8, color=TINTA2):
    for x, y, s in zip(xs, ys, labels):
        ax.text(x + dx, y, s, fontsize=tam(fs), color=color, va="center", ha=ha)

TYPE_EN = {"Inicial grande": "Early, large", "Inicial pequena e fraca": "Early, small & weak",
           "Inicial pequena e intensa": "Early, small & intense", "Restante da seca": "Late season",
           "Fora da seca (nov-abr)": "Outside dry season", "Fragmento < 1 ha": "Fragments < 1 ha"}
TYPE_COL = {"Early, large": "#1d5aa6", "Early, small & weak": AZUL, "Early, small & intense": AZUL_CLARO,
            "Late season": LARANJA, "Outside dry season": "#c9c7bf", "Fragments < 1 ha": "#dcdad2"}
CMAP_NBR = LinearSegmentedColormap.from_list("nbr", ["#4a2a12", "#8c5a2b", "#c9a46b", "#efe3c6", "#a9cf8f", "#4f9a4a", "#1d5e2a"])
CMAP_DNBR = LinearSegmentedColormap.from_list("dnbr", ["#fbf6ea", "#fde0a3", "#f9a35a", "#e0532b", "#a8201a", "#5a0b10"])
SEM_DADO = "#e4e3de"
C_INI, C_TAR, C_PASSOU = "#1f5fc8", "#f28322", "#d1127a"
C_SEMQ, C_MISTO = "#e9e8e3", "#9a7fc6"
CMAP_PASSA = LinearSegmentedColormap.from_list("passa", ["#b2182b", "#ef8a62", "#fbe3c4", "#9ec9e2", "#2f78b4", "#163f73"])
CMAP_AREA2 = LinearSegmentedColormap.from_list("area2", ["#c6dbf7", "#6aa6e8", "#1f5fc8", "#0b2a66"])

# ============================================================
# DADOS
# ============================================================
def _csv(p, **kw):
    return pd.read_csv(p, **kw) if Path(p).exists() else None

STATS = ["B06_tipologia_resumo", "D1_tempo", "D2_foco_noturno_taxa", "D2_foco_noturno", "B09_celula_resumo",
         "B09_celula_coeficientes", "B08a_regra_antiga_x_simetrica", "B09_segmento_resumo",
         "B09_segmento_coeficientes", "B10_robustez_segmentos", "B09_cicatriz_vs_referencia"]
IDX0 = ("B06_tipologia_resumo", "D2_foco_noturno_taxa", "D2_foco_noturno", "B09_celula_coeficientes",
        "B09_segmento_coeficientes")
SEG_COLS = ["ti_id", "year", "tipo_seg", "resultado", "x", "y", "area_cicatriz_ha", "largura_local_m"]

AMOSTRA = load_sample_ids()
seg_file = cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[FUEL_MAIN]}_{TAG_SEG}", "parquet")
segs = pd.read_parquet(seg_file, columns=SEG_COLS)
art1 = _csv(DIRS["raw"] / "artigo1_tis.csv")
TI_NAME = dict(zip(tis["ti_id"].astype(int), tis["ti_name"]))
ORDER8 = tis[tis["ti_id"].astype(int).isin(AMOSTRA)].sort_values("ti_name")
NUM = {int(t): k for k, t in enumerate(ORDER8["ti_id"], start=1)}
R = {n: _csv(stats_path(n), index_col=0 if n in IDX0 else None) for n in STATS}
faltam = [n for n, v in R.items() if v is None]
if faltam:
    console.print(f"[yellow]WARNING faltam tabelas (paineis correspondentes saem vazios): {faltam}[/yellow]")
REGRA_OK = lambda s: s.astype(str).str.startswith("simetrica")

def annual_area():
    rows = []
    for ti in ORDER8["ti_id"].astype(int):
        p = FIRE_DIR / f"l9_{RUN_TAG}_firemonth_ti{ti}.tif"
        if not p.exists():
            continue
        with rasterio.open(p) as src:
            inside = src.read(1) == 1
            px_ha = abs(src.transform.a * src.transform.e) / 1e4
            for k, y in enumerate(SCAR_YEARS, start=2):
                if y in YEARS:
                    m = src.read(k)
                    rows.append({"ti_id": ti, "year": y, "early_ha": (inside & np.isin(m, EARLY)).sum() * px_ha,
                                 "late_ha": (inside & np.isin(m, LATE)).sum() * px_ha, "ti_ha": inside.sum() * px_ha})
    return pd.DataFrame(rows)

def nbr_profiles(step=3, max_px=4000, seed=7):
    """NBR mensal minimo (Landsat 8/9) por classe de pixel: cicatriz inicial, fogo posterior, nao queimado."""
    rng = np.random.default_rng(seed)
    acc = {}
    for ti in ORDER8["ti_id"].astype(int):
        for y in YEARS:
            try:
                r = read_raster(ti, y)
            except Exception:
                continue
            mon = r["month"][::step, ::step]
            cls = {"early": np.isin(mon, EARLY), "late": np.isin(mon, LATE), "unburned": mon == 0}
            for m in LS_MONTHS:
                v = r[f"nbr{m:02d}"][::step, ::step].astype(np.int16)
                ok = v > -101
                for c, mask in cls.items():
                    vals = v[ok & mask]
                    if len(vals) > max_px:
                        vals = rng.choice(vals, max_px, replace=False)
                    if len(vals):
                        acc.setdefault((c, m), []).append(vals / 100.0)
    rows = []
    for (c, m), lst in acc.items():
        a = np.concatenate(lst)
        rows.append({"classe": c, "mes": m, "p25": np.percentile(a, 25), "p50": np.median(a),
                     "p75": np.percentile(a, 75), "n": len(a)})
    return pd.DataFrame(rows).sort_values(["classe", "mes"])

area_anual = annual_area()
perfil_nbr = nbr_profiles()
perfil_nbr.to_csv(stats_path("F1_perfil_nbr_por_classe"), index=False)

_d_ok = segs[(segs["tipo_seg"] == "cicatriz") & segs["resultado"].isin(["interrupcao", "continuidade"])]
REP = {int(t): int(g.groupby("year").size().idxmax()) for t, g in _d_ok.groupby("ti_id")}

def pick_window():
    d = _d_ok
    if JANELA:
        cand = [tuple(JANELA)]
    else:
        g = d.groupby(["ti_id", "year"]).agg(n=("resultado", "size"),
                                             nc=("resultado", lambda r: (r == "continuidade").sum())).reset_index()
        g = g[g["nc"] >= 3] if (g["nc"] >= 3).any() else g
        cand = [tuple(int(v) for v in r) for r in g.sort_values("n", ascending=False)[["ti_id", "year"]].values[:15]]
    for ti, yr in cand:
        dd = d[(d["ti_id"] == ti) & (d["year"] == yr)]
        H, xe, ye = np.histogram2d(dd["x"], dd["y"], bins=[max(int(np.ptp(dd["x"]) // 3000), 1),
                                                           max(int(np.ptp(dd["y"]) // 3000), 1)])
        geom = tis[tis["ti_id"].astype(int) == ti].geometry.iloc[0].buffer(300)
        for flat in np.argsort(H, axis=None)[::-1][:300]:
            i, j = np.unravel_index(flat, H.shape)
            cx, cy = (xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2
            win = (cx - 6000, cy - 6000, cx + 6000, cy + 6000)
            if geom.contains(_box(*win)):
                return ti, yr, win
    ti, yr = cand[0]
    dd = d[(d["ti_id"] == ti) & (d["year"] == yr)]
    cx, cy = dd["x"].median(), dd["y"].median()
    return ti, yr, (cx - 6000, cy - 6000, cx + 6000, cy + 6000)

W = pick_window()
console.print(f"[cyan]Janela 12 x 12 km:[/cyan] {TI_NAME.get(W[0])}, {W[1]}")

def window_nbr():
    r = read_raster(W[0], W[1])
    tr = r["_transform"]; px = abs(tr.a)
    c0, r0 = int(round((W[2][0] - tr.c) / px)), int(round((tr.f - W[2][3]) / px))
    n = int(round((W[2][2] - W[2][0]) / px))
    cut = lambda a: a[max(r0, 0):r0 + n, max(c0, 0):c0 + n]
    pre = cut(r["nbr07"]).astype(np.int16)
    post = np.stack([cut(r[f"nbr{m:02d}"]).astype(np.int16) for m in LATE])
    post = np.where(post > -101, post, 999).min(0); post[post == 999] = -128
    return {"pre": pre, "post": post, "month": cut(r["month"]).astype(np.int16),
            "ext": np.array([W[2][0], W[2][2], W[2][1], W[2][3]], dtype=float)}

JNBR = window_nbr()

def ti_geom(ti):
    return tis[tis["ti_id"].astype(int) == ti]

def context_outlines():
    out = {}
    try:
        g = ee.FeatureCollection(EE_ASSET_BIOME).geometry(ee.ErrorMargin(500)).simplify(2000)
        out["cerrado"] = gpd.GeoDataFrame(geometry=[shape(g.getInfo())], crs="EPSG:4326").to_crs(AREA_CRS)
    except Exception as e:
        console.print(f"[dim]contorno do Cerrado indisponivel: {str(e)[:80]}[/dim]")
    try:
        br = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Brazil"))
        g = br.geometry(ee.ErrorMargin(1000)).simplify(5000)
        out["brasil"] = gpd.GeoDataFrame(geometry=[shape(g.getInfo())], crs="EPSG:4326").to_crs(AREA_CRS)
    except Exception as e:
        console.print(f"[dim]contorno do Brasil indisponivel: {str(e)[:80]}[/dim]")
    return out

CTX = context_outlines()

def mapa_localizacao(ax, cor_ti=None, cmap=None, norm=None, rotulos=True):
    """Cerrado + 14 TIs; cor_ti = {ti_id: valor} pinta as TIs analisadas."""
    if "brasil" in CTX:
        CTX["brasil"].plot(ax=ax, facecolor=FUNDO, edgecolor="#bdbcb6", lw=0.35, zorder=0)
    if "cerrado" in CTX:
        CTX["cerrado"].plot(ax=ax, facecolor=CERRADO, edgecolor=CERRADO_BORDA, lw=0.45, zorder=1)
    elig = tis["ti_id"].astype(int).isin(AMOSTRA)
    tis[~elig].plot(ax=ax, facecolor="white", edgecolor=TINTA2, lw=0.5, zorder=3)
    if cor_ti is None:
        tis[elig].plot(ax=ax, facecolor=LARANJA, edgecolor=TINTA, lw=0.35, zorder=4)
    for _, r in ORDER8.iterrows():
        p = r.geometry.representative_point(); ti = int(r["ti_id"])
        if cor_ti is not None and ti in cor_ti:
            ax.scatter(p.x, p.y, s=46, color=cmap(norm(cor_ti[ti])), edgecolor=TINTA, lw=0.6, zorder=5)
        if rotulos:
            ax.annotate(str(NUM[ti]), (p.x, p.y), xytext=(4.5, 2.5), textcoords="offset points",
                        fontsize=tam(6.2), fontweight="bold", color=TINTA, path_effects=HALO, zorder=6)
    b = CTX["cerrado"].total_bounds if "cerrado" in CTX else tis.total_bounds
    cx, cy, h = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[2] - b[0], b[3] - b[1]) / 2 * 1.05
    return (cx - h, cy - h, cx + h, cy + h)

def colorbar_fina(fig, mappable, ax, label, ticks=None, extend="neither", orientation="horizontal", **kw):
    cb = fig.colorbar(mappable, ax=ax, orientation=orientation, fraction=0.05, pad=0.02, aspect=28,
                      shrink=kw.get("shrink", 0.9), extend=extend)
    cb.set_label(label, fontsize=tam(6.2))
    if ticks is not None:
        cb.set_ticks(ticks)
    cb.outline.set_linewidth(0.4)
    cb.ax.tick_params(labelsize=tam(5.8), width=0.5, length=2)
    return cb

def mapa_ti(ti):
    """Ano REP[ti]: sequencia (bloco 10), dNBR (Landsat) e area de cada cicatriz inicial (~700 px)."""
    from scipy import ndimage
    yr = REP.get(ti)
    p = SEQ_DIR / f"seq_ti{ti}_{yr}.tif"
    if yr is None or not p.exists():
        return None
    with rasterio.open(p) as src:
        seq = src.read(1); tr = src.transform; b = src.bounds
    early = np.isin(seq, [1, 3])
    lab, n = ndimage.label(early, structure=np.ones((3, 3), int))
    area = np.zeros(seq.shape, np.float32)
    if n:
        sizes = np.bincount(lab.ravel())[1:] * abs(tr.a * tr.e) / 1e4
        area[early] = sizes[lab[early] - 1]
    out = {"seq": seq, "area": area}
    try:
        r = read_raster(ti, yr)
        pre = r["nbr07"].astype(np.int16)
        post = np.stack([r[f"nbr{m:02d}"].astype(np.int16) for m in LATE])
        post = np.where(post > -101, post, 999).min(0)
        dn = np.where((pre > -101) & (post < 999), (pre - post) / 100.0, np.nan).astype(np.float32)
        if dn.shape == seq.shape:
            out["dnbr"] = dn
    except Exception as e:
        console.print(f"[dim]dNBR indisponivel para TI {ti}: {str(e)[:60]}[/dim]")
    f = int(np.ceil(max(seq.shape) / 700))
    out = {k: v[::f, ::f] for k, v in out.items()}
    out["ext"] = np.array([b.left, b.right, b.bottom, b.top])
    return out

MAPAS = {int(t): mapa_ti(int(t)) for t in ORDER8["ti_id"]}

from matplotlib.path import Path as _MPath
from matplotlib.patches import PathPatch as _PathPatch

def _geom_path(geom):
    verts, codes = [], []
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            xy = np.asarray(ring.coords)
            verts += xy.tolist(); codes += [_MPath.MOVETO] + [_MPath.LINETO] * (len(xy) - 2) + [_MPath.CLOSEPOLY]
    return _MPath(verts, codes)

def recortar_na_ti(ax, ti):
    pp = _PathPatch(_geom_path(ti_geom(ti).geometry.iloc[0]), transform=ax.transData, facecolor="none", edgecolor="none")
    for a in list(ax.images) + list(ax.collections):
        a.set_clip_path(pp)

def grade_tis(sf, desenhar, info=None, ncols=4):
    """As TIs analisadas, cada uma num painel quadrado na sua escala, recortado no limite da TI."""
    nrows = int(np.ceil(len(ORDER8) / ncols))
    axs = np.atleast_2d(sf.subplots(nrows, ncols))
    for ax, (_, r) in zip(axs.ravel(), ORDER8.iterrows()):
        ti = int(r["ti_id"])
        ti_geom(ti).plot(ax=ax, facecolor=C_SEMQ, edgecolor="none", zorder=0)
        desenhar(ax, ti)
        recortar_na_ti(ax, ti)
        ti_geom(ti).boundary.plot(ax=ax, color=TINTA, lw=0.45, zorder=6)
        bb = r.geometry.bounds
        h = max(bb[2] - bb[0], bb[3] - bb[1]) / 2 * 1.04; cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        e = (cx - h, cy - h, cx + h, cy + h)
        canto = "lower left"
        for cand in ["lower left", "lower right", "upper left", "upper right"]:
            bw = barra_redonda(2 * h)
            xx = e[0] + 0.06 * 2 * h if "left" in cand else e[2] - 0.06 * 2 * h - bw
            yy = e[1] + 0.03 * 2 * h if "lower" in cand else e[3] - 0.12 * 2 * h
            if not _box(xx, yy, xx + bw, yy + 0.09 * 2 * h).intersects(r.geometry):
                canto = cand; break
        moldura(ax, e, barra_m=barra_redonda(2 * h), seta=(NUM[ti] == 1), fs=4.6, canto_barra=canto,
                canto_seta="upper right")
        ax.set_title(f"{NUM[ti]} {r['ti_name']}", fontsize=tam(5.8), pad=1.5, loc="left", fontweight="bold")
        if info:
            s = info(ti)
            if s:
                ax.text(0.0, -0.02, s, transform=ax.transAxes, ha="left", va="top", fontsize=tam(5.2), color=TINTA2)
    for ax in axs.ravel()[len(ORDER8):]:
        ax.set_axis_off()
    return axs

def _img(ax, arr, ext, **kw):
    return ax.imshow(arr, extent=(ext[0], ext[1], ext[2], ext[3]), interpolation="nearest", zorder=2,
                     rasterized=True, **kw)

def season_class(ti):
    p = FIRE_DIR / f"l9_{RUN_TAG}_firemonth_ti{ti}.tif"
    if not p.exists():
        return None, None
    with rasterio.open(p) as src:
        inside = src.read(1) == 1
        ne = np.zeros(inside.shape, np.uint8); nl = np.zeros(inside.shape, np.uint8)
        for k, y in enumerate(SCAR_YEARS, start=2):
            if y in YEARS:
                m = src.read(k)
                ne += np.isin(m, EARLY); nl += np.isin(m, LATE)
        b = src.bounds
    cl = np.zeros(inside.shape, np.uint8)
    cl[inside] = 1; cl[inside & (ne > nl)] = 2; cl[inside & (ne == nl) & (ne > 0)] = 3; cl[inside & (nl > ne)] = 4
    f = int(np.ceil(max(cl.shape) / 650))
    return np.ma.masked_equal(cl[::f, ::f], 0), (b.left, b.right, b.bottom, b.top)

def _regra_sim(rg):
    return rg[(rg["combustivel"] == FUEL_MAIN) & REGRA_OK(rg["regra"])].set_index("tipo_seg")

# ============================================================
# FIGURA 1 - PREMISSA
# ============================================================
def fig1():
    fig = plt.figure(figsize=(LARG, 13.6 * CM), layout="constrained")
    sf_m, sf_g = fig.subfigures(2, 1, height_ratios=[1.45, 1], hspace=0.04)
    cmap = ListedColormap([C_SEMQ, C_INI, C_MISTO, C_TAR]); norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], 4)

    def desenhar(ax, ti):
        cl, e = season_class(ti)
        if cl is not None:
            ax.imshow(cl, cmap=cmap, norm=norm, extent=e, interpolation="nearest", zorder=2, rasterized=True)
    axs = grade_tis(sf_m, desenhar)
    sf_m.legend(handles=[mpatches.Patch(color=C_INI, label="Burned mostly in May–Jul"),
                         mpatches.Patch(color=C_TAR, label="Burned mostly in Aug–Oct"),
                         mpatches.Patch(color=C_MISTO, label="Equal"), mpatches.Patch(color=C_SEMQ, label="Not burned")],
                loc="outside lower center", ncol=4, fontsize=tam(5.8), handlelength=1.0, columnspacing=1.0)
    rotulo_painel(axs[0, 0], "a")

    axb, axc = sf_g.subplots(1, 2)
    a = area_anual.groupby("year")[["early_ha", "late_ha"]].sum() / 1000
    axb.fill_between(a.index, 0, a["early_ha"], color=C_INI, alpha=0.12, lw=0)
    axb.plot(a.index, a["late_ha"], lw=1.6, color=C_TAR, marker="s", ms=3.4, mec="white", mew=0.5, zorder=3)
    axb.plot(a.index, a["early_ha"], lw=1.8, color=C_INI, marker="o", ms=3.8, mec="white", mew=0.6, zorder=4)
    axb.text(a.index[-1] + 0.3, a["late_ha"].iloc[-1], "Aug–Oct", color=C_TAR, fontsize=tam(5.8), va="center")
    axb.text(a.index[-1] + 0.3, a["early_ha"].iloc[-1], "May–Jul", color=C_INI, fontsize=tam(5.8), va="center")
    axb.set_xlim(YEARS[0] - 0.5, YEARS[-1] + 2.4); axb.spines["bottom"].set_bounds(YEARS[0], YEARS[-1])
    axb.set_xticks(range(YEARS[0], YEARS[-1] + 1, 2)); axb.set_xticks(YEARS, minor=True)
    axb.grid(axis="x", visible=False)
    axb.set_ylim(0, a.values.max() * 1.25); axb.yaxis.set_major_locator(MaxNLocator(4))
    axb.set_ylabel("Burned area (kha)")
    sh = 100 * a["early_ha"].sum() / (a["early_ha"].sum() + a["late_ha"].sum())
    axb.set_title(f"early burning = {sh:.0f}% of dry-season area", fontsize=tam(5.8), color=MUDO, loc="left", pad=2)
    rotulo_painel(axb, "b")

    axc.axvspan(4.5, 7.5, color=C_INI, alpha=0.08, lw=0, zorder=0)
    axc.axvspan(7.5, 10.5, color=C_TAR, alpha=0.10, lw=0, zorder=0)
    for c, cor, lab in [("unburned", "#7d7c78", "Unburned"), ("late", C_TAR, "Burned\nAug–Oct"),
                        ("early", C_INI, "Burned\nMay–Jul")]:
        d = perfil_nbr[perfil_nbr["classe"] == c]
        if not len(d):
            continue
        axc.fill_between(d["mes"], d["p25"], d["p75"], color=cor, alpha=0.14, lw=0, zorder=1)
        axc.plot(d["mes"], d["p50"], color=cor, lw=1.8, marker="o", ms=3.2, mec="white", mew=0.5, zorder=3)
        ult = d.iloc[-1]
        axc.text(ult["mes"] + 0.2, ult["p50"], lab, color=cor, fontsize=tam(5.6), va="center", ha="left", linespacing=1.0)
    axc.set_xticks(LS_MONTHS); axc.set_xticklabels(["A", "M", "J", "J", "A", "S", "O", "N"][:len(LS_MONTHS)])
    axc.set_xlim(LS_MONTHS[0] - 0.4, LS_MONTHS[-1] + 2.4); axc.spines["bottom"].set_bounds(LS_MONTHS[0], LS_MONTHS[-1])
    axc.grid(axis="x", visible=False); axc.yaxis.set_major_locator(MaxNLocator(4))
    axc.set_ylabel("Landsat NBR")
    axc.set_title("NBR drops in the month each pixel burns", fontsize=tam(5.8), color=MUDO, loc="left", pad=2)
    rotulo_painel(axc, "c")
    salvar(fig, "Fig1_premise")

# ============================================================
# FIGURA 2 - O TESTE NAS BORDAS
# ============================================================
def fig2():
    fig = plt.figure(figsize=(LARG, 14.2 * CM), layout="constrained")
    sf_m, sf_g = fig.subfigures(2, 1, height_ratios=[1.5, 1], hspace=0.04)
    norm_d = mpl.colors.Normalize(0, 0.6)

    def info(ti):
        dd = _d_ok[(_d_ok["ti_id"] == ti) & (_d_ok["year"] == REP.get(ti))]
        return f"{REP.get(ti)} · {100 * (dd['resultado'] == 'interrupcao').mean():.0f}% stopped" if len(dd) else ""

    def desenhar(ax, ti):
        m = MAPAS.get(ti)
        if m is None:
            return
        e = m["ext"]
        if "dnbr" in m:
            _img(ax, np.ma.masked_invalid(np.clip(m["dnbr"], 0, 0.8)), e, cmap=CMAP_DNBR, norm=norm_d)
        early = np.isin(m["seq"], [1, 3]).astype(float)
        if early.any():
            ax.contour(np.flipud(early), levels=[0.5], colors=[C_INI], linewidths=0.35, extent=(e[0], e[1], e[2], e[3]), zorder=4)
        dd = _d_ok[(_d_ok["ti_id"] == ti) & (_d_ok["year"] == REP.get(ti)) & (_d_ok["resultado"] == "continuidade")]
        ax.scatter(dd["x"], dd["y"], s=5, color=C_PASSOU, edgecolor="white", lw=0.25, zorder=5)
    axs = grade_tis(sf_m, desenhar, info=info)
    cb = sf_m.colorbar(mpl.cm.ScalarMappable(norm=norm_d, cmap=CMAP_DNBR), ax=axs, location="bottom",
                       shrink=0.32, aspect=30, pad=0.01, extend="max")
    cb.set_label("Landsat dNBR, July − min(Aug–Oct): later burning", fontsize=tam(5.8))
    cb.outline.set_linewidth(0.4); cb.ax.tick_params(labelsize=tam(5.4), width=0.4, length=1.5)
    sf_m.legend(handles=[Line2D([], [], color=C_INI, lw=1.0, label="Early-scar outline (May–Jul)"),
                         Line2D([], [], marker="o", ls="", ms=3.2, mfc=C_PASSOU, mec="white", mew=0.4,
                                label="Scar edge crossed by later fire")],
                loc="outside lower center", ncol=2, fontsize=tam(5.8), handlelength=1.2, columnspacing=1.4)
    rotulo_painel(axs[0, 0], "a")

    axb, axc = sf_g.subplots(1, 2, width_ratios=[1, 1.15])
    rg, rv = R["B08a_regra_antiga_x_simetrica"], R["B09_cicatriz_vs_referencia"]
    if rg is not None:
        g = _regra_sim(rg)
        for xi, (t, cor) in enumerate([("cicatriz", C_INI), ("referencia", "#8f8e88")]):
            v = g.loc[t, "% interrupcao"]; n = int(g.loc[t, "interrupcao"] + g.loc[t, "continuidade"])
            axb.bar(xi, v, width=0.62, color=cor, zorder=2)
            axb.text(xi, v + 2, f"{v:.1f}%", ha="center", va="bottom", fontsize=tam(6.4), fontweight="bold", color=cor)
            axb.text(xi, -4, f"n = {n:,}", ha="center", va="top", fontsize=tam(5.2), color=MUDO)
        axb.set_xticks([0, 1]); axb.set_xticklabels(["Early-scar\nedges", "Reference\nedges"], fontsize=tam(6.0))
        axb.tick_params(axis="x", length=0, pad=12)
        axb.set_ylim(0, 112); axb.set_yticks([0, 50, 100]); axb.set_ylabel("Arriving fires stopped (%)")
        axb.grid(axis="x", visible=False)
    if rv is not None:
        r_ = rv[(rv["combustivel"] == FUEL_MAIN) & REGRA_OK(rv["regra"])]
        if len(r_):
            r_ = r_.iloc[0]
            axb.set_title(f"adjusted OR {r_['razao_chances_cicatriz']:.0f} ({r_['ic95_inf']:.0f}–{r_['ic95_sup']:.0f})",
                          fontsize=tam(5.8), color=MUDO, loc="left", pad=2)
    rotulo_painel(axb, "b")
    per = (segs[segs["resultado"].isin(["interrupcao", "continuidade"])]
           .assign(i=lambda x: x["resultado"] == "interrupcao").groupby(["ti_id", "tipo_seg"])["i"].mean().unstack())
    tl = ORDER8["ti_id"].astype(int).tolist()[::-1]
    for yi, t in enumerate(tl):
        if t not in per.index:
            continue
        s, r_ = 100 * per.loc[t].get("cicatriz", np.nan), 100 * per.loc[t].get("referencia", np.nan)
        axc.plot([r_, s], [yi, yi], color="#cfcec7", lw=2.2, zorder=1, solid_capstyle="round")
        axc.scatter(r_, yi, s=24, color="#8f8e88", edgecolor="white", lw=0.5, zorder=3)
        axc.scatter(s, yi, s=28, color=C_INI, edgecolor="white", lw=0.5, zorder=3)
    axc.set_yticks(range(len(tl))); axc.set_yticklabels([f"{NUM[t]} {TI_NAME[t]}" for t in tl], fontsize=tam(5.6))
    axc.set_xlim(-3, 103); axc.set_xticks([0, 50, 100]); axc.set_xlabel("Arriving fires stopped (%)", fontsize=tam(6.0))
    axc.grid(axis="y", visible=False); axc.tick_params(axis="y", length=0)
    axc.set_title("each IL: reference (grey) vs early-scar edges (blue)", fontsize=tam(5.6), color=MUDO, loc="left", pad=2)
    rotulo_painel(axc, "c")
    salvar(fig, "Fig2_edge_test")

# ============================================================
# FIGURA 3 - CONFIGURACAO ALEM DA QUANTIDADE
# ============================================================
BINS_AREA, LAB_AREA = [1, 10, 100, 1000, np.inf], ["1–10", "10–100", "100–1000", "> 1000"]
BINS_LARG, LAB_LARG = [0, 150, 300, 600, np.inf], ["< 150", "150–300", "300–600", "> 600"]

def taxa_por_faixa(col, bins, labs):
    d = _d_ok.dropna(subset=[col]).copy()
    d["faixa"] = pd.cut(d[col], bins, labels=labs, right=False)
    g = d.groupby("faixa", observed=False)["resultado"].agg(n="size", p=lambda r: (r == "interrupcao").mean())
    g["ep"] = np.sqrt(g["p"] * (1 - g["p"]) / g["n"].clip(lower=1))
    return g

def fig3():
    fig = plt.figure(figsize=(LARG, 14.0 * CM), layout="constrained")
    sf_m, sf_g = fig.subfigures(2, 1, height_ratios=[1.45, 1], hspace=0.04)
    norm_a = mpl.colors.LogNorm(1, 1000)

    def desenhar(ax, ti):
        m = MAPAS.get(ti)
        if m is None:
            return
        e = m["ext"]
        _img(ax, np.ma.masked_where(m["seq"] != 2, np.ones(m["seq"].shape)), e, cmap=ListedColormap(["#f9c9a2"]), vmin=0, vmax=1)
        _img(ax, np.ma.masked_less_equal(m["area"], 0), e, cmap=CMAP_AREA2, norm=norm_a)
        dd = _d_ok[(_d_ok["ti_id"] == ti) & (_d_ok["year"] == REP.get(ti)) & (_d_ok["resultado"] == "continuidade")]
        ax.scatter(dd["x"], dd["y"], s=6, color=C_PASSOU, edgecolor="white", lw=0.3, zorder=5)
    axs = grade_tis(sf_m, desenhar, info=lambda ti: f"{REP.get(ti)}")
    cb = sf_m.colorbar(mpl.cm.ScalarMappable(norm=norm_a, cmap=CMAP_AREA2), ax=axs, location="bottom",
                       shrink=0.36, aspect=30, pad=0.03)
    cb.set_ticks([1, 10, 100, 1000]); cb.set_ticklabels(["1", "10", "100", "1000"])
    cb.set_label("Size of each early scar (ha)", fontsize=tam(5.8))
    cb.outline.set_linewidth(0.4); cb.ax.tick_params(labelsize=tam(5.4), width=0.4, length=1.5)
    sf_m.legend(handles=[mpatches.Patch(color="#f9c9a2", label="Burned Aug–Oct"),
                         Line2D([], [], marker="o", ls="", ms=3.4, mfc=C_PASSOU, mec="white", mew=0.4,
                                label="Scar edge crossed by later fire")],
                loc="outside lower center", ncol=2, fontsize=tam(5.8), handlelength=1.2, columnspacing=1.4)
    rotulo_painel(axs[0, 0], "a")

    axb, axc, axd = sf_g.subplots(1, 3, width_ratios=[1, 1, 1.15])
    for ax, (col, bins, labs, xl, letra) in zip([axb, axc], [("area_cicatriz_ha", BINS_AREA, LAB_AREA, "Early-scar size (ha)", "b"),
                                                             ("largura_local_m", BINS_LARG, LAB_LARG, "Local scar width (m)", "c")]):
        g = taxa_por_faixa(col, bins, labs)
        x = np.arange(len(g)); cores = [CMAP_AREA2(v) for v in np.linspace(0.3, 1.0, len(g))]
        ax.bar(x, 100 * g["p"], width=0.66, color=cores, zorder=2)
        ax.errorbar(x, 100 * g["p"], yerr=196 * g["ep"], fmt="none", ecolor=TINTA, elinewidth=0.7, capsize=1.5)
        for xi, (_, r) in zip(x, g.iterrows()):
            if r["n"]:
                ax.text(xi, 100 * r["p"] + 196 * r["ep"] + 0.25, f"{100 * r['p']:.1f}", ha="center", va="bottom",
                        fontsize=tam(5.6), color=TINTA)
        lo = max(0, np.floor(100 * (g["p"] - 2.2 * g["ep"]).min() / 2) * 2 - 2)
        ax.set_ylim(lo, 100.8)
        ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=tam(5.6))
        ax.tick_params(axis="x", length=0); ax.grid(axis="x", visible=False)
        ax.yaxis.set_major_locator(MaxNLocator(4)); ax.set_xlabel(xl, fontsize=tam(6.0))
        rotulo_painel(ax, letra)
    axb.set_ylabel("Arriving fires stopped (%)", fontsize=tam(6.0))
    sc = R["B09_segmento_coeficientes"]
    lab = {"log_area_cicatriz": "Scar size", "largura_local_100m": "Scar width",
           "conf_split_win": "Fragmentation", "conf_lpi_win": "Largest patch"}
    if sc is not None:
        k = sc[(sc["combustivel"] == FUEL_MAIN) & (sc["modelo"] == "segmento | config")]
        vars_ = [v for v in lab if v in k.index]; y = np.arange(len(vars_))[::-1].astype(float)
        axd.axvline(1.0, color=TINTA2, lw=0.7, ls=(0, (3, 2)), zorder=1)
        his = []
        for yi, v in zip(y, vars_):
            e = k.loc[v]; sig = e["ic95_inf"] > 1 or e["ic95_sup"] < 1
            cor = C_INI if sig else "#9a9992"
            axd.plot([e["ic95_inf"], e["ic95_sup"]], [yi, yi], color=cor, lw=2.0, solid_capstyle="round", zorder=2)
            axd.scatter(e["razao_chances_1dp"], yi, s=34, color=cor if sig else "white", edgecolor="white" if sig else cor,
                        lw=0.6 if sig else 1.0, zorder=3)
            axd.text(e["ic95_sup"] * 1.05, yi, f"{e['razao_chances_1dp']:.2f}", fontsize=tam(5.8), color=cor,
                     va="center", fontweight="bold" if sig else "normal")
            his.append(e["ic95_sup"])
        axd.set_xscale("log"); axd.set_xlim(0.65, max(his) * 1.55)
        axd.xaxis.set_major_locator(FixedLocator([0.75, 1, 1.5, 2, 3])); axd.xaxis.set_minor_locator(NullLocator())
        axd.xaxis.set_major_formatter(FormatStrFormatter("%g"))
        axd.set_yticks(y); axd.set_yticklabels([lab[v] for v in vars_], fontsize=tam(5.8))
        axd.set_ylim(-0.6, len(vars_) - 0.4)
        axd.grid(axis="y", visible=False); axd.tick_params(axis="y", length=0)
        axd.set_xlabel("Odds of stopping per SD,\nbeyond quantity", fontsize=tam(6.0))
    rotulo_painel(axd, "d")
    salvar(fig, "Fig3_configuration")

# ============================================================
# FIGURA 4 - GENERALIZACAO
# ============================================================
def fig4():
    fig = plt.figure(figsize=(LARG, 13.8 * CM), layout="constrained")
    sf_m, sf_g = fig.subfigures(2, 1, height_ratios=[1.45, 1], hspace=0.04)
    d = _d_ok.copy()
    d["x"] = np.floor(d["x"] / CELL_M) * CELL_M + CELL_M / 2
    d["y"] = np.floor(d["y"] / CELL_M) * CELL_M + CELL_M / 2
    gcell = (d.groupby(["ti_id", "x", "y"]).agg(n=("resultado", "size"),
             rate=("resultado", lambda r: 100 * (r == "interrupcao").mean())).reset_index())
    gcell = gcell[gcell["n"] >= 10]
    lo = float(np.floor(gcell["rate"].quantile(0.02) / 5) * 5) if len(gcell) else 80
    norm = mpl.colors.Normalize(lo, 100)

    def desenhar(ax, ti):
        g = gcell[gcell["ti_id"] == ti]
        if not len(g):
            return
        h = CELL_M / 2
        gg = gpd.GeoDataFrame(g[["rate"]], geometry=[_box(x - h, y - h, x + h, y + h) for x, y in zip(g["x"], g["y"])],
                              crs=AREA_CRS)
        gg.plot(ax=ax, column="rate", cmap=CMAP_PASSA, norm=norm, edgecolor="white", linewidth=0.15, zorder=2)
    axs = grade_tis(sf_m, desenhar)
    cb = sf_m.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=CMAP_PASSA), ax=axs, location="bottom",
                       shrink=0.42, aspect=34, pad=0.03, extend="min" if gcell["rate"].min() < lo else "neither")
    cb.set_label(f"Arriving fires stopped at early-scar edges (%), {CELL_M / 1000:.0f}-km cells, {YEARS[0]}–{YEARS[-1]}",
                 fontsize=tam(5.8))
    cb.outline.set_linewidth(0.4); cb.ax.tick_params(labelsize=tam(5.4), width=0.4, length=1.5)
    rotulo_painel(axs[0, 0], "a")

    axb, axc = sf_g.subplots(1, 2, width_ratios=[1, 1.25])
    tl = ORDER8["ti_id"].astype(int).tolist()
    for xi, t in enumerate(tl):
        v = gcell.loc[gcell["ti_id"] == t, "rate"].to_numpy()
        if not len(v):
            continue
        jit = (np.random.default_rng(t).random(len(v)) - 0.5) * 0.5
        axb.scatter(xi + jit, v, s=5, c=CMAP_PASSA(norm(v)), lw=0, alpha=0.85, zorder=2, rasterized=True)
        axb.plot([xi - 0.3, xi + 0.3], [np.median(v)] * 2, color=TINTA, lw=1.2, zorder=3)
    axb.set_xticks(range(len(tl))); axb.set_xticklabels([str(NUM[t]) for t in tl], fontsize=tam(5.8))
    axb.tick_params(axis="x", length=0); axb.grid(axis="x", visible=False)
    axb.set_ylim(max(lo - 3, 0), 101); axb.yaxis.set_major_locator(MaxNLocator(4))
    axb.set_xlabel("IL (numbers as in a)", fontsize=tam(6.0)); axb.set_ylabel("Stopped (%), per cell", fontsize=tam(6.0))
    rotulo_painel(axb, "b")
    rob = R["B10_robustez_segmentos"]
    grupos = [("Seasonal split", ["artigo1", "local", "local_100"], ["Article 1", "Local, 60 mm", "Local, 100 mm"]),
              ("Encounter criteria", ["segmento 150 m", "segmento 600 m", "faixa 60 m", "faixa 150 m",
                                      "chegada >= 20%", "chegada >= 50%"],
               ["Segment 150 m", "Segment 600 m", "Strip 60 m", "Strip 150 m", "Arrival ≥ 20%", "Arrival ≥ 50%"]),
              ("Fuel", ["nativa+pastagem", "nativa"], ["Natural + pasture", "Natural only"])]
    if rob is not None and len(rob):
        rb = rob.drop_duplicates("variante").set_index("variante")
        y = 0.0; ticks, labs = [], []
        axc.axvline(1.0, color=TINTA2, lw=0.7, ls=(0, (3, 2)), zorder=1)
        if "padrao" in rb.index:
            axc.axvspan(rb.loc["padrao", "ic_inf"], rb.loc["padrao", "ic_sup"], color=C_INI, alpha=0.10, lw=0, zorder=0)
        for gname, keys, names in grupos[::-1]:
            ks = [(k, n) for k, n in zip(keys, names) if k in rb.index]
            for k, n in ks[::-1]:
                r = rb.loc[k]; sig = r["ic_inf"] > 1 or r["ic_sup"] < 1; cor = C_INI if sig else "#9a9992"
                axc.plot([r["ic_inf"], r["ic_sup"]], [y, y], color=cor, lw=1.6, solid_capstyle="round", zorder=2)
                axc.scatter(r["rc_conf_split"], y, s=20, color=cor, edgecolor="white", lw=0.5, zorder=3)
                ticks.append(y); labs.append(n); y += 1
            axc.text(1.0, y - 0.35, gname, transform=mpl.transforms.blended_transform_factory(axc.transAxes, axc.transData),
                     ha="right", va="bottom", fontsize=tam(5.4), fontstyle="italic", color=MUDO)
            y += 0.9
        axc.set_yticks(ticks); axc.set_yticklabels(labs, fontsize=tam(5.4))
        axc.set_ylim(-0.7, y - 0.4)
        axc.grid(axis="y", visible=False); axc.tick_params(axis="y", length=0)
        axc.set_xlabel("Odds ratio, window fragmentation (band = default)", fontsize=tam(6.0))
    rotulo_painel(axc, "c")
    salvar(fig, "Fig4_generalisation")

# ============================================================
# FIGURA S2 - TIPOLOGIA DESCRITIVA
# ============================================================
def figS2():
    fig = plt.figure(figsize=(LARG, 6.4 * CM), layout="constrained")
    gs = fig.add_gridspec(1, 3)
    rows = ["Early, large", "Early, small & weak", "Early, small & intense", "Late season"]
    ypos = np.array([3.4, 2.4, 1.4, 0.0])
    axes = [fig.add_subplot(gs[0])]
    axes += [fig.add_subplot(gs[k], sharey=axes[0]) for k in (1, 2)]
    tp, d1, d2t = R["B06_tipologia_resumo"], R["D1_tempo"], R["D2_foco_noturno_taxa"]
    if tp is not None:
        t = tp.copy(); t.index = [TYPE_EN.get(i, i) for i in t.index]
        v = [t.loc[k, "area_ha"] / 1e6 for k in rows]
        axes[0].scatter(v, ypos, s=26, color=[TYPE_COL[k] for k in rows], edgecolor="white", lw=0.6, zorder=3)
        dot_labels(axes[0], v, ypos + 0.42, [f"{x:.2f}" if x >= 0.01 else f"{x:.3f}" for x in v], 0, ha="center", fs=5.4)
        axes[0].set_xscale("log"); axes[0].set_xlim(5e-4, 40)
        axes[0].xaxis.set_major_locator(FixedLocator([0.001, 0.1, 10])); axes[0].xaxis.set_minor_locator(NullLocator())
        axes[0].xaxis.set_major_formatter(FormatStrFormatter("%g"))
    axes[0].set_xlabel("Burned area (Mha)", fontsize=tam(6.2))
    if d1 is not None:
        v = d1[d1["variavel"] == "P_vpd_max"].copy(); v["lab"] = v["tipo"].map(TYPE_EN); v = v.set_index("lab")
        rr = [k for k in rows if k in v.index]
        m = [v.loc[k, "media_percentil"] for k in rr]; yy = [ypos[rows.index(k)] for k in rr]
        axes[1].axvline(0.5, color=MUDO, lw=0.6, ls=(0, (3, 2)), zorder=1)
        for k, yi in zip(rr, yy):
            axes[1].plot([v.loc[k, "ic95_inf"], v.loc[k, "ic95_sup"]], [yi, yi], color=TYPE_COL[k], lw=1.3, alpha=0.85,
                         solid_capstyle="round", zorder=2)
        axes[1].scatter(m, yy, s=26, color=[TYPE_COL[k] for k in rr], edgecolor="white", lw=0.6, zorder=3)
        dot_labels(axes[1], m, np.array(yy) + 0.42, [f"{x:.2f}" for x in m], 0, ha="center", fs=5.4)
        axes[1].set_xlim(0.40, 0.80)
    axes[1].set_xlabel("VPD percentile, 1st MODIS detection", fontsize=tam(6.2))
    if d2t is not None:
        t = d2t.copy(); t.index = [TYPE_EN.get(i, i) for i in t.index]
        rr = [k for k in rows if k in t.index]
        v = [100 * t.loc[k, "mean"] for k in rr]; yy = [ypos[rows.index(k)] for k in rr]
        axes[2].scatter(v, yy, s=26, color=[TYPE_COL[k] for k in rr], edgecolor="white", lw=0.6, zorder=3)
        dot_labels(axes[2], v, np.array(yy) + 0.42, [f"{x:.0f}%" for x in v], 0, ha="center", fs=5.4)
        axes[2].set_xlim(-3, max(v) * 1.3 if v else 10); axes[2].xaxis.set_major_locator(MaxNLocator(3, integer=True))
    axes[2].set_xlabel("Night-time MODIS detections (%)", fontsize=tam(6.2))
    for k_, ax in enumerate(axes):
        ax.axhline(0.7, color=EIXO, lw=0.5, ls=(0, (2, 2)))
        ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0, labelleft=(k_ == 0))
        rotulo_painel(ax, "abc"[k_])
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(["Early, large", "Early, small\n& weak", "Early, small\n& intense", "Late season"],
                            fontsize=tam(6.0), linespacing=1.0)
    axes[0].set_ylim(-0.5, 4.0)
    salvar(fig, "FigS2_scar_types")

# ============================================================
# FIGURA S3 - JANELA DE 12 km A 30 m
# ============================================================
def figS3():
    fig = plt.figure(figsize=(LARG, 9.4 * CM), layout="constrained")
    sf_m, sf_d = fig.subfigures(2, 1, height_ratios=[1.62, 0.62], hspace=0.0)
    ti, yr, win = W
    e = JNBR["ext"]; ext_img = (e[0], e[1], e[2], e[3])
    early = np.isin(JNBR["month"], EARLY)
    dd = segs[(segs["ti_id"] == ti) & (segs["year"] == yr) & (segs["tipo_seg"] == "cicatriz") &
              segs["x"].between(win[0], win[2]) & segs["y"].between(win[1], win[3]) &
              segs["resultado"].isin(["interrupcao", "continuidade"])]
    norm_nbr = mpl.colors.TwoSlopeNorm(vmin=-0.3, vcenter=0.15, vmax=0.6)
    norm_d = mpl.colors.Normalize(0, 0.6)
    axs = list(sf_m.subplots(1, 3))
    titulos = [f"NBR, July {yr}", f"NBR, min. Aug–Oct {yr}", "dNBR, July − (Aug–Oct)"]
    pre = np.ma.masked_less(JNBR["pre"], -100) / 100.0
    post = np.ma.masked_less(JNBR["post"], -100) / 100.0
    for k, ax in enumerate(axs):
        ax.add_patch(mpatches.Rectangle(win[:2], win[2] - win[0], win[3] - win[1], color=SEM_DADO, zorder=0))
        if k == 0:
            im_n = ax.imshow(pre, extent=ext_img, cmap=CMAP_NBR, norm=norm_nbr, interpolation="nearest", zorder=1, rasterized=True)
        elif k == 1:
            ax.imshow(post, extent=ext_img, cmap=CMAP_NBR, norm=norm_nbr, interpolation="nearest", zorder=1, rasterized=True)
        else:
            im_d = ax.imshow(np.ma.clip(pre - post, -0.1, 0.8), extent=ext_img, cmap=CMAP_DNBR, norm=norm_d,
                             interpolation="nearest", zorder=1, rasterized=True)
        if early.any():
            ax.contour(np.flipud(early.astype(float)), levels=[0.5], colors=[AZUL], linewidths=0.45, extent=ext_img, zorder=3)
        if k == 2 and len(dd):
            q = dd[dd["resultado"] == "continuidade"]
            ax.scatter(q["x"], q["y"], s=11, color="#d63aa8", edgecolor="white", lw=0.5, zorder=5)
        ti_geom(ti).boundary.plot(ax=ax, color=TINTA, lw=0.5, zorder=4)
        moldura(ax, win, barra_m=2000 if k == 0 else None, seta=(k == 2), fs=5)
        ax.set_title(titulos[k], fontsize=tam(6.4), pad=2, loc="center")
        rotulo_painel(ax, "abc"[k])
    colorbar_fina(sf_m, im_n, axs[:2], "Landsat 8/9 NBR (grey: > 500 m from any burn)", ticks=[-0.3, 0, 0.15, 0.3, 0.6], shrink=0.7)
    colorbar_fina(sf_m, im_d, axs[2], "dNBR", ticks=[0, 0.2, 0.4, 0.6], extend="max", shrink=0.9)
    if len(dd):
        pi = 100 * (dd["resultado"] == "interrupcao").mean()
        axs[2].text(0.02, 0.98, f"{len(dd):,} edges reached\n{pi:.0f}% interrupted", transform=axs[2].transAxes,
                    ha="left", va="top", fontsize=tam(5.6), color=TINTA, linespacing=1.15, path_effects=HALO, zorder=9)
    sf_m.legend(handles=[Line2D([], [], color=AZUL, lw=0.9, label="Early-scar outline (May–Jul)"),
                         Line2D([], [], marker="o", ls="", ms=3.4, mfc="#d63aa8", mec="white", mew=0.5,
                                label="Scar edge crossed by later fire")],
                loc="outside lower center", ncol=2, fontsize=tam(5.8), handlelength=1.2, columnspacing=1.2)
    ax = sf_d.subplots()
    rg = R["B08a_regra_antiga_x_simetrica"]
    if rg is not None:
        g = _regra_sim(rg)
        nomes = [("cicatriz", "Early-scar edges", AZUL), ("referencia", "Reference edges (no earlier burn)", MUDO)]
        for yi, (t, lab, cor) in zip([1, 0], nomes):
            v = g.loc[t, "% interrupcao"]; n = int(g.loc[t, "interrupcao"] + g.loc[t, "continuidade"])
            ax.barh(yi, v, height=0.5, color=cor, alpha=0.9, zorder=2)
            ax.text(v + 1.2 if v < 85 else v - 1.2, yi, f"{v:.1f}%  (n = {n:,})", fontsize=tam(5.8),
                    color=TINTA if v < 85 else "white", ha="left" if v < 85 else "right", va="center", zorder=3)
        ax.set_yticks([1, 0]); ax.set_yticklabels([n[1] for n in nomes], fontsize=tam(6.2))
        ax.set_ylim(-0.5, 1.5); ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100])
        ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
        ax.set_xlabel(f"Arriving fires interrupted (%), {len(ORDER8)} ILs, {YEARS[0]}–{YEARS[-1]}", fontsize=tam(6.2))
    rotulo_painel(ax, "d")
    salvar(fig, "FigS3_window_landsat")

# ============================================================
# TABELA 1
# ============================================================
def table1():
    rows = []
    for ti in ORDER8["ti_id"].astype(int):
        r = {"#": NUM.get(ti), "IL": TI_NAME.get(ti, ti)}
        a = tis.loc[tis["ti_id"].astype(int) == ti, "area_ha"]
        r["Area (km²)"] = int(round(float(a.iloc[0]) / 100)) if len(a) else np.nan
        aa = area_anual[area_anual["ti_id"] == ti]
        if len(aa):
            r["Early burned (% yr⁻¹)"] = round(100 * (aa["early_ha"] / aa["ti_ha"]).mean(), 1)
            r["Late burned (% yr⁻¹)"] = round(100 * (aa["late_ha"] / aa["ti_ha"]).mean(), 1)
        g = segs[segs["ti_id"] == ti]
        for t, nome in [("cicatriz", "scar"), ("referencia", "reference")]:
            q = g[(g["tipo_seg"] == t) & g["resultado"].isin(["interrupcao", "continuidade"])]
            if t == "cicatriz":
                r["Scar edges with arrival"] = len(q)
            r[f"Interrupted, {nome} edges (%)"] = round(100 * (q["resultado"] == "interrupcao").mean(), 1) if len(q) else np.nan
        if art1 is not None:
            cod = tis.loc[tis["ti_id"].astype(int) == ti, "terrai_cod"]
            a1 = art1[art1["terrai_cod"] == int(cod.iloc[0])] if len(cod) else art1.iloc[0:0]
            r["Article-1 class"] = a1["classe"].iloc[0] if len(a1) else ""
            r["FRRI"] = round(float(a1["frri"].iloc[0]), 2) if len(a1) and pd.notna(a1["frri"].iloc[0]) else np.nan
        rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(FIG_DIR / "Table1_analysed_ILs.csv", index=False)
    display(t)
    return t

CAP = {
    "Fig1_premise": "Figure 1. Early dry-season scars and their timing. (a) Dominant burn season of each 30-m pixel in "
                    f"the analysed Indigenous Lands (ILs), {YEARS[0]}–{YEARS[-1]} (MapBiomas Fire). (b) Annual burned area "
                    "in May–July and August–October. (c) Monthly minimum Landsat 8/9 NBR of pixels burned early, burned "
                    "later and unburned (median and interquartile range; NBR within 500 m of burns).",
    "Fig2_edge_test": "Figure 2. Do early scars stop arriving fire? (a) Each IL in the year with most scar edges reached by "
                      "later fire: Landsat dNBR between July and the August–October minimum, early-scar outlines and 300-m "
                      "scar edges crossed by later fire (magenta). (b) Arriving fires stopped at early-scar and reference "
                      "edges with the same Landsat + MODIS entry rule, and the adjusted odds ratio. (c) The same in each IL.",
    "Fig3_configuration": "Figure 3. Configuration beyond quantity. (a) Early scars coloured by size, later fire and crossed "
                          "edges. (b, c) Share of arriving fires stopped by early-scar size and local width (95% binomial "
                          "interval). (d) Odds ratios of stopping per SD beyond the reference model with quantity (SE "
                          "clustered by fire and IL; open symbol, CI includes 1).",
    "Fig4_generalisation": f"Figure 4. Generalisation. (a) Share of arriving fires stopped at early-scar edges in "
                           f"{CELL_M / 1000:.0f}-km cells (>= 10 edges). (b) Distribution of the cells in each IL (bar, "
                           "median). (c) Odds ratio for window fragmentation under alternative seasonal splits, encounter "
                           "criteria and fuel definitions, one change at a time (95% CI; band, default model).",
    "FigS2_scar_types": "Figure S2. Descriptive types of early dry-season scars (>= 1 ha): (a) burned area; (b) mean VPD "
                        "percentile on the day of the first MODIS detection (ERA5-Land; IL-bootstrap 95% CI); (c) share of "
                        "scars with night-time MODIS detections. Types are not attributed to management or brigades.",
    "FigS3_window_landsat": f"Figure S3. Detail at 30 m: a 12 × 12 km window of {TI_NAME.get(W[0])}, {W[1]}. (a–c) Landsat "
                            "8/9 NBR in July, minimum NBR of August–October and dNBR, with early-scar outlines and crossed "
                            "edges. (d) Share of arriving fires stopped at early-scar and reference edges, all ILs.",
}

console.print("[bold cyan]-- Figuras da letter --[/bold cyan]")
for fn in [fig1, fig2, fig3, fig4, figS2, figS3]:
    try:
        fn()
    except Exception as e:
        console.print(f"[yellow]{fn.__name__} pulada: {str(e)[:160]}[/yellow]")
t1 = table1()

d = docx.Document()
d.styles["Normal"].font.name = "Times New Roman"; d.styles["Normal"].font.size = Pt(10)
d.add_heading("Figures and Table – early-burn configuration and fire continuity", 1)
for name, cap in CAP.items():
    png = FIG_DIR / f"{name}.png"
    if png.exists():
        d.add_picture(str(png), width=DocxCm(LARGURA_CM))
        d.add_paragraph(cap)
d.add_paragraph("Table 1. Analysed Indigenous Lands (numbers as in Fig. 1): area in the Cerrado, mean annual share burned "
                f"in May–July and August–October ({YEARS[0]}–{YEARS[-1]}), early-scar edges reached by later fire with a "
                "defined outcome, share interrupted at scar and reference edges (same Landsat + MODIS rule), and the class "
                "and FRRI of our first article.")
tb = d.add_table(rows=1, cols=len(t1.columns)); tb.style = "Light Grid Accent 1"
for j, c in enumerate(t1.columns):
    tb.rows[0].cells[j].text = str(c)
for row in t1.itertuples(index=False):
    cl_ = tb.add_row().cells
    for j, x in enumerate(row):
        cl_[j].text = "" if (isinstance(x, float) and np.isnan(x)) else (f"{x:,}" if isinstance(x, (int, np.integer)) else str(x))
d.save(TXT_DIR / "RSL_figuras_tabela.docx")
console.print(f"[bold green]OK BLOCO 16 completo: figuras em {FIG_DIR}.[/bold green]")
