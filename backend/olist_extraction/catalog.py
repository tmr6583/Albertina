from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IncrementalStrategy:
    mode: str
    start_param: str
    end_param: str | None = None
    datetime_format: str = "iso"


@dataclass(frozen=True)
class EndpointStep:
    name: str
    endpoint_path: str
    source_step: str | None = None
    path_params: dict[str, tuple[str, ...]] = field(default_factory=dict)
    record_id_keys: tuple[str, ...] = ()
    updated_at_keys: tuple[str, ...] = ()
    nested_collection_keys: tuple[str, ...] = ()
    item_keys: tuple[str, ...] = ()
    pagination: bool = False
    page_limit: int | None = None
    incremental: IncrementalStrategy | None = None
    extra_params: dict[str, str] = field(default_factory=dict)
    singleton: bool = False
    only_if_changed: bool = False
    ignore_http_statuses: tuple[int, ...] = ()
    ignore_invalid_json: bool = False


@dataclass(frozen=True)
class Workflow:
    entity_name: str
    root_step: str
    steps: tuple[EndpointStep, ...]


WATERMARK_UPDATED = IncrementalStrategy(mode="watermark", start_param="dataAtualizacao")
WATERMARK_UPDATED_BR = IncrementalStrategy(mode="watermark", start_param="dataAtualizacao", datetime_format="br")
WATERMARK_CHANGED = IncrementalStrategy(mode="watermark", start_param="dataAlteracao")
DATE_RANGE_EMISSAO = IncrementalStrategy(mode="date_range", start_param="dataInicialEmissao", end_param="dataFinalEmissao")


