# Pagamento — Decisões Arquiteturais

Documento de decisões arquiteturais e funcionais do módulo de pagamento do backend **Croma Drip**.

**Status do módulo:** 🚧 em implementação — bloco Checkout.

---

## Visão geral

O backend **não processa pagamento diretamente**.

O Mercado Pago (MP) é responsável pelas operações sensíveis de pagamento, incluindo captura, antifraude, 3DS e processamento do PIX/cartão conforme o produto utilizado.

O backend da Croma é responsável por:

1. Criar cobranças/pagamentos no Mercado Pago.
2. Associar a cobrança ao pedido interno.
3. Receber e validar webhooks assinados pelo Mercado Pago.
4. Persistir eventos externos para auditoria e idempotência.
5. Atualizar o estado financeiro do pedido.
6. Expor o estado do pedido para o frontend e administração.
7. Permitir reconciliação manual com o Mercado Pago.
8. Nunca armazenar dados sensíveis de cartão.
9. Nunca executar estorno automático no MVP.

**Princípio norteador:**

> Segurança e consistência financeira > velocidade de implementação.

---

# PAYMENT-01 — Escopo do MVP

## Dentro do MVP

* PIX via API de Payments do Mercado Pago.
* QR Code PIX renderizado no frontend da Croma.
* Cartão via **Checkout Pro**.
* Redirecionamento do cliente para o ambiente do Mercado Pago no pagamento com cartão.
* Webhook público do Mercado Pago.
* Validação de assinatura HMAC do webhook.
* Persistência de eventos recebidos.
* Processamento idempotente de webhooks.
* Reconciliação manual por administrador.
* Máquina de estados para `orders.status`.
* Controle separado de `orders.payment_status`.
* CPF/CNPJ obrigatório para novos cadastros.
* Snapshot do endereço no momento da criação do pedido.
* Parcelamento:

  * até 4x para pedidos abaixo de R$ 600;
  * até 5x para pedidos a partir de R$ 600;
  * sem juros para o cliente conforme regra comercial definida pela Croma.

## Fora do MVP

* NF-e / emissão fiscal.
* Refund automático via API do Mercado Pago.
* Job automático de reconciliação.
* Fila assíncrona para pagamentos.
* Cartão via Checkout Transparente.
* PIX via Checkout Pro.
* Parcelamento com juros.
* Assinaturas/recorrência.
* Rate limiting específico do módulo de pagamento.
* Sistema próprio de antifraude.
* Armazenamento de dados de cartão.

---

# PAYMENT-02 — PIX

## Estratégia

O PIX será implementado utilizando a API de Payments do Mercado Pago.

O QR Code será disponibilizado diretamente na experiência da Croma.

O backend nunca recebe dados bancários do cliente além dos dados necessários ao Mercado Pago para identificar o pagador.

## Fluxo

```text
Cliente
   │
   │ POST /orders/{order_id}/pay/pix
   │ Idempotency-Key: UUID
   ▼
PaymentRoute
   │
   ▼
PaymentService
   │
   ├── valida usuário
   ├── valida pedido
   ├── valida status
   ├── valida CPF/CNPJ
   ├── verifica cobrança existente
   │
   ▼
MPClient
   │
   │ POST /v1/payments
   │ X-Idempotency-Key: UUID
   ▼
Mercado Pago
   │
   │ payment.id
   │ qr_code
   │ qr_code_base64
   │ ticket_url
   ▼
PaymentService
   │
   ├── persiste referência externa
   └── retorna resposta
   ▼
Frontend Croma
   │
   └── renderiza QR Code
          │
          ▼
      Cliente paga
          │
          ▼
Mercado Pago
          │
          │ POST /webhooks/mercadopago
          ▼
WebhookRoute
          │
          ▼
PaymentService
          │
          ├── valida assinatura
          ├── persiste evento
          ├── consulta pagamento no MP
          └── atualiza pedido
```

## Dados enviados ao Mercado Pago

O pagamento deve conter, quando aplicável:

```text
transaction_amount
payment_method_id = "pix"
external_reference = order.id
payer.email
payer.identification.type
payer.identification.number
```

O `external_reference` deve ser sempre o ID interno do pedido.

Isso permite relacionar inequivocamente o pagamento externo ao pedido da Croma.

## CPF/CNPJ

O CPF/CNPJ utilizado no pagamento deve vir do perfil autenticado do usuário.

