<div align="center">
  <img src="images/logo.png" alt="Logo" width="100" height="100">

  # Alpsolar Inteless for Home Assistant
  
  [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
  ![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)
  ![Community](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
  ![Platform](https://img.shields.io/badge/Platform-Home%20Assistant-blue.svg)

  **A professional, native integration for Alpsolar and E-Linter (Inteless) Inverters.**
  *Developed by ICFLOURISH INTEGRATED SERVICES*
</div>

---

### 📖 Introduction
This integration connects Home Assistant directly to the **Inteless (E-Linter)** cloud API used by **Alpsolar Pulse S3** and similar inverters. Unlike basic scripts, this integration automatically handles the complex math required for the Home Assistant Energy Dashboard.

### 🚀 Key Features
* **Automatic Energy Helpers:** Automatically creates Riemann Sum Integrals for Solar, Grid, and Load.
* **Smart Battery Logic:** Automatically splits bidirectional battery power into separate **Charge** and **Discharge** entities for the Energy Dashboard.
* **Global Support:** Choose your region (Europe, Asia, America, or Global) during setup.
* **Zero YAML:** 100% UI-based configuration via Config Flow.
* **Device Grouping:** All entities are neatly organized under one "Alpsolar Inverter" device.

---

### 🛠 Installation

#### Option 1: HACS (Recommended)
1. Open **HACS** > **Integrations**.
2. Click the three dots (top right) > **Custom repositories**.
3. Paste: `https://github.com/chukaonline/ha-alpsolar-inteless`
4. Select Category: **Integration**.
5. Click **Add** and then **Download**.
6. **Restart Home Assistant.**

#### Option 2: Manual
1. Copy the `custom_components/alpsolar_inteless` folder to your HA `/config/custom_components/` directory.
2. **Restart Home Assistant.**

---

### ⚙️ Configuration
1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **Alpsolar Inteless**.
3. Select your **Region** and enter your Inteless Credentials and **Plant ID**.

---

### 📊 Entities Provided
| Type | Entity | Description |
| :--- | :--- | :--- |
| ⚡ **Power** | `Solar PV Power` | Real-time production (W) |
| 🏠 **Power** | `House Load` | Domestic consumption (W) |
| 🔋 **Power** | `Battery Power In/Out` | Separated Charge/Discharge (W) |
| 📈 **Energy** | `Solar PV Power Energy` | Dashboard-ready (kWh) |
| 📈 **Energy** | `Grid Power Energy` | Dashboard-ready (kWh) |
| 🔋 **Energy** | `Battery Energy In/Out` | Dashboard-ready (kWh) |



