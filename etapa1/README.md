# Etapa 1 — Datos limpios, valores por línea y marcador base

Pipeline reproducible que convierte los datos crudos del hackathon (fenotipos 2000–2008, genotipos, ambiente) en los insumos de la Etapa 2: genotipos imputados, valores fenotípicos por línea con su confiabilidad, ambiente sin fuga de información, pliegues de validación y los modelos base que hay que superar.

## Cómo correrlo

```bash
pip install -r requirements.txt
bash run_stage1.sh "/ruta/a/Simplified Hackathon Dataset V3" artifacts
```

Los tiempos son de una máquina con 1 CPU y 4 GB de RAM: unos 8 minutos en total, de los cuales ~3 son de genotipos. Cada script también se puede correr por separado con `--data-dir` y `--out-dir`.

| Script | Qué hace | Salidas principales |
|---|---|---|
| `s01_clean_phenotypes.py` | Limpieza, IDs normalizados, padres y retrocruzas | `pheno_clean.parquet`, `populations.parquet` |
| `s02_build_genotypes.py` | Re-imputa C1 y C2 desde los archivos sin imputar | `geno/{C}_geno_int8.npy`, `geno/{C}_origin_uint8.npy`, `geno/{C}_lines.parquet`, `geno/{C}_parents.parquet` |
| `s03_environment.py` | Clima y suelo, relleno de huecos, normales sin fuga | `env_actual.parquet`, `env_normals.parquet` |
| `s04_line_values.py` | Modelo de dos niveles (intra y entre familias) para 8 rasgos | `line_values.parquet`, `pop_values.parquet`, `varcomp.parquet`, `env_quality.parquet` |
| `s05_cv_baselines.py` | Pliegues hacia adelante y modelos base B0–B3 | `cv_folds.json`, `baseline_scores.csv` |

Cada paso escribe su propio `qc_*.json`.

## Problemas encontrados en los datos (y cómo se resolvieron)

**Archivos genómicos**
- `ImputedC2Populations.zip` está corrupto: no es un zip válido.
- El imputado oficial de C1 deja 14 % de NA, concentrados en los marcadores polimórficos entre padres, que son justo los que distinguen hermanos.
- Solución: se re-imputan ambos clusters desde `Unimputed_*`. Dentro de cada cromosoma se interpola en cM la dosis de origen parental entre los 49–123 SNPs observados de cada línea.
- Validación con 15 % de llamadas enmascaradas: concordancia de 75–76 % (80 % cuando los marcadores vecinos coinciden), contra ~50 % de la línea base.
- Coincide 99 % con el imputado oficial donde este tiene dato.

**IDs y cruzas**
- En C2 el ID trae `.0` (`C2.1.1.0`), así que el join de la guía oficial no encuentra nada.
- En 4 poblaciones de C1 la misma línea aparece como `12` y como `00000000012`; se unificaron 667 líneas.
- `CROSS` usa la notación `A*2/B` para retrocruzas (239 poblaciones): A aporta 75 % del genoma. Con esto, los padres de `CROSS` coinciden 100 % con los del archivo genómico.

**Ambiente**
- El archivo cubre solo ~80 % de los ambientes de C2. Los faltantes se rellenan con el ambiente más cercano del mismo año (mediana: 44 km).
- 18 localidades no tienen coordenadas; se usa el centroide de su estado.
- DP01/DP10 son días con lluvia (convención NOAA), no punto de rocío.

**Fuga de información.** El clima de abril–octubre de 2008 no se conoce en enero de 2008. `env_normals.parquet` resume para cada año Y solo los años anteriores; las localidades nuevas se resuelven con sus 3 vecinas más cercanas.

## Hallazgo de diseño que define la estrategia

En ~90 % de las combinaciones localidad × SET hay una sola población (mediana: 2 poblaciones por localidad-año). **Cada familia es prácticamente su propio ensayo.** Por eso el modelo separa dos niveles:

