# ======================================================================
# BLOCO 10 - Sequencia das queimadas e encontros por segmento de borda (Landsat + MODIS)
# Depende dos blocos 00, 02, 03 (rasters), 04 (ERA5), 05 (MODIS) e 06 (estacoes).
# ======================================================================

check_version()
# ======================================================================

# ============================================================
# BLOCK 8 - Burn sequence + encounters at edge segments
#
# MUDANCA (2026-10-17): os focos ativos agora sao MODIS C6.1 (MOD14A1 +
#   MYD14A1, 1 km, FireMask >= 8), como no artigo 1. Raios ajustados a 1 km:
#     chegada : foco a ate FOCO_ARR_M (1000 m) da borda, do lado de fora
#     entrada : centro do pixel MODIS a >= FOCO_IN_M (1000 m) dentro da cicatriz
#   As colunas internas mantem o prefixo "viirs_" (viirs_chegada, viirs_dentro,
#   ordem "landsat+viirs"...) para nao quebrar bloco 10/bloco 12/bloco 16: leia "foco ativo".
#   Os checkpoints ganham o sufixo "_md" (TAG_SEG): os de VIIRS ficam intactos.
#
# Objetivo 1 - SEQUENCIA e QUALIDADE: cada cicatriz do inicio da seca
#   (MapBiomas) tem a ordem conferida antes de virar "anterior":
#     Landsat : mes da 1a queda de NBR (>= NBR_DROP) nos pixels da cicatriz
#     MODIS   : 1o foco da cicatriz antes do 1o foco que chega a borda = confirma
#   ordem_q = landsat+viirs | landsat | viirs | so_mapbiomas | contraditoria
#
# Objetivo 3 - ENCONTROS (unidade = SEGMENTO DE BORDA):
#   segmento  = trecho da borda de uma cicatriz anterior voltado para
#               vegetacao ainda nao queimada, cortado a cada SEG_LEN m
#   CHEGADA   = o fogo do restante queimou >= ARRIVAL da faixa externa
#               (MapBiomas) OU ha foco MODIS do restante a <= 1 km da borda,
#               do lado de fora. Sem chegada -> nao conta.
#   continuidade : nova queda de NBR em >= CONT_MIN da faixa interna bem
#                  observada, ou foco MODIS do restante >= 1 km dentro
#   interrupcao  : faixa interna bem observada e sem entrada
#   indeterminado: observacao insuficiente ou ordem nao verificavel
#
# NOVO - estado da faixa interna (para tratar a deteccao assimetrica do NBR):
#   nbr_pre_int   : NBR medio da faixa interna no fim do inicio da seca
#   drop_int_med  : queda mediana de NBR na faixa interna (pre - min do restante)
#   (o bloco 11 usa essas colunas; o bloco 12 pode usar nbr_pre_int como covariavel)
#
# REFERENCIA: pseudo-cicatrizes de mesma forma, deslocadas 2-10 km para
#   vegetacao nao queimada da mesma TI; mesma regra (Landsat + MODIS).
# ============================================================

from scipy import ndimage
from scipy.spatial import cKDTree
import rasterio

# ============================================================
# 1. PARAMETERS (o bloco 14 varia SEG_LEN, STRIP e ARRIVAL)
# ============================================================

FOCOS_NAME = globals().get("FOCOS_NAME", f"modis_focos_v1_{TAG_YEARS}")
TAG_SEG    = globals().get("TAG_SEG", f"{TAG_YEARS}_md")
ENC_DEFAULT = dict(
    seg_len=300,       # comprimento do segmento (m)
    strip=90,          # largura das faixas externa e interna (m)
    arrival=0.3,       # fracao da faixa externa queimada para haver chegada
    cont_min=0.2,      # fracao da faixa interna com nova queda de NBR = continuidade
    obs_min=0.5,       # fracao da faixa interna com Landsat antes e durante o restante
    nbr_drop=10,       # queda de NBR (x100) que conta como queimada
    min_seg_px=5,      # segmento com >= 5 pixels de borda (150 m)
    win=990,           # janela das covariaveis de quantidade/configuracao (m)
    viirs_arr=1000,    # (MODIS) foco a ate 1 km da borda, do lado de fora = chegada
    viirs_in=1000,     # (MODIS) centro do pixel >= 1 km dentro da cicatriz = entrada
    ref_min=2000, ref_max=10000, ref_tries=25,
)
SEASONS = load_seasons()
AMOSTRA = load_sample_ids()
CROSS = ndimage.generate_binary_structure(2, 1)
CONN8 = np.ones((3, 3), int)
SEQ_DIR = DIRS["exports"] / "sequencia_md"
SEQ_DIR.mkdir(parents=True, exist_ok=True)
rng_ref = np.random.default_rng(2024)

