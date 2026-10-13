# Backlog mínimo — anonimizador-pdf

Fonte: [Escopo do MVP](escopo-mvp.md). IDs `RF-xx.n` referenciam requisitos funcionais do escopo; IDs `RT-xx` identificam requisitos técnicos e operacionalizam os requisitos não funcionais. Cada checkbox corresponde a um critério de aceite independente.

CLI, SQLite restrito a metadados e publicação são complementos definidos para as releases. Não incluem histórico de conteúdo, reversão ou exposição pública da API. Todos os testes usam dados sintéticos ou autorizados; testes de integração remota usam mocks.

## Release 1 — Core

- [ ] **RF-01.1 — Entrada válida:** teste de integração aceita um PDF sintético com camada de texto e conclui seu processamento.
- [ ] **RF-01.2 — Rejeição de entrada:** teste parametrizado rejeita arquivo não PDF, PDF corrompido, PDF protegido sem leitura e PDF sem texto extraível com erro explícito, sem resposta de sucesso.
- [ ] **RF-01.3 — PDF misto:** teste com página textual e página somente de imagem processa apenas o texto extraível, sem chamar OCR; a documentação informa essa limitação sem prometer cobertura das imagens.
- [ ] **RF-02.1 — Extração:** teste com PDF de duas páginas compara o Markdown com uma saída esperada, verificando sequência das páginas e separação dos parágrafos identificáveis.
- [ ] **RF-03.1 — Regex:** teste parametrizado verifica categoria e posições exatas das ocorrências de CPF, CNPJ, e-mail, telefone e CEP nas apresentações usuais documentadas, com e sem formatação quando aplicável.
- [ ] **RF-05.1 — Presidio local:** teste de integração com Presidio e `pt_core_news_lg` previamente instalados detecta nome e endereço em fixture controlada, com categoria e posições esperadas, sem acesso à rede.
- [ ] **RF-06.1 — Marcadores:** teste parametrizado verifica os formatos `[PESSOA_1]`, `[CPF_1]`, `[CNPJ_1]`, `[EMAIL_1]`, `[TELEFONE_1]`, `[CEP_1]` e `[ENDERECO_1]` e a ausência dos valores detectados na saída.
- [ ] **RF-06.2 — Consistência:** teste com entidades repetidas em páginas diferentes verifica o mesmo marcador para a mesma entidade e categoria, marcadores distintos para entidades diferentes e numeração independente por categoria.
- [ ] **RF-06.3 — Sobreposição:** teste com detecções sobrepostas compara a saída com o resultado esperado da regra de precedência documentada, sem substituição duplicada ou fragmentos da entidade selecionada.
- [ ] **RF-08.1 — API:** teste de integração verifica que o endpoint de processamento recebe um único PDF e devolve corpo Markdown com `Content-Type: text/markdown`, sem PDF original ou mapa de correspondências.
- [ ] **RF-08.2 — CLI:** teste de subprocesso fornece um PDF à CLI e verifica Markdown na saída padrão e código de saída zero.
- [ ] **RF-08.3 — Falhas:** testes da API e da CLI provocam falhas de validação, extração e detecção e verificam erros distinguíveis, resposta HTTP não exitosa ou código de saída não zero, sem conteúdo pessoal ou credenciais nas mensagens.
- [ ] **RF-08.4 — Health:** teste de `GET /health` verifica status HTTP 200 e corpo `{"status": "ok"}`, sem invocar o processamento de documentos.
- [ ] **RT-01 — Isolamento:** teste com dois documentos processados concorrentemente verifica que entidades e contadores não são compartilhados entre requisições.
- [ ] **RT-02 — Limites:** testes parametrizados verificam aceitação nos limites documentados de tamanho e páginas, rejeição acima deles e erro explícito ao exceder o tempo de processamento, sem truncamento silencioso.
- [ ] **RT-03 — Limpeza:** testes de sucesso e falha verificam remoção de arquivos temporários e ausência de persistência de PDF, texto extraído ou correspondências.

## Release 2 — Qualidade

