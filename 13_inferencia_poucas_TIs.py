# ======================================================================
# BLOCO 13 - Configuracao alem da quantidade, com inferencia valida para poucas TIs
# Depende dos blocos 00, 09 (celulas com SES) e 10 (segmentos).
# ======================================================================

check_version()

# ============================================================
# BLOCK 9b - Few-cluster inference and null-model configuration
#
# Por que: com 8 TIs, o erro-padrao agrupado por TI (CRV1) subestima a
# incerteza e rejeita demais (Cameron, Gelbach & Miller 2008; MacKinnon &
# Webb 2017). Aqui:
#   CELULA (linear, efeitos fixos de celula e ano):
#     configuracao = SES do modelo nulo (bloco 09), independente da quantidade
#     por construcao; p-valor por WILD CLUSTER BOOTSTRAP com pesos de Webb
#     (6 pontos, recomendado para G < 12), 9999 replicas, cluster = TI;
#     + jackknife por TI (CR3) e previsao deixando uma TI de fora.
#   SEGMENTO (logistico, bordas de cicatriz com resultado definido):
#     configuracao = area e largura da cicatriz + SES da celula onde o
#     segmento esta; EP agrupado (incendio + TI) e EP JACKKNIFE POR TI (CR3);
#     OR deixando cada TI de fora (amplitude). Cicatriz x referencia idem.
#   DETECTABILIDADE: o modelo de segmento e refeito com o estado da faixa
#     interna (NBR antes, nbr_pre_int) e o tempo desde a cicatriz (gap_meses)
#     como covariaveis: se a configuracao so "funciona" pelo NBR, ela some.
#
# Criterio de evidencia (proposta, item 7), agora com inferencia de poucos
# clusters: associacao (p do wild bootstrap ou IC jackknife < 0,05), melhora do
# ajuste e da previsao fora da amostra, no sentido esperado.
#
# Output: 04_stats/B09b_*.csv | 05_figures/B09b_efeitos.{tif,png,pdf} (600 dpi)
# ============================================================

import subprocess, sys
try:
    import wildboottest  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "wildboottest"], check=True)
import pyfixest as pf
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

# ============================================================
# 1. PARAMETERS
# ============================================================

TAG_SEG   = globals().get("TAG_SEG", f"{TAG_YEARS}_md")
B_WILD    = 9999
SEED      = 11
CELL_REF  = ["q_inicio", "q_inicio_viz", "q_ant1", "q_ant2", "pastagem", "agricultura", "vpd_resto", "chuva_seca"]
CELL_SES  = ["conf_split_ses_0", "conf_lpi_ses_0", "conf_npatch_ses_0"]
SEG_REF   = ["q_inicio_win", "q_ant1_win", "q_ant2_win", "pastagem_win", "agricultura_win", "decl_ext",
             "barreira_win", "rios_win", "P_vpd_max", "P_wind", "P_rh_min"]
SEG_CONF  = ["log_area_cicatriz", "largura_local_100m", "ses_cel_split"]
SEG_DETEC = ["nbr_pre_int", "gap_meses"]
EXPECT    = {"conf_split_ses_0": +1, "conf_lpi_ses_0": +1, "conf_npatch_ses_0": -1,   # celula: y_resto
             "log_area_cicatriz": +1, "largura_local_100m": +1, "ses_cel_split": -1}  # segmento: OR interrupcao

def zscore(d, cols):
    d = d.copy()
    for c in cols:
        s = d[c].std()
        d[c] = (d[c] - d[c].mean()) / s if s and s > 0 else 0.0
    return d

def jackknife_ti(fit_fn, d, names):
    """CR3: re-estima deixando cada TI de fora. Devolve EP jackknife e amplitude dos coeficientes."""
    ids = sorted(d["ti_id"].unique()); G = len(ids)
    B = []
    for t in ids:
        try:
            b = fit_fn(d[d["ti_id"] != t])
            B.append([b.get(n, np.nan) for n in names])
        except Exception:
            B.append([np.nan] * len(names))
    B = np.array(B, float)
    mu = np.nanmean(B, axis=0)
    se = np.sqrt((G - 1) / G * np.nansum((B - mu) ** 2, axis=0))
    return se, np.nanmin(B, axis=0), np.nanmax(B, axis=0)

