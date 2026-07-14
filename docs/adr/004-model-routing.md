# ADR 004: Model Routing

## Context
We need to decide how to route queries to the appropriate LLM based on cost, latency, capability, and domain.

## Decision
We will implement a model routing system with three tiers:
1. **Cheap**: GPT-3.5-turbo / Claude Haiku - for simple queries (summarization, basic QA)
2. **Standard**: GPT-4o-mini / Claude Sonnet - for most queries
3. **Premium**: GPT-4o / Claude Opus - for complex queries (reasoning, code, creative writing)

## Routing Matrix
| Query Type               | Model Tier |
|--------------------------|------------|
| Simple QA (factual)      | Cheap      |
| Summarization            | Cheap      |
| General QA               | Standard   |
| Creative writing         | Premium    |
| Code generation          | Premium    |
| Complex reasoning        | Premium    |
| Domain-specific (e.g., medical) | Fine-tuned (if available) |

## Consequences
### Positive
- **Cost optimization**: We can save money by using cheaper models for simple queries.
- **Latency optimization**: Cheaper models are often faster.
- **Quality**: We can use the best model for each query type.

### Negative
- **Complexity**: The routing system adds complexity to the codebase.
- **Routing errors**: The router might sometimes choose the wrong model tier.

### Neutral
- We will start with heuristic routing (query length, keywords) and can later add ML-based routing.
- We will track which model is used for each query and its performance to improve the routing logic over time.
