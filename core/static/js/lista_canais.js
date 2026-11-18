/*
 * Tela de listas de canais: Esc fecha a dica (descrição) da lista em foco ou sob o mouse.
 * A dica aparece por CSS (hover/focus-within); aqui só se adiciona/remove .dica-oculta.
 * JS puro, sem dependências.
 */
(function () {
    'use strict';

    const ITEM = '#telegram-canais .tc-tag-item';

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || !e.target.closest) return;
        const item = e.target.closest(ITEM);
        if (item) item.classList.add('dica-oculta');
    });

    document.querySelectorAll(ITEM).forEach((item) => {
        const mostrar = () => item.classList.remove('dica-oculta');
        item.addEventListener('focusout', mostrar);
        item.addEventListener('mouseleave', mostrar);
    });
})();
