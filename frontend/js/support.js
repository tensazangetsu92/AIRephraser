document.addEventListener('DOMContentLoaded', () => {
    const email = 'humary.service@mail.ru';
    const button = document.getElementById('supportCopyEmailBtn');
    if (!button) return;

    button.addEventListener('click', async () => {
        const copied = await window.copyTextToClipboard?.(email);
        const message = copied
            ? (typeof window.t === 'function' ? window.t('support_email_copied') : 'Email скопирован')
            : (typeof window.t === 'function' ? window.t('support_email_copy_failed') : 'Не удалось скопировать email');
        window.showNotification?.(message, copied ? 'success' : 'error');
    });
});
