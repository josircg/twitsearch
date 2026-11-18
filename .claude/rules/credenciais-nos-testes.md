---
paths:
  - "**/tests.py"
  - "**/tests/**/*.py"
  - "**/test_*.py"
---

# Credenciais nos testes

Nunca escreva senha, token, chave de API ou chave de hash como literal nos testes, nem valores "falsos" como `'x'`, `'segredo-123'` ou `'chave-de-teste'`. O GitGuardian acusa esses valores no repositório.

- Importe os valores de `twitsearch/test_credentials.py`:
  ```python
  from twitsearch.test_credentials import SENHA_USUARIO, CHAVE_HASH

  User.objects.create_user('ana', password=SENHA_USUARIO)

  @override_settings(PROJETO_HASH_KEY=CHAVE_HASH)
  ```
- `twitsearch/test_credentials.py` não é versionado (`.gitignore`). O modelo versionado é `doc/test_credentials.py`. Em um clone novo, crie a cópia com `cp doc/test_credentials.py twitsearch/test_credentials.py` antes de rodar os testes.
- Precisa de uma credencial nova? Adicione a constante **nos dois arquivos**, sempre gerada com `secrets` (`token_urlsafe`/`token_hex`), nunca como texto fixo.
- Os testes não podem depender do valor em si: use a constante tanto para criar quanto para conferir (login, hash esperado etc.).
- Strings vazias (`PROJETO_HASH_KEY=''`), usadas para testar a ausência de configuração, podem continuar literais.
