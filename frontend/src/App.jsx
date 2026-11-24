import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getResourceOptimization,
  generateRecommendations,
  getEquipment,
  getMaintenanceRecords,
  getReportsData
} from "./api";
import "./App.css";

import { getDemandForecasts } from "./api";

const navigation = [
  { label: "Dashboard", icon: "▦" },
  { label: "Inventory", icon: "▤" },
  { label: "Demand Forecasting", icon: "⌁" },
  { label: "Risk & Alerts", icon: "⚠" },
  { label: "Equipment", icon: "⚙" },
  { label: "Resource Optimization", icon: "⇄" },
  { label: "Recommendations", icon: "✓" },
  { label: "Reports & Evaluation", icon: "▥" },
];

function App() {
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState("");

  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState("");

  const [recommendations, setRecommendations] = useState([]);
  const [recommendationsLoading, setRecommendationsLoading] =
    useState(false);
  const [recommendationsError, setRecommendationsError] = useState("");
  const [recommendationActionId, setRecommendationActionId] =
    useState(null);

  const [activePage, setActivePage] = useState("Dashboard");
  const [search, setSearch] = useState("");


  const [email, setEmail] = useState("admin@hospital.com");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  const [isLoggedIn, setIsLoggedIn] = useState(
    Boolean(localStorage.getItem("access_token"))
  );

  // INVENTORY STATES
  const [inventory, setInventory] = useState([]);
  const [resources, setResources] = useState([]);
  const [batches, setBatches] = useState([]);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [inventoryError, setInventoryError] = useState("");
  const [inventorySearch, setInventorySearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");

  const [optimizationData, setOptimizationData] = useState(null);
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [optimizationError, setOptimizationError] = useState("");
  const [generationLoading, setGenerationLoading] = useState(false);
  const [generationMessage, setGenerationMessage] = useState("");

  const [forecasts, setForecasts] = useState([]);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState("");
  const [forecastModel, setForecastModel] = useState("");

  // EQUIPMENT STATES
  const [equipment, setEquipment] = useState([]);
  const [maintenanceRecords, setMaintenanceRecords] = useState([]);
  const [equipmentLoading, setEquipmentLoading] = useState(false);
  const [equipmentError, setEquipmentError] = useState("");

  // REPORTS STATES
  const [reportData, setReportData] = useState(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState("");

  // LOGIN
  async function handleLogin(event) {
    event.preventDefault();
    setLoginError("");

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

    if (!apiBaseUrl) {
      setLoginError("Backend URL is missing. Check frontend .env.");
      return;
    }

    setLoginLoading(true);

    try {
      const formData = new URLSearchParams();

      formData.set("username", email.trim());
      formData.set("password", password);
      formData.set("grant_type", "password");
      formData.set("scope", "");

      const response = await fetch(`${apiBaseUrl}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || `Login failed (${response.status})`
        );
      }

      if (!data.access_token) {
        throw new Error(
          "Login response did not include an access token."
        );
      }

      localStorage.setItem("access_token", data.access_token);

      setPassword("");
      setIsLoggedIn(true);
    } catch (error) {
      setLoginError(
        error.message || "Unable to log in. Please try again."
      );
    } finally {
      setLoginLoading(false);
    }
  }

// LOGOUT
function handleLogout() {
  // Remove authentication token
  localStorage.removeItem("access_token");

  // Reset authentication
  setIsLoggedIn(false);
  setActivePage("Dashboard");
  setSearch("");
  setPassword("");
  setLoginError("");

  // Clear dashboard data
  setDashboardSummary(null);
  setSummaryError("");
  setSummaryLoading(false);

  // Clear alerts
  setAlerts([]);
  setAlertsError("");
  setAlertsLoading(false);

  // Clear recommendations
  setRecommendations([]);
  setRecommendationsError("");
  setRecommendationsLoading(false);
  setRecommendationActionId(null);

  // Clear inventory
  setInventory([]);
  setResources([]);
  setBatches([]);
  setInventoryError("");
  setInventoryLoading(false);
  setInventorySearch("");
  setCategoryFilter("All");

  // Clear optimization
  setOptimizationData(null);
  setOptimizationError("");
  setOptimizationLoading(false);
  setGenerationLoading(false);
  setGenerationMessage("");

  // Clear forecasts
  setForecasts([]);
  setForecastError("");
  setForecastLoading(false);
  setForecastModel("");

  // Clear equipment
  setEquipment([]);
  setMaintenanceRecords([]);
  setEquipmentError("");
  setEquipmentLoading(false);

  // Clear reports
  setReportData(null);
  setReportsError("");
  setReportsLoading(false);
}

  // FETCH DASHBOARD SUMMARY
  useEffect(() => {
    if (!isLoggedIn) {
      setDashboardSummary(null);
      setSummaryLoading(false);
      return;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
    const token = localStorage.getItem("access_token");

    if (!apiBaseUrl || !token) {
      setSummaryError("Please log in to load dashboard data.");
      setSummaryLoading(false);
      return;
    }

    let cancelled = false;

    setSummaryLoading(true);

    fetch(`${apiBaseUrl}/dashboard/summary`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (response) => {
        if (response.status === 401) {
          handleLogout();
          throw new Error("Session expired. Please log in again.");
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(
            data.detail ||
              `Dashboard request failed (${response.status})`
          );
        }

        return data;
      })
      .then((data) => {
        if (!cancelled) {
          setDashboardSummary(data);
          setSummaryError("");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSummaryError(
            error.message || "Could not load dashboard summary."
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSummaryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

  // FETCH RISK ALERTS
  useEffect(() => {
    if (!isLoggedIn) {
      setAlertsLoading(false);
      return;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
    const token = localStorage.getItem("access_token");

    if (!apiBaseUrl || !token) {
      setAlertsError("Please log in to load risk alerts.");
      setAlertsLoading(false);
      return;
    }

    setAlertsLoading(true);

    fetch(`${apiBaseUrl}/risk-alerts`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (response) => {
        if (response.status === 401) {
          handleLogout();
          throw new Error("Session expired. Please log in again.");
        }

        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setAlerts(data.alerts ?? []);
        setAlertsError("");
      })
      .catch((error) => {
        console.error("Failed to load risk alerts:", error);

        setAlertsError(
          error.message ||
            "Could not load risk alerts from the backend."
        );
      })
      .finally(() => {
        setAlertsLoading(false);
      });
  }, [isLoggedIn]);

  // FETCH RECOMMENDATIONS
  useEffect(() => {
    if (!isLoggedIn || activePage !== "Recommendations") {
      return;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
    const token = localStorage.getItem("access_token");

    if (!apiBaseUrl || !token) {
      setRecommendationsError(
        "Please log in to load recommendations."
      );
      return;
    }

    let cancelled = false;

    setRecommendationsLoading(true);
    setRecommendationsError("");

    fetch(`${apiBaseUrl}/recommendations`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (response) => {
        if (response.status === 401) {
          handleLogout();
          throw new Error("Session expired. Please log in again.");
        }

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));

          throw new Error(
            body.detail || `Request failed: ${response.status}`
          );
        }

        return response.json();
      })
      .then((data) => {
        if (!cancelled) {
          setRecommendations(data.recommendations ?? []);
          setRecommendationsError("");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setRecommendationsError(
            error.message || "Could not load recommendations."
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setRecommendationsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isLoggedIn, activePage]);



useEffect(() => {
  if (!isLoggedIn || activePage !== "Demand Forecasting") return;

  let cancelled = false;

  async function loadForecasts() {
    setForecastLoading(true);
    setForecastError("");

    try {
      const data = await getDemandForecasts();

      if (!cancelled) {
        setForecasts(data.forecasts ?? []);
        setForecastModel(data.forecasts?.[0]?.model_name ?? "—");
      }
    } catch (error) {
      if (!cancelled) {
        setForecastError(error.message || "Could not load demand forecasts.");
      }
    } finally {
      if (!cancelled) setForecastLoading(false);
    }
  }

  loadForecasts();

  return () => {
    cancelled = true;
  };
}, [isLoggedIn, activePage]);


  // FETCH INVENTORY, RESOURCES AND BATCHES
useEffect(() => {
  if (!isLoggedIn || activePage !== "Inventory") return;

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  const token = localStorage.getItem("access_token");

  if (!apiBaseUrl || !token) {
    setInventoryError("Please log in to view inventory.");
    return;
  }

  let cancelled = false;

  async function loadInventory() {
    setInventoryLoading(true);
    setInventoryError("");

    try {
      const headers = {
        Authorization: `Bearer ${token}`,
      };

      const [inventoryRes, resourcesRes, batchesRes] =
        await Promise.all([
          fetch(`${apiBaseUrl}/inventory`, { headers }),
          fetch(`${apiBaseUrl}/resources`, { headers }),
          fetch(`${apiBaseUrl}/resource-batches`, { headers }),
        ]);

      if (
        inventoryRes.status === 401 ||
        resourcesRes.status === 401 ||
        batchesRes.status === 401
      ) {
        handleLogout();
        throw new Error("Session expired. Please log in again.");
      }

      if (!inventoryRes.ok || !resourcesRes.ok || !batchesRes.ok) {
        throw new Error("One or more inventory APIs failed to load.");
      }

      const [inventoryData, resourcesData, batchesData] =
        await Promise.all([
          inventoryRes.json(),
          resourcesRes.json(),
          batchesRes.json(),
        ]);

      if (!cancelled) {
        setInventory(Array.isArray(inventoryData) ? inventoryData : []);
        setResources(Array.isArray(resourcesData) ? resourcesData : []);
        setBatches(Array.isArray(batchesData) ? batchesData : []);
      }
    } catch (error) {
      if (!cancelled) {
        setInventoryError(error.message || "Unable to load inventory.");
      }
    } finally {
      if (!cancelled) setInventoryLoading(false);
    }
  }

  loadInventory();

  return () => {
    cancelled = true;
  };
}, [isLoggedIn, activePage]);


  // FETCH EQUIPMENT AND MAINTENANCE RECORDS
  useEffect(() => {
    if (!isLoggedIn || activePage !== "Equipment") return;

    let cancelled = false;

    async function loadEquipment() {
      setEquipmentLoading(true);
      setEquipmentError("");

      try {
        const [equipmentData, maintenanceData] = await Promise.all([
          getEquipment(),
          getMaintenanceRecords(),
        ]);

        if (!cancelled) {
          setEquipment(
            Array.isArray(equipmentData) ? equipmentData : []
          );

          setMaintenanceRecords(
            Array.isArray(maintenanceData) ? maintenanceData : []
          );
        }
      } catch (error) {
        if (!cancelled) {
          setEquipmentError(
            error.message || "Unable to load equipment data."
          );
        }
      } finally {
        if (!cancelled) {
          setEquipmentLoading(false);
        }
      }
    }

    loadEquipment();

    return () => {
      cancelled = true;
    };
  }, [isLoggedIn, activePage]);

  // FETCH REPORT DATA
useEffect(() => {
  if (!isLoggedIn || activePage !== "Reports & Evaluation") return;

  let cancelled = false;

  async function loadReports() {
    setReportsLoading(true);
    setReportsError("");

    try {
      const data = await getReportsData();

      if (!cancelled) {
        setReportData(data);
      }
    } catch (error) {
      if (!cancelled) {
        setReportsError(
          error.message || "Unable to load report data."
        );
      }
    } finally {
      if (!cancelled) {
        setReportsLoading(false);
      }
    }
  }

  loadReports();

  return () => {
    cancelled = true;
  };
}, [isLoggedIn, activePage]);


  // APPROVE OR REJECT RECOMMENDATION
  async function handleRecommendationAction(
    recommendationId,
    action
  ) {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
    const token = localStorage.getItem("access_token");

    if (!apiBaseUrl || !token) {
      setRecommendationsError(
        "Please log in again to manage recommendations."
      );
      return;
    }

    setRecommendationActionId(recommendationId);
    setRecommendationsError("");

    try {
      const response = await fetch(
        `${apiBaseUrl}/recommendations/${recommendationId}/${action}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        handleLogout();
        throw new Error("Session expired. Please log in again.");
      }

      if (!response.ok) {
        throw new Error(
          data.detail || `Action failed (${response.status})`
        );
      }

      setRecommendations((current) =>
        current.map((item) =>
          item.recommendation_id === recommendationId
            ? {
                ...item,
                status:
                  action === "approve" ? "APPROVED" : "REJECTED",
              }
            : item
        )
      );
    } catch (error) {
      setRecommendationsError(
        error.message || "Could not update recommendation."
      );
    } finally {
      setRecommendationActionId(null);
    }
  }

  // RUN RESOURCE OPTIMIZATION
async function handleRunOptimization() {
  setOptimizationLoading(true);
  setOptimizationError("");
  setGenerationMessage("");

  try {
    const data = await getResourceOptimization();
    setOptimizationData(data);
  } catch (error) {
    setOptimizationError(error.message);
  } finally {
    setOptimizationLoading(false);
  }
}

// GENERATE RECOMMENDATIONS
async function handleGenerateRecommendations() {
  setGenerationLoading(true);
  setGenerationMessage("");
  setOptimizationError("");

  try {
    const data = await generateRecommendations();

    setGenerationMessage(
      `${data.recommendations?.length ?? 0} recommendation(s) generated successfully.`
    );
  } catch (error) {
    setOptimizationError(error.message);
  } finally {
    setGenerationLoading(false);
  }
}

  const pageDescriptions = {
    Inventory:
      "Review resource stock, availability and expiry information.",

    "Demand Forecasting":
      "Explore historical demand and predicted resource requirements.",

    "Risk & Alerts":
      "Monitor potential shortages, wastage and equipment risks.",

    Equipment:
      "Review equipment utilization and maintenance requirements.",

    "Resource Optimization":
      "Explore suggested transfers and resource allocation.",

    Recommendations:
      "Review recommendations and their approval status.",

    "Reports & Evaluation":
      "Review model performance and system evaluation.",
  };

  const isDashboard = activePage === "Dashboard";

  const highRiskCount = alerts.filter(
    (alert) => (alert.risk_level || "").toUpperCase() === "HIGH"
  ).length;

  // INVENTORY DATA PROCESSING
const inventoryDetails = inventory.map((item) => {
  const resource = resources.find(
    (r) => r.resource_id === item.resource_id
  );

  const itemBatches = batches.filter(
    (batch) => batch.inventory_id === item.inventory_id
  );

  const reorderLevel = resource?.reorder_level ?? 0;

  return {
    ...item,
    resource_name: resource?.resource_name || "Unknown resource",
    category: resource?.category || "Uncategorized",
    unit: resource?.unit || "units",
    reorder_level: reorderLevel,
    safety_stock: resource?.safety_stock ?? 0,
    batches: itemBatches,
    stockStatus:
      item.usable_quantity <= reorderLevel
        ? "Low Stock"
        : "Healthy",
  };
});

const categories = [
  "All",
  ...new Set(inventoryDetails.map((item) => item.category)),
];

const filteredInventory = inventoryDetails.filter((item) => {
  const matchesSearch = item.resource_name
    .toLowerCase()
    .includes(inventorySearch.toLowerCase());

  const matchesCategory =
    categoryFilter === "All" ||
    item.category === categoryFilter;

  return matchesSearch && matchesCategory;
});

const totalCurrentStock = inventory.reduce(
  (sum, item) => sum + Number(item.current_quantity || 0),
  0
);

const totalUsableStock = inventory.reduce(
  (sum, item) => sum + Number(item.usable_quantity || 0),
  0
);

const lowStockCount = inventoryDetails.filter(
  (item) => item.stockStatus === "Low Stock"
).length;

const hospitalInventoryIds = new Set(
  inventory.map((item) => item.inventory_id)
);

const hospitalBatches = batches.filter(
  (batch) => hospitalInventoryIds.has(batch.inventory_id)
);

const expiredBatchCount = hospitalBatches.filter(
  (batch) => new Date(batch.expiry_date) < new Date()
).length;

  // LOGIN SCREEN
  if (!isLoggedIn) {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: "24px",
          background: "#f4f7fb",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <form
          onSubmit={handleLogin}
          style={{
            width: "100%",
            maxWidth: "420px",
            boxSizing: "border-box",
            background: "white",
            padding: "32px",
            borderRadius: "16px",
            boxShadow: "0 12px 36px rgba(20, 40, 80, 0.12)",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              letterSpacing: "1.5px",
              color: "#2673d9",
              marginBottom: "8px",
            }}
          >
            CARESYNC
          </div>

          <h1
            style={{
              margin: "0 0 8px",
              color: "#17243b",
              fontSize: "28px",
            }}
          >
            Hospital Admin Login
          </h1>

          <p
            style={{
              margin: "0 0 24px",
              color: "#64748b",
              lineHeight: 1.5,
            }}
          >
            Sign in to access Hospital Resource Intelligence.
          </p>

          <label
            htmlFor="login-email"
            style={{
              display: "block",
              marginBottom: "7px",
              fontWeight: 600,
              color: "#334155",
            }}
          >
            Email
          </label>

          <input
            id="login-email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "12px",
              marginBottom: "16px",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              fontSize: "15px",
            }}
          />

          <label
            htmlFor="login-password"
            style={{
              display: "block",
              marginBottom: "7px",
              fontWeight: 600,
              color: "#334155",
            }}
          >
            Password
          </label>

          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "12px",
              marginBottom: "16px",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              fontSize: "15px",
            }}
          />

          {loginError && (
            <p
              role="alert"
              style={{
                color: "#b91c1c",
                background: "#fef2f2",
                padding: "10px",
                borderRadius: "8px",
                fontSize: "14px",
              }}
            >
              {loginError}
            </p>
          )}

          <button
            type="submit"
            disabled={loginLoading}
            style={{
              width: "100%",
              padding: "12px",
              border: 0,
              borderRadius: "8px",
              background: loginLoading ? "#93b7e8" : "#2563eb",
              color: "white",
              fontWeight: 700,
              fontSize: "15px",
              cursor: loginLoading ? "wait" : "pointer",
            }}
          >
            {loginLoading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </main>
    );
  }

  // MAIN APPLICATION
  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">✚</div>

          <div>
            <h2>CareSync</h2>
            <span>RESOURCE INTELLIGENCE</span>
          </div>
        </div>

        <div className="nav-caption">WORKSPACE</div>

        <nav className="navigation">
          {navigation.map((item) => (
            <button
              key={item.label}
              className={`nav-item ${
                activePage === item.label ? "active" : ""
              }`}
              onClick={() => setActivePage(item.label)}
            >
              <span className="nav-icon">{item.icon}</span>

              <span>{item.label}</span>

              {item.label === "Risk & Alerts" && (
                <span className="nav-count">
                  {alertsLoading ? "…" : alerts.length}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon">?</div>

            <strong>Need assistance?</strong>

            <p>
              Review your resource management workflow.
            </p>

            <button
              onClick={() =>
                setActivePage("Reports & Evaluation")
              }
            >
              View reports <span>→</span>
            </button>
          </div>

          <div className="profile">
            <div className="avatar">A</div>

            <div className="profile-info">
              <strong>Hospital Admin</strong>
              <span>Administrator</span>
            </div>

              <button
                type="button"
                className="profile-menu"
                onClick={handleLogout}
                title="Logout"
                aria-label="Logout"
              >
                <span className="logout-icon" aria-hidden="true">
                  ↪
                </span>
                <span>Logout</span>
              </button>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">
        {/* TOPBAR */}
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>

            <span className="breadcrumb-separator">/</span>

            <strong>{activePage}</strong>
          </div>

          <div className="topbar-actions">
            <span className="demo-label">
              <span /> Demo preview
            </span>

            <button
              className="icon-button"
              aria-label="Notifications"
              onClick={() => setActivePage("Risk & Alerts")}
            >
              ♧<i />
            </button>

            <div className="top-avatar">A</div>
          </div>
        </header>

        <div className="page-content">
          {/* PAGE HEADER */}
          <section className="welcome-row">
            <div>
              <div className="eyebrow">
                HOSPITAL RESOURCE INTELLIGENCE
              </div>

              <h1>
                {isDashboard
                  ? "Dashboard Overview"
                  : activePage}
              </h1>

              <p>
                {isDashboard
                  ? "Monitor resources, anticipate demand and make informed decisions."
                  : pageDescriptions[activePage]}
              </p>
            </div>

            <button
              className="primary-button"
              onClick={() =>
                setActivePage("Resource Optimization")
              }
            >
              <span>✧</span> Optimize Resources
            </button>
          </section>

          {/* DASHBOARD PAGE */}
          {isDashboard ? (
            <>
              {/* METRIC CARDS */}
              <section className="metric-grid">
                {[
                  {
                    label: "Total Resources",
                    value: dashboardSummary?.total_resources,
                    change: "Registered resource types",
                    icon: "▤",
                    color: "blue",
                  },
                  {
                    label: "Low Stock Items",
                    value: dashboardSummary?.low_stock_count,
                    change: "Require attention",
                    icon: "↓",
                    color: "orange",
                  },
                  {
                    label: "Expiry Alerts",
                    value:
                      (dashboardSummary?.expired_batch_count ?? 0) +
                      (dashboardSummary?.expiring_within_30_days_count ??
                        0),
                    change: "Expired or expiring within 30 days",
                    icon: "♧",
                    color: "purple",
                  },
                  {
                    label: "Pending Approvals",
                    value: dashboardSummary?.pending_recommendations,
                    change: "Awaiting admin action",
                    icon: "✓",
                    color: "green",
                  },
                ].map((metric) => (
                  <article
                    className="metric-card"
                    key={metric.label}
                  >
                    <div className="metric-top">
                      <span className="metric-label">
                        {metric.label}
                      </span>

                      <span
                        className={`metric-icon ${metric.color}`}
                      >
                        {metric.icon}
                      </span>
                    </div>

                    <div className="metric-value">
                      {summaryLoading
                        ? "…"
                        : metric.value ?? "—"}
                    </div>

                    <div className="metric-foot">
                      <span
                        className={`metric-dot ${metric.color}`}
                      />

                      {metric.change}
                    </div>
                  </article>
                ))}
              </section>

              {summaryError && (
                <p className="placeholder-note" role="alert">
                  {summaryError}
                </p>
              )}

              {/* CHART AND PRIORITY ALERTS */}
              <section className="dashboard-grid">
                {/* STOCK CHART */}
                <article className="panel demand-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Current Stock Overview</h2>

                      <p>
                        Live stock totals from your hospital inventory
                      </p>
                    </div>

                    <button
                      className="select-button"
                      onClick={() => setActivePage("Inventory")}
                    >
                      View inventory ↗
                    </button>
                  </div>

                  {summaryLoading ? (
                    <p className="chart-empty">
                      Loading inventory summary…
                    </p>
                  ) : dashboardSummary ? (
                    <>
                      <div className="stock-chart-wrap">
                        <ResponsiveContainer
                          width="100%"
                          height={230}
                        >
                          <BarChart
                            data={[
                              {
                                label: "Current stock",
                                quantity: Number(
                                  dashboardSummary.total_current_stock ??
                                    0
                                ),
                              },
                              {
                                label: "Usable stock",
                                quantity: Number(
                                  dashboardSummary.total_usable_stock ??
                                    0
                                ),
                              },
                            ]}
                            margin={{
                              top: 12,
                              right: 12,
                              left: 0,
                              bottom: 4,
                            }}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              vertical={false}
                            />

                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 11 }}
                            />

                            <YAxis
                              allowDecimals={false}
                              tick={{ fontSize: 10 }}
                            />

                            <Tooltip />

                            <Legend />

                            <Bar
                              dataKey="quantity"
                              name="Quantity"
                              fill="#347ce0"
                              radius={[6, 6, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="chart-note">
                        <span className="note-icon">i</span>

                        This chart uses live totals returned by the
                        dashboard API; it is not a demand forecast.
                      </div>
                    </>
                  ) : (
                    <p className="chart-empty">
                      Dashboard summary is not available yet.
                    </p>
                  )}
                </article>

                {/* PRIORITY ALERTS */}
                <article className="panel alerts-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Priority Alerts</h2>

                      <p>Items that may need attention</p>
                    </div>

                    <span className="alert-total">
                      {String(alerts.length).padStart(2, "0")}
                    </span>
                  </div>

                  <div className="alert-list">
                    {alertsLoading && (
                      <p>Loading risk alerts...</p>
                    )}

                    {alertsError && (
                      <p className="placeholder-note">
                        {alertsError}
                      </p>
                    )}

                    {!alertsLoading &&
                      !alertsError &&
                      alerts.slice(0, 3).map((alert, index) => {
                        const level = (
                          alert.risk_level || "LOW"
                        ).toLowerCase();

                        const symbol =
                          level === "high"
                            ? "!"
                            : level === "medium"
                              ? "△"
                              : "✓";

                        return (
                          <div
                            className="alert-item"
                            key={`${alert.risk_id}-${index}`}
                          >
                            <div
                              className={`alert-symbol ${
                                level === "high"
                                  ? "critical"
                                  : level === "medium"
                                    ? "warning"
                                    : "normal"
                              }`}
                            >
                              {symbol}
                            </div>

                            <div className="alert-copy">
                              <strong>
                                {alert.resource_name ||
                                  "Resource alert"}
                              </strong>

                              <span>
                                {alert.message ||
                                  `Risk level: ${
                                    alert.risk_level || "Unknown"
                                  }`}
                              </span>

                              <small>
                                Shortage risk:{" "}
                                {Number(
                                  alert.shortage_risk ?? 0
                                ).toFixed(1)}
                                %
                              </small>
                            </div>

                            <span className="alert-arrow">›</span>
                          </div>
                        );
                      })}

                    {!alertsLoading &&
                      !alertsError &&
                      alerts.length === 0 && (
                        <p>No active risk alerts.</p>
                      )}
                  </div>

                  <button
                    className="text-button"
                    onClick={() =>
                      setActivePage("Risk & Alerts")
                    }
                  >
                    View all alerts <span>→</span>
                  </button>
                </article>
              </section>

              {/* INVENTORY AND RECOMMENDATIONS */}
              <section className="bottom-grid">
                {/* INVENTORY SNAPSHOT */}
                <article className="panel inventory-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Inventory Snapshot</h2>

                      <p>
                        Live inventory and expiry summary
                      </p>
                    </div>

                    <button
                      className="select-button"
                      onClick={() => setActivePage("Inventory")}
                    >
                      View inventory ↗
                    </button>
                  </div>

                  <div className="inventory-table">
                    <div className="inventory-row inventory-header">
                      <span>Metric</span>
                      <span>Value</span>
                      <span>Status</span>
                    </div>

                    <div className="inventory-row">
                      <span>Total inventory records</span>

                      <strong>
                        {summaryLoading
                          ? "…"
                          : dashboardSummary?.total_inventory_records ??
                            "—"}
                      </strong>

                      <span className="status-pill normal">
                        Tracked
                      </span>
                    </div>

                    <div className="inventory-row">
                      <span>Expired batches</span>

                      <strong>
                        {summaryLoading
                          ? "…"
                          : dashboardSummary?.expired_batch_count ??
                            "—"}
                      </strong>

                      <span
                        className={`status-pill ${
                          (dashboardSummary?.expired_batch_count ?? 0) >
                          0
                            ? "danger"
                            : "normal"
                        }`}
                      >
                        {(dashboardSummary?.expired_batch_count ?? 0) >
                        0
                          ? "Action needed"
                          : "Clear"}
                      </span>
                    </div>

                    <div className="inventory-row">
                      <span>Expiring within 30 days</span>

                      <strong>
                        {summaryLoading
                          ? "…"
                          : dashboardSummary?.expiring_within_30_days_count ??
                            "—"}
                      </strong>

                      <span
                        className={`status-pill ${
                          (dashboardSummary?.expiring_within_30_days_count ??
                            0) > 0
                            ? "warning"
                            : "normal"
                        }`}
                      >
                        {(dashboardSummary?.expiring_within_30_days_count ??
                          0) > 0
                          ? "Monitor"
                          : "Clear"}
                      </span>
                    </div>
                  </div>
                </article>

                {/* RECOMMENDED ACTIONS */}
                <article className="panel recommendation-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Recommended Actions</h2>

                      <p>Suggested next steps</p>
                    </div>

                    <span className="recommendation-icon">
                      ✧
                    </span>
                  </div>

                  <div className="recommendation-body">
                    <div className="recommendation-tag">
                      RESOURCE REDISTRIBUTION
                    </div>

                    <h3>Review inter-hospital transfers</h3>

                    <p>
                      Check whether available resources can be
                      moved to facilities with shortages.
                    </p>

                    <button
                      className="primary-button small-button"
                      onClick={() =>
                        setActivePage("Recommendations")
                      }
                    >
                      Review recommendations <span>→</span>
                    </button>
                  </div>
                </article>
              </section>
            </>
          ) : activePage === "Inventory" ? (
  <section className="inventory-page">

    {inventoryError && (
      <p className="placeholder-note" role="alert">
        {inventoryError}
      </p>
    )}

    {inventoryLoading ? (
      <div className="panel">
        Loading inventory data...
      </div>
    ) : (
      <>
        <div className="metric-grid">
          <article className="metric-card">
            <span className="metric-label">Inventory Records</span>
            <div className="metric-value">{inventory.length}</div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Current Stock</span>
            <div className="metric-value">{totalCurrentStock.toLocaleString()}</div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Usable Stock</span>
            <div className="metric-value">{totalUsableStock.toLocaleString()}</div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Low Stock Items</span>
            <div className="metric-value">{lowStockCount}</div>
          </article>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Hospital Inventory</h2>
              <p>Live resource and stock information</p>
            </div>

            <span className="status-pill normal">
              Live Data
            </span>
          </div>

          <div className="inventory-toolbar">
            <input
              type="text"
              placeholder="Search resources..."
              value={inventorySearch}
              onChange={(event) =>
                setInventorySearch(event.target.value)
              }
            />

            <select
              value={categoryFilter}
              onChange={(event) =>
                setCategoryFilter(event.target.value)
              }
            >
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>

          <div className="inventory-table-wrapper">
            <table className="inventory-data-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Category</th>
                  <th>Current Stock</th>
                  <th>Reserved</th>
                  <th>Usable</th>
                  <th>Reorder Level</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {filteredInventory.map((item) => (
                  <tr key={item.inventory_id}>
                    <td>
                      <strong>{item.resource_name}</strong>
                      <small>ID: {item.resource_id}</small>
                    </td>

                    <td>{item.category}</td>

                    <td>
                      {item.current_quantity} {item.unit}
                    </td>

                    <td>{item.reserved_quantity}</td>

                    <td>
                      <strong>{item.usable_quantity}</strong>
                    </td>

                    <td>{item.reorder_level}</td>

                    <td>
                      <span
                        className={`status-pill ${
                          item.stockStatus === "Low Stock"
                            ? "danger"
                            : "normal"
                        }`}
                      >
                        {item.stockStatus}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {filteredInventory.length === 0 && (
              <p className="chart-empty">
                No inventory records found.
              </p>
            )}
          </div>
        </div>

        <div className="panel batch-panel">
          <div className="panel-heading">
            <div>
              <h2>Batch & Expiry Tracking</h2>
              <p>Expiry information for your hospital's inventory</p>
            </div>
          </div>

          <div className="inventory-table-wrapper">
            <table className="inventory-data-table">
              <thead>
                <tr>
                  <th>Batch Number</th>
                  <th>Inventory ID</th>
                  <th>Quantity</th>
                  <th>Manufacturing Date</th>
                  <th>Expiry Date</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {hospitalBatches.map((batch) => {
                  const expired =
                    new Date(batch.expiry_date) < new Date();

                  const daysRemaining = Math.ceil(
                    (new Date(batch.expiry_date).getTime() -
                      new Date().getTime()) /
                      (1000 * 60 * 60 * 24)
                  );

                  const expiringSoon =
                    !expired && daysRemaining <= 30;

                  return (
                    <tr key={batch.batch_id}>
                      <td>
                        <strong>{batch.batch_number}</strong>
                      </td>

                      <td>{batch.inventory_id}</td>

                      <td>{batch.quantity}</td>

                      <td>{batch.manufacturing_date}</td>

                      <td>{batch.expiry_date}</td>

                      <td>
                        <span
                          className={`status-pill ${
                            expired
                              ? "danger"
                              : expiringSoon
                                ? "warning"
                                : "normal"
                          }`}
                        >
                          {expired
                            ? "Expired"
                            : expiringSoon
                              ? "Expiring Soon"
                              : "Valid"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {hospitalBatches.length === 0 && (
              <p className="chart-empty">
                No batches found for this hospital.
              </p>
            )}
          </div>

          <p className="placeholder-note">
            Expired batches: {expiredBatchCount}
          </p>
        </div>
      </>
    )}

    <button
      className="select-button"
      onClick={() => setActivePage("Dashboard")}
    >
      ← Back to dashboard
    </button>
  </section>

) : activePage === "Resource Optimization" ? (
  <section className="optimization-page">
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Resource Allocation Optimization</h2>
          <p>
            AI-based demand planning and inter-hospital
            resource allocation using OR-Tools.
          </p>
        </div>
        <span className="status-pill normal">OR-Tools</span>
      </div>

      <button
        className="primary-button"
        onClick={handleRunOptimization}
        disabled={optimizationLoading}
      >
        {optimizationLoading ? "Optimizing..." : "Run Optimization"}
      </button>

      {optimizationError && (
        <p className="placeholder-note" role="alert">
          {optimizationError}
        </p>
      )}

      {generationMessage && (
        <p className="placeholder-note">{generationMessage}</p>
      )}
    </div>

    {optimizationData && (
      <>
        <div className="metric-grid">
          <article className="metric-card">
            <span className="metric-label">Optimization Status</span>
            <div className="metric-value">
              {optimizationData.optimization?.status || "—"}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Objective Value</span>
            <div className="metric-value">
              {optimizationData.optimization?.objective_value ?? "—"}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Redistribution Plans</span>
            <div className="metric-value">
              {optimizationData.optimization?.redistribution?.length ?? 0}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Shortage Alerts</span>
            <div className="metric-value">
              {optimizationData.optimization?.shortage?.length ?? 0}
            </div>
          </article>
        </div>

        {[
          {
            title: "Redistribution",
            key: "redistribution",
            render: (item) =>
              `Hospital ${item.source_hospital_id} → Hospital ${item.target_hospital_id} | Resource ID: ${item.resource_id} | Quantity: ${item.quantity}`,
          },
          {
            title: "Procurement",
            key: "procurement",
            render: (item) => JSON.stringify(item),
          },
          {
            title: "Shortages",
            key: "shortage",
            render: (item) => JSON.stringify(item),
          },
          {
            title: "Projected Excess / Wastage",
            key: "wastage",
            render: (item) =>
              `Hospital ${item.hospital_id} | Resource ${item.resource_id} | Excess: ${item.excess_quantity}`,
          },
          {
            title: "Maintenance",
            key: "maintenance",
            render: (item) => JSON.stringify(item),
          },
        ].map((section) => {
          const items =
            optimizationData.optimization?.[section.key] ?? [];

          return (
            <div className="panel" key={section.key}>
              <h2>{section.title}</h2>
              {items.length === 0 ? (
                <p className="chart-empty">
                  No {section.title.toLowerCase()} actions identified.
                </p>
              ) : (
                <ul>
                  {items.map((item, index) => (
                    <li key={index} style={{ marginBottom: "12px" }}>
                      {section.render(item)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}

        <div className="panel">
          <h2>Generate Recommendations</h2>
          <p>
            Convert optimization results into actionable
            recommendations for administrative review.
          </p>
          <button
            className="primary-button"
            onClick={handleGenerateRecommendations}
            disabled={generationLoading}
          >
            {generationLoading
              ? "Generating..."
              : "Generate Recommendations"}
          </button>
        </div>
      </>
    )}

    <button
      className="select-button"
      onClick={() => setActivePage("Dashboard")}
    >
      ← Back to dashboard
    </button>
  </section>


) : activePage === "Demand Forecasting" ? (
  <section className="panel section-placeholder">
    <div className="panel-heading">
      <div>
        <h2>30-Day Demand Forecast</h2>
        <p>Predictions generated by your trained ML model</p>
      </div>
      <span className="status-pill normal">{forecastModel}</span>
    </div>

    {forecastLoading && <p>Loading forecasts...</p>}

    {forecastError && (
      <p className="placeholder-note" role="alert">{forecastError}</p>
    )}

    {!forecastLoading && !forecastError && (
      <>
        <div className="metric-grid">
          <article className="metric-card">
            <span className="metric-label">Forecast Records</span>
            <div className="metric-value">{forecasts.length}</div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Resource</span>
            <div className="metric-value" style={{fontSize:"20px"}}>
              {forecasts[0]?.resource_name || "—"}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Average Predicted Demand</span>
            <div className="metric-value">
              {forecasts.length
                ? Math.round(
                    forecasts.reduce(
                      (sum, item) => sum + Number(item.predicted_quantity),
                      0
                    ) / forecasts.length
                  )
                : 0}
            </div>
          </article>
        </div>

        {forecasts.length > 0 ? (
          <>
            <h3>Predicted Daily Demand</h3>
            <div style={{width:"100%", height:320}}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={forecasts}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="forecast_date"
                    tick={{fontSize:10}}
                    angle={-35}
                    textAnchor="end"
                    height={65}
                  />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="predicted_quantity"
                    name="Predicted Demand"
                    fill="#347ce0"
                    radius={[5,5,0,0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <h3>Forecast Details</h3>
            <div style={{overflowX:"auto"}}>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr>
                    <th style={{textAlign:"left",padding:"12px"}}>Date</th>
                    <th style={{textAlign:"left",padding:"12px"}}>Resource</th>
                    <th style={{textAlign:"left",padding:"12px"}}>Predicted Quantity</th>
                    <th style={{textAlign:"left",padding:"12px"}}>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {forecasts.map((item) => (
                    <tr key={item.prediction_id}>
                      <td style={{padding:"12px"}}>{item.forecast_date}</td>
                      <td style={{padding:"12px"}}>{item.resource_name}</td>
                      <td style={{padding:"12px"}}>
                        {Number(item.predicted_quantity).toFixed(0)}
                      </td>
                      <td style={{padding:"12px"}}>{item.model_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p>No forecast records available.</p>
        )}
      </>
    )}

    <button className="select-button" onClick={() => setActivePage("Dashboard")}>
      ← Back to dashboard
    </button>
  </section>


) : activePage === "Equipment" ? (
  <section className="inventory-page">

    {equipmentError && (
      <p className="placeholder-note" role="alert">
        {equipmentError}
      </p>
    )}

    {equipmentLoading ? (
      <div className="panel">Loading equipment data...</div>
    ) : (
      <>
        <div className="metric-grid">
          <article className="metric-card">
            <span className="metric-label">Total Equipment</span>
            <div className="metric-value">{equipment.length}</div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Operational</span>
            <div className="metric-value">
              {equipment.filter(
                item => item.status?.toLowerCase() === "operational"
              ).length}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Urgent Criticality</span>
            <div className="metric-value">
              {equipment.filter(
                item => item.criticality === "URGENT"
              ).length}
            </div>
          </article>

          <article className="metric-card">
            <span className="metric-label">Maintenance Records</span>
            <div className="metric-value">
              {maintenanceRecords.length}
            </div>
          </article>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Hospital Equipment</h2>
              <p>Live equipment information from the backend</p>
            </div>
            <span className="status-pill normal">Live Data</span>
          </div>

          <div className="inventory-table-wrapper">
            <table className="inventory-data-table">
              <thead>
                <tr>
                  <th>Equipment</th>
                  <th>Type</th>
                  <th>Manufacturer</th>
                  <th>Model</th>
                  <th>Utilization</th>
                  <th>Criticality</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {equipment.map(item => {
                  const utilization =
                    Number(item.available_hours) > 0
                      ? (
                          Number(item.utilization_hours) /
                          Number(item.available_hours)
                        ) * 100
                      : null;

                  return (
                    <tr key={item.equipment_id}>
                      <td>
                        <strong>{item.equipment_name}</strong>
                        <small>ID: {item.equipment_id}</small>
                      </td>

                      <td>{item.equipment_type}</td>
                      <td>{item.manufacturer}</td>
                      <td>{item.model_number}</td>

                      <td>
                        {item.utilization_hours} / {item.available_hours}
                        {utilization !== null
                          ? ` (${utilization.toFixed(1)}%)`
                          : " (N/A)"}
                      </td>

                      <td>
                        <span className={`status-pill ${
                          item.criticality === "URGENT" ||
                          item.criticality === "HIGH"
                            ? "danger"
                            : "warning"
                        }`}>
                          {item.criticality}
                        </span>
                      </td>

                      <td>
                        <span className="status-pill normal">
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {equipment.length === 0 && (
              <p className="chart-empty">
                No equipment records found.
              </p>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Maintenance History</h2>
              <p>Recorded equipment maintenance activities</p>
            </div>
          </div>

          <div className="inventory-table-wrapper">
            <table className="inventory-data-table">
              <thead>
                <tr>
                  <th>Equipment</th>
                  <th>Maintenance Type</th>
                  <th>Date</th>
                  <th>Cost</th>
                  <th>Downtime</th>
                  <th>Failure Reason</th>
                </tr>
              </thead>

              <tbody>
                {maintenanceRecords.map(record => {
                  const item = equipment.find(
                    e => e.equipment_id === record.equipment_id
                  );

                  return (
                    <tr key={record.maintenance_id}>
                      <td>
                        {item?.equipment_name ||
                          `Equipment ${record.equipment_id}`}
                      </td>
                      <td>{record.maintenance_type}</td>
                      <td>{record.maintenance_date}</td>
                      <td>
                        {record.maintenance_cost != null
                          ? `₹${Number(record.maintenance_cost).toLocaleString("en-IN")}`
                          : "—"}
                      </td>
                      <td>{record.downtime_hours} hours</td>
                      <td>{record.failure_reason || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {maintenanceRecords.length === 0 && (
              <p className="chart-empty">
                No maintenance records found.
              </p>
            )}
          </div>
        </div>
      </>
    )}

    <button
      className="select-button"
      onClick={() => setActivePage("Dashboard")}
    >
      ← Back to dashboard
    </button>
  </section>
) : activePage === "Recommendations" ? (
            /* RECOMMENDATIONS PAGE */
            <section className="panel section-placeholder">
              <div className="placeholder-icon">✓</div>

              <h2>Recommendations</h2>

              <p>
                Live recommendations generated by the hospital
                resource optimization engine.
              </p>

              {recommendationsLoading && (
                <p>Loading recommendations...</p>
              )}

              {recommendationsError && (
                <p
                  className="placeholder-note"
                  role="alert"
                >
                  {recommendationsError}
                </p>
              )}

              {!recommendationsLoading &&
                !recommendationsError &&
                recommendations.length === 0 && (
                  <p>
                    No recommendations found. Generate
                    recommendations from the backend first.
                  </p>
                )}

              <div className="risk-alert-list">
                {recommendations.map((item) => (
                  <article
                    className="panel"
                    key={item.recommendation_id}
                    style={{
                      textAlign: "left",
                      marginBottom: "16px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: "12px",
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      <h3 style={{ margin: 0 }}>
                        {item.resource_name ||
                          item.equipment_name ||
                          item.recommendation_type}
                      </h3>

                      <span
                        className={`status-pill ${
                          item.status === "PENDING"
                            ? "warning"
                            : item.status === "APPROVED"
                              ? "normal"
                              : "danger"
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>

                    <p>
                      <strong>Type:</strong>{" "}
                      {item.recommendation_type}
                    </p>

                    {item.resource_name && (
                      <p>
                        <strong>Resource:</strong>{" "}
                        {item.resource_name} (ID: {item.resource_id})
                      </p>
                    )}

                    {item.equipment_name && (
                      <p>
                        <strong>Equipment:</strong>{" "}
                        {item.equipment_name} (ID: {item.equipment_id})
                      </p>
                    )}

                    <p>
                      <strong>Recommended quantity:</strong>{" "}
                      {item.recommended_quantity ?? "—"}
                    </p>

                    {item.source_hospital_id != null && (
                      <p>
                        <strong>Source hospital:</strong>{" "}
                        {item.source_hospital_id}
                      </p>
                    )}

                    {item.target_hospital_id != null && (
                      <p>
                        <strong>Target hospital:</strong>{" "}
                        {item.target_hospital_id}
                      </p>
                    )}

                    <p>
                      <strong>Priority:</strong>{" "}
                      {item.priority || "Not specified"}
                    </p>

                    {item.reason && (
                      <p>
                        <strong>Reason:</strong> {item.reason}
                      </p>
                    )}

                    {item.status === "PENDING" && (
                      <div
                        style={{
                          display: "flex",
                          gap: "10px",
                          flexWrap: "wrap",
                          marginTop: "14px",
                        }}
                      >
                        <button
                          className="primary-button"
                          disabled={
                            recommendationActionId ===
                            item.recommendation_id
                          }
                          onClick={() =>
                            handleRecommendationAction(
                              item.recommendation_id,
                              "approve"
                            )
                          }
                        >
                          {recommendationActionId ===
                          item.recommendation_id
                            ? "Saving..."
                            : "Approve"}
                        </button>

                        <button
                          className="select-button"
                          disabled={
                            recommendationActionId ===
                            item.recommendation_id
                          }
                          onClick={() =>
                            handleRecommendationAction(
                              item.recommendation_id,
                              "reject"
                            )
                          }
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </article>
                ))}
              </div>

              <button
                className="select-button"
                onClick={() => setActivePage("Dashboard")}
              >
                ← Back to dashboard
              </button>
            </section>
          ) : activePage === "Risk & Alerts" ? (
            /* RISK & ALERTS PAGE */
            <section className="panel section-placeholder">
              <div className="placeholder-icon">✧</div>

              <h2>Risk & Alerts</h2>

              <p>
                Live risk alerts fetched from the hospital backend.
              </p>

              {alertsLoading && (
                <p>Loading risk alerts...</p>
              )}

              {alertsError && (
                <p className="placeholder-note">
                  {alertsError}
                </p>
              )}

              {!alertsLoading && !alertsError && (
                <>
                  <div className="metric-grid">
                    <article className="metric-card">
                      <h3>Total Alerts</h3>
                      <p>{alerts.length}</p>
                    </article>

                    <article className="metric-card">
                      <h3>High-Risk Alerts</h3>
                      <p>{highRiskCount}</p>
                    </article>
                  </div>

                  <div className="risk-alert-list">
                    {alerts
                      .filter((alert) =>
                        (alert.resource_name || "")
                          .toLowerCase()
                          .includes(search.trim().toLowerCase())
                      )
                      .map((alert, index) => (
                        <article
                          className="panel"
                          key={`${alert.risk_id}-${index}`}
                        >
                          <h3>
                            {alert.resource_name ||
                              "Unknown resource"}
                          </h3>

                          <p>
                            Risk level:{" "}
                            <strong>
                              {alert.risk_level || "Unknown"}
                            </strong>
                          </p>

                          <p>
                            Shortage risk:{" "}
                            {Number(
                              alert.shortage_risk ?? 0
                            ).toFixed(2)}
                            %
                          </p>

                          <p>
                            Wastage risk:{" "}
                            {Number(
                              alert.wastage_risk ?? 0
                            ).toFixed(2)}
                            %
                          </p>

                          <p>
                            Expected stockout:{" "}
                            {alert.expected_stockout_date ||
                              "Not available"}
                          </p>

                          <p>
                            Expected wastage quantity:{" "}
                            {alert.expected_wastage_quantity ?? 0}
                          </p>

                          <p>
                            {alert.message ||
                              "No additional details available."}
                          </p>
                        </article>
                      ))}
                  </div>

                  {alerts.length === 0 && (
                    <p>No risk alerts found.</p>
                  )}

                  {alerts.length > 0 &&
                    alerts.filter((alert) =>
                      (alert.resource_name || "")
                        .toLowerCase()
                        .includes(search.trim().toLowerCase())
                    ).length === 0 && (
                      <p>No alerts match your search.</p>
                    )}
                </>
              )}

              <button
                className="select-button"
                onClick={() => setActivePage("Dashboard")}
              >
                ← Back to dashboard
              </button>
            </section>
          ) : activePage === "Reports & Evaluation" ? (
            /* REPORTS & EVALUATION PAGE */
            <section className="reports-page panel section-placeholder">
              <div className="placeholder-icon">▥</div>
              <h2>Reports & Evaluation</h2>
              <p>
                Consolidated overview of inventory, demand forecasts, risk,
                recommendations and equipment maintenance.
              </p>

              {reportsLoading && <p>Loading reports and evaluation data...</p>}

              {reportsError && (
                <p className="placeholder-note" role="alert">
                  {reportsError}
                </p>
              )}

              {!reportsLoading && !reportsError && reportData && (
                <>
                  <div className="metric-grid">
                    {[
                      {
                        label: "Resource Types",
                        value: reportData.summary?.total_resources ?? reportData.resources?.length ?? 0,
                        note: "Registered resource types",
                      },
                      {
                        label: "Usable Stock",
                        value: Number(reportData.summary?.total_usable_stock ?? 0).toLocaleString(),
                        note: "Units available for use",
                      },
                      {
                        label: "Risk Alerts",
                        value: reportData.alerts?.length ?? 0,
                        note: "Current high/critical alerts",
                      },
                      {
                        label: "Equipment",
                        value: reportData.summary?.total_equipment ?? reportData.equipment?.length ?? 0,
                        note: "Registered equipment",
                      },
                    ].map((metric) => (
                      <article className="metric-card" key={metric.label}>
                        <h3>{metric.label}</h3>
                        <p>{metric.value}</p>
                        <span>{metric.note}</span>
                      </article>
                    ))}
                  </div>

                  <div className="metric-grid" style={{ marginTop: "20px" }}>
                    <article className="metric-card">
                      <h3>Inventory Records</h3>
                      <p>{reportData.summary?.total_inventory_records ?? reportData.inventory?.length ?? 0}</p>
                      <span>Tracked inventory entries</span>
                    </article>
                    <article className="metric-card">
                      <h3>Low Stock Items</h3>
                      <p>{reportData.summary?.low_stock_count ?? 0}</p>
                      <span>At or below reorder level</span>
                    </article>
                    <article className="metric-card">
                      <h3>Expired Batches</h3>
                      <p>{reportData.summary?.expired_batch_count ?? 0}</p>
                      <span>Based on recorded expiry dates</span>
                    </article>
                    <article className="metric-card">
                      <h3>Forecast Records</h3>
                      <p>{reportData.forecasts?.length ?? 0}</p>
                      <span>Saved demand predictions</span>
                    </article>
                  </div>

                  <div className="panel" style={{ marginTop: "22px", padding: "20px" }}>
                    <h3>Demand Forecast Summary</h3>
                    <p>
                      Forecast model: <strong>{reportData.forecasts?.[0]?.model_name ?? "Not available"}</strong>
                    </p>
                    <p>
                      Forecast horizon: <strong>{reportData.forecasts?.length ?? 0}</strong> saved prediction records
                    </p>
                    <p>
                      Average predicted demand:{" "}
                      <strong>
                        {reportData.forecasts?.length
                          ? (
                              reportData.forecasts.reduce(
                                (sum, item) => sum + Number(item.predicted_quantity || 0),
                                0
                              ) / reportData.forecasts.length
                            ).toFixed(2)
                          : "—"}
                      </strong>
                    </p>
                    <p className="placeholder-note">
                      These values summarize stored predictions. They are not actual future consumption or model-accuracy scores.
                    </p>
                  </div>

                  <div className="panel" style={{ marginTop: "22px", padding: "20px" }}>
                    <h3>Risk Evaluation</h3>
                    {reportData.alerts?.length ? (
                      <div className="risk-alert-list">
                        {reportData.alerts.map((alert) => (
                          <article className="panel" key={alert.risk_id}>
                            <h4>{alert.resource_name || "Unknown resource"}</h4>
                            <p>
                              Risk level: <strong>{alert.risk_level || "Not available"}</strong>
                            </p>
                            <p>
                              Shortage risk: {Number(alert.shortage_risk || 0).toFixed(2)}%
                            </p>
                            <p>
                              Wastage risk: {Number(alert.wastage_risk || 0).toFixed(2)}%
                            </p>
                            <p>
                              Expected stockout: {alert.expected_stockout_date || "Not available"}
                            </p>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p>No current high/critical risk alerts were returned.</p>
                    )}
                  </div>

                  <div className="panel" style={{ marginTop: "22px", padding: "20px" }}>
                    <h3>Recommendation Summary</h3>
                    <div className="metric-grid">
                      {["PENDING", "SOURCE_APPROVED", "APPROVED", "EXECUTED", "REJECTED"].map((status) => (
                        <article className="metric-card" key={status}>
                          <h3>{status.replaceAll("_", " ")}</h3>
                          <p>
                            {(reportData.recommendations || []).filter(
                              (item) => (item.status || "").toUpperCase() === status
                            ).length}
                          </p>
                        </article>
                      ))}
                    </div>
                    <p>Total recommendations: <strong>{reportData.recommendations?.length ?? 0}</strong></p>
                  </div>

                  <div className="panel" style={{ marginTop: "22px", padding: "20px" }}>
                    <h3>Equipment & Maintenance Evaluation</h3>
                    <p>
                      Equipment records: <strong>{reportData.equipment?.length ?? 0}</strong>
                      {" · "}
                      Maintenance records: <strong>{reportData.maintenance?.length ?? 0}</strong>
                    </p>
                    <p>
                      Operational equipment:{" "}
                      <strong>
                        {(reportData.equipment || []).filter(
                          (item) => (item.status || "").toLowerCase() === "operational"
                        ).length}
                      </strong>
                    </p>
                    {reportData.maintenance?.length ? (
                      <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Equipment ID</th>
                              <th>Maintenance Date</th>
                              <th>Type</th>
                              <th>Downtime (hrs)</th>
                              <th>Cost</th>
                            </tr>
                          </thead>
                          <tbody>
                            {reportData.maintenance.map((record, index) => (
                              <tr key={record.maintenance_id ?? `${record.equipment_id}-${index}`}>
                                <td>{record.equipment_id ?? "—"}</td>
                                <td>{record.maintenance_date ?? "—"}</td>
                                <td>{record.maintenance_type ?? "—"}</td>
                                <td>{record.downtime_hours ?? 0}</td>
                                <td>₹{Number(record.maintenance_cost ?? 0).toLocaleString("en-IN")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p>No maintenance records were returned.</p>
                    )}
                  </div>

                  <div className="panel" style={{ marginTop: "22px", padding: "20px" }}>
                    <h3>Inventory Evaluation</h3>
                    <p>
                      Current stock: <strong>{Number(reportData.summary?.total_current_stock ?? 0).toLocaleString()}</strong>
                      {" · "}
                      Usable stock: <strong>{Number(reportData.summary?.total_usable_stock ?? 0).toLocaleString()}</strong>
                    </p>
                    <p>
                      Reserved stock:{" "}
                      <strong>
                        {(
                          Number(reportData.summary?.total_current_stock ?? 0) -
                          Number(reportData.summary?.total_usable_stock ?? 0)
                        ).toLocaleString()}
                      </strong>
                    </p>
                    <p>
                      Batches tracked: <strong>{reportData.batches?.length ?? 0}</strong>
                    </p>
                  </div>
                </>
              )}

              {!reportsLoading && !reportsError && !reportData && (
                <p>No report data is available yet.</p>
              )}

              <button
                className="select-button"
                onClick={() => setActivePage("Dashboard")}
              >
                ← Back to dashboard
              </button>
            </section>
          ) : (

            <section className="panel section-placeholder">
              <div className="placeholder-icon">✧</div>

              <h2>{activePage}</h2>

              <p>{pageDescriptions[activePage]}</p>

              <div className="placeholder-search">
                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder={`Search ${activePage.toLowerCase()}...`}
                />

                <button
                  className="primary-button"
                  onClick={() => setSearch(search.trim())}
                >
                  Search
                </button>
              </div>

              <p className="placeholder-note">
                This page is a frontend starting point. We'll
                implement its features and connect the relevant
                backend APIs in the next steps.
              </p>

              <button
                className="select-button"
                onClick={() => setActivePage("Dashboard")}
              >
                ← Back to dashboard
              </button>
            </section>
          )}

          {/* FOOTER */}
          <footer className="footer">
            <span>
              CareSync{" "}
              <span className="footer-separator">·</span>{" "}
              Hospital Resource Intelligence
            </span>

            <span>
              Project dashboard{" "}
              <span className="footer-separator">·</span>{" "}
              Frontend preview
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;