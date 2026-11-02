# ======================================================================
# BLOCO 15 - Sintese: Materiais e Metodos + Resultados (PT e EN)
# Depende do bloco 00 e das tabelas gravadas pelos blocos 02-14. Segundos.
# ======================================================================
#
# Le os resultados ja salvos e escreve:
#   08_textos/RSL_metodos_resultados_PT.docx (+ .md)
#   08_textos/RSL_methods_results_EN.docx   (+ .md)
# Os numeros vem SEMPRE das tabelas; a interpretacao segue regras fixas e e
# cautelosa: nada e atribuido as BRIFs; ausencia de fogo nao e contencao;
# associacao, nao causalidade. Bloco nao rodado -> "[falta: rode o bloco xx]".
# Rascunho fiel aos numeros: revise antes de usar.
# ======================================================================

check_version()

import docx
from docx.shared import Pt

OUT_DIR = PROJECT_ROOT / "08_textos"
OUT_DIR.mkdir(exist_ok=True)
REGRA_PRINCIPAL = "simetrica (Landsat + MODIS)"
REGRA_SENS      = "antiga (MapBiomas na referencia)"

def _csv(path, **kw):
    return pd.read_csv(path, **kw) if Path(path).exists() else None

def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else None

R = {
    "amostra":   _csv(table_path("amostra_final_tis")),
    "tipo":      _csv(stats_path("B06_tipologia_resumo"), index_col=0),
    "d1":        _csv(stats_path("D1_tempo")),
    "d2":        _csv(stats_path("D2_foco_noturno"), index_col=0),
    "d2_taxa":   _csv(stats_path("D2_foco_noturno_taxa"), index_col=0),
    "corr":      _csv(stats_path("B07_correlacao_quantidade_configuracao"), index_col=0),
    "ses_corr":  _csv(stats_path("B07b_correlacao_ses_quantidade"), index_col=0),
    "ses_res":   _csv(stats_path("B07b_ses_resumo")),
    "regra":     _csv(stats_path("B08a_regra_antiga_x_simetrica")),
    "ordem":     _csv(stats_path("B08_ordem_qualidade"), index_col=0),
    "conc":      _csv(stats_path("B08_concordancia_mapbiomas_landsat")),
    "modis_c":   _csv(stats_path("B08_contribuicao_modis"), index_col=0),
    "det_sens":  _csv(stats_path("B08b_sensibilidade_landsat"), index_col=0),
    "det_rr":    _csv(stats_path("B08b_modis_razao_taxas")),
    "det_curva": _csv(stats_path("B08b_curva_limiar")),
    "cell":      _csv(stats_path("B09_celula_resumo")),
    "ref":       _csv(stats_path("B09_cicatriz_vs_referencia")),
    "seg":       _csv(stats_path("B09_segmento_resumo")),
    "seg_coef":  _csv(stats_path("B09_segmento_coeficientes"), index_col=0),
    "b_cell":    _csv(stats_path("B09b_celula_ses_coeficientes"), index_col=0),
    "b_cell_s":  _csv(stats_path("B09b_celula_ses_resumo")),
    "b_seg":     _csv(stats_path("B09b_segmento_or_jackknife"), index_col=0),
    "b_seg_s":   _csv(stats_path("B09b_segmento_resumo")),
    "b_verd":    _csv(stats_path("B09b_criterio_evidencia")),
    "rob_s":     _csv(stats_path("B10_robustez_segmentos")),
    "rob_c":     _csv(stats_path("B10_robustez_celulas")),
}
faltam = [k for k, v in R.items() if v is None]
console.print(f"[cyan]Tabelas encontradas:[/cyan] {len(R) - len(faltam)}/{len(R)}"
              + (f" | [yellow]faltam: {faltam}[/yellow]" if faltam else ""))

def num(x, d=2, lang="pt"):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "NA"
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "pt" else s

def pval(p, lang="pt"):
    if p is None or np.isnan(p):
        return "p = NA"
    if p < 0.001:
        return "p < 0,001" if lang == "pt" else "p < 0.001"
    return f"p = {num(p, 3, lang)}"