Não deve ser recebido arbitrariamente pelo frontend durante a criação do pagamento.

---

# PAYMENT-03 — Cartão via Checkout Pro

## Estratégia

Cartão será implementado utilizando o **Checkout Pro** do Mercado Pago.

O backend **não recebe número do cartão, CVV, validade ou PAN**.

O cliente é redirecionado para o Mercado Pago para realizar o pagamento.

## Fluxo

```text
Cliente
   │
   │ POST /orders/{order_id}/pay/card
   │ Idempotency-Key: UUID
   ▼
PaymentRoute
   │
   ▼
PaymentService
   │
   ├── valida usuário
   ├── valida pedido
   ├── valida status
   └── verifica cobrança existente
   │
   ▼
MPClient
   │
   │ POST /checkout/preferences
   ▼
Mercado Pago
   │
   │ preference_id
   │ init_point
   │ sandbox_init_point
   ▼
PaymentService
   │
   ├── persiste preference_id
   └── retorna URL
   ▼
Frontend Croma
   │
   └── redireciona cliente para o Mercado Pago
                │
                ▼
             Pagamento
                │
                ├──────────────► Webhook
                │
                └──────────────► back_url
                                   │
                                   ▼
                              Frontend Croma
```

O retorno do frontend **não é considerado prova de pagamento**.

A confirmação financeira deve ocorrer através da consulta ao Mercado Pago e/ou webhook válido.

---

# PAYMENT-04 — Checkout Pro e Webhooks

O backend deve ser capaz de processar os eventos configurados no Mercado Pago.

No MVP, o webhook deve suportar pelo menos:

```text
payment
merchant_order
```

## Evento `payment`

Quando receber um evento `payment`, o backend:

1. valida a assinatura;
2. identifica o recurso externo;
3. persiste o evento;
4. consulta o pagamento diretamente no Mercado Pago;
5. utiliza o estado retornado pelo Mercado Pago como fonte de verdade;
6. relaciona o pagamento ao `order` através de `external_reference`;
7. atualiza o pedido conforme as regras de estado.

## Evento `merchant_order`

Quando receber um evento `merchant_order`, o backend:

1. valida a assinatura;
2. persiste o evento;
3. consulta a `merchant_order` no Mercado Pago;
4. identifica os pagamentos associados;
5. consulta/valida os pagamentos relevantes;
6. identifica o pedido interno;
7. atualiza o pedido conforme as regras de estado.

### Regra importante

O backend **não deve assumir que existe uma ordem específica entre eventos `payment` e `merchant_order`.

Eventos podem:

* chegar fora de ordem;
* chegar repetidos;
* chegar com atraso;
* chegar antes ou depois de outro evento relacionado.

Portanto, o processamento deve ser **idempotente e independente da ordem de chegada**.

---

# PAYMENT-05 — Webhook público

## Endpoint

```http
POST /webhooks/mercadopago
```

O endpoint não utiliza autenticação JWT.

O Mercado Pago não possui sessão/autorização de usuário da Croma.

A autenticação do webhook ocorre através da assinatura enviada pelo Mercado Pago.

## Fluxo

```text
Mercado Pago
      │
      │ POST /webhooks/mercadopago
      │
      │ headers:
      │ x-signature
      │ x-request-id
      ▼
WebhookRoute
      │
      ├── lê body cru
      ├── valida assinatura
      │
      ├── assinatura inválida
      │       └── 401
      │
      ▼
PaymentService
      │
      ├── identifica evento
      ├── persiste evento
      ├── verifica duplicidade
      ├── consulta MP
      └── processa
```

## Body

A assinatura deve ser calculada utilizando o **body cru da requisição**.

O endpoint não deve depender de um Pydantic model para validar o body antes da verificação criptográfica.

O body original deve ser preservado para auditoria.

---

# PAYMENT-06 — Validação HMAC

A assinatura do webhook deve ser validada antes de qualquer processamento financeiro.

O `mp_client.py` deve concentrar a lógica de validação criptográfica.

O processamento deve utilizar:

```text
raw_body
x-signature
x-request-id
MP_WEBHOOK_SECRET
```

A comparação da assinatura deve utilizar comparação segura contra timing attacks, como `hmac.compare_digest`.

## Assinatura inválida

Quando a assinatura for inválida:

```http
401 Unauthorized
```

O evento não deve ser persistido como evento processável.

