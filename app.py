from flask import Flask, request, Response, render_template_string
from flask_cors import CORS
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

app = Flask(__name__)
CORS(app)

# HTML template for the root page
HOME_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Visit Counter</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        pre {
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
        }
        code {
            font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 85%;
        }
        .example {
            margin: 2rem 0;
            padding: 1rem;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
        }
    </style>
</head>
<body>
    <h1>GitHub Visit Counter</h1>
    <p>This service generates a dynamic visitor count badge for your GitHub repository.</p>

    <h2>Usage</h2>
    <p>Add this badge to your repository by adding the following line to your README.md:</p>
    <pre><code>[![Visitor Badge](https://github-visit-counter.onrender.com/badge/your-repo-name)](https://github-visit-counter.onrender.com/badge/your-repo-name)</code></pre>

    <div class="example">
        <h3>Example</h3>
        <p>To test the badge, visit:</p>
        <a href="/badge/test-repo">/badge/test-repo</a>
    </div>

    <h2>Features</h2>
    <ul>
        <li>Tracks unique visitors using IP addresses</li>
        <li>Shows last 7 days of visitor statistics</li>
        <li>Displays total visitor count</li>
        <li>Updates in real-time</li>
        <li>Clean, minimal design</li>
    </ul>

    <h2>API Endpoints</h2>
    <ul>
        <li><code>/</code> - This documentation page</li>
        <li><code>/badge/&lt;repository&gt;</code> - Get visitor badge for a specific repository</li>
    </ul>
</body>
</html>
"""

# Style configurations
plt.style.use('seaborn-v0_8-darkgrid')
BRAND_RED = '#e41a1c'
BACKGROUND_COLOR = '#ffffff'
GRID_COLOR = '#e0e0e0'
TEXT_COLOR = '#2d3436'
THRESHOLD_COLOR = '#34495e'


def init_db():
    conn = sqlite3.connect('visits.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS visits
                 (ip TEXT, timestamp TEXT, repository TEXT)''')
    conn.commit()
    conn.close()


@app.route('/')
def home():
    """Display documentation and usage instructions"""
    return render_template_string(HOME_PAGE)


def get_visit_stats(repository):
    conn = sqlite3.connect('visits.db')

    # Dynamic date range calculation - always gets last 7 days including today
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)

    query = '''
       SELECT 
           date(timestamp) as date,
           COUNT(DISTINCT ip) as visitors
       FROM visits
       WHERE 
           repository = ? AND
           date(timestamp) >= date('now', '-6 days')
       GROUP BY date(timestamp)
       ORDER BY date ASC
       '''

    df = pd.read_sql_query(query, conn, params=(repository,))
    df['date'] = pd.to_datetime(df['date'])

    # Fill in missing dates with zero visits
    date_range = pd.date_range(end=pd.Timestamp.now(), periods=7)
    df = df.set_index('date').reindex(date_range, fill_value=0)
    df = df.reset_index()
    df.columns = ['date', 'visitors']

    # Get all-time total unique visitors
    total_visitors = pd.read_sql_query('''
        SELECT COUNT(DISTINCT ip) as total
        FROM visits
        WHERE repository = ?
    ''', conn, params=(repository,)).iloc[0]['total']

    conn.close()
    return df, total_visitors


@app.route('/badge/<repository>')
def generate_badge(repository):
    # Record the visit
    visitor_ip = request.remote_addr
    conn = sqlite3.connect('visits.db')
    c = conn.cursor()
    c.execute('INSERT INTO visits VALUES (?, ?, ?)',
              (visitor_ip, datetime.now().isoformat(), repository))
    conn.commit()
    conn.close()

    # Get visit statistics
    df, total_visitors = get_visit_stats(repository)

    # Create the visualization with smaller dimensions
    fig, ax = plt.subplots(figsize=(4, 2), facecolor=BACKGROUND_COLOR)

    # Plot thinner bars
    bars = ax.bar(df['date'], df['visitors'],
                  color=BRAND_RED, alpha=0.8,
                  width=pd.Timedelta(days=0.5))  # Reduced width

    # Set y-axis thresholds
    max_visits = max(df['visitors'].max(), 200)  # At least show up to 200
    thresholds = [50, 100, 150, 200]
    thresholds = [t for t in thresholds if t <= max_visits * 1.2]

    ax.set_yticks(thresholds)
    ax.set_ylim(0, max(thresholds) * 1.2)

    # Add threshold lines
    for threshold in thresholds:
        ax.axhline(y=threshold, color=THRESHOLD_COLOR,
                   linestyle='--', alpha=0.3)

    # Customize appearance
    ax.set_facecolor(BACKGROUND_COLOR)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRID_COLOR)
    ax.spines['bottom'].set_color(GRID_COLOR)

    # Customize grid
    ax.grid(True, axis='y', linestyle='--', alpha=0.7, color=GRID_COLOR)

    # Format x-axis with improved date handling
    def format_date(x, p):
        date = mdates.num2date(x)
        if date.day == 1:
            # Show month name on the first day
            return date.strftime('%b %d')
        return date.strftime('%d')

    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_date))
    ax.xaxis.set_major_locator(mdates.DayLocator())

    # Add week boundary markers
    for date in df['date']:
        if date.weekday() == 0:  # Monday
            ax.axvline(x=date, color=GRID_COLOR,
                       linestyle=':', alpha=0.5)

    # Rotate and align date labels
    plt.xticks(df['date'], rotation=0, ha='center')

    # Ensure x-axis always shows exactly 7 days
    ax.set_xlim(df['date'].iloc[0] - pd.Timedelta(hours=12),
                df['date'].iloc[-1] + pd.Timedelta(hours=12))

    # Add total visits text with smaller font
    ax.text(0.98, 0.92, f'{total_visitors} Total Visits',
            transform=ax.transAxes,
            color=TEXT_COLOR,
            fontsize=8,
            fontweight='bold',
            ha='right')

    # Add website URL with smaller font
    plt.figtext(0.98, 0.02, 'blt.owasp.org',
                ha='right',
                color=TEXT_COLOR,
                fontsize=6,
                style='italic')

    # Adjust layout
    plt.tight_layout()

    # Save to SVG
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format='svg',
                bbox_inches='tight',
                dpi=300,
                facecolor=BACKGROUND_COLOR)
    plt.close()

    # Create response with headers
    response = Response(img_bytes.getvalue(), mimetype='image/svg+xml')

    # Add CORS and cache control headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=9090)