const NOTIFICATION_TYPES = new Set(['success', 'error', 'warning', 'info']);
const NOTIFICATION_DURATIONS = {
    success: 3500,
    error: 6500,
    warning: 5000,
    info: 3500,
};

let notificationTimeout = null;
let notificationHideTimeout = null;
let activeNotification = null;
let notificationShownAt = 0;
let notificationRemaining = 0;
const notificationQueue = [];
const notificationPauseReasons = new Set();

function getNotificationElements() {
    const toast = document.getElementById('notificationToast');
    return {
        toast,
        message: document.getElementById('notificationMessage'),
        icon: document.getElementById('notificationIcon'),
        close: document.getElementById('notificationClose'),
    };
}

function clearNotificationTimers() {
    if (notificationTimeout) clearTimeout(notificationTimeout);
    if (notificationHideTimeout) clearTimeout(notificationHideTimeout);
    notificationTimeout = null;
    notificationHideTimeout = null;
}

function normalizeNotification(message, type, duration) {
    const normalizedType = NOTIFICATION_TYPES.has(type) ? type : 'info';
    const normalizedDuration = Number(duration);
    return {
        message: String(message || ''),
        type: normalizedType,
        duration: Number.isFinite(normalizedDuration) && normalizedDuration > 0
            ? normalizedDuration
            : NOTIFICATION_DURATIONS[normalizedType],
    };
}

function pauseNotificationDismiss(reason) {
    notificationPauseReasons.add(reason);
    if (!activeNotification || !notificationTimeout) return;
    notificationRemaining = Math.max(0, notificationRemaining - (Date.now() - notificationShownAt));
    clearTimeout(notificationTimeout);
    notificationTimeout = null;
}

function resumeNotificationDismiss(reason) {
    notificationPauseReasons.delete(reason);
    if (notificationPauseReasons.size > 0 || !activeNotification || !notificationRemaining) return;
    scheduleNotificationDismiss();
}

function showNextNotification() {
    if (document.hidden || activeNotification || notificationQueue.length === 0) return;
    showNotificationItem(notificationQueue.shift());
}

function dismissActiveNotification(showNext = true) {
    const { toast } = getNotificationElements();
    clearNotificationTimers();
    notificationPauseReasons.clear();
    if (toast) toast.classList.remove('show');
    activeNotification = null;
    notificationRemaining = 0;

    if (showNext) {
        notificationHideTimeout = window.setTimeout(() => {
            notificationHideTimeout = null;
            showNextNotification();
        }, 220);
    }
}

function scheduleNotificationDismiss() {
    if (!activeNotification || document.hidden || notificationPauseReasons.size > 0) return;
    notificationShownAt = Date.now();
    notificationTimeout = window.setTimeout(() => dismissActiveNotification(true), notificationRemaining);
}

function showNotificationItem(notification) {
    const { toast, message, icon, close } = getNotificationElements();
    if (!toast || !message || !icon || document.hidden) {
        notificationQueue.unshift(notification);
        return;
    }

    const iconClasses = {
        success: 'fa-circle-check',
        error: 'fa-circle-exclamation',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info',
    };

    clearNotificationTimers();
    notificationPauseReasons.clear();
    activeNotification = notification;
    notificationRemaining = notification.duration;
    toast.classList.remove('success', 'error', 'warning', 'info');
    toast.classList.add(notification.type);
    toast.setAttribute('role', notification.type === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', notification.type === 'error' ? 'assertive' : 'polite');
    icon.className = `notification-icon fa-solid ${iconClasses[notification.type]}`;
    message.textContent = notification.message;
    if (close) close.hidden = false;
    toast.classList.add('show');
    scheduleNotificationDismiss();
}

function showNotification(message, type = 'info', duration = null) {
    const notification = normalizeNotification(message, type, duration);
    const { toast } = getNotificationElements();
    if (!toast) return;

    if (document.hidden) {
        notificationQueue.push(notification);
        return;
    }

    if (!activeNotification) {
        showNotificationItem(notification);
        return;
    }

    // A completed or failed operation must replace its earlier informational
    // toast immediately; otherwise users would see an obsolete "processing" message.
    if (activeNotification.type === 'info' && notification.type !== 'info') {
        dismissActiveNotification(false);
        notificationHideTimeout = window.setTimeout(() => {
            notificationHideTimeout = null;
            showNotificationItem(notification);
        }, 160);
        return;
    }

    notificationQueue.push(notification);
}

function closeNotification() {
    if (!activeNotification) return;
    dismissActiveNotification(true);
}

function initNotifications() {
    const { toast, close } = getNotificationElements();
    if (!toast) return;

    close?.addEventListener('click', closeNotification);
    toast.addEventListener('mouseenter', () => pauseNotificationDismiss('pointer'));
    toast.addEventListener('mouseleave', () => resumeNotificationDismiss('pointer'));
    toast.addEventListener('focusin', () => pauseNotificationDismiss('focus'));
    toast.addEventListener('focusout', (event) => {
        if (!toast.contains(event.relatedTarget)) resumeNotificationDismiss('focus');
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            pauseNotificationDismiss('visibility');
            return;
        }
        resumeNotificationDismiss('visibility');
        if (!activeNotification) showNextNotification();
    });

    showNextNotification();
}

document.addEventListener('DOMContentLoaded', initNotifications);

window.showNotification = showNotification;
window.closeNotification = closeNotification;
