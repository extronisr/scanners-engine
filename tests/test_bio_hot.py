"""Biotech 'hottest alerts' ordering: corroborated material events on top,
split/data artifacts excluded, trading-day dates, no duplicate cards."""
import generate as g


def _alert(sev, kind, ticker, head, date="2026-10-30", ts=1000.0, link="https://example.com"):
    return {"sev": sev, "kind": kind, "ticker": ticker, "name": ticker,
            "date": date, "ts": ts, "head": head, "sub": "", "link": link,
            "source": "T"}


def test_plausible_daily_chg_blocks_split_artifacts():
    assert g.plausible_daily_chg(-90.8)          # real biotech crash
    assert g.plausible_daily_chg(280.0)          # real FDA pop
    assert not g.plausible_daily_chg(3883.9)     # 1:40 reverse-split artifact
    assert not g.plausible_daily_chg(-99.999 if False else 600.0)


def test_sec_items_parsing_and_materiality():
    a = _alert("warn", "sec", "PTHS", "PTHS: דיווח 8-K חדש · סעיפים 1.01,2.03,7.01,9.01")
    assert g._sec_items(a) == {"1.01", "2.03", "7.01", "9.01"}
    assert g._sec_items(a) & g.BIO_MATERIAL_ITEMS
    plain = _alert("warn", "sec", "VIR", "VIR: דיווח 8-K חדש · סעיפים 5.02")
    assert not (g._sec_items(plain) & g.BIO_MATERIAL_ITEMS)


def test_fda_claim_unconfirmed_rule():
    issuer = _alert("info", "news", "NRXP",
                    "NRx Pharmaceuticals Receives FDA Approval of Preservative-Free Ketamine",
                    link="https://finance.yahoo.com/news/x")
    confirmed_src = _alert("info", "news", "INO", "FDA Approves First DNA Immunotherapy for RRP",
                           link="https://www.fda.gov/news-events/press-announcements/x")
    plain = _alert("info", "news", "X", "Company reports quarterly results")
    sec = _alert("warn", "sec", "Y", "Y: דיווח 8-K חדש · סעיפים 8.01")
    assert g.fda_claim_unconfirmed(issuer)
    assert not g.fda_claim_unconfirmed(confirmed_src)
    assert not g.fda_claim_unconfirmed(plain)
    assert not g.fda_claim_unconfirmed(sec)


def test_select_bio_hot_corroboration_order_and_repr():
    alerts = [
        # ABOS: crash + material 8-K + news -> top, SEC card is the representative
        _alert("crit", "price", "ABOS", "ABOS: ירידה חדה -90.8%"),
        _alert("warn", "sec", "ABOS", "ABOS: דיווח 8-K חדש · סעיפים 7.01,8.01,9.01", ts=1001),
        _alert("info", "news", "ABOS", "Acumen Ends Sabirnetug Alzheimer Program", ts=1002),
        # INO: price + news + breakthrough event
        _alert("crit", "price", "INO", "INO: ירידה חדה -22.1%"),
        _alert("info", "news", "INO", "Inovio surges 280% following FDA approval of Voceryq", ts=1003),
        # PMN: critical move but NO corroborating event -> not in the hot strip
        # (split/data anomalies hide among naked price moves; they stay in the feed)
        _alert("crit", "price", "PMN", "PMN: ירידה חדה -70.1%"),
        # LNAI: crit price + content-farm junk news -> junk never corroborates
        _alert("crit", "price", "LNAI", "LNAI: ירידה חדה -30.1%"),
        _alert("info", "news", "LNAI", "Lunai Bioworks Inc Balance Sheet - TradingView"),
        _alert("info", "news", "LNAI", "Senti Biosciences Seasonal returns chart - Yahoo"),
        # VIR: single weak signal -> NOT hot
        _alert("warn", "sec", "VIR", "VIR: דיווח 8-K חדש · סעיפים 5.02"),
        _alert("info", "news", "REGN", "REGN stock gains on Q3 beat"),
    ]
    bt = {"items": [{"tickers": ["INO"], "title": "FDA approves DNA immunotherapy"}]}
    hot = g.select_bio_hot(alerts, bt, n=5)
    tickers = [a["ticker"] for a in hot]
    assert tickers[0] == "ABOS"
    assert hot[0]["kind"] == "news"                   # the readable event card represents it
    assert "VIR" not in tickers and "REGN" not in tickers
    assert "PMN" not in tickers and "LNAI" not in tickers
    assert "INO" in tickers                           # price + event news + breakthrough
    assert len({id(a) for a in hot}) == len(hot)      # one card per ticker


def test_fda_verified_via_config_link_upgrades_card():
    import generate as g
    from datetime import datetime
    ino = _alert("info", "news", "INO",
                 "Inovio surges 280% following FDA approval of Voceryq for rare disease",
                 link="https://seekingalpha.com/x")
    ino2 = dict(ino)
    alerts = [ino, _alert("crit", "price", "INO", "INO: ירידה חדה -22.1%")]
    extra = {"overview": None, "cnn": None, "cats": None, "trials": None,
             "secw": None, "radar": [], "acc": None, "bt": None,
             "verified_fda": {"INO": "https://www.fda.gov/news-events/press-announcements/x"}}
    html = g.build_html(None, [], alerts, None, datetime.now(g.JER), extra)
    bio = html[html.index('id="pane-bio"'):html.index('id="pane-pulse"')]
    hot = bio[:bio.index("התראות רשימת המעקב")]
    assert "אומת: הודעת FDA רשמית" in hot
    assert "https://www.fda.gov/news-events/press-announcements/x" in hot
    assert "דיווח - לא אומת מול FDA" not in hot


