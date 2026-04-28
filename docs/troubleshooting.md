# Troubleshooting

## Pod Scheduling

**Error**: `FailedScheduling: untolerated taint {nvidia.com/gpu: l40-gpu}`

**Fix**: Patch the NVIDIA GPU HardwareProfile:
```bash
oc patch hardwareprofile nvidia-gpu -n $NS_MODELS --type merge \
  -p '{"spec":{"tolerations":[{"key":"nvidia.com/gpu","value":"l40-gpu","effect":"NoSchedule"}]}}'
```

## Llama Stack

**Error**: `ValueError: Provider vllm-embedding not found`

**Cause**: Model registered with a non-existent provider ID.

**Fix**: Check `llamastack-user-config` ConfigMap. Ensure model `provider_id` matches a configured provider.

---

**Error**: `RuntimeError: Could not connect to PGVector database server`

**Fix**: Verify pgvector service is reachable. Check `host`, `port`, `db`, `user`, `password` in the ConfigMap. Use `db` (not `database`).

---

**Error**: Llama Stack pod in `CrashLoopBackOff` after ConfigMap change

**Fix**: Check for YAML syntax errors (especially tab characters). Validate with:
```bash
oc get configmap llamastack-user-config -n $NS_LLAMASTACK -o yaml | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)"
```

## Agent

**Error**: `400: max_tokens must be at least 1, got 0`

**Cause**: Agent configuration missing `sampling_params`.

**Fix**: Ensure agent creation includes `"sampling_params": {"max_tokens": 4096}`.

---

**Error**: `400: maximum context length is 32768 tokens`

**Cause**: System prompt too long or too many tool iterations.

**Fix**: Trim prompts, reduce `max_infer_iters`, or increase `max_tokens` on the model.

---

**Error**: Agent doesn't call `knowledge_search` (hallucinating plans)

**Fix**: Strengthen the prompt with "STRICT ORDER" and "MANDATORY -- DO NOT SKIP" instructions. Increase `max_infer_iters` to 8 for compare_plan agents.

---

**Error**: Agent readiness probe failing (0/1 Ready)

**Cause**: Health check calls Llama Stack, which may be slow.

**Fix**: Increase `timeoutSeconds` to 10 in the deployment manifest.

## Router

**Error**: `Redis connection failed: [Errno 61] Connect call failed`

**Fix**: Ensure Redis is deployed in the same namespace and `REDIS_HOST` is correct. Check `REDIS_PASSWORD`.

---

**Error**: `Postgres pool creation failed`

**Fix**: Ensure userchat database exists and the user has access. Check `DATABASE_URL`.

## OpenShift Build

**Error**: `PermissionError: [Errno 13] Permission denied`

**Cause**: OpenShift runs containers as arbitrary non-root UIDs.

**Fix**: Dockerfiles must include:
```dockerfile
USER 0
RUN chmod -R g=u /app
USER 1001
```

---

**Error**: `error: build error: building at STEP "RUN chmod"`

**Fix**: Ensure `USER 0` appears before the `chmod` command in the Dockerfile.

## BERT Classification

**Issue**: BERT classifies English text incorrectly

**Cause**: BERT was fine-tuned on Thai text. English input produces unreliable results.

**Workaround**: Use `predefined_intent` in the `/chat` request to bypass BERT for testing.

## General

**Issue**: `SSL: EOF occurred in violation of protocol`

**Cause**: Intermittent OpenShift router/TLS issue.

**Workaround**: Retry the request. If persistent, check the OpenShift router pods.