# --- Focos MODIS e ERA5 ---------------------------------------------------
if "focos_raw" not in globals():
    focos_raw = read_table(cache_path(FOCOS_NAME, "parquet"))
vi = focos_raw.copy()
vi = vi[vi["confidence"].astype(str).str.lower().str[0] != "l"].copy()   # FireMask >= 8 (artigo 1)
vi["acq_date"] = pd.to_datetime(vi["acq_date"])
_g = gpd.GeoSeries(gpd.points_from_xy(vi["longitude"], vi["latitude"]), crs="EPSG:4326").to_crs(AREA_CRS)
vi["x"], vi["y"] = _g.x.to_numpy(), _g.y.to_numpy()
vi["year"], vi["mes"] = vi["acq_date"].dt.year, vi["acq_date"].dt.month
console.print(f"[cyan]Focos MODIS (FireMask >= 8):[/cyan] {len(vi):,}")

if "era5_daily" not in globals():
    era5_daily = read_table(cache_path(f"era5_diario_v2_{TAG_YEARS}", "parquet"))
e5 = era5_daily.copy()
e5["date"] = pd.to_datetime(e5["date"])
e5["mo"] = e5["date"].dt.month
for v in ["vpd_max", "rh_min", "wind"]:
    e5[f"P_{v}"] = e5.groupby(["point_id", "mo"])[v].rank(method="max", pct=True)
e5_idx = e5.set_index(["point_id", "date"])[["vpd_max", "wind", "rh_min", "P_vpd_max", "P_wind", "P_rh_min"]]
e5_pts = e5.drop_duplicates("point_id")[["point_id", "lon", "lat"]].reset_index(drop=True)
e5_tree = cKDTree(e5_pts[["lon", "lat"]].to_numpy())
from pyproj import Transformer
_to_ll8 = Transformer.from_crs(AREA_CRS, "EPSG:4326", always_xy=True)

# ============================================================
# 2. LANDSAT: estado no fim do inicio, nova queda no restante, mes da queda
# ============================================================

def landsat_layers(yr, ini, res, nbr_drop):
    # sem dado = -128 (arquivos de 8 bits) ou -32768 (16 bits); NBR valido vai de -100 a 100
    nbr = {m: np.where(yr[f"nbr{m:02d}"] <= -101, np.nan, yr[f"nbr{m:02d}"].astype(float)) for m in LS_MONTHS}
    pre = np.full(next(iter(nbr.values())).shape, np.nan)
    for m in [m for m in LS_MONTHS if m <= max(ini)]:
        pre = np.where(~np.isnan(nbr[m]), nbr[m], pre)
    rm = [m for m in res if m in nbr]
    stack = np.stack([nbr[m] for m in rm]) if rm else np.full((1,) + pre.shape, np.nan)
    with np.errstate(all="ignore"):
        min_res = np.nanmin(stack, axis=0)
    obs_ok = ~np.isnan(pre) & ~np.isnan(min_res)
    drop = np.where(obs_ok, pre - min_res, np.nan)
    nova = obs_ok & (drop >= nbr_drop)
    ls_mes = np.zeros(pre.shape, np.int16)
    prev = np.full(pre.shape, np.nan)
    for m in LS_MONTHS:
        cur = nbr[m]
        hit = (ls_mes == 0) & ~np.isnan(cur) & ~np.isnan(prev) & ((prev - cur) >= nbr_drop)
        ls_mes[hit] = m
        prev = np.where(~np.isnan(cur), cur, prev)
    return obs_ok, nova, ls_mes, pre, drop

# ============================================================
# 3. SEGMENTOS DE UMA "CICATRIZ" (real ou pseudo)
# ============================================================

def _px(xs, ys, tr, shape):
    c = np.floor((np.asarray(xs) - tr.c) / PIX_M).astype(int)
    r = np.floor((tr.f - np.asarray(ys)) / PIX_M).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    return r, c, ok

