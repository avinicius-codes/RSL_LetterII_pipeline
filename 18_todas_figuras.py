# ======================================================================
# BLOCO 18 - TODAS AS FIGURAS DO PROJETO, num bloco so (600 dpi TIFF LZW + PDF vetorial + PNG)
# Depende so do bloco 00 e dos resultados ja gravados pelos blocos 01-14. Nao recalcula analises.
# Cada figura roda isolada: se faltar um insumo, so ela e pulada (aviso amarelo).
#
#   Letter     Fig1 premissa | Fig2 o teste | Fig3 configuracao | Fig4 generalizacao   (eram do bloco 16)
#   Sensoriam. FigR1 area e triagem | FigR2 encontro Landsat+MODIS | FigR3 teste MODIS | FigR4 SES  (bloco 17)
#   Suplem.    FigS2 tipologia (07) | FigS3 janela 30 m (16) | FigS4 estacao seca (06) | FigS5 MODIS x
#              cicatrizes (05) | FigS6 detectabilidade (11) | FigS7 inferencia 8 TIs (13) | FigS8 modelo
#              nulo x quantidade (09) | FigS9 resultado dos segmentos (10)
#   + Tabela 1 e 08_textos/RSL_figuras_tabela.docx (figuras + legendas)
# Saida: 05_figures/letter/
# ======================================================================

# Confere se o 00_configuracao.py DESTA pasta (RSL - LETTER II) rodou nesta sessao
if globals().get("BLOCKS_VERSION") != "2026-10-17-final" or "TAG_SEG" not in globals():
    raise RuntimeError(
        "O 00_configuracao.py da pasta RSL - LETTER II nao foi rodado nesta sessao "
        f"(versao carregada: {globals().get('BLOCKS_VERSION')}). "
        "Faca: Ambiente de execucao > Reiniciar sessao; rode o 00_configuracao.py; depois rode este bloco 18.")

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
    for i, (x, y, l_) in enumerate(fixos):            # letras da mesma linha na mesma altura
        mesma = [yy for _, yy, _ in fixos if abs(yy - y) < 0.12]
        fixos[i] = (x, max(mesma), l_)
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

from matplotlib.offsetbox import AnchoredOffsetbox, AuxTransformBox, DrawingArea, HPacker, TextArea, VPacker

FS_MAPA = 5.2          # mesmo tamanho de texto de escala e norte em todos os mapas

def _caixa(ax, filho, canto):
    ab = AnchoredOffsetbox(loc=canto, child=filho, pad=0.25, borderpad=0.35, frameon=True)
    ab.patch.set_boxstyle("round,pad=0.12")
    ab.patch.set_facecolor("white"); ab.patch.set_edgecolor("none"); ab.patch.set_alpha(0.88)
    ab.set_zorder(9)
    ax.add_artist(ab)

def moldura(ax, ext, barra_m=None, seta=True, canto_barra="lower left", canto_seta="lower right", **_):
    """Padrao de todos os mapas: barra de escala no canto inferior esquerdo, com o rotulo AO LADO da barra,
    e seta de norte no canto inferior direito, ambas numa caixa branca (nunca sobre texto ou outra marca)."""
    fs = tam(FS_MAPA)
    ax.set_xlim(ext[0], ext[2]); ax.set_ylim(ext[1], ext[3])
    ax.set_aspect("equal")
    if not getattr(ax, "_grat", False):
        ax.set_axis_off()
    h = ext[3] - ext[1]
    if barra_m:
        th = 0.018 * h
        bar = AuxTransformBox(ax.transData)
        bar.add_artist(mpatches.Rectangle((0, 0), barra_m / 2, th, fc=TINTA, ec=TINTA, lw=0.4))
        bar.add_artist(mpatches.Rectangle((barra_m / 2, 0), barra_m / 2, th, fc="white", ec=TINTA, lw=0.4))
        rot = f"{barra_m / 1000:g} km" if barra_m >= 1000 else f"{barra_m:g} m"
        txt = TextArea(rot, textprops=dict(fontsize=fs, color=TINTA))
        _caixa(ax, HPacker(children=[bar, txt], align="center", pad=0, sep=2.5), canto_barra)
    if seta:
        w_, h_ = fs * 0.75, fs * 1.25
        da = DrawingArea(w_, h_, 0, 0)
        da.add_artist(mpatches.Polygon([(w_ / 2, h_), (0, 0), (w_ / 2, 0.3 * h_)], closed=True, fc=TINTA, ec=TINTA, lw=0.4))
        da.add_artist(mpatches.Polygon([(w_ / 2, h_), (w_, 0), (w_ / 2, 0.3 * h_)], closed=True, fc="white", ec=TINTA, lw=0.4))
        n_ = TextArea("N", textprops=dict(fontsize=fs, fontweight="bold", color=TINTA))
        _caixa(ax, VPacker(children=[n_, da], align="center", pad=0, sep=0.6), canto_seta)

