# ======================================================================
# BLOCO 09 - Configuracao das cicatrizes contra um modelo nulo (mesma quantidade, posicao ao acaso)
# Depende dos blocos 00, 03 (rasters), 06 (estacoes) e 08 (celulas).
# ======================================================================

check_version()

# ============================================================
# BLOCK 7b - Null-model configuration (standardized effect size, SES)
#
# Problema do bloco 08: na celula, m_eff e densidade de borda sao quase a propria
# quantidade (Spearman -1,00 e 0,97 com q_inicio), e o residuo pela curva
# depende da forma escolhida para a curva.
#
# Solucao (padrao em ecologia da paisagem): para CADA celula-ano, as
# cicatrizes do inicio da seca sao REPOSICIONADAS AO ACASO dentro do
# combustivel da propria celula, N_NULL vezes:
#   - cada cicatriz (mancha conectada, vizinhanca de 8) mantem a FORMA e a AREA;
#   - so pode cair sobre combustivel disponivel (fuel0) e sem sobrepor outra;
#   - cicatriz que nao cabe em lugar nenhum fica onde estava (contada em n_fixas).
# Quantidade, numero e tamanho das cicatrizes ficam IGUAIS ao observado; so a
# POSICAO muda. Para cada metrica de configuracao do combustivel restante:
#   SES = (observado - media do nulo) / desvio do nulo
#   p_nulo = fracao das replicas <= observado
# Leitura (conf_split = log m_eff depois/antes):
#   SES < 0 -> as cicatrizes fragmentam o combustivel MAIS do que o acaso
#              (ficaram espalhadas / atravessadas no combustivel)
#   SES > 0 -> fragmentam MENOS (agrupadas, encostadas em barreiras ou na borda)
# Assim a configuracao e independente da quantidade POR CONSTRUCAO, nao por
# uma regressao. E isto que testa a hipotese do professor: "mesma proporcao
# queimada, organizacao espacial diferente".
#
# Custo: uma replica = reposicionar as cicatrizes e rotular o combustivel.
# Roda em paralelo por TI-ano e guarda checkpoint por TI (se cair, continua).
#
# Output:
#   02_cache/nulo/nulo_<esquema>_<cel>_<comb>_ti<id>_<tag>.parquet (por TI)
#   02_cache/celulas_<esquema>_<cel>_<comb>_<tag>_nulo.parquet  (celulas do bloco 08 + SES)
#   04_stats/B07b_ses_resumo.csv, B07b_correlacao_ses_quantidade.csv
#   05_figures/B07b_ses_mapa_exemplo.{tif,png,pdf}, B07b_ses_x_quantidade.{tif,png,pdf} (600 dpi)
# ============================================================

from scipy import ndimage
from joblib import Parallel, delayed

# ============================================================
# 1. PARAMETERS
# ============================================================

N_NULL       = 29          # replicas por celula-ano (p minimo = 1/30)
TRIES        = 40          # tentativas de posicao por cicatriz
MIN_SCAR_PX  = 2           # manchas de 1 pixel ficam fixas (ruido do MapBiomas)
N_JOBS       = -1
SEED         = 2026
NULO_DIR     = DIRS["cache"] / "nulo"
NULO_DIR.mkdir(exist_ok=True)
CONN8 = np.ones((3, 3), int)
SEASONS = load_seasons()
AMOSTRA = load_sample_ids()
FUEL_RUNS_NULO = [FUEL_MAIN]          # acrescente "nativa+pastagem" se quiser o nulo nas duas
SES_VARS = ["conf_split", "conf_lpi", "conf_npatch"]
SES_CAP  = 5.0             # |SES| limitado (nulo quase sem variancia gera razoes enormes)

# ============================================================
# 2. METRICAS E REPOSICIONAMENTO (funcoes puras, testaveis)
# ============================================================

def config_metrics(f0, e, s0, A):
    """Configuracao do combustivel restante (f0 sem as cicatrizes e) numa celula."""
    s1, mx1, n1 = _meff(f0 & ~e)
    split = np.log(s1 / s0) if (s0 > 0 and s1 > 0) else np.nan
    return split, mx1 / A, n1 / (A * 0.09 / 100)

