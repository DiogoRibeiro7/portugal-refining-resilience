# Processed data policy

Processed datasets are versioned because they are part of the empirical record. Each final analytical table should have:

1. a CSV file for human review;
2. a Parquet file when the pipeline has `pyarrow` available;
3. provenance metadata in `data/provenance/`;
4. an explicit key and unit column;
5. no silent imputation.

The `_seed` dataset is provisional and must not be the sole source for publication claims.
