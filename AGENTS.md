# Regras do projeto

- A versão executada neste notebook e o pacote portátil destinado ao notebook corporativo devem permanecer funcionalmente idênticos.
- Depois de validar uma alteração local, copie os mesmos arquivos de aplicação para uma nova versão `dist/expert-code-flow-vX.Y.Z-local-portable`, preserve o runtime portátil e gere um novo ZIP sem sobrescrever versões anteriores.
- Antes da entrega, compare por SHA-256 todos os arquivos de `backend/` e `frontend/` entre a raiz e o pacote, execute os testes locais e informe o hash SHA-256 do ZIP.
- Não publique o pacote no GitHub sem autorização explícita do usuário.