def random_layout(e, f0, rng, tries=TRIES, min_px=MIN_SCAR_PX):
    """Mesmas cicatrizes (forma e area), posicoes ao acaso dentro de f0, sem sobrepor.
    Devolve (mascara nova, n de cicatrizes que nao couberam e ficaram no lugar)."""
    H, W = e.shape
    lab, n = ndimage.label(e, structure=CONN8)
    if n == 0:
        return e.copy(), 0
    objs = ndimage.find_objects(lab)
    sizes = np.bincount(lab.ravel())[1:]
    order = np.argsort(-sizes)                      # maiores primeiro (mais dificeis de encaixar)
    out = np.zeros_like(e)
    fixed_mask = np.zeros_like(e)
    n_fix = 0
    for k in order:
        sl = objs[k]
        shp = lab[sl] == (k + 1)
        h, w = shp.shape
        placed = False
        if sizes[k] >= min_px and h <= H and w <= W:
            r0s = rng.integers(0, H - h + 1, tries)
            c0s = rng.integers(0, W - w + 1, tries)
            for r0, c0 in zip(r0s, c0s):
                tgt = (slice(r0, r0 + h), slice(c0, c0 + w))
                if f0[tgt][shp].all() and not out[tgt][shp].any():
                    out[tgt][shp] = True
                    placed = True
                    break
        if not placed:                               # fica no lugar observado
            fixed_mask[sl] |= shp
            n_fix += 1
    # cicatrizes fixas entram por ultimo; se colidirem com uma reposicionada, a reposicionada perde
    out |= fixed_mask
    return out, n_fix

def null_cell(e, f0, n_null, rng):
    """SES de cada metrica para uma celula. Devolve dict."""
    A = int(f0.sum())
    s0, _, _ = _meff(f0)
    obs = config_metrics(f0, e, s0, A)
    sims, fixes = [], []
    for _ in range(n_null):
        en, nf = random_layout(e, f0, rng)
        sims.append(config_metrics(f0, en, s0, A))
        fixes.append(nf)
    sims = np.array(sims, float)
    out = {"n_cicatrizes_cel": int(ndimage.label(e, structure=CONN8)[1]),
           "n_fixas_media": float(np.mean(fixes))}
    for j, v in enumerate(SES_VARS):
        mu, sd = np.nanmean(sims[:, j]), np.nanstd(sims[:, j], ddof=1)
        out[f"{v}_obs"] = obs[j]
        out[f"{v}_nulo_media"] = mu
        out[f"{v}_nulo_dp"] = sd
        if not np.isfinite(obs[j]) or not np.isfinite(mu):
            ses = np.nan
        elif not (sd > 1e-9):                       # nulo sem variancia: nenhuma posicao muda a metrica
            ses = 0.0 if abs(obs[j] - mu) < 1e-9 else float(np.sign(obs[j] - mu) * SES_CAP)
        else:
            ses = float(np.clip((obs[j] - mu) / sd, -SES_CAP, SES_CAP))
        out[f"{v}_ses"] = ses
        # p de posto medio: empates contam meio (evita p = 1 quando o nulo e igual ao observado)
        out[f"{v}_p_nulo"] = (float(np.mean(sims[:, j] < obs[j]) + 0.5 * np.mean(sims[:, j] == obs[j]))
                              if np.isfinite(obs[j]) else np.nan)
    return out

# ============================================================
# 3. UMA TI-ANO (mesmas mascaras do bloco 08)
# ============================================================

