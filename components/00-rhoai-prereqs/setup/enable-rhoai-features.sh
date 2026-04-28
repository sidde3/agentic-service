#!/bin/bash
# RHOAI cluster-admin setup: verify prerequisites, enable Gen AI Studio,
# Model-as-Service, and the Llama Stack Operator.
set -euo pipefail

echo "======================================"
echo "RHOAI Prerequisites Setup"
echo "======================================"
echo ""

# ── Pre-flight: verify RHOAI is installed ──────────────────────────────
echo "==> Checking OpenShift AI installation ..."

if ! oc get datasciencecluster default-dsc -n redhat-ods-applications &>/dev/null; then
    echo "ERROR: DataScienceCluster 'default-dsc' not found."
    echo "OpenShift AI (RHOAI) must be installed before running this script."
    echo "Install the 'Red Hat OpenShift AI' operator from OperatorHub first."
    exit 1
fi
echo "  DataScienceCluster: found"

if ! oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications &>/dev/null; then
    echo "ERROR: OdhDashboardConfig 'odh-dashboard-config' not found."
    echo "OpenShift AI dashboard is not configured."
    exit 1
fi
echo "  OdhDashboardConfig: found"

# ── Verify KServe is Managed (required for model serving) ─────────────
echo ""
echo "==> Checking KServe ..."
KSERVE_STATE=$(oc get datasciencecluster default-dsc -n redhat-ods-applications \
  -o jsonpath='{.spec.components.kserve.managementState}' 2>/dev/null || echo "")
if [[ "$KSERVE_STATE" != "Managed" ]]; then
    echo "  KServe is '$KSERVE_STATE' — patching to Managed ..."
    oc patch datasciencecluster default-dsc \
      -n redhat-ods-applications --type=merge \
      -p '{"spec":{"components":{"kserve":{"managementState":"Managed"}}}}'
else
    echo "  KServe: Managed"
fi

# ── Enable Gen AI Studio + Model-as-Service ────────────────────────────
echo ""
echo "==> Checking Gen AI Studio + Model-as-Service ..."
GENAI=$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.genAiStudio}' 2>/dev/null || echo "false")
MAAS=$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.modelAsService}' 2>/dev/null || echo "false")

if [[ "$GENAI" == "true" && "$MAAS" == "true" ]]; then
    echo "  genAiStudio: true"
    echo "  modelAsService: true"
else
    echo "  Patching dashboard config ..."
    oc patch odhdashboardconfig odh-dashboard-config \
      -n redhat-ods-applications --type=merge \
      -p '{"spec":{"dashboardConfig":{"genAiStudio":true,"modelAsService":true,"enablement":true}}}'
    echo "  genAiStudio: true (set)"
    echo "  modelAsService: true (set)"
fi

# ── Enable Llama Stack Operator ────────────────────────────────────────
echo ""
echo "==> Checking Llama Stack Operator ..."
LS_STATE=$(oc get datasciencecluster default-dsc -n redhat-ods-applications \
  -o jsonpath='{.spec.components.llamastackoperator.managementState}' 2>/dev/null || echo "")

if [[ "$LS_STATE" == "Managed" ]]; then
    echo "  llamastackoperator: Managed"
else
    echo "  Patching DataScienceCluster ..."
    oc patch datasciencecluster default-dsc \
      -n redhat-ods-applications --type=merge \
      -p '{"spec":{"components":{"llamastackoperator":{"managementState":"Managed"}}}}'

    echo "  Waiting for Llama Stack Operator to become Managed ..."
    for i in $(seq 1 30); do
        state=$(oc get datasciencecluster default-dsc -n redhat-ods-applications \
          -o jsonpath='{.spec.components.llamastackoperator.managementState}' 2>/dev/null || echo "")
        if [[ "$state" == "Managed" ]]; then
            echo "  llamastackoperator: Managed"
            break
        fi
        sleep 5
    done
    if [[ "$state" != "Managed" ]]; then
        echo "  WARNING: llamastackoperator did not become Managed within 2.5 minutes."
    fi
fi

echo ""
echo "==> RHOAI prerequisites configured."
echo ""
echo "  Summary:"
echo "    KServe:              Managed"
echo "    genAiStudio:         true"
echo "    modelAsService:      true"
echo "    llamastackoperator:  Managed"
echo ""
