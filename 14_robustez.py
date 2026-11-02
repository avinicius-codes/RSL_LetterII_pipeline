# ======================================================================
# BLOCO 14 - Robustez: recorte sazonal, escala, criterios dos encontros, combustivel
# Depende das FUNCOES dos blocos 08, 10 e 12 (rode-os nesta sessao antes).
# ======================================================================
#
# Refaz as analises mudando UMA coisa de cada vez:
#   (1) recorte sazonal : artigo1 (principal) | local (60 mm) | local_100 (100 mm)
#   (2) escala (celula) : 2490 | 4980 (principal) | 9990 m
#   (3) encontros       : segmento 150/600 m; faixa 60/150 m; chegada 20%/50%
#   (4) combustivel     : todos os vegetados (principal) | natural + pastagem | so natural
# Para cada variante: n, teste do bloco de configuracao, ganho de ajuste/previsao
# e o coeficiente da configuracao (celula: n de manchas; segmento: conf_split_win).
# Cada variante de segmentos refaz todas as TIs-ano (dezenas de minutos).
#
# Output: 04_stats/B10_robustez_celulas.csv, B10_robustez_segmentos.csv
# ======================================================================

check_version()

RUN_SAZONAL, RUN_ESCALA, RUN_ENCONTROS, RUN_COMBUSTIVEL = True, True, True, True

SCHEMES = [s for s in ["artigo1", "local", "local_100"] if s in load_seasons()]
ENC_VARIANTS = {
    "padrao":           {},
    "segmento 150 m":   {"seg_len": 150},
    "segmento 600 m":   {"seg_len": 600},
    "faixa 60 m":       {"strip": 60},
    "faixa 150 m":      {"strip": 150},
    "chegada >= 20%":   {"arrival": 0.2},
    "chegada >= 50%":   {"arrival": 0.5},
}
for fn in ["build_cells", "build_segments", "fit_cells", "fit_segments", "fit_scar_vs_reference"]:
    if fn not in globals():
        raise RuntimeError(f"Funcao {fn} nao definida - rode os blocos 08, 10 e 12 nesta sessao antes do 14.")

CELL_TRACK = "conf_npatch"

def cell_row(cells, grupo, variante):
    s, c = fit_cells(cells, "y_resto", CELL_CONF, f"{grupo}: {variante}")
    est = c.loc[CELL_TRACK] if CELL_TRACK in c.index else None
    s.update({"grupo": grupo, "variante": variante,
              "coef_conf_celula": est["Estimate"] if est is not None else np.nan,
              "ic_inf": est["2.5%"] if est is not None else np.nan,
              "ic_sup": est["97.5%"] if est is not None else np.nan})
    return s

def seg_row(segs, grupo, variante):
    s, c = fit_segments(segs, SEG_CONF, f"{grupo}: {variante}")
    r = fit_scar_vs_reference(segs)
    s.update({"grupo": grupo, "variante": variante,
              "rc_conf_split": c.loc["conf_split_win", "razao_chances_1dp"],
              "ic_inf": c.loc["conf_split_win", "ic95_inf"], "ic_sup": c.loc["conf_split_win", "ic95_sup"],
              "rc_cicatriz_vs_ref": r["razao_chances_cicatriz"]})
    return s

rows_c, rows_s = [], []
if RUN_SAZONAL:
    for sch in SCHEMES:
        console.print(f"[cyan]Recorte sazonal: {sch}[/cyan]")
        rows_c.append(cell_row(build_cells(sch, CELL_M), "sazonal", sch))
        sg, _ = build_segments(sch)
        rows_s.append(seg_row(sg, "sazonal", sch))
if RUN_ESCALA:
    for cm in CELL_SIZES:
        console.print(f"[cyan]Escala: {cm} m[/cyan]")
        rows_c.append(cell_row(build_cells(SEASON_MAIN, cm), "escala", f"{cm} m"))
if RUN_ENCONTROS:
    for lab, P in ENC_VARIANTS.items():
        console.print(f"[cyan]Encontros: {lab}[/cyan]")
        sg, _ = build_segments(SEASON_MAIN, P)
        rows_s.append(seg_row(sg, "encontros", lab))
if RUN_COMBUSTIVEL:
    for fm in FUEL_MODES:
        if fm == FUEL_MAIN:
            continue
        console.print(f"[cyan]Combustivel: {fm}[/cyan]")
        rows_c.append(cell_row(build_cells(SEASON_MAIN, CELL_M, fuel_mode=fm), "combustivel", fm))
        sg, _ = build_segments(SEASON_MAIN, fuel_mode=fm)
        rows_s.append(seg_row(sg, "combustivel", fm))

rob_c, rob_s = pd.DataFrame(rows_c), pd.DataFrame(rows_s)
rob_c.to_csv(stats_path("B10_robustez_celulas"), index=False)
rob_s.to_csv(stats_path("B10_robustez_segmentos"), index=False)
display(rob_c[["grupo", "variante", "n", "coef_conf_celula", "ic_inf", "ic_sup", "wald_p",
               "ganho_r2_within", "ganho_previsao_fora_TI_%"]].round(4))
display(rob_s[["grupo", "variante", "n_segmentos", "prop_interrupcao", "rc_conf_split", "ic_inf", "ic_sup",
               "wald_p", "cv_TI_logloss_ref", "cv_TI_logloss_conf", "rc_cicatriz_vs_ref"]].round(4))

if len(rob_c):
    ref_sign = np.sign(rob_c["coef_conf_celula"].iloc[0])
    console.print(f"Celula: mesmo sinal em {(np.sign(rob_c['coef_conf_celula']) == ref_sign).sum()}/{len(rob_c)}; "
                  f"ganho de previsao fora da TI em {(rob_c['ganho_previsao_fora_TI_%'] > 0).sum()}/{len(rob_c)}.")
if len(rob_s):
    ref_sign = np.sign(np.log(rob_s["rc_conf_split"].iloc[0]))
    ganho = (rob_s["cv_TI_logloss_conf"] < rob_s["cv_TI_logloss_ref"]) & \
            (rob_s["cv_incendio_logloss_conf"] < rob_s["cv_incendio_logloss_ref"])
    console.print(f"Segmento: mesmo sinal em {(np.sign(np.log(rob_s['rc_conf_split'])) == ref_sign).sum()}/"
                  f"{len(rob_s)}; melhora a previsao em {ganho.sum()}/{len(rob_s)}.")
console.print("[bold green]OK BLOCO 14 completo.[/bold green]")
