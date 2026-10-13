# anonimizador-pdf

API FastAPI e CLI para converter **PDFs com camada de texto em Markdown
pseudonimizado**, com processamento local por padrão. Desenvolvido e testado
em Python 3.11.

Substitui os dados detectados por `[PESSOA_1]`, `[CPF_1]`, `[CNPJ_1]`,
`[EMAIL_1]`, `[TELEFONE_1]`, `[CEP_1]` e `[ENDERECO_1]`. Os marcadores são
consistentes dentro de cada documento, não entre documentos.

**Pseudonimização não é garantia de anonimização irreversível.** Podem restar
dados pessoais ou informações que permitam reidentificação. Revise a saída
antes de divulgá-la.

## Como a IA Acelerou Este Projeto

O projeto foi desenvolvido com apoio de IA generativa usando GitHub Copilot no
Visual Studio Code e o modelo GPT 6.1 Sol. As ferramentas aceleraram a criação
incremental da estrutura do projeto, dos contratos Pydantic, dos detectores, da
API FastAPI, da CLI, dos testes automatizados e da documentação técnica.

A IA também auxiliou na organização do backlog por releases, na elaboração do
diagrama de componentes, na geração do corpus sintético e na proposta de casos
de teste para erros, fallback, privacidade e isolamento de dependências.
Isso reduziu o tempo de implementação e permitiu concentrar mais esforço na
validação de requisitos e riscos do domínio.

As sugestões não foram aceitas automaticamente. Cada mudança relevante passou
por revisão humana, testes e validação de comportamento. Em especial, foram
verificados os dados persistidos no SQLite, o bloqueio de vazamento de texto e
credenciais em logs, a política de chamadas remotas, a qualidade das métricas
e os resultados do fallback. A IA acelera a produção de artefatos, mas a
responsabilidade por revisar, testar e decidir permanece humana.

## Como funciona

1. `PdfExtractor` extrai texto com pdfplumber, mantendo a sequência das páginas
   e separações de parágrafos quando identificáveis.
2. `RegexDetector` detecta identificadores; CPF e CNPJ numéricos precisam ter
   ambos os dígitos verificadores válidos.
3. `FallbackDetector` tenta a LLM configurada para nomes e endereços; quando
   necessário, usa Microsoft Presidio + spaCy `pt_core_news_lg` localmente.
4. `PseudonymReplacer` une as entidades, prioriza a mais longa em sobreposições
   e substitui deterministicamente. A LLM apenas detecta, nunca reescreve a saída.
5. SQLite registra somente metadados operacionais.

Documentação: [escopo](docs/escopo-mvp.md), [backlog](docs/backlog.md) e
[diagrama Mermaid](docs/arquitetura-componentes.mmd).

## Instalação

Na raiz do repositório, em PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`requirements.txt` fixa o conjunto transitivo testado, inclusive o modelo
`pt_core_news_lg`. Para instalar o pacote local em modo editável, com as mesmas
dependências de desenvolvimento, use
`.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.
Dependências e modelos são baixados na instalação; não há downloads automáticos
durante o processamento. `/health` não carrega detectores nem verifica sua
disponibilidade.

Para usar Ollama, instale-o e prepare o modelo:

```powershell
ollama pull qwen3.5:4b
ollama serve
```

Se o aplicativo Ollama já estiver servindo na porta 11434, não inicie outro
servidor. Disponibilidade, memória e tempo de inferência dependem do equipamento.

## Configuração

O `.env` da raiz é carregado sem sobrescrever variáveis existentes no processo.
Não versione esse arquivo nem credenciais. Reinicie a API após alterar a
configuração: serviço e repositório são mantidos em cache.

| Variável | Padrão / significado |
|---|---|
| `PRIVACY_MODE` | `local`; também aceita `remote_allowed` |
| `RUNS_DB_PATH` | `runs.sqlite`, relativo ao diretório de execução |
| `LLM_BASE_URL` | Ausente; base OpenAI-compatible, normalmente terminada em `/v1` |
| `LLM_MODEL` | Ausente; nome do modelo instalado ou disponível no provedor |
| `LLM_API_KEY` | Ausente; chave Bearer, opcional para Ollama |
| `LLM_TIMEOUT_S` | `30`; segundos por operação HTTP, positivo e finito |

### Ollama local

```dotenv
PRIVACY_MODE=local
RUNS_DB_PATH=runs.sqlite
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3.5:4b
LLM_API_KEY=
LLM_TIMEOUT_S=300
```

Este exemplo usa o modelo e o timeout da avaliação abaixo. O padrão do código
continua sendo 30 segundos. Ajuste conforme a latência local; 300 segundos não
é um limite global de duração do processamento.

Para usar **somente Presidio**, deixe `LLM_BASE_URL` e `LLM_MODEL` vazios.

### API pública compatível com OpenAI

Exemplo ilustrativo; escolha um modelo disponível na sua conta:

```dotenv
PRIVACY_MODE=remote_allowed
RUNS_DB_PATH=runs.sqlite
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=SUBSTITUA_POR_SUA_CHAVE
LLM_TIMEOUT_S=30
```

O cliente acrescenta `/chat/completions` à base e pede JSON com
`response_format={"type":"json_object"}`. O provedor precisa suportar esse
contrato. APIs públicas não foram usadas na avaliação nem nos testes.

## API e CLI

Inicie a API local:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
curl.exe http://127.0.0.1:8000/health
curl.exe -F "file=@tests\fixtures\corpus\contrato.pdf" http://127.0.0.1:8000/anonymize
curl.exe "http://127.0.0.1:8000/runs?limit=50&offset=0"
```

