# MenteX — plataforma de aprendizagem

Projeto web em Flask + SQLite, preparado para GitHub e hospedagem Python (Render, Railway ou servidor próprio).

## O que funciona nesta versão
- Cadastro e login com hash de senha (Werkzeug).
- Banco SQLite com conta, progresso por matéria, XP, moedas, conquistas e configurações.
- Oito matérias e trilha de até 50 níveis por matéria.
- Cinco perguntas por fase, correção e explicação após resposta.
- Professor MenteX em modo local; pode conectar à API da OpenAI usando variável de ambiente.
- Configurações de música ambiente procedural, volume, efeitos, animações e salvamento por conta.
- Layout responsivo para computador e celular.

## Executar no Windows
1. Instale Python 3.11 ou 3.12.
2. Extraia o ZIP.
3. Dê dois cliques em `INICIAR_MENTEX.bat`.
4. Na primeira execução, o instalador cria `.venv` e instala as dependências.
5. Abra `http://127.0.0.1:5000`.

Também pode executar manualmente:
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

## Publicar
Envie os arquivos deste projeto para um repositório GitHub. Para colocar o app no ar, use um host que execute Python/Flask (por exemplo Render). GitHub Pages hospeda sites estáticos e **não executa Flask nem SQLite**.

Configuração típica no Render:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment: `SECRET_KEY` (obrigatório em produção)
- Opcional: `OPENAI_API_KEY` e `OPENAI_MODEL`

O disco SQLite local pode ser temporário em alguns planos de hospedagem. Para produção com vários usuários, configure PostgreSQL e armazenamento persistente.

## Limitações importantes
- Sem `OPENAI_API_KEY`, o Professor usa respostas locais de demonstração, não IA generativa.
- O banco SQLite é adequado para testar e uso pequeno em uma única instância. Para comunidade, ranking global, pedidos de amizade entre dispositivos e alta disponibilidade, é necessário PostgreSQL hospedado e endpoints próprios.
- Login Google/OAuth, pagamentos, assinaturas, mensagens privadas e compras reais não estão ativados. Não colete senha Google nem dados de cartão.
- Música e efeitos são sintetizados pelo navegador (Web Audio), sem arquivos de áudio externos. O navegador exige uma interação do usuário para iniciar o áudio.
- As questões locais são um conjunto inicial de prática; não representam ainda 2.000 questões revisadas por especialistas.

## Segurança
Defina `SECRET_KEY` forte no ambiente de produção, use HTTPS, mantenha dependências atualizadas, configure backup e prefira PostgreSQL para produção. Nunca publique chaves de API no GitHub.
