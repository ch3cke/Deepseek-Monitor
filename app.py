from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3
import json
import os

app = FastAPI(title="DeepSeek Monitor")

@app.get("/api/data")
def get_data():
    if not os.path.exists('usage_history.db'):
        return {"users": {}, "summary": {"cost": 0, "tokens": 0, "requests": 0}}

    conn = sqlite3.connect('usage_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 获取每个用户最新的一条记录
    c.execute('''
        SELECT user, cost, tokens, requests, models_info, status
        FROM usage_records
        WHERE id IN (
            SELECT MAX(id) FROM usage_records GROUP BY user
        )
    ''')
    rows = c.fetchall()

    result = {"users": {}, "summary": {"cost": 0, "tokens": 0, "requests": 0}}
    total_cost = 0
    total_tokens = 0
    total_requests = 0

    for row in rows:
        user = row['user']
        cost = row['cost']
        tokens = row['tokens']
        reqs = row['requests']
        models_info = json.loads(row['models_info']) if row['models_info'] else {}
        status = row['status'] if 'status' in row.keys() and row['status'] else 'active'

        result["users"][user] = {
            "cost": cost,
            "tokens": tokens,
            "requests": reqs,
            "models": models_info,
            "status": status
        }

        total_cost += cost
        total_tokens += tokens
        total_requests += reqs

    result["summary"] = {
        "cost": round(total_cost, 4),
        "tokens": total_tokens,
        "requests": total_requests
    }

    conn.close()
    return result

@app.get("/")
def index():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DeepSeek Monitor</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            .summary { display: flex; gap: 20px; margin-bottom: 20px; }
            .summary-box { flex: 1; padding: 20px; border-radius: 8px; color: white; text-align: center; }
            .bg-blue { background-color: #007bff; }
            .bg-green { background-color: #28a745; }
            .bg-purple { background-color: #6f42c1; }
            .summary-box h3 { margin: 0; font-size: 1.2em; font-weight: normal; }
            .summary-box p { margin: 10px 0 0; font-size: 1.8em; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; }
            .warning { color: #856404; background-color: #fff3cd; }
            .danger { color: #721c24; background-color: #f8d7da; }
            .usage-bar { width: 100%; height: 8px; background-color: #eee; border-radius: 4px; overflow: hidden; margin-top: 5px; }
            .usage-fill { height: 100%; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>DeepSeek API Monitor</h1>
            <div class="summary" id="summary">
                Loading...
            </div>
            
            <h2>User Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>User</th>
                        <th>API Key</th>
                        <th>Cost (¥)</th>
                        <th>Tokens</th>
                        <th>Requests</th>
                    </tr>
                </thead>
                <tbody id="user-table">
                </tbody>
            </table>
        </div>

        <script>
            async function fetchData() {
                try {
                    const response = await fetch('/api/data');
                    const data = await response.json();
                    
                    // Render summary
                    const s = data.summary;
                    document.getElementById('summary').innerHTML = `
                        <div class="summary-box bg-blue">
                            <h3>Total Cost</h3>
                            <p>¥${s.cost.toFixed(2)}</p>
                        </div>
                        <div class="summary-box bg-green">
                            <h3>Total Tokens</h3>
                            <p>${s.tokens.toLocaleString()}</p>
                        </div>
                        <div class="summary-box bg-purple">
                            <h3>Total Requests</h3>
                            <p>${s.requests.toLocaleString()}</p>
                        </div>
                    `;

                    // Render users
                    const tbody = document.getElementById('user-table');
                    tbody.innerHTML = '';
                    
                    const users = Object.entries(data.users).map(([name, info]) => ({ name, ...info }));
                    users.sort((a, b) => b.cost - a.cost);

                    users.forEach(u => {
                        const tr = document.createElement('tr');
                        const isDeleted = u.status === 'deleted';
                        
                        if (isDeleted || u.cost > 99) {
                            tr.className = 'danger';
                        } else if (u.cost >= 80) {
                            tr.className = 'warning';
                        }
                        
                        // basic limit 100 as reference for progress bar
                        const pct = Math.min(100, (u.cost / 100) * 100);
                        const fillColor = isDeleted ? '#6c757d' : (u.cost > 99 ? '#dc3545' : u.cost >= 80 ? '#ffc107' : '#28a745');
                        const statusBadge = isDeleted ? '<span style="background:#dc3545; color:white; padding:2px 6px; border-radius:4px; font-size:12px; margin-left:8px; white-space:nowrap;">Token Deleted</span>' : '';

                        tr.innerHTML = `
                            <td>${u.name} ${statusBadge}</td>
                            <td>${Object.values(u.models).length ? 'Hidden' : ''}</td>
                            <td>
                                ¥${u.cost.toFixed(2)}
                                <div class="usage-bar">
                                    <div class="usage-fill" style="width: ${pct}%; background-color: ${fillColor}"></div>
                                </div>
                            </td>
                            <td>${u.tokens.toLocaleString()}</td>
                            <td>${u.requests.toLocaleString()}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } catch (error) {
                    console.error('Error fetching data:', error);
                    document.getElementById('summary').innerHTML = '<p style="color:red">Failed to load data. See console.</p>';
                }
            }

            fetchData();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
