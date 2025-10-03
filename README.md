# eroha-pro

![CI](https://github.com/Eroha68/eroha-pro/actions/workflows/ci.yml/badge.svg?branch=main)

Набор экспериментов и инфраструктуры для проекта.

## Как запустить проверки локально

```bash
# создать и активировать venv (пример для Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# зависимости
pip install -r tests/requirements.txt || pip install -r requirements.txt

# линтер
ruff check .

# тесты
pytest -q
