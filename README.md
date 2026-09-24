# Intelligent Hospital Resource Allocation & Wastage Prevention System

A full-stack intelligent hospital resource management system designed to help hospitals **monitor resources, forecast demand, identify shortage and wastage risks, and support better resource allocation**.

## 🚀 Overview

Hospitals often face problems such as resource shortages, overstocking, expired medicines, inefficient inventory management, and difficulty predicting future demand.

This project provides a centralized system for managing hospital resources while using **machine learning and risk analysis** to identify potential shortages and wastage before they become critical.

## ✨ Key Features

* 🏥 **Multi-Hospital Resource Management**

  * Manage hospitals and their available resources.
  * Track resources across multiple hospitals.

* 📦 **Inventory Management**

  * Track resource quantities and batches.
  * Monitor inventory levels and resource usage.

* 📊 **Demand Forecasting**

  * Predict future resource demand using historical consumption data.
  * Generate features from hospital resource usage patterns.

* ⚠️ **Shortage Risk Detection**

  * Identify resources that may face future shortages.
  * Use demand and inventory information for risk assessment.

* 🗑️ **Wastage Risk Detection**

  * Identify resources at risk of overstocking or wastage.
  * Consider inventory and consumption patterns.

* 🔄 **Resource Redistribution**

  * Support resource movement between hospitals based on availability and demand.

* 🚚 **Supplier Management**

  * Maintain supplier information.
  * Track supplier-related resource information.

* 🛠️ **Equipment & Maintenance**

  * Manage hospital equipment.
  * Maintain maintenance records and equipment status.

* 🔐 **Backend Security**

  * Authentication and protected backend functionality.

## 🏗️ System Architecture

```text
                ┌─────────────────────────┐
                │      Hospital Users     │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │       FastAPI Backend    │
                ├─────────────────────────┤
                │ REST APIs                │
                │ Authentication           │
                │ Resource Management      │
                │ Risk Analysis            │
                └────────────┬────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
     ┌──────────────────┐          ┌──────────────────┐
     │   PostgreSQL DB  │          │   ML Pipeline    │
     │                  │          │                  │
     │ Hospitals        │          │ Data Cleaning    │
     │ Resources        │          │ Feature Eng.     │
     │ Inventory        │          │ Forecasting      │
     │ Suppliers        │          │ Risk Detection   │
     │ Equipment        │          │                  │
     └──────────────────┘          └──────────────────┘
```

## 🛠️ Tech Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* Psycopg
* Uvicorn

### Database

* PostgreSQL

### Machine Learning & Data Processing

* Python
* Pandas
* NumPy
* Scikit-learn
* Feature Engineering
* Demand Forecasting

### Development Tools

* VS Code
* Git
* GitHub
* Virtual Environment

## 📁 Project Structure

```text
Intelligent-Hospital-Resources-System/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── config.py
│   ├── security.py
│   │
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │
│   ├── data_pipeline/
│   │   ├── cleaning.py
│   │   ├── feature_engineering.py
│   │   └── load_features.py
│   │
│   ├── ml/
│   │   ├── forecasting.py
│   │   ├── predict_demand.py
│   │   └── train_forecasting_model.py
│   │
│   └── risk/
│       ├── shortage_risk.py
│       └── wastage_risk.py
│
├── data/
│   ├── raw/
│   └── processed/
│
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚙️ Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/Mahak-agrawal05/intelligent-hospital-resource-management-system.git
cd intelligent-hospital-resource-management-system
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root and add your database configuration.

Example:

```env
DATABASE_URL=your_postgresql_database_url
```

Do not commit `.env` to GitHub.

### 5. Run the backend

```bash
uvicorn backend.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## 🔄 ML Pipeline

The machine-learning workflow follows:

```text
Raw Hospital Data
       ↓
Data Cleaning
       ↓
Feature Engineering
       ↓
Processed Features
       ↓
Model Training
       ↓
Demand Forecasting
       ↓
Shortage / Wastage Risk Analysis
       ↓
Resource Allocation Support
```

The system is designed to support **periodic model retraining**, with validation and comparison against the currently deployed model before a replacement is considered.

## 🎯 Project Objectives

1. Reduce hospital resource wastage.
2. Detect potential shortages earlier.
3. Improve inventory visibility.
4. Forecast future resource requirements.
5. Support resource redistribution between hospitals.
6. Improve data-driven hospital resource planning.
7. Provide a foundation for intelligent resource allocation.

## 🔮 Future Enhancements

* React-based hospital management dashboard
* Automated inter-hospital redistribution optimization
* Advanced ML forecasting models
* Real-time inventory alerts
* Automated model retraining pipeline
* Equipment failure prediction
* Supplier lead-time prediction
* Role-based access control
* Cloud deployment
* Monitoring and model performance tracking

## 👩‍💻 Developer

**Mahak Agrawal**

B.Tech — Computer Science Engineering

GitHub: (https://github.com/Mahak-agrawal05)

## 📌 Project Status

**Currently under active development.**

The backend, database layer, data-processing pipeline, demand forecasting, and resource risk-analysis components are being developed incrementally.
