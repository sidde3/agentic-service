# 03 — Models

Four AI models must be pre-deployed as KServe InferenceServices before running the deployment script. All must be in `Ready` state before LlamaStack and downstream services can function.

The `deploy-all.sh` script **does not create** these models — it only verifies they are Ready. Reference manifests are provided in `components/03-models/reference/` for deploying them manually or via the OpenShift AI dashboard.

## Models

### Qwen 2.5 7B Instruct
- **Role**: Decoder LLM for reasoning and tool calling
- **Used by**: **LlamaStack** (`04-llamastack`) — powers the agentic loop: selecting tools, interpreting results, and generating plan recommendations
- **Key args**: `--tool-call-parser hermes --enable-auto-tool-choice` (enables MCP tool calling)
- **Requires**: 1 NVIDIA GPU (L40/A100)
- **HuggingFace**: `Qwen/Qwen2.5-7B-Instruct`

### Qwen3-Reranker-0.6B
- **Role**: Reranker for post-retrieval scoring of RAG results
- **Used by**: **Agent** (`08-agent`) — re-scores vector search results via `/v1/rerank` endpoint before the LLM sees them
- **Key args**: `--runner=pooling --task=score` (runs as a scoring model, not generative)
- **Requires**: 1 NVIDIA GPU (L40/A100)
- **HuggingFace**: `Qwen/Qwen3-Reranker-0.6B`

### Fine-tuned BERT (Phayathai)
- **Role**: Intent classification — classifies user messages into mobile-service intents
- **Used by**: **Router** (`09-router`) — sends every user message to BERT's `/classify` endpoint to determine the intent before routing
- **Key args**: `--runner=pooling --convert=classify --hf-overrides={"architectures":["RobertaForSequenceClassification"]}`
- **Runs on**: CPU
- **Source**: S3 bucket (fine-tuned model, `merged-models/encoder` path)

### BGE-small-en-v1.5
- **Role**: Embedding model for semantic search (384-dimensional embeddings)
- **Used by**: **LlamaStack** (`04-llamastack`) — generates vector embeddings when ingesting plan documents and when the agent performs `knowledge_search`
- **Key args**: `--runner=pooling` (runs as an embedding model)
- **Runs on**: CPU
- **HuggingFace**: `BAAI/bge-small-en-v1.5`

## Reference Manifests

These files in `components/03-models/reference/` are captured from the live `intent-classification-sidd` namespace. They are **reference only** — not applied by `deploy-all.sh`.

| File | Kind | Model |
|------|------|-------|
| `namespace.yaml` | Namespace | `${NS_MODELS}` |
| `qwen-serving-runtime.yaml` | ServingRuntime | qwen25-7b-instruct (GPU) |
| `qwen-inferenceservice.yaml` | InferenceService | qwen25-7b-instruct |
| `reranker-serving-runtime.yaml` | ServingRuntime | qwen3-reranker-06b (GPU) |
| `reranker-inferenceservice.yaml` | InferenceService | qwen3-reranker-06b |
| `bge-small-serving-runtime.yaml` | ServingRuntime | bge-small-en-v15 (CPU) |
| `bge-small-inferenceservice.yaml` | InferenceService | bge-small-en-v15 |
| `bert-serving-runtime.yaml` | ServingRuntime | finetuned-phayathai-bert (CPU) |
| `bert-inferenceservice.yaml` | InferenceService | finetuned-phayathai-bert |

## Configuration

| Variable | Purpose |
|----------|---------|
| `NS_MODELS` | Namespace where the models are deployed |
| `BERT_MODEL_NAME` | Name of the BERT InferenceService |

## Connections

- **Qwen** ← **04-llamastack** (via `VLLM_INTERNAL_URL`)
- **Qwen3-Reranker** ← **08-agent** (via `RERANKER_URL`)
- **BERT** ← **09-router** (via `VLLM_API_URL` / BERT route)
- **BGE** ← **04-llamastack** (via `vllm-bge-small` inference provider)