- `GET /health`: `{"status":"ok"}`.
- `POST /anonymize`: exatamente um campo multipart `file`; sucesso HTTP 200
  com corpo somente Markdown e `Content-Type: text/markdown`.
- `GET /runs`: envelope `items`, `total`, `limit`, `offset`; limite padrão 50,
  permitido de 1 a 100; offset de 0 a `2**63 - 1`. Ordem decrescente por
  `created_at`, depois `id`.

CLI, usando o mesmo serviço e configuração:

```powershell
.\.venv\Scripts\python.exe -m api.cli tests\fixtures\corpus\contrato.pdf
```

Markdown vai para stdout e erros para stderr. Códigos de saída: 0 no sucesso,
2 na falha de leitura e 1 na falha de processamento. Salvar stdout em arquivo
é uma decisão do usuário: o Markdown pode conter dados não detectados.

Erros da API seguem `{"code":"...","message":"..."}`, com mensagens fixas
sem conteúdo pessoal: HTTP 422 para entrada inválida; 503 para configuração,
banco ou detector indisponível; 500 para falhas de processamento.
Não há entrega de Markdown parcial como sucesso.

## Privacidade e fallback

Em `local`, a política é verificada **antes do envio**. Permite somente
`localhost`, IPs loopback, IPv4 RFC1918 (`10/8`, `172.16/12`, `192.168/16`)
e IPv6 ULA (`fc00::/7`). Hostnames arbitrários não são resolvidos para
autorizar acesso: use um IP privado literal. Link-local não é permitido.
Uma rede privada precisa ser confiável; o cliente não verifica se o servidor
repassa dados a terceiros.

Credencial configurada não autoriza acesso remoto. `remote_allowed` habilita
explicitamente o envio do **texto extraído original completo**, ainda não
pseudonimizado, e das instruções. Não envia PDF binário, nome de arquivo ou
mapa de pseudônimos. Não há divisão em trechos nesta implementação.
Redirects e proxies de ambiente são desabilitados em ambos os modos.
URLs com credenciais embutidas, query ou fragmento são rejeitadas.

O JSON `{"entidades":[{"tipo":"PESSOA","texto":"..."}]}` é validado por
Pydantic estrito. Só PESSOA e ENDERECO são aceitos; campos extras ou textos
inexistentes invalidam a resposta inteira. Os offsets de todas as ocorrências
exatas são calculados localmente. Uma resposta válida vazia não aciona fallback,
mesmo que o modelo tenha deixado de detectar entidades.

| Motivo registrado | Quando o Presidio é acionado |
|---|---|
| `endpoint_missing` | Endpoint ausente |
| `model_missing` | Modelo ausente |
| `privacy_blocked` | Endpoint proibido no modo local |
| `endpoint_unavailable` | URL inválida, conexão ou resposta HTTP não exitosa |
| `timeout` | Timeout HTTP |
| `invalid_response` | JSON/schema inválido ou entidade incompatível com o texto |

Se o Presidio também falhar, há erro explícito. O fallback não desfaz um envio
já realizado a uma LLM pública.

SQLite guarda apenas `id`, `created_at` UTC, `status`, `duration_ms`,
`error_code`, `detector_used` e `fallback_reason`. Detector e motivo são
enumerados; não armazena PDFs, texto, entidades, nomes de arquivo, credenciais
ou correspondências. Registros anteriores à inclusão do relatório são
preservados com os novos campos em `null`. Não há expiração automática.
A falha de persistência impede retorno de sucesso.

O pipeline não grava originais deliberadamente; o upload é fechado ao final.
Logs são filtrados durante o processamento sensível nos handlers registrados.
Fora dele, registram apenas códigos e metadados operacionais. Essa proteção
não controla logs do Ollama, do provedor, de proxies externos ou de handlers
criados posteriormente, nem threads externas sem propagação do contexto.

### LGPD e LLM pública

Ativar `remote_allowed` é uma escolha técnica, **não uma base legal nem prova
de conformidade com a LGPD**. Antes de enviar documentos, avalie finalidade,
base legal adequada, necessidade/minimização, dados sensíveis, contrato com
o provedor, retenção, uso para treinamento, controles de acesso e eventual
transferência internacional. Consulte a área jurídica/encarregado quando
necessário. Não presuma que todo tratamento exige consentimento ou que
pseudonimizar a saída elimina as obrigações sobre os originais enviados.

## Avaliação e métricas

