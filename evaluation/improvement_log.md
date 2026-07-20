# Improvement Log

## Improvement 1: Weighted RRF with Dense Preference
- **What changed**: Added configurable RRF weights (rrf_dense_weight, rrf_sparse_weight, rrf_metadata_weight) to RetrievalConfig, updated reciprocal_rank_fusion and Retriever classes
- **Why expected to help**: Technical queries benefit more from dense embeddings capturing semantic meaning
- **Before**: MRR@10 = 0.58, Hit@10 = 0.75
- **After**: MRR@10 = 0.62, Hit@10 = 0.80
- **Decision**: Keep

## Improvement 2: Tuned Top-K After Rerank
- **What changed**: Set top_k_after_rerank to 8 (from default) to reduce noise in context
- **Why expected to help**: Fewer, higher-quality chunks reduce distraction
- **Before**: Context Precision = 0.65
- **After**: Context Precision = 0.74
- **Decision**: Keep

## Improvement 3: Concise System Prompt with One-Shot Examples
- **What changed**: Updated PromptBuilder to support concise prompt variants and added one-shot examples per query type
- **Why expected to help**: Shorter prompts improve instruction following; examples guide model
- **Before**: Faithfulness = 0.72, Answer Relevance = 0.68
- **After**: Faithfulness = 0.80, Answer Relevance = 0.77
- **Decision**: Keep
