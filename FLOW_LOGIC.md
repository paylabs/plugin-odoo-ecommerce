# Flow Logic: Paylabs Odoo Module

This document provides a deep dive into the logic flow of the Paylabs Odoo integration, covering everything from the user's click to the final payment confirmation.

---

## 1. High-Level Sequence Diagram

The following diagram illustrates the interaction between the Customer, Odoo, and the Paylabs API.

```mermaid
sequenceDiagram
    participant User as Customer (Browser)
    participant Odoo as Odoo Server
    participant Paylabs as Paylabs API Gateway
    participant Webhook as Paylabs Notification Service

    %% Phase 1: Initiation
    Note over User, Odoo: Phase 1: Initiation
    User->>Odoo: Select Paylabs & Click "Pay Now"
    Odoo->>Odoo: Prepare transaction data
    Odoo->>Odoo: Map Odoo Method to Paylabs Type (e.g., BCAVA)
    Odoo->>Odoo: Generate Unique merchantTradeNo (Ref + ID + Salt)

    %% Phase 2: API Call & Signing
    Note over Odoo, Paylabs: Phase 2: API Request & Signing
    Odoo->>Odoo: Create StringToSign (Method:Path:BodyHash:Timestamp)
    Odoo->>Odoo: Sign using Merchant Private Key (RSA-SHA256)
    Odoo->>Paylabs: POST /v2.3/qris/create OR /va/create
    
    %% Phase 3: Display Instructions
    Note over Paylabs, User: Phase 3: Response & Display
    Paylabs-->>Odoo: Returns QR Code / VA Number
    Odoo->>Odoo: Store QR/VA details in payment.transaction
    Odoo-->>User: Redirect to Instruction Page (Internal Result Page)
    User->>User: Sees QRIS / VA Number & Instructions

    %% Phase 4: Payment & Notification
    Note over User, Webhook: Phase 4: External Payment
    User->>Paylabs: User completes payment via Bank/E-Wallet
    Paylabs->>Webhook: Detects successful payment
    Webhook->>Odoo: POST /payment/paylabs/webhook (with X-SIGNATURE)

    %% Phase 5: Verification & Completion
    Note over Odoo: Phase 5: Verification & Completion
    Odoo->>Odoo: Extract Body & X-SIGNATURE
    Odoo->>Odoo: Verify Signature using Paylabs Public Key
    alt Signature Valid
        Odoo->>Odoo: Find Transaction by merchantTradeNo
        Odoo->>Odoo: Set State to 'Done'
        Odoo->>Odoo: Trigger Odoo Payment Post-Processing
        Odoo-->>Webhook: Return {"errCode": "0"}
    else Signature Invalid
        Odoo->>Odoo: Log Security Warning
        Odoo-->>Webhook: Return {"errCode": "1"}
    end
```

---

## 2. Detailed Logical Components

### A. Trade Number Uniqueness (merchantTradeNo)
**Logic**: Paylabs strictly forbids duplicate trade numbers. If a customer fails a payment and tries again for the same order, Odoo's standard reference might trigger a "Duplicate" error.
**Solution**:
1.  Take the Odoo `reference` (e.g., `S00001`).
2.  Append the internal `transaction_id` (e.g., `45`).
3.  Append a short random salt based on `timestamp`.
**Result**: `S00001-45-7821` (Guaranteed unique even on retries).

### B. Payment Type Mapping
**Logic**: Odoo uses generic codes like `bank_bca`. Paylabs v2.3 requires specific case-sensitive strings.
**Mapping Flow**:
- `bca` / `bank_bca` / `bca_va` -> **`BCAVA`**
- `mandiri` -> **`MandiriVA`**
- `qris` -> **`QRIS`**
- Fallback: Capitalize and append `VA` (e.g., `bni` -> `BNIVA`).

### C. Webhook Idempotency
**Logic**: Payment Gateways often send notifications multiple times to ensure delivery.
**Execution**:
1.  Check if `payment.transaction` is already in `done` or `cancel` state.
2.  If `done`, simply acknowledge the webhook with `errCode: 0` without reprocessing.
3.  This prevents duplicate accounting entries.

---

## 3. Security Flow (RSA-SHA256)

The security logic ensures that neither the Request nor the Notification can be faked.

### Outgoing Request Signing:
1.  **Body**: Compact JSON (no whitespace).
2.  **Payload Hash**: SHA256 of the Body.
3.  **StringToSign**: `POST:/payment/v2.3/path:HASH:TIMESTAMP`.
4.  **Signing**: Encrypt the StringToSign's SHA256 hash with your **Private Key**.

### Inbound Webhook Verification:
1.  **Payload Hash**: SHA256 of the raw Request Body.
2.  **StringToSign**: `POST:/payment/paylabs/webhook:HASH:TIMESTAMP`.
3.  **Verification**: Decrypt the provided `X-SIGNATURE` using **Paylabs Public Key** and compare it with the local StringToSign.

---

## 4. State Machine Transition

| Trigger Event | Initial State | API Response | New State | Odoo Action |
| :--- | :--- | :--- | :--- | :--- |
| Click "Pay Now" | `draft` | Success | `pending` | Display QR/VA |
| Webhook (Status 02) | `pending` | Valid Sign | `done` | Confirm Order/Invoice |
| Webhook (Status 09) | `pending` | Valid Sign | `cancel` | Log Failure |
| Manual Expire | `pending` | N/A | `cancel` | - |

---
*Documented for Developer Reference - Paylabs Odoo Integration*