- **Intra-familia.** Es la desviación de cada línea respecto a su familia. Es limpia, porque los errores de ambiente se cancelan entre hermanos que comparten los mismos ensayos.
- **Entre familias.** Se ajusta un modelo sobre las medias de ensayo con un término familia × ambiente (σ² ≈ 125). Su confiabilidad es menor.

| Yield (bu/ac) | C1 | C2 |
|---|---|---|
| Varianza genética intra-familia | 36 | 28 |
| Varianza genética entre familias | 113 | 105 |
| h² de la media de línea (intra, modelo) | 0,45 | 0,42 |
| h² intra por división de ambientes (verificación independiente) | 0,44 | 0,40 |
| Confiabilidad de la media familiar (empírica, ambientes partidos) | 0,56 | 0,43 |
| Parcelas atípicas descartadas / ambientes excluidos | 270 / 42 | 271 / 53 |

Las confiabilidades ponen un techo a cualquier modelo. Por ejemplo, con una h² de 0,45 la correlación esperable contra BLUEs de 2008 es de, a lo sumo, ~0,67 × la precisión real.

**Advertencia:** ningún genotipo se repite entre años (no hay testigos comunes). Los valores se centran dentro de cada año: son comparables dentro del año, no entre años.

## Validación y marcador base (rendimiento)

- **Validación hacia adelante:** se entrena con los años anteriores a Y y se predicen las familias nuevas de Y (Y = 2004–2007).
- **Holdout:** 2008 se reserva y no se usa para ajustar nada.
- **Pliegues internos:** son por familia (`GroupKFold`), para que la media familiar no se filtre.

Métricas en `metrics.py`:
- r global, r entre familias y ρ intra-familia (Spearman);
- precisión en el top 10 %;
- **% de la ganancia máxima capturada** al elegir el top 10 % predicho, que es la métrica de negocio.

Promedio de validación 2004–2007 → holdout 2008:

| Modelo | C1: r entre familias | C1: % ganancia | C2: r entre familias | C2: % ganancia |
|---|---|---|---|---|
| B0 al azar | −0,06 → 0,11 | 0 → −1 | 0,03 → −0,01 | 0 → 0 |
| B1 GCA histórico de padres | 0,29 → 0,38 | 11 → 31 | 0,35 → 0,33 | 31 → 51 |
| B2 B1 + tester | 0,43 → 0,36 | 28 → 5 | 0,42 → 0,63 | 28 → 58 |
| B3 ridge sobre genotipo esperado de la familia + tester | 0,46 → 0,34 | 23 → 25 | 0,47 → 0,71 | 20 → 56 |

Los modelos B1–B3 predicen solo la media familiar, así que no ordenan hermanos: la ρ intra-familia queda vacía. Ese es el hueco principal que debe llenar la Etapa 2.

## Qué usa la Etapa 2

- **Objetivo intra-familia:** `DEV_YLD_BE`, con peso 1/`PEV_YLD_BE`.
- **Objetivo entre familias:** `POP_BLUE` (en `pop_values.parquet`), con peso `REL_POP`.
- **Genotipos:** cargar con `np.load("geno/C1_geno_int8.npy") / 100`. Las filas se alinean con `geno/C1_lines.parquet` a través de la columna `ROW`.
- **Origen parental:** `origin_uint8 / 200` es la fracción del genoma que viene del padre `PA` en cada marcador. Sirve para modelos de efectos de segmentos parentales.

## Limitaciones conocidas

- **Imputación.** La interpolación lineal de dosis es una aproximación a un HMM completo.
- **Heterocigosis.** Las poblaciones BC y F2 tienen niveles distintos de heterocigosis. Esto no se modela explícitamente.
- **Rasgos de acame (STLP, RTLP).** Son muy asimétricos, con muchas parcelas atípicas y baja confiabilidad. Úsalos solo como restricción, no como objetivo.
