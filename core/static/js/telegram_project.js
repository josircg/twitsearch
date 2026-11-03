/*
 * Formulário de projeto Telegram (criação e edição): validação ao vivo, alerta,
 * botão bloqueado, foco no primeiro erro e confirmação ao sair para importar lista.
 * JS puro, sem dependências. As regras espelham telegram/forms.py (TelegramProjectForm);
 * o servidor continua validando tudo, e sem JavaScript o formulário funciona como antes.
 */
(function () {
    'use strict';

    const form = document.querySelector('#telegram-project form');
    if (!form) return;

    // Mesmos textos do servidor (telegram/forms.py)
    const MSG = {
        obrigatorio: 'Este campo é obrigatório.',
        dataFinal: 'A data final não pode ser anterior à data inicial.',
        semTermo: 'Informe ao menos um termo de busca.',
        termoLongo: (inicio) => `Termo muito longo (máximo 2000 caracteres): ${inicio}...`,
        conectivo: (termo) => `Uso inválido de AND/OR no termo: ${termo}`,
        sairSemSalvar: 'Você tem alterações não salvas neste projeto. Sair para importar uma lista mesmo assim?',
    };
    const CONECTIVOS = ['AND', 'OR'];
    const MAX_TERMO = 2000;
    // ordem do formulário: define o primeiro campo inválido, que recebe o foco
    const CAMPOS = ['nome', 'objetivo', 'lista', 'dt_inicio', 'dt_final', 'termos'];

    const campo = (nome) => form.elements[nome];
    const valor = (nome) => (campo(nome).value || '');

    // ---- Regras (cada uma devolve a mensagem de erro ou '') ----

    function validarTermos(texto) {
        // str.splitlines() do Python também quebra em \v, \f, \x1c-\x1e, \x85, \u2028 e
        const termos = texto.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/).map((l) => l.trim()).filter(Boolean);
        if (!termos.length) return MSG.semTermo;
        for (const termo of termos) {
            const letras = Array.from(termo); // conta caracteres, não unidades UTF-16 (como o len() do Python)
            if (letras.length > MAX_TERMO) return MSG.termoLongo(letras.slice(0, 30).join(''));
            const tokens = termo.split(/\s+/);
            const invalido = CONECTIVOS.includes(tokens[0]) || CONECTIVOS.includes(tokens[tokens.length - 1]) ||
                tokens.some((t, i) => i > 0 && CONECTIVOS.includes(t) && CONECTIVOS.includes(tokens[i - 1]));
            if (invalido) return MSG.conectivo(termo);
        }
        return '';
    }

    const REGRAS = {
        nome: (v) => (v.trim() ? '' : MSG.obrigatorio),
        objetivo: (v) => (v.trim() ? '' : MSG.obrigatorio),
        lista: (v) => (v ? '' : MSG.obrigatorio),
        dt_inicio: (v) => (v ? '' : MSG.obrigatorio),
        // valores de <input type="date"> são ISO (aaaa-mm-dd), então a comparação de texto vale
        dt_final: (v) => {
            if (!v) return MSG.obrigatorio;
            const inicio = valor('dt_inicio');
            return inicio && v < inicio ? MSG.dataFinal : '';
        },
        termos: (v) => (v.trim() ? validarTermos(v) : MSG.obrigatorio),
    };

    // ---- Estado ----

    const tocados = new Set();   // campos já alterados (ou enviados): só eles mostram erro
    const servidor = new Set();  // campos com erro vindo do servidor e ainda não editados
    const visiveis = {};         // nome -> mensagem exibida
    const alerta = document.querySelector('#telegram-project .tp-alerta');
    const botao = form.querySelector('.btn-start');

    function divErro(nome, criar) {
        let div = document.getElementById('erro_' + nome);
        if (div || !criar) return div;
        div = document.createElement('div');
        div.className = 'text-danger tp-erro';
        div.id = 'erro_' + nome;
        div.hidden = true;
        // logo após o campo (depois do texto de ajuda, se houver); a lista fica num flex junto do botão de importar
        let ancora = nome === 'lista' ? campo(nome).closest('.d-flex') : campo(nome);
        const proximo = ancora.nextElementSibling;
        if (proximo && proximo.classList.contains('form-text')) ancora = proximo;
        ancora.after(div);
        return div;
    }

    function descritoPor(nome) {
        // ids que já descreviam o campo antes do erro (ajuda e, nos termos, o aviso da edição)
        return ['ajuda_' + nome, nome === 'termos' ? 'termos_aviso' : '']
            .filter((id) => id && document.getElementById(id));
    }

    function exibir(nome, mensagem) {
        const el = campo(nome);
        const div = divErro(nome, Boolean(mensagem));
        const ids = descritoPor(nome);
        if (mensagem) {
            div.textContent = mensagem;
            div.hidden = false;
            el.classList.add('is-invalido');
            el.setAttribute('aria-invalid', 'true');
            el.setAttribute('aria-describedby', ids.concat(div.id).join(' '));
            visiveis[nome] = mensagem;
        } else {
            if (div) {
                div.textContent = '';
                div.hidden = true;
            }
            el.classList.remove('is-invalido');
            el.removeAttribute('aria-invalid');
            if (ids.length) el.setAttribute('aria-describedby', ids.join(' '));
            else el.removeAttribute('aria-describedby');
            delete visiveis[nome];
        }
    }

    function atualizarEnvio() {
        const comErro = Object.keys(visiveis).length > 0;
        if (alerta) alerta.hidden = !comErro;
        if (botao) {
            botao.classList.toggle('is-bloqueado', comErro);
            // aria-disabled em vez de disabled: o clique continua chegando ao handler (mostra os erros e foca o primeiro)
            if (comErro) botao.setAttribute('aria-disabled', 'true');
            else botao.removeAttribute('aria-disabled');
        }
    }

    function validar(nome) {
        exibir(nome, REGRAS[nome](valor(nome)));
    }

    function aoAlterar(nome) {
        tocados.add(nome);
        servidor.delete(nome);
        validar(nome);
        // a data final depende da inicial
        if (nome === 'dt_inicio' && tocados.has('dt_final')) {
            servidor.delete('dt_final');
            validar('dt_final');
        }
        atualizarEnvio();
    }

    // ---- Eventos ----

    CAMPOS.forEach((nome) => {
        const el = campo(nome);
        if (!el) return;
        el.addEventListener('input', () => aoAlterar(nome));
        el.addEventListener('change', () => aoAlterar(nome));
    });

    form.addEventListener('submit', (evento) => {
        let primeiro = null;
        CAMPOS.forEach((nome) => {
            if (!campo(nome)) return;
            tocados.add(nome);
            // erro do servidor ainda não corrigido permanece (o JS não sabe julgar todos os casos)
            if (!servidor.has(nome)) validar(nome);
            if (visiveis[nome] && !primeiro) primeiro = campo(nome);
        });
        atualizarEnvio();
        if (primeiro) {
            evento.preventDefault();
            primeiro.focus();
        }
    });

    // Erros vindos do servidor: mesmo visual, e somem quando o campo é corrigido
    CAMPOS.forEach((nome) => {
        const div = document.getElementById('erro_' + nome);
        const texto = div ? div.textContent.trim() : '';
        if (!campo(nome) || !texto) return;
        tocados.add(nome);
        servidor.add(nome);
        exibir(nome, texto);
    });
    atualizarEnvio();
    // sem os balões de validação nativa por cima dos nossos; sem JS a validação nativa continua valendo
    form.noValidate = true;

    // ---- Confirmação ao sair para importar lista com alterações não salvas (req. 8.5) ----

    function valorOriginal(el) {
        if (el.tagName === 'SELECT') {
            const marcada = Array.from(el.options).find((o) => o.defaultSelected);
            return marcada ? marcada.value : (el.options[0] ? el.options[0].value : '');
        }
        return el.defaultValue;
    }

    function alterado() {
        return Array.from(form.elements).some((el) => {
            if (!el.name || ['hidden', 'submit', 'button'].includes(el.type)) return false;
            return el.value !== valorOriginal(el);
        });
    }

    document.querySelectorAll('#telegram-project [data-confirma-saida]').forEach((link) => {
        link.addEventListener('click', (evento) => {
            if (alterado() && !window.confirm(MSG.sairSemSalvar)) evento.preventDefault();
        });
    });
})();