WORKFLOWS: tuple[Workflow, ...] = (
    Workflow(
        entity_name="company_info",
        root_step="company.info",
        steps=(EndpointStep(name="company.info", endpoint_path="/info", singleton=True),),
    ),
    Workflow(
        entity_name="users",
        root_step="users.list",
        steps=(EndpointStep(name="users.list", endpoint_path="/usuarios", pagination=False),),
    ),
    Workflow(
        entity_name="vendors",
        root_step="vendors.list",
        steps=(EndpointStep(name="vendors.list", endpoint_path="/vendedores", pagination=False),),
    ),
    Workflow(
        entity_name="brands",
        root_step="brands.list",
        steps=(EndpointStep(name="brands.list", endpoint_path="/marcas", pagination=False),),
    ),
    Workflow(
        entity_name="categories",
        root_step="categories.tree",
        steps=(
            EndpointStep(name="categories.tree", endpoint_path="/categorias/todas", pagination=False, item_keys=("itens", "items")),
            EndpointStep(
                name="categories.detail",
                endpoint_path="/categorias/{idCategoria}",
                source_step="categories.tree",
                path_params={"idCategoria": ("id", "idCategoria")},
                record_id_keys=("id", "idCategoria"),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="revenue_expense_categories",
        root_step="financial_categories.list",
        steps=(
            EndpointStep(
                name="financial_categories.list",
                endpoint_path="/categorias-receita-despesa",
                pagination=True,
                record_id_keys=("id",),
            ),
        ),
    ),
    Workflow(
        entity_name="contacts",
        root_step="contacts.list",
        steps=(
            EndpointStep(name="contacts.types", endpoint_path="/contatos/tipos", singleton=False),
            EndpointStep(
                name="contacts.list",
                endpoint_path="/contatos",
                pagination=True,
                page_limit=50,
                incremental=WATERMARK_UPDATED,
                record_id_keys=("id", "idContato"),
                updated_at_keys=("dataAtualizacao",),
            ),
            EndpointStep(
                name="contacts.detail",
                endpoint_path="/contatos/{idContato}",
                source_step="contacts.list",
                path_params={"idContato": ("record_id", "id", "idContato")},
                record_id_keys=("id", "idContato"),
                singleton=True,
                only_if_changed=True,
            ),
            EndpointStep(
                name="contacts.people",
                endpoint_path="/contatos/{idContato}/pessoas",
                source_step="contacts.list",
                path_params={"idContato": ("record_id", "id", "idContato")},
                record_id_keys=("id", "idPessoa"),
                only_if_changed=True,
            ),
            EndpointStep(
                name="contacts.person_detail",
                endpoint_path="/contatos/{idContato}/pessoas/{idPessoa}",
                source_step="contacts.people",
                path_params={
                    "idContato": ("idContato",),
                    "idPessoa": ("record_id", "id", "idPessoa"),
                },
                record_id_keys=("id", "idPessoa"),
                singleton=True,
                only_if_changed=True,
            ),
        ),
    ),
    Workflow(
        entity_name="payment_methods",
        root_step="payment_methods.list",
        steps=(
            EndpointStep(name="payment_methods.list", endpoint_path="/formas-pagamento", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="payment_methods.detail",
                endpoint_path="/formas-pagamento/{idFormaPagamento}",
                source_step="payment_methods.list",
                path_params={"idFormaPagamento": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="receipt_methods",
        root_step="receipt_methods.list",
        steps=(
            EndpointStep(name="receipt_methods.list", endpoint_path="/formas-recebimento", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="receipt_methods.detail",
                endpoint_path="/formas-recebimento/{idFormaRecebimento}",
                source_step="receipt_methods.list",
                path_params={"idFormaRecebimento": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="shipping_methods",
        root_step="shipping_methods.list",
        steps=(
            EndpointStep(name="shipping_methods.list", endpoint_path="/formas-envio", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="shipping_methods.detail",
                endpoint_path="/formas-envio/{idFormaEnvio}",
                source_step="shipping_methods.list",
                path_params={"idFormaEnvio": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="deposits",
        root_step="deposits.list",
        steps=(
            EndpointStep(name="deposits.list", endpoint_path="/depositos", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="deposits.detail",
                endpoint_path="/depositos/{idDeposito}",
                source_step="deposits.list",
                path_params={"idDeposito": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="intermediators",
        root_step="intermediators.list",
        steps=(
            EndpointStep(name="intermediators.list", endpoint_path="/intermediadores", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="intermediators.detail",
                endpoint_path="/intermediadores/{idIntermediador}",
                source_step="intermediators.list",
                path_params={"idIntermediador": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="price_lists",
        root_step="price_lists.list",
        steps=(
            EndpointStep(name="price_lists.list", endpoint_path="/listas-precos", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="price_lists.detail",
                endpoint_path="/listas-precos/{idListaDePreco}",
                source_step="price_lists.list",
                path_params={"idListaDePreco": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="services",
        root_step="services.list",
        steps=(
            EndpointStep(name="services.list", endpoint_path="/servicos", pagination=False, record_id_keys=("id",)),
            EndpointStep(
                name="services.detail",
                endpoint_path="/servicos/{idServico}",
                source_step="services.list",
                path_params={"idServico": ("record_id", "id")},
                record_id_keys=("id",),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="tag_groups",
        root_step="tag_groups.list",
        steps=(EndpointStep(name="tag_groups.list", endpoint_path="/grupos-tags", pagination=False, record_id_keys=("id",)),),
    ),
    Workflow(
        entity_name="product_tags",
        root_step="product_tags.list",
        steps=(EndpointStep(name="product_tags.list", endpoint_path="/tags", pagination=False, record_id_keys=("id",)),),
    ),
    Workflow(
        entity_name="products",
        root_step="products.list",
        steps=(
            EndpointStep(
                name="products.list",
                endpoint_path="/produtos",
                pagination=True,
                incremental=WATERMARK_CHANGED,
                record_id_keys=("id", "idProduto"),
                updated_at_keys=("dataAlteracao",),
            ),
            EndpointStep(
                name="products.detail",
                endpoint_path="/produtos/{idProduto}",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
                record_id_keys=("id", "idProduto"),
                singleton=True,
            ),
            EndpointStep(
                name="products.costs",
                endpoint_path="/produtos/{idProduto}/custos",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
                singleton=True,
            ),
            EndpointStep(
                name="products.fabricated",
                endpoint_path="/produtos/{idProduto}/fabricado",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
                singleton=True,
                ignore_http_statuses=(404,),
            ),
            EndpointStep(
                name="products.kit",
                endpoint_path="/produtos/{idProduto}/kit",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
                singleton=True,
                ignore_http_statuses=(400,),
            ),
            EndpointStep(
                name="products.tags",
                endpoint_path="/produtos/{idProduto}/tags",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
            ),
            EndpointStep(
                name="products.stock",
                endpoint_path="/estoque/{idProduto}",
                source_step="products.list",
                path_params={"idProduto": ("record_id", "id", "idProduto")},
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="orders",
        root_step="orders.list",
        steps=(
            EndpointStep(
                name="orders.list",
                endpoint_path="/pedidos",
                pagination=True,
                incremental=WATERMARK_UPDATED_BR,
                record_id_keys=("id", "idPedido"),
                updated_at_keys=("dataAtualizacao",),
            ),
            EndpointStep(
                name="orders.detail",
                endpoint_path="/pedidos/{idPedido}",
                source_step="orders.list",
                path_params={"idPedido": ("record_id", "id", "idPedido")},
                record_id_keys=("id", "idPedido"),
                singleton=True,
            ),
            EndpointStep(
                name="orders.markers",
                endpoint_path="/pedidos/{idPedido}/marcadores",
                source_step="orders.list",
                path_params={"idPedido": ("record_id", "id", "idPedido")},
            ),
        ),
    ),
    Workflow(
        entity_name="accounts_receivable",
        root_step="accounts_receivable.list",
        steps=(
            EndpointStep(
                name="accounts_receivable.list",
                endpoint_path="/contas-receber",
                pagination=True,
                incremental=DATE_RANGE_EMISSAO,
                record_id_keys=("id", "idContaReceber"),
            ),
            EndpointStep(
                name="accounts_receivable.detail",
                endpoint_path="/contas-receber/{idContaReceber}",
                source_step="accounts_receivable.list",
                path_params={"idContaReceber": ("record_id", "id", "idContaReceber")},
                record_id_keys=("id", "idContaReceber"),
                singleton=True,
            ),
            EndpointStep(
                name="accounts_receivable.markers",
                endpoint_path="/contas-receber/{idContaReceber}/marcadores",
                source_step="accounts_receivable.list",
                path_params={"idContaReceber": ("record_id", "id", "idContaReceber")},
            ),
            EndpointStep(
                name="accounts_receivable.receipts",
                endpoint_path="/contas-receber/{idContaReceber}/recebimentos",
                source_step="accounts_receivable.list",
                path_params={"idContaReceber": ("record_id", "id", "idContaReceber")},
                ignore_invalid_json=True,
                ignore_http_statuses=(404,),
            ),
        ),
    ),
    Workflow(
        entity_name="accounts_payable",
        root_step="accounts_payable.list",
        steps=(
            EndpointStep(
                name="accounts_payable.list",
                endpoint_path="/contas-pagar",
                pagination=True,
                incremental=DATE_RANGE_EMISSAO,
                record_id_keys=("id", "idContaPagar"),
            ),
            EndpointStep(
                name="accounts_payable.detail",
                endpoint_path="/contas-pagar/{idContaPagar}",
                source_step="accounts_payable.list",
                path_params={"idContaPagar": ("record_id", "id", "idContaPagar")},
                record_id_keys=("id", "idContaPagar"),
                singleton=True,
            ),
            EndpointStep(
                name="accounts_payable.markers",
                endpoint_path="/contas-pagar/{idContaPagar}/marcadores",
                source_step="accounts_payable.list",
                path_params={"idContaPagar": ("record_id", "id", "idContaPagar")},
            ),
            EndpointStep(
                name="accounts_payable.receipts",
                endpoint_path="/contas-pagar/{idContaPagar}/recebimentos",
                source_step="accounts_payable.list",
                path_params={"idContaPagar": ("record_id", "id", "idContaPagar")},
                ignore_invalid_json=True,
                ignore_http_statuses=(404,),
            ),
        ),
    ),
    Workflow(
        entity_name="invoices",
        root_step="invoices.list",
        steps=(
            EndpointStep(name="invoices.list", endpoint_path="/notas", pagination=True, record_id_keys=("id", "idNota")),
            EndpointStep(
                name="invoices.detail",
                endpoint_path="/notas/{idNota}",
                source_step="invoices.list",
                path_params={"idNota": ("record_id", "id", "idNota")},
                record_id_keys=("id", "idNota"),
                singleton=True,
            ),
            EndpointStep(
                name="invoices.link",
                endpoint_path="/notas/{idNota}/link",
                source_step="invoices.list",
                path_params={"idNota": ("record_id", "id", "idNota")},
                singleton=True,
            ),
            EndpointStep(
                name="invoices.markers",
                endpoint_path="/notas/{idNota}/marcadores",
                source_step="invoices.list",
                path_params={"idNota": ("record_id", "id", "idNota")},
            ),
            EndpointStep(
                name="invoices.xml",
                endpoint_path="/notas/{idNota}/xml",
                source_step="invoices.list",
                path_params={"idNota": ("record_id", "id", "idNota")},
                singleton=True,
                ignore_http_statuses=(400, 404),
                ignore_invalid_json=True,
            ),
            EndpointStep(
                name="invoices.item_detail",
                endpoint_path="/notas/{idNota}/itens/{idItem}",
                source_step="invoices.detail",
                path_params={
                    "idNota": ("idNota",),
                    "idItem": ("record_id", "id", "idItem"),
                },
                nested_collection_keys=("itens", "items"),
                record_id_keys=("id", "idItem"),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="shipments",
        root_step="shipments.list",
        steps=(
            EndpointStep(name="shipments.list", endpoint_path="/expedicao", pagination=True, record_id_keys=("id", "idAgrupamento")),
            EndpointStep(
                name="shipments.detail",
                endpoint_path="/expedicao/{idAgrupamento}",
                source_step="shipments.list",
                path_params={"idAgrupamento": ("record_id", "id", "idAgrupamento")},
                record_id_keys=("id", "idAgrupamento"),
                singleton=True,
            ),
            EndpointStep(
                name="shipments.labels",
                endpoint_path="/expedicao/{idAgrupamento}/etiquetas",
                source_step="shipments.list",
                path_params={"idAgrupamento": ("record_id", "id", "idAgrupamento")},
                singleton=True,
            ),
            EndpointStep(
                name="shipments.child_labels",
                endpoint_path="/expedicao/{idAgrupamento}/expedicao/{idExpedicao}/etiquetas",
                source_step="shipments.detail",
                path_params={
                    "idAgrupamento": ("idAgrupamento",),
                    "idExpedicao": ("record_id", "id", "idExpedicao"),
                },
                nested_collection_keys=("expedicoes",),
                record_id_keys=("id", "idExpedicao"),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="separations",
        root_step="separations.list",
        steps=(
            EndpointStep(name="separations.list", endpoint_path="/separacao", pagination=True, record_id_keys=("id", "idSeparacao")),
            EndpointStep(
                name="separations.detail",
                endpoint_path="/separacao/{idSeparacao}",
                source_step="separations.list",
                path_params={"idSeparacao": ("record_id", "id", "idSeparacao")},
                record_id_keys=("id", "idSeparacao"),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="crm_stages",
        root_step="crm.stages",
        steps=(
            EndpointStep(name="crm.stages", endpoint_path="/crm/estagios", pagination=False, record_id_keys=("id", "idEstagio")),
            EndpointStep(
                name="crm.stage_detail",
                endpoint_path="/crm/estagios/{idEstagio}",
                source_step="crm.stages",
                path_params={"idEstagio": ("record_id", "id", "idEstagio")},
                record_id_keys=("id", "idEstagio"),
                singleton=True,
            ),
        ),
    ),
    Workflow(
        entity_name="crm_subjects",
        root_step="crm.subjects",
        steps=(
            EndpointStep(
                name="crm.subjects",
                endpoint_path="/crm/assuntos",
                pagination=True,
                incremental=WATERMARK_UPDATED,
                record_id_keys=("id", "idAssunto"),
                updated_at_keys=("dataAtualizacao",),
            ),
            EndpointStep(
                name="crm.subject_detail",
                endpoint_path="/crm/assuntos/{idAssunto}",
                source_step="crm.subjects",
                path_params={"idAssunto": ("record_id", "id", "idAssunto")},
                record_id_keys=("id", "idAssunto"),
                singleton=True,
            ),
            EndpointStep(
                name="crm.actions",
                endpoint_path="/crm/assuntos/{idAssunto}/acoes",
                source_step="crm.subjects",
                path_params={"idAssunto": ("record_id", "id", "idAssunto")},
                record_id_keys=("id", "idAcao"),
            ),
            EndpointStep(
                name="crm.action_detail",
                endpoint_path="/crm/assuntos/{idAssunto}/acoes/{idAcao}",
                source_step="crm.actions",
                path_params={
                    "idAssunto": ("idAssunto",),
                    "idAcao": ("record_id", "id", "idAcao"),
                },
                record_id_keys=("id", "idAcao"),
                singleton=True,
            ),
            EndpointStep(
                name="crm.notes",
                endpoint_path="/crm/assuntos/{idAssunto}/anotacoes",
                source_step="crm.subjects",
                path_params={"idAssunto": ("record_id", "id", "idAssunto")},
                record_id_keys=("id", "idAnotacao"),
            ),
            EndpointStep(
                name="crm.markers",
                endpoint_path="/crm/assuntos/{idAssunto}/marcadores",
                source_step="crm.subjects",
                path_params={"idAssunto": ("record_id", "id", "idAssunto")},
            ),
        ),
    ),
    Workflow(
        entity_name="purchase_orders",
        root_step="purchase_orders.list",
        steps=(
            EndpointStep(name="purchase_orders.list", endpoint_path="/ordem-compra", pagination=True, record_id_keys=("id", "idOrdemCompra")),
            EndpointStep(
                name="purchase_orders.detail",
                endpoint_path="/ordem-compra/{idOrdemCompra}",
                source_step="purchase_orders.list",
                path_params={"idOrdemCompra": ("record_id", "id", "idOrdemCompra")},
                record_id_keys=("id", "idOrdemCompra"),
                singleton=True,
            ),
            EndpointStep(
                name="purchase_orders.markers",
                endpoint_path="/ordem-compra/{idOrdemCompra}/marcadores",
                source_step="purchase_orders.list",
                path_params={"idOrdemCompra": ("record_id", "id", "idOrdemCompra")},
            ),
        ),
    ),
    Workflow(
        entity_name="service_orders",
        root_step="service_orders.list",
        steps=(
            EndpointStep(
                name="service_orders.list",
                endpoint_path="/ordem-servico",
                pagination=True,
                incremental=DATE_RANGE_EMISSAO,
                record_id_keys=("id", "idOrdemServico"),
            ),
            EndpointStep(
                name="service_orders.detail",
                endpoint_path="/ordem-servico/{idOrdemServico}",
                source_step="service_orders.list",
                path_params={"idOrdemServico": ("record_id", "id", "idOrdemServico")},
                record_id_keys=("id", "idOrdemServico"),
                singleton=True,
            ),
            EndpointStep(
                name="service_orders.markers",
                endpoint_path="/ordem-servico/{idOrdemServico}/marcadores",
                source_step="service_orders.list",
                path_params={"idOrdemServico": ("record_id", "id", "idOrdemServico")},
            ),
        ),
    ),
)


WORKFLOW_BY_ENTITY = {workflow.entity_name: workflow for workflow in WORKFLOWS}
