"""Risk brief for one stress run: deterministic HTML (all numbers come from the stored run) and, when WeasyPrint is installed,
a PDF of the same page. The narrative is the engine's template text: no model writes any number."""
from __future__ import annotations

from html import escape


class PdfUnavailable(RuntimeError):
    pass


def _m(x) -> str:
    return f"${x / 1e6:,.1f}m"


def _pct(a, b) -> str:
    return f"{(b - a) / abs(a) * 100:+.2f}%" if a else "n/a"


def _rows(items: list, key: str, n: int = 10) -> str:
    return "".join(f"<tr><td>{escape(str(i[key]).replace('_', ' '))}</td><td class='r'>{_m(i['delta'])}</td></tr>" for i in items[:n])


CSS = """body{font:13px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;margin:32px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:14px;margin:22px 0 6px;border-bottom:1px solid #ddd;padding-bottom:3px}
table{border-collapse:collapse;width:100%;margin:4px 0}td,th{padding:3px 8px;border-bottom:1px solid #eee;text-align:left}
.r{text-align:right;font-variant-numeric:tabular-nums}.k{display:flex;gap:28px;margin:12px 0}.k div{min-width:120px}
.k b{display:block;font-size:18px}.f{margin-top:26px;color:#666;font-size:11px}.tag{background:#fde68a;padding:1px 6px;border-radius:3px;font-size:11px}"""


def render_html(run: dict) -> str:
    vb, va = run["valueBefore"], run["valueAfter"]
    shocks = run.get("appliedShocks") or {}
    el = run.get("expectedLoss")
    body = [f"<h1>SENTINEL stress brief</h1><div>Run <code>{escape(run['id'])}</code> &middot; {escape(run['ts'])} &middot; "
            f"scenario <b>{escape(str(run['scenarioId']))}</b> ({escape(run['mode'])}) <span class='tag'>SYNTHETIC PORTFOLIO</span></div>",
            f"<p>{escape(run['narrative'])}</p>",
            f"<div class='k'><div>Book value before<b>{_m(vb)}</b></div><div>Book value after<b>{_m(va)}</b></div>"
            f"<div>Change<b>{_pct(vb, va)}</b></div><div>99% VaR (1d)<b>{_m(run['varBefore'])} &rarr; {_m(run['varAfter'])}</b></div>"
            f"<div>Expected shortfall<b>{_m(run['esBefore'])} &rarr; {_m(run['esAfter'])}</b></div></div>",
            "<h2>Attribution by risk factor (Shapley, order-independent)</h2><table>" + _rows(run["byFactor"], "factor") + "</table>",
            "<h2>By sector</h2><table>" + _rows(run["bySector"], "sector") + "</table>",
            "<h2>By country</h2><table>" + _rows(run["byCountry"], "country") + "</table>",
            "<h2>By asset class</h2><table><tr><th></th><th class='r'>Before</th><th class='r'>After</th></tr>" +
            "".join(f"<tr><td>{escape(a['assetClass'])}</td><td class='r'>{_m(a['before'])}</td><td class='r'>{_m(a['after'])}</td></tr>"
                    for a in run["byAssetClass"]) + "</table>"]
    if shocks:
        body.append("<h2>Applied factor shocks</h2><table>" + "".join(
            f"<tr><td>{escape(k.replace('_', ' '))}</td><td class='r'>{v:+.4g}</td></tr>" for k, v in sorted(shocks.items())) +
            "</table><div class='f'>Equity, FX and oil shocks are fractions; rates and spreads are basis points.</div>")
    if el:
        body.append(f"<h2>Expected credit loss (one year)</h2><p>{_m(el['before'])} &rarr; {_m(el['after'])} "
                    f"({el['delta'] / 1e6:+,.1f}m). <i>{escape(el['assumption'])}.</i></p>")
    body.append("<div class='f'>Risk analytics for demonstration, not investment advice. The wholesale banking book is synthetic by "
                "design; market levels and shocks come from real price, rate and spread history.</div>")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>SENTINEL stress brief {escape(run['id'])}</title><style>{CSS}</style></head><body>{''.join(body)}</body></html>"


def render_pdf(html: str) -> bytes:
    try:
        import weasyprint
    except Exception as e:                       # not installed, or its system libraries (pango) are missing
        raise PdfUnavailable(f"PDF rendering needs WeasyPrint: {e!r}")
    return weasyprint.HTML(string=html).write_pdf()