Deve ser registrado apenas um log seguro contendo informações não sensíveis, por exemplo:

```text
PAYMENT_WEBHOOK_INVALID_SIGNATURE
```

Nunca registrar:

* secret;
* access token;
* payload completo;
* CPF/CNPJ completo;
* dados financeiros sensíveis.

---

# PAYMENT-07 — Persistência dos eventos

A tabela `payment_events` é o registro de auditoria dos eventos recebidos do Mercado Pago.

O payload original deve ser persistido em:

```text
payment_events.payload
```

como `jsonb`.

## Idempotência

A identificação de duplicidade deve utilizar o identificador externo do evento/recurso conforme o contrato adotado pelo webhook.

A constraint:

```text
payment_events_provider_event_uniq
```

garante unicidade por provedor + evento externo.

## Evento duplicado

Se o evento já existir:

```text
200 OK
```

e o processamento não deve ser executado novamente.

Registrar apenas um log seguro:

```text
PAYMENT_WEBHOOK_DUPLICATE
```

---

# PAYMENT-08 — Regras de resposta do webhook

Depois que a assinatura for validada e o evento for persistido, o endpoint deve responder ao Mercado Pago de forma que o mesmo evento não seja reenviado indefinidamente por uma falha interna transitória.

O evento persistido deve possuir informação suficiente para ser processado posteriormente através de reconciliação.

Se o processamento interno falhar após a persistência:

```text
processed_at = NULL
```

O erro deve ser registrado nos logs sem expor dados sensíveis.

O webhook não deve transformar um problema interno em uma falsa confirmação de pagamento.

## Regra de ouro

> Receber e persistir o evento não significa confirmar o pagamento.

Somente uma consulta válida ao Mercado Pago, retornando estado financeiro compatível com aprovação, pode fazer o pedido avançar para `paid`.

---

# PAYMENT-09 — Nunca confiar no frontend

O frontend pode receber:

* `success`;
* `pending`;
* `failure`;
* retorno do Checkout Pro;
* informações de URL.

Nenhuma dessas informações é suficiente para confirmar pagamento.

O backend deve considerar como fonte de verdade financeira:

```text
Mercado Pago
```

através de:

1. consulta direta à API;
2. webhook válido;
3. reconciliação administrativa.

---

# PAYMENT-10 — Máquina de estados do pedido

O campo:

```text
orders.status
```

representa o estado operacional do pedido.

Fluxo principal:

```text
created
   │
   ▼
 paid
   │
   ▼
production
   │
   ▼
shipped
   │
   ▼
delivered
```

Cancelamento:

```text
created ───────────────► cancelled
paid ──────────────────► cancelled
production ────────────► cancelled
shipped ───────────────► cancelled
```

## Transições válidas

```text
created    → paid | cancelled
paid       → production | cancelled
production → shipped | cancelled
shipped    → delivered | cancelled
delivered  → final
cancelled  → final
```

## Transições proibidas

Não são permitidos:

* saltos de etapa;
* retorno de etapa;
* `delivered → production`;
* `shipped → paid`;
* `cancelled → paid`;
* `cancelled → production`;
* qualquer outra transição não explicitamente permitida.

A validação deve acontecer no backend.

O frontend nunca define livremente a máquina de estados.

---

# PAYMENT-11 — Máquina de estados financeiro

O campo:

```text
orders.payment_status
```

representa exclusivamente o estado financeiro.

Fluxo:

```text
pending
   │
   ├────────► paid
   │
   └────────► failed

paid
   │
   └────────► refunded

failed → final
refunded → final
```

## Transições válidas

```text
pending  → paid | failed
paid     → refunded
failed   → final
refunded → final
```

## Regra de não regressão

Um webhook nunca pode transformar:

```text
paid → pending
```

nem:

```text
paid → failed
```

automaticamente.

O backend deve proteger estados financeiros já confirmados contra eventos atrasados ou fora de ordem.

---

# PAYMENT-12 — Relação entre `status` e `payment_status`

Os campos possuem responsabilidades diferentes.

### `orders.status`

Representa o ciclo operacional:

```text
created
paid
production
shipped
delivered
cancelled
```

### `orders.payment_status`

Representa o financeiro:

```text
pending
paid
failed
refunded
```

## Confirmação de pagamento

Quando um pagamento aprovado for confirmado pelo Mercado Pago, o backend deve atualizar:

```text
payment_status = paid
status = paid
```