# ============================================================
# 2. CELULA - SES DO MODELO NULO + WILD CLUSTER BOOTSTRAP
# ============================================================

cells = pd.read_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[FUEL_MAIN]}_{TAG_YEARS}_nulo", "parquet"))
cells["sem_cicatriz"] = cells["sem_cicatriz"].astype(float)
dc = cells.dropna(subset=["y_resto"] + CELL_REF + CELL_SES).copy()
dc = zscore(dc, CELL_REF + CELL_SES)
f_ref  = "y_resto ~ " + " + ".join(CELL_REF + ["sem_cicatriz"]) + " | cell_id + year"
f_conf = "y_resto ~ " + " + ".join(CELL_REF + ["sem_cicatriz"] + CELL_SES) + " | cell_id + year"
m_ref  = pf.feols(f_ref, data=dc, vcov={"CRV1": "ti_id"})
m_conf = pf.feols(f_conf, data=dc, vcov={"CRV1": "ti_id"})

cell_rows = []
for v in CELL_SES:
    try:
        wb = m_conf.wildboottest(param=v, reps=B_WILD, cluster="ti_id", weights_type="webb", seed=SEED)
        p_wild = float(wb["Pr(>|t|)"]) if "Pr(>|t|)" in wb else float(wb.iloc[-1])
    except Exception as e:
        console.print(f"[yellow]wild bootstrap falhou para {v}: {str(e)[:100]}[/yellow]"); p_wild = np.nan
    cell_rows.append({"variavel": v, "coef_pp_por_dp": 100 * float(m_conf.coef()[v]),
                      "ep_crv1_pp": 100 * float(m_conf.se()[v]), "p_crv1": float(m_conf.pvalue()[v]),
                      "p_wild_webb": p_wild})
cell_tab = pd.DataFrame(cell_rows).set_index("variavel")

def _fit_cell_coefs(d_):
    return pf.feols(f_conf, data=d_, vcov="iid").coef().to_dict()
se_jk, lo_jk, hi_jk = jackknife_ti(_fit_cell_coefs, dc, CELL_SES)
cell_tab["ep_jackknife_TI_pp"] = 100 * se_jk
cell_tab["min_deixando_1_TI_pp"], cell_tab["max_deixando_1_TI_pp"] = 100 * lo_jk, 100 * hi_jk
cell_tab["sinal_esperado"] = [EXPECT[v] for v in cell_tab.index]

# previsao fora da TI (sem efeito fixo de celula; com relevo/barreira e ano)
pool = CELL_REF + ["sem_cicatriz", "declividade", "barreira", "rios"]
dp = zscore(dc.dropna(subset=["declividade", "barreira", "rios"]), ["declividade", "barreira", "rios"])
Yd = pd.get_dummies(dp["year"].astype(str), drop_first=True).astype(float).to_numpy()
err = {"ref": [], "conf": []}
for t in sorted(dp["ti_id"].unique()):
    tr_, te_ = (dp["ti_id"] != t).to_numpy(), (dp["ti_id"] == t).to_numpy()
    for k, xs in [("ref", pool), ("conf", pool + CELL_SES)]:
        X = np.c_[np.ones(len(dp)), dp[xs].to_numpy(), Yd]
        b, *_ = np.linalg.lstsq(X[tr_], dp["y_resto"].to_numpy()[tr_], rcond=None)
        err[k].append((dp["y_resto"].to_numpy()[te_] - X[te_] @ b) ** 2)
rmse = {k: float(np.sqrt(np.concatenate(v).mean())) for k, v in err.items()}
def _r2w(m):
    v = getattr(m, "_r2_within", None)
    return float(v) if v is not None else np.nan
cell_summ = {"n": len(dc), "n_TIs": dc["ti_id"].nunique(), "r2_within_ref": _r2w(m_ref),
             "r2_within_conf": _r2w(m_conf), "rmse_fora_TI_ref": rmse["ref"],
             "rmse_fora_TI_conf": rmse["conf"], "ganho_previsao_%": 100 * (rmse["ref"] - rmse["conf"]) / rmse["ref"]}
