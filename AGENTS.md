# Repository Guidelines

## Project Structure & Module Organization
- `main.py` runs a targeted BeautifulSoup crawler that imports `process_saflii_page` from `saflii_utils.py` and writes to the directory defined by `BASE_DATA_DIR`.
- `saflii_processor_yearly.py` drives the full site crawl (databases → courts → years → documents) and prompts for `FILTER_COURT`, `FILTER_YEAR`, and format choices at startup.
- `saflii_utils.py` hosts URL parsing, filename generation, and HTML persistence helpers; keep it free of network calls so both crawlers can reuse it.
- Runtime artefacts land in `saflii_data/` (document exports) and `storage/` (Crawlee request queues, key-value stores); clean these consciously, not with blanket deletes.
- `docker-compose.yml` bootstraps the optional Kotaemon review stack; keep external volume paths in sync with local infrastructure before editing.

## Build, Test, and Development Commands
- `uv sync` installs Python 3.13 dependencies defined in `pyproject.toml` and `uv.lock`.
- `uv run python main.py` executes the targeted crawler (adjust court/year constants before running).
- `uv run python saflii_processor_yearly.py` performs the multi-format crawl; answer the startup prompts to narrow scope when testing changes.
- `docker-compose up -d` starts the Kotaemon service for document triage; use `docker-compose down` when finished to avoid orphaned containers.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, descriptive snake_case for functions, and uppercase constants such as `BASE_DATA_DIR`.
- Prefer explicit async functions and `await` over synchronous helpers inside crawler handlers to avoid blocking the event loop.
- Use the standard `logging` module (module-level logger or `logging.getLogger(__name__)`) instead of print statements for diagnostics.
- Keep filenames derived from titles filesystem-safe by reusing `generate_filename_from_title` and sanitising additional characters when adding formats.

## Testing Guidelines
- No automated test suite exists yet; add focused tests under `tests/` (pytest is preferred) when introducing new parsing or storage logic.
- For manual smoke tests, crawl a narrow slice (e.g., set `year_str = "2024"` and limit request counts) and confirm the expected files appear under `saflii_data/COURT/YEAR/`.
- Validate new download formats by checking both presence and readability of saved files, and watch the logs for skipped or retried URLs.

## Commit & Pull Request Guidelines
- Match the repository history by using imperative, descriptive commit subjects (e.g., `Add multi-format download handling`) and supply context in the body when the diff is non-trivial.
- Summarise behaviour changes, list manual crawl commands you executed, and link related issues in pull requests; include sample output paths or log excerpts when they clarify the impact.
- Ensure large data folders remain untracked in commits, and call out any migrations to `BASE_DATA_DIR` so reviewers know to relocate existing artefacts.
