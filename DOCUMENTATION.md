# Complete Documentation: Paylabs Payment Plugin for Odoo

Welcome to the official documentation for the **Paylabs Payment Gateway** integration for Odoo. This module is designed to provide a seamless, secure, and efficient payment experience for merchants in Indonesia using the Odoo platform.

---

## 1. Introduction

**Paylabs** is a licensed Payment Gateway provider in Indonesia. This plugin integrates Paylabs services directly into the Odoo Payment module, allowing your customers to pay using popular payment methods such as QRIS and Virtual Accounts from various major banks.

### Supported Payment Methods:
*   **QRIS**: Instant payment via e-wallet applications (Gopay, OVO, Dana, LinkAja, ShopeePay) and Mobile Banking.
*   **Virtual Account (VA)**: BCA, Mandiri, BNI, BRI, Permata, CIMB Niaga, BSI, Nobu, BTN, Maybank, Danamon, BNC, Muamalat, and Sinarmas.

---

## 🛠️ Technical Documentation (Developer Only)

If you are a developer looking to understand the Python code structure, data flow, or how RSA encryption works in this module, please read:
👉 **[LOGIC.md - Architecture & Logic Flow](./LOGIC.md)**

---

## 2. System Requirements

Before installation, ensure your system meets the following requirements:

*   **Odoo**: Version 16, 17, or 18 (Community or Enterprise Edition).
*   **Python Dependencies**: This module requires the `pycryptodome` library for RSA encryption handling.
    *   *Installation:* `pip install pycryptodome`
*   **Currency**: Ensure **IDR** currency is activated in Odoo (Accounting -> Configuration -> Currencies).

---

## 3. Installation

1.  **Upload Module**: Copy the `payment_paylabs` folder to your Odoo server's `addons` directory.
2.  **Update App List**: Log in to Odoo as Administrator, enable *Developer Mode*, then go to the **Apps** menu and click **Update Apps List**.
3.  **Install**: Search for "Paylabs" in the Apps menu search bar, then click the **Install** button.

---

## 4. Provider Configuration

After installation is complete, follow these steps to configure the connection to Paylabs:

1.  Navigate to **Accounting** (or Invoicing) -> **Configuration** -> **Payment Providers**.
2.  Find and click on **Paylabs**.
3.  In the **Credentials** tab, complete the following information:
    *   **State**: Select **Test Mode** for Sandbox integration, or **Enabled** for Live Production.
    *   **Merchant ID (X-PARTNER-ID)**: Obtain this from the Paylabs merchant portal.
    *   **RSA Private Key (Merchant)**: Enter your RSA Private Key (PEM format).
    *   **RSA Public Key (Paylabs)**: Enter the Public Key provided by Paylabs.
4.  In the **Configuration** tab, you can set:
    *   **Payment Journal**: The accounting journal where transactions will be recorded.
    *   **Enabled VA Banks**: A comma-separated list of VA bank codes (Example: `BCAVA, BRIVA, MandiriVA`).
5.  **IMPORTANT: Refresh Payment Method Icons**
    *   Click the **"Refresh Payment Method Icons"** button at the top of the form or in the configuration tab. This will automatically sync bank and QRIS logos for a clean checkout page appearance.

---

## 5. Webhook Configuration (Notification URL)

To ensure order statuses in Odoo automatically change to "Paid" after a customer pays, you must set the **Notification URL** in the Paylabs Merchant Portal.

*   **Your Webhook URL**: `https://your-odoo-domain.com/payment/paylabs/webhook`
*   **Recommendation**: If you are using multi-database, use the format: `https://your-odoo-domain.com/payment/paylabs/webhook?db=DATABASE_NAME`

### How to Configure in the Paylabs Portal:
1.  Log in to the [Paylabs Portal](https://portal.paylabs.co.id).
2.  Go to **Settings** -> **Technical Settings**.
3.  Enter the URL above into the **Notification URL** (or Webhook URL) field.
4.  Save the settings.

---

## 6. Payment Flow (User Experience)

### Customer Steps:
1.  Customer proceeds to checkout on the Odoo Website.
2.  Selects **Paylabs** (or a specific Bank/QRIS logo) as the payment method.
3.  After clicking "Pay Now", the system processes the request to Paylabs.
4.  **Instruction Page**:
    *   If **QRIS** is selected: Customer will see a QR Code on the screen to be scanned immediately.
    *   If **VA** is selected: Customer will see the Virtual Account number and transfer instructions.
5.  After successful payment, the page will automatically redirect to the success status, and the transaction in the Odoo backend will change to **Done**.

---

## 7. Technical Features & Security

*   **RSA-SHA256 Signing**: All requests to the Paylabs API are signed using the RSA-SHA256 algorithm in accordance with the latest banking security standards.
*   **Signature Verification**: Inbound webhooks are verified for authenticity using the Paylabs Public Key to prevent fraudulent transactions.
*   **Smart Trade Numbering**: Uses unique references to ensure no duplicate transactions on the Paylabs side.
*   **Automatic Assets**: The module includes optimized image assets (bank/QRIS logos) for the Odoo frontend display.

---

## 8. Troubleshooting (FAQ)

**Q: Why doesn't the Paylabs button appear at checkout?**
*   A: Ensure the Provider is in **Enabled** or **Test Mode** state, and the transaction currency is **IDR**. Paylabs only supports IDR.

**Q: Transaction is paid but the status in Odoo remains "Pending"?**
*   A: Check your Odoo logs. Ensure your Odoo server is accessible from the internet (not blocked by firewall/local network) so Paylabs can send Webhook notifications. Also, verify if the Webhook URL is correctly set in the Paylabs Portal.

**Q: "Signature Verification Failed" Error?**
*   A: Ensure the **RSA Public Key (Paylabs)** entered in Odoo is correct and matches the one in the Paylabs portal.

---

## 9. Support Contact

If you encounter further technical issues, please contact:
*   **Technical Support**: [support@paylabs.co.id](mailto:support@paylabs.co.id)
*   **Website**: [https://paylabs.co.id](https://paylabs.co.id)
*   **API Docs**: [https://docs.paylabs.co.id](https://docs.paylabs.co.id)

---
*Created by the Advanced Agentic Coding team for Paylabs Indonesia.*
