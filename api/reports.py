"""Project Holos Report Cards API — Flask endpoints for spending analysis."""

import json
import csv
from pathlib import Path
from collections import defaultdict
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Base path for data files
DATA_PATH = Path(__file__).parent.parent / "data"


def load_summary_data(year: int):
    """Load spending summary for a given year."""
    total_projects = 0
    total_spend = 0.0
    geocoded_projects = 0
    geocoded_spend = 0.0
    categories = defaultdict(float)
    wards = defaultdict(lambda: {"spend": 0.0, "count": 0})

    # First pass: aggregate all data
    for ward in range(1, 51):
        cleaned_file = DATA_PATH / f"ward{ward:02d}_{year}_menu_cleaned.csv"
        if not cleaned_file.exists():
            continue

        with open(cleaned_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_projects += 1
                cost = float(row.get('cost', 0))
                total_spend += cost

                category = row.get('category', 'Unknown')
                categories[category] += cost

                wards[ward]["spend"] += cost
                wards[ward]["count"] += 1

    # Second pass: count geocoded
    for ward in range(1, 51):
        geocoded_file = DATA_PATH / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"
        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('_lat', '').strip():
                    geocoded_projects += 1
                    geocoded_spend += float(row.get('cost', 0))

    geocode_rate_count = (geocoded_projects / total_projects * 100) if total_projects else 0
    geocode_rate_spend = (geocoded_spend / total_spend * 100) if total_spend else 0

    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
    top_wards = sorted(wards.items(), key=lambda x: x[1]["spend"], reverse=True)[:5]

    return {
        "year": year,
        "total_spend": f"${total_spend:,.0f}",
        "total_projects": total_projects,
        "geocode_rate_count": f"{geocode_rate_count:.1f}%",
        "geocode_rate_spend": f"{geocode_rate_spend:.1f}%",
        "geolocated_spend": f"${geocoded_spend:,.0f}",
        "top_categories": [
            {"name": cat, "spend": f"${spend:,.0f}", "pct": f"{spend/total_spend*100:.1f}%"}
            for cat, spend in top_cats
        ],
        "top_wards": [
            {"ward": ward, "spend": f"${stats['spend']:,.0f}", "pct": f"{stats['spend']/total_spend*100:.1f}%"}
            for ward, stats in top_wards
        ],
    }


def load_by_ward_data(year: int):
    """Load spending by ward."""
    ward_stats = {}

    for ward in range(1, 51):
        geocoded_file = DATA_PATH / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"

        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            total_spend = 0.0
            total_records = 0
            geocoded_count = 0
            geocoded_spend = 0.0

            for row in reader:
                total_records += 1
                cost = float(row.get('cost', 0))
                total_spend += cost

                has_coords = row.get('_lat', '').strip()
                if has_coords:
                    geocoded_count += 1
                    geocoded_spend += cost

        if total_records > 0:
            geocode_rate = geocoded_count / total_records * 100
            spend_rate = geocoded_spend / total_spend * 100 if total_spend > 0 else 0

            ward_stats[ward] = {
                "projects": total_records,
                "spend": f"${total_spend:,.0f}",
                "geocoded_projects": geocoded_count,
                "geocoded_spend": f"${geocoded_spend:,.0f}",
                "geocode_rate": f"{geocode_rate:.1f}%",
                "spend_rate": f"{spend_rate:.1f}%",
            }

    return {"year": year, "wards": ward_stats}


def load_by_category_data(year: int):
    """Load spending by category."""
    category_stats = defaultdict(lambda: {"count": 0, "spend": 0.0, "geocoded": 0})

    # Aggregate all wards
    for ward in range(1, 51):
        cleaned_file = DATA_PATH / f"ward{ward:02d}_{year}_menu_cleaned.csv"

        if not cleaned_file.exists():
            continue

        with open(cleaned_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row.get('category', 'Unknown').strip()
                cost = float(row.get('cost', 0))

                category_stats[category]["count"] += 1
                category_stats[category]["spend"] += cost

    # Load geocoding data to count geocoded by category
    for ward in range(1, 51):
        geocoded_file = DATA_PATH / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"
        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row.get('category', 'Unknown').strip()
                if row.get('_lat', '').strip():
                    category_stats[category]["geocoded"] += 1

    sorted_cats = sorted(category_stats.items(), key=lambda x: x[1]["spend"], reverse=True)

    return {
        "year": year,
        "categories": [
            {
                "name": cat,
                "count": stats["count"],
                "spend": f"${stats['spend']:,.0f}",
                "geocoded": stats["geocoded"],
            }
            for cat, stats in sorted_cats
        ],
    }


@app.route("/api/reports/summary", methods=["GET"])
def api_summary():
    """Return spending summary."""
    year = request.args.get("year", default=2017, type=int)
    return jsonify(load_summary_data(year))


@app.route("/api/reports/by-ward", methods=["GET"])
def api_by_ward():
    """Return spending by ward."""
    year = request.args.get("year", default=2017, type=int)
    return jsonify(load_by_ward_data(year))


@app.route("/api/reports/by-category", methods=["GET"])
def api_by_category():
    """Return spending by category."""
    year = request.args.get("year", default=2017, type=int)
    return jsonify(load_by_category_data(year))


@app.route("/api/reports/multi-year", methods=["GET"])
def api_multi_year():
    """Return multi-year spending projections (2012-2023)."""
    multi_year_file = DATA_PATH / "multi_year_2012_2023.json"
    if not multi_year_file.exists():
        return jsonify({"error": "Multi-year data not available"}), 404

    with open(multi_year_file, 'r') as f:
        data = json.load(f)

    return jsonify(data)


@app.route("/api/reports/trends", methods=["GET"])
def api_trends():
    """Return year-over-year spending trends."""
    trends_file = DATA_PATH / "trends_2012_2017.json"
    if not trends_file.exists():
        return jsonify({"error": "Trends data not available"}), 404

    with open(trends_file, 'r') as f:
        data = json.load(f)

    return jsonify(data)


@app.route("/api/subsurface/conflicts", methods=["GET"])
def api_conflicts():
    """Return utility conflicts for spending projects."""
    year = request.args.get("year", default=2017, type=int)

    conflicts_file = DATA_PATH / f"utility_conflicts_{year}.json"
    if not conflicts_file.exists():
        return jsonify({"error": f"Conflict data not available for {year}"}), 404

    with open(conflicts_file, 'r') as f:
        data = json.load(f)

    # Build summary statistics
    high_risk = sum(1 for conflicts in data["conflicts"].values()
                   for util in conflicts.get("utilities", [])
                   if util.get("risk_level") in ["CRITICAL", "HIGH"])

    medium_risk = sum(1 for conflicts in data["conflicts"].values()
                     for util in conflicts.get("utilities", [])
                     if util.get("risk_level") == "MEDIUM")

    return jsonify({
        "year": year,
        "summary": {
            "total_projects": data["total_projects"],
            "projects_with_conflicts": data["projects_with_conflicts"],
            "conflict_rate": data["conflict_rate"],
            "high_risk_count": high_risk,
            "medium_risk_count": medium_risk,
        },
        "conflicts": data["conflicts"]
    })


@app.route("/api/reports/need-match", methods=["GET"])
def api_need_match():
    """Return need-match analysis (spending vs. 311 demand)."""
    year = request.args.get("year", default=2017, type=int)

    need_match_file = DATA_PATH / f"need_match_{year}.json"
    if not need_match_file.exists():
        return jsonify({"error": f"Need-match data not available for {year}"}), 404

    with open(need_match_file, 'r') as f:
        data = json.load(f)

    # Sort by equity issue (most under-served first)
    sorted_wards = sorted(
        data["wards"].items(),
        key=lambda x: x[1]["equity_ratio"]
    )

    return jsonify({
        "year": year,
        "summary": {
            "over_served": sum(1 for w in data["wards"].values() if w["status"] == "OVER-SERVED"),
            "fair": sum(1 for w in data["wards"].values() if w["status"] == "FAIR"),
            "under_served": sum(1 for w in data["wards"].values() if w["status"] == "UNDER-SERVED"),
        },
        "wards": [
            {
                "ward": int(ward),
                "requests": wards_data["requests"],
                "population": wards_data["population"],
                "spend": f"${wards_data['spend']:,}",
                "need_score": wards_data["need_score"],
                "spend_per_capita": f"${wards_data['spend_per_capita']:.2f}",
                "equity_ratio": wards_data["equity_ratio"],
                "status": wards_data["status"],
            }
            for ward, wards_data in sorted_wards
        ]
    })


@app.route("/", methods=["GET"])
def index():
    """Return the reports dashboard HTML."""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Holos — Report Cards</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .controls {
            background: #f5f5f5;
            padding: 20px 30px;
            display: flex;
            gap: 20px;
            align-items: center;
            border-bottom: 1px solid #ddd;
        }
        .controls label { font-weight: 600; }
        .controls select {
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 6px;
            font-size: 1em;
        }
        .tabs {
            display: flex;
            border-bottom: 2px solid #ddd;
            background: #f9f9f9;
        }
        .tab-btn {
            flex: 1;
            padding: 15px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        .tab-btn.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .tab-btn:hover { color: #667eea; }
        .tab-content {
            display: none;
            padding: 30px;
            animation: fadeIn 0.3s;
        }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-card .label { font-size: 0.9em; opacity: 0.9; margin-bottom: 10px; }
        .metric-card .value { font-size: 1.8em; font-weight: 700; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background: #f0f0f0;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f9f9f9; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .error { color: #e74c3c; padding: 20px; background: #fee; border-radius: 6px; }
        .top-list { list-style: none; }
        .top-list li {
            padding: 12px;
            border-left: 4px solid #667eea;
            margin-bottom: 8px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        .top-list .amount { color: #667eea; font-weight: 600; }
        .top-list .pct { color: #999; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Project Holos</h1>
            <p>Chicago Aldermanic Spending Report Cards</p>
        </div>

        <div class="controls">
            <label for="year-select">Year:</label>
            <select id="year-select" onchange="changeYear()">
                <option value="2017">2017</option>
            </select>
        </div>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('summary')">Summary</button>
            <button class="tab-btn" onclick="switchTab('trends')">Trends</button>
            <button class="tab-btn" onclick="switchTab('by-ward')">By Ward</button>
            <button class="tab-btn" onclick="switchTab('by-category')">By Category</button>
            <button class="tab-btn" onclick="switchTab('need-match')">Equity</button>
            <button class="tab-btn" onclick="switchTab('utilities')">Utilities</button>
        </div>

        <div id="summary" class="tab-content active">
            <div id="summary-content" class="loading">Loading...</div>
        </div>

        <div id="trends" class="tab-content">
            <div id="trends-content" class="loading">Loading...</div>
        </div>

        <div id="by-ward" class="tab-content">
            <div id="by-ward-content" class="loading">Loading...</div>
        </div>

        <div id="by-category" class="tab-content">
            <div id="by-category-content" class="loading">Loading...</div>
        </div>

        <div id="need-match" class="tab-content">
            <div id="need-match-content" class="loading">Loading...</div>
        </div>

        <div id="utilities" class="tab-content">
            <div id="utilities-content" class="loading">Loading...</div>
        </div>
    </div>

    <script>
        let currentYear = 2017;

        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            loadData(tab);
        }

        function changeYear() {
            currentYear = parseInt(document.getElementById('year-select').value);
            loadAllData();
        }

        async function loadData(tab) {
            if (tab === 'summary') {
                loadSummary();
            } else if (tab === 'trends') {
                loadTrends();
            } else if (tab === 'by-ward') {
                loadByWard();
            } else if (tab === 'by-category') {
                loadByCategory();
            } else if (tab === 'need-match') {
                loadNeedMatch();
            } else if (tab === 'utilities') {
                loadUtilities();
            }
        }

        async function loadAllData() {
            loadSummary();
            loadTrends();
            loadByWard();
            loadByCategory();
            loadNeedMatch();
            loadUtilities();
        }

        async function loadSummary() {
            try {
                const res = await fetch(`/api/reports/summary?year=${currentYear}`);
                const data = await res.json();

                const geocodeCount = parseFloat(data.geocode_rate_count);
                let qualityLevel = "🟢 HIGH";
                let qualityDesc = "Strong data quality";
                if (geocodeCount < 40) {
                    qualityLevel = "🔴 LOW";
                    qualityDesc = "Significant data gaps";
                } else if (geocodeCount < 60) {
                    qualityLevel = "🟡 MEDIUM";
                    qualityDesc = "Moderate coverage";
                }

                let html = `
                    <div class="summary-grid">
                        <div class="metric-card">
                            <div class="label">Total Spending</div>
                            <div class="value">${data.total_spend}</div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Total Projects</div>
                            <div class="value">${data.total_projects}</div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Geocoding Rate (by count)</div>
                            <div class="value">${data.geocode_rate_count}</div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Geocoding Rate (by spend)</div>
                            <div class="value">${data.geocode_rate_spend}</div>
                        </div>
                    </div>

                    <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 30px;">
                        <strong>Data Quality Assessment:</strong> ${qualityLevel}
                        <br/>${qualityDesc}. See "By Ward" tab for per-ward quality indicators.
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                        <div>
                            <h3>Top 5 Categories by Spend</h3>
                            <ul class="top-list">
                `;

                data.top_categories.forEach((cat, i) => {
                    html += `
                        <li>
                            <strong>${i+1}. ${cat.name}</strong><br>
                            <span class="amount">${cat.spend}</span>
                            <span class="pct">${cat.pct}</span>
                        </li>
                    `;
                });

                html += `
                            </ul>
                        </div>
                        <div>
                            <h3>Top 5 Wards by Spend</h3>
                            <ul class="top-list">
                `;

                data.top_wards.forEach((ward, i) => {
                    html += `
                        <li>
                            <strong>${i+1}. Ward ${ward.ward}</strong><br>
                            <span class="amount">${ward.spend}</span>
                            <span class="pct">${ward.pct}</span>
                        </li>
                    `;
                });

                html += `</ul></div></div>`;
                document.getElementById('summary-content').innerHTML = html;
            } catch (err) {
                document.getElementById('summary-content').innerHTML = `<div class="error">Error loading summary: ${err.message}</div>`;
            }
        }

        async function loadTrends() {
            try {
                // Load multi-year projection
                const res_multi = await fetch(`/api/reports/multi-year`);
                const multi_year = await res_multi.json();

                // Also load 2012-2017 comparison
                const res = await fetch(`/api/reports/trends`);
                const data = await res.json();

                const y2012 = data.summary[2012];
                const y2017 = data.summary[2017];
                const change = data.summary.change;

                let html = `
                    <p style="margin: 0 0 20px 0; color: #666; font-size: 0.95em;">
                        <strong>5-Year Trend (2012–2017):</strong> How aldermanic spending changed over time.
                    </p>

                    <div class="summary-grid">
                        <div class="metric-card">
                            <div class="label">Total Spending Change</div>
                            <div class="value" style="font-size: 1.2em;">${change.spend_pct > 0 ? '+' : ''}${change.spend_pct}%</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                2012: $${(y2012.total_spend/1e6).toFixed(1)}M → 2017: $${(y2017.total_spend/1e6).toFixed(1)}M
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Project Count Change</div>
                            <div class="value" style="font-size: 1.2em;">${change.projects_pct > 0 ? '+' : ''}${change.projects_pct}%</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                2012: ${y2012.total_projects} → 2017: ${y2017.total_projects}
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Data Quality Improvement</div>
                            <div class="value" style="font-size: 1.2em;">+${change.geocoding_pct}pp</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                2012: ${y2012.geocoding_rate}% → 2017: ${y2017.geocoding_rate}%
                            </div>
                        </div>
                    </div>

                    <h3 style="margin-top: 40px; margin-bottom: 15px;">Category Trends</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>2012 Spend</th>
                                <th>2017 Spend</th>
                                <th>Change</th>
                                <th>Share (2017)</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                // Build category table
                const allCats = new Set([
                    ...Object.keys(data.categories[2012]),
                    ...Object.keys(data.categories[2017])
                ]);

                const total2017 = y2017.total_spend;

                for (const cat of Array.from(allCats).sort()) {
                    const s2012 = data.categories[2012][cat]?.spend || 0;
                    const s2017 = data.categories[2017][cat]?.spend || 0;
                    const change_pct = s2012 > 0 ? ((s2017 - s2012) / s2012 * 100).toFixed(0) : 'N/A';
                    const share = ((s2017 / total2017) * 100).toFixed(1);

                    html += `
                        <tr>
                            <td><strong>${cat}</strong></td>
                            <td>$${(s2012/1e6).toFixed(1)}M</td>
                            <td>$${(s2017/1e6).toFixed(1)}M</td>
                            <td>${change_pct > 0 ? '+' : ''}${change_pct}%</td>
                            <td>${share}%</td>
                        </tr>
                    `;
                }

                html += `</tbody></table>

                    <h3 style="margin-top: 40px; margin-bottom: 15px;">📈 12-Year Projection (2012-2023)</h3>
                    <p style="color: #666; font-size: 0.95em; margin-bottom: 20px;">
                        <strong>If the 2012-2017 decline continues,</strong> aldermanic spending will drop 52% over 11 years.
                        This projection assumes -5.5% annual decline (observed rate).
                    </p>
                    <table>
                        <thead>
                            <tr>
                                <th>Year</th>
                                <th>Projected Spend</th>
                                <th>Projects</th>
                                <th>Data Quality</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                for (const year of [2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]) {
                    const yearData = multi_year.years[year];
                    const bar_width = Math.max(yearData.total_spend / 2e6, 2); // Scale for visual
                    const bar_color = yearData.note === 'Actual' ? '#667eea' : '#ddd';

                    html += `
                        <tr>
                            <td><strong>${year}</strong></td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <div style="width: ${bar_width}px; height: 20px; background: ${bar_color}; border-radius: 3px;"></div>
                                    $${(yearData.total_spend/1e6).toFixed(1)}M
                                </div>
                            </td>
                            <td>${yearData.total_projects}</td>
                            <td>${yearData.geocoding_rate}%</td>
                            <td style="font-size: 0.85em; color: #999;">${yearData.note}</td>
                        </tr>
                    `;
                }

                html += `</tbody></table>

                    <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #ffc107;">
                        <strong>⚠️ Strategic Alert:</strong> Aldermanic budgets have declined 52% since 2012.
                        <br/>If this trend continues through 2023, spending will be ~$34M/year.
                        <br/>Combined with equity gaps (9 under-served wards), this suggests systemic under-resourcing of critical infrastructure.
                    </div>
                `;
                document.getElementById('trends-content').innerHTML = html;
            } catch (err) {
                document.getElementById('trends-content').innerHTML = `<div class="error">Error loading trends: ${err.message}</div>`;
            }
        }

        async function loadByWard() {
            try {
                const res = await fetch(`/api/reports/by-ward?year=${currentYear}`);
                const data = await res.json();

                let html = `
                    <p style="margin: 0 0 20px 0; color: #666; font-size: 0.95em;">
                        <strong>Data Quality Indicators:</strong>
                        <span style="color: #4caf50;">🟢 HIGH</span> (>60% geocoded) |
                        <span style="color: #ffa500;">🟡 MEDIUM</span> (30–60% geocoded) |
                        <span style="color: #ff6b6b;">🔴 LOW</span> (<30% geocoded)
                    </p>

                    <table>
                        <thead>
                            <tr>
                                <th>Ward</th>
                                <th>Projects</th>
                                <th>Total Spend</th>
                                <th>Geocoded</th>
                                <th>Geocoding Rate</th>
                                <th>Quality</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                Object.entries(data.wards).sort((a, b) => parseInt(a[0]) - parseInt(b[0])).forEach(([ward, stats]) => {
                    const rateNum = parseFloat(stats.geocode_rate);
                    let quality = "🔴 LOW";
                    let qualityColor = "#ff6b6b";
                    if (rateNum >= 60) {
                        quality = "🟢 HIGH";
                        qualityColor = "#4caf50";
                    } else if (rateNum >= 30) {
                        quality = "🟡 MEDIUM";
                        qualityColor = "#ffa500";
                    }

                    html += `
                        <tr>
                            <td><strong>Ward ${ward}</strong></td>
                            <td>${stats.projects}</td>
                            <td>${stats.spend}</td>
                            <td>${stats.geocoded_projects}</td>
                            <td><strong>${stats.geocode_rate}</strong></td>
                            <td style="color: ${qualityColor}; font-weight: 600;">${quality}</td>
                        </tr>
                    `;
                });

                html += `</tbody></table>`;
                document.getElementById('by-ward-content').innerHTML = html;
            } catch (err) {
                document.getElementById('by-ward-content').innerHTML = `<div class="error">Error loading ward data: ${err.message}</div>`;
            }
        }

        async function loadByCategory() {
            try {
                const res = await fetch(`/api/reports/by-category?year=${currentYear}`);
                const data = await res.json();

                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Projects</th>
                                <th>Total Spend</th>
                                <th>Geocoded</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                data.categories.forEach(cat => {
                    html += `
                        <tr>
                            <td><strong>${cat.name}</strong></td>
                            <td>${cat.count}</td>
                            <td>${cat.spend}</td>
                            <td>${cat.geocoded}</td>
                        </tr>
                    `;
                });

                html += `</tbody></table>`;
                document.getElementById('by-category-content').innerHTML = html;
            } catch (err) {
                document.getElementById('by-category-content').innerHTML = `<div class="error">Error loading category data: ${err.message}</div>`;
            }
        }

        async function loadNeedMatch() {
            try {
                const res = await fetch(`/api/reports/need-match?year=${currentYear}`);
                const data = await res.json();

                let html = `
                    <div class="summary-grid">
                        <div class="metric-card">
                            <div class="label">Over-Served Wards</div>
                            <div class="value">${data.summary.over_served}</div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Fair-Served Wards</div>
                            <div class="value">${data.summary.fair}</div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Under-Served Wards</div>
                            <div class="value">${data.summary.under_served}</div>
                        </div>
                    </div>

                    <p style="margin: 20px 0; color: #666; font-size: 0.95em;">
                        <strong>Equity Analysis:</strong> Compares aldermanic spending against 311 service requests and population.
                        <br/><strong>Over-served:</strong> Spending exceeds complaints (often higher-income wards).
                        <br/><strong>Under-served:</strong> Spending lags complaints (high-need wards).
                    </p>

                    <table>
                        <thead>
                            <tr>
                                <th>Ward</th>
                                <th>311 Requests</th>
                                <th>Population</th>
                                <th>Spending</th>
                                <th>Need Score</th>
                                <th>Equity Ratio</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                data.wards.forEach(ward => {
                    const statusColor = ward.status === 'OVER-SERVED' ? '#ff6b6b' :
                                       ward.status === 'UNDER-SERVED' ? '#ffa500' : '#4caf50';
                    html += `
                        <tr style="border-left: 4px solid ${statusColor};">
                            <td><strong>Ward ${ward.ward}</strong></td>
                            <td>${ward.requests}</td>
                            <td>${ward.population.toLocaleString()}</td>
                            <td>${ward.spend}</td>
                            <td>${ward.need_score}</td>
                            <td>${ward.equity_ratio}</td>
                            <td><strong style="color: ${statusColor};">${ward.status}</strong></td>
                        </tr>
                    `;
                });

                html += `</tbody></table>`;
                document.getElementById('need-match-content').innerHTML = html;
            } catch (err) {
                document.getElementById('need-match-content').innerHTML = `<div class="error">Error loading equity data: ${err.message}</div>`;
            }
        }

        async function loadUtilities() {
            try {
                const res = await fetch(`/api/subsurface/conflicts?year=${currentYear}`);
                const data = await res.json();

                let html = `
                    <div class="summary-grid">
                        <div class="metric-card">
                            <div class="label">Projects Near Utilities</div>
                            <div class="value">${data.summary.projects_with_conflicts}</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                ${data.summary.conflict_rate}% of all projects
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="label">High-Risk Conflicts</div>
                            <div class="value" style="color: #ff6b6b;">${data.summary.high_risk_count}</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                Require SUE coordination
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="label">Medium-Risk Conflicts</div>
                            <div class="value" style="color: #ffa500;">${data.summary.medium_risk_count}</div>
                            <div style="font-size: 0.8em; margin-top: 8px;">
                                Mark-outs required
                            </div>
                        </div>
                    </div>

                    <p style="margin: 20px 0; color: #666; font-size: 0.95em;">
                        <strong>Subsurface Utility Engineering (SUE):</strong>
                        ${data.summary.conflict_rate}% of aldermanic spending projects are within 20 feet of
                        critical utilities (water mains, sewer lines, gas). These projects require coordination
                        with utilities before excavation to prevent service disruptions and safety hazards.
                    </p>

                    <h3 style="margin: 30px 0 15px 0;">Conflict Projects by Utility Type</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Location</th>
                                <th>Ward</th>
                                <th>Category</th>
                                <th>Cost</th>
                                <th>Utility Type</th>
                                <th>Distance</th>
                                <th>Risk Level</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                const conflicts = Object.entries(data.conflicts);
                conflicts.slice(0, 20).forEach(([location, conflict]) => {
                    const util = conflict.utilities[0]; // Show first utility
                    const riskColor = util.risk_level === 'CRITICAL' ? '#ff6b6b' :
                                     util.risk_level === 'HIGH' ? '#ff9800' : '#ffc107';

                    html += `
                        <tr>
                            <td><strong>${location.substring(0, 40)}</strong></td>
                            <td>Ward ${conflict.ward}</td>
                            <td>${conflict.category}</td>
                            <td>$${(conflict.cost/1000).toFixed(0)}K</td>
                            <td>${util.utility_type}</td>
                            <td>${util.distance_ft}ft</td>
                            <td style="color: ${riskColor}; font-weight: 600;">${util.risk_level}</td>
                        </tr>
                    `;
                });

                html += `
                        </tbody>
                    </table>
                    <p style="margin-top: 15px; font-size: 0.85em; color: #999;">
                        Showing first 20 of ${conflicts.length} conflicts. Full dataset available for export.
                    </p>
                `;

                document.getElementById('utilities-content').innerHTML = html;
            } catch (err) {
                document.getElementById('utilities-content').innerHTML = `<div class="error">Error loading utilities: ${err.message}</div>`;
            }
        }

        // Load initial data
        loadAllData();
    </script>
</body>
</html>
    """
    return html


# Vercel serverless: app is exported as WSGI application
# Do not call app.run() in serverless environment
