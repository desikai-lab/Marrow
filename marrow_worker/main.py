import argparse
import asyncio
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.embedding import LazyEncoder
from src.parser import extract_chunks
from src.transport import MCPClient, WorkerOutbox
from src.watcher import AsyncDebouncer, SkeletonEventBridge
from watchdog.observers.polling import PollingObserver

# Directories that should never be scanned during the initial repo analysis
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "bin",
    "obj",
    "dist",
    "build",
    ".next",
    "out",
}


def setup_logging(log_file: str = "logs/worker.log", level: int = logging.INFO) -> None:
    """Configures the root logger to output to both console and a daily rotating log file."""
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    if root.hasHandlers():
        root.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=30, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.info(
        "Worker logging initialized. File target: %s | Level: %s",
        log_file,
        logging.getLevelName(level),
    )


async def extract_and_encode(filepath: str, encoder: LazyEncoder | None = None):
    """
    Pure logic: reads file, parses skeletons, and generates embeddings.
    Returns a list of dictionaries ready for transport.
    """

    path_obj = Path(filepath)
    if not path_obj.exists() or not path_obj.is_file():
        return []

    source_bytes = path_obj.read_bytes()
    ext = path_obj.suffix.lower()

    extracted_chunks = extract_chunks(source_bytes, ext)
    if not extracted_chunks:
        return []

    texts_to_embed = [c["skeleton_text"] for c in extracted_chunks]

    if encoder:
        vectors = encoder.encode(texts_to_embed)
    else:
        with LazyEncoder() as enc:
            vectors = enc.encode(texts_to_embed)

    # Attach vectors to the chunk dictionaries
    for chunk, vec in zip(extracted_chunks, vectors):
        chunk["vector"] = vec

    return extracted_chunks


async def process_file(filepath: str, api_client: MCPClient, encoder: LazyEncoder | None = None):
    """
    Orchestrator: coordinates extraction and submission.
    """
    logger = logging.getLogger("worker")
    try:
        logger.info("Analyzing %s", filepath)
        chunks = await extract_and_encode(filepath, encoder)

        if not chunks:
            return

        logger.info("Submitting %s chunks from %s to MCP Remote", len(chunks), filepath)
        # Reuse file name as summary
        file_summary = f"Summary for {os.path.basename(filepath)}"
        await api_client.send_chunks(filepath, file_summary, chunks)
        logger.info("Successfully synced: %s", filepath)

    except Exception as e:
        logger.error("Error processing %s: %s", filepath, e)


async def delete_file(filepath: str, api_client: MCPClient) -> None:
    """Symmetric to process_file. Called when a watched file is deleted or moved."""
    logger = logging.getLogger("worker")
    try:
        await api_client.delete_chunks(filepath)
        logger.info("Deleted from index: %s", filepath)
    except Exception as e:
        logger.error("Error deleting %s: %s", filepath, e)


async def initial_scan(repo_dir: str, extensions: list[str], api_client: MCPClient) -> int:
    """
    Walks the entire repo and processes every file matching `extensions`.
    Skips SKIP_DIRS to avoid indexing build artifacts, VCS internals, etc.
    Returns the total number of files submitted.
    """
    logger = logging.getLogger("worker")
    logger.info("Starting full repository scan of: %s", repo_dir)
    submitted = 0

    with LazyEncoder() as enc:
        for dirpath, dirnames, filenames in os.walk(repo_dir):
            # Prune skip directories in-place (prevents os.walk from descending)
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

            for filename in filenames:
                if any(filename.lower().endswith(ext) for ext in extensions):
                    full_path = os.path.join(dirpath, filename)
                    await process_file(full_path, api_client, encoder=enc)
                    submitted += 1

    logger.info("Scan complete — %s file(s) submitted.", submitted)
    return submitted


