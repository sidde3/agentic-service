# 03 — Models

KServe InferenceServices for the 4 models used in this solution.

See [full documentation](../../docs/components/03-models.md).

## Models

| Model | Purpose | Runtime | Hardware |
|-------|---------|---------|----------|
| **qwen25-7b-instruct** | LLM for agent reasoning and tool calling | vLLM CUDA (GPU) | NVIDIA L40 GPU |
| **qwen3-reranker-06b** | Reranker for RAG post-retrieval scoring | vLLM CUDA (GPU) | NVIDIA L40 GPU |
| **bge-small-en-v15** | Embedding model for vector search | vLLM CPU | CPU only |
| **finetuned-phayathai-bert** | Intent classification (fine-tuned BERT) | vLLM CPU | CPU only |

## Reference Manifests

The `reference/` folder contains clean ServingRuntime and InferenceService manifests captured from the `intent-classification-sidd` namespace. These are **reference only** — models are deployed via the OpenShift AI dashboard, not via `oc apply`.

| File | Kind | Model |
|------|------|-------|
| `qwen-serving-runtime.yaml` | ServingRuntime | Qwen2.5-7B-Instruct |
| `qwen-inferenceservice.yaml` | InferenceService | Qwen2.5-7B-Instruct |
| `reranker-serving-runtime.yaml` | ServingRuntime | Qwen3-Reranker-0.6B |
| `reranker-inferenceservice.yaml` | InferenceService | Qwen3-Reranker-0.6B |
| `bge-small-serving-runtime.yaml` | ServingRuntime | bge-small-en-v1.5 |
| `bge-small-inferenceservice.yaml` | InferenceService | bge-small-en-v1.5 |
| `bert-serving-runtime.yaml` | ServingRuntime | finetuned-phayathai-bert |
| `bert-inferenceservice.yaml` | InferenceService | finetuned-phayathai-bert |
| `namespace.yaml` | Namespace | Model serving namespace |
