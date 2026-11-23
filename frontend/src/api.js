const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

async function apiRequest(path, options = {}) {
  if (!API_BASE_URL) {
    throw new Error("Backend URL is missing. Check frontend .env.");
  }

  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("Please log in to continue.");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Session expired. Please log in again.");
    }

    throw new Error(data.detail || `Request failed: ${response.status}`);
  }

  return data;
}

export async function getRiskAlerts() {
  return apiRequest("/risk-alerts");
}

export async function getResourceOptimization() {
  return apiRequest("/optimize-allocation");
}

export async function generateRecommendations() {
  return apiRequest("/recommendations/generate", { method: "POST" });
}

export function getDemandForecasts() {
  return apiRequest("/demand-forecasts");
}

export function getEquipment() {
  return apiRequest("/equipment");
}

export function getMaintenanceRecords() {
  return apiRequest("/maintenance-records");
}

export async function getReportsData() {
  const [
    summary,
    inventory,
    resources,
    batches,
    riskData,
    forecastData,
    recommendationData,
    equipment,
    maintenance,
  ] = await Promise.all([
    apiRequest("/dashboard/summary"),
    apiRequest("/inventory"),
    apiRequest("/resources"),
    apiRequest("/resource-batches"),
    apiRequest("/risk-alerts"),
    apiRequest("/demand-forecasts"),
    apiRequest("/recommendations"),
    apiRequest("/equipment"),
    apiRequest("/maintenance-records"),
  ]);

  return {
    summary,
    inventory: Array.isArray(inventory) ? inventory : [],
    resources: Array.isArray(resources) ? resources : [],
    batches: Array.isArray(batches) ? batches : [],
    alerts: riskData.alerts ?? [],
    forecasts: forecastData.forecasts ?? [],
    recommendations: recommendationData.recommendations ?? [],
    equipment: Array.isArray(equipment) ? equipment : [],
    maintenance: Array.isArray(maintenance) ? maintenance : [],
  };
}