def titulo_mapa(ax, titulo, sub=None, negrito=False):
    """Padrao de titulo: sempre a esquerda; a informacao extra vai numa segunda linha, abaixo, cinza."""
    fs_t, fs_s = tam(5.8), tam(5.2)
    ax.set_title(titulo, fontsize=fs_t, loc="left", fontweight="bold" if negrito else "normal",
                 pad=(fs_s * 1.2 + 2.0) if sub else 2.0)
    if sub:
        ax.annotate(sub, xy=(0, 1), xycoords="axes fraction", xytext=(0, 1.2), textcoords="offset points",
                    ha="left", va="bottom", fontsize=fs_s, color=TINTA2, annotation_clip=False)

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
        H = max(bb[2] - bb[0], bb[3] - bb[1]) * 1.04
        S = H / 0.80                                   # 20% de baixo ficam livres para escala e norte
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        e = (cx - S / 2, cy - 0.6 * S, cx + S / 2, cy + 0.4 * S)
        moldura(ax, e, barra_m=barra_redonda(S), seta=True)
        titulo_mapa(ax, f"{NUM[ti]} {r['ti_name']}", info(ti) if info else None, negrito=True)
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

    _fim = []
    axc.axvspan(4.5, 7.5, color=C_INI, alpha=0.08, lw=0, zorder=0)
    axc.axvspan(7.5, 10.5, color=C_TAR, alpha=0.10, lw=0, zorder=0)
    for c, cor, lab in [("unburned", "#7d7c78", "Unburned"), ("late", C_TAR, "Burned\nAug–Oct"),
                        ("early", C_INI, "Burned\nMay–Jul")]:
        d = perfil_nbr[perfil_nbr["classe"] == c]
        if not len(d):
            continue
        axc.fill_between(d["mes"], d["p25"], d["p75"], color=cor, alpha=0.14, lw=0, zorder=1)
        axc.plot(d["mes"], d["p50"], color=cor, lw=1.8, marker="o", ms=3.2, mec="white", mew=0.5, zorder=3)
        _fim.append([d.iloc[-1]["p50"], lab, cor, d.iloc[-1]["mes"]])
    if _fim:
        _fim.sort(key=lambda z: z[0])
        ys = [z[0] for z in _fim]
        gap = 0.075 * (axc.get_ylim()[1] - axc.get_ylim()[0])
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + gap)
        for (y0, lab, cor, mx), yl in zip(_fim, ys):
            axc.annotate(lab.replace("\n", " "), (mx, y0), xytext=(mx + 0.25, yl), color=cor, fontsize=tam(5.6),
                         va="center", ha="left", arrowprops=dict(arrowstyle="-", color=cor, lw=0.4, shrinkA=0, shrinkB=2))
    axc.set_xticks(LS_MONTHS); axc.set_xticklabels(["A", "M", "J", "J", "A", "S", "O", "N"][:len(LS_MONTHS)])
    axc.set_xlim(LS_MONTHS[0] - 0.4, LS_MONTHS[-1] + 3.2); axc.spines["bottom"].set_bounds(LS_MONTHS[0], LS_MONTHS[-1])
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
            ax.contour(np.flipud(early), levels=[0.5], colors=[C_INI], linewidths=0.22, alpha=0.9, extent=(e[0], e[1], e[2], e[3]), zorder=4)
        dd = _d_ok[(_d_ok["ti_id"] == ti) & (_d_ok["year"] == REP.get(ti)) & (_d_ok["resultado"] == "continuidade")]
        ax.scatter(dd["x"], dd["y"], s=2.2, color=C_PASSOU, edgecolor="none", alpha=0.85, zorder=5)
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
BINS_AREA, LAB_AREA = [1, 10, 100, 1000, np.inf], ["1–10", "10–\n100", "100–\n1000", "> 1000"]
BINS_LARG, LAB_LARG = [0, 150, 300, 600, np.inf], ["< 150", "150–\n300", "300–\n600", "> 600"]

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
        ax.scatter(dd["x"], dd["y"], s=2.2, color=C_PASSOU, edgecolor="none", alpha=0.85, zorder=5)
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
        ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=tam(5.4), linespacing=0.95)
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
    grupos = [("Seasonal split", ["artigo1", "local", "local_100"], ["Dias et al. (2026)", "Local, 60 mm", "Local, 100 mm"]),
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
            ticks.append(y - 0.15); labs.append(gname.upper()); y += 1.1
        axc.set_yticks(ticks); axc.set_yticklabels(labs, fontsize=tam(5.4))
        for tl_ in axc.get_yticklabels():
            if tl_.get_text().isupper():
                tl_.set_fontsize(tam(4.8)); tl_.set_color(MUDO); tl_.set_fontweight("bold")
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
        moldura(ax, win, barra_m=2000, seta=True)
        titulo_mapa(ax, titulos[k])
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
            r["Dias et al. (2026) class"] = a1["classe"].iloc[0] if len(a1) else ""
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


# ============================================================
# FIGURAS DE SENSORIAMENTO (eram do bloco 17)
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
def graticule(ax, ext, step=None, labels=True, fs=5.2):
    """Linhas de lat/long (EPSG:5880) e rotulos FORA do quadro: longitude embaixo, latitude a esquerda."""
    x0, y0, x1, y1 = ext
    lons, lats = _to_ll.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    if step is None:
        span = max(lo1 - lo0, la1 - la0)
        step = next(s for s in [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10] if span / s <= 4)
    fmt = (lambda v, ew: f"{abs(v):.{0 if step >= 1 else (1 if step >= 0.1 else 2)}f}°{ew}")
    xt, xl, yt, yl = [], [], [], []
    for lo in np.arange(np.ceil(lo0 / step) * step, lo1, step):
        la = np.linspace(la0 - 1, la1 + 1, 200)
        xs, ys = _to_xy.transform(np.full_like(la, lo), la)
        ax.plot(xs, ys, color=GRAT, lw=0.3, zorder=1.5, clip_on=True)
        xb, _ = _to_xy.transform(lo, la0)
        if x0 < xb < x1:
            xt.append(xb); xl.append(fmt(lo, "W" if lo < 0 else "E"))
    for la in np.arange(np.ceil(la0 / step) * step, la1, step):
        lo = np.linspace(lo0 - 1, lo1 + 1, 200)
        xs, ys = _to_xy.transform(lo, np.full_like(lo, la))
        ax.plot(xs, ys, color=GRAT, lw=0.3, zorder=1.5, clip_on=True)
        _, yb = _to_xy.transform(lo0, la)
        if y0 < yb < y1:
            yt.append(yb); yl.append(fmt(la, "S" if la < 0 else "N"))
    ax._grat = True
    ax.grid(False)
    ax.set_xticks(xt); ax.set_xticklabels(xl if labels else [])
    ax.set_yticks(yt); ax.set_yticklabels(yl if labels else [], rotation=90, va="center")
    ax.tick_params(labelsize=tam(fs), length=1.8, width=0.4, pad=1.2, colors=TINTA2)
    for s in ax.spines.values():
        s.set_visible(True); s.set_linewidth(0.5); s.set_color(TINTA2)

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
    moldura(ax, ext, barra_m=500000, seta=True)
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
        graticule(ax, win)
        moldura(ax, win, barra_m=2000, seta=True)
        titulo_mapa(ax, titles[k])
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
    moldura(ax, ext, barra_m=barra_redonda(2 * h), seta=True)
    titulo_mapa(ax, TI_NAME.get(int(ex['ti_id'])), f"{int(ex['year'])}", negrito=True)
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
    graticule(axb, ext_l, step=5)
    moldura(axb, ext_l, barra_m=500000, seta=True)
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
# FIGURAS DOS OUTROS BLOCOS (refeitas no mesmo estilo, a partir do que ja foi gravado)
# ============================================================
from scipy import ndimage as _nd
SEASONS = load_seasons()
CORE_M, LOCAL_M = [1000, 1500], 5000          # mesmos valores do bloco 11

_fo_cache = {}
def _focos():
    if "fo" not in _fo_cache:
        fo = read_table(cache_path(FOCOS_NAME, "parquet"))
        fo = fo[fo["confidence"].astype(str).str[0] != "l"].copy()
        fo["acq_date"] = pd.to_datetime(fo["acq_date"])
        fo = fo.drop_duplicates(["latitude", "longitude", "acq_date"])
        x, y = _to_xy.transform(fo["longitude"].to_numpy(), fo["latitude"].to_numpy())
        fo["x"], fo["y"] = x, y
        fo["year"], fo["mes"] = fo["acq_date"].dt.year, fo["acq_date"].dt.month
        _fo_cache["fo"] = fo
    return _fo_cache["fo"]

def core_counts(ti, y, core_m, scheme=SEASON_MAIN, fuel_mode=FUEL_MAIN, keep_masks=False):
    """Mesma conta do bloco 11: focos MODIS do restante da seca nos nucleos de cicatriz x nao queimado."""
    fo = _focos()
    st, yr = static_of(ti), read_raster(ti, y)
    ini, res = SEASONS[scheme][int(ti)]
    inside = st["ti"] == ti
    queim = inside & fuel_from_cover(yr["cover"], fuel_mode) & (st["barrier"] == 0)
    sm_ = season_masks(yr["month"], ti, scheme, SEASONS)
    E = sm_["inicio"] & queim
    U = queim & ~sm_["antes"] & ~E
    k = core_m / PIX_M
    coreE = _nd.distance_transform_edt(E) > k
    coreU = _nd.distance_transform_edt(U) > k
    tr = st["_transform"]
    p = fo[(fo["ti_id"] == ti) & (fo["year"] == y) & fo["mes"].isin(res)]
    c_ = np.floor((p["x"].to_numpy() - tr.c) / PIX_M).astype(int)
    r_ = np.floor((tr.f - p["y"].to_numpy()) / PIX_M).astype(int)
    ok = (r_ >= 0) & (r_ < E.shape[0]) & (c_ >= 0) & (c_ < E.shape[1])
    out = {"ti_id": ti, "year": y, "core_m": core_m}
    if keep_masks:
        return out, dict(coreE=coreE, coreU=coreU, E=E, L=sm_["resto"] & inside, inside=inside, tr=tr,
                         pts=(p["x"].to_numpy()[ok], p["y"].to_numpy()[ok]))
    return out

# ---------- S4: estacao seca de cada TI (bloco 06) ----------
def figS4():
    pr = pd.read_csv(stats_path("chuva_mensal_por_ti"))
    fig = plt.figure(figsize=(LARG, 8.6 * CM), layout="constrained")
    axs = fig.subplots(2, 4, sharex=True, sharey=True)
    mes_lab = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    for ax, (_, r) in zip(axs.ravel(), ORDER8.iterrows()):
        ti = int(r["ti_id"])
        g = pr[pr["ti_id"] == ti].sort_values("mes")
        ini, res = SEASONS.get("local", SEASONS["artigo1"]).get(ti, (EARLY, LATE))
        cores = [C_INI if m in ini else C_TAR if m in res else "#cfcec7" for m in g["mes"]]
        ax.axvspan(4.5, 7.5, color=C_INI, alpha=0.07, lw=0); ax.axvspan(7.5, 10.5, color=C_TAR, alpha=0.08, lw=0)
        ax.bar(g["mes"], g["chuva_mm"], color=cores, width=0.75, zorder=2)
        ax.axhline(60, color=TINTA2, lw=0.6, ls=(0, (3, 2)), zorder=3)
        ax.set_title(f"{NUM[ti]} {r['ti_name']}", fontsize=tam(5.8), pad=1.5, loc="left", fontweight="bold")
        ax.set_xticks(range(1, 13)); ax.set_xticklabels(mes_lab, fontsize=tam(5))
        ax.grid(axis="x", visible=False); ax.tick_params(axis="x", length=0)
    for ax in axs[:, 0]:
        ax.set_ylabel("Rain (mm)", fontsize=tam(6))
    fig.legend(handles=[mpatches.Patch(color=C_INI, label="Local early dry season"),
                        mpatches.Patch(color=C_TAR, label="Local rest of dry season"),
                        Line2D([], [], color=TINTA2, lw=0.6, ls=(0, (3, 2)), label="60 mm"),
                        mpatches.Patch(color=C_INI, alpha=0.15, label="Dias et al. (2026): May–Jul | Aug–Oct")],
               loc="outside lower center", ncol=4, fontsize=tam(5.6), handlelength=1.2, columnspacing=1.0)
    rotulo_painel(axs[0, 0], "a")
    salvar(fig, "FigS4_dry_season_per_IL")

# ---------- S5: focos MODIS sobre as cicatrizes (bloco 05) ----------
def figS5():
    fo = _focos()
    scars = read_table(cache_path(SCARS_NAME, "gpkg"))
    fig = plt.figure(figsize=(LARG, 9.6 * CM), layout="constrained")

    def desenhar(ax, ti):
        yr = REP.get(ti)
        s = scars[(scars["ti_id"] == ti) & (scars["year"] == yr)]
        s[s["month"].isin(EARLY)].plot(ax=ax, color=C_INI, lw=0, zorder=2, rasterized=True)
        s[s["month"].isin(LATE)].plot(ax=ax, color=C_TAR, lw=0, zorder=2, rasterized=True)
        f = fo[(fo["ti_id"] == ti) & (fo["year"] == yr)]
        ax.scatter(f["x"], f["y"], s=1.6, color=np.where(f["mes"].isin(EARLY), "#0b2a66", VINHO), lw=0, zorder=4)
    axs = grade_tis(fig, desenhar, info=lambda ti: str(REP.get(ti, "")))
    fig.legend(handles=[mpatches.Patch(color=C_INI, label="Scar May–Jul (MapBiomas)"),
                        mpatches.Patch(color=C_TAR, label="Scar Aug–Oct (MapBiomas)"),
                        Line2D([], [], marker="o", ls="", ms=2.4, color="#0b2a66", label="MODIS fire pixel, May–Jul"),
                        Line2D([], [], marker="o", ls="", ms=2.4, color=VINHO, label="MODIS fire pixel, Aug–Oct")],
               loc="outside lower center", ncol=4, fontsize=tam(5.6), handlelength=1.0, columnspacing=1.0)
    rotulo_painel(axs[0, 0], "a")
    salvar(fig, "FigS5_modis_over_scars")

# ---------- S6: detectabilidade (bloco 11) ----------
def figS6():
    curva = pd.read_csv(stats_path("B08b_curva_limiar"))
    sens = pd.read_csv(stats_path("B08b_sensibilidade_landsat"), index_col=0)
    rr = pd.read_csv(stats_path("B08b_modis_razao_taxas"))
    fig = plt.figure(figsize=(LARG, 6.6 * CM), layout="constrained")
    ax1, ax2, ax3 = fig.subplots(1, 3, width_ratios=[1.2, 0.8, 1.1])
    for tipo, cor, lab in [("cicatriz", C_INI, "Early-scar edges"), ("referencia", "#8f8e88", "Reference edges")]:
        g = curva[curva["tipo_seg"] == tipo]
        ax1.plot(g["limiar"], g["interrupcao_abs_%"], color=cor, lw=1.6, label=lab)
        ax1.plot(g["limiar"], g["interrupcao_rel_%"], color=cor, lw=1.0, ls=(0, (3, 2)))
    ax1.axvline(0.10, color=TINTA2, lw=0.6, ls=":")
    ax1.text(0.102, 2, "used", fontsize=tam(5.2), color=TINTA2)
    ax1.set_xlabel("NBR-drop threshold", fontsize=tam(6)); ax1.set_ylabel("Interrupted (%)", fontsize=tam(6))
    ax1.set_ylim(0, 102); ax1.legend(fontsize=tam(5.4), loc="center right")
    rotulo_painel(ax1, "a")
    x = np.arange(len(sens))
    ax2.bar(x, 100 * sens["landsat_viu_entrada"], color=[C_INI, "#8f8e88"][:len(sens)], width=0.6, zorder=2)
    for k_, (i_, r) in enumerate(sens.iterrows()):
        ax2.text(k_, 100 * r["landsat_viu_entrada"] + 2, f"{100 * r['landsat_viu_entrada']:.0f}%\nn = {int(r['n_segmentos']):,}",
                 ha="center", va="bottom", fontsize=tam(5.2), linespacing=1.0)
    ax2.set_xticks(x); ax2.set_xticklabels([{"cicatriz": "Scar", "referencia": "Ref."}.get(i, i) for i in sens.index])
    ax2.set_ylim(0, 118); ax2.set_ylabel("Landsat saw the entry (%)", fontsize=tam(6))
    ax2.grid(axis="x", visible=False); ax2.tick_params(axis="x", length=0)
    rotulo_painel(ax2, "b")
    y = 0; labs = []
    lab = {"naoqueimado": "all unburned", "naoqueimado_local": "unburned ≤ 5 km"}
    for cm_ in sorted(rr["core_m"].unique()):
        for ref in ["naoqueimado", "naoqueimado_local"]:
            r = rr[(rr["core_m"] == cm_) & (rr["referencia"] == ref)]
            if not len(r):
                continue
            r = r.iloc[0]
            ax3.plot([r["ic95_inf_boot_TI"], r["ic95_sup_boot_TI"]], [y, y], color=C_INI, lw=1.8, solid_capstyle="round")
            ax3.scatter(r["razao_taxas_agregada"], y, s=26, color=C_INI, edgecolor="white", zorder=3)
            ax3.text(r["ic95_sup_boot_TI"] * 1.12, y, f"{r['razao_taxas_agregada']:.2f}", va="center", fontsize=tam(5.4))
            labs.append(f"core > {cm_ / 1000:g} km, {lab[ref]}"); y += 1
    ax3.axvline(1, color=TINTA2, lw=0.7, ls=(0, (3, 2)))
    ax3.set_xscale("log"); ax3.set_yticks(range(len(labs))); ax3.set_yticklabels(labs, fontsize=tam(5.2))
    ax3.set_ylim(-0.6, len(labs) - 0.4); ax3.grid(axis="y", visible=False); ax3.tick_params(axis="y", length=0)
    ax3.set_xlabel("MODIS density, scar / unburned", fontsize=tam(6))
    rotulo_painel(ax3, "c")
    salvar(fig, "FigS6_detectability")

# ---------- S7: inferencia para poucas TIs (bloco 13) ----------
def figS7():
    ct = pd.read_csv(stats_path("B09b_celula_ses_coeficientes"), index_col=0)
    st_ = pd.read_csv(stats_path("B09b_segmento_or_jackknife"), index_col=0)
    LAB = {"conf_split_ses_0": "Fragmentation SES", "conf_lpi_ses_0": "Largest-patch SES",
           "conf_npatch_ses_0": "N patches SES", "log_area_cicatriz": "Scar size (log)",
           "largura_local_100m": "Local scar width", "ses_cel_split": "Cell fragmentation SES",
           "nbr_pre_int": "Inner-strip NBR before", "gap_meses": "Months since scar"}
    fig = plt.figure(figsize=(LARG, 6.8 * CM), layout="constrained")
    axa, axb = fig.subplots(1, 2)
    y = np.arange(len(ct))[::-1]
    axa.axvline(0, color=TINTA2, lw=0.7, ls=(0, (3, 2)))
    for yi, (v, r) in zip(y, ct.iterrows()):
        lo, hi = r["coef_pp_por_dp"] - 1.96 * r["ep_jackknife_TI_pp"], r["coef_pp_por_dp"] + 1.96 * r["ep_jackknife_TI_pp"]
        sig = r["p_wild_webb"] < 0.05; cor = C_INI if sig else "#9a9992"
        axa.plot([lo, hi], [yi, yi], color=cor, lw=1.8, solid_capstyle="round")
        axa.scatter(r["coef_pp_por_dp"], yi, s=28, color=cor if sig else "white", edgecolor="white" if sig else cor, lw=0.9, zorder=3)
        axa.text(hi, yi + 0.22, f"wild p = {r['p_wild_webb']:.3f}", fontsize=tam(5), color=TINTA2, ha="right", va="bottom")
    axa.set_yticks(y); axa.set_yticklabels([LAB.get(v, v) for v in ct.index], fontsize=tam(5.8))
    axa.grid(axis="y", visible=False); axa.tick_params(axis="y", length=0)
    axa.set_xlabel("Later burned area (p.p. per SD)", fontsize=tam(6))
    axa.set_title(f"{CELL_M / 1000:.0f}-km cells", fontsize=tam(5.8), color=MUDO, loc="right", pad=2)
    rotulo_painel(axa, "a")
    t = st_[st_["modelo"] == "cicatriz | configuracao + deteccao"] if "modelo" in st_ else st_
    y = np.arange(len(t))[::-1]
    axb.axvline(1, color=TINTA2, lw=0.7, ls=(0, (3, 2)))
    for yi, (v, r) in zip(y, t.iterrows()):
        sig = r["ic95_jackknife_TI_inf"] > 1 or r["ic95_jackknife_TI_sup"] < 1; cor = C_INI if sig else "#9a9992"
        axb.plot([r["ic95_jackknife_TI_inf"], r["ic95_jackknife_TI_sup"]], [yi + 0.12] * 2, color=cor, lw=1.8,
                 solid_capstyle="round")
        axb.scatter(r["or_1dp"], yi + 0.12, s=28, color=cor if sig else "white", edgecolor="white" if sig else cor,
                    lw=0.9, zorder=3)
        axb.plot([r["ic95_cluster_inf"], r["ic95_cluster_sup"]], [yi - 0.18] * 2, color="#bdbcb4", lw=1.2,
                 solid_capstyle="round")
    axb.set_xscale("log")
    axb.xaxis.set_major_locator(FixedLocator([0.5, 0.75, 1, 1.5, 2, 3])); axb.xaxis.set_minor_locator(NullLocator())
    axb.xaxis.set_major_formatter(FormatStrFormatter("%g"))
    axb.set_yticks(y); axb.set_yticklabels([LAB.get(v, v) for v in t.index], fontsize=tam(5.8))
    axb.grid(axis="y", visible=False); axb.tick_params(axis="y", length=0)
    axb.set_xlabel("Odds of stopping per SD", fontsize=tam(6))
    axb.legend(handles=[Line2D([], [], color=C_INI, lw=1.8, label="Jackknife by IL"),
                        Line2D([], [], color="#bdbcb4", lw=1.2, label="Clustered (fire + IL)")],
               loc="lower right", fontsize=tam(5.2))
    axb.set_title("scar edges, adjusted for detectability", fontsize=tam(5.8), color=MUDO, loc="right", pad=2)
    rotulo_painel(axb, "b")
    salvar(fig, "FigS7_few_IL_inference")

# ---------- S8: configuracao pelo modelo nulo x quantidade (bloco 09) ----------
def figS8():
    cn = pd.read_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[FUEL_MAIN]}_{TAG_YEARS}_nulo", "parquet"))
    sub = cn[cn["q_inicio"] > 0].dropna(subset=["conf_split_ses"])
    from scipy.stats import spearmanr
    fig = plt.figure(figsize=(LARG, 6.4 * CM), layout="constrained")
    axa, axb = fig.subplots(1, 2)
    for ax, col, cor, yl, let in [(axa, "conf_split", "#8f8e88", "Raw fragmentation\nlog(m$_{eff}$ after/before)", "a"),
                                  (axb, "conf_split_ses", C_INI, "Fragmentation SES\nvs null model", "b")]:
        hb = ax.hexbin(sub["q_inicio"], sub[col], gridsize=40, bins="log", mincnt=1, linewidths=0,
                       cmap=LinearSegmentedColormap.from_list("h", ["#f1f0eb", cor]))
        rho = spearmanr(sub["q_inicio"], sub[col]).correlation
        ax.set_title(f"Spearman ρ = {rho:.2f}", fontsize=tam(5.8), color=MUDO, loc="right", pad=2)
        ax.set_xlabel("Early burned fraction of the cell", fontsize=tam(6)); ax.set_ylabel(yl, fontsize=tam(6))
        if col.endswith("ses"):
            ax.axhline(0, color=TINTA2, lw=0.7, ls=(0, (3, 2)))
        rotulo_painel(ax, let)
    salvar(fig, "FigS8_null_model_vs_quantity")

