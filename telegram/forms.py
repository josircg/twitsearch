from django import forms
from django.db.models import Q

from .models import Lista, Categoria
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, HTML, Div
from core.crispy_admin_layout import AdminFieldset, AdminSubmitRow, AdminField


CONECTIVOS = ('AND', 'OR')


class TelegramProjectForm(forms.Form):
    nome = forms.CharField(label='Nome do Projeto', max_length=40)
    objetivo = forms.CharField(label='Descrição Breve da Pesquisa', widget=forms.Textarea(attrs={'rows': 3}))
    lista = forms.ModelChoiceField(label='Lista de canais', queryset=Lista.objects.none(), empty_label='Selecione...')
    # <input type="date"> envia e espera o formato ISO, independente do locale
    dt_inicio = forms.DateField(label='Data Inicial da Coleta', input_formats=['%Y-%m-%d'],
                                widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    dt_final = forms.DateField(label='Data Final da Coleta', input_formats=['%Y-%m-%d'],
                               widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    termos = forms.CharField(
        label='Termos de busca',
        widget=forms.Textarea(attrs={'rows': 5}),
        help_text='Um termo por linha. Use os conectivos AND e OR em maiúsculas. '
                  'Exemplos: ecologia OR ecológico, ecologia AND ecológico.')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lista'].queryset = Lista.objects.filter(
            Q(publica=True) | Q(dono=user)).order_by('nome')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field, forms.ModelChoiceField) else 'form-control'

    def clean_termos(self):
        termos = [linha.strip() for linha in self.cleaned_data['termos'].splitlines() if linha.strip()]
        if not termos:
            raise forms.ValidationError('Informe ao menos um termo de busca.')
        for termo in termos:
            if len(termo) > 2000:
                raise forms.ValidationError(f'Termo muito longo (máximo 2000 caracteres): {termo[:30]}...')
            tokens = termo.split()
            if tokens[0] in CONECTIVOS or tokens[-1] in CONECTIVOS or any(
                    a in CONECTIVOS and b in CONECTIVOS for a, b in zip(tokens, tokens[1:])):
                raise forms.ValidationError(f'Uso inválido de AND/OR no termo: {termo}')
        return termos

    def clean(self):
        cleaned = super().clean()
        inicio, final = cleaned.get('dt_inicio'), cleaned.get('dt_final')
        if inicio and final and final < inicio:
            self.add_error('dt_final', 'A data final não pode ser anterior à data inicial.')
        return cleaned


class ImportListaForm(forms.Form):
    nome = forms.CharField(label='Nome da lista', max_length=100)
    publica = forms.TypedChoiceField(
        label='Visibilidade', coerce=lambda valor: valor == 'True', initial='False',
        choices=(('False', 'Privada (somente eu posso usar)'), ('True', 'Pública (qualquer usuário pode usar)')),
        widget=forms.RadioSelect)
    arquivo = forms.FileField(
        label='Arquivo (CSV ou Excel)',
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,.xlsx'}),
        help_text='O arquivo deve conter apenas uma coluna, com a URL (https://t.me/canal) '
                  'ou o identificador (@canal) de cada canal.')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for nome, field in self.fields.items():
            field.widget.attrs['class'] = 'form-check-input' if nome == 'publica' else 'form-control'

    def clean_nome(self):
        nome = self.cleaned_data['nome'].strip()
        if Lista.objects.filter(dono=self.user, nome__iexact=nome).exists():
            raise forms.ValidationError('Você já possui uma lista com este nome.')
        return nome

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        if not arquivo.name.lower().endswith(('.csv', '.xlsx')):
            raise forms.ValidationError('Envie um arquivo .csv ou .xlsx.')
        return arquivo


class ImportForm(forms.Form):
    lista = forms.ModelChoiceField(queryset=Lista.objects.all())
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), required=False)
    arquivo = forms.FileField(label='Arquivo:', widget=forms.ClearableFileInput(attrs={'accept': '.xlsx, .csv'}))

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        post_buttons = (
                Div(Submit('submit', 'Importar'), css_class="col"),
            )

        self.helper.layout = Layout(
            AdminFieldset(
                '',
                Row(AdminField('lista')),
                Row(AdminField('arquivo')),
            ),
            AdminSubmitRow(*post_buttons)
        )
