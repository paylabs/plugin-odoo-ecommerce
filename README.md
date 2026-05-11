# Paylabs Payment Provider for Odoo

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-16.0%20%7C%2017.0%20%7C%2018.0-714B67.svg)](https://www.odoo.com)

Professional Odoo integration for **Paylabs**, a leading Indonesian payment gateway. This module enables seamless payment processing through QRIS and various Virtual Account (VA) banks.

---

## 🚀 Features

-   **QRIS Support**: Automated QR Code generation (Indonesian Standard).
-   **Virtual Accounts**: Comprehensive support for major Indonesian banks (BCA, Mandiri, BNI, BRI, BSI, BTN, Danamon, Permata, and more).
-   **Secure Communication**: Built-in RSA-SHA256 signature generation and verification.
-   **Automatic Asset Management**: Smart logic to match and display high-quality bank logos in the checkout form.
-   **Real-time Webhooks**: Automated order status updates (Pending -> Done) upon successful payment.
-   **Maintenance Tools**: Built-in utility to refresh and sync payment method icons.

---

## 📖 Documentation

For detailed setup, configuration, and troubleshooting guides in Indonesian, please refer to:
👉 **[INSTALLATION.md (Panduan Instalasi)](./INSTALLATION.md)**
👉 **[DOCUMENTATION.md (Panduan Lengkap)](./DOCUMENTATION.md)**

---

## 🛠 Installation

1.  **Prerequisites**:
    -   Python `pycryptodome` is required for RSA signatures.
    -   Install it via pip: `pip install pycryptodome`
2.  **Deploy**: Upload the `payment_paylabs` folder to your Odoo addons directory.
3.  **Install**: Search for "Paylabs" in the Apps menu and click **Install**.

---

## ⚙️ Quick Configuration

1.  Go to **Accounting -> Configuration -> Payment Providers**.
2.  Select **Paylabs**.
3.  Enter your **Merchant ID** and **RSA Private Key**.
4.  Set the state to **Test Mode** (Sandbox) or **Enabled** (Production).
5.  Click the **"Refresh Payment Method Icons"** button in the configuration tab to apply bank logos.

---

## 🔒 Security

This module follows the latest security standards required by Indonesian financial regulations:
-   **Request Signing**: RSA-SHA256 signatures for every API request.
-   **Webhook Verification**: Inbound notifications are verified using Paylabs' Public Key.
-   **Data Integrity**: Secure handling of payment references and amounts.

---

## 📄 License
This module is licensed under **LGPL-3**.

---

**Developed by**: Paylabs Indonesia & Advanced Agentic Coding
**Support**: [support@paylabs.co.id](mailto:support@paylabs.co.id)
**Website**: [https://paylabs.co.id](https://paylabs.co.id)