def null_ti_year(ti, year, scheme, cell_m, fuel_mode, seed):
    st = static_of(ti)
    yr = read_raster(ti, year)
    inside = st["ti"] == ti
    queim = inside & fuel_from_cover(yr["cover"], fuel_mode) & (st["barrier"] == 0)
    sm = season_masks(yr["month"], ti, scheme, SEASONS)
    E = sm["inicio"] & queim
    fuel0 = queim & ~sm["antes"]
    cp = int(round(cell_m / PIX_M))
    H, W = queim.shape
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(H // cp):
        for j in range(W // cp):
            sl = (slice(i * cp, (i + 1) * cp), slice(j * cp, (j + 1) * cp))
            q = queim[sl]
            if q.sum() < 0.25 * cp * cp:              # MIN_QUEIMAVEL do bloco 08
                continue
            e, f0 = E[sl], fuel0[sl]
            if not e.any() or f0.sum() == 0:
                continue
            r = null_cell(e, f0, N_NULL, rng)
            r.update({"ti_id": ti, "year": year, "row": i, "col": j})
            rows.append(r)
    return rows

def run_null(scheme=SEASON_MAIN, cell_m=CELL_M, fuel_mode=FUEL_MAIN) -> pd.DataFrame:
    parts = []
    for ti in AMOSTRA:
        p = NULO_DIR / f"nulo_{scheme}_{cell_m}_{FUEL_TAG[fuel_mode]}_ti{ti}_{TAG_YEARS}.parquet"
        if p.exists() and not FORCE_REPROCESS:
            parts.append(pd.read_parquet(p)); continue
        static_of(ti)                                  # carrega uma vez antes de paralelizar
        res = Parallel(n_jobs=N_JOBS, prefer="threads")(
            delayed(null_ti_year)(ti, y, scheme, cell_m, fuel_mode, SEED + 1000 * ti + y) for y in YEARS)
        d = pd.DataFrame([r for rr in res for r in rr])
        d.to_parquet(p, index=False)
        console.print(f"  [dim]{tis.set_index('ti_id').loc[ti, 'ti_name']}: {len(d):,} celulas-ano com cicatriz[/dim]")
        parts.append(d)
    return pd.concat(parts, ignore_index=True)

# ============================================================
# 4. RUN + JUNTA COM AS CELULAS DO bloco 08
# ============================================================

cells_null = {}
for fm in FUEL_RUNS_NULO:
    console.print(f"[cyan]Modelo nulo - {fm}, {N_NULL} replicas por celula-ano[/cyan]")
    nd = run_null(fuel_mode=fm)
    c = pd.read_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[fm]}_{TAG_YEARS}", "parquet"))
    c = c.merge(nd, on=["ti_id", "year", "row", "col"], how="left")
    # celulas sem cicatriz: configuracao indefinida -> SES = 0 (igual ao nulo) + indicador
    c["sem_cicatriz"] = c["conf_split_ses"].isna() & (c["q_inicio"] == 0)
    for v in SES_VARS:
        c[f"{v}_ses_0"] = c[f"{v}_ses"].fillna(0.0)
    c.to_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[fm]}_{TAG_YEARS}_nulo", "parquet"), index=False)
    cells_null[fm] = c

cn = cells_null[FUEL_MAIN]
sub = cn[cn["q_inicio"] > 0].dropna(subset=["conf_split_ses"])
corr = sub[["q_inicio", "conf_split", "conf_lpi", "conf_npatch"] + [f"{v}_ses" for v in SES_VARS]] \
          .corr(method="spearman").loc[["q_inicio"]]
corr.to_csv(stats_path("B07b_correlacao_ses_quantidade"))
console.print("[bold]Spearman com a quantidade: metricas brutas x SES do modelo nulo[/bold]")
display(corr.round(2))
resumo = pd.DataFrame({
    "celulas_ano_com_cicatriz": [len(sub)],
    "frac_mais_fragmentado_que_acaso (p_nulo<=0.05)": [(sub["conf_split_p_nulo"] <= 0.05).mean()],
    "frac_menos_fragmentado_que_acaso (p_nulo>=0.95)": [(sub["conf_split_p_nulo"] >= 0.95).mean()],
    "ses_split_mediana": [sub["conf_split_ses"].median()],
    "cicatrizes_fixas_media": [sub["n_fixas_media"].mean()]})
resumo.to_csv(stats_path("B07b_ses_resumo"), index=False)
display(resumo.round(3))