- [ ] **RT-04 — Contratos Pydantic:** testes dos modelos validam entidades com categoria suportada e intervalo válido no texto e rejeitam categorias desconhecidas, intervalos inválidos e configurações inválidas.
- [ ] **RT-05 — Contrato comum:** testes verificam que regex e Presidio retornam entidades compatíveis com o mesmo contrato Pydantic, incluindo categoria e posições no texto.
- [ ] **RT-06 — Logs:** testes capturam logs de sucesso, erro e exceção e verificam ausência de valores pessoais sintéticos, texto do documento, credenciais e correspondências de pseudônimos.
- [ ] **RT-07 — SQLite restrito:** teste consulta esquema e registros de uma base temporária e verifica somente campos permitidos de metadados operacionais documentados, sem conteúdo, entidades, correspondências, nomes de arquivos ou credenciais.
- [ ] **RT-08 — Métricas:** teste com corpus sintético anotado verifica precisão e recall por categoria para as sete categorias, segundo a regra de correspondência documentada; um caso com TP=2, FP=1 e FN=1 deve retornar precisão e recall iguais a `2/3`, dentro da tolerância numérica do teste.
- [ ] **RT-09 — Casos sem ocorrências:** testes verificam o tratamento documentado de denominadores zero nas métricas, distinguindo resultado indefinido de zero e sem produzir avaliação enganosa.
- [ ] **RT-10 — Regressão:** a suíte pytest executada em Python 3.11 cobre os critérios das releases 1 e 2 e termina sem falhas, sem chamadas a serviços públicos ou uso de documentos sensíveis.

## Release 3 — Entrega final

- [ ] **RF-04.1 — LLM configurável:** teste com transporte HTTP simulado verifica uso do endpoint, modelo e credencial configurados na API compatível com OpenAI, sem alteração de código.
- [ ] **RF-04.2 — Entidades válidas:** teste com resposta simulada de nomes e endereços verifica validação pelo contrato comum e correspondência das posições e valores com o texto original antes da substituição.
- [ ] **RF-04.3 — Resposta inválida:** teste parametrizado com resposta malformada, categoria inválida, entidade inexistente ou posições incompatíveis verifica rejeição da resposta e acionamento do fallback, sem alterações arbitrárias.
- [ ] **RF-04.4 — Documento como dado:** teste com instruções maliciosas no texto verifica que endpoint, credencial, modo de privacidade e fluxo configurados permanecem inalterados.
- [ ] **RF-05.2 — Fallback:** teste parametrizado com LLM ausente, timeout, erro de conexão e erro HTTP verifica acionamento do Presidio local e produção de Markdown pelo fluxo de fallback.
- [ ] **RF-05.3 — Fallback indisponível:** teste com falha da LLM e do Presidio verifica erro explícito, sem entrega de Markdown parcial como sucesso.
- [ ] **RF-07.1 — Padrão local:** teste com `PRIVACY_MODE` ausente verifica modo local e zero chamadas remotas durante o processamento.
- [ ] **RF-07.2 — Bloqueio remoto:** teste parametrizado com modo local e endpoint remoto, inclusive com credencial configurada, verifica bloqueio antes de qualquer envio de documento, entidade ou dado derivado.
- [ ] **RF-07.3 — Redirecionamento:** teste com endpoint local que responde com redirecionamento para endpoint remoto verifica que o destino remoto não recebe chamadas nem conteúdo.
- [ ] **RF-07.4 — LLM local:** teste com servidor OpenAI-compatible local e tráfego externo bloqueado verifica detecção e pseudonimização sem comunicação remota.
- [ ] **RF-07.5 — Autorização explícita:** testes verificam que somente um modo remoto válido e explicitamente configurado permite a chamada remota simulada e que um valor desconhecido produz erro antes do envio.
- [ ] **RT-11 — Minimização remota:** teste inspeciona a requisição simulada e verifica envio apenas do trecho necessário e das instruções de detecção, sem PDF binário, metadados de arquivo ou mapa de pseudônimos.
- [ ] **RT-12 — Contexto e timeout:** testes com limite de contexto reduzido e resposta atrasada verificam divisão sem perda de texto, consistência dos marcadores entre trechos e timeout seguido de fallback local.
- [ ] **RT-13 — Logs da LLM:** testes capturam logs de respostas e falhas simuladas da LLM e verificam ausência de prompts com dados pessoais, respostas integrais e credenciais.
- [ ] **RT-14 — Regressão final:** a suíte completa executa em Python 3.11 sem falhas, utilizando mocks para serviços remotos e cobrindo detecção, fallback e política de privacidade.
- [ ] **RT-15 — Publicação:** teste de instalação do artefato versionado em ambiente limpo Python 3.11 executa `GET /health` e o fluxo CLI com PDF sintético, seguindo as instruções publicadas de configuração local e instalação do modelo, sem segredos ou documentos reais no artefato.