def falta(bloco, lang):
    return f"[falta: rode o bloco {bloco}]" if lang == "pt" else f"[missing: run block {bloco}]"

VAR = {"pt": {"conf_split_ses_0": "fragmentacao (SES)", "conf_lpi_ses_0": "maior mancha (SES)",
              "conf_npatch_ses_0": "numero de manchas (SES)", "log_area_cicatriz": "area da cicatriz (log)",
              "largura_local_100m": "largura local da cicatriz", "ses_cel_split": "fragmentacao da celula (SES)",
              "nbr_pre_int": "NBR da faixa interna antes", "gap_meses": "meses desde a cicatriz"},
       "en": {"conf_split_ses_0": "fragmentation (SES)", "conf_lpi_ses_0": "largest patch (SES)",
              "conf_npatch_ses_0": "number of patches (SES)", "log_area_cicatriz": "scar area (log)",
              "largura_local_100m": "local scar width", "ses_cel_split": "cell fragmentation (SES)",
              "nbr_pre_int": "inner-strip NBR before", "gap_meses": "months since scar"}}

# ============================================================
# MATERIAIS E METODOS
# ============================================================

def methods(lang):
    T = lambda pt, en: pt if lang == "pt" else en
    out = [("h1", T("Materiais e Metodos", "Materials and Methods"))]
    am = R["amostra"]
    if am is not None:
        eleg = am[am["elegivel"].astype(bool)]
        nomes = ", ".join(eleg["ti_name"].astype(str))
        out += [("h2", T("Area de estudo e amostra", "Study area and sample")),
                ("p", T(f"Partimos das 14 Terras Indigenas (TIs) do Cerrado com Brigadas Federais Indigenas (BRIF) "
                        f"do primeiro artigo, selecionadas pelo codigo FUNAI, recortadas no bioma e analisadas em "
                        f"EPSG:5880. O periodo e 2014-2024 (pos-BRIF); 2012-2013 entram so como historico de queima. "
                        f"Entraram as TIs com >= 6 anos de imagens Landsat 8/9 utilizaveis (cena <= 30% de nuvem, "
                        f"jun-out, <= 32 dias entre datas limpas) e >= 20 encontros entre cicatrizes do inicio da "
                        f"seca e queimadas posteriores: {len(eleg)} TIs ({nomes}).",
                        f"We started from the 14 Cerrado Indigenous Lands (ILs) with Indigenous Federal Brigades "
                        f"(BRIF) of our first article, selected by FUNAI code, clipped to the biome and analysed in "
                        f"EPSG:5880. The period is 2014-2024 (post-BRIF); 2012-2013 enter only as burn history. ILs "
                        f"were retained with >= 6 years of usable Landsat 8/9 imagery (scene cloud <= 30%, June-"
                        f"October, <= 32 days between clear dates) and >= 20 encounters between early dry-season "
                        f"scars and later fires: {len(eleg)} ILs ({nomes})."))]
    out += [
        ("h2", T("Dados", "Data")),
        ("p", T("Cicatrizes mensais (30 m) do MapBiomas Fogo Colecao 4 e cobertura do MapBiomas Colecao 10. A sequencia "
                "das queimadas foi verificada com o NBR mensal minimo do Landsat 8/9 Colecao 2 Nivel 2 e com focos "
                "ativos MODIS Colecao 6.1 (MOD14A1 Terra e MYD14A1 Aqua, 1 km, FireMask >= 8, como no primeiro artigo). "
                "Tempo diario do ERA5-Land, chuva mensal do CHIRPS, relevo do SRTM e rios do HydroSHEDS; agua e areas "
                "nao vegetadas foram barreiras permanentes.",
                "Monthly 30-m scars came from MapBiomas Fire Collection 4 and land cover from MapBiomas Collection 10. "
                "The burn sequence was verified with the monthly minimum NBR of Landsat 8/9 Collection 2 Level 2 and with "
                "MODIS Collection 6.1 daily active fires (MOD14A1 Terra and MYD14A1 Aqua, 1 km, FireMask >= 8, as in "
                "our first article). Daily weather came from ERA5-Land, monthly rainfall from CHIRPS, slope from SRTM "
                "and rivers from HydroSHEDS; water and non-vegetated areas were permanent barriers.")),
        ("h2", T("Encontros nas bordas", "Encounters at scar edges")),
        ("p", T("Bordas de cicatrizes iniciais (mai-jul) voltadas para combustivel nao queimado foram cortadas em "
                "segmentos de 300 m, com faixas externa e interna de 90 m. Houve CHEGADA quando >= 30% da faixa externa "
                "queimou em ago-out (MapBiomas) ou havia pixel MODIS com fogo a ate 1 km fora da borda; sem chegada, o "
                "segmento nao entra. Com chegada, CONTINUIDADE = nova queda de NBR >= 0,10 em >= 20% da faixa interna "
                "bem observada, ou centro de pixel MODIS com fogo >= 1 km dentro da cicatriz; INTERRUPCAO = faixa bem "
                "observada sem entrada. A ordem cicatriz -> chegada foi conferida com Landsat e MODIS. Como REFERENCIA, "
                "cada cicatriz com chegada recebeu uma pseudo-cicatriz de mesma forma, deslocada 2-10 km para vegetacao "
                "nao queimada da mesma TI, com a mesma regra.",
                "Edges of early scars (May-July) facing unburned fuel were cut into 300-m segments with 90-m outer and "
                "inner strips. A later fire ARRIVED when >= 30% of the outer strip burned in August-October (MapBiomas) "
                "or a MODIS fire pixel lay within 1 km outside the edge; segments without arrival were excluded. Given "
                "arrival, CONTINUITY = a new NBR drop >= 0.10 over >= 20% of a well-observed inner strip, or a MODIS "
                "fire-pixel centre >= 1 km inside the scar; INTERRUPTION = a well-observed strip with no entry. The scar "
                "-> arrival order was checked with Landsat and MODIS. As a REFERENCE, each scar with arrival received a "
                "same-shape pseudo-scar displaced 2-10 km into unburned vegetation of the same IL, with the same rule.")),
        ("h2", T("Detectabilidade", "Detectability")),
        ("p", T("Como uma nova queda de NBR e mais dificil de detectar sobre area ja queimada, o contraste cicatriz x "
                "referencia foi verificado (i) variando o limiar de queda (0,02-0,20, absoluto e relativo ao NBR "
                "anterior), (ii) medindo em que fracao o Landsat marca entrada quando o MODIS a confirma, e (iii) por um "
                "teste independente do NBR: a densidade de pixels-dia MODIS com fogo em ago-out nos nucleos das "
                "cicatrizes (> 1 km da borda) contra nucleos de combustivel nao queimado da mesma TI-ano (razao de "
                "taxas, Poisson com efeito fixo de TI-ano, IC por bootstrap de TIs).",
                "Because a new NBR drop is harder to detect over already burned ground, the scar-reference contrast was "
                "checked by (i) varying the drop threshold (0.02-0.20, absolute and relative to prior NBR), (ii) "
                "measuring how often Landsat flags entry when MODIS confirms it, and (iii) an NBR-independent test: the "
                "density of August-October MODIS fire pixel-days in scar cores (> 1 km from the edge) versus unburned "
                "fuel cores of the same IL-year (rate ratio, Poisson with IL-year fixed effects, IL bootstrap CI).")),
        ("h2", T("Configuracao alem da quantidade", "Configuration beyond quantity")),
        ("p", T(f"Em celulas de {num(CELL_M / 1000, 2, lang)} km, a configuracao do combustivel restante (fragmentacao "
                "pelo tamanho efetivo de malha, maior mancha e numero de manchas) foi comparada com um MODELO NULO: as "
                "cicatrizes de cada celula-ano foram reposicionadas ao acaso no combustivel disponivel, mantendo forma, "
                "area e numero (29 replicas), e a configuracao foi expressa como tamanho de efeito padronizado (SES). "
                "Assim, a configuracao independe da quantidade por construcao. Nas celulas, modelos lineares com efeitos "
                "fixos de celula e ano compararam a referencia (quantidade em t, vizinhas, t-1, t-2, cobertura, VPD e "
                "chuva) com o mesmo modelo + SES; nos segmentos de cicatriz, regressao logistica comparou a referencia "
                "(quantidade na janela de 1 km, cobertura, relevo, barreiras, tempo no dia da chegada, ano) com o mesmo "
                "modelo + area e largura local da cicatriz e SES da celula, e com o NBR da faixa interna antes do fogo "
                "como controle de detectabilidade. Com 8 TIs, a inferencia usou wild cluster bootstrap com pesos de "
                "Webb (9.999 replicas) nas celulas e jackknife por TI (CR3) nos segmentos; a previsao foi validada "
                "deixando incendios (5 grupos) ou TIs de fora. Configuracao so foi considerada relevante com "
                "associacao no sentido esperado, melhora do ajuste e da previsao fora da amostra.",
                f"In {num(CELL_M / 1000, 2, lang)}-km cells, the configuration of remaining fuel (fragmentation by "
                "effective mesh size, largest patch and number of patches) was compared with a NULL MODEL: the scars "
                "of each cell-year were randomly repositioned within available fuel, keeping shape, area and number "
                "(29 replicates), and configuration was expressed as a standardized effect size (SES), independent of "
                "quantity by construction. In cells, linear models with cell and year fixed effects compared a "
                "reference (quantity at t, neighbours, t-1, t-2, land cover, VPD and rainfall) with the same model + "
                "SES; at scar edges, logistic regression compared a reference (quantity in a 1-km window, land cover, "
                "terrain, barriers, arrival-day weather, year) with the same model + scar area, local width and cell "
                "SES, and with inner-strip NBR before the fire as a detectability control. With 8 ILs, inference used "
                "wild cluster bootstrap with Webb weights (9,999 replicates) for cells and IL jackknife (CR3) for "
                "edges; prediction was validated leaving fires (5 groups) or ILs out. Configuration was deemed relevant "
                "only with an association in the expected direction, better fit and better out-of-sample prediction.")),
        ("h2", T("Robustez", "Robustness")),
        ("p", T("Os modelos foram refeitos mudando uma escolha de cada vez: recorte sazonal (artigo 1; seca local "
                "CHIRPS < 60 e < 100 mm), celula (2,49; 4,98; 9,99 km), criterios dos encontros (segmento 150/600 m, "
                "faixa 60/150 m, chegada 20%/50%) e combustivel (toda vegetacao; natural + pastagem; so natural).",
                "Models were refitted changing one choice at a time: seasonal split (article 1; local CHIRPS < 60 and "
                "< 100 mm), cell size (2.49, 4.98, 9.99 km), encounter criteria (150/600-m segments, 60/150-m strips, "
                "20%/50% arrival) and fuel (all vegetation; natural + pasture; natural only).")),
    ]
    return out

