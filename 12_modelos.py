# ======================================================================
# BLOCO 12 - Modelos: referencia (quantidade) x referencia + configuracao
# Depende do bloco 00 e dos checkpoints dos blocos 08 (celulas) e 10 (segmentos).
# ======================================================================
#
# Hipotese: com quantidade queimada antes, vegetacao, relevo, tempo e barreiras
# comparaveis, cicatrizes que fragmentam mais o combustivel estao associadas a
# MENOS continuidade do fogo posterior.
#
# ESCALA 1 - CELULA (bloco 08, 4980 m): y_resto e y_cont
#   REFERENCIA: q_inicio + q_inicio_viz + q_ant1 + q_ant2 + pastagem + agricultura
#               + vpd_resto + chuva_seca | celula + ano
#   + CONFIG  : conf_lpi + conf_npatch (bruta e residual); m_eff/borda so residuais
#   Wald do bloco, R2 within, previsao deixando uma TI de fora.
# ESCALA 2 - SEGMENTO (bloco 10; interrupcao x continuidade)
#   (a) borda de cicatriz x borda de referencia (pseudo-cicatriz)
#   (b) so cicatrizes: referencia x + configuracao (fragmentacao e maior mancha
#       na janela de ~1 km, area e largura local da cicatriz)
#   EP agrupado por incendio e TI; validacao cruzada deixando incendios / TIs de fora.
# A inferencia valida para 8 TIs (wild bootstrap, jackknife) esta no bloco 13.
#
# Output: 04_stats/B09_*.csv
# ======================================================================

check_version()

import pyfixest as pf
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

REGRA_PRINCIPAL = "simetrica (Landsat + MODIS)"
REGRA_SENS      = "antiga (MapBiomas na referencia)"

CELL_REF  = ["q_inicio", "q_inicio_viz", "q_ant1", "q_ant2", "pastagem", "agricultura", "vpd_resto", "chuva_seca"]
CELL_CONF = ["conf_lpi", "conf_npatch"]
CELL_CONF_ALT = ["conf_split_res", "conf_borda_res"]
CELL_POOL_EXTRA = ["declividade", "barreira", "rios"]
SEG_REF  = ["q_inicio_win", "q_ant1_win", "q_ant2_win", "pastagem_win", "agricultura_win", "decl_ext",
            "barreira_win", "rios_win", "P_vpd_max", "P_wind", "P_rh_min"]
SEG_CONF = ["conf_split_win", "conf_lpi_win", "log_area_cicatriz", "largura_local_100m"]
N_FOLDS  = 5

# ============================================================
# 1. CELULA
# ============================================================

def demean_twoway(M, g1, g2, tol=1e-10, maxit=2000):
    M = M.astype(float).copy()
    n1, n2 = g1.max() + 1, g2.max() + 1
    c1, c2 = np.bincount(g1, minlength=n1), np.bincount(g2, minlength=n2)
    for _ in range(maxit):
        old = M.copy()
        for j in range(M.shape[1]):
            M[:, j] -= (np.bincount(g1, M[:, j], n1) / c1)[g1]
            M[:, j] -= (np.bincount(g2, M[:, j], n2) / c2)[g2]
        if np.max(np.abs(M - old)) < tol:
            break
    return M

def r2_within(d, y, xs):
    g1 = pd.factorize(d["cell_id"])[0]; g2 = pd.factorize(d["year"])[0]
    Z = demean_twoway(d[[y] + xs].to_numpy(), g1, g2)
    yy, X = Z[:, 0], Z[:, 1:]
    b, *_ = np.linalg.lstsq(X, yy, rcond=None)
    return 1 - ((yy - X @ b) ** 2).sum() / (yy ** 2).sum()

def wald_block(names, b, V, block):
    idx = [names.index(v) for v in block if v in names]
    bb, VV = b[idx], V[np.ix_(idx, idx)]
    chi = float(bb @ np.linalg.pinv(VV) @ bb)
    return chi, len(idx), float(stats.chi2.sf(chi, len(idx)))

def zscore(d, cols):
    d = d.copy()
    for c in cols:
        s = d[c].std()
        d[c] = (d[c] - d[c].mean()) / s if s and s > 0 else 0.0
    return d

