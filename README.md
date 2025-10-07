![CI](https://github.com/Eroha68/eroha-pro/actions/workflows/ci.yml/badge.svg)

![CI](https://github.com/Eroha68/eroha-pro/actions/workflows/ci.yml/badge.svg)
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

> Бейдж берётся по адресу:  
> `https://github.com/Eroha68/eroha-pro/actions/workflows/ci.yml/badge.svg?branch=main`

---

# 2) Защитим основную ветку (чтобы в `main` попадали только «зелёные» изменения)

### Пошагово
1. **Settings** → слева **Branches**.  
2. В разделе **Branch protection rules** нажми **Add branch protection rule**.  
3. В **Branch name pattern** напиши: `main`.  
4. Отметь:
   - ✅ **Require a pull request before merging** (по желанию, но полезно)
   - ✅ **Require status checks to pass before merging**
   - В списке ниже выбери твой чек **CI** (workflow `ci.yml`)
   - (опционально) ✅ **Require conversation resolution before merging**
5. Внизу **Create**.

Теперь GitHub не даст слить в `main`, если CI «красный».

---

# 3) Мелкое улучшение workflow: кэш pip (быстрее сборки)

Это необязательно, но ускорит прогон.

### Как обновить `.github/workflows/ci.yml`
Открой файл и замени блок установки Python на такой (добавили кэш для pip):

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.10"
    cache: "pip"        # <— кэшируем зависимости pip
    cache-dependency-path: |
      requirements.txt
      tests/requirements.txt