async def serve(
    repo_dir: str,
    target_url: str,
    extensions: list[str],
    project_name: str,
    secret_token: str,
    run_init: bool = False,
    polling_interval: float = 1.0,
):
    logger = logging.getLogger("worker")
    logger.info("Initializing Worker for %s", repo_dir)
    logger.info("Project Name: %s", project_name)
    logger.info("Target Server: %s", target_url)
    logger.info("Watching Extensions: %s", extensions)

    # --- Outbox setup ---
    outbox_path = os.getenv("WORKER_OUTBOX_PATH", "./worker_outbox.db")
    flush_interval = int(os.getenv("WORKER_FLUSH_INTERVAL_SECONDS", "60"))
    flush_concurrency = int(os.getenv("WORKER_FLUSH_CONCURRENCY", "3"))
    outbox = WorkerOutbox(
        db_path=outbox_path, flush_interval=flush_interval, flush_concurrency=flush_concurrency
    )
    await outbox.setup()

    api_client = MCPClient(
        target_url=target_url,
        project_name=project_name,
        secret_token=secret_token,
        root_dir=repo_dir,
        outbox=outbox,
    )

    # --- Flush any payloads pending from a previous run ---
    deliver_fn = api_client._make_deliver_fn()
    await outbox.flush_pending_batched(deliver_fn)

    if run_init:
        await initial_scan(repo_dir, extensions, api_client)

    # Closure to bridge the callback dependencies
    async def callback(filepath: str):
        await process_file(filepath, api_client)

    async def callback_delete(filepath: str):
        await delete_file(filepath, api_client)

    loop = asyncio.get_running_loop()
    debouncer = AsyncDebouncer(loop, callback)
    bridge = SkeletonEventBridge(loop, debouncer, extensions, delete_callback=callback_delete)

    observer = PollingObserver(timeout=polling_interval)
    observer.schedule(bridge, path=repo_dir, recursive=True)
    observer.start()

    # --- Launch background outbox flush task ---
    flush_task = asyncio.create_task(outbox.background_flush_loop(deliver_fn))

    logger.info("Worker is active. Press CTRL+C to perform a graceful shutdown.")

    try:
        # Keep the event loop alive forever
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        # Graceful cleanup
        logger.info("Shutting down outbox flush task.")
        flush_task.cancel()
        try:
            await flush_task
        except asyncio.CancelledError:
            pass

        logger.info("Shutting down directory observer.")
        observer.stop()
        observer.join()

        logger.info("Closing network connections.")
        await api_client.close()
        await outbox.close()
        logger.info("Worker safely terminated.")


def main():
    parser = argparse.ArgumentParser(description="Marrow Worker Application Monitor")
    parser.add_argument(
        "--repo-dir",
        type=str,
        default=os.getcwd(),
        help="Absolute or relative path to the codebase to monitor",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="DefaultProject",
        help="Project identifier for the remote MCP server (e.g. 'YourProject')",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default="http://localhost:8000",
        help="Root URL for the remote Vectorizer Transport Server",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        default=".cs,.ts,.py",
        help="Comma-separated list of file extensions",
    )
    parser.add_argument(
        "--secret-token",
        type=str,
        default=os.getenv("MCP_SECRET_TOKEN", ""),
        help="Bearer token for marrow_server authentication (or set MCP_SECRET_TOKEN env var)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Scan and index the entire repo before starting the file watcher",
    )
    parser.add_argument(
        "--polling-interval",
        type=float,
        default=float(os.getenv("POLLING_INTERVAL", "1.0")),
        help="File system polling interval in seconds (default: 1.0). "
        "Lower values increase responsiveness but raise CPU usage on large repos. "
        "Can also be set via POLLING_INTERVAL env var.",
    )

    args = parser.parse_args()

    # Initialize persistent logging before anything else
    _log_level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO").upper())
    if not isinstance(_log_level, int):
        _log_level = logging.INFO
    setup_logging(level=_log_level)

    logger = logging.getLogger("worker")
    if not args.secret_token:
        logger.warning(
            "--secret-token not provided and MCP_SECRET_TOKEN env var is unset. "
            "Requests to /api/vectorize will be rejected with 401."
        )

    extension_list = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]

    try:
        asyncio.run(
            serve(
                args.repo_dir,
                args.target_url,
                extension_list,
                args.project_name,
                args.secret_token,
                run_init=args.init,
                polling_interval=args.polling_interval,
            )
        )
    except KeyboardInterrupt:
        # Captured from standard shell Ctrl+C sequence
        pass


if __name__ == "__main__":
    main()
