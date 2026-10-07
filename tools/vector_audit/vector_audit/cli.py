"""Command-line interface for the S3 Vectors filterability audit."""

from __future__ import annotations

import random

import click

from . import audit as audit_mod
from .audit import QUERY_CAP, AssetCounts, AssetResult


def _disp_count(value: int | None, exist: int) -> str:
    """Show ``>CAP`` when the probe hit the query cap, else the number."""
    if value is None:
        return "err"
    if value >= QUERY_CAP and exist > QUERY_CAP:
        return f">{QUERY_CAP}"
    return str(value)


def _disp_exist(exist: int) -> str:
    return f">{QUERY_CAP}" if exist > QUERY_CAP else str(exist)


def _select(
    counts_by_id: dict,
    inventory_ids: str | None,
    sample: int,
) -> list[AssetCounts]:
    """Choose which assets to probe based on the selection options."""
    if inventory_ids:
        ids = [i.strip() for i in inventory_ids.split(",") if i.strip()]
        out = []
        for inv in ids:
            out.append(
                counts_by_id.get(inv, AssetCounts(inventory_id=inv))
            )
        return out
    ordered = sorted(
        counts_by_id.values(), key=lambda c: c.total, reverse=True
    )
    if sample > 0 and sample < len(ordered):
        return random.sample(ordered, sample)
    return ordered


def _print_table(results: list[AssetResult], show_names: bool) -> None:
    """Render the per-asset result table."""
    if show_names:
        header = (
            f"\n{'asset_id':<38} {'name':<32} {'visual':>7} {'audio':>7} "
            f"{'trans':>7} {'filterable':>11} {'probe_s':>8}   verdict"
        )
    else:
        header = (
            f"\n{'asset_id':<38} {'visual':>7} {'audio':>7} {'trans':>7} "
            f"{'filterable':>11} {'probe_s':>8}   verdict"
        )
    click.echo(header)
    for res in results:
        uuid = res.inventory_id.replace("asset:uuid:", "")
        counts = res.counts
        if counts.total == 0:
            visual = audio = trans = "0"
            filt = "-"
        else:
            visual = _disp_exist(counts.visual)
            audio = str(counts.audio)
            trans = str(counts.transcription)
            filt = (
                "-"
                if res.filterable is None and res.verdict == "no-visual"
                else _disp_count(res.filterable, counts.visual)
            )
        secs = (
            f"{res.probe_seconds:.2f}"
            if res.probe_seconds is not None
            else "-"
        )
        if show_names:
            name = (res.name or "-")[:30]
            click.echo(
                f"{uuid:<38} {name:<32} {visual:>7} {audio:>7} "
                f"{trans:>7} {filt:>11} {secs:>8}   {res.verdict}"
            )
        else:
            click.echo(
                f"{uuid:<38} {visual:>7} {audio:>7} {trans:>7} "
                f"{filt:>11} {secs:>8}   {res.verdict}"
            )


@click.command()
@click.option("--bucket", required=True, help="S3 Vectors bucket to audit.")
@click.option("--index", default="media-vectors", show_default=True,
              help="Vector index name.")
@click.option("--profile", default=None, help="AWS profile.")
@click.option("--region", default=None,
              help="AWS region (default: inferred from the bucket name).")
@click.option("--asset-table", default=None,
              help="Asset table for --names (default: inferred from bucket).")
@click.option("--inventory-ids", default=None,
              help="Comma-separated asset IDs to audit (troubleshooting).")
@click.option("--sample", type=int, default=0,
              help="Probe a random sample of N assets (large libraries).")
@click.option("--concurrency", type=int, default=8, show_default=True,
              help="Parallel probe workers (1 = serial).")
@click.option("--names", is_flag=True,
              help="Also show each asset's filename (1 lookup/asset).")
@click.option("--summary", is_flag=True,
              help="Verdict only; skip the per-asset table.")
def main(
    bucket: str,
    index: str,
    profile: str | None,
    region: str | None,
    asset_table: str | None,
    inventory_ids: str | None,
    sample: int,
    concurrency: int,
    names: bool,
    summary: bool,
) -> None:
    """Check that assets' visual embeddings are FILTERABLE.

    For each asset, report embedding clip counts and whether an
    ``embedding_option = visual`` filter returns any results (the property
    semantic search depends on). Any hit (>0) is a PASS; exactly 0 is the
    S3 Vectors metadata-filter bug.
    """
    if region is None:
        region = audit_mod.region_from_bucket(bucket) or "us-east-1"
    client = audit_mod.make_client(profile, region)

    click.echo(f"Auditing bucket: {bucket}  index: {index}  region: {region}")

    total, counts_by_id = audit_mod.collect_counts(client, bucket, index)
    click.echo(f"Indexed vectors: {total}")
    click.echo(f"Distinct assets with vectors: {len(counts_by_id)}")

    selected = _select(counts_by_id, inventory_ids, sample)
    if sample > 0:
        click.echo(f"Probing a random sample of {len(selected)} assets")

    results, probe_total = audit_mod.audit_assets(
        client, bucket, index, selected, concurrency
    )

    if names:
        dynamodb = audit_mod.make_dynamodb(profile, region)
        table = asset_table or audit_mod.asset_table_from_bucket(bucket)
        for res in results:
            res.name = audit_mod.lookup_name(
                dynamodb, table, res.inventory_id
            )

    if not summary:
        _print_table(results, names)

    ok = sum(1 for r in results if r.verdict == "ok")
    broken = sum(1 for r in results if r.verdict == "BROKEN")
    errors = sum(1 for r in results if r.verdict == "ERROR")
    novisual = sum(1 for r in results if r.verdict == "no-visual")
    missing = sum(1 for r in results if r.counts.total == 0)
    probed = ok + broken

    avg = probe_total / len(results) if results else 0.0
    click.echo("\n==================== SUMMARY ====================")
    click.echo(f"  indexed vectors ......... {total}")
    click.echo(f"  assets with vectors ..... {len(counts_by_id)}")
    click.echo(
        f"  assets probed ........... {probed}  "
        f"(+{novisual} no-visual, +{missing} no-vectors)"
    )
    click.echo(f"  filterable (>0 visual) .. {ok}")
    click.echo(f"  BROKEN (0 filterable) ... {broken}")
    if errors:
        click.echo(f"  probe ERRORS ............ {errors}  (re-run these)")
    click.echo(
        f"  probe time .............. {probe_total:.1f}s total, "
        f"{avg:.2f}s/asset avg (concurrency={concurrency})"
    )
    click.echo("=================================================")
    if broken == 0 and errors == 0:
        click.echo("  RESULT: PASS — every probed asset is filterable.")
    elif broken == 0:
        click.echo(
            f"  RESULT: INCONCLUSIVE — 0 broken but {errors} error(s). Re-run."
        )
    else:
        click.echo(
            f"  RESULT: FAIL — {broken} broken. Filterability issue present."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