Essa alteração deve ser feita de maneira consistente dentro da operação do banco.

## Cancelamento de pedido pago

**Decisão travada com a Croma:**

Se um administrador fizer:

```http
PATCH /admin/orders/{id}/status
```

e mudar:

```text
paid → cancelled
```

o backend **não altera**:

```text
payment_status
```

Portanto:

```text
status = cancelled
payment_status = paid
```

é um estado válido.

### Motivo

O cancelamento operacional e o estorno financeiro são responsabilidades diferentes.

O sistema da Croma não realizará refund automático no MVP.

O dinheiro será tratado manualmente pela Croma no painel do Mercado Pago.

Depois de um estorno manual, a atualização de:

```text
payment_status = refunded
```

poderá ser implementada em uma feature futura.

> **Decisão definitiva:** cancelar um pedido pago NÃO dispara refund automático e NÃO altera `payment_status`.

---

# PAYMENT-13 — Idempotência na criação de pagamento

Existem duas camadas diferentes de idempotência:

## 1. Idempotência da requisição da Croma

O frontend envia:

```http
Idempotency-Key: <UUID v4>
```

O backend deve validar o formato no boundary HTTP.

Essa chave representa a intenção do cliente de executar aquela operação.

## 2. Idempotência enviada ao Mercado Pago

O backend deve utilizar uma chave própria para a chamada ao Mercado Pago:

```http
X-Idempotency-Key: <UUID>
```

Essa chave pertence à integração backend → Mercado Pago.

Ela não deve ser confundida conceitualmente com a chave enviada pelo frontend.

O backend deve garantir que uma mesma tentativa lógica não resulte em múltiplas cobranças externas.

---

# PAYMENT-14 — Regras para criação de pagamento

Antes de criar qualquer pagamento, o `PaymentService` deve validar:

1. usuário autenticado;
2. pedido existente;
3. pedido pertence ao usuário;
4. pedido permite pagamento;
5. `payment_status` ainda permite criação;
6. método solicitado;
7. dados necessários ao método;
8. CPF/CNPJ quando exigido;
9. existência de cobrança anterior;
10. consistência do valor do pedido.

## Pedido com cobrança existente

Se já existir uma cobrança válida para o mesmo método:

```text
retornar a referência existente
```

e não criar outra cobrança.

## Pedido com cobrança de outro método

Exemplo:

```text
payment_method = pix
```

e o usuário tenta:

```text
POST /pay/card
```

deve retornar:

```http
409 Conflict
```

Não criar uma segunda cobrança automaticamente.

---

# PAYMENT-15 — Idempotência do PIX

Para PIX, a referência externa será o ID do pagamento no Mercado Pago:

```text
payment_external_id
```

O backend deve armazenar a referência necessária para recuperar o pagamento posteriormente.

A resposta pode conter:

```text
payment_id
qr_code
qr_code_base64
ticket_url
```

O frontend utiliza esses dados para apresentar o pagamento.

---

# PAYMENT-16 — Idempotência do Checkout Pro

Para cartão, a referência externa inicial é a:

```text
preference_id
```

A preferência deve ser associada ao pedido através de:

```text
external_reference = order.id
```

O backend não considera a criação da preferência como confirmação de pagamento.

O pagamento somente será confirmado após consulta/validação do recurso financeiro correspondente no Mercado Pago.

---

# PAYMENT-17 — Validação do valor do pedido

O valor utilizado para criar a cobrança deve ser derivado do pedido armazenado no backend.

O backend **não deve confiar em um valor enviado pelo frontend**.

O frontend pode informar apenas:

```text
order_id
```

e dados estritamente necessários à operação.

O servidor calcula/obtém:

```text
total
items
quantidades
preços
```

a partir da fonte persistida do pedido.

Isso evita manipulação do preço através do cliente.

---

# PAYMENT-18 — Reconciliação manual

Endpoint:

```http
POST /admin/orders/{order_id}/reconcile
```

## Objetivo

Permitir que um administrador consulte o Mercado Pago quando:

* um webhook não chegou;
* existe dúvida sobre o estado financeiro;
* ocorreu falha de processamento;
* existe divergência entre banco local e Mercado Pago.

## Fluxo

```text
Admin
 │
 │ POST /admin/orders/{id}/reconcile
 ▼
Backend
 │
 ├── busca order
 ├── valida payment_external_id
 ├── identifica método
 │
 ├── consulta Mercado Pago
 │
 ├── compara estado externo
 │
 └── sincroniza estado permitido
```

