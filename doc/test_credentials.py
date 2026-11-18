# Modelo das credenciais usadas só nos testes automatizados.
#
# Copie este arquivo para twitsearch/test_credentials.py (não versionado, ver .gitignore):
#     cp doc/test_credentials.py twitsearch/test_credentials.py
#
# Os valores são gerados a cada execução, então nenhum segredo fica escrito no repositório
# e o GitGuardian não acusa credenciais nos testes. Se precisar de um valor fixo localmente,
# troque-o só na sua cópia em twitsearch/, nunca aqui.
import secrets

SENHA_USUARIO = secrets.token_urlsafe(16)            # senha de usuários criados nos testes
CHAVE_HASH = secrets.token_hex(16)                   # PROJETO_HASH_KEY nos testes
CHAVE_HASH_ALTERNATIVA = secrets.token_hex(16)       # uma segunda chave, para comparar hashes
TOKEN_GIT = secrets.token_urlsafe(20)                # git_token enviado em formulários de teste