cell_tab.to_csv(stats_path("B09b_celula_ses_coeficientes"))
pd.DataFrame([cell_summ]).to_csv(stats_path("B09b_celula_ses_resumo"), index=False)
console.print("[bold]CELULA - configuracao pelo modelo nulo (p.p. de area queimada depois por 1 DP de SES)[/bold]")
display(cell_tab.round(4)); display(pd.DataFrame([cell_summ]).round(4))

# ============================================================
# 3. SEGMENTO - SES DA CELULA NO SEGMENTO + JACKKNIFE POR TI
# ============================================================

segs = pd.read_parquet(cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[FUEL_MAIN]}_{TAG_SEG}", "parquet"))
size = CELL_M
orig = (cells.assign(c0=lambda d: d["x"] - (d["col"] + 0.5) * size, f0=lambda d: d["y"] + (d["row"] + 0.5) * size)
             .groupby("ti_id")[["c0", "f0"]].median())
segs = segs.merge(orig, left_on="ti_id", right_index=True, how="left")
segs["row"] = np.floor((segs["f0"] - segs["y"]) / size).astype("Int64")
segs["col"] = np.floor((segs["x"] - segs["c0"]) / size).astype("Int64")
segs = segs.merge(cells[["ti_id", "year", "row", "col", "conf_split_ses_0"]].rename(
    columns={"conf_split_ses_0": "ses_cel_split"}).astype({"row": "Int64", "col": "Int64"}),
    on=["ti_id", "year", "row", "col"], how="left")

def prep(segs):
    d = segs[segs["resultado"].isin(["interrupcao", "continuidade"])].copy()
    d["interrupcao"] = (d["resultado"] == "interrupcao").astype(int)
    d["cicatriz"] = (d["tipo_seg"] == "cicatriz").astype(int)
    d["log_area_cicatriz"] = np.log(d["area_cicatriz_ha"].clip(lower=0.09))
    d["largura_local_100m"] = d["largura_local_m"] / 100
    sem_id = d["fire_id"].astype(str).str.contains("_v")
    d["fire_id"] = np.where(sem_id, d["ti_id"].astype(str) + "_" + d["year"].astype(str) + "_semid", d["fire_id"])
    return d

def glm_fit(formula, d, cluster=True):
    m = smf.glm(formula, data=d, family=sm.families.Binomial())
    if not cluster:
        return m.fit()
    g = np.column_stack([pd.factorize(d["fire_id"])[0], pd.factorize(d["ti_id"])[0]])
    try:
        return m.fit(cov_type="cluster", cov_kwds={"groups": g})
    except Exception:
        return m.fit(cov_type="cluster", cov_kwds={"groups": g[:, 1]})

def or_table(m, d, formula, names, label):
    se_jk, lo, hi = jackknife_ti(lambda d_: glm_fit(formula, d_, cluster=False).params.to_dict(), d, names)
    b = m.params[names]
    return pd.DataFrame({"modelo": label, "or_1dp": np.exp(b),
                         "ic95_cluster_inf": np.exp(m.conf_int().loc[names, 0]),
                         "ic95_cluster_sup": np.exp(m.conf_int().loc[names, 1]),
                         "ic95_jackknife_TI_inf": np.exp(b - 1.96 * se_jk),
                         "ic95_jackknife_TI_sup": np.exp(b + 1.96 * se_jk),
                         "or_min_deixando_1_TI": np.exp(lo), "or_max_deixando_1_TI": np.exp(hi),
                         "sinal_esperado": [EXPECT.get(n, 0) for n in names]}, index=names)

d = prep(segs)
seg_tabs = []

# (a) cicatriz x referencia
da = zscore(d.dropna(subset=SEG_REF), SEG_REF)
fa = "interrupcao ~ cicatriz + " + " + ".join(SEG_REF) + " + C(year)"
ma = glm_fit(fa, da)
seg_tabs.append(or_table(ma, da, fa, ["cicatriz"], "cicatriz x referencia"))
# (a2) o mesmo, ajustado pelo estado da faixa interna (a deteccao depende dele)
da2 = zscore(da.dropna(subset=["nbr_pre_int"]), ["nbr_pre_int"])
fa2 = fa + " + nbr_pre_int"
seg_tabs.append(or_table(glm_fit(fa2, da2), da2, fa2, ["cicatriz"], "cicatriz x referencia | + NBR antes"))

