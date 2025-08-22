# Info Checker

Este projeto é uma ferramenta de automação para extrair dados de relatórios do Power BI a partir de uma plataforma web. Ele utiliza o Playwright para simular o acesso de um usuário, fazer o login, navegar até os relatórios e exportar os dados para uma pasta chamada "exports".

## Funcionalidades

* **Automação de Login:** Acessa uma URL de login, preenche as credenciais de usuário e senha, e autentica na plataforma.
* **Navegação Inteligente:** Navega para a página do relatório do Power BI após o login bem-sucedido.
* **Extração de Dados:** Identifica e interage com as tabelas de dados em diferentes abas do relatório.
* **Exportação:** Salva os dados de cada aba em arquivos CSV e os consolida em uma única planilha Excel.
* **Configurável:** Permite ajustar URLs, credenciais, abas para extrair e opções de exportação através de um arquivo de configuração (`config.yaml`).

## Pré-requisitos

Para rodar este projeto, você precisa ter o Python instalado. Depois, instale as bibliotecas necessárias.

```bash
pip install -r info_checker/requirements.txt

O script utiliza o playwright e os seus navegadores. Instale-os com o seguinte comando:

Bash

python -m playwright install
