"""
Rich Interactive CLI for Sentinel: Run, Inspect, and Human-in-the-Loop Review.
"""

import argparse
import sys
import uuid
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from sentinel.graph import build_sentinel_graph

console = Console()


def print_banner() -> None:
    """Render Sentinel header banner."""
    console.print(
        Panel.fit(
            "[bold cyan]🛡️  SENTINEL[/bold cyan] : [bold white]An Eval-First Code Patch Agent with HITL Approval[/bold white]\n"
            "[dim]Bounded Repair Loops • Network-Isolated Docker Sandbox • Durable Postgres Checkpoints[/dim]",
            border_style="cyan",
        )
    )


def render_evaluation_card(eval_report: dict[str, Any]) -> None:
    """Render rich evaluation summary table."""
    table = Table(title="📊 Evaluation Scorecard", header_style="bold magenta", border_style="dim")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold green")
    table.add_column("Details", style="white")

    score = eval_report.get("overall_score", 0.0)
    score_color = "green" if score >= 0.8 else ("yellow" if score >= 0.5 else "red")
    table.add_row("Composite Score", f"[{score_color}]{score:.2f} / 1.00[/{score_color}]", "Weighted quality score")

    test_passed = eval_report.get("test_pass_rate", 0.0) == 1.0
    table.add_row(
        "Test Suite",
        "✅ PASSED" if test_passed else "❌ FAILED",
        f"Pass rate: {eval_report.get('test_pass_rate', 0.0) * 100:.1f}%",
    )

    loc_added = eval_report.get("loc_added", 0)
    loc_deleted = eval_report.get("loc_deleted", 0)
    files = eval_report.get("files_touched", [])
    table.add_row(
        "Blast Radius",
        f"+{loc_added} / -{loc_deleted} LOC",
        f"{len(files)} file(s): {', '.join(files) if files else 'None'}",
    )

    lint_passed = eval_report.get("lint_passed", True)
    violations = eval_report.get("lint_violations", [])
    table.add_row(
        "Static Analysis",
        "✅ Clean" if lint_passed else "⚠️ Violations",
        f"{len(violations)} violation(s)" if violations else "Syntax & style validated",
    )

    console.print(table)


def render_diff(patch_diff: str) -> None:
    """Render unified diff with syntax highlighting."""
    console.print("\n[bold yellow]📄 Proposed Unified Diff Patch:[/bold yellow]")
    syntax = Syntax(patch_diff, "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, border_style="yellow"))


def run_pipeline(repo_name: str, issue_number: int, repo_path: str = ".") -> None:
    """Execute Sentinel on target issue with interactive Human Gate pausing and resumption."""
    print_banner()

    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": f"issue-{issue_number}-{thread_id}"}}

    initial_state = {
        "repo_name": repo_name,
        "repo_path": repo_path,
        "issue_number": issue_number,
        "issue_title": f"Issue #{issue_number}",
        "issue_body": "",
    }

    console.print(f"[bold green]Starting Sentinel execution thread:[/bold green] [cyan]{config['configurable']['thread_id']}[/cyan]\n")
    graph = build_sentinel_graph()

    # Stream execution until interrupt or completion
    for event in graph.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            console.print(f"  [dim]✔ Completed node:[/dim] [bold blue]{node_name.upper()}[/bold blue]")

    # Check state after pausing
    current_snapshot = graph.get_state(config)
    state_values = current_snapshot.values

    # Check if graph paused at human_gate
    if current_snapshot.next and "human_gate" in current_snapshot.next:
        console.print("\n" + "=" * 70)
        console.print("[bold red]⏸️  PAUSED AT HUMAN APPROVAL GATE[/bold red]")
        console.print("=" * 70 + "\n")

        eval_report = state_values.get("eval_report") or {}
        patch_diff = state_values.get("current_patch") or ""

        render_evaluation_card(eval_report)
        render_diff(patch_diff)

        console.print("\n[bold cyan]Sentinel requires human review before opening a draft pull request.[/bold cyan]")
        choice = console.input("[bold yellow]Approve this patch? [y/N]: [/bold yellow]").strip().lower()

        approved = choice in ("y", "yes")
        reviewer = console.input("[dim]Reviewer Name (default: human_reviewer): [/dim]").strip() or "human_reviewer"
        feedback = console.input("[dim]Optional Feedback: [/dim]").strip()

        # Resume graph with human decision
        resume_payload = {
            "approved": approved,
            "reviewer": reviewer,
            "feedback": feedback or ("Approved" if approved else "Rejected by user"),
        }

        console.print(f"\n[bold green]Resuming thread {config['configurable']['thread_id']}...[/bold green]")
        for event in graph.stream(Command(resume=resume_payload), config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                console.print(f"  [dim]✔ Completed node:[/dim] [bold blue]{node_name.upper()}[/bold blue]")

    # Final Summary
    final_snapshot = graph.get_state(config)
    final_state = final_snapshot.values
    final_status = final_state.get("status")

    if final_status == "committed":
        pr_info = final_state.get("pr_result", {})
        console.print(
            Panel(
                f"[bold green]🎉 Draft Pull Request Opened Successfully![/bold green]\n"
                f"PR URL: [link={pr_info.get('pr_url')}]{pr_info.get('pr_url')}[/link]\n"
                f"Branch: [cyan]{pr_info.get('branch_name')}[/cyan]",
                border_style="green",
            )
        )
    elif final_status == "rejected":
        console.print(
            Panel(
                f"[bold yellow]✋ Patch Rejected by Human Reviewer[/bold yellow]\n"
                f"Reason: {final_state.get('error_message') or 'Reviewer declined proposal.'}",
                border_style="yellow",
            )
        )
    elif final_status == "escalated":
        console.print(
            Panel(
                f"[bold red]🚨 Patch Escalated (Repair Cap / Cycle Detected)[/bold red]\n"
                f"Details: {final_state.get('error_message')}",
                border_style="red",
            )
        )


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Sentinel: Code Patch Proposal Agent")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run Sentinel on a GitHub issue")
    run_parser.add_argument("--repo", type=str, required=True, help="Target repository (e.g. owner/repo)")
    run_parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    run_parser.add_argument("--path", type=str, default=".", help="Local repository path")

    args = parser.parse_args()
    if args.command == "run":
        run_pipeline(args.repo, args.issue, args.path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
