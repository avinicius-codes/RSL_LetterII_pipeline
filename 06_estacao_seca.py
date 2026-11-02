# ======================================================================
# BLOCO 06 - Inicio e restante da seca: recorte do artigo 1 + recorte local
# Depende do bloco 00.
# ======================================================================
#
# PRINCIPAL ("artigo1"): igual para todas as TIs - seca = mai-out;
#   inicio = mai-jul; restante = ago-out.
# SENSIBILIDADE ("local", "local_100"): a seca de CADA TI pela chuva local
#   (CHIRPS, media mensal 2014-2024 sobre a TI): sequencia continua de meses
#   com chuva < limiar (60 / 100 mm) contendo o mes mais seco, dividida pela
#   mesma regra (metade inicial x final; n impar -> mes do meio no inicio).
#   Meses limitados a abr-nov (Landsat do bloco 03). Seca local < 2 meses ->
#   a TI fica com o recorte do artigo 1.
#
# Output: 03_tables/estacoes_por_ti.json | 04_stats/chuva_mensal_por_ti.csv,
#         estacoes_por_ti.csv | 05_figures/06_estacoes_por_ti.png
# ======================================================================

check_version()

LOCAL_SCHEMES = {"local": 60, "local_100": 100}
MONTH_LIMITS  = (4, 11)

def monthly_precip() -> pd.DataFrame:
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(f"{YEARS[0]}-01-01", f"{YEARS[-1] + 1}-01-01")
    n_years = len(YEARS)
    imgs = [chirps.filter(ee.Filter.calendarRange(m, m, "month")).sum().divide(n_years).rename(f"p{m:02d}")
            for m in range(1, 13)]
    fc = ee.Image.cat(imgs).reduceRegions(collection=tis_fc, reducer=ee.Reducer.mean(), scale=5566)
    info = fc.map(lambda f: ee.Feature(None, ee.Feature(f).toDictionary())).getInfo()
    df = pd.DataFrame([x["properties"] for x in info["features"]])
    long = df.melt(id_vars=["ti_id"], value_vars=[f"p{m:02d}" for m in range(1, 13)],
                   var_name="mes", value_name="chuva_mm")
    long["mes"] = long["mes"].str[1:].astype(int)
    long["ti_id"] = long["ti_id"].astype(int)
    return long.sort_values(["ti_id", "mes"]).reset_index(drop=True)

precip = checkpoint_load_or_run(f"chuva_mensal_{TAG_YEARS}", monthly_precip, ext="parquet")
precip.to_csv(stats_path("chuva_mensal_por_ti"), index=False)

def local_season(p_by_month: pd.Series, limiar: float):
    dry = p_by_month < limiar
    driest = int(p_by_month.idxmin())
    run = [driest]
    m = driest
    while True:
        m = 12 if m == 1 else m - 1
        if not dry[m] or m in run:
            break
        run.insert(0, m)
    m = driest
    while True:
        m = 1 if m == 12 else m + 1
        if not dry[m] or m in run:
            break
        run.append(m)
    run = [m for m in run if MONTH_LIMITS[0] <= m <= MONTH_LIMITS[1]]
    if len(run) < 2:
        return None
    k = int(np.ceil(len(run) / 2))
    return run[:k], run[k:]

seasons_out, rows = {}, []
for sch, limiar in LOCAL_SCHEMES.items():
    seasons_out[sch] = {}
    for ti, g in precip.groupby("ti_id"):
        res = local_season(g.set_index("mes")["chuva_mm"], limiar)
        fallback = res is None
        ini, rest = (list(EARLY), list(LATE)) if fallback else res
        seasons_out[sch][str(int(ti))] = {"inicio": ini, "restante": rest}
        rows.append({"esquema": sch, "ti_id": int(ti), "limiar_mm": limiar,
                     "inicio": "-".join(map(str, ini)), "restante": "-".join(map(str, rest)),
                     "usou_artigo1": fallback})
for ti in tis["ti_id"].astype(int):
    rows.append({"esquema": "artigo1", "ti_id": ti, "limiar_mm": np.nan,
                 "inicio": "-".join(map(str, EARLY)), "restante": "-".join(map(str, LATE)),
                 "usou_artigo1": True})

with open(table_path("estacoes_por_ti", "json"), "w", encoding="utf-8") as f:
    json.dump(seasons_out, f, indent=2)
est = pd.DataFrame(rows).merge(tis[["ti_id", "ti_name"]], on="ti_id")
est.to_csv(stats_path("estacoes_por_ti"), index=False)

SEASONS = load_seasons()
display(est.pivot_table(index="ti_name", columns="esquema", values="inicio", aggfunc="first").add_suffix(" (inicio)")
           .join(est.pivot_table(index="ti_name", columns="esquema", values="restante", aggfunc="first")
                    .add_suffix(" (restante)")))

ids = sorted(precip["ti_id"].unique())
nc = 4
nr = int(np.ceil(len(ids) / nc))
fig, axs = plt.subplots(nr, nc, figsize=(3.2 * nc, 2.4 * nr), sharex=True, sharey=True)
names = tis.set_index("ti_id")["ti_name"]
for ax, ti in zip(np.ravel(axs), ids):
    g = precip[precip["ti_id"] == ti]
    ini, rest = SEASONS["local"][int(ti)]
    cols = ["#1b7837" if m in ini else "#b2182b" if m in rest else "#9e9e9e" for m in g["mes"]]
    ax.bar(g["mes"], g["chuva_mm"], color=cols)
    ax.axhline(LOCAL_SCHEMES["local"], color="black", lw=0.7, ls="--")
    for m in EARLY + LATE:
        ax.axvspan(m - 0.5, m + 0.5, color="#e0e0e0", zorder=0, lw=0)
    ax.set_title(str(names.get(ti, ti)), fontsize=8)
    ax.set_xticks(range(1, 13)); ax.tick_params(labelsize=6)
for ax in np.ravel(axs)[len(ids):]:
    ax.set_axis_off()
fig.suptitle("Chuva media mensal (CHIRPS). Verde = inicio, vermelho = restante da seca local; "
             "faixa cinza = recorte do artigo 1", fontsize=9)
fig.savefig(fig_path("06_estacoes_por_ti"))
plt.show()
console.print("[bold green]OK BLOCO 06 completo: esquemas " + ", ".join(SEASONS) + ".[/bold green]")
