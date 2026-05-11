/** ================================================================
 *  Paylabs Payment Form — Frontend JS
 * ================================================================ */

odoo.define('payment_paylabs.payment_form', ['@web/core/utils/hooks', 'web.core'], function (require) {
    'use strict';

    // ================================================================
    // Odoo 16+ (OWL-based payment form)
    // ================================================================
    try {
        const { PaymentForm } = require('@payment/js/payment_form');
        const { patch } = require('@web/core/utils/patch');

        patch(PaymentForm.prototype, {
            async _submitForm(ev) {
                const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
                if (checkedRadio && checkedRadio.dataset.providerCode === 'paylabs') {
                    const wrapper = checkedRadio.closest('.o_payment_option_card, .payment_option_form, .list-group-item') || checkedRadio.closest('label').parentElement;
                    const methodName = (wrapper.textContent || '').toLowerCase();
                    
                    if (methodName.includes('virtual account') || methodName.includes('va') || methodName.includes('bank transfer')) {
                        const vaSelect = document.querySelector('#paylabs-va-bank-select');
                        if (vaSelect && vaSelect.value) {
                            this._paylabsPaymentType = vaSelect.value;
                        } else {
                            alert("Silakan pilih Bank Virtual Account terlebih dahulu sebelum melanjutkan.");
                            return false; // Stop submission
                        }
                    } else {
                        this._paylabsPaymentType = 'QRIS';
                    }
                }
                return super._submitForm(ev);
            },

            _prepareTransactionRouteParams() {
                const params = super._prepareTransactionRouteParams(...arguments);
                if (this._paylabsPaymentType) {
                    params.paylabs_payment_type = this._paylabsPaymentType;
                }
                return params;
            }
        });
    } catch (e) {
        // Odoo < 16 fallback
    }

    // ================================================================
    // DOM Injection for VA Dropdown
    // ================================================================
    function initPaylabsPaymentForm() {
        const container = document.querySelector('.o_payment_form, #payment_method, .o_payment_options');
        if (!container) return;

        // Use event delegation to handle clicks
        container.addEventListener('change', function (ev) {
            const target = ev.target;
            if (target && target.type === 'radio' && target.name === 'o_payment_radio') {
                _handleSelectionChange(target);
            }
        });

        // Also check on load or click for OWL re-renders
        container.addEventListener('click', function(ev) {
            setTimeout(() => {
                const checked = container.querySelector('input[name="o_payment_radio"]:checked');
                if (checked) _handleSelectionChange(checked);
            }, 50);
        });

        // Initial check
        const initialRadio = container.querySelector('input[name="o_payment_radio"]:checked');
        if (initialRadio) {
            _handleSelectionChange(initialRadio);
        }
    }

    function _handleSelectionChange(radio) {
        // Clean up previous dropdowns
        document.querySelectorAll('.paylabs-va-dropdown-container').forEach(el => el.remove());

        if (radio.dataset.providerCode !== 'paylabs') return;

        const wrapper = radio.closest('.o_payment_option_card, .payment_option_form, .list-group-item') || radio.closest('label').parentElement;
        if (!wrapper) return;

        const methodName = (wrapper.textContent || '').toLowerCase();
        const isVA = methodName.includes('virtual account') || methodName.includes('va') || methodName.includes('bank transfer');

        if (isVA) {
            // Find a good place to inject the dropdown (usually inline form container)
            let injectTarget = wrapper.querySelector('.o_payment_method_inline_form, .payment_option_inline_form');
            if (!injectTarget) injectTarget = wrapper;

            const div = document.createElement('div');
            div.className = 'paylabs-va-dropdown-container mt-2 mb-3 ms-0 ms-md-4';
            div.innerHTML = `
                <div class="p-3 bg-light rounded border">
                    <label class="form-label fw-semibold text-dark mb-2">💳 Pilih Bank Virtual Account</label>
                    <select id="paylabs-va-bank-select" class="form-select border-secondary shadow-sm" style="max-width: 100%;">
                        <option value="">-- Pilih Bank --</option>
                        <option value="BCAVA">BCA Virtual Account</option>
                        <option value="BRIVA">BRI Virtual Account</option>
                        <option value="BNIVA">BNI Virtual Account</option>
                        <option value="MandiriVA">Mandiri Virtual Account</option>
                        <option value="PermataVA">Permata Virtual Account</option>
                        <option value="CIMBVA">CIMB Niaga Virtual Account</option>
                        <option value="BSIVA">BSI Virtual Account</option>
                        <option value="NobuVA">Nobu Virtual Account</option>
                        <option value="BTNVA">BTN Virtual Account</option>
                        <option value="MaybankVA">Maybank Virtual Account</option>
                        <option value="DanamonVA">Danamon Virtual Account</option>
                        <option value="BNCVA">BNC Virtual Account</option>
                        <option value="MuamalatVA">Muamalat Virtual Account</option>
                        <option value="SinarmasVA">Sinarmas Virtual Account</option>
                    </select>
                </div>
            `;
            injectTarget.appendChild(div);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPaylabsPaymentForm);
    } else {
        initPaylabsPaymentForm();
    }

    return { initPaylabsPaymentForm };
});

