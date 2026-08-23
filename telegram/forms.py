from django import forms

from .models import Lista, Categoria
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, HTML, Div
from core.crispy_admin_layout import AdminFieldset, AdminSubmitRow, AdminField


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