def segments_for(S, labS, ctx, P, kind):
    """S: mascara das cicatrizes (reais ou pseudo); labS: rotulos; ctx: camadas do TI-ano."""
    fuel1, L, obs_ok, nova, tr = ctx["fuel1"], ctx["L"], ctx["obs_ok"], ctx["nova"], ctx["tr"]
    H, W = S.shape
    facing = fuel1 & ~S
    B = S & ndimage.binary_dilation(facing, structure=CROSS)
    if not B.any():
        return pd.DataFrame()
    tpx = max(1, int(round(P["seg_len"] / PIX_M)))
    rr, cc = np.nonzero(B)
    ntc = W // tpx + 1
    key = labS[rr, cc].astype(np.int64) * (ntc * (H // tpx + 1)) + (rr // tpx) * ntc + (cc // tpx)
    uk, seg_of_b, nb = np.unique(key, return_inverse=True, return_counts=True)
    keep = nb[seg_of_b] >= P["min_seg_px"]
    rr, cc, seg_of_b = rr[keep], cc[keep], seg_of_b[keep]
    if len(rr) == 0:
        return pd.DataFrame()
    _, seg_of_b = np.unique(seg_of_b, return_inverse=True)
    nseg = seg_of_b.max() + 1
    segmap = np.full((H, W), -1, np.int64)
    segmap[rr, cc] = seg_of_b
    Bk = segmap >= 0
    dist, inds = ndimage.distance_transform_edt(~Bk, return_indices=True)
    near = segmap[inds[0], inds[1]]
    scar_near = labS[inds[0], inds[1]]
    wpx = P["strip"] / PIX_M
    # faixa externa: combustivel fora da cicatriz; pixel de agricultura nao conta
    ext = (dist <= wpx) & ~S & fuel1 & (ctx["cover"] != 3)
    intr = (dist <= wpx) & S & (labS == scar_near)
    deep = (dist <= 10) & S & (labS == scar_near)                 # ate 300 m para dentro
    d_in = ndimage.distance_transform_edt(S)

    def bc(mask, w=None):
        ids = near[mask]
        return np.bincount(ids, weights=None if w is None else w[mask], minlength=nseg)

    io = intr & obs_ok
    seg = pd.DataFrame({
        "seg": np.arange(nseg),
        "scar": np.bincount(seg_of_b, weights=labS[rr, cc], minlength=nseg) / np.bincount(seg_of_b, minlength=nseg),
        "comprimento_m": np.bincount(seg_of_b, minlength=nseg) * PIX_M,
        "r": np.bincount(seg_of_b, weights=rr, minlength=nseg) / np.bincount(seg_of_b, minlength=nseg),
        "c": np.bincount(seg_of_b, weights=cc, minlength=nseg) / np.bincount(seg_of_b, minlength=nseg),
        "n_ext": bc(ext), "n_ext_q": bc(ext & L),
        "n_int": bc(intr), "n_int_obs": bc(io), "n_int_nova": bc(io & nova),
        "n_int_L": bc(intr & L),
        "decl_ext": bc(ext, ctx["slope"]),
        "nbr_pre_int": bc(io, np.nan_to_num(ctx["pre"])),
        "drop_int_soma": bc(io, np.nan_to_num(ctx["drop"])),
    })
    seg["scar"] = seg["scar"].round().astype(int)
    seg["decl_ext"] = seg["decl_ext"] / seg["n_ext"].replace(0, np.nan)
    seg["nbr_pre_int"] = seg["nbr_pre_int"] / seg["n_int_obs"].replace(0, np.nan) / 100.0
    seg["drop_int_med"] = seg.pop("drop_int_soma") / seg["n_int_obs"].replace(0, np.nan) / 100.0
    wmax = np.zeros(nseg)
    np.maximum.at(wmax, near[deep], d_in[deep])
    seg["largura_local_m"] = 2 * wmax * PIX_M
    m_ext = ctx["month"][ext & L]; s_ext = near[ext & L]; f_ext = ctx["fire"][ext & L]
    if len(s_ext):
        tmp = pd.DataFrame({"seg": s_ext, "mes": m_ext, "fire": f_ext})
        moda = tmp.groupby("seg").agg(mes_chegada=("mes", lambda x: x.mode().iat[0]),
                                      fire=("fire", lambda x: x.mode().iat[0]))
        seg = seg.merge(moda, left_on="seg", right_index=True, how="left")
    else:
        seg["mes_chegada"], seg["fire"] = np.nan, np.nan

    # FOCOS MODIS: chegada (fora, perto da borda) e entrada (dentro, longe da borda)
    vl, ve = ctx["viirs_res"], ctx["viirs_ini"]
    seg["viirs_chegada"], seg["data_chegada_viirs"], seg["viirs_dentro"] = 0, pd.NaT, 0
    if len(vl):
        r, c, ok = _px(vl["x"], vl["y"], tr, S.shape)
        r, c, d = r[ok], c[ok], vl["acq_date"].to_numpy()[ok]
        out = ~S[r, c] & (dist[r, c] <= P["viirs_arr"] / PIX_M)
        inn = S[r, c] & (d_in[r, c] >= P["viirs_in"] / PIX_M)
        if out.any():
            t = pd.DataFrame({"seg": near[r[out], c[out]], "d": d[out]}).groupby("seg")["d"].agg(["size", "min"])
            seg.loc[t.index, "viirs_chegada"] = t["size"].to_numpy()
            seg.loc[t.index, "data_chegada_viirs"] = t["min"].to_numpy()
        if inn.any():
            t = pd.Series(near[r[inn], c[inn]]).value_counts()
            seg.loc[t.index, "viirs_dentro"] = t.to_numpy()
    seg["data_1o_foco_cicatriz"] = pd.NaT
    if kind == "cicatriz" and len(ve):
        r, c, ok = _px(ve["x"], ve["y"], tr, S.shape)
        r, c, d = r[ok], c[ok], ve["acq_date"].to_numpy()[ok]
        hit = labS[r, c] > 0
        if hit.any():
            first = pd.DataFrame({"scar": labS[r[hit], c[hit]], "d": d[hit]}).groupby("scar")["d"].min()
            seg["data_1o_foco_cicatriz"] = seg["scar"].map(first)
    seg["tipo_seg"] = kind
    return seg

# ============================================================
# 4. PSEUDO-CICATRIZES (referencia sem queima anterior)
# ============================================================

def place_pseudo(labS, scar_ids, ctx, P):
    H, W = labS.shape
    fuel1, burned_before = ctx["fuel1"], ctx["E"] | ctx["antes"]
    barrier, inside = ctx["barrier"], ctx["inside"]
    pseudo = np.zeros((H, W), np.int32)
    objs = ndimage.find_objects(labS)
    k = 0
    for sid in scar_ids:
        sl = objs[sid - 1]
        if sl is None:
            continue
        shape_mask = labS[sl] == sid
        h, w = shape_mask.shape
        for _ in range(P["ref_tries"]):
            ang = rng_ref.uniform(0, 2 * np.pi)
            dd = rng_ref.uniform(P["ref_min"], P["ref_max"]) / PIX_M
            r0 = int(sl[0].start + dd * np.sin(ang)); c0 = int(sl[1].start + dd * np.cos(ang))
            if r0 < 0 or c0 < 0 or r0 + h > H or c0 + w > W:
                continue
            tgt = (slice(r0, r0 + h), slice(c0, c0 + w))
            n = shape_mask.sum()
            if (inside[tgt] & shape_mask).sum() < n:
                continue
            if (fuel1[tgt] & shape_mask).sum() < 0.8 * n:
                continue
            if ((burned_before[tgt] | barrier[tgt]) & shape_mask).sum() > 0.05 * n:
                continue
            if (pseudo[tgt][shape_mask] > 0).any():
                continue
            k += 1
            pseudo[tgt][shape_mask] = k
            break
    return pseudo

# ============================================================
# 5. UM TI-ANO COMPLETO
# ============================================================

def tile_conf(fuel0, fuel1, E, queim, P1, P2, P):
    """quantidade e configuracao em janelas de ~1 km (mesmas metricas do bloco 08)."""
    tp = max(1, int(round(P["win"] / PIX_M)))
    H, W = fuel1.shape
    nr, nc = H // tp + 1, W // tp + 1
    out = {k: np.full((nr, nc), np.nan) for k in ["q", "a1", "a2", "split", "lpi", "nat"]}
    for i in range(nr):
        for j in range(nc):
            sl = (slice(i * tp, (i + 1) * tp), slice(j * tp, (j + 1) * tp))
            A = queim[sl].sum()
            out["nat"][i, j] = queim[sl].mean() if queim[sl].size else np.nan
            if A < 10:
                continue
            s0, _, _ = _meff(fuel0[sl]); s1, mx1, _ = _meff(fuel1[sl])
            out["q"][i, j] = (E[sl] & queim[sl]).sum() / A
            out["a1"][i, j] = P1[sl].sum() / A
            out["a2"][i, j] = P2[sl].sum() / A
            out["split"][i, j] = np.log(s1 / s0) if (s0 > 0 and s1 > 0) else np.nan
            out["lpi"][i, j] = mx1 / A
    return out, tp

def ti_year_segments(ti, year, scheme, P, save_seq=False, fuel_mode=FUEL_MAIN):
    st = static_of(ti)
    yr, l1, l2 = read_raster(ti, year), read_raster(ti, year - 1), read_raster(ti, year - 2)
    ini, res = SEASONS[scheme][int(ti)]
    tr = st["_transform"]
    inside = st["ti"] == ti
    barrier = st["barrier"] == 1
    queim = inside & fuel_from_cover(yr["cover"], fuel_mode) & ~barrier
    sm = season_masks(yr["month"], ti, scheme, SEASONS)
    E = sm["inicio"] & inside
    L = sm["resto"] & inside
    fuel0 = queim & ~sm["antes"]
    fuel1 = fuel0 & ~E
    obs_ok, nova, ls_mes, pre, drop = landsat_layers(yr, ini, res, P["nbr_drop"])
    fire, _ = ndimage.label(L, structure=CONN8)
    v = vi[(vi["year"] == year)]
    ctx = dict(fuel1=fuel1, L=L, E=E, antes=sm["antes"], obs_ok=obs_ok, nova=nova, tr=tr, cover=yr["cover"],
               slope=st["slope10"] / 10.0, month=yr["month"], fire=fire, barrier=barrier, inside=inside,
               pre=pre, drop=drop,
               viirs_res=v[v["mes"].isin(res)], viirs_ini=v[v["mes"].isin(ini)])

    labE, nE = ndimage.label(E, structure=CONN8)
    segs = segments_for(E, labE, ctx, P, "cicatriz")
    if segs.empty:
        return pd.DataFrame(), None
    lab_px = labE[E]
    lm = ls_mes[E]
    before = np.bincount(lab_px, weights=((lm > 0) & (lm <= max(ini))), minlength=nE + 1)
    after = np.bincount(lab_px, weights=(lm > max(ini)), minlength=nE + 1)
    segs["ls_antes"], segs["ls_depois"] = before[segs["scar"]], after[segs["scar"]]
    segs["area_cicatriz_ha"] = np.bincount(lab_px, minlength=nE + 1)[segs["scar"]] * 0.09
    mes_cic = pd.Series(yr["month"][E]).groupby(lab_px).agg(lambda x: x.mode().iat[0])
    segs["mes_cicatriz"] = segs["scar"].map(mes_cic)

    arr = (segs["n_ext_q"] / segs["n_ext"].replace(0, np.nan) >= P["arrival"]) | (segs["viirs_chegada"] > 0)
    pseudo = place_pseudo(labE, sorted(segs.loc[arr, "scar"].unique()), ctx, P)
    refs = segments_for(pseudo > 0, pseudo, ctx, P, "referencia") if pseudo.any() else pd.DataFrame()
    if len(refs):
        refs["area_cicatriz_ha"] = np.bincount(pseudo[pseudo > 0], minlength=pseudo.max() + 1)[refs["scar"]] * 0.09
        refs["ls_antes"] = refs["ls_depois"] = 0
        refs["mes_cicatriz"] = np.nan
    allseg = pd.concat([segs, refs], ignore_index=True)

    P1 = (l1["month"] > 0) & queim
    P2 = (l2["month"] > 0) & queim
    tc, tp = tile_conf(fuel0, fuel1, E, queim, P1, P2, P)
    ti_r = (allseg["r"] // tp).astype(int).clip(0, tc["q"].shape[0] - 1)
    ti_c = (allseg["c"] // tp).astype(int).clip(0, tc["q"].shape[1] - 1)
    for k, col in [("q", "q_inicio_win"), ("a1", "q_ant1_win"), ("a2", "q_ant2_win"),
                   ("split", "conf_split_win"), ("lpi", "conf_lpi_win"), ("nat", "combustivel_win")]:
        allseg[col] = tc[k][ti_r, ti_c]
    win = max(3, int(round(P["win"] / PIX_M)))
    bar_f = ndimage.uniform_filter(barrier.astype(float), size=win)
    riv_f = ndimage.uniform_filter((st["river"] == 1).astype(float), size=win)
    rr, cc = allseg["r"].round().astype(int), allseg["c"].round().astype(int)
    allseg["barreira_win"], allseg["rios_win"] = bar_f[rr, cc], riv_f[rr, cc]
    for g, col in [(1, "nativa_win"), (2, "pastagem_win"), (3, "agricultura_win")]:
        allseg[col] = ndimage.uniform_filter(((yr["cover"] == g) & inside).astype(float), size=win)[rr, cc]
    allseg["x"] = tr.c + (allseg["c"] + 0.5) * PIX_M
    allseg["y"] = tr.f - (allseg["r"] + 0.5) * PIX_M
    allseg["ti_id"], allseg["year"], allseg["esquema"], allseg["combustivel"] = ti, year, scheme, fuel_mode
    allseg["fonte_focos"] = "MODIS"

    if save_seq:
        seqr = np.zeros(E.shape, np.uint8)
        seqr[E] = 1; seqr[L] = 2; seqr[E & nova] = 3; seqr[pseudo > 0] = 4
        prof = dict(driver="GTiff", height=E.shape[0], width=E.shape[1], count=1, dtype="uint8",
                    crs=st["_crs"], transform=tr, compress="deflate", nodata=0)
        with rasterio.open(SEQ_DIR / f"seq_ti{ti}_{year}.tif", "w", **prof) as dst:
            dst.write(seqr, 1)

    mb = yr["month"]
    okp = inside & (mb > 0) & (ls_mes > 0)
    conc = {"ti_id": ti, "year": year, "esquema": scheme,
            "n_pixels_comparados": int(okp.sum()),
            "mesmo_mes": float((mb[okp] == ls_mes[okp]).mean()) if okp.any() else np.nan,
            "ate_1_mes": float((np.abs(mb[okp] - ls_mes[okp]) <= 1).mean()) if okp.any() else np.nan}
    return allseg, conc

# ============================================================
# 6. CLASSIFICACAO: ORDEM, CHEGADA E RESULTADO
# ============================================================

def classify_segments(df, P):
    df = df.copy()
    df["frac_ext_queimada"] = df["n_ext_q"] / df["n_ext"].replace(0, np.nan)
    df["frac_int_obs"] = df["n_int_obs"] / df["n_int"].replace(0, np.nan)
    df["frac_int_nova"] = df["n_int_nova"] / df["n_int_obs"].replace(0, np.nan)
    df["chegada_mapbiomas"] = df["frac_ext_queimada"] >= P["arrival"]
    df["chegada"] = df["chegada_mapbiomas"] | (df["viirs_chegada"] > 0)

    df["ordem_landsat"] = np.select(
        [(df["ls_antes"] >= 5) & (df["ls_antes"] >= df["ls_depois"]),
         (df["ls_depois"] >= 5) & (df["ls_depois"] > df["ls_antes"])],
        ["confirma", "contradiz"], "sem_dado")
    has_v = df["data_1o_foco_cicatriz"].notna() & df["data_chegada_viirs"].notna()
    df["ordem_viirs"] = np.where(~has_v, "sem_dado",
                                 np.where(pd.to_datetime(df["data_1o_foco_cicatriz"]) <
                                          pd.to_datetime(df["data_chegada_viirs"]), "confirma", "contradiz"))
    ol, ov = df["ordem_landsat"], df["ordem_viirs"]
    df["ordem_q"] = np.select(
        [(ol == "contradiz") | (ov == "contradiz"),
         (ol == "confirma") & (ov == "confirma"), ol == "confirma", ov == "confirma"],
        ["contraditoria", "landsat+viirs", "landsat", "viirs"], "so_mapbiomas")
    df["gap_meses"] = df["mes_chegada"] - df["mes_cicatriz"]
    ref = df["tipo_seg"] == "referencia"
    df.loc[ref, ["ordem_landsat", "ordem_viirs", "ordem_q"]] = "nao_se_aplica"
    ordem_ok = ref | df["ordem_q"].isin(["landsat+viirs", "landsat", "viirs"]) | \
               ((df["ordem_q"] == "so_mapbiomas") & (df["gap_meses"] >= 2))

    bem_obs = df["frac_int_obs"] >= P["obs_min"]
    entrou_ls = bem_obs & (df["frac_int_nova"] >= P["cont_min"])
    entrou = entrou_ls | (df["viirs_dentro"] > 0)
    entrou_mb = ref & (df["n_int_L"] / df["n_int"].replace(0, np.nan) >= P["cont_min"])

    df["resultado"] = np.select(
        [~df["chegada"], ~ordem_ok, entrou, bem_obs],
        ["sem_chegada", "indeterminado", "continuidade", "interrupcao"], "indeterminado")
    df["resultado_mb"] = np.select(
        [~df["chegada"], ~ordem_ok, entrou | entrou_mb, bem_obs],
        ["sem_chegada", "indeterminado", "continuidade", "interrupcao"], "indeterminado")
    df["regra_continuidade"] = "simetrica_v1"
    df["motivo"] = np.select(
        [~df["chegada"], ~ordem_ok, entrou, bem_obs],
        ["fogo nao chegou a borda", "ordem nao verificada/contraditoria", "", ""],
        "observacao insuficiente da faixa interna")
    df["interrupcao"] = (df["resultado"] == "interrupcao").astype(float)
    df.loc[~df["resultado"].isin(["interrupcao", "continuidade"]), "interrupcao"] = np.nan
    df["fire_id"] = np.where(df["fire"].notna(),
                             df["ti_id"].astype(str) + "_" + df["year"].astype(str) + "_f" +
                             df["fire"].fillna(-1).astype(int).astype(str),
                             df["ti_id"].astype(str) + "_" + df["year"].astype(str) + "_v" + df["seg"].astype(str))
    return df

def add_weather(df):
    df = df.copy()
    dt = pd.to_datetime(df["data_chegada_viirs"])
    mes_dt = pd.to_datetime(pd.DataFrame({"year": df["year"].astype(int),
                                          "month": df["mes_chegada"].fillna(9).astype(int), "day": 15}))
    df["data_chegada"] = dt.fillna(mes_dt).dt.normalize()
    df["fonte_data"] = np.where(dt.notna(), "modis", "mapbiomas_mes")
    lon, lat = _to_ll8.transform(df["x"].to_numpy(), df["y"].to_numpy())
    _, idx = e5_tree.query(np.c_[lon, lat])
    df["era5_point"] = e5_pts.loc[idx, "point_id"].to_numpy()
    w = e5_idx.reindex(pd.MultiIndex.from_arrays([df["era5_point"], df["data_chegada"]])).reset_index(drop=True)
    for c in w.columns:
        df[c] = w[c].to_numpy()
    return df

# ============================================================
# 7. TODAS AS TIs DA AMOSTRA
# ============================================================

def param_tag(P):
    return f"s{P['seg_len']}_f{P['strip']}_a{int(P['arrival'] * 100)}"

def seg_cache_name(scheme=SEASON_MAIN, P=None, fuel_mode=FUEL_MAIN):
    P = {**ENC_DEFAULT, **(P or {})}
    return f"segmentos_{scheme}_{param_tag(P)}_{FUEL_TAG[fuel_mode]}_{TAG_SEG}"

def build_segments(scheme=SEASON_MAIN, P=None, force=False, save_seq=False, fuel_mode=FUEL_MAIN):
    P = {**ENC_DEFAULT, **(P or {})}
    p = cache_path(seg_cache_name(scheme, P, fuel_mode), "parquet")
    if p.exists() and not (force or FORCE_REPROCESS):
        return pd.read_parquet(p), None
    parts, concs = [], []
    for ti in tqdm(AMOSTRA, desc=f"Segmentos {scheme} {param_tag(P)}"):
        for y in YEARS:
            seg, conc = ti_year_segments(ti, y, scheme, P, save_seq=save_seq, fuel_mode=fuel_mode)
            if len(seg):
                parts.append(seg)
            if conc:
                concs.append(conc)
    if not parts:
        raise RuntimeError("Nenhum segmento encontrado - confira os rasters do bloco 03 e a amostra do bloco 02.")
    df = classify_segments(pd.concat(parts, ignore_index=True), P)
    df = add_weather(df)
    df["seg_uid"] = (df["ti_id"].astype(str) + "_" + df["year"].astype(str) + "_" +
                     df["tipo_seg"].str[0] + df["seg"].astype(str))
    for c in ["data_chegada_viirs", "data_1o_foco_cicatriz", "data_chegada"]:
        df[c] = pd.to_datetime(df[c])
    df.to_parquet(p, index=False)
    return df, pd.DataFrame(concs)

segs_by_fuel, conc = {}, None
for fm in FUEL_RUNS:
    s_, c_ = build_segments(save_seq=(fm == FUEL_MAIN), fuel_mode=fm)
    segs_by_fuel[fm] = s_
    if fm == FUEL_MAIN:
        conc = c_
    console.print(f"[green]OK [{fm}] {len(s_):,} segmentos[/green]")
segs = segs_by_fuel[FUEL_MAIN]
console.print("[bold]Resultado por definicao de combustivel[/bold]")
display(pd.concat({fm: s_.groupby(["tipo_seg", "resultado"]).size() for fm, s_ in segs_by_fuel.items()},
                  axis=1).fillna(0).astype(int))

# ============================================================
# 8. RESUMOS
# ============================================================

res_tab = (segs.groupby(["tipo_seg", "resultado"]).agg(n=("seg_uid", "size"),
                                                         km=("comprimento_m", lambda x: x.sum() / 1000))
               .reset_index())
res_tab.to_csv(stats_path("B08_resultado_segmentos"), index=False)
display(res_tab)

ordem_tab = (segs[(segs["tipo_seg"] == "cicatriz") & segs["chegada"]]
             .groupby(["ti_id", "ordem_q"]).size().unstack(fill_value=0))
ordem_tab.to_csv(stats_path("B08_ordem_qualidade"))
display(ordem_tab)

# quanto o MODIS contribui (com 1 km ele pesa menos que o VIIRS: declarar)
ch = segs[segs["chegada"]]
fontes = pd.DataFrame({
    "chegada_so_mapbiomas": (ch["chegada_mapbiomas"] & (ch["viirs_chegada"] == 0)).groupby(ch["tipo_seg"]).mean(),
    "chegada_com_modis": (ch["viirs_chegada"] > 0).groupby(ch["tipo_seg"]).mean(),
    "entrada_vista_pelo_modis": (ch["viirs_dentro"] > 0).groupby(ch["tipo_seg"]).mean(),
    "data_chegada_modis": (ch["fonte_data"] == "modis").groupby(ch["tipo_seg"]).mean()}).round(3)
fontes.to_csv(stats_path("B08_contribuicao_modis"))
console.print("[bold]Contribuicao dos focos MODIS (fracao dos segmentos com chegada)[/bold]")
display(fontes)

if conc is not None and len(conc):
    conc.to_csv(stats_path("B08_concordancia_mapbiomas_landsat"), index=False)
    display(conc.groupby("ti_id")[["mesmo_mes", "ate_1_mes"]].mean().round(2))


# ============================================================
# 9. REGRA SIMETRICA x REGRA ANTIGA (sensibilidade)
#    resultado    = regra SIMETRICA: entrada detectada do MESMO jeito nas bordas de
#                   cicatriz e de referencia (Landsat + MODIS) -> principal
#    resultado_mb = regra antiga: na referencia o MapBiomas tambem conta entrada
#                   (o MapBiomas guarda um so mes por pixel/ano e nunca mostra a
#                   cicatriz queimando de novo) -> so sensibilidade
# ============================================================

rows = []
for fm, s_ in segs_by_fuel.items():
    for regra, col in [("antiga (MapBiomas na referencia)", "resultado_mb"), ("simetrica (Landsat + MODIS)", "resultado")]:
        for tipo, g in s_.groupby("tipo_seg"):
            vc = g[col].value_counts()
            n_i, n_c = int(vc.get("interrupcao", 0)), int(vc.get("continuidade", 0))
            rows.append({"combustivel": fm, "regra": regra, "tipo_seg": tipo, "interrupcao": n_i,
                         "continuidade": n_c, "indeterminado": int(vc.get("indeterminado", 0)),
                         "sem_chegada": int(vc.get("sem_chegada", 0)),
                         "% interrupcao": round(100 * n_i / max(n_i + n_c, 1), 1)})
comp = pd.DataFrame(rows)
comp.to_csv(stats_path("B08a_regra_antiga_x_simetrica"), index=False)
console.print("[bold]Interrupcao x continuidade: regra simetrica (principal) x antiga (sensibilidade)[/bold]")
display(comp.set_index(["combustivel", "regra", "tipo_seg"]))

anal = segs[segs["resultado"].isin(["interrupcao", "continuidade"])]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
pv = segs.pivot_table(index="tipo_seg", columns="resultado", values="seg_uid", aggfunc="size", fill_value=0)
pv.plot.barh(stacked=True, ax=axs[0], color={"continuidade": "#b2182b", "interrupcao": "#1b7837",
                                              "indeterminado": "#bdbdbd", "sem_chegada": "#f0f0f0"})
axs[0].set_xlabel("Segmentos"); axs[0].set_ylabel("")
axs[0].legend(fontsize=7, frameon=False)
p_int = anal.groupby(["tipo_seg"])["interrupcao"].mean()
axs[1].bar(p_int.index, p_int.values, color=["#1b7837", "#9e9e9e"][:len(p_int)])
axs[1].set_ylim(0, 1)
axs[1].set_ylabel("Proporcao de interrupcao\n(segmentos com chegada e resultado definido)")
fig.savefig(fig_path("B08_resultados_md"))
plt.show()

console.print(f"[bold green]OK BLOCO 10 completo: {len(segs):,} segmentos "
              f"({len(anal):,} com resultado definido).[/bold green]")
