# 03 — Models

Three AI models must be pre-deployed as KServe InferenceServices before running the deployment script. All three must be in `Ready` state before LlamaStack and downstream services can function.

The `deploy-all.sh` script **does not create** these models — it only verifies they are Ready. Reference manifests are provided in `components/03-models/reference/` for deploying them manually or via the OpenShift AI dashboard.

## Models

### Qwen 2.5 7B Instruct (AWQ)
- **Role**: Decoder LLM for reasoning and tool calling
- **Used by**: **LlamaStack** (`04-llamastack`) — powers the agentic loop: selecting tools, interpreting results, and generating plan recommendations
- **Requires**: 1 NVIDIA GPU (T4 with AWQ quantization, or L40/A100 for full precision)

### Fine-tuned BERT (Phayathai)
- **Role**: Intent classification — classifies user messages into 10 mobile-service intents
- **Used by**: **Router** (`09-router`) — sends every user message to BERT's `/classify` endpoint to determine the intent before routing to the appropriate handler
- **Runs on**: CPU

### BGE-small-en-v1.5
- **Role**: Embedding model for semantic search (384-dimensional embeddings)
- **Used by**: **LlamaStack** (`04-llamastack`) — generates vector embeddings when ingesting plan documents and when the agent performs `knowledge_search` against the plan catalog
- **Runs on**: CPU

## Reference Manifests

These files in `components/03-models/reference/` are provided as reference for how the models should be configured. They are **not** applied by `deploy-all.sh`.

| File | Resource |
|------|----------|
| `namespace.yaml` | Namespace `${NS_MODELS}` |
| `qwen-serving-runtime.yaml` | ServingRuntime `vllm-qwen-runtime` |
| `qwen-inferenceservice.yaml` | InferenceService `qwen25-7b-instruct` |
| `bert-serving-runtime.yaml` | ServingRuntime `bert-intent-runtime` |
| `bert-inferenceservice.yaml` | InferenceService `${BERT_MODEL_NAME}` |
| `bge-small-serving-runtime.yaml` | ServingRuntime `vllm-bge-small-runtime` |
| `bge-small-inferenceservice.yaml` | InferenceService `bge-small-en-v15` |

## Configuration

| Variable | Purpose |
|----------|---------|
| `NS_MODELS` | Namespace where the models are deployed |
| `BERT_MODEL_NAME` | Name of the BERT InferenceService |

## Connections

- **Qwen** ← **04-llamastack** (via `VLLM_INTERNAL_URL`)
- **BERT** ← **09-router** (via `VLLM_API_URL` / BERT route)
- **BGE** ← **04-llamastack** (via `vllm-bge-small` inference provider)
