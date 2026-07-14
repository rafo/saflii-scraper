"""Sync a local folder of scraped PDFs into a RAGFlow dataset.

The local folder (usually a subtree of the pdf/ collection) is the source
of truth. For each PDF, the neutral citation in the filename (e.g.
"[2024] ZAWCHC 147") is the stable key:

- file exists locally but not in RAGFlow, citation unknown there
    -> upload (+ trigger parsing)
- citation exists in RAGFlow under an outdated name (SAFLII corrected
  the title)
    -> rename the RAGFlow document; content is identical, so nothing is
       re-parsed or re-embedded
- document exists in RAGFlow but not locally
    -> deleted only with --delete (off by default)

Usage:
    export RAGFLOW_API_KEY=ragflow-...   # RAGFlow UI -> avatar -> API
    uv run python ragflow_sync.py <local_dir> <dataset_name>            # dry run
    uv run python ragflow_sync.py <local_dir> <dataset_name> --apply
    uv run python ragflow_sync.py ... --apply --delete                  # also remove orphans

Example:
    uv run python ragflow_sync.py \\
        "/Volumes/data/Work/RE3_scraper_saflii_data/pdf/za/cases/ZAWCHC" \\
        "SA Case Law ZAWCHC" --apply
"""

import argparse
import logging
import os
import sys

from ragflow_sdk import RAGFlow

from saflii_utils import CITATION_PATTERN

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1"
UPLOAD_BATCH_SIZE = 8
LIST_PAGE_SIZE = 100


def collect_local_pdfs(local_dir):
    """Map filename -> absolute path for every PDF under local_dir."""
    pdfs = {}
    for dirpath, _dirnames, filenames in os.walk(local_dir):
        for name in filenames:
            if not name.lower().endswith(".pdf"):
                continue
            if name in pdfs:
                log.warning(f"Duplicate filename in different folders, skipping: {name}")
                continue
            pdfs[name] = os.path.join(dirpath, name)
    return pdfs


def citation_of(name):
    match = CITATION_PATTERN.search(name)
    return match.group(0) if match else None


def get_dataset(rag, name, apply_changes):
    # No server-side name filter: RAGFlow answers with a permission error
    # (instead of an empty list) when no dataset matches the name.
    page = 1
    while True:
        batch = rag.list_datasets(page=page, page_size=LIST_PAGE_SIZE)
        for dataset in batch:
            if dataset.name == name:
                return dataset
        if len(batch) < LIST_PAGE_SIZE:
            break
        page += 1
    if not apply_changes:
        log.info(f"Dataset '{name}' does not exist yet (would be created).")
        return None
    log.info(f"Creating dataset '{name}'.")
    return rag.create_dataset(name=name)


def list_remote_documents(dataset):
    documents = []
    page = 1
    while True:
        batch = dataset.list_documents(page=page, page_size=LIST_PAGE_SIZE)
        documents.extend(batch)
        if len(batch) < LIST_PAGE_SIZE:
            return documents
        page += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local_dir", help="folder with PDFs (searched recursively)")
    parser.add_argument("dataset_name", help="RAGFlow dataset (created if missing)")
    parser.add_argument("--apply", action="store_true", help="perform changes (default: dry run)")
    parser.add_argument("--delete", action="store_true", help="delete RAGFlow documents that no longer exist locally")
    parser.add_argument("--no-parse", action="store_true", help="skip triggering parsing after upload")
    parser.add_argument("--base-url", default=os.environ.get("RAGFLOW_BASE_URL", DEFAULT_BASE_URL))
    args = parser.parse_args()

    api_key = os.environ.get("RAGFLOW_API_KEY")
    if not api_key:
        log.error("RAGFLOW_API_KEY is not set (RAGFlow UI -> avatar menu -> API -> API key).")
        sys.exit(1)
    if not os.path.isdir(args.local_dir):
        log.error(f"Local folder not found: {args.local_dir}")
        sys.exit(1)

    local = collect_local_pdfs(args.local_dir)
    log.info(f"{len(local)} local PDFs under {args.local_dir}")

    rag = RAGFlow(api_key=api_key, base_url=args.base_url)
    dataset = get_dataset(rag, args.dataset_name, args.apply)
    remote_docs = list_remote_documents(dataset) if dataset else []
    log.info(f"{len(remote_docs)} documents in dataset '{args.dataset_name}'")

    remote_by_name = {doc.name: doc for doc in remote_docs}
    remote_by_citation = {}
    for doc in remote_docs:
        cit = citation_of(doc.name)
        if cit:
            remote_by_citation.setdefault(cit, doc)

    to_upload, to_rename = [], []
    for name, path in sorted(local.items()):
        if name in remote_by_name:
            continue
        cit = citation_of(name)
        doc = remote_by_citation.get(cit) if cit else None
        if doc and doc.name not in local:
            to_rename.append((doc, name))
        else:
            to_upload.append((name, path))

    local_citations = {citation_of(n) for n in local}
    renamed_ids = {doc.id for doc, _ in to_rename}
    to_delete = [
        doc
        for doc in remote_docs
        if doc.name not in local
        and doc.id not in renamed_ids
        and citation_of(doc.name) not in local_citations
    ]

    log.info(f"Plan: {len(to_upload)} upload, {len(to_rename)} rename, {len(to_delete)} orphan(s)")

    for doc, new_name in to_rename:
        log.info(f"RENAME: {doc.name}\n     -> {new_name}")
        if args.apply:
            doc.update({"name": new_name})

    for doc in to_delete:
        log.info(f"ORPHAN{' (use --delete to remove)' if not args.delete else ''}: {doc.name}")
    if args.apply and args.delete and to_delete:
        dataset.delete_documents(ids=[doc.id for doc in to_delete])
        log.info(f"{len(to_delete)} orphan(s) deleted.")

    uploaded_ids = []
    for i in range(0, len(to_upload), UPLOAD_BATCH_SIZE):
        batch = to_upload[i : i + UPLOAD_BATCH_SIZE]
        for name, _path in batch:
            log.info(f"UPLOAD: {name}")
        if args.apply:
            payload = []
            for name, path in batch:
                with open(path, "rb") as fh:
                    payload.append({"display_name": name, "blob": fh.read()})
            uploaded_ids.extend(doc.id for doc in dataset.upload_documents(payload))

    if args.apply and uploaded_ids and not args.no_parse:
        dataset.async_parse_documents(uploaded_ids)
        log.info(f"Parsing triggered for {len(uploaded_ids)} new document(s).")

    if not args.apply:
        log.info("Dry run only — re-run with --apply to perform these changes.")


if __name__ == "__main__":
    main()
