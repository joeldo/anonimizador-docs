# Escopo do MVP — anonimizador-pdf

## 1. Objetivo

Disponibilizar uma API para pseudonimizar documentos de uso geral, recebendo exclusivamente PDFs com camada de texto e devolvendo exclusivamente Markdown. Os dados pessoais detectados devem ser substituídos por marcadores consistentes, como `[PESSOA_1]`, `[CPF_1]` e `[ENDERECO_1]`.

O processamento deve ser local por padrão. O uso de uma LLM remota exige configuração explícita que permita o envio de conteúdo a um serviço externo.

Neste documento, “anonimizador” é o nome do produto. A técnica empregada é pseudonimização; o MVP não garante anonimização irreversível, ausência de dados residuais ou impossibilidade de reidentificação.

## 2. Entradas, saídas e arquitetura

- **Entrada:** um PDF por requisição, com texto extraível.
- **Saída de sucesso:** conteúdo Markdown com os dados detectados substituídos por pseudônimos.
- **Categorias cobertas:** nomes de pessoas, CPF, CNPJ, e-mail, telefone, CEP e endereço.
- **Detecção determinística:** regex para CPF, CNPJ, e-mail, telefone e CEP.
- **Detecção contextual:** LLM configurável para nomes e endereços, acessada por API compatível com OpenAI.
- **Fallback local:** Microsoft Presidio com spaCy e o modelo `pt_core_news_lg`, sem dependência de endpoint remoto durante o processamento.
- **Camadas:** `api/`, `services/`, `repositories/`, `models/` e `detectors/`.

## 3. Requisitos funcionais

### RF-01 — Receber e validar o documento

A API deve aceitar somente PDF com camada de texto. Arquivos de outros formatos, PDFs inválidos, protegidos sem possibilidade de leitura ou sem texto extraível devem ser rejeitados com erro explícito.

Páginas ou regiões contendo apenas imagens não serão interpretadas. Um PDF misto pode ter seu texto extraível processado, mas a resposta não deve ser apresentada como cobertura dos dados existentes em imagens.

### RF-02 — Extrair texto e gerar Markdown

O sistema deve extrair o texto das páginas em sequência e gerar uma representação textual em Markdown, preservando parágrafos e separações quando identificáveis.

A saída não precisa reproduzir fielmente o layout, as tabelas, as colunas, as fontes ou outros elementos visuais do PDF.

### RF-03 — Detectar identificadores por regex

O sistema deve detectar CPF, CNPJ, e-mail, telefone e CEP por regex, contemplando apresentações brasileiras usuais com e sem formatação quando aplicável.

A detecção por padrão não constitui consulta cadastral nem comprovação da existência ou titularidade do identificador.

### RF-04 — Detectar nomes e endereços com LLM

O sistema deve permitir configurar uma LLM local ou pública por API compatível com OpenAI, incluindo endpoint, modelo e credencial quando exigida.

A LLM deve identificar nomes de pessoas e endereços no texto fornecido. Suas respostas devem ser validadas contra o texto original antes da substituição; entidades inexistentes ou respostas malformadas não devem gerar alterações arbitrárias.

O conteúdo do documento deve ser tratado como dado, não como instrução capaz de alterar a configuração, a política de privacidade ou o fluxo de processamento.

### RF-05 — Utilizar fallback local

Quando a LLM não estiver configurada, estiver indisponível, falhar ou retornar uma resposta inválida, o sistema deve utilizar Microsoft Presidio com spaCy `pt_core_news_lg` para detectar nomes e endereços.

O fallback deve executar localmente e respeitar o mesmo contrato de entidades utilizado pela LLM. A indisponibilidade do fallback, quando necessário, deve produzir erro explícito, sem entregar como sucesso um resultado com etapas obrigatórias omitidas.

### RF-06 — Aplicar pseudônimos consistentes

Cada entidade detectada deve receber um marcador correspondente à sua categoria:

| Categoria | Exemplo |
|---|---|
| Nome de pessoa | `[PESSOA_1]` |
| CPF | `[CPF_1]` |
| CNPJ | `[CNPJ_1]` |
| E-mail | `[EMAIL_1]` |
| Telefone | `[TELEFONE_1]` |
| CEP | `[CEP_1]` |
| Endereço | `[ENDERECO_1]` |

As ocorrências reconhecidas como a mesma entidade e categoria devem receber o mesmo marcador dentro do documento. Entidades diferentes devem receber marcadores distintos, com numeração independente por categoria.

A consistência deve abranger todas as páginas e trechos processados na mesma requisição. Não há obrigação de manter os mesmos pseudônimos entre documentos ou requisições.

Detecções sobrepostas devem ser resolvidas de modo determinístico, sem duplicar substituições, corromper o texto ou deixar fragmentos de uma entidade detectada por aplicação parcial.

### RF-07 — Respeitar o modo de privacidade

`PRIVACY_MODE=local` deve ser o valor padrão, inclusive quando a variável estiver ausente.