## PIX

Consultar:

```http
GET /v1/payments/{payment_id}
```

## Checkout Pro

A partir da referência persistida e da associação via `external_reference`, localizar o recurso financeiro correspondente e consultar seu estado no Mercado Pago.

Não assumir que `preference_id` seja um ID de pagamento.

---

# PAYMENT-19 — Regras de reconciliação

A reconciliação pode promover:

```text
pending → paid
```

quando o Mercado Pago confirmar pagamento aprovado.

Também pode promover:

```text
pending → failed
```

quando o estado externo indicar uma falha definitiva compatível.

## Nunca rebaixar automaticamente

Se localmente:

```text
payment_status = paid
```

a reconciliação não deve transformar o pedido automaticamente em:

```text
pending
failed
```

Estados financeiros já confirmados exigem tratamento explícito.

---

# PAYMENT-20 — CPF/CNPJ

CPF/CNPJ será obrigatório para novos cadastros.

Campos:

```text
profiles.cpf_cnpj
profiles.tipo_pessoa
```

## Regras

`cpf_cnpj` deve conter somente dígitos.

Formatos aceitos:

```text
CPF  → 11 dígitos
CNPJ → 14 dígitos
```

O backend deve validar:

* quantidade de dígitos;
* dígitos verificadores;
* unicidade.

Não basta validar somente regex.

## Tipo de pessoa

O backend deriva:

```text
11 dígitos → fisica
14 dígitos → juridica
```

O cliente não deve conseguir declarar arbitrariamente um `tipo_pessoa` incompatível.

## Unicidade

A constraint:

```text
profiles_cpf_cnpj_uniq
```

garante unicidade global.

Conflito:

```http
409 Conflict
```

## Usuários legados

A coluna continua nullable no banco para permitir migração gradual.

Usuários existentes precisam completar seus dados antes de utilizar o fluxo de pagamento que exige CPF/CNPJ.

---

# PAYMENT-21 — Snapshot do endereço

O pedido deve armazenar:

```text
orders.address_snapshot
```

como `jsonb`.

O snapshot representa o endereço **no momento da compra**.

## Campos

Exemplo:

```json
{
  "nome_destinatario": "...",
  "cep": "...",
  "logradouro": "...",
  "numero": "...",
  "complemento": "...",
  "bairro": "...",
  "cidade": "...",
  "estado": "..."
}
```

Não incluir:

```text
id
user_id
principal
```

no snapshot.

## Motivo

O usuário pode alterar ou remover o endereço posteriormente.

O pedido histórico não pode mudar junto com o cadastro do usuário.

Portanto:

```text
addresses
```

é a entidade atual do usuário.

Enquanto:

```text
orders.address_snapshot
```

é a fotografia histórica do endereço utilizado na compra.

`address_id` pode continuar existindo para rastreabilidade, mas o snapshot é a fonte de verdade para a entrega histórica.

---

# PAYMENT-22 — Rotas de pagamento

Os métodos terão endpoints separados.

## PIX

```http
POST /orders/{order_id}/pay/pix
```

Resposta:

```text
PixPaymentResponse
```

## Cartão

```http
POST /orders/{order_id}/pay/card
```

Resposta:

```text
CardPaymentResponse
```

## Motivo

Os métodos possuem comportamentos diferentes.

PIX retorna dados para renderização.

Cartão retorna URL para redirecionamento.

As rotas compartilham validações internas através do:

```text
PaymentService._validate_order_for_payment(...)
```

Não duplicar regras entre os endpoints.

---

# PAYMENT-23 — Endpoints administrativos

Prefixo:

```text
/admin/orders
```

Todos os endpoints exigem:

```text
get_current_admin_user
```

## Listagem

```http
GET /admin/orders
```

Filtros:

```text
status
payment_status
user_id
limit
offset
```

## Detalhes

```http
GET /admin/orders/{order_id}
```

Deve retornar, conforme os models existentes:

* pedido;
* items;
* status;
* payment_status;
* método de pagamento;
* referência externa;
* snapshot do endereço;
* demais dados administrativos permitidos.

## Alteração de status

```http
PATCH /admin/orders/{order_id}/status
```

Body:

```json
{
  "status": "production"
}
```

A transição deve ser validada pela máquina de estados.