# ============================================================
# 5. FIGURAS (espaciais, 600 dpi)
# ============================================================

def _save3(fig, nome):
    for ext, kw in [("tif", {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", {}), ("pdf", {})]:
        fig.savefig(fig_path(nome, ext), dpi=600, facecolor="white", **kw)
    plt.show(); plt.close(fig)

# (a) exemplo: uma celula observada x uma replica nula, mesma quantidade
try:
    k = sub.assign(a=lambda d: (d["q_inicio"] - 0.25).abs()).sort_values(["a", "n_cicatrizes_cel"],
                                                                         ascending=[True, False]).iloc[0]
    ti, y, i, j = int(k["ti_id"]), int(k["year"]), int(k["row"]), int(k["col"])
    st, yr = static_of(ti), read_raster(ti, y)
    cp = int(round(CELL_M / PIX_M)); sl = (slice(i * cp, (i + 1) * cp), slice(j * cp, (j + 1) * cp))
    inside = st["ti"] == ti
    queim = inside & fuel_from_cover(yr["cover"], FUEL_MAIN) & (st["barrier"] == 0)
    sm = season_masks(yr["month"], ti, SEASON_MAIN, SEASONS)
    e, f0 = (sm["inicio"] & queim)[sl], (queim & ~sm["antes"])[sl]
    en, _ = random_layout(e, f0, np.random.default_rng(1))
    from matplotlib.colors import ListedColormap
    cm3 = ListedColormap(["#f4f3ef", "#a9cf8f", "#1f5fc8"])
    fig, axs = plt.subplots(1, 2, figsize=(14 / 2.54, 7.4 / 2.54), layout="constrained")
    for ax, ee_, tt in [(axs[0], e, f"Observed (SES = {k['conf_split_ses']:.2f})"),
                        (axs[1], en, "One null layout (same scars, random positions)")]:
        im = np.where(ee_, 2, np.where(f0, 1, 0))
        ax.imshow(im, cmap=cm3, vmin=0, vmax=2, interpolation="nearest")
        ax.add_patch(plt.Rectangle((cp * 0.06, cp * 0.92), 1000 / PIX_M, cp * 0.02, color="black"))
        ax.text(cp * 0.06 + 500 / PIX_M, cp * 0.89, "1 km", ha="center", va="bottom", fontsize=7)
        ax.set_title(tt, fontsize=8); ax.set_axis_off()
    fig.suptitle(f"{tis.set_index('ti_id').loc[ti, 'ti_name']} {y}, {CELL_M / 1000:.2f}-km cell: "
                 f"early scars (blue) {100 * k['q_inicio']:.0f}% of burnable fuel (green)", fontsize=8)
    _save3(fig, "B07b_ses_mapa_exemplo")
except Exception as ex:
    console.print(f"[dim]figura de exemplo pulada: {str(ex)[:100]}[/dim]")

fig, axs = plt.subplots(1, 2, figsize=(14 / 2.54, 6.2 / 2.54), layout="constrained")
axs[0].scatter(sub["q_inicio"], sub["conf_split"], s=2, alpha=0.25, color="#9a9992", rasterized=True)
axs[0].set_xlabel("Early burned fraction"); axs[0].set_ylabel("log(m_eff after / before)")
axs[0].set_title(f"raw: Spearman {corr.loc['q_inicio', 'conf_split']:.2f}", fontsize=8, loc="left")
axs[1].scatter(sub["q_inicio"], sub["conf_split_ses"], s=2, alpha=0.25, color="#1f5fc8", rasterized=True)
axs[1].axhline(0, color="black", lw=0.6)
axs[1].set_xlabel("Early burned fraction"); axs[1].set_ylabel("SES vs null model")
axs[1].set_title(f"null-model SES: Spearman {corr.loc['q_inicio', 'conf_split_ses']:.2f}", fontsize=8, loc="left")
_save3(fig, "B07b_ses_x_quantidade")

console.print("[bold green]OK BLOCO 09 completo: SES gravado nas celulas (*_nulo.parquet).[/bold green]")