Nesse modo, nenhum conteúdo do documento, entidade extraída ou dado derivado deve ser enviado a endpoints remotos. Somente detectores locais e uma LLM efetivamente local podem ser utilizados.

A existência de credencial ou endpoint remoto configurado não autoriza seu uso no modo local. Configurações incompatíveis devem ser bloqueadas antes de qualquer envio; redirecionamentos não podem contornar essa restrição.

O uso de LLM pública deve exigir a ativação explícita de um modo que permita processamento remoto. Valores de configuração inválidos devem causar erro, sem habilitar envio remoto implicitamente.

### RF-08 — Devolver o resultado e informar falhas

O resultado de sucesso deve conter apenas Markdown, sem o PDF original, mapa de correspondências ou recurso de recuperação dos dados substituídos.

Erros de validação, extração e detecção devem ser distinguíveis por mensagens técnicas que não exponham o conteúdo do documento ou credenciais.

O endpoint `GET /health` deve permanecer disponível para verificação básica da API, sem receber ou processar documentos.

## 4. Requisitos não funcionais

### RNF-01 — Privacidade por padrão

A política de processamento local deve ser aplicada antes das chamadas aos detectores. No modo local, o fluxo deve funcionar sem envio de dados do documento a serviços externos, com dependências e modelos previamente instalados.

Quando o processamento remoto for autorizado, deve ser enviado somente o conteúdo necessário à detecção. Essa autorização não elimina os riscos de retenção e tratamento pelo provedor externo.

### RNF-02 — Minimização e retenção

PDFs, texto extraído, entidades e correspondências de pseudônimos não devem ser persistidos por padrão. Arquivos temporários eventualmente necessários devem ser removidos ao término do processamento, inclusive em caso de erro.

Logs não devem registrar conteúdo de documentos, valores pessoais detectados, respostas integrais da LLM ou segredos.

### RNF-03 — Qualidade e limitações de detecção

A qualidade deve ser avaliada separadamente por categoria, utilizando documentos sintéticos ou autorizados e métricas de precisão e revocação.

Não é prometida detecção completa de todos os dados pessoais. Erros de extração, ambiguidade textual e limitações dos modelos podem produzir falsos positivos e falsos negativos. A saída deve ser revisada antes de divulgação quando houver exigência de alta garantia.

### RNF-04 — Confiabilidade e isolamento

Cada requisição deve manter estado e numeração de pseudônimos isolados. Dados e correspondências de um documento não podem contaminar o processamento de outro.

Falhas dos componentes obrigatórios não devem ser ocultadas por respostas aparentando sucesso.

### RNF-05 — Limites operacionais

O processamento deve possuir limites explícitos para tamanho do arquivo, quantidade de páginas e tempo de execução. Chamadas à LLM devem ter timeout e respeitar a capacidade de contexto do modelo.

Se houver divisão em trechos, a consistência dos pseudônimos deve ser preservada no documento inteiro. Conteúdo não pode ser truncado silenciosamente. Os valores dos limites serão definidos e documentados durante a implementação.

### RNF-06 — Configuração e manutenção

O projeto deve utilizar Python 3.11, FastAPI, código tipado e separação das responsabilidades entre as camadas previstas.

Modo de privacidade, endpoint, modelo e credenciais devem ser configuráveis sem alteração do código. Segredos não devem ser incluídos no repositório; exemplos de configuração não devem conter valores secretos.

### RNF-07 — Testabilidade

Devem existir testes para validação de entrada, categorias detectadas, consistência dos pseudônimos, resolução de sobreposições, fallback e bloqueio de endpoints remotos no modo local.

Os testes automatizados não devem depender de documentos reais sensíveis nem de chamadas a serviços públicos. Integrações remotas devem ser simuladas.

## 5. Fora de escopo

- **OCR:** reconhecimento de texto em PDFs digitalizados, imagens ou regiões sem camada de texto.
- **DOCX:** leitura ou processamento de documentos Word.
- **Saída em PDF:** geração de PDF anonimizado, edição visual ou aplicação de tarjas.
- **Interface web:** telas de upload, revisão, configuração ou acompanhamento.
- **Autenticação:** login, gestão de usuários, autorização e controle de acesso.
- **Reversão da anonimização:** exportação de correspondências, recuperação de valores originais ou endpoint de desanonimização.
- Entrada ou saída em formatos adicionais ao PDF de texto e Markdown.
- Reprodução fiel do layout e dos elementos gráficos do documento.
- Detecção de categorias além de nomes de pessoas, CPF, CNPJ, e-mail, telefone, CEP e endereços.
- Resolução de identidade entre documentos ou reconhecimento garantido de apelidos e variantes de um mesmo nome.
- Consulta a bases cadastrais externas ou validação da titularidade dos identificadores.
- Histórico persistente de documentos, armazenamento de originais e processamento em lote.
- Treinamento ou ajuste fino de modelos.
- Garantia de anonimização irreversível, certificação de conformidade legal ou substituição de revisão humana.

A ausência de autenticação limita o MVP a ambientes controlados; sua exposição pública não faz parte deste escopo.