# ============================================================
# RESULTADOS
# ============================================================

def results(lang):
    T = lambda pt, en: pt if lang == "pt" else en
    n = lambda x, d=2: num(x, d, lang)
    out = [("h1", T("Resultados", "Results"))]

    am = R["amostra"]
    if am is not None:
        excl = am[~am["elegivel"].astype(bool)]
        out += [("h2", T("Amostra", "Sample")),
                ("p", T(f"{int(am['elegivel'].sum())} das {len(am)} TIs entraram. Exclusoes: "
                        + "; ".join(f"{r.ti_name}: {r.motivo_exclusao}" for r in excl.itertuples()) + ".",
                        f"{int(am['elegivel'].sum())} of the {len(am)} ILs entered. Exclusions: "
                        + "; ".join(f"{r.ti_name}: {r.motivo_exclusao}" for r in excl.itertuples()) + "."))]

    out.append(("h2", T("Interrupcao nas bordas", "Interruption at scar edges")))
    rg = R["regra"]
    if rg is None:
        out.append(("p", falta("10", lang)))
    else:
        g = rg[rg["combustivel"] == FUEL_MAIN].set_index(["regra", "tipo_seg"])
        sim = g.xs(REGRA_PRINCIPAL, level="regra")
        tot = int(sim[["interrupcao", "continuidade", "indeterminado", "sem_chegada"]].sum().sum())
        sem = int(sim["sem_chegada"].sum())
        out.append(("p", T(
            f"Dos {n(tot, 0)} segmentos, {n(100 * sem / tot, 0)}% nao receberam fogo posterior e foram excluidos. O fogo "
            f"que chegou foi interrompido em {n(sim.loc['cicatriz', '% interrupcao'], 1)}% das bordas de cicatriz e em "
            f"{n(sim.loc['referencia', '% interrupcao'], 1)}% das bordas de referencia.",
            f"Of {n(tot, 0)} segments, {n(100 * sem / tot, 0)}% received no later fire and were excluded. Arriving fire was "
            f"interrupted at {n(sim.loc['cicatriz', '% interrupcao'], 1)}% of scar edges and at "
            f"{n(sim.loc['referencia', '% interrupcao'], 1)}% of reference edges.")))
    rf = R["ref"]
    if rf is not None:
        a = rf[(rf["combustivel"] == FUEL_MAIN) & (rf["regra"] == REGRA_PRINCIPAL)]
        if len(a):
            a = a.iloc[0]
            out.append(("p", T(f"Ajustada, a razao de chances de interrupcao cicatriz x referencia foi "
                               f"{n(a['razao_chances_cicatriz'], 1)} (IC {n(a['ic95_inf'], 1)}-{n(a['ic95_sup'], 1)}).",
                               f"Adjusted, the odds ratio of interruption at scar versus reference edges was "
                               f"{n(a['razao_chances_cicatriz'], 1)} (CI {n(a['ic95_inf'], 1)}-{n(a['ic95_sup'], 1)}).")))
    bs = R["b_seg"]
    if bs is not None and "cicatriz x referencia | + NBR antes" in set(bs["modelo"]):
        e = bs[bs["modelo"] == "cicatriz x referencia | + NBR antes"].iloc[0]
        out.append(("p", T(f"Controlando o NBR da faixa interna antes do fogo, a razao foi {n(e['or_1dp'], 1)} "
                           f"(IC jackknife por TI {n(e['ic95_jackknife_TI_inf'], 1)}-{n(e['ic95_jackknife_TI_sup'], 1)}).",
                           f"Controlling for inner-strip NBR before the fire, the ratio was {n(e['or_1dp'], 1)} "
                           f"(IL-jackknife CI {n(e['ic95_jackknife_TI_inf'], 1)}-{n(e['ic95_jackknife_TI_sup'], 1)}).")))

    out.append(("h2", T("Detectabilidade", "Detectability")))
    ds, rr = R["det_sens"], R["det_rr"]
    if ds is None or rr is None:
        out.append(("p", falta("11", lang)))
    else:
        txt_s = "; ".join(f"{T('cicatriz', 'scar') if i == 'cicatriz' else T('referencia', 'reference')} "
                          f"{n(100 * r['landsat_viu_entrada'], 0)}% (n = {int(r['n_segmentos'])})" for i, r in ds.iterrows())
        r0 = rr[(rr["core_m"] == rr["core_m"].min()) & (rr["referencia"] == "naoqueimado_local")]
        r0 = r0.iloc[0] if len(r0) else rr.iloc[0]
        barreira = r0["ic95_sup_boot_TI"] < 1
        out.append(("p", T(
            f"Quando o MODIS confirmou entrada do fogo, o Landsat tambem a marcou em: {txt_s}. Sem usar o NBR, a "
            f"densidade de pixels MODIS com fogo em ago-out nos nucleos das cicatrizes foi {n(r0['razao_taxas_agregada'], 2)} "
            f"vez a dos nucleos de combustivel nao queimado a ate 5 km (IC {n(r0['ic95_inf_boot_TI'], 2)}-"
            f"{n(r0['ic95_sup_boot_TI'], 2)}). "
            + ("O efeito de barreira, portanto, nao depende do detector." if barreira else
               "O teste independente nao confirma o efeito de barreira; o contraste das bordas deve ser lido com cautela."),
            f"When MODIS confirmed fire entry, Landsat also flagged it in: {txt_s}. Without NBR, the density of "
            f"August-October MODIS fire pixels in scar cores was {n(r0['razao_taxas_agregada'], 2)} times that in unburned "
            f"fuel cores within 5 km (CI {n(r0['ic95_inf_boot_TI'], 2)}-{n(r0['ic95_sup_boot_TI'], 2)}). "
            + ("The barrier effect therefore does not depend on the detector." if barreira else
               "The independent test does not confirm the barrier effect; the edge contrast must be read with caution."))))

    out.append(("h2", T("Configuracao alem da quantidade", "Configuration beyond quantity")))
    sc, sr = R["ses_corr"], R["ses_res"]
    if sc is not None and sr is not None:
        out.append(("p", T(
            f"A fragmentacao bruta acompanhou a quantidade (Spearman {n(sc.loc['q_inicio', 'conf_split'])}); o SES do "
            f"modelo nulo nao ({n(sc.loc['q_inicio', 'conf_split_ses'])}). Em "
            f"{n(100 * sr.iloc[0, 1], 0)}% das celulas-ano com cicatriz, as cicatrizes fragmentaram o combustivel mais "
            f"que o acaso (p <= 0,05) e em {n(100 * sr.iloc[0, 2], 0)}% menos.",
            f"Raw fragmentation tracked quantity (Spearman {n(sc.loc['q_inicio', 'conf_split'])}); the null-model SES did "
            f"not ({n(sc.loc['q_inicio', 'conf_split_ses'])}). In {n(100 * sr.iloc[0, 1], 0)}% of cell-years with scars, "
            f"scars split fuel more than chance (p <= 0.05) and in {n(100 * sr.iloc[0, 2], 0)}% less.")))
    bc, bcs = R["b_cell"], R["b_cell_s"]
    if bc is not None and bcs is not None:
        fr = "; ".join(f"{VAR[lang][v]}: {n(r['coef_pp_por_dp'], 2)} p.p./DP (wild p {n(r['p_wild_webb'], 3)})"
                       for v, r in bc.iterrows())
        s0 = bcs.iloc[0]
        out.append(("p", T(f"Celulas: {fr}. R2 within {n(s0['r2_within_ref'], 3)} -> {n(s0['r2_within_conf'], 3)}; "
                           f"erro de previsao em TIs novas mudou {n(s0['ganho_previsao_%'], 1)}% (positivo = melhora).",
                           f"Cells: {fr}. Within R2 {n(s0['r2_within_ref'], 3)} -> {n(s0['r2_within_conf'], 3)}; "
                           f"prediction error in new ILs changed by {n(s0['ganho_previsao_%'], 1)}% (positive = better).")))
    if bs is not None and R["b_seg_s"] is not None:
        t = bs[bs["modelo"] == "cicatriz | configuracao + deteccao"]
        fr = "; ".join(f"{VAR[lang].get(v, v)}: OR {n(r['or_1dp'])} (IC jk {n(r['ic95_jackknife_TI_inf'])}-"
                       f"{n(r['ic95_jackknife_TI_sup'])})" for v, r in t.iterrows())
        s0 = R["b_seg_s"].iloc[0]
        out.append(("p", T(f"Bordas de cicatriz ({n(s0['n_segmentos'], 0)} segmentos, {int(s0['n_TIs'])} TIs), com controle "
                           f"de detectabilidade: {fr}. Log-loss deixando TIs de fora {n(s0['logloss_TI_fora_ref'], 4)} -> "
                           f"{n(s0['logloss_TI_fora_conf'], 4)}; AUC {n(s0['auc_TI_fora_ref'], 3)} -> {n(s0['auc_TI_fora_conf'], 3)}.",
                           f"Scar edges ({n(s0['n_segmentos'], 0)} segments, {int(s0['n_TIs'])} ILs), with detectability "
                           f"control: {fr}. Leave-IL-out log-loss {n(s0['logloss_TI_fora_ref'], 4)} -> "
                           f"{n(s0['logloss_TI_fora_conf'], 4)}; AUC {n(s0['auc_TI_fora_ref'], 3)} -> {n(s0['auc_TI_fora_conf'], 3)}.")))
    if R["b_verd"] is not None:
        out += [("h2", T("Criterio de evidencia", "Evidence criterion")), ("table", R["b_verd"])]

    out.append(("h2", T("Robustez", "Robustness")))
    rs = R["rob_s"]
    if rs is None:
        out.append(("p", falta("14", lang)))
    else:
        out.append(("p", T(f"A razao de chances cicatriz x referencia variou de {n(rs['rc_cicatriz_vs_ref'].min(), 1)} a "
                           f"{n(rs['rc_cicatriz_vs_ref'].max(), 1)} entre {len(rs)} variantes de metodo.",
                           f"The scar versus reference odds ratio ranged from {n(rs['rc_cicatriz_vs_ref'].min(), 1)} to "
                           f"{n(rs['rc_cicatriz_vs_ref'].max(), 1)} across {len(rs)} method variants.")))

    out += [("h2", T("Limitacoes", "Limitations")),
            ("p", T("Associacoes observacionais em 8 TIs; nenhuma queimada foi atribuida as BRIFs nem chamada de prescrita. "
                    "O MODIS (1 km) so ve entrada em cicatrizes largas e chegada com incerteza de ~1 km; a data da chegada "
                    "usa o mes do MapBiomas quando nao ha foco. Os resultados valem para a mesma estacao seca.",
                    "Observational associations in 8 ILs; no burn was attributed to the brigades or called prescribed. "
                    "MODIS (1 km) sees entry only into wide scars and arrival with ~1-km uncertainty; arrival dates fall "
                    "back to the MapBiomas month without a detection. Results concern the same dry season only."))]
    return out