def test_bio_pane_hot_section_renders_once_and_dedups(monkeypatch):
    from datetime import datetime
    alerts = [
        _alert("crit", "price", "ABOS", "ABOS: ירידה חדה -90.8%"),
        _alert("warn", "sec", "ABOS", "ABOS: דיווח 8-K חדש · סעיפים 7.01,8.01,9.01"),
        _alert("info", "news", "ABOS", "Acumen Ends Sabirnetug Alzheimer Program"),
        _alert("crit", "price", "PMN", "PMN: ירידה חדה -70.1%"),
        _alert("info", "news", "REGN", "REGN stock gains on Q3 beat"),
    ]
    extra = {"overview": None, "cnn": None, "cats": None, "trials": None,
             "secw": None, "radar": [], "acc": None, "bt": None}
    html = g.build_html(None, [], alerts, None, datetime.now(g.JER), extra)
    bio = html[html.index('id="pane-bio"'):html.index('id="pane-pulse"')]
    assert "ההתראות החמות" in bio
    assert bio.index("ההתראות החמות") < bio.index("פריצות דרך ביוטק") if "פריצות דרך ביוטק" in bio else True
    # hot representative appears exactly once in the whole pane
    assert bio.count("Acumen Ends Sabirnetug Alzheimer Program") == 1
    assert bio.count("ABOS: דיווח 8-K חדש · סעיפים 7.01,8.01,9.01") == 1  # stays in feed
    assert bio.count("PMN: ירידה חדה -70.1%") == 1   # price-only: in the feed, not hot
    # non-hot alert still in the feed
    assert "REGN stock gains on Q3 beat" in bio


# ---- representative card: an old headline must neither misrepresent nor hide a fresh material filing ----
NOW = 1_800_000_000.0
DAY = 86400.0


def _rep_for(*cards):
    # a critical price move corroborates a lone news/filing card so the ticker is hot
    corro = _alert("crit", "price", "TKR", "TKR: ירידה חדה -30.1%", ts=NOW)
    hot = g.select_bio_hot(list(cards) + [corro], None, n=5, now=NOW)
    assert len(hot) == 1
    return hot[0]


def _news(head, age_days, kind="news"):
    return _alert("info", kind, "TKR", head, ts=NOW - age_days * DAY)


def _sec(items, age_days):
    # EDGAR filing dates are midnight UTC of the filing day
    return _alert("warn", "sec", "TKR", f"TKR: דיווח 8-K חדש · סעיפים {items}",
                  ts=NOW - age_days * DAY)


def test_rep_old_event_news_does_not_hide_fresh_material_filing():
    old = _news("Tkr announces pricing of public offering", 4)
    fresh = _sec("1.01,9.01", 0.2)
    assert _rep_for(old, fresh) is fresh


def test_rep_fresh_news_is_not_replaced_by_a_filing():
    news = _news("Tkr announces pricing of public offering", 0.3)
    sec = _sec("1.01,9.01", 0.1)
    assert _rep_for(sec, news) is news


def test_rep_generic_filing_never_replaces_news():
    old = _news("Tkr announces pricing of public offering", 4)
    generic = _sec("5.02", 0.1)              # not a declared-material item
    price = _alert("crit", "price", "TKR", "TKR: ירידה חדה -30.1%", ts=NOW)
    assert _rep_for(old, generic, price) is old


def test_rep_old_filing_does_not_replace_news():
    news = _news("Tkr announces pricing of public offering", 0.5)
    old_sec = _sec("1.01", 6)
    assert _rep_for(old_sec, news) is news


def test_rep_both_old_keeps_previous_preference_and_unknown_time_counts_as_fresh():
    news = _news("Tkr announces pricing of public offering", 5)
    sec = _sec("1.01", 4)
    assert _rep_for(news, sec) is news       # both stale: unchanged behaviour
    undated = _alert("info", "news", "TKR", "Tkr announces pricing of public offering", ts=None)
    assert _rep_for(undated, _sec("1.01", 0.1)) is undated


def test_rep_filing_date_counts_to_end_of_day():
    # filed "today" (midnight UTC of the filing day is 20h ago) is fresh; filed 3.1 days ago (more than 48h after its end of day) is not
    old = _news("Tkr announces pricing of public offering", 4)
    assert _rep_for(old, _sec("8.01", 20 / 24)) is not old
    assert _rep_for(old, _sec("8.01", 3.1)) is old


def test_rep_picks_newest_of_several_event_headlines():
    a = _news("Tkr announces pricing of public offering", 3)
    b = _news("Tkr announces closing of public offering", 0.2)
    assert _rep_for(a, b) is b