## Reconciliação

```http
POST /admin/orders/{order_id}/reconcile
```

Consulta o Mercado Pago e sincroniza o estado financeiro permitido.

---

# PAYMENT-24 — Estorno

Não existe endpoint de refund no MVP.

Não implementar:

```http
POST /admin/orders/{id}/refund
```

Não chamar API de refund automaticamente.

## Processo atual

```text
Pedido pago
    │
    ▼
Admin cancela pedido
    │
    ▼
orders.status = cancelled
payment_status = paid
    │
    ▼
Croma acessa painel do Mercado Pago
    │
    ▼
Estorno manual
```

A implementação de refund automático é uma feature futura.

---

# PAYMENT-25 — Segurança

## Nunca armazenar

O backend não deve armazenar:

* número completo de cartão;
* CVV;
* validade do cartão;
* PAN;
* dados equivalentes de cartão.

## Nunca logar

Nunca registrar:

```text
MP_ACCESS_TOKEN
MP_PUBLIC_KEY
MP_WEBHOOK_SECRET
```

Também não registrar:

* payload completo de webhook nos logs;
* CPF/CNPJ completo;
* QR Code completo;
* tokens;
* headers sensíveis;
* credenciais do Mercado Pago.

## Logs permitidos

Exemplos:

```text
PAYMENT_CREATED
PAYMENT_WEBHOOK_RECEIVED
PAYMENT_WEBHOOK_DUPLICATE
PAYMENT_WEBHOOK_INVALID_SIGNATURE
PAYMENT_RECONCILED
PAYMENT_STATUS_UPDATED
```

Sempre utilizar IDs técnicos e informações não sensíveis.

---

# PAYMENT-26 — Autorização

## Pagamento

```text
/orders/{order_id}/pay/*
```

exige:

```text
get_current_user
```

O backend deve verificar que o pedido pertence ao usuário autenticado.

Se o pedido não pertencer ao usuário, preferir:

```http
404 Not Found
```

em vez de revelar que o recurso existe.

## Administração

```text
/admin/orders/*
```

exige:

```text
get_current_admin_user
```

RBAC deve ser fail-closed.

Nunca confiar em:

```text
role
```

enviado pelo frontend.

---

# PAYMENT-27 — Variáveis de ambiente

```env
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_ENV=sandbox
```

## Regras

Obrigatórias:

```text
MP_ACCESS_TOKEN
MP_WEBHOOK_SECRET
```

`MP_PUBLIC_KEY` pode ser utilizada pelo frontend e/ou infraestrutura de integração conforme a implementação.

`MP_ENV`:

```text
sandbox
production
```

Default:

```text
sandbox
```

A configuração deve validar os valores no boot da aplicação quando necessários ao ambiente.

## Produção

A mudança de:

```text
sandbox
```

para:

```text
production
```

deve exigir apenas a configuração apropriada das credenciais e ambiente.

Nenhuma lógica de negócio deve depender de código diferente para produção.

---

# PAYMENT-28 — Cliente HTTP do Mercado Pago

Arquivo:

```text
app/infra/mp_client.py
```

Responsabilidade:

> encapsular toda comunicação HTTP com o Mercado Pago.

Não colocar regra de negócio de pedido nesse módulo.

## Operações esperadas

```python
create_pix_payment(payload, idempotency_key)
create_card_preference(payload)
get_payment(payment_id)
get_merchant_order(merchant_order_id)
verify_webhook_signature(raw_body, headers)
```

O cliente deve cuidar de:

* URL base;
* headers;
* autenticação;
* timeout;
* tratamento de erro HTTP;
* serialização;
* parsing da resposta;
* assinatura do webhook.

O `PaymentService` decide **o que fazer** com o resultado.

O `MPClient` decide apenas **como falar com o Mercado Pago**.

---

# PAYMENT-29 — Repository

Arquivo:

```text
app/repositories/payment_repository.py
```

Responsabilidade:

> ser o ponto de acesso aos dados persistidos relacionados ao pagamento.

Deve concentrar operações como:

* criar `payment_events`;
* detectar evento duplicado;
* atualizar `processed_at`;
* buscar eventos;
* atualizar referências externas do pedido;
* atualizar estados financeiros;
* obter informações necessárias à reconciliação.

Nenhuma query de `payment_events` deve ficar espalhada em routes/services.

---

# PAYMENT-30 — Service

Arquivo:

```text
app/services/payment_service.py
```

Responsabilidade:

> conter as regras de negócio do pagamento.

Deve coordenar:

```text
Route
  ↓
PaymentService
  ↓
Repository + MPClient
```

O service deve ser responsável por:

* validar pedido;
* validar usuário;
* validar método;
* validar estado;
* criar PIX;
* criar Checkout Pro;
* processar webhook;
* confirmar pagamento;
* reconciliar;
* aplicar máquina de estados;
* impedir regressões;
* garantir idempotência lógica.

As routes não devem conter regra financeira.

---

# PAYMENT-31 — Models

Arquivo:

```text
app/models/payment.py
```

Responsabilidade:

> contratos de entrada e saída da API.

Exemplos conceituais:

```text
PixPaymentResponse
CardPaymentResponse
PaymentWebhookResponse
AdminOrderStatusUpdate
```

Os models não devem executar chamadas externas nem acessar banco.

---

# PAYMENT-32 — Webhook Route

Arquivo:

```text
app/routes/webhook_routes.py
```

Responsabilidade mínima:

1. receber request;
2. obter body cru;
3. obter headers;
4. delegar validação ao `MPClient`;
5. delegar processamento ao `PaymentService`;
6. retornar resposta HTTP.

A route não deve:

* atualizar banco diretamente;
* chamar API do Mercado Pago diretamente;
* implementar máquina de estados;
* implementar HMAC manualmente fora do client.

---

# PAYMENT-33 — Ordem de responsabilidades

Arquitetura desejada:

```text
HTTP
 │
 ▼
Routes
 │
 ▼
Services
 │
 ├──────────────► Repositories
 │
 └──────────────► Infra / MPClient
```

### Routes

HTTP.

### Services

Regras de negócio.

### Repositories

Persistência.

### Infra

Integrações externas.

### Models

Contratos.

Essa separação deve ser preservada.

---

# PAYMENT-34 — Arquivos novos

Estrutura:

```text
app/
├── infra/
│   └── mp_client.py
│
├── models/
│   └── payment.py
│
├── repositories/
│   └── payment_repository.py
│
├── routes/
│   ├── payment_routes.py
│   ├── webhook_routes.py
│   └── admin_order_routes.py
│
└── services/
    └── payment_service.py
```

---

# PAYMENT-35 — Arquivos existentes afetados

## `app/models/auth.py`

`RegisterRequest` passa a aceitar/validar:

```text
cpf_cnpj
```

## `app/models/order.py`

`OrderResponse` passa a expor:

```text
address_snapshot
```

quando apropriado ao contrato atual da API.

## `app/models/profile.py`

Adicionar:

```text
cpf_cnpj
tipo_pessoa
```

## `app/services/auth_service.py`

Garantir que `cpf_cnpj` seja persistido no perfil durante o cadastro.

## `app/services/profile_service.py`

Retornar os novos campos do perfil.

## `app/services/order_service.py`

Criar `address_snapshot` no momento da criação do pedido.

## `app/config/settings.py`

Adicionar configurações do Mercado Pago.

## `app/main.py`

Registrar:

```text
payment_routes
webhook_routes
admin_order_routes
```

## `app/utils/exceptions.py`

Adicionar exceções específicas quando necessário, incluindo erro de assinatura inválida.

## `app/utils/validators.py`

Adicionar validação de:

* CPF;
* CNPJ.

---

# PAYMENT-36 — Testes

O módulo deve ser entregue com testes em camadas.

## Unitários

Testar:

* CPF;
* CNPJ;
* tipo de pessoa;
* máquina de estados;
* transições inválidas;
* idempotência;
* cálculo de parcelamento;
* validação de webhook;
* regras de promoção de status.

## Route tests

Testar:

* autenticação;
* autorização;
* ownership;
* payload;
* status HTTP;
* respostas;
* conflitos;
* webhook público;
* assinatura inválida.

## Integração

Testar:

* repository;
* Supabase;
* persistência de `payment_events`;
* atualização de `orders`;
* integração com MP mockado.

## Não depender do Mercado Pago real nos testes automatizados

As chamadas externas devem ser mockadas/stubadas.

Testes reais no sandbox podem existir como testes manuais ou smoke tests separados.

---

# PAYMENT-37 — Critérios de aceite

O módulo será considerado funcional quando:

### PIX

