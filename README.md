# RSL – Letter II: código de análise

**Does early-season burn configuration constrain subsequent fires in Cerrado Indigenous Lands?**
Dias, Alcântara & Rodrigues — *Remote Sensing Letters*

O código roda no Google Colab, com Google Earth Engine e Google Drive. Cada bloco é uma célula do Colab. Rode os blocos **na ordem numérica e na mesma sessão**. Todos gravam em `MyDrive/RSL_LETTER_II/` (as exportações do Earth Engine passam por `MyDrive/RSL_LETTER_II_exports/`); se a sessão cair, rode de novo o bloco 00 e continue de onde parou, porque o que já existe não é refeito.

O arquivo `RSL_LetterII_pipeline.ipynb` traz os 18 blocos na mesma ordem, um por célula.

## Sequência

| Bloco | Arquivo | O que faz | Saídas principais |
|---|---|---|---|
| 00 | `00_configuracao.py` | Drive, Earth Engine, as 14 TIs com BRIF (código FUNAI, recorte no Cerrado, EPSG:5880), período pós-BRIF e funções comuns | `01_boundaries/tis_brif_cerrado.gpkg` |
| 01 | `01_cicatrizes_mapbiomas.py` | MapBiomas Fogo Col. 4 mensal → raster do mês da queima por TI e polígonos de cicatriz | `02_cache/cicatrizes_*.gpkg` |
| 02 | `02_elegibilidade_amostra.py` | Triagem das 14 TIs: imagens Landsat 8/9 e encontros analisáveis → amostra final com o motivo de cada exclusão | `03_tables/amostra_final_tis.csv` |
| 03 | `03_rasters_30m.py` | Pilhas de 30 m por TI-ano: mês da queima, cobertura, NBR mensal mínimo do Landsat, relevo e barreiras | `07_exports/rasters/*.tif` |
| 04 | `04_era5_diario.py` | ERA5-Land diário: VPD, umidade, vento e chuva | `02_cache/era5_diario_*.parquet` |
| 05 | `05_focos_modis.py` | Focos MODIS C6.1 (MOD14A1 + MYD14A1, 1 km, FireMask ≥ 8) por pixel e dia | `02_cache/modis_focos_*.parquet` |
| 06 | `06_estacao_seca.py` | Recorte do artigo 1 (mai–jul × ago–out) e seca local por TI (CHIRPS, sensibilidade) | `03_tables/estacoes_por_ti.json` |
| 07 | `07_tipologia_cicatrizes.py` | Tipologia descritiva das cicatrizes iniciais, tempo no dia do foco e focos noturnos | `04_stats/B06_*, D1_*, D2_*` |
| 08 | `08_configuracao_celulas.py` | Quantidade × configuração (m_eff, LPI, borda, nº de manchas) em células de 2,5, 5 e 10 km | `02_cache/celulas_*.parquet` |
| 09 | `09_configuracao_modelo_nulo.py` | **Modelo nulo:** cicatrizes reposicionadas ao acaso (mesma forma e área) → SES, configuração independente da quantidade | `02_cache/celulas_*_nulo.parquet` |
| 10 | `10_encontros_bordas.py` | Sequência das queimadas e encontros por segmento de borda (chegada, interrupção, continuidade), pseudo-cicatrizes de referência e regra simétrica × antiga | `02_cache/segmentos_*_md.parquet` |
| 11 | `11_detectabilidade.py` | Detectabilidade: curva do limiar de NBR, sensibilidade do Landsat e teste MODIS independente do NBR (núcleos de cicatriz × núcleos não queimados) | `04_stats/B08b_*` |
| 12 | `12_modelos.py` | Modelos referência × referência + configuração (célula e segmento), validação fora da amostra | `04_stats/B09_*` |
| 13 | `13_inferencia_poucas_TIs.py` | Inferência para 8 TIs: wild cluster bootstrap (Webb) e jackknife por TI; SES e controle de detectabilidade | `04_stats/B09b_*` |
| 14 | `14_robustez.py` | Robustez: recorte sazonal, escala, critérios dos encontros e combustível | `04_stats/B10_*` |
| 15 | `15_sintese_texto.py` | Métodos e Resultados em PT e EN, com os números lidos das tabelas | `08_textos/*.docx` |
| 16 | `16_figuras_letter.py` | Figuras 1–4, S2, S3 e Tabela 1 | `05_figures/letter/` |
| 17 | `17_figuras_sensoriamento.py` | Figuras espaciais R1–R4: área de estudo, Landsat falsa-cor + MODIS, teste MODIS e SES no mapa | `05_figures/letter/` |

Os blocos 14 e 17 usam funções definidas em blocos anteriores (08, 10, 11, 12 e 16). Por isso, rode-os na mesma sessão desses blocos.

## Pastas no Drive (`MyDrive/RSL_LETTER_II/`)

| Subpasta | Conteúdo |
|---|---|
| `00_raw` | `artigo1_tis.csv` (classe e FRRI do artigo 1), preenchido pelo usuário |
| `01_boundaries` | TIs recortadas no Cerrado |
| `02_cache` | Checkpoints (cicatrizes, ERA5, focos MODIS, células, segmentos, modelo nulo) |
| `03_tables` | Amostra final e estações por TI |
| `04_stats` | Tabelas de resultados (CSV) |
| `05_figures/letter` | Figuras da revista (600 dpi, TIFF/PDF/PNG) |
| `06_logs` | Registros das tarefas e da amostra |
| `07_exports` | Rasters de 30 m, mês da queima, ERA5, MODIS, sequências |
| `08_textos` | Métodos/Resultados (PT e EN) e figuras com legendas (.docx) |

Para usar outra pasta, troque `PROJECT_NAME` no bloco 00.

## Figuras

Todas as figuras saem a **600 dpi** em três formatos: TIFF (compressão LZW), PDF vetorial e PNG. A largura é a da mancha de texto da revista (14 cm), e os mapas têm escala, norte e grade de coordenadas.

## Dados de entrada

- **Ativos do Earth Engine do autor:** `tis_poligonais` (FUNAI) e `biome_border` (limite do Cerrado).
- **Coleções públicas do Earth Engine:**
  - MapBiomas Fogo Col. 4 e Cobertura Col. 10;
  - Landsat 8/9 C2 L2;
  - MODIS MOD14A1 e MYD14A1 C6.1;
  - ERA5-Land diário;
  - CHIRPS;
  - SRTM;
  - HydroSHEDS.
- **Tabela opcional `00_raw/artigo1_tis.csv`** (colunas `terrai_cod`, `classe`, `frri`): classe e FRRI de cada TI, vindos do primeiro artigo.

## Princípios da análise

- Período pós-BRIF (2014–2024); 2013 é o ano de transição e nunca é analisado.
- Ausência de fogo junto a uma cicatriz não conta como contenção: só entram segmentos com chegada do fogo.
- Nenhuma queimada é atribuída às BRIFs nem chamada de prescrita.
- A configuração só é tratada como relevante além da quantidade quando há, ao mesmo tempo:
  - associação no sentido esperado;
  - melhora do ajuste;
  - melhora da previsão fora da amostra.