# ---------- S9: resultado dos segmentos (bloco 10) ----------
def figS9():
    sg = pd.read_parquet(cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[FUEL_MAIN]}_{TAG_SEG}", "parquet"),
                         columns=["tipo_seg", "resultado"])
    ordem = ["interrupcao", "continuidade", "indeterminado", "sem_chegada"]
    nomes = {"interrupcao": "Stopped", "continuidade": "Crossed", "indeterminado": "Undetermined",
             "sem_chegada": "No later fire arrived"}
    cores = {"interrupcao": C_INI, "continuidade": C_PASSOU, "indeterminado": "#bdbcb4", "sem_chegada": "#ecebe6"}
    tab = sg.groupby(["tipo_seg", "resultado"]).size().unstack(fill_value=0).reindex(columns=ordem, fill_value=0)
    pct = 100 * tab.div(tab.sum(axis=1), axis=0)
    fig = plt.figure(figsize=(LARG, 4.6 * CM), layout="constrained")
    ax = fig.subplots()
    rows = [r for r in ["cicatriz", "referencia"] if r in pct.index]
    for yi, t in enumerate(rows[::-1]):
        left = 0
        for c in ordem:
            v = pct.loc[t, c]
            ax.barh(yi, v, left=left, color=cores[c], height=0.6, edgecolor="white", lw=0.6)
            if v >= 6:
                ax.text(left + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=tam(5.4),
                        color="white" if c in ("interrupcao", "continuidade") else TINTA)
            left += v
        ax.text(101, yi, f"n = {int(tab.loc[t].sum()):,}", va="center", fontsize=tam(5.4), color=TINTA2)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([{"cicatriz": "Early-scar edges", "referencia": "Reference edges"}[t]
                                                         for t in rows[::-1]])
    ax.set_xlim(0, 118); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel("Share of 300-m edge segments (%)", fontsize=tam(6))
    ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
    fig.legend(handles=[mpatches.Patch(color=cores[c], label=nomes[c]) for c in ordem], loc="outside lower center",
               ncol=4, fontsize=tam(5.6), handlelength=1.0)
    rotulo_painel(ax, "a")
    salvar(fig, "FigS9_edge_outcomes")