def fit_cells(cells, outcome="y_resto", conf=CELL_CONF, label=""):
    d = cells.dropna(subset=[outcome] + CELL_REF + conf).copy()
    d = zscore(d, CELL_REF + conf)
    m_conf = pf.feols(f"{outcome} ~ " + " + ".join(CELL_REF + conf) + " | cell_id + year", data=d,
                      vcov={"CRV1": "ti_id"})
    names = list(m_conf._coefnames)
    b = m_conf.coef().reindex(names).to_numpy(); V = np.asarray(m_conf._vcov)
    chi, k, p = wald_block(names, b, V, conf)
    tid = m_conf.tidy()
    coefs = tid.loc[[c for c in conf if c in tid.index]].copy()
    coefs.insert(0, "modelo", label or outcome)
    r2r, r2c = r2_within(d, outcome, CELL_REF), r2_within(d, outcome, CELL_REF + conf)
    pool = CELL_REF + CELL_POOL_EXTRA
    dp = zscore(d.dropna(subset=CELL_POOL_EXTRA).copy(), CELL_POOL_EXTRA)
    Yd = pd.get_dummies(dp["year"].astype(str), prefix="a", drop_first=True).astype(float)
    err = {"ref": [], "conf": []}
    for ti in sorted(dp["ti_id"].unique()):
        tr, te = dp["ti_id"] != ti, dp["ti_id"] == ti
        for k_, xs in [("ref", pool), ("conf", pool + conf)]:
            X = np.c_[np.ones(len(dp)), dp[xs].to_numpy(), Yd.to_numpy()]
            bb, *_ = np.linalg.lstsq(X[tr.to_numpy()], dp.loc[tr, outcome], rcond=None)
            err[k_].append(((dp.loc[te, outcome] - X[te.to_numpy()] @ bb) ** 2).to_numpy())
    rmse_r = float(np.sqrt(np.concatenate(err["ref"]).mean()))
    rmse_c = float(np.sqrt(np.concatenate(err["conf"]).mean()))
    summ = {"modelo": label or outcome, "n": len(d), "n_celulas": d["cell_id"].nunique(),
            "n_TIs": d["ti_id"].nunique(), "r2_within_ref": r2r, "r2_within_conf": r2c,
            "ganho_r2_within": r2c - r2r, "wald_chi2_conf": chi, "wald_gl": k, "wald_p": p,
            "rmse_fora_TI_ref": rmse_r, "rmse_fora_TI_conf": rmse_c,
            "ganho_previsao_fora_TI_%": 100 * (rmse_r - rmse_c) / rmse_r}
    return summ, coefs

# ============================================================
# 2. SEGMENTO
# ============================================================

def prep_segments(segs):
    d = segs[segs["resultado"].isin(["interrupcao", "continuidade"])].copy()
    d["interrupcao"] = (d["resultado"] == "interrupcao").astype(int)
    d["cicatriz"] = (d["tipo_seg"] == "cicatriz").astype(int)
    d["log_area_cicatriz"] = np.log(d["area_cicatriz_ha"].clip(lower=0.09))
    d["largura_local_100m"] = d["largura_local_m"] / 100
    d["ano"] = pd.Categorical(d["year"], categories=sorted(d["year"].unique()))
    sem_id = d["fire_id"].astype(str).str.contains("_v")
    d["fire_id"] = np.where(sem_id, d["ti_id"].astype(str) + "_" + d["year"].astype(str) + "_semid", d["fire_id"])
    return d

def glm_cluster(formula, d):
    m = smf.glm(formula, data=d, family=sm.families.Binomial())
    g = np.column_stack([pd.factorize(d["fire_id"])[0], pd.factorize(d["ti_id"])[0]])
    try:
        return m.fit(cov_type="cluster", cov_kwds={"groups": g}), "incendio + TI"
    except Exception:
        return m.fit(cov_type="cluster", cov_kwds={"groups": g[:, 1]}), "TI"

