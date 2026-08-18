import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select

from leadminer.config import get_settings
from leadminer.crawler.service import crawl_company_ids
from leadminer.database import SessionLocal, create_database
from leadminer.models import Company
from leadminer.services.domains import normalize_domain
from leadminer.services.importer import import_companies, parse_company_csv

app = typer.Typer(help="VoyageAge Lead Miner internal operations CLI.", no_args_is_help=True)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@app.command("init-db")
def init_db() -> None:
    """Create local database tables."""
    create_database()
    typer.echo("Database initialized.")


@app.command("import")
def import_csv(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Import and deduplicate companies from a UTF-8 CSV file."""
    create_database()
    items = parse_company_csv(path.read_bytes())
    with SessionLocal() as session:
        result = import_companies(session, items)
    typer.echo(
        f"created={result.created} existing={result.existing} "
        f"sources_added={result.sources_added} errors={len(result.errors)}"
    )
    for error in result.errors:
        typer.echo(f"row={error.row} value={error.value!r} error={error.message}", err=True)


@app.command()
def serve(reload: bool = typer.Option(False, help="Reload on source changes.")) -> None:
    """Run the FastAPI development server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "leadminer.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=reload,
    )


@app.command()
def crawl(
    target: Annotated[str | None, typer.Argument(help="Company domain or website.")] = None,
    company_id: Annotated[int | None, typer.Option("--company-id")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    max_pages: Annotated[int | None, typer.Option("--max-pages", min=1, max=50)] = None,
) -> None:
    """Crawl one imported company by domain or database ID."""
    create_database()
    if company_id is None and target is None:
        raise typer.BadParameter("Provide a domain or --company-id")
    with SessionLocal() as session:
        if company_id is None:
            domain = normalize_domain(target or "")
            company_id = session.scalar(select(Company.id).where(Company.domain == domain))
        if company_id is None or session.get(Company, company_id) is None:
            raise typer.BadParameter("Company is not imported")
    settings = get_settings()
    if max_pages is not None:
        settings = settings.model_copy(update={"crawler_max_pages_per_domain": max_pages})
    _configure_logging()
    report = asyncio.run(
        crawl_company_ids([company_id], force=force, concurrency=1, settings=settings)
    )[0]
    _print_report(report)


@app.command("crawl-all")
def crawl_all(
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 20,
    force: Annotated[bool, typer.Option("--force")] = False,
    concurrency: Annotated[int | None, typer.Option("--concurrency", min=1, max=20)] = None,
    max_pages: Annotated[int | None, typer.Option("--max-pages", min=1, max=50)] = None,
) -> None:
    """Crawl a bounded batch of imported companies."""
    create_database()
    with SessionLocal() as session:
        company_ids = list(
            session.scalars(
                select(Company.id)
                .order_by(Company.last_crawled_at.asc().nulls_first(), Company.created_at)
                .limit(limit)
            )
        )
    settings = get_settings()
    if max_pages is not None:
        settings = settings.model_copy(update={"crawler_max_pages_per_domain": max_pages})
    _configure_logging()
    reports = asyncio.run(
        crawl_company_ids(company_ids, force=force, concurrency=concurrency, settings=settings)
    )
    for report in reports:
        _print_report(report)


def _print_report(report) -> None:
    typer.echo(
        f"domain={report.domain} status={report.status.value} pages={report.pages_crawled} "
        f"failed={report.pages_failed} strong={report.strong_signals} weak={report.weak_signals} "
        f"providers={','.join(report.providers) or '-'} models={','.join(report.models) or '-'} "
        f"errors={len(report.errors)}"
    )