CAP.update({
    "FigS4_dry_season_per_IL": "Figure S4. Mean monthly rainfall (CHIRPS) in each IL; bars coloured by the local early and "
                               "rest of the dry season (months < 60 mm); shading, the Dias et al. (2026) split.",
    "FigS5_modis_over_scars": "Figure S5. MapBiomas scars (May–July, August–October) and MODIS MOD14A1/MYD14A1 fire pixels "
                              "(FireMask >= 8) in each IL, in the same year as Fig. 2.",
    "FigS6_detectability": "Figure S6. Detectability. (a) Share of interrupted edges by NBR-drop threshold (dashed, "
                           "relative drop). (b) Share of MODIS-confirmed entries also detected by Landsat. (c) Density of "
                           "later MODIS fire pixels in early-scar cores relative to unburned-fuel cores (95% CI, bootstrap "
                           "over ILs).",
    "FigS7_few_IL_inference": "Figure S7. Inference with eight ILs. (a) Cell-scale effects of configuration (null-model SES) "
                              "with jackknife-by-IL 95% CI and wild-bootstrap p. (b) Odds ratios at scar edges adjusted for "
                              "detectability: jackknife-by-IL and fire-and-IL clustered 95% CI.",
    "FigS8_null_model_vs_quantity": "Figure S8. Raw fuel fragmentation is almost a function of the early burned fraction "
                                    "(a); the null-model SES removes that dependence (b). Hexagons, cell-years.",
    "FigS9_edge_outcomes": "Figure S9. Outcome of all 300-m edge segments: stopped, crossed, undetermined and without later "
                           "fire arrival (excluded: absence of fire is not containment).",
    "FigR1_study_area_sample": "Figure R1. (a) The 14 ILs with BRIF and the 8 analysed. (b) Screening: longest gap between "
                               "clear Landsat 8/9 dates (colour) and candidate encounters (numbers) per IL and year.",
    "FigR2_encounter_landsat_modis": "Figure R2. The encounter seen by satellite: Landsat 8/9 SWIR2–NIR–red before and "
                                     "after the later fire, and dNBR with early scars, MODIS fire pixels and edge outcomes.",
    "FigR3_modis_independent_test": "Figure R3. NBR-independent test: MODIS later-fire pixels in early-scar cores and in "
                                    "unburned-fuel cores; rate ratio per IL and pooled (95% CI, bootstrap over ILs).",
    "FigR4_null_model_configuration": "Figure R4. Fuel-fragmentation SES against the null model per 5-km cell (mean "
                                      "2014–2024); blue, early scars split fuel more than chance.",
})

# ============================================================
# RODAR TUDO
# ============================================================
console.print("[bold cyan]-- Bloco 18: todas as figuras (versao 2026-10-25b, mapas padronizados) --[/bold cyan]")
for fn in [fig1, fig2, fig3, fig4, figR1, figR2, figR3, figR4, figS2, figS3, figS4, figS5, figS6, figS7, figS8, figS9]:
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
                "and FRRI of Dias et al. (2026).")
tb = d.add_table(rows=1, cols=len(t1.columns)); tb.style = "Light Grid Accent 1"
for j, c in enumerate(t1.columns):
    tb.rows[0].cells[j].text = str(c)
for row in t1.itertuples(index=False):
    cl_ = tb.add_row().cells
    for j, x in enumerate(row):
        cl_[j].text = "" if (isinstance(x, float) and np.isnan(x)) else (f"{x:,}" if isinstance(x, (int, np.integer)) else str(x))
d.save(TXT_DIR / "RSL_figuras_tabela.docx")
console.print(f"[bold green]OK BLOCO 18 completo: figuras em {FIG_DIR} e legendas em "
              f"{TXT_DIR / 'RSL_figuras_tabela.docx'}.[/bold green]")
