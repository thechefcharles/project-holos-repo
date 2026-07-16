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
            <button class="tab-btn" onclick="switchTab('by-ward')">By Ward</button>
            <button class="tab-btn" onclick="switchTab('by-category')">By Category</button>
        </div>

        <div id="summary" class="tab-content active">
            <div id="summary-content" class="loading">Loading...</div>
        </div>

        <div id="by-ward" class="tab-content">
            <div id="by-ward-content" class="loading">Loading...</div>
        </div>

        <div id="by-category" class="tab-content">
            <div id="by-category-content" class="loading">Loading...</div>
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
            } else if (tab === 'by-ward') {
                loadByWard();
            } else if (tab === 'by-category') {
                loadByCategory();
            }
        }

        async function loadAllData() {
            loadSummary();
            loadByWard();
            loadByCategory();
        }

        async function loadSummary() {
            try {
                const res = await fetch(`/api/reports/summary?year=${currentYear}`);
                const data = await res.json();

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

        async function loadByWard() {
            try {
                const res = await fetch(`/api/reports/by-ward?year=${currentYear}`);
                const data = await res.json();

                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Ward</th>
                                <th>Projects</th>
                                <th>Total Spend</th>
                                <th>Geocoded Projects</th>
                                <th>Geocoding Rate</th>
                                <th>Spend Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                Object.entries(data.wards).sort((a, b) => parseInt(a[0]) - parseInt(b[0])).forEach(([ward, stats]) => {
                    html += `
                        <tr>
                            <td><strong>Ward ${ward}</strong></td>
                            <td>${stats.projects}</td>
                            <td>${stats.spend}</td>
                            <td>${stats.geocoded_projects}</td>
                            <td>${stats.geocode_rate}</td>
                            <td>${stats.spend_rate}</td>
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

        // Load initial data
        loadAllData();
    </script>
</body>
</html>
    """
    return html


if __name__ == "__main__":
    app.run(debug=True, port=5000)
