# Bybit Trade Analyzer - Dashboard de Análise de Performance

Este é um dashboard web interativo construído em Python com Flask e Plotly, projetado para analisar o histórico de trades de uma conta de trading unificada (Unified Trading Account) da Bybit. A ferramenta permite que traders e desenvolvedores de bots visualizem métricas de performance cruciais, identifiquem os pares mais e menos lucrativos, e gerenciem uma blacklist de ativos para otimizar estratégias de trading.

A aplicação é totalmente interativa, buscando dados diretamente da API da Bybit em tempo real e permitindo simulações de resultados sem os pares de baixo desempenho.

![Exemplo do Dashboard](https://i.imgur.com/URL_DA_SUA_IMAGEM_AQUI.png ) 
*(Sugestão: Tire um print da sua aplicação rodando e substitua o link acima para ter uma imagem real no seu README)*

---

## ✨ Funcionalidades Principais

-   **Dashboard Interativo:** Interface web moderna e responsiva construída com Flask e um design limpo.
-   **Coleta de Dados em Tempo Real:** Conecta-se à API V5 da Bybit para buscar o histórico completo de execuções e trades no período especificado.
-   **Métricas de Performance (KPIs):**
    -   **PnL de Trades (USDT):** Lucro ou prejuízo líquido total, considerando apenas as operações fechadas.
    -   **Custo Total (Margem):** Soma de toda a margem alocada para abrir as posições, medindo o capital total arriscado.
    -   **Taxa de Acerto:** Percentual de operações que fecharam com lucro.
    -   **ROI Agregado Total:** Retorno sobre o investimento, calculado sobre o custo total da margem.
    -   **Total de Trades:** Número total de operações fechadas no período.
-   **Rankings Detalhados:**
    -   **Ranking de Ganhadores:** Lista de pares que geraram lucro, ordenados pelo maior PnL.
    -   **Ranking de Perdedores:** Lista de pares que geraram prejuízo, ordenados pelo maior prejuízo.
    -   **Resumo por Tipo de Saída:** Agrupa os resultados por `StopLoss`, `TakeProfit`, `TrailingStop` e `Parcial` (fechamentos manuais/pelo bot).
-   **Tabelas Ordenáveis:** Todas as colunas das tabelas de ranking podem ser ordenadas de forma ascendente ou descendente.
-   **Drill-Down de Trades:** Clique em qualquer par para abrir uma nova aba com a lista detalhada de todos os trades daquele ativo, incluindo duração, PnL, ROI e custo de cada operação.
-   **Gerenciamento de Blacklist:**
    -   **Banir Pares:** Adicione pares de baixo desempenho a uma blacklist diretamente pela interface, sem recarregar a página.
    -   **Simulação de Resultados:** Recalcule toda a análise excluindo os pares da blacklist para simular qual teria sido o seu desempenho.
    -   **Gerenciamento Centralizado:** Uma seção na barra lateral permite visualizar e remover pares da blacklist.
-   **Interface Persistente:** A análise e a blacklist são mantidas na sessão, permitindo que você mude as datas e recalcule os dados sem precisar inserir as credenciais novamente.

---

## 🛠️ Estrutura do Projeto

O projeto foi modularizado para facilitar a manutenção e futuras expansões:

-   `app.py`: O servidor web principal (Flask). Controla as rotas, a lógica da sessão e a renderização dos templates.
-   `bybit_client.py`: Responsável por toda a comunicação com a API da Bybit.
-   `analysis.py`: Contém toda a lógica de processamento e análise dos dados brutos dos trades.
-   `templates/`: Pasta que contém os arquivos HTML.
    -   `layout.html`: A estrutura base da página (cabeçalho, barra lateral).
    -   `dashboard.html`: A página principal que herda do layout e contém a lógica das abas e tabelas.
    -   `trades_detail.html`: A página que mostra os detalhes de um par específico.
    -   `partials/results.html`: Um template parcial que é renderizado dinamicamente via JavaScript para atualizar os resultados sem recarregar a página.
-   `requirements.txt`: Lista de todas as dependências Python do projeto.
-   `Dockerfile`: Arquivo de configuração para construir a imagem Docker e facilitar a implantação.

---

## 🚀 Como Executar o Projeto

### Pré-requisitos

-   Python 3.9 ou superior
-   Docker (opcional, para implantação)
-   Uma conta na Bybit com chaves de API (API Key e API Secret) geradas.

### Configuração Local (Recomendado para Desenvolvimento)

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/seu-usuario/seu-repositorio.git
    cd seu-repositorio
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Execute a aplicação:**
    ```bash
    python app.py
    ```

5.  **Acesse o dashboard:** Abra seu navegador e vá para `http://localhost:5001`.

### Execução com Docker

1.  **Construa a imagem Docker:**
    ```bash
    docker build -t bybit-dashboard .
    ```

2.  **Execute o contêiner:**
    ```bash
    docker run --name bybit-app -d -p 5001:5001 bybit-dashboard
    ```
    -   O contêiner rodará em segundo plano. Para ver os logs, use `docker logs bybit-app`.

3.  **Acesse o dashboard:** Abra seu navegador e vá para `http://localhost:5001`.

---

## 📈 Como Usar a Interface

1.  **Preencha os Controles:** Na barra lateral esquerda, insira o nome da conta (opcional ), suas credenciais da API da Bybit, a alavancagem usada e o período de análise.
2.  **Analise:** Clique em "Analisar Trades". Os resultados serão carregados na área principal.
3.  **Explore os Dados:**
    -   Navegue entre as abas "Ganhadores", "Perdedores" e "Por Saída".
    -   Ordene as tabelas clicando nos cabeçalhos das colunas.
    -   Clique no nome de um par para ver o detalhe de cada trade em uma nova aba.
4.  **Gerencie a Blacklist:**
    -   Use o menu de "Ações" (⋮) em qualquer par para adicioná-lo à blacklist.
    -   A lista de pares banidos aparecerá na barra lateral.
    -   Clique em "Recalcular Análise sem Pares da Blacklist" para simular os resultados.
    -   Clique em "Permitir" para remover um par da blacklist.
5.  **Nova Análise:** Para analisar um novo período ou conta, clique em "Sair / Nova Análise" no canto superior direito.