def cv_scores(d, xs_ref, xs_conf, splitter, groups):
    out = {"ref": np.full(len(d), np.nan), "conf": np.full(len(d), np.nan)}
    for tr, te in splitter.split(d, d["interrupcao"], groups):
        dtr, dte = d.iloc[tr], d.iloc[te]
        if dtr["interrupcao"].nunique() < 2:
            continue
        for k, xs in [("ref", xs_ref), ("conf", xs_conf)]:
            try:
                m = smf.glm("interrupcao ~ " + " + ".join(xs) + " + C(ano)", data=dtr,
                            family=sm.families.Binomial()).fit()
                out[k][te] = m.predict(dte).to_numpy()
            except Exception:
                pass
    ok = ~np.isnan(out["ref"]) & ~np.isnan(out["conf"])
    y = d["interrupcao"].to_numpy()[ok]
    res = {}
    for k in ["ref", "conf"]:
        p = np.clip(out[k][ok], 1e-6, 1 - 1e-6)
        res[k] = {"log_loss": log_loss(y, p), "brier": brier_score_loss(y, p),
                  "auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan}
    return res, int(ok.sum())

def fit_segments(segs, conf=SEG_CONF, label=""):
    d = prep_segments(segs)
    sc = zscore(d[d["cicatriz"] == 1].dropna(subset=SEG_REF + conf).copy(), SEG_REF + conf)
    m_ref, cl = glm_cluster("interrupcao ~ " + " + ".join(SEG_REF) + " + C(ano)", sc)
    m_conf, _ = glm_cluster("interrupcao ~ " + " + ".join(SEG_REF + conf) + " + C(ano)", sc)
    w = m_conf.wald_test(", ".join(f"{v} = 0" for v in conf), scalar=True)
    coefs = pd.DataFrame({"modelo": label or "segmento", "coef": m_conf.params[conf],
                          "razao_chances_1dp": np.exp(m_conf.params[conf]),
                          "ic95_inf": np.exp(m_conf.conf_int().loc[conf, 0]),
                          "ic95_sup": np.exp(m_conf.conf_int().loc[conf, 1]),
                          "p": m_conf.pvalues[conf]})
    cv_f, _ = cv_scores(sc.reset_index(drop=True), SEG_REF, SEG_REF + conf,
                        GroupKFold(n_splits=N_FOLDS), sc["fire_id"].to_numpy())
    cv_t, _ = cv_scores(sc.reset_index(drop=True), SEG_REF, SEG_REF + conf,
                        LeaveOneGroupOut(), sc["ti_id"].to_numpy())
    summ = {"modelo": label or "segmento", "n_segmentos": len(sc), "n_incendios": sc["fire_id"].nunique(),
            "n_TIs": sc["ti_id"].nunique(), "prop_interrupcao": sc["interrupcao"].mean(),
            "agrupamento_EP": cl, "aic_ref": m_ref.aic, "aic_conf": m_conf.aic,
            "wald_chi2_conf": float(w.statistic), "wald_p": float(w.pvalue),
            "cv_incendio_logloss_ref": cv_f["ref"]["log_loss"], "cv_incendio_logloss_conf": cv_f["conf"]["log_loss"],
            "cv_incendio_auc_ref": cv_f["ref"]["auc"], "cv_incendio_auc_conf": cv_f["conf"]["auc"],
            "cv_TI_logloss_ref": cv_t["ref"]["log_loss"], "cv_TI_logloss_conf": cv_t["conf"]["log_loss"],
            "cv_TI_auc_ref": cv_t["ref"]["auc"], "cv_TI_auc_conf": cv_t["conf"]["auc"],
            "cv_TI_brier_ref": cv_t["ref"]["brier"], "cv_TI_brier_conf": cv_t["conf"]["brier"]}
    return summ, coefs

def fit_scar_vs_reference(segs):
    d = zscore(prep_segments(segs).dropna(subset=SEG_REF), SEG_REF)
    m, cl = glm_cluster("interrupcao ~ cicatriz + " + " + ".join(SEG_REF) + " + C(ano)", d)
    return {"n": len(d), "n_cicatriz": int(d["cicatriz"].sum()), "n_referencia": int((1 - d["cicatriz"]).sum()),
            "prop_interrupcao_cicatriz": d.loc[d["cicatriz"] == 1, "interrupcao"].mean(),
            "prop_interrupcao_referencia": d.loc[d["cicatriz"] == 0, "interrupcao"].mean(),
            "razao_chances_cicatriz": float(np.exp(m.params["cicatriz"])),
            "ic95_inf": float(np.exp(m.conf_int().loc["cicatriz", 0])),
            "ic95_sup": float(np.exp(m.conf_int().loc["cicatriz", 1])),
            "p": float(m.pvalues["cicatriz"]), "agrupamento_EP": cl}

# ============================================================
# 3. RUN - as duas definicoes de combustivel
# ============================================================

cell_rows, cell_coefs, seg_rows, seg_coefs_all, ref_rows = [], [], [], [], []
seg_sens_rows, seg_sens_coefs, seg_corr = [], [], []
for fm in FUEL_RUNS:
    cells = residualize_conf(pd.read_parquet(cache_path(f"celulas_{SEASON_MAIN}_{CELL_M}_{FUEL_TAG[fm]}_{TAG_YEARS}", "parquet")),
                             ["conf_split", "conf_lpi", "conf_borda", "conf_npatch"])
    segs = pd.read_parquet(cache_path(f"segmentos_{SEASON_MAIN}_s300_f90_a30_{FUEL_TAG[fm]}_{TAG_SEG}", "parquet"))

    for outcome in ["y_resto", "y_cont"]:
        for conf, lab in [(CELL_CONF, "bruta"), ([f"{c}_res" for c in CELL_CONF], "sem quantidade"),
                          (CELL_CONF_ALT, "m_eff e borda sem quantidade")]:
            s_, c_ = fit_cells(cells, outcome, conf, f"{outcome} | config {lab}")
            s_["combustivel"] = fm
            cell_rows.append(s_); cell_coefs.append(c_.assign(combustivel=fm))

    r_ = fit_scar_vs_reference(segs); r_.update(combustivel=fm, regra=REGRA_PRINCIPAL); ref_rows.append(r_)
    r_ = fit_scar_vs_reference(segs.assign(resultado=segs["resultado_mb"]))
    r_.update(combustivel=fm, regra=REGRA_SENS); ref_rows.append(r_)

    s_, c_ = fit_segments(segs, SEG_CONF, "segmento | config")
    s_["combustivel"] = fm
    seg_rows.append(s_); seg_coefs_all.append(c_.assign(combustivel=fm))
    for conf, lab in [(["conf_split_win", "conf_lpi_win"], "segmento | so paisagem (sem area/largura)"),
                      (["log_area_cicatriz", "largura_local_100m"], "segmento | so cicatriz (area/largura)")]:
        s2, c2 = fit_segments(segs, conf, lab)
        s2["combustivel"] = fm
        seg_sens_rows.append(s2); seg_sens_coefs.append(c2.assign(combustivel=fm))
    dc = prep_segments(segs); dc = dc[dc["cicatriz"] == 1]
    seg_corr.append(dc[["q_inicio_win"] + SEG_CONF].corr(method="spearman").round(2).assign(combustivel=fm))

cell_summary = pd.DataFrame(cell_rows); cell_coefs = pd.concat(cell_coefs)
ref_vs = pd.DataFrame(ref_rows)
seg_summary = pd.DataFrame(seg_rows); seg_coefs = pd.concat(seg_coefs_all)
pd.DataFrame(seg_sens_rows).to_csv(stats_path("B09_segmento_sensibilidade_resumo"), index=False)
pd.concat(seg_sens_coefs).to_csv(stats_path("B09_segmento_sensibilidade_coeficientes"))
pd.concat(seg_corr).to_csv(stats_path("B09_segmento_correlacoes"))
cell_summary.to_csv(stats_path("B09_celula_resumo"), index=False)
cell_coefs.to_csv(stats_path("B09_celula_coeficientes"))
ref_vs.to_csv(stats_path("B09_cicatriz_vs_referencia"), index=False)
seg_summary.to_csv(stats_path("B09_segmento_resumo"), index=False)
seg_coefs.to_csv(stats_path("B09_segmento_coeficientes"))

console.print("[bold]CELULA[/bold]"); display(cell_summary.set_index(["combustivel", "modelo"]).round(4))
console.print("[bold]SEGMENTO (a): cicatriz x referencia[/bold]"); display(ref_vs.set_index(["combustivel", "regra"]).round(3))
console.print("[bold]SEGMENTO (b): referencia x configuracao[/bold]"); display(seg_summary.set_index("combustivel").T.round(4))
display(seg_coefs.round(3))

# ============================================================
# 4. CRITERIO DE EVIDENCIA (proposta, item 7)
# ============================================================

vrows = []
for fm in FUEL_RUNS:
    c_main = cell_summary[(cell_summary["combustivel"] == fm) & (cell_summary["modelo"] == "y_resto | config bruta")].iloc[0]
    s_main = seg_summary[seg_summary["combustivel"] == fm].iloc[0]
    vrows += [
        {"combustivel": fm, "escala": "celula",
         "configuracao associada (Wald p < 0,05)": c_main["wald_p"] < 0.05,
         "melhora o ajuste": c_main["ganho_r2_within"] > 0,
         "melhora a previsao fora da amostra": c_main["ganho_previsao_fora_TI_%"] > 0},
        {"combustivel": fm, "escala": "segmento",
         "configuracao associada (Wald p < 0,05)": s_main["wald_p"] < 0.05,
         "melhora o ajuste": s_main["aic_conf"] < s_main["aic_ref"],
         "melhora a previsao fora da amostra": bool((s_main["cv_incendio_logloss_conf"] < s_main["cv_incendio_logloss_ref"])
                                                    and (s_main["cv_TI_logloss_conf"] < s_main["cv_TI_logloss_ref"]))}]
verdict = pd.DataFrame(vrows)
verdict.to_csv(stats_path("B09_criterio_evidencia"), index=False)
display(verdict)
console.print("[bold green]OK BLOCO 12 completo.[/bold green]")
