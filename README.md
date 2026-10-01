# 🛠️ Gerenciador de Duplicidades PostgreSQL (`dedup-pedidos`)

CLI interativa para diagnóstico, simulação e deduplicação transacional de pedidos em bases de dados PostgreSQL. O projeto conta com suporte nativo a relatórios detalhados com comparativo de itens (`item_pedido`), controle para pular registros manuais e compatibilidade total com **Linux, macOS e Windows**.

---

## 📋 Pré-requisitos

- **Python 3.12** ou superior
- **uv** (Gerenciador de pacotes e ambientes Python de alta performance)
- Acesso a um servidor **PostgreSQL** com permissões de leitura e escrita nas bases alvo.

---

## ⚙️ Preparação do Ambiente

### 1. Clonar o Repositório

```bash
git clone [https://github.com/khalegjr/dedup-pedidos.git](https://github.com/khalegjr/dedup-pedidos.git)
cd dedup-pedidos
```

### 2. Sincronizar Dependências com o uv

Execute o comando abaixo na raiz do projeto para criar o ambiente virtual e instalar todas as dependências do projeto (incluindo o suporte para relatórios em PDF):

```bash
uv sync
```

### 🎛️ 3. Configuração de Variáveis de Ambiente

A aplicação busca as credenciais do servidor PostgreSQL a partir de variáveis de ambiente. Você pode exportá-las no seu terminal ou criar um arquivo .env na raiz do projeto:

Exemplo de Configuração:
Linux / macOS (Terminal):

```bash
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_USER="postgres"
export DB_PASSWORD="sua_senha_aqui"
export DEFAULT_DB="postgres"
```

Windows (PowerShell):

```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="5432"
$env:DB_USER="postgres"
$env:DB_PASSWORD="sua_senha_aqui"
$env:DEFAULT_DB="postgres"
```

Windows (CMD):

```dos
set DB_HOST=localhost
set DB_PORT=5432
set DB_USER=postgres
set DB_PASSWORD=sua_senha_aqui
set DEFAULT_DB=postgres
```

**Hierarquia de Precedência:**
Mais alta: `export DB_HOST="192.168.1.50"` (Variável enviada explicitamente via shell/terminal).

Média:`DB_HOST=10.0.0.1` (Definida dentro do arquivo .env).

Mais baixa (Fallback): `"localhost"` (Valor padrão definido no segundo argumento do os.getenv).

### 🚀 Como Executar a Aplicação

Para iniciar o assistente interativo da CLI, execute:

```Bash
uv run dedup-app
```

### 🔄 4. Fluxo de Funcionamento e Recursos

Varredura e Diagnóstico:
A CLI analisa automaticamente todas as bases de dados ativas do servidor buscando registros duplicados na tabela pedido agrupados por numero_pedido e filial.

Modos de Execução:

auto_simulacao: Roda o algoritmo de prioridade, gera os logs comparativos de exclusão/manutenção e faz o rollback transacional (nada é alterado no BD).

auto_efetivo: Modifica as chaves estrangeiras (item_relacionado, log_associacao, etc.), exclui os cabeçalhos/itens duplicados e confirma a alteração via commit.

manual: Permite selecionar interativamente qual ID preservar em cada grupo.

Opção de Pular (Ação Manual):
Durante a seleção manual, você pode digitar pular para ignorar o registro atual e seguir em frente. Todos os itens pulados serão agrupados ao final.

Relatórios e Exportação:
Após a execução, escolha o formato do relatório:

tela: Exibe as tabelas formatadas diretamente no terminal.

csv: Exporta o comparativo em formato CSV.

pdf: Gera um arquivo PDF formatado com o detalhamento dos itens.

Local de salvamento: Você pode aceitar o diretório padrão (raiz do projeto) ou digitar qualquer caminho customizado (ex: /home/user/documentos ou C:\Relatorios). A aplicação adicionará e formatará a extensão do arquivo automaticamente.

Local de salvamento: Você pode aceitar o diretório padrão (raiz do projeto) ou digitar qualquer caminho customizado (ex: /home/user/documentos ou C:\Relatorios). A aplicação adicionará e formatará a extensão do arquivo automaticamente.

### 🧪 5. Instalação Global como Ferramenta CLI (Opcional)

Se desejar executar o comando dedup-app diretamente de qualquer pasta do seu sistema operacional sem precisar navegar até o projeto:

```bash
uv tool install .
```

Agora você pode rodar em qualquer terminal:

```Bash
dedup-app
```
