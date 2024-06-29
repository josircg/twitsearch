from crispy_forms.layout import Fieldset, Row, Field


class AdminFieldset(Fieldset):
    """Layout baseado no form do admin <fieldset class='module aligned></fieldset>. """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.css_class = 'module aligned'


class AdminSubmitRow(Row):
    """Layout baseado no form do admin <div class='submit-row></div>. """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.css_class = 'submit-row'


class AdminField(Field):
    """Layout baseado no form do admin <div class='fieldBox></div>. """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrapper_class = 'fieldBox ' + kwargs.get('wrapper_class', '')
