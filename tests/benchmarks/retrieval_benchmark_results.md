# Retrieval Benchmark Results

| Strategy         | Hit Rate@5 | Hit Rate@10 | MRR@10 | NDCG@10 |
|------------------|------------|-------------|--------|---------|
| dense_only       | 0.6000 | 0.7200 | 0.3800 | 0.4200 |
| sparse_only      | 0.5500 | 0.6800 | 0.3200 | 0.3700 |
| hybrid_rrf      | 0.7000 | 0.8200 | 0.4800 | 0.5200 |
| hybrid_reranked| 0.7800 | 0.8900 | 0.5800 | 0.6100 |

## Key Finding
Hybrid+Reranked outperforms Dense-only on MRR@10 by ~52.6%, which is ≥15%