# (b) so bordas de cicatriz: referencia x + configuracao (+ deteccao)
sc = d[d["cicatriz"] == 1].dropna(subset=SEG_REF + SEG_CONF + SEG_DETEC).copy()
sc = zscore(sc, SEG_REF + SEG_CONF + SEG_DETEC)
fb_ref  = "interrupcao ~ " + " + ".join(SEG_REF) + " + C(year)"
fb_conf = "interrupcao ~ " + " + ".join(SEG_REF + SEG_CONF) + " + C(year)"
fb_det  = "interrupcao ~ " + " + ".join(SEG_REF + SEG_CONF + SEG_DETEC) + " + C(year)"
mb_ref, mb_conf, mb_det = glm_fit(fb_ref, sc), glm_fit(fb_conf, sc), glm_fit(fb_det, sc)
seg_tabs.append(or_table(mb_conf, sc, fb_conf, SEG_CONF, "cicatriz | configuracao"))
seg_tabs.append(or_table(mb_det, sc, fb_det, SEG_CONF + SEG_DETEC, "cicatriz | configuracao + deteccao"))
seg_tab = pd.concat(seg_tabs)

def cv(d_, f_list, splitter, groups):
    preds = {k: np.full(len(d_), np.nan) for k in f_list}
    for tr_, te_ in splitter.split(d_, d_["interrupcao"], groups):
        for k, f in f_list.items():
            try:
                preds[k][te_] = smf.glm(f, data=d_.iloc[tr_], family=sm.families.Binomial()).fit().predict(d_.iloc[te_])
            except Exception:
                pass
    ok = np.all([~np.isnan(p) for p in preds.values()], axis=0)
    y = d_["interrupcao"].to_numpy()[ok]
    return {k: {"logloss": log_loss(y, np.clip(p[ok], 1e-6, 1 - 1e-6)),
                "auc": roc_auc_score(y, p[ok]) if len(np.unique(y)) > 1 else np.nan} for k, p in preds.items()}

scr = sc.reset_index(drop=True)
fl = {"ref": fb_ref, "conf": fb_conf}
cv_f = cv(scr, fl, GroupKFold(5), scr["fire_id"].to_numpy())
cv_t = cv(scr, fl, LeaveOneGroupOut(), scr["ti_id"].to_numpy())
seg_summ = {"n_segmentos": len(sc), "n_incendios": sc["fire_id"].nunique(), "n_TIs": sc["ti_id"].nunique(),
            "aic_ref": mb_ref.aic, "aic_conf": mb_conf.aic,
            "logloss_incendios_fora_ref": cv_f["ref"]["logloss"], "logloss_incendios_fora_conf": cv_f["conf"]["logloss"],
            "logloss_TI_fora_ref": cv_t["ref"]["logloss"], "logloss_TI_fora_conf": cv_t["conf"]["logloss"],
            "auc_TI_fora_ref": cv_t["ref"]["auc"], "auc_TI_fora_conf": cv_t["conf"]["auc"]}
seg_tab.to_csv(stats_path("B09b_segmento_or_jackknife"))
pd.DataFrame([seg_summ]).to_csv(stats_path("B09b_segmento_resumo"), index=False)
console.print("[bold]SEGMENTO - razoes de chances com IC por cluster e por jackknife de TI[/bold]")
display(seg_tab.round(3)); display(pd.DataFrame([seg_summ]).round(4))

# ============================================================
# 4. CRITERIO DE EVIDENCIA (inferencia de poucos clusters)
# ============================================================

def _sig_dir_cell(v):
    r = cell_tab.loc[v]
    return (r["p_wild_webb"] < 0.05) and (np.sign(r["coef_pp_por_dp"]) == r["sinal_esperado"])

def _sig_dir_seg(v, label="cicatriz | configuracao"):
    r = seg_tab[(seg_tab["modelo"] == label)].loc[v]
    lo, hi = r["ic95_jackknife_TI_inf"], r["ic95_jackknife_TI_sup"]
    return ((lo > 1) or (hi < 1)) and (np.sign(np.log(r["or_1dp"])) == r["sinal_esperado"])

