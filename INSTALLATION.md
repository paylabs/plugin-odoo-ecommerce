# Panduan Instalasi Modul Paylabs Odoo

Dokumen ini menjelaskan langkah-langkah untuk menginstal dan mengonfigurasi modul pembayaran **Paylabs** pada sistem Odoo (eCommerce & Invoicing).

---

## 1. Prasyarat Sistem

Sebelum memulai instalasi, pastikan sistem Anda memenuhi kriteria berikut:

- **Versi Odoo**: Odoo 16, 17, atau 18 (Community atau Enterprise).
- **Python Library**: Modul ini membutuhkan pustaka `pycryptodome` untuk enkripsi RSA.
  ```bash
  pip install pycryptodome
  ```
- **Mata Uang**: Pastikan mata uang **IDR (Rupiah)** sudah diaktifkan di Odoo Anda.
  - Pergi ke: **Accounting** > **Configuration** > **Currencies**.
  - Cari **IDR** dan pastikan statusnya **Active**.

---

## 2. Langkah Instalasi Modul

### Cara A: Melalui Antarmuka Odoo (GUI)
1. **Unggah Folder Modul**:
   Salin folder `payment_paylabs` ke dalam direktori `addons` pada server Odoo Anda.
2. **Perbarui Daftar Aplikasi**:
   - Masuk ke Odoo sebagai **Administrator**.
   - Aktifkan **Developer Mode** (Mode Pengembang).
   - Pergi ke menu **Apps**.
   - Klik tombol **Update Apps List** di bilah menu atas.
3. **Instal Modul**:
   - Cari kata kunci "Paylabs" di kolom pencarian aplikasi.
   - Klik tombol **Activate** atau **Install** pada modul "Payment Provider: Paylabs".

---

## 3. Pengaturan Hak Akses (Linux Server)

Jika Anda menggunakan server Linux (Ubuntu/Debian), pastikan Odoo memiliki izin untuk membaca file modul:

1. **Ubah Kepemilikan**:
   Ganti `odoo` dengan nama user sistem Odoo Anda jika berbeda.
   ```bash
   sudo chown -R odoo:odoo /path/to/addons/payment_paylabs
   ```

2. **Atur Permission**:
   Berikan izin akses standar (755 untuk folder, 644 untuk file).
   ```bash
   sudo find /path/to/addons/payment_paylabs -type d -exec chmod 755 {} \;
   sudo find /path/to/addons/payment_paylabs -type f -exec chmod 644 {} \;
   ```

---

## 4. Konfigurasi Provider Paylabs

Setelah modul terinstal, Anda perlu menghubungkannya dengan akun Paylabs Anda:

1. Pergi ke menu **Accounting** (atau Invoicing) > **Configuration** > **Payment Providers**.
2. Pilih **Paylabs**.
3. Di tab **Credentials**, lengkapi data berikut:
   - **State**: Pilih **Test Mode** (untuk percobaan/Sandbox) atau **Enabled** (untuk transaksi asli/Production).
   - **Merchant ID (X-PARTNER-ID)**: Masukkan Partner ID yang didapat dari Portal Paylabs.
   - **RSA Private Key (Merchant)**: Masukkan Private Key RSA Anda (format PEM).
   - **RSA Public Key (Paylabs)**: Masukkan Public Key yang disediakan oleh Paylabs.
4. Di tab **Configuration**, tentukan **Payment Journal** yang akan digunakan untuk mencatat transaksi masuk.
5. Klik **Save**.

> [!IMPORTANT]
> **Sinkronisasi Metode Pembayaran**:
> Klik tombol **"Refresh Payment Method Icons"** di bagian atas formulir untuk memuat logo bank dan QRIS secara otomatis.

---

## 5. Konfigurasi Webhook (Notification URL)

Agar status pesanan di Odoo otomatis berubah menjadi "Lunas" (Paid), Anda harus mengatur URL Notifikasi di Portal Merchant Paylabs.

- **URL Webhook Anda**: `https://domain-anda.com/payment/paylabs/webhook`
- **Multi-Database**: Jika server Odoo Anda memiliki banyak database, gunakan format:
  `https://domain-anda.com/payment/paylabs/webhook?db=NAMA_DATABASE`

---

## 6. Troubleshooting (Masalah Umum)

- **Tombol Paylabs Tidak Muncul**: Pastikan mata uang transaksi adalah **IDR**. Tombol tidak akan muncul jika menggunakan USD atau mata uang lainnya.
- **Status Tidak Berubah Menjadi Paid**:
  - Pastikan server Odoo dapat diakses dari internet (tidak terhalang firewall).
  - Pastikan URL Webhook di Portal Paylabs sudah benar.
- **Error Signature Verification**: Periksa kembali apakah **RSA Public Key (Paylabs)** yang dimasukkan di Odoo sudah sesuai dengan yang ada di Portal Paylabs.

---
*Dibuat oleh tim integrasi Paylabs.*
