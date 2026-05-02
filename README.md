# Baseball

A Python utility to fetch today's MLB matchups using the [MLB Stats API](https://statsapi.mlb.com).

## Usage

```bash
# Show today's matchups
python baseball_news.py

# Show matchups for a specific date (YYYY-MM-DD)
python baseball_news.py 2025-05-02
```

## Example output

```
MLB Matchups for 2025-05-02
========================================
  New York Yankees @ Boston Red Sox
    Status : Scheduled
    Time   : 2025-05-02T23:05:00Z

  Los Angeles Dodgers @ San Francisco Giants
    Status : In Progress
    Time   : 2025-05-02T20:10:00Z
```

No external dependencies are required — only the Python standard library is used.