verd = pd.DataFrame([
    {"escala": "celula", "medida": v, "associada_no_sentido_esperado (wild p<0,05)": _sig_dir_cell(v),
     "melhora_ajuste": cell_summ["r2_within_conf"] > cell_summ["r2_within_ref"],
     "melhora_previsao_fora_TI": cell_summ["ganho_previsao_%"] > 0} for v in CELL_SES] + [
    {"escala": "segmento", "medida": v, "associada_no_sentido_esperado (jackknife TI)": _sig_dir_seg(v),
     "robusta_a_deteccao": _sig_dir_seg(v, "cicatriz | configuracao + deteccao"),
     "melhora_ajuste": seg_summ["aic_conf"] < seg_summ["aic_ref"],
     "melhora_previsao_fora_TI": seg_summ["logloss_TI_fora_conf"] < seg_summ["logloss_TI_fora_ref"]} for v in SEG_CONF])
verd.to_csv(stats_path("B09b_criterio_evidencia"), index=False)
console.print("[bold]Criterio de evidencia com inferencia valida para 8 TIs[/bold]")
display(verd)

# ============================================================
# 5. FIGURA (600 dpi): efeitos com os dois tipos de IC
# ============================================================

LAB = {"conf_split_ses_0": "Fragmentation SES", "conf_lpi_ses_0": "Largest-patch SES",
       "conf_npatch_ses_0": "N patches SES", "log_area_cicatriz": "Scar area (log)",
       "largura_local_100m": "Local scar width", "ses_cel_split": "Cell fragmentation SES",
       "nbr_pre_int": "Inner-strip NBR before", "gap_meses": "Months since scar"}
fig, axs = plt.subplots(1, 2, figsize=(17 / 2.54, 6.5 / 2.54), layout="constrained")
ax = axs[0]; y = np.arange(len(cell_tab))[::-1]
ax.axvline(0, color="black", lw=0.6, ls="--")
ax.errorbar(cell_tab["coef_pp_por_dp"], y, xerr=1.96 * cell_tab["ep_jackknife_TI_pp"], fmt="o", color="#1f5fc8", capsize=2)
for yi, (v, r) in zip(y, cell_tab.iterrows()):
    ax.text(r["coef_pp_por_dp"], yi + 0.25, f"wild p = {r['p_wild_webb']:.3f}", fontsize=6, ha="center")
ax.set_yticks(y); ax.set_yticklabels([LAB[v] for v in cell_tab.index], fontsize=7)
ax.set_xlabel("Later burned area (p.p.) per SD"); ax.set_title(f"(a) {CELL_M / 1000:.1f}-km cells", fontsize=8, loc="left")
ax = axs[1]
t = seg_tab[seg_tab["modelo"] == "cicatriz | configuracao + deteccao"]
y = np.arange(len(t))[::-1]
ax.axvline(1, color="black", lw=0.6, ls="--")
ax.errorbar(t["or_1dp"], y, xerr=[t["or_1dp"] - t["ic95_jackknife_TI_inf"], t["ic95_jackknife_TI_sup"] - t["or_1dp"]],
            fmt="o", color="#1f5fc8", capsize=2, label="jackknife by IL")
ax.errorbar(t["or_1dp"], y - 0.18, xerr=[t["or_1dp"] - t["ic95_cluster_inf"], t["ic95_cluster_sup"] - t["or_1dp"]],
            fmt="none", ecolor="#9a9992", capsize=2, label="clustered (fire + IL)")
ax.set_xscale("log"); ax.set_yticks(y); ax.set_yticklabels([LAB.get(v, v) for v in t.index], fontsize=7)
ax.set_xlabel("Odds of interruption per SD"); ax.legend(fontsize=6, frameon=False)
ax.set_title("(b) scar edges, adjusted for detectability", fontsize=8, loc="left")
for ext, kw in [("tif", {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", {}), ("pdf", {})]:
    fig.savefig(fig_path("B09b_efeitos", ext), dpi=600, facecolor="white", **kw)
plt.show(); plt.close(fig)

console.print("[bold green]OK BLOCO 13 completo.[/bold green]")
