"""Generate vector figures from the most recent results/metrics.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"
STAGES = ("sediment", "uf", "carbon", "ro")


def _write_svg(name: str, body: str, title: str, width: int = 1400, height: int = 800) -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#0d151d"/><style>
text{{font-family:Inter,Arial,sans-serif;fill:#d8e4e8}}.muted{{fill:#8da2ac}}.title{{font-size:30px;font-weight:650}}.small{{font-size:18px}}.label{{font-size:20px}}.value{{font-size:17px;font-weight:600}}
</style><text x="60" y="62" class="title">{title}</text><text x="60" y="98" class="small muted">SIMULATED · Generated from this run's results/metrics.json</text>
{body}<line x1="60" y1="740" x2="1340" y2="740" stroke="#263943"/><text x="60" y="774" class="small muted">FilterTwin · deterministic simulator only · not field validation</text></svg>'''
    (OUT / name).write_text(svg, encoding="utf-8")


def render(metrics: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    colors = {"p1": "#56dfcf", "b1": "#a58bd2", "b0_schedule": "#d9a76d", "b0_volume": "#7795ae"}
    # P1 and baseline comparison at the proposal's 21-day horizon.
    values = [
        float(metrics["stages"][s]["test"][m]["21"]["mae_days"] or 0)
        for s in STAGES
        for m in colors
    ]
    scale = 520 / max(max(values, default=1), 1)
    body = '<text x="60" y="145" class="small muted">Mean absolute error in days · TEST · 21 days before simulated EOL</text>'
    legend_x = 680
    for i, (key, color) in enumerate(colors.items()):
        x = legend_x + i * 165
        body += f'<rect x="{x}" y="124" width="18" height="18" rx="4" fill="{color}"/><text x="{x + 27}" y="140" class="small">{key}</text>'
    plot_y, group_w = 220, 300
    for index, stage in enumerate(STAGES):
        x0 = 105 + index * group_w
        body += f'<text x="{x0 + 80}" y="190" class="label">{stage.title()}</text>'
        for tick in range(0, int(max(values, default=0)) + 11, 10):
            y = 690 - tick * scale
            if y >= plot_y:
                body += f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + 225}" y2="{y:.1f}" stroke="#263943"/><text x="{x0 - 38}" y="{y + 6:.1f}" class="small muted">{tick}</text>'
        for j, model in enumerate(colors):
            value = float(metrics["stages"][stage]["test"][model]["21"]["mae_days"] or 0)
            h = value * scale
            x = x0 + 10 + j * 53
            body += f'<rect x="{x}" y="{690 - h:.1f}" width="39" height="{h:.1f}" rx="5" fill="{colors[model]}"/><text x="{x + 19}" y="{680 - h:.1f}" text-anchor="middle" class="value">{value:.1f}</text>'
    _write_svg("rul_mae_21d.svg", body, "Forecast error by stage and baseline")

    # Headline telemetry-tier comparison. Values and group labels come from evaluated holdout data.
    tier_colors = {"A": "#7795ae", "B": "#a58bd2", "C": "#56dfcf"}
    values = [
        float(metrics["telemetry_tiers"][tier]["test"][s]["21"]["mae_days"] or 0)
        for s in STAGES
        for tier in tier_colors
    ]
    scale = 490 / max(max(values, default=1), 1)
    body = '<text x="60" y="145" class="small muted">Mean absolute error in days · TEST · 21 days before simulated EOL</text>'
    plot_y, group_w = 220, 300
    for i, (tier, color) in enumerate(tier_colors.items()):
        x = 850 + i * 145
        body += f'<rect x="{x}" y="124" width="18" height="18" rx="4" fill="{color}"/><text x="{x + 28}" y="140" class="small">Tier {tier}</text>'
    for index, stage in enumerate(STAGES):
        x0 = 105 + index * group_w
        body += f'<text x="{x0 + 80}" y="190" class="label">{stage.title()}</text>'
        for j, (tier, color) in enumerate(tier_colors.items()):
            value = float(metrics["telemetry_tiers"][tier]["test"][stage]["21"]["mae_days"] or 0)
            h = value * scale
            x = x0 + 25 + j * 65
            body += f'<line x1="{x0}" y1="690" x2="{x0 + 240}" y2="690" stroke="#40535d"/><rect x="{x}" y="{690 - h:.1f}" width="48" height="{h:.1f}" rx="5" fill="{color}"/><text x="{x + 24}" y="{680 - h:.1f}" text-anchor="middle" class="value">{value:.1f}</text>'
    _write_svg("telemetry_tiers_21d.svg", body, "What each telemetry tier adds")

    # Policy comparison: useful life discarded and share of scheduled replacements that fail first.
    policies = metrics["business_impact"]["policies"]
    names = ["fixed_schedule", "volume_counter", "filtertwin"]
    labels = {
        "fixed_schedule": "Fixed schedule",
        "volume_counter": "Volume counter",
        "filtertwin": "FilterTwin warning",
    }
    colors_policy = {
        "fixed_schedule": "#d9a76d",
        "volume_counter": "#7795ae",
        "filtertwin": "#56dfcf",
    }
    body = '<text x="60" y="145" class="small muted">Three simulated years · 1,000 households · percentages over modeled cartridge replacement cycles</text>'
    for i, name in enumerate(names):
        y = 220 + i * 150
        wasted = float(policies[name]["mean_useful_life_wasted_fraction"]) * 100
        failed = float(policies[name]["cartridges_failing_before_replacement_fraction"]) * 100
        body += f'<text x="80" y="{y + 28}" class="label">{labels[name]}</text>'
        for j, (metric, val) in enumerate(
            (("Useful life wasted", wasted), ("Fail before replacement", failed))
        ):
            x, by = 390, y + j * 48
            body += f'<text x="390" y="{by + 19}" class="small muted">{metric}</text><rect x="650" y="{by}" width="500" height="26" rx="7" fill="#1b2b34"/><rect x="650" y="{by}" width="{5 * max(0, min(val, 100)):.1f}" height="26" rx="7" fill="{colors_policy[name]}"/><text x="1170" y="{by + 20}" class="value">{val:.1f}%</text>'
        body += f'<text x="80" y="{y + 72}" class="small muted">{int(policies[name]["replacements_per_1000_households_3y"]):,} replacements</text>'
    body += '<text x="60" y="690" class="small muted">Scenario-dependent simulator policy comparison; not measured customer savings.</text>'
    _write_svg("business_policy.svg", body, "Maintenance policy trade-offs")

    # Paired perturbation signature grid. Color denotes sign and intensity is normalized per observable.
    signature = metrics["signature_matrix"]["delta_from_baseline"]
    columns = (
        "flow_l_h",
        "fill_time_h",
        "current_a",
        "rpm",
        "current_ripple_a",
        "outlet_tds_mg_l",
        "normalised_permeability",
    )
    headers = ("Flow", "Fill time", "Current", "RPM", "Ripple", "Outlet TDS", "Normalized A")
    maxima = {
        column: max((abs(float(row.get(column, 0))) for row in signature.values()), default=1.0)
        or 1.0
        for column in columns
    }
    body = '<text x="60" y="145" class="small muted">Delta from nominal · 12 controlled conditions × 2 assumed controller modes</text>'
    x0, y0, cell_w, row_h = 470, 190, 115, 23
    for j, header in enumerate(headers):
        body += f'<text x="{x0 + j * cell_w + cell_w / 2}" y="177" text-anchor="middle" class="small muted">{header}</text>'
    for i, (name, row) in enumerate(signature.items()):
        y = y0 + i * row_h
        body += f'<text x="60" y="{y + 17}" class="small">{name.replace(":", " / ").replace("_", " ")}</text>'
        for j, column in enumerate(columns):
            value = float(row.get(column, 0))
            intensity = min(1.0, abs(value) / maxima[column])
            color = (
                f"#{int(20 + 36 * intensity):02x}{int(35 + 130 * intensity):02x}{int(42 + 118 * intensity):02x}"
                if value >= 0
                else f"#{int(45 + 135 * intensity):02x}{int(28 + 42 * intensity):02x}{int(35 + 46 * intensity):02x}"
            )
            x = x0 + j * cell_w
            body += f'<rect x="{x + 4}" y="{y}" width="{cell_w - 8}" height="20" rx="4" fill="{color}"/><text x="{x + cell_w / 2}" y="{y + 15}" text-anchor="middle" class="small">{value:.2g}</text>'
    _write_svg("signature_matrix.svg", body, "Observable signatures by condition")


def main() -> None:
    metrics = json.loads((ROOT / "results" / "metrics.json").read_text(encoding="utf-8"))
    render(metrics)
    print(f"Generated SVG figure pack in {OUT}")


if __name__ == "__main__":
    main()