* [ ] usuário autenticado consegue iniciar PIX;
* [ ] pedido de outro usuário não pode ser pago;
* [ ] pedido inválido é rejeitado;
* [ ] CPF/CNPJ é validado;
* [ ] pagamento é criado no MP;
* [ ] QR Code é retornado;
* [ ] repetição idempotente não cria cobrança duplicada;
* [ ] webhook válido confirma pagamento;
* [ ] webhook duplicado não processa novamente.

### Cartão

* [ ] usuário consegue criar preferência;
* [ ] backend retorna `init_point`;
* [ ] frontend consegue redirecionar;
* [ ] backend não recebe dados de cartão;
* [ ] pagamento aprovado pode ser associado ao pedido;
* [ ] webhook/reconciliação atualiza o pedido;
* [ ] retorno do frontend não é tratado como confirmação financeira.

### Administração

* [ ] admin consegue listar pedidos;
* [ ] admin consegue visualizar pedido;
* [ ] admin consegue alterar status;
* [ ] máquina de estados é respeitada;
* [ ] admin consegue reconciliar;
* [ ] cancelamento de pedido pago mantém `payment_status=paid`;
* [ ] nenhum refund automático é executado.

### Segurança

* [ ] webhook exige assinatura válida;
* [ ] secrets não aparecem em logs;
* [ ] payload sensível não aparece em logs;
* [ ] dados de cartão nunca passam pelo backend;
* [ ] endpoints admin exigem RBAC;
* [ ] ownership é validado;
* [ ] estados financeiros não sofrem regressão indevida.

---

# PAYMENT-38 — O que NÃO pertence ao backend neste MVP

O backend da Croma não será responsável por:

```text
Captura de cartão
Antifraude
3DS
Armazenamento de cartão
Estorno automático
Emissão de NF-e
Job automático de reconciliação
Fila assíncrona de pagamentos
Parcelamento com juros
Assinaturas
```

Essas responsabilidades pertencem ao Mercado Pago ou a features futuras da plataforma.

---

# PAYMENT-39 — NF-e

**NF-e está fora deste bloco de Checkout.**

Pagamento aprovado não significa emissão fiscal automática.

O módulo de pagamento deve apenas deixar disponível a informação necessária para uma futura integração fiscal.

A implementação de:

```text
NF-e
NFC-e
NFS-e
SEFAZ
certificado digital
tributação
```

não deve entrar neste bloco.

Isso evita acoplamento prematuro entre:

```text
Pagamento
```

e:

```text
Fiscal
```

---

# PAYMENT-40 — Princípios finais

As seguintes decisões são consideradas **travadas** para a implementação do MVP:

1. Mercado Pago é responsável pelo processamento financeiro.
2. Backend nunca recebe dados completos de cartão.
3. PIX usa API de Payments.
4. Cartão usa Checkout Pro.
5. Webhook é público, mas protegido por assinatura.
6. Webhook é idempotente.
7. Ordem dos eventos externos não é confiável.
8. Frontend nunca é fonte de verdade financeira.
9. Mercado Pago é a fonte de verdade do pagamento externo.
10. `orders.status` e `orders.payment_status` são estados independentes.
11. Pagamento aprovado leva o pedido a `paid`.
12. Cancelamento operacional não executa refund.
13. `cancelled + paid` é um estado permitido.
14. Refund é manual no painel do Mercado Pago no MVP.
15. Não existe endpoint de refund neste bloco.
16. Reconciliação é manual.
17. CPF/CNPJ é obrigatório para novos cadastros.
18. CPF/CNPJ deve possuir validação real de dígitos verificadores.
19. Endereço do pedido possui snapshot histórico.
20. Rotas de PIX e cartão são separadas.
21. Regras de negócio ficam no service.
22. Persistência fica no repository.
23. Integração com MP fica no `MPClient`.
24. Segurança financeira tem prioridade sobre conveniência.
25. Nenhuma alteração futura deve quebrar essas invariantes sem uma nova decisão arquitetural documentada.

---

# Referências

Documentação oficial do Mercado Pago utilizada como referência para implementação:

* API de Payments
* Checkout Pro
* Webhooks
* Assinatura secreta
* Idempotência
* Merchant Orders

**Observação:** detalhes específicos da API do Mercado Pago devem ser conferidos na documentação oficial no momento da implementação, especialmente headers, formato exato da assinatura, payloads de webhook e relacionamento entre `preference`, `merchant_order` e `payment`.
