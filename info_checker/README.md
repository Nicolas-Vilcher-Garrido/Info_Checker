# info_checker

Um esqueleto de *verificador de informações* em Python, com coletores plugáveis:
- HTTP (`requests` + `BeautifulSoup`)
- Browser real (`playwright`) — opcional
- Desktop (`pyautogui`) — opcional

## Requisitos

- Python 3.10+
- `pip install -r requirements.txt`

### requirements.txt sugerido
```
requests
beautifulsoup4
pyyaml
# opcionais:
# playwright
# pyautogui
# pytesseract
# python -m info_checker.main -c C:\Users\Nicolas\Desktop\info_checker\config.yaml
```

## Como rodar

1. Ajuste `config.yaml` (fonte, estratégia de extração e regras).
2. Execute:
```
python -m info_checker.main
```
ou, dentro da pasta do projeto:
```
python main.py
```

## Estrutura

- `core/` modelos, runner e validadores.
- `collectors/` estratégias de coleta (HTTP, Playwright, Desktop).
- `utils/` utilitários (logging/parsing).
- `tests/` testes com `pytest` (exemplo simples).

## Extensões comuns

- Adicionar *login/fluxos* no coletor Playwright via `request.extra`.
- Implementar `desktop` com OCR (p. ex., `pytesseract`) ou `pywinauto`.
- Criar novos validadores (por exemplo, `jsonpath`, `date_before`, etc.).
