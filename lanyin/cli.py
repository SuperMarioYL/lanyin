"""LanYin CLI — turn a serialized WeChat column into a voice-locked, chapter-structured, subscribable audio series.

Commands:
  init          scaffold lanyin.toml for a new column
  voice lock    clone/lock a MiniMax-H3 voice into .lanyin/voice-lock.json   (m1)
  voice show    print the locked column voice profile                         (m1)
  add           register an episode; ## headings become chapter marks         (pure)
  build         synthesize an episode in the locked voice (m2 — roadmap)
  export rss    emit 小宇宙/喜马拉雅-compliant RSS (m3 — roadmap)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__, chapter, export_rss, synth, voice_lock
from .config import (
    ConfigError,
    episodes_path,
    init_config,
    load_config,
    load_episodes,
    lock_path,
    save_episodes,
)
from .models import ColumnVoiceLock

app = typer.Typer(
    name="lanyin",
    help="栏音 — turn a serialized WeChat column into a voice-locked audio series.",
    no_args_is_help=True,
    add_completion=False,
)
voice_app = typer.Typer(name="voice", help="Column-level voice lock (m1).")
export_app = typer.Typer(name="export", help="Platform export (m3).")
app.add_typer(voice_app, name="voice")
app.add_typer(export_app, name="export")

console = Console()
err = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"lanyin {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the lanyin version and exit.",
    ),
) -> None:
    """栏音 (LanYin) — the voice-lock skill for serialized WeChat columns."""


# --- m1: init ---------------------------------------------------------------


@app.command("init")
def init_cmd(
    column_name: str = typer.Argument(..., help="Human-readable column name, e.g. '硅谷早茶'."),
    platform: str = typer.Option("xiaoyuzhou", "--platform", "-p", help="xiaoyuzhou | ximalaya"),
    heading_level: int = typer.Option(2, "--heading-level", help="Markdown heading level that marks a chapter (## = 2)."),
) -> None:
    """Scaffold ``lanyin.toml`` for a new column."""
    cfg = init_config(
        column_name,
        chapter_heading_level=heading_level,
        platform_target=platform,
    )
    console.print(
        Panel.fit(
            f"[bold]column_id[/bold]      {cfg.column_id}\n"
            f"[bold]column_name[/bold]    {cfg.column_name}\n"
            f"[bold]heading_level[/bold]  {cfg.chapter_heading_level}\n"
            f"[bold]platform[/bold]       {cfg.platform_target}\n"
            f"[bold]config[/bold]          {Path('lanyin.toml').resolve()}",
            title="lanyin init — done",
            border_style="magenta",
        )
    )
    console.print(
        "\nNext: [cyan]lanyin voice lock --sample ./voice.mp3 --name \"作者签名音色\"[/cyan]"
        "  (needs MINIMAX_API_KEY)"
    )


# --- m1: voice lock + show --------------------------------------------------


@voice_app.command("lock")
def voice_lock_cmd(
    sample: Path = typer.Option(..., "--sample", "-s", exists=True, dir_okay=False,
                               help="Audio sample (mp3/wav) to clone the voice from."),
    name: str = typer.Option(..., "--name", "-n", help="Locked voice label, e.g. '作者签名音色'."),
) -> None:
    """Clone a MiniMax-H3 voice and persist the column lock (m1)."""
    try:
        lock = voice_lock.lock_voice(sample, name=name)
    except (voice_lock.VoiceLockError, ConfigError) as exc:
        err.print(f"[red]voice lock failed:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(
        Panel.fit(
            f"[bold]column_id[/bold]    {lock.column_id}\n"
            f"[bold]voice_id[/bold]     {lock.voice_id}\n"
            f"[bold]voice_prompt[/bold] {lock.voice_prompt}\n"
            f"[bold]locked_at[/bold]    {lock.locked_at.isoformat()}\n"
            f"[bold]lock file[/bold]    {lock_path()}",
            title="voice locked — m1",
            border_style="green",
        )
    )
    console.print("\nNow every episode built in this column reuses this voice_id.")


@voice_app.command("show")
def voice_show_cmd() -> None:
    """Print the locked column voice profile (m1)."""
    lock = voice_lock.load_lock()
    if lock is None:
        err.print(
            f"[yellow]no voice lock found at {lock_path()}[/yellow]\n"
            "Run [cyan]lanyin voice lock --sample ./voice.mp3 --name \"签名音色\"[/cyan] first."
        )
        raise typer.Exit(code=1)
    row = voice_lock.show_lock(lock)
    table = Table(title="column voice lock", show_header=True, header_style="bold magenta")
    table.add_column("field")
    table.add_column("value")
    for key, val in row.items():
        table.add_row(key, str(val))
    console.print(table)


# --- pure: add (register episode + chapter preview) -------------------------


@app.command("add")
def add_cmd(
    source: Path = typer.Argument(..., exists=True, dir_okay=False,
                                   help="A .md file (or paste a column episode as markdown)."),
) -> None:
    """Register an episode; ``##`` headings become chapter marks (pure)."""
    try:
        cfg = load_config()
    except ConfigError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    if cfg is None:
        err.print("[red]no lanyin.toml here — run `lanyin init <name>` first.[/red]")
        raise typer.Exit(code=1)
    chapters = chapter.parse_markdown_file(source, heading_level=cfg.chapter_heading_level)
    registry = load_episodes()
    entry = {
        "source": str(source),
        "column_id": cfg.column_id,
        "chapters": [c.model_dump() for c in chapters],
    }
    # de-dup by source path
    registry = [e for e in registry if e.get("source") != str(source)]
    registry.append(entry)
    save_episodes(registry)
    console.print(
        Panel.fit(
            f"[bold]source[/bold]        {source}\n"
            f"[bold]chapters[/bold]      {len(chapters)}\n"
            f"[bold]registry[/bold]      {episodes_path()}",
            title="episode registered",
            border_style="cyan",
        )
    )
    if chapters:
        for idx, c in enumerate(chapters, 1):
            console.print(f"  [dim]ch{idx:02d}[/dim]  {c.title}")


# --- m2: build (stub) -------------------------------------------------------


@app.command("build")
def build_cmd(
    source: Optional[Path] = typer.Argument(
        None, help="A .md file to build. Omit to batch-build all registered episodes."
    ),
) -> None:
    """Synthesize an episode in the locked voice (m2 — not implemented yet)."""
    try:
        synth.synthesize_episode(source if source else ".")
    except NotImplementedError as exc:
        err.print(f"[yellow]m2 roadmap:[/yellow] {exc}")
        raise typer.Exit(code=2)


# --- m3: export rss (stub) --------------------------------------------------


@export_app.command("rss")
def export_rss_cmd(
    platform: str = typer.Option("xiaoyuzhou", "--platform", "-p", help="xiaoyuzhou | ximalaya"),
) -> None:
    """Emit 小宇宙/喜马拉雅-compliant RSS (m3 — not wired without built episodes)."""
    try:
        out = export_rss.export_series(platform)
        console.print(f"[green]wrote[/green] {out}")
    except export_rss.ExportError as exc:
        err.print(f"[yellow]m3 roadmap:[/yellow] {exc}")
        raise typer.Exit(code=2)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
