from django import forms
from django.conf import settings
from django.core.validators import EMPTY_VALUES
from django.db import models
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.template.defaultfilters import capfirst
from django.urls import reverse

from core.models import Termo
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, HTML, Div
from .crispy_admin_layout import AdminFieldset, AdminSubmitRow, AdminField


class ImportForm(forms.Form):
    termo = forms.ModelChoiceField(queryset=Termo.objects.filter(status='A'))
    arquivo = forms.FileField(label='Arquivo:', widget=forms.ClearableFileInput(attrs={'accept': '.xlsx, .txt'}))

    def __init__(self, *args, **kwargs):
        has_hash = kwargs.pop('has_hash', False)

        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        post_buttons = (
                Div(Submit('submit', 'Importar'), css_class="col"),
            )

        self.helper.layout = Layout(
            AdminFieldset(
                '',
                Row(AdminField('termo')),
                Row(AdminField('arquivo')),
            ),
            AdminSubmitRow(*post_buttons)
        )
    '''
    def clean_arquivo_csv(self):
        if self.cleaned_data['arquivo']:
            arquivo = self.files['arquivo']
            # abre o arquivo e verifica se está delimitado com , e com os atributos mínimos necessários
            return
    '''
