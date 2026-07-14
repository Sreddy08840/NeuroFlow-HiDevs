# ADR 003: Evaluation Framework

## Context
We need an evaluation framework for our RAG system. The options considered are:
- Human evaluation only
- Automated LLM-as-judge evaluation
- Hybrid (both human and automated)

## Decision
We will use automated LLM-as-judge evaluation as the primary method, with human evaluation for edge cases and calibration.

## Consequences
### Positive
- **Scalability**: Automated evaluation can handle thousands of queries per day.
- **Consistency**: LLM-as-judge provides consistent evaluation criteria.
- **Cost-effective**: Much cheaper than human evaluation at scale.

### Negative
- **Hallucinations**: LLM-as-judge can make mistakes or hallucinate.
- **Bias**: The judge LLM may have biases that affect evaluation.
- **Cost**: Still requires LLM calls, which add cost.

### Neutral
- We will use GPT-4o as the judge LLM.
- We will monitor evaluation quality with a small human-annotated golden dataset.
- We will implement detection for inconsistent or suspicious evaluation scores.
