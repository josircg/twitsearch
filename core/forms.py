from django import forms
from django.conf import settings
from django.core.validators import EMPTY_VALUES
from django.db import models
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.template.defaultfilters import capfirst
from django.urls import reverse

from core.models import Termo, Projeto
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, HTML, Div

from core.opensearch import connect_opensearch, create_if_not_exists_index
from .crispy_admin_layout import AdminFieldset, AdminSubmitRow, AdminField
import re


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
class ProjetoAdminForm(forms.ModelForm):
    
    
    def clean_prefix(self):
        value = self.cleaned_data.get('prefix', '')
        # Remove espaços em branco
        value = value.replace(' ', '')
        # Permitir apenas lowercase, alfanuméricos e '-'
        value = re.sub(r'[^a-z0-9\-]', '', value.lower())
       
        if value and value[0].isdigit():
            raise forms.ValidationError("O prefixo não pode começar com número.")
        return value
    
    def save(self, commit=True):
        result = super().save(commit)
        
        if settings.OPENSEARCH_SERVERS and result.prefix:
            index_name_catalog = "catalogo-vtrack"
            client = connect_opensearch('minerva-teste')
            if client and index_name_catalog:
                create_if_not_exists_index(client, index_name_catalog)
            
            index_name = result.prefix.lower().replace('*', '')
            client.index(
                index=index_name_catalog,
                id=index_name,
                body={
                    "index_name": index_name,
                    "descricao": result.nome
                })
       
        return result
    class Meta:
        model = Projeto
        fields = '__all__'