Medição em 13/10/2026: seis PDFs sintéticos (contrato, ofício, currículo, ata,
nota fiscal simples e e-mail impresso), seed `20261013`, com gabaritos por
ocorrência. Dois CPFs propositalmente inválidos são excluídos dos positivos.
Identificadores com verificadores válidos são gerados, sem consulta cadastral;
podem coincidir acidentalmente com registros existentes.

Acerto exige categoria, texto e intervalo exatos no mesmo documento, após
seleção de sobreposições. Precisão = TP/(TP+FP); recall = TP/(TP+FN).
Denominadores zero resultam em `N/A`. Ambas as avaliações incluem regex.

| Categoria | Presidio TP/FP/FN | Precisão | Recall | LLM local TP/FP/FN | Precisão | Recall |
|---|---|---|---|---|---|---|
| PESSOA | 12/0/0 | 1,0000 | 1,0000 | 12/0/0 | 1,0000 | 1,0000 |
| CPF | 6/0/0 | 1,0000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |
| CNPJ | 6/0/0 | 1,0000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |
| EMAIL | 6/0/0 | 1,0000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |
| TELEFONE | 6/0/0 | 1,0000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |
| CEP | 6/0/0 | 1,0000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |
| ENDERECO | 6/6/0 | 0,5000 | 1,0000 | 6/0/0 | 1,0000 | 1,0000 |

Presidio usou `pt_core_news_lg` 3.8.0. LLM: Ollama com `qwen3.5:4b`,
temperatura 0, timeout HTTP de **300 segundos somente na avaliação**, sem
fallback. A tentativa com 30 segundos falhou por timeout; não gerou métricas
completas. Resultados perfeitos neste corpus pequeno não garantem recall
de nomes ou qualidade em documentos reais.

O comando padrão mede **somente Presidio**, independentemente do `.env`:

```powershell
.\.venv\Scripts\python.exe scripts\avaliar.py
```

Para medir a LLM local sem confundir seus resultados com o fallback, use a
função do mesmo avaliador, com modelo/endpoint locais configurados:

```powershell
@'
from models.settings import get_settings
from detectors.llm_detector import LlmDetector, LlmDetectionError
from models.errors import ApplicationError
from scripts.avaliar import CORPUS, evaluate_corpus

settings = get_settings().model_copy(update={
    "privacy_mode": "local", "llm_timeout_s": 300.0,
})
try:
    report = evaluate_corpus(CORPUS, LlmDetector(settings))
except ApplicationError as error:
    reason = error.reason if isinstance(error, LlmDetectionError) else error.code
    print("Avaliacao nao concluida:", reason)
    raise SystemExit(1)
print("Modelo:", settings.llm_model, "| PDFs:", report.documentos)
for m in report.metricas:
    p = "N/A" if m.precisao is None else f"{m.precisao:.4f}"
    r = "N/A" if m.recall is None else f"{m.recall:.4f}"
    print(m.tipo, "TP/FP/FN:", m.tp, m.fp, m.fn, "Precisao:", p, "Recall:", r)
'@ | .\.venv\Scripts\python.exe -
```

O avaliador não grava no SQLite e não imprime valores pessoais. Para outro
corpus, o comando padrão aceita `--corpus CAMINHO`.

## Limitações e estado da entrega

- Sem OCR: PDFs só de imagem são rejeitados; PDFs mistos cobrem somente o
  texto extraível, não os dados existentes em imagens.
- Layouts complexos, tabelas e múltiplas colunas não são reconstruídos
  fielmente; erros de extração afetam a detecção.
- Nomes raros, abreviados, ambíguos ou dependentes de contexto podem escapar.
  O Presidio analisa por linha; entidades multilinha podem ter cobertura menor.
- JSON válido não comprova completude da detecção. LLMs podem omitir entidades;
  o prompt não é garantia de resistência a todas as instruções maliciosas.
- CPF/CNPJ com verificadores incorretos não são cobertos nessas categorias;
  CNPJ alfanumérico não é suportado. E-mail, CEP e telefone dependem de padrões.
- Sem limites próprios implementados para tamanho/páginas ou duração global,
  nem divisão por janela de contexto. PDFs grandes podem consumir memória,
  demorar ou exceder o contexto do modelo.
- Sem DOCX, saída em PDF, interface de upload/revisão, autenticação, reversão
  ou resolução de identidade entre documentos. Use em ambiente controlado;
  não exponha a API publicamente.
- O backlog ainda contém pendências de limites, verificação de limpeza,
  minimização por trechos, contexto e publicação/instalação do artefato.
  A medição manual local não substitui o teste automatizado RF-07.4.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -m "not presidio" -q
```

A segunda opção dispensa o modelo spaCy. Testes HTTP da LLM usam mocks,
sem Ollama ou API pública. Integrações marcadas `presidio` usam o modelo
real previamente instalado, com rede bloqueada; no Windows a fixture
permite apenas o `socketpair` interno do asyncio.

Última execução: **224 testes aprovados**, com um aviso de depreciação
preexistente Starlette/httpx. Essa suíte não inclui chamadas reais à LLM.

Para regenerar o corpus determinístico:

```powershell
.\.venv\Scripts\python.exe tests\fixtures\gerar_corpus.py
```