def write_doc(blocks, path_docx, title):
    d = docx.Document()
    st = d.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
    d.add_heading(title, 0)
    md = [f"# {title}", ""]
    for kind, val in blocks:
        if kind == "h1":
            d.add_heading(val, 1); md += [f"## {val}", ""]
        elif kind == "h2":
            d.add_heading(val, 2); md += [f"### {val}", ""]
        elif kind == "p" and val:
            d.add_paragraph(val); md += [val, ""]
        elif kind == "table" and val is not None and len(val):
            t = d.add_table(rows=1, cols=len(val.columns)); t.style = "Light Grid Accent 1"
            for j, c in enumerate(val.columns):
                t.rows[0].cells[j].text = str(c)
            for row in val.itertuples(index=False):
                cells = t.add_row().cells
                for j, x in enumerate(row):
                    cells[j].text = f"{x:,.3f}" if isinstance(x, float) else str(x)
            md += ["```", val.to_string(index=False), "```", ""]
    d.save(path_docx)
    Path(str(path_docx).replace(".docx", ".md")).write_text("\n".join(md), encoding="utf-8")

for lang, (fname, title) in {
        "pt": ("RSL_metodos_resultados_PT.docx", "Configuracao das queimadas iniciais e continuidade do fogo"),
        "en": ("RSL_methods_results_EN.docx", "Early-burn configuration and fire continuity")}.items():
    write_doc(methods(lang) + results(lang), OUT_DIR / fname, title)
    console.print(f"[green]OK {OUT_DIR / fname}[/green]")
console.print("[bold green]OK BLOCO 15 completo (revise o texto antes de usar).[/bold green]")
