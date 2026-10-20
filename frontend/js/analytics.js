(function () {
    const METRIKA_COUNTER_ID = 113701868;
    const TRACKED_PAYMENT_STORAGE_KEY = 'humary.metrika.tracked-payments.v1';
    const SENSITIVE_INPUT_SELECTOR = 'textarea, input[type="email"], input[type="text"]';
    const SENSITIVE_CONTENT_SELECTOR = [
        '#userEmailText',
        '#result',
        '#studyWorkEdited',
        '#historyDetailOriginal',
        '#historyDetailResult',
        '.history-item-original',
        '.history-item-result',
    ].join(', ');
    let initialized = false;

    function protectSensitiveContent(root = document) {
        const nodes = [];
        if (root.nodeType === Node.ELEMENT_NODE) nodes.push(root);
        const descendants = typeof root.querySelectorAll === 'function'
            ? root.querySelectorAll(`${SENSITIVE_INPUT_SELECTOR}, ${SENSITIVE_CONTENT_SELECTOR}`)
            : [];
        nodes.push(...descendants);

        nodes.forEach((node) => {
            if (node.matches?.(SENSITIVE_INPUT_SELECTOR)) node.classList.add('ym-disable-keys');
            if (node.matches?.(SENSITIVE_CONTENT_SELECTOR)) node.classList.add('ym-hide-content');
        });
    }

    function analyticsAllowed() {
        return window.getCookieConsentPreferences?.()?.analytics === true;
    }

    function init() {
        if (initialized || !analyticsAllowed()) return false;

        window.ym = window.ym || function () {
            (window.ym.a = window.ym.a || []).push(arguments);
        };
        window.ym.l = Date.now();
        window.dataLayer = window.dataLayer || [];

        if (!document.querySelector('script[data-humary-metrika]')) {
            const script = document.createElement('script');
            script.async = true;
            script.src = `https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_COUNTER_ID}`;
            script.dataset.humaryMetrika = 'true';
            document.head.append(script);
        }

        window.ym(METRIKA_COUNTER_ID, 'init', {
            clickmap: true,
            trackLinks: true,
            accurateTrackBounce: true,
            webvisor: true,
            ecommerce: 'dataLayer',
        });
        initialized = true;
        return true;
    }

    function track(goal, params = {}) {
        if (!init()) return false;
        window.ym(METRIKA_COUNTER_ID, 'reachGoal', goal, params);
        return true;
    }

    function readTrackedPayments() {
        try {
            return new Set(JSON.parse(sessionStorage.getItem(TRACKED_PAYMENT_STORAGE_KEY) || '[]'));
        } catch {
            return new Set();
        }
    }

    function trackPurchase(payment) {
        if (!payment?.id || !payment?.fulfilled || !init()) return false;

        const trackedPayments = readTrackedPayments();
        if (trackedPayments.has(payment.id)) return false;

        const amount = Number(payment.amount);
        if (!Number.isFinite(amount) || amount <= 0) return false;

        const productId = `${payment.product_type}:${payment.product_id}`;
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
            ecommerce: {
                currencyCode: payment.currency || 'RUB',
                purchase: {
                    actionField: {
                        id: payment.id,
                        revenue: amount,
                    },
                    products: [{
                        id: productId,
                        name: payment.product_id,
                        category: payment.product_type,
                        price: amount,
                        quantity: 1,
                    }],
                },
            },
        });
        track('payment_succeeded', {
            product_type: payment.product_type,
            product_id: payment.product_id,
            amount,
            currency: payment.currency || 'RUB',
        });

        trackedPayments.add(payment.id);
        try {
            sessionStorage.setItem(TRACKED_PAYMENT_STORAGE_KEY, JSON.stringify([...trackedPayments].slice(-50)));
        } catch {
            // Analytics must never affect checkout if browser storage is unavailable.
        }
        return true;
    }

    window.HumaryAnalytics = { init, track, trackPurchase };
    window.addEventListener('cookieConsentChanged', (event) => {
        if (event.detail?.analytics) init();
    });
    document.addEventListener('DOMContentLoaded', () => {
        protectSensitiveContent();
        new MutationObserver((records) => {
            records.forEach((record) => {
                record.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) protectSensitiveContent(node);
                });
            });
        }).observe(document.body, { childList: true, subtree: true });
        init();
    });
})